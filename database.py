import os
from datetime import datetime, date

import psycopg2
from psycopg2.extras import RealDictCursor

# Supabase (PostgreSQL) connection string.
# Locally it is read from .env.local (see app.py); on Vercel it is an env var.
DATABASE_URL = os.environ.get('DATABASE_URL')


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
    """Convert a DB row to a JSON-friendly dict (timestamps -> strings)."""
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, datetime):
            out[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, date):
            out[key] = value.isoformat()
    return out


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '업무',
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')

    # Check if empty, add welcoming sample tasks
    cursor.execute('SELECT COUNT(*) AS count FROM todos')
    count = cursor.fetchone()['count']
    if count == 0:
        sample_todos = [
            (
                "Flask 웹앱 환경 구성 및 테스트",
                "Python Flask 기반 할일 관리 웹 애플리케이션 정상 기동 확인",
                "개발",
                "high",
                datetime.now().strftime("%Y-%m-%d"),
                1,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
            (
                "프로젝트 주간 보고서 작성",
                "이번 주 주요 마일스톤 및 성과 요약하여 팀 공유하기",
                "업무",
                "high",
                datetime.now().strftime("%Y-%m-%d"),
                0,
                None
            ),
            (
                "클로드 업무자동화 교재 복습",
                "프롬프트 엔지니어링 및 AI 에이전트 실습 예제 다시 살펴보기",
                "학습",
                "medium",
                None,
                0,
                None
            ),
            (
                "매일 30분 가벼운 운동 및 스트레칭",
                "건강 관리 루틴 실천하기",
                "개인",
                "low",
                None,
                0,
                None
            )
        ]
        cursor.executemany('''
            INSERT INTO todos (title, description, category, priority, due_date, completed, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', sample_todos)

    conn.commit()
    conn.close()


def get_todos(status=None, category=None, search=None, sort_by='created_desc'):
    conn = get_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM todos WHERE 1=1'
    params = []

    if status == 'active':
        query += ' AND completed = 0'
    elif status == 'completed':
        query += ' AND completed = 1'

    if category and category != 'all':
        query += ' AND category = %s'
        params.append(category)

    if search:
        query += ' AND (title ILIKE %s OR description ILIKE %s)'
        wildcard = f'%{search}%'
        params.extend([wildcard, wildcard])

    if sort_by == 'due_date':
        query += ' ORDER BY completed ASC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, id DESC'
    elif sort_by == 'priority':
        query += ''' ORDER BY completed ASC,
                    CASE priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END, id DESC'''
    else:  # default created_desc
        query += ' ORDER BY completed ASC, id DESC'

    cursor.execute(query, params)
    todos = [_serialize(row) for row in cursor.fetchall()]
    conn.close()
    return todos


def get_todo_by_id(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM todos WHERE id = %s', (todo_id,))
    row = cursor.fetchone()
    conn.close()
    return _serialize(row)


def create_todo(title, description='', category='업무', priority='medium', due_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO todos (title, description, category, priority, due_date)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', (title.strip(), description.strip(), category.strip(), priority, due_date if due_date else None))
    new_id = cursor.fetchone()['id']
    conn.commit()
    conn.close()
    return get_todo_by_id(new_id)


def update_todo(todo_id, title, description='', category='업무', priority='medium', due_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE todos
        SET title = %s, description = %s, category = %s, priority = %s, due_date = %s
        WHERE id = %s
    ''', (title.strip(), description.strip(), category.strip(), priority, due_date if due_date else None, todo_id))
    conn.commit()
    conn.close()
    return get_todo_by_id(todo_id)


def toggle_todo(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT completed FROM todos WHERE id = %s', (todo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    new_status = 0 if row['completed'] == 1 else 1
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == 1 else None

    cursor.execute('''
        UPDATE todos
        SET completed = %s, completed_at = %s
        WHERE id = %s
    ''', (new_status, completed_at, todo_id))
    conn.commit()
    conn.close()
    return get_todo_by_id(todo_id)


def delete_todo(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM todos WHERE id = %s', (todo_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) AS total, SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed FROM todos')
    row = cursor.fetchone()
    total = row['total'] or 0
    completed = row['completed'] or 0
    pending = total - completed
    rate = round((completed / total * 100), 1) if total > 0 else 0

    cursor.execute("SELECT DISTINCT category FROM todos WHERE category IS NOT NULL AND category != ''")
    categories = [r['category'] for r in cursor.fetchall()]

    conn.close()
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': rate,
        'categories': categories
    }
