import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'todos.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    cursor.execute('SELECT COUNT(*) FROM todos')
    count = cursor.fetchone()[0]
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
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
        query += ' AND category = ?'
        params.append(category)
        
    if search:
        query += ' AND (title LIKE ? OR description LIKE ?)'
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
    rows = cursor.fetchall()
    todos = [dict(row) for row in rows]
    conn.close()
    return todos

def get_todo_by_id(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM todos WHERE id = ?', (todo_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_todo(title, description='', category='업무', priority='medium', due_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO todos (title, description, category, priority, due_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (title.strip(), description.strip(), category.strip(), priority, due_date if due_date else None))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return get_todo_by_id(new_id)

def update_todo(todo_id, title, description='', category='업무', priority='medium', due_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE todos 
        SET title = ?, description = ?, category = ?, priority = ?, due_date = ?
        WHERE id = ?
    ''', (title.strip(), description.strip(), category.strip(), priority, due_date if due_date else None, todo_id))
    conn.commit()
    conn.close()
    return get_todo_by_id(todo_id)

def toggle_todo(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT completed FROM todos WHERE id = ?', (todo_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    new_status = 0 if row['completed'] == 1 else 1
    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_status == 1 else None
    
    cursor.execute('''
        UPDATE todos 
        SET completed = ?, completed_at = ?
        WHERE id = ?
    ''', (new_status, completed_at, todo_id))
    conn.commit()
    conn.close()
    return get_todo_by_id(todo_id)

def delete_todo(todo_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total, SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed FROM todos')
    row = cursor.fetchone()
    total = row['total'] or 0
    completed = row['completed'] or 0
    pending = total - completed
    rate = round((completed / total * 100), 1) if total > 0 else 0
    
    cursor.execute('SELECT DISTINCT category FROM todos WHERE category IS NOT NULL AND category != ""')
    categories = [r['category'] for r in cursor.fetchall()]
    
    conn.close()
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': rate,
        'categories': categories
    }
