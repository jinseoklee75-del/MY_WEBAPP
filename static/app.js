/**
 * AI 뉴스 브리핑 - Frontend (Vanilla JS)
 *
 * Flow on load:
 *   1. fetch stats + article list and render immediately
 *   2. call /api/refresh (discover new articles), then /api/process repeatedly
 *      until nothing is pending - the list re-renders as summaries arrive.
 */

const state = {
    articles: [],
    source: 'all',          // 'all' | '매일경제' | '한국경제'
    searchQuery: '',
    pipelineRunning: false,
};

const el = {
    currentDateDisplay: document.getElementById('currentDateDisplay'),
    dbStatus: document.getElementById('dbStatus'),
    dbStatusText: document.getElementById('dbStatusText'),
    footerDbInfo: document.getElementById('footerDbInfo'),
    footerSummarizer: document.getElementById('footerSummarizer'),
    statTotal: document.getElementById('statTotal'),
    statMk: document.getElementById('statMk'),
    statHk: document.getElementById('statHk'),
    statRateText: document.getElementById('statRateText'),
    statProgressBar: document.getElementById('statProgressBar'),
    statFootnote: document.getElementById('statFootnote'),
    badgeAll: document.getElementById('badgeAll'),
    badgeMk: document.getElementById('badgeMk'),
    badgeHk: document.getElementById('badgeHk'),
    searchInput: document.getElementById('searchInput'),
    btnClearSearch: document.getElementById('btnClearSearch'),
    btnRefresh: document.getElementById('btnRefresh'),
    btnRefreshText: document.getElementById('btnRefreshText'),
    pipelineBar: document.getElementById('pipelineBar'),
    pipelineText: document.getElementById('pipelineText'),
    articleList: document.getElementById('articleList'),
    emptyState: document.getElementById('emptyState'),
    toastContainer: document.getElementById('toastContainer'),
};

document.addEventListener('DOMContentLoaded', async () => {
    setupDateDisplay();
    setupEventListeners();
    fetchDbHealth();
    await Promise.all([fetchStats(), fetchArticles()]);
    runPipeline({ discover: true, silent: true });
});

function setupDateDisplay() {
    const now = new Date();
    el.currentDateDisplay.textContent = now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
}

function setupEventListeners() {
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.source = tab.dataset.source;
            fetchArticles();
        });
    });

    let searchTimer;
    el.searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.searchQuery = e.target.value.trim();
            el.btnClearSearch.style.display = state.searchQuery ? 'block' : 'none';
            fetchArticles();
        }, 300);
    });
    el.btnClearSearch.addEventListener('click', () => {
        el.searchInput.value = '';
        state.searchQuery = '';
        el.btnClearSearch.style.display = 'none';
        fetchArticles();
    });

    el.btnRefresh.addEventListener('click', () => runPipeline({ discover: true, silent: false }));
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function fetchDbHealth() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        if (!data.connected) throw new Error(data.error || 'DB 연결 실패');
        el.dbStatus.classList.add('is-connected');
        el.dbStatusText.textContent = `${data.db.provider} 연결됨`;
        el.dbStatus.title = `${data.db.host} / ${data.db.database} (${data.db.version})`;
        el.footerDbInfo.textContent = `DB: ${data.db.host}`;
    } catch (err) {
        el.dbStatus.classList.add('is-error');
        el.dbStatusText.textContent = 'DB 연결 안 됨';
        el.footerDbInfo.textContent = 'DB 연결 실패';
        console.error('DB 상태 확인 실패:', err);
    }
}

async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const { stats } = await res.json();
        const total = stats.total || 0;
        const done = stats.done || 0;
        const rate = total ? Math.round((done / total) * 100) : 0;

        el.statTotal.textContent = total;
        el.statMk.textContent = stats.mk || 0;
        el.statHk.textContent = stats.hk || 0;
        el.statRateText.textContent = `${rate}%`;
        el.statProgressBar.style.width = `${rate}%`;
        el.statFootnote.textContent = stats.pending
            ? `요약 대기 ${stats.pending}건${stats.failed ? ` · 실패 ${stats.failed}건` : ''}`
            : (stats.failed ? `실패 ${stats.failed}건` : '모든 기사 요약 완료');
        el.badgeAll.textContent = total;
        el.badgeMk.textContent = stats.mk || 0;
        el.badgeHk.textContent = stats.hk || 0;

        el.footerSummarizer.textContent = stats.summarizer === 'claude'
            ? '요약 엔진: Claude (Anthropic API)'
            : '요약 엔진: 핵심 문장 추출 (ANTHROPIC_API_KEY를 설정하면 Claude AI 요약으로 자동 전환됩니다)';
        return stats;
    } catch (err) {
        console.error('통계 불러오기 실패:', err);
        return null;
    }
}

async function fetchArticles() {
    try {
        const params = new URLSearchParams({ source: state.source });
        if (state.searchQuery) params.set('search', state.searchQuery);
        const res = await fetch(`/api/articles?${params}`);
        const data = await res.json();
        state.articles = data.articles || [];
        renderArticles();
    } catch (err) {
        console.error('기사 불러오기 실패:', err);
        showToast('기사를 불러오지 못했습니다.', 'error');
    }
}

// ---------------------------------------------------------------------------
// Pipeline: discover new articles, then process pending ones in small batches
// ---------------------------------------------------------------------------

