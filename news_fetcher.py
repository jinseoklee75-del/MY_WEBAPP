"""
Discover and fetch AI-related news articles from 매일경제 / 한국경제.

Discovery uses Google News RSS (site-restricted, last 3 days, keyword "AI"),
because the publishers' own RSS feeds only expose the latest ~50 items of the
current day. Google News links are redirects, so they are decoded back to the
original article URL before the article body is fetched.
"""
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0 Safari/537.36')
HEADERS = {'User-Agent': USER_AGENT, 'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.5'}

SOURCES = {
    '매일경제': {'domain': 'mk.co.kr', 'home': 'https://www.mk.co.kr'},
    '한국경제': {'domain': 'hankyung.com', 'home': 'https://www.hankyung.com'},
}

DAYS_BACK = 3

# An article is kept only if its title or body mentions one of these.
AI_KEYWORDS = [
    'AI', 'A.I', '인공지능', '생성형', 'LLM', '거대언어모델', '대규모언어모델', 'GPT', '챗GPT',
    '클로드', 'Claude', '제미나이', 'Gemini', '오픈AI', 'OpenAI', '앤스로픽', 'Anthropic',
    '딥러닝', '머신러닝', '기계학습', 'AI반도체', 'AI 반도체', '에이전트', 'Agent', '코파일럿', 'Copilot',
    '딥시크', 'DeepSeek', '엔비디아', 'NVIDIA', 'HBM', '휴머노이드', '자율주행',
]
_KEYWORD_RE = re.compile('|'.join(re.escape(k) for k in AI_KEYWORDS), re.IGNORECASE)


def _http_get(url, timeout=10, data=None, extra_headers=None):
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', 'ignore')


def is_ai_related(*texts):
    return any(t and _KEYWORD_RE.search(t) for t in texts)


# ---------------------------------------------------------------------------
# Discovery via Google News RSS
# ---------------------------------------------------------------------------

def gnews_feed_url(domain, term='AI', after=None, before=None, days=DAYS_BACK):
    """Google News search feed. With after/before (date objects) the window is explicit."""
    if after and before:
        query = f'{term} site:{domain} after:{after.isoformat()} before:{before.isoformat()}'
    else:
        query = f'{term} site:{domain} when:{days}d'
    return ('https://news.google.com/rss/search?'
            + urllib.parse.urlencode({'q': query, 'hl': 'ko', 'gl': 'KR', 'ceid': 'KR:ko'}))


def _clean_title(title, source):
    title = re.sub(r'<.*?>', '', title).strip()
    # Google News appends " - 매일경제", " - 매일경제 마켓", " - 한국경제" ...
    title = re.sub(r'\s*[-|–]\s*[^-|–]*' + re.escape(source) + r'[^-|–]*$', '', title)
    return title.strip()


def _parse_feed(xml, source, cutoff_ts):
    items = re.findall(r'<item>(.*?)</item>', xml, re.S)
    results = []
    for item in items:
        title_m = re.search(r'<title>(.*?)</title>', item, re.S)
        link_m = re.search(r'<link>(.*?)</link>', item, re.S)
        date_m = re.search(r'<pubDate>(.*?)</pubDate>', item, re.S)
        if not (title_m and link_m and date_m):
            continue
        try:
            published = parsedate_to_datetime(date_m.group(1).strip())
        except Exception:
            continue
        if published.timestamp() < cutoff_ts:
            continue
        title = _clean_title(title_m.group(1), source)
        if not title:
            continue
        results.append({
            'source': source,
            'title': title,
            'gnews_url': link_m.group(1).strip(),
            'published_at': published,
        })
    return results


def discover(source, days=DAYS_BACK):
    """Return candidate AI articles for one source.

    Google News caps every feed at 100 items and pads date-restricted queries
    with loosely related results, so several feeds are merged (different search
    terms + one window per day) and only items whose *headline* mentions AI are
    kept. That headline rule is what defines "AI 기사" for this app.
    """
    domain = SOURCES[source]['domain']
    now = datetime.now(timezone.utc)
    cutoff_ts = now.timestamp() - days * 86400
    today = now.date()

    urls = [gnews_feed_url(domain, term=t, days=days) for t in ('AI', '인공지능', 'intitle:AI')]
    for i in range(days, -1, -1):
        urls.append(gnews_feed_url(domain, term='AI', after=today - timedelta(days=i), before=today - timedelta(days=i - 2)))

    found = {}
    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        for xml in pool.map(lambda u: _safe_get(u, 12), urls):
            if not xml:
                continue
            for cand in _parse_feed(xml, source, cutoff_ts):
                if is_ai_related(cand['title']):
                    found.setdefault(cand['gnews_url'], cand)
    return list(found.values())


def _safe_get(url, timeout):
    try:
        return _http_get(url, timeout=timeout)
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# Resolve Google News redirect -> original article URL
# ---------------------------------------------------------------------------

def decode_gnews_url(gnews_url, timeout=8):
    m = re.search(r'/articles/([^?/]+)', gnews_url)
    if not m:
        return None
    art_id = m.group(1)
    page = _http_get(f'https://news.google.com/rss/articles/{art_id}', timeout=timeout)
    sig = re.search(r'data-n-a-sg="([^"]+)"', page)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sig and ts):
        return None
    inner = [
        'garturlreq',
        [['ko', 'KR', ['FINANCE_TOP_INDICES', 'WEB_TEST_1_0_0'], None, None, 1, 1, 'KR:ko', None, 180,
          None, None, None, None, None, 0, None, None, [1608992183, 723341000]],
         'ko', 'KR', 1, [2, 3, 4, 8], 1, 0, '655000234', 0, 0, None, 0],
        art_id, int(ts.group(1)), sig.group(1),
    ]
    payload = [[['Fbv4je', json.dumps(inner), None, 'generic']]]
    body = urllib.parse.urlencode({'f.req': json.dumps(payload)}).encode()
    resp = _http_get('https://news.google.com/_/DotsSplashUi/data/batchexecute', timeout=timeout, data=body,
                     extra_headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})
    m = re.search(r'(https?://[a-z0-9.-]*(?:mk\.co\.kr|hankyung\.com)/[^\s"\\]+)', resp)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Article body extraction
# ---------------------------------------------------------------------------

_BODY_SELECTORS = {
    'mk.co.kr': ['div.news_cnt_detail_wrap', 'div.news_detail_wrap', 'section#news_body',
                 '[itemprop="articleBody"]', 'div#article_body'],
    'hankyung.com': ['div#articletxt', 'div.article-body', '[itemprop="articleBody"]'],
}


def fetch_article(url, timeout=8):
    """Return {'text': ..., 'description': ...} for an original article URL."""
    html = _http_get(url, timeout=timeout)
    soup = BeautifulSoup(html, 'html.parser')

    og = soup.find('meta', property='og:description')
    description = og['content'].strip() if og and og.get('content') else ''

    for tag in soup(['script', 'style', 'noscript', 'iframe', 'figure', 'figcaption', 'table']):
        tag.decompose()

    selectors = []
    for domain, sels in _BODY_SELECTORS.items():
        if domain in url:
            selectors = sels
    node = None
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            break
    text = ''
    if node:
        text = node.get_text('\n', strip=True)
        text = re.sub(r'\n{2,}', '\n', text)
        # drop trailing reporter/email lines and share widgets
        text = re.sub(r'\n[^\n]*(기자|@|▶|Copyright|무단 전재)[^\n]*$', '', text).strip()
    return {'text': text, 'description': description}
