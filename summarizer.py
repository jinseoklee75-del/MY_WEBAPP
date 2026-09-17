"""
Summarize a news article into three Korean bullet points.

Uses Claude (Anthropic SDK) when ANTHROPIC_API_KEY is configured; otherwise
falls back to a keyword-frequency extractive summary so the app always works.
"""
import os
import re
from collections import Counter

CLAUDE_MODEL = 'claude-opus-5'
MAX_INPUT_CHARS = 6000

_SYSTEM_PROMPT = (
    '당신은 경제 신문 기사를 요약하는 편집자입니다. '
    '주어진 기사를 한국어로 정확히 3개의 불릿으로 요약하세요. '
    '각 불릿은 "• "로 시작하는 한 문장(60자 내외)이며, 핵심 사실·수치·기업명·인물을 담아야 합니다. '
    '기사에 없는 내용을 추가하거나 추측하지 마세요. 불릿 3개 외에 다른 텍스트는 출력하지 마세요.'
)


def claude_available():
    return bool(os.environ.get('ANTHROPIC_API_KEY'))


def summarize(title, text, description=''):
    """Return (summary, method). method is 'claude' or 'extractive'."""
    body = (text or '').strip() or (description or '').strip()
    if not body:
        return '', 'none'
    if claude_available():
        try:
            return _summarize_with_claude(title, body), 'claude'
        except Exception as e:  # network / auth / rate limit -> degrade gracefully
            print(f'[summarizer] Claude failed, falling back to extractive: {e}')
    return _summarize_extractive(title, body), 'extractive'


# ---------------------------------------------------------------------------
# Claude
# ---------------------------------------------------------------------------

def _summarize_with_claude(title, body):
    import anthropic

    client = anthropic.Anthropic()
    user_content = f'제목: {title}\n\n본문:\n{body[:MAX_INPUT_CHARS]}'
    kwargs = dict(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        output_config={'effort': 'low'},
        messages=[{'role': 'user', 'content': user_content}],
    )
    try:
        # Server-side refusal fallback (routes to another model if the request is declined)
        response = client.beta.messages.create(
            betas=['server-side-fallback-2026-07-01'], fallbacks='default', **kwargs)
    except (TypeError, anthropic.BadRequestError):
        response = client.messages.create(**kwargs)

    if response.stop_reason == 'refusal':
        raise RuntimeError('Claude declined to summarize this article')
    parts = [block.text for block in response.content if block.type == 'text']
    summary = '\n'.join(parts).strip()
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    lines = [ln if ln.startswith('•') else '• ' + ln.lstrip('-*· ') for ln in lines]
    return '\n'.join(lines[:3])


# ---------------------------------------------------------------------------
# Extractive fallback (no external service)
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r'(?<=[다요임음됨죠][.!?])\s+|(?<=[.!?])\s+(?=[가-힣A-Z“"\'(\[])')
_TOKEN = re.compile(r'[가-힣A-Za-z0-9]{2,}')
_STOP = {'있다', '했다', '이다', '것으로', '대한', '위해', '통해', '이번', '지난', '관련', '기자', '대해',
         '경우', '때문', '있는', '하는', '으로', '에서', '에게', '한다', '됐다', '밝혔다', '말했다', '설명했다'}


def _split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s and len(s.strip()) > 15]
    return sents


def _summarize_extractive(title, body, n=3):
    sents = _split_sentences(body)
    if not sents:
        return '• ' + body[:120]
    if len(sents) <= n:
        return '\n'.join('• ' + _trim(s) for s in sents)

    freq = Counter()
    for s in sents:
        for tok in _TOKEN.findall(s):
            if tok not in _STOP:
                freq[tok] += 1
    title_tokens = set(_TOKEN.findall(title or ''))

    scored = []
    for idx, s in enumerate(sents):
        toks = _TOKEN.findall(s)
        if not toks:
            continue
        score = sum(freq[t] for t in toks if t not in _STOP) / (len(toks) ** 0.5)
        score += 2.0 * len(title_tokens.intersection(toks))   # matches the headline
        score *= 1.0 + max(0.0, 0.6 - idx * 0.06)              # lead sentences matter more
        scored.append((score, idx, s))

    top = sorted(scored, key=lambda x: -x[0])[:n]
    top.sort(key=lambda x: x[1])  # keep original order
    return '\n'.join('• ' + _trim(s) for _, _, s in top)


def _trim(sentence, limit=140):
    sentence = sentence.strip()
    return sentence if len(sentence) <= limit else sentence[:limit - 1].rstrip() + '…'
