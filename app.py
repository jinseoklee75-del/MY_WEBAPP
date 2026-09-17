import os
from dotenv import load_dotenv

# Local development: load DATABASE_URL from .env.local (pulled via `vercel env pull`)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env.local'))

from flask import Flask, render_template, request, jsonify
import database

app = Flask(__name__)

# Ensure DB is initialized
with app.app_context():
    database.init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/todos', methods=['GET'])
def list_todos():
    status = request.args.get('status')
    category = request.args.get('category')
    search = request.args.get('search')
    sort_by = request.args.get('sort', 'created_desc')
    
    todos = database.get_todos(status=status, category=category, search=search, sort_by=sort_by)
    return jsonify({'success': True, 'todos': todos})

@app.route('/api/todos', methods=['POST'])
def create_todo():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': '할 일 제목을 입력해주세요.'}), 400
        
    description = data.get('description', '').strip()
    category = data.get('category', '업무').strip() or '업무'
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date')
    
    new_todo = database.create_todo(
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=due_date
    )
    return jsonify({'success': True, 'todo': new_todo}), 201

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': '할 일 제목을 입력해주세요.'}), 400
        
    description = data.get('description', '').strip()
    category = data.get('category', '업무').strip() or '업무'
    priority = data.get('priority', 'medium')
    due_date = data.get('due_date')
    
    updated = database.update_todo(
        todo_id=todo_id,
        title=title,
        description=description,
        category=category,
        priority=priority,
        due_date=due_date
    )
    if not updated:
        return jsonify({'success': False, 'error': '항목을 찾을 수 없습니다.'}), 404
        
    return jsonify({'success': True, 'todo': updated})

@app.route('/api/todos/<int:todo_id>/toggle', methods=['PATCH'])
def toggle_todo(todo_id):
    updated = database.toggle_todo(todo_id)
    if not updated:
        return jsonify({'success': False, 'error': '항목을 찾을 수 없습니다.'}), 404
    return jsonify({'success': True, 'todo': updated})

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    success = database.delete_todo(todo_id)
    if not success:
        return jsonify({'success': False, 'error': '항목을 찾을 수 없습니다.'}), 404
    return jsonify({'success': True, 'message': '삭제되었습니다.'})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = database.get_stats()
    return jsonify({'success': True, 'stats': stats})

import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"[Flask] Todo Web App Server started: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
