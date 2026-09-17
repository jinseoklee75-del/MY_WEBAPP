"""
End-to-end check for the AI 뉴스 브리핑 app.

Usage:
    python verify_app.py                      # against http://127.0.0.1:5000
    python verify_app.py https://20260927v.vercel.app
"""
import json
import sys
import urllib.request

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:5000'


def call(method, path, body=None):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(f'{BASE_URL}{path}', data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode('utf-8')
        return resp.status, (json.loads(raw) if raw.startswith('{') else raw)


def test_app():
    print(f'=== AI 뉴스 브리핑 검증 시작 ({BASE_URL}) ===')

    print('\n1. 메인 페이지 (GET /)')
    status, html = call('GET', '/')
    assert status == 200 and 'AI' in html and '뉴스 브리핑' in html
    print('  ✓ 200 OK, 페이지 타이틀 확인')

    print('\n2. DB 연결 (GET /api/health)')
    status, data = call('GET', '/api/health')
    assert data['connected'] is True, data
    print(f"  ✓ {data['db']['provider']} 연결됨 ({data['db']['host']})")

    print('\n3. 통계 (GET /api/stats)')
    status, data = call('GET', '/api/stats')
    s = data['stats']
    assert data['success'] and set(['total', 'done', 'pending', 'mk', 'hk']).issubset(s)
    print(f"  ✓ 전체 {s['total']} / 매경 {s['mk']} / 한경 {s['hk']} / 요약완료 {s['done']} / 대기 {s['pending']} / 엔진 {s['summarizer']}")

    print('\n4. 기사 수집 (POST /api/refresh)')
    status, data = call('POST', '/api/refresh')
    assert data['success'], data
    print(f"  ✓ 신규 {data['inserted']}건, 요약 {data['processed']}건, 남은 대기 {data['remaining']}건")

    print('\n5. 요약 처리 (POST /api/process)')
    status, data = call('POST', '/api/process')
    assert data['success'], data
    print(f"  ✓ 요약 {data['processed']}건, 제외 {data['skipped']}건, 실패 {data['failed']}건, 남은 대기 {data['remaining']}건")

    print('\n6. 기사 목록 (GET /api/articles)')
    status, data = call('GET', '/api/articles')
    arts = data['articles']
    assert data['success'] and isinstance(arts, list)
    sources = {a['source'] for a in arts}
    assert sources.issubset({'매일경제', '한국경제'}), sources
    done = [a for a in arts if a['status'] == 'done']
    print(f"  ✓ {len(arts)}건 조회 (출처: {', '.join(sorted(sources)) or '-'}), 요약 완료 {len(done)}건")
    if done:
        a = done[0]
        print(f"     예) [{a['source']}] {a['title']}\n        " + a['summary'].replace('\n', '\n        '))

    print('\n7. 출처 필터 + 검색 (GET /api/articles?source=매일경제&search=AI)')
    status, data = call('GET', '/api/articles?source=%EB%A7%A4%EC%9D%BC%EA%B2%BD%EC%A0%9C&search=AI')
    assert data['success'] and all(a['source'] == '매일경제' for a in data['articles'])
    print(f"  ✓ 매일경제 + 'AI' 검색 결과 {len(data['articles'])}건")

    print('\n🎉 모든 검증을 통과했습니다!')


if __name__ == '__main__':
    test_app()
