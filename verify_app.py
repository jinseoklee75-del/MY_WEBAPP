import urllib.request
import json
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = 'http://127.0.0.1:5000'

def test_app():
    print("=== TaskFlow WebApp 검증 시작 ===")
    
    # 1. Main Page Check
    print("\n1. 메인 웹 페이지 (GET /) 요청 테스트...")
    req = urllib.request.Request(f"{BASE_URL}/")
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8')
        assert resp.status == 200, f"예상치 못한 상태 코드: {resp.status}"
        assert 'TaskFlow' in html, "페이지 내 TaskFlow 타이틀 누락"
        assert '새로운 할일 등록' in html, "페이지 내 할일 등록 UI 누락"
        print("  ✓ 메인 HTML 페이지 정상 응답 (Status: 200 OK)")

    # 2. Get Todos List
    print("\n2. 할일 목록 조회 (GET /api/todos) 테스트...")
    req = urllib.request.Request(f"{BASE_URL}/api/todos")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "할일 목록 조회 실패"
        initial_count = len(data['todos'])
        print(f"  ✓ 초기 할일 {initial_count}개 정상 조회됨")

    # 3. Create Todo
    print("\n3. 새로운 할일 등록 (POST /api/todos) 테스트...")
    new_todo_payload = {
        "title": "자동화 검증 테스트 항목",
        "description": "Flask 웹앱 기능 검증 스크립트로 자동 생성됨",
        "category": "테스트",
        "priority": "high",
        "due_date": "2026-09-20"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/todos",
        data=json.dumps(new_todo_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "할일 등록 실패"
        created_id = data['todo']['id']
        assert data['todo']['title'] == new_todo_payload['title']
        print(f"  ✓ 할일 등록 성공 (ID: {created_id}, Title: '{data['todo']['title']}')")

    # 4. Toggle Todo Status
    print(f"\n4. 할일 상태 토글 (PATCH /api/todos/{created_id}/toggle) 테스트...")
    req = urllib.request.Request(
        f"{BASE_URL}/api/todos/{created_id}/toggle",
        headers={'Content-Type': 'application/json'},
        method='PATCH'
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "할일 상태 토글 실패"
        assert data['todo']['completed'] == 1, "완료 상태가 1로 변경되지 않음"
        print(f"  ✓ 할일 완료 상태 토글 성공 (completed = {data['todo']['completed']})")

    # 5. Update Todo
    print(f"\n5. 할일 정보 수정 (PUT /api/todos/{created_id}) 테스트...")
    update_payload = {
        "title": "자동화 검증 테스트 항목 (수정 완료)",
        "description": "설명 내용 업데이트됨",
        "category": "테스트",
        "priority": "medium",
        "due_date": "2026-09-25"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/api/todos/{created_id}",
        data=json.dumps(update_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "할일 정보 수정 실패"
        assert data['todo']['title'] == update_payload['title']
        assert data['todo']['priority'] == "medium"
        print(f"  ✓ 할일 정보 수정 성공 (Title: '{data['todo']['title']}')")

    # 6. Check Stats
    print("\n6. 대시보드 통계 조회 (GET /api/stats) 테스트...")
    req = urllib.request.Request(f"{BASE_URL}/api/stats")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "통계 조회 실패"
        stats = data['stats']
        print(f"  ✓ 통계 정상 집계 (전체: {stats['total']}, 완료: {stats['completed']}, 진행중: {stats['pending']}, 달성률: {stats['completion_rate']}%)")

    # 7. Delete Todo
    print(f"\n7. 할일 삭제 (DELETE /api/todos/{created_id}) 테스트...")
    req = urllib.request.Request(
        f"{BASE_URL}/api/todos/{created_id}",
        method='DELETE'
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        assert data['success'] is True, "할일 삭제 실패"
        print(f"  ✓ 할일 ID {created_id} 정상 삭제 완료")

    print("\n🎉 모든 기능 동작 및 실행 테스트를 100% 통과했습니다!")

if __name__ == '__main__':
    test_app()
