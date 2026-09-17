import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Local development: load env vars from .env.local (pulled via `vercel env pull`)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.local'))

from flask import Flask, render_template, request, jsonify
import database
import news_fetcher
import summarizer

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Serverless functions have a hard wall-clock limit; keep each request under this.
REQUEST_TIME_BUDGET = float(os.environ.get('REQUEST_TIME_BUDGET', '8'))
# Articles processed concurrently per wave
PARALLEL = int(os.environ.get('PROCESS_PARALLEL', '6'))

# Ensure DB schema exists
with app.app_context():
    database.init_db()


@app.route('/')
def index():
    return render_template('index.html')


# ---------------------------------------------------------------------------
# Read APIs
# ---------------------------------------------------------------------------

@app.route('/api/articles', methods=['GET'])
def list_articles():
    source = request.args.get('source', 'all')
    search = (request.args.get('search') or '').strip() or None
    articles = database.get_articles(source=source, search=search, days=news_fetcher.DAYS_BACK)
    return jsonify({'success': True, 'articles': articles, 'days': news_fetcher.DAYS_BACK})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = database.get_stats(days=news_fetcher.DAYS_BACK)
    stats['summarizer'] = 'claude' if summarizer.claude_available() else 'extractive'
    stats['sources'] = list(news_fetcher.SOURCES.keys())
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/health', methods=['GET'])
def health():
    try:
        info = database.check_connection()
        return jsonify({'success': True, 'connected': True, 'db': info})
    except Exception as e:
        return jsonify({'success': False, 'connected': False, 'error': str(e)}), 503


# ---------------------------------------------------------------------------
# Pipeline: discover -> process (resolve URL, fetch body, summarize)
# ---------------------------------------------------------------------------

def _discover_all():
    """Pull the Google News feeds for every source and store new candidates."""
    inserted = 0
    errors = []
    for source in news_fetcher.SOURCES:
        try:
            candidates = news_fetcher.discover(source, days=news_fetcher.DAYS_BACK)
            inserted += database.upsert_candidates(candidates)
        except Exception as e:
            errors.append(f'{source}: {e}')
    database.set_meta('last_refresh', str(inserted))
    return inserted, errors


def _process_one(item):
    """Resolve, fetch and summarize a single pending article."""
    url = news_fetcher.decode_gnews_url(item['gnews_url'])
    if not url:
        raise RuntimeError('원문 URL을 확인할 수 없습니다')
    article = news_fetcher.fetch_article(url)
    text, description = article['text'], article['description']
    if not news_fetcher.is_ai_related(item['title'], description, text[:1500]):
        database.mark_status(item['id'], 'skipped', 'AI 관련 기사가 아님', url=url)
        return 'skipped'
    summary, method = summarizer.summarize(item['title'], text, description)
    if not summary:
        raise RuntimeError('본문을 추출하지 못했습니다')
    database.mark_done(item['id'], url, description, text[:20000], summary, method)
    return 'done'


def _process_safely(item):
    try:
        return _process_one(item)
    except Exception as e:
        database.mark_status(item['id'], 'failed', str(e))
        return 'failed'


def _process_batch(started_at, max_items=None):
    """Process pending articles in parallel until the time budget is nearly used up."""
    processed = skipped = failed = 0
    # one wave = PARALLEL articles resolved/fetched/summarized concurrently (I/O bound)
    wave_seconds = 6.0 if summarizer.claude_available() else 3.5
    while True:
        elapsed = time.time() - started_at
        if elapsed + wave_seconds > REQUEST_TIME_BUDGET:
            break
        if max_items is not None and processed + skipped + failed >= max_items:
            break
        pending = database.get_pending(limit=PARALLEL, days=news_fetcher.DAYS_BACK)
        if not pending:
            break
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            for result in pool.map(_process_safely, pending):
                if result == 'done':
                    processed += 1
                elif result == 'skipped':
                    skipped += 1
                else:
                    failed += 1
    return processed, skipped, failed


@app.route('/api/refresh', methods=['POST'])
def refresh():
    started = time.time()
    inserted, errors = _discover_all()
    processed, skipped, failed = _process_batch(started)
    return jsonify({
        'success': True,
        'inserted': inserted,
        'processed': processed,
        'skipped': skipped,
        'failed': failed,
        'remaining': database.count_pending(days=news_fetcher.DAYS_BACK),
        'errors': errors,
    })


@app.route('/api/process', methods=['POST'])
def process():
    started = time.time()
    processed, skipped, failed = _process_batch(started)
    return jsonify({
        'success': True,
        'processed': processed,
        'skipped': skipped,
        'failed': failed,
        'remaining': database.count_pending(days=news_fetcher.DAYS_BACK),
    })


@app.route('/api/cron', methods=['GET'])
def cron():
    """Called by Vercel Cron once a day: discover new articles and process a few."""
    secret = os.environ.get('CRON_SECRET')
    if secret and request.headers.get('Authorization') != f'Bearer {secret}':
        return jsonify({'success': False, 'error': 'unauthorized'}), 401
    started = time.time()
    purged = database.purge_old(days=7)
    inserted, errors = _discover_all()
    processed, skipped, failed = _process_batch(started)
    return jsonify({'success': True, 'purged': purged, 'inserted': inserted, 'processed': processed,
                    'skipped': skipped, 'failed': failed,
                    'remaining': database.count_pending(days=news_fetcher.DAYS_BACK), 'errors': errors})


if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[Flask] AI News Briefing server started: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
