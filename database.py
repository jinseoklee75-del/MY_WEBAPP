import os
from datetime import datetime, date, timedelta, timezone

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# Supabase (PostgreSQL) connection string.
# Locally it is read from .env.local (see app.py); on Vercel it is an env var.
DATABASE_URL = os.environ.get('DATABASE_URL')

KST = timezone(timedelta(hours=9))


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL 환경변수가 설정되어 있지 않습니다.')
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def check_connection():
    """Ping the database and report where the app is connected."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT version() AS version, current_database() AS db')
    row = cursor.fetchone()
    conn.close()
    host = DATABASE_URL.split('@')[-1].split('/')[0]
    return {
        'provider': 'Supabase' if 'supabase' in host else 'PostgreSQL',
        'host': host,
        'database': row['db'],
        'version': row['version'].split(',')[0],
    }


def _serialize(row):
    """Convert a DB row to a JSON-friendly dict (timestamps -> ISO strings in KST)."""
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            out[key] = value.astimezone(KST).isoformat()
        elif isinstance(value, date):
            out[key] = value.isoformat()
    return out


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            gnews_url TEXT NOT NULL UNIQUE,
            url TEXT,
            published_at TIMESTAMPTZ NOT NULL,
            description TEXT DEFAULT '',
            content TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            summary_method TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT DEFAULT '',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            processed_at TIMESTAMPTZ
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_published ON articles (published_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    ''')
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Meta (last refresh time etc.)
# ---------------------------------------------------------------------------

def get_meta(key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value, updated_at FROM app_meta WHERE key = %s', (key,))
    row = cursor.fetchone()
    conn.close()
    return _serialize(row)


def set_meta(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO app_meta (key, value, updated_at) VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    ''', (key, value))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------

def upsert_candidates(candidates):
    """Insert newly discovered articles; returns the number actually inserted."""
    if not candidates:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    rows = [(c['source'], c['title'], c['gnews_url'], c['published_at']) for c in candidates]
    execute_values(cursor, '''
        INSERT INTO articles (source, title, gnews_url, published_at)
        VALUES %s
        ON CONFLICT (gnews_url) DO NOTHING
    ''', rows, page_size=1000)
    inserted = cursor.rowcount
    conn.commit()
    conn.close()
    return inserted


def get_pending(limit=3, days=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, source, title, gnews_url, published_at
        FROM articles
        WHERE status = 'pending' AND published_at >= NOW() - (%s || ' days')::interval
        ORDER BY published_at DESC
        LIMIT %s
    ''', (str(days), limit))
    rows = [_serialize(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def count_pending(days=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) AS n FROM articles
        WHERE status = 'pending' AND published_at >= NOW() - (%s || ' days')::interval
    ''', (str(days),))
    n = cursor.fetchone()['n']
    conn.close()
    return n


def mark_done(article_id, url, description, content, summary, method):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE articles
        SET url = %s, description = %s, content = %s, summary = %s, summary_method = %s,
            status = 'done', error = '', processed_at = NOW()
        WHERE id = %s
    ''', (url, description, content, summary, method, article_id))
    conn.commit()
    conn.close()


def mark_status(article_id, status, error='', url=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE articles
        SET status = %s, error = %s, url = COALESCE(%s, url), processed_at = NOW()
        WHERE id = %s
    ''', (status, error[:500], url, article_id))
    conn.commit()
    conn.close()


def get_articles(source=None, search=None, days=3, include_pending=True):
    conn = get_connection()
    cursor = conn.cursor()
    query = '''
        SELECT id, source, title, gnews_url, url, published_at, description, summary,
               summary_method, status, processed_at
        FROM articles
        WHERE published_at >= NOW() - (%s || ' days')::interval
          AND status <> 'skipped'
    '''
    params = [str(days)]
    if not include_pending:
        query += " AND status = 'done'"
    if source and source != 'all':
        query += ' AND source = %s'
        params.append(source)
    if search:
        query += ' AND (title ILIKE %s OR summary ILIKE %s)'
        params.extend([f'%{search}%', f'%{search}%'])
    query += ' ORDER BY published_at DESC, id DESC'
    cursor.execute(query, params)
    rows = [_serialize(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_stats(days=3):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            COUNT(*) FILTER (WHERE status <> 'skipped')                          AS total,
            COUNT(*) FILTER (WHERE status = 'done')                              AS done,
            COUNT(*) FILTER (WHERE status = 'pending')                           AS pending,
            COUNT(*) FILTER (WHERE status = 'failed')                            AS failed,
            COUNT(*) FILTER (WHERE source = '매일경제' AND status <> 'skipped')   AS mk,
            COUNT(*) FILTER (WHERE source = '한국경제' AND status <> 'skipped')   AS hk,
            COUNT(*) FILTER (WHERE summary_method = 'claude')                    AS claude
        FROM articles
        WHERE published_at >= NOW() - (%s || ' days')::interval
    ''', (str(days),))
    row = dict(cursor.fetchone())
    conn.close()
    meta = get_meta('last_refresh')
    row['last_refresh'] = meta['updated_at'] if meta else None
    return row


def purge_old(days=7):
    """Delete articles older than the retention window so the free-tier DB stays small."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM articles WHERE published_at < NOW() - (%s || ' days')::interval", (str(days),))
    n = cursor.rowcount
    conn.commit()
    conn.close()
    return n