async function runPipeline({ discover, silent }) {
    if (state.pipelineRunning) return;
    state.pipelineRunning = true;
    setPipelineUI(true, discover ? '매일경제·한국경제에서 새 AI 기사를 확인하고 있습니다...' : '요약을 생성하고 있습니다...');

    let totalProcessed = 0, totalInserted = 0, rounds = 0;
    try {
        let remaining = 0;
        if (discover) {
            const r = await postJson('/api/refresh');
            totalInserted = r.inserted || 0;
            totalProcessed += r.processed || 0;
            remaining = r.remaining || 0;
            if (r.errors && r.errors.length) console.warn('discover errors', r.errors);
        } else {
            remaining = 1;
        }

        await Promise.all([fetchStats(), fetchArticles()]);

        while (remaining > 0 && rounds < 120) {
            rounds += 1;
            setPipelineUI(true, `기사 요약 생성 중... (남은 기사 ${remaining}건)`);
            const r = await postJson('/api/process');
            totalProcessed += r.processed || 0;
            remaining = r.remaining || 0;
            if ((r.processed || 0) + (r.skipped || 0) + (r.failed || 0) === 0) break; // nothing moved -> stop
            await Promise.all([fetchStats(), fetchArticles()]);
        }

        if (!silent || totalInserted || totalProcessed) {
            showToast(
                totalInserted || totalProcessed
                    ? `새 기사 ${totalInserted}건 수집, ${totalProcessed}건 요약 완료`
                    : '새로운 AI 기사가 없습니다. 최신 상태입니다.',
                'success'
            );
        }
    } catch (err) {
        console.error('파이프라인 오류:', err);
        showToast('기사 업데이트 중 오류가 발생했습니다.', 'error');
    } finally {
        state.pipelineRunning = false;
        setPipelineUI(false);
        await Promise.all([fetchStats(), fetchArticles()]);
    }
}

async function postJson(url) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    if (!res.ok) throw new Error(`${url} -> HTTP ${res.status}`);
    return res.json();
}

function setPipelineUI(running, text) {
    el.pipelineBar.classList.toggle('hidden', !running);
    if (text) el.pipelineText.textContent = text;
    el.btnRefresh.disabled = running;
    el.btnRefreshText.textContent = running ? '업데이트 중...' : '기사 업데이트';
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderArticles() {
    el.articleList.innerHTML = '';
    if (!state.articles.length) {
        el.emptyState.classList.remove('hidden');
        return;
    }
    el.emptyState.classList.add('hidden');

    // group by publish date (KST)
    const groups = new Map();
    for (const a of state.articles) {
        const key = a.published_at.slice(0, 10);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(a);
    }

    for (const [dateKey, items] of groups) {
        const header = document.createElement('div');
        header.className = 'date-header';
        header.innerHTML = `<span class="date-label">${dateLabel(dateKey)}</span><span class="date-count">${items.length}건</span>`;
        el.articleList.appendChild(header);
        for (const a of items) el.articleList.appendChild(createArticleCard(a));
    }
}

function createArticleCard(a) {
    const card = document.createElement('article');
    card.className = `article-card ${a.status !== 'done' ? 'is-pending' : ''}`;
    const sourceClass = a.source === '매일경제' ? 'badge-mk' : 'badge-hk';
    const link = a.url || a.gnews_url;

    let summaryHtml;
    if (a.status === 'done' && a.summary) {
        const lines = a.summary.split('\n').map(s => s.replace(/^[•\-*·]\s*/, '').trim()).filter(Boolean);
        summaryHtml = `<ul class="summary-list">${lines.map(l => `<li>${escapeHtml(l)}</li>`).join('')}</ul>`;
    } else if (a.status === 'failed') {
        summaryHtml = `<p class="summary-pending is-failed">요약을 생성하지 못했습니다. 원문 링크로 확인해 주세요.</p>`;
    } else {
        summaryHtml = `<p class="summary-pending"><span class="spinner small"></span> 요약 생성 대기 중...</p>`;
    }

    const methodBadge = a.status === 'done'
        ? `<span class="badge-tag badge-method">${a.summary_method === 'claude' ? '✨ Claude 요약' : '📝 핵심문장 요약'}</span>`
        : '';

    card.innerHTML = `
        <div class="article-head">
            <span class="badge-tag ${sourceClass}">${escapeHtml(a.source)}</span>
            <span class="article-time">${timeLabel(a.published_at)}</span>
        </div>
        <h3 class="article-title"><a href="${escapeAttr(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.title)}</a></h3>
        ${summaryHtml}
        <div class="article-foot">
            ${methodBadge}
            <a class="link-original" href="${escapeAttr(link)}" target="_blank" rel="noopener noreferrer">원문 보기 ↗</a>
        </div>
    `;
    return card;
}

function dateLabel(dateKey) {
    const today = new Date();
    const d = new Date(dateKey + 'T00:00:00+09:00');
    const todayKey = toKstKey(today);
    const yesterdayKey = toKstKey(new Date(today.getTime() - 86400000));
    const dayBeforeKey = toKstKey(new Date(today.getTime() - 2 * 86400000));
    const pretty = d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short', timeZone: 'Asia/Seoul' });
    if (dateKey === todayKey) return `오늘 · ${pretty}`;
    if (dateKey === yesterdayKey) return `어제 · ${pretty}`;
    if (dateKey === dayBeforeKey) return `그저께 · ${pretty}`;
    return pretty;
}

function toKstKey(date) {
    return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
}

function timeLabel(iso) {
    const d = new Date(iso);
    return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Seoul' });
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    el.toastContainer.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function escapeAttr(text) {
    return escapeHtml(text).replace(/"/g, '&quot;');
}
