/**
 * TaskFlow Frontend Application Logic
 * Pure Vanilla JavaScript
 */

// Application State
const state = {
    todos: [],
    filterStatus: 'all', // 'all', 'active', 'completed'
    selectedCategory: 'all',
    searchQuery: '',
    sortBy: 'created_desc',
    editingTodo: null
};

// DOM Elements
const elements = {
    currentDateDisplay: document.getElementById('currentDateDisplay'),
    statTotal: document.getElementById('statTotal'),
    statPending: document.getElementById('statPending'),
    statCompleted: document.getElementById('statCompleted'),
    statRateText: document.getElementById('statRateText'),
    statProgressBar: document.getElementById('statProgressBar'),
    addTodoForm: document.getElementById('addTodoForm'),
    todoTitleInput: document.getElementById('todoTitleInput'),
    todoCategoryInput: document.getElementById('todoCategoryInput'),
    todoPriorityInput: document.getElementById('todoPriorityInput'),
    todoDueDateInput: document.getElementById('todoDueDateInput'),
    todoDescInput: document.getElementById('todoDescInput'),
    todoList: document.getElementById('todoList'),
    emptyState: document.getElementById('emptyState'),
    tabAll: document.getElementById('tabAll'),
    tabActive: document.getElementById('tabActive'),
    tabCompleted: document.getElementById('tabCompleted'),
    badgeAll: document.getElementById('badgeAll'),
    badgeActive: document.getElementById('badgeActive'),
    badgeCompleted: document.getElementById('badgeCompleted'),
    searchInput: document.getElementById('searchInput'),
    btnClearSearch: document.getElementById('btnClearSearch'),
    categoryFilter: document.getElementById('categoryFilter'),
    categorySuggestions: document.getElementById('categorySuggestions'),
    sortFilter: document.getElementById('sortFilter'),
    editModal: document.getElementById('editModal'),
    editTodoForm: document.getElementById('editTodoForm'),
    editTodoId: document.getElementById('editTodoId'),
    editTitleInput: document.getElementById('editTitleInput'),
    editCategoryInput: document.getElementById('editCategoryInput'),
    editPriorityInput: document.getElementById('editPriorityInput'),
    editDueDateInput: document.getElementById('editDueDateInput'),
    editDescInput: document.getElementById('editDescInput'),
    btnCloseModal: document.getElementById('btnCloseModal'),
    btnCancelEdit: document.getElementById('btnCancelEdit'),
    toastContainer: document.getElementById('toastContainer')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    setupDateDisplay();
    setupEventListeners();
    fetchStats();
    fetchTodos();
});

// Setup Current Date in Header
function setupDateDisplay() {
    const now = new Date();
    const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' };
    elements.currentDateDisplay.textContent = now.toLocaleDateString('ko-KR', options);
}

// Event Listeners Setup
function setupEventListeners() {
    // Add Todo Form Submit
    elements.addTodoForm.addEventListener('submit', handleAddTodo);

    // Tab Filters
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.filterStatus = tab.dataset.status;
            fetchTodos();
        });
    });

    // Category Filter Change
    elements.categoryFilter.addEventListener('change', (e) => {
        state.selectedCategory = e.target.value;
        fetchTodos();
    });

    // Sort Filter Change
    elements.sortFilter.addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        fetchTodos();
    });

    // Search with Debounce
    let debounceTimer;
    elements.searchInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        elements.btnClearSearch.classList.toggle('visible', val.length > 0);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.searchQuery = val;
            fetchTodos();
        }, 250);
    });

    // Clear Search Button
    elements.btnClearSearch.addEventListener('click', () => {
        elements.searchInput.value = '';
        elements.btnClearSearch.classList.remove('visible');
        state.searchQuery = '';
        fetchTodos();
    });

    // Edit Modal Events
    elements.btnCloseModal.addEventListener('click', closeEditModal);
    elements.btnCancelEdit.addEventListener('click', closeEditModal);
    elements.editModal.addEventListener('click', (e) => {
        if (e.target === elements.editModal) closeEditModal();
    });
    elements.editTodoForm.addEventListener('submit', handleSaveEdit);
}

// API: Fetch Todos
async function fetchTodos() {
    try {
        const params = new URLSearchParams();
        if (state.filterStatus !== 'all') params.append('status', state.filterStatus);
        if (state.selectedCategory !== 'all') params.append('category', state.selectedCategory);
        if (state.searchQuery) params.append('search', state.searchQuery);
        if (state.sortBy) params.append('sort', state.sortBy);

        const res = await fetch(`/api/todos?${params.toString()}`);
        const data = await res.json();

        if (data.success) {
            state.todos = data.todos;
            renderTodoList();
        }
    } catch (err) {
        console.error('할일 목록 불러오기 실패:', err);
        showToast('할일 목록을 불러오는 중 오류가 발생했습니다.', 'error');
    }
}

// API: Fetch Stats
async function fetchStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();

        if (data.success) {
            const { total, completed, pending, completion_rate, categories } = data.stats;
            elements.statTotal.textContent = total;
            elements.statPending.textContent = pending;
            elements.statCompleted.textContent = completed;
            elements.statRateText.textContent = `${completion_rate}%`;
            elements.statProgressBar.style.width = `${completion_rate}%`;

            elements.badgeAll.textContent = total;
            elements.badgeActive.textContent = pending;
            elements.badgeCompleted.textContent = completed;

            updateCategoryOptions(categories);
        }
    } catch (err) {
        console.error('통계 데이터 불러오기 실패:', err);
    }
}

// Update Category Filter and Datalist Suggestions
function updateCategoryOptions(categories) {
    const currentSelected = elements.categoryFilter.value;
    
    // Update Filter Select
    let optionsHtml = '<option value="all">모든 카테고리</option>';
    categories.forEach(cat => {
        if (cat) {
            optionsHtml += `<option value="${escapeHtml(cat)}">${escapeHtml(cat)}</option>`;
        }
    });
    elements.categoryFilter.innerHTML = optionsHtml;
    if (categories.includes(currentSelected)) {
        elements.categoryFilter.value = currentSelected;
    }

    // Update Datalist
    let datalistHtml = '';
    const defaultCategories = ['업무', '개발', '학습', '개인', '회의'];
    const allUnique = Array.from(new Set([...defaultCategories, ...categories]));
    allUnique.forEach(cat => {
        if (cat) {
            datalistHtml += `<option value="${escapeHtml(cat)}">`;
        }
    });
    elements.categorySuggestions.innerHTML = datalistHtml;
}

// Render Todo List to DOM
function renderTodoList() {
    elements.todoList.innerHTML = '';

    if (state.todos.length === 0) {
        elements.emptyState.classList.remove('hidden');
        return;
    }

    elements.emptyState.classList.add('hidden');

    state.todos.forEach(todo => {
        const item = createTodoElement(todo);
        elements.todoList.appendChild(item);
    });
}

// Create Todo Item Element
function createTodoElement(todo) {
    const card = document.createElement('div');
    card.className = `todo-card ${todo.completed ? 'is-completed' : ''}`;
    card.id = `todo-${todo.id}`;

    // Priority badge helper
    let priorityLabel = '보통';
    let priorityClass = 'badge-priority-medium';
    if (todo.priority === 'high') {
        priorityLabel = '🔥 높음';
        priorityClass = 'badge-priority-high';
    } else if (todo.priority === 'low') {
        priorityLabel = '🌱 낮음';
        priorityClass = 'badge-priority-low';
    } else {
        priorityLabel = '⚡ 보통';
    }

    // Due date badge calculation
    let dueBadgeHtml = '';
    if (todo.due_date) {
        const dueInfo = formatDueDate(todo.due_date);
        dueBadgeHtml = `<span class="badge-tag badge-due ${dueInfo.className}">📅 ${escapeHtml(dueInfo.text)}</span>`;
    }

    // Description
    const descHtml = todo.description 
        ? `<p class="todo-desc">${escapeHtml(todo.description)}</p>` 
        : '';

    card.innerHTML = `
        <div class="todo-checkbox-wrapper">
            <input 
                type="checkbox" 
                class="todo-checkbox" 
                id="check-${todo.id}" 
                ${todo.completed ? 'checked' : ''} 
                aria-label="할일 완료 여부 토글"
            >
        </div>
        <div class="todo-body">
            <div class="todo-header-row">
                <span class="todo-title">${escapeHtml(todo.title)}</span>
            </div>
            ${descHtml}
            <div class="todo-meta">
                <span class="badge-tag badge-category">📁 ${escapeHtml(todo.category || '기타')}</span>
                <span class="badge-tag ${priorityClass}">${priorityLabel}</span>
                ${dueBadgeHtml}
            </div>
        </div>
        <div class="todo-actions">
            <button class="action-btn btn-edit" title="수정" aria-label="할일 수정">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            </button>
            <button class="action-btn btn-delete" title="삭제" aria-label="할일 삭제">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        </div>
    `;

    // Event Bindings
    const checkbox = card.querySelector('.todo-checkbox');
    checkbox.addEventListener('change', () => handleToggleTodo(todo.id));

    const btnEdit = card.querySelector('.btn-edit');
    btnEdit.addEventListener('click', () => openEditModal(todo));

    const btnDelete = card.querySelector('.btn-delete');
    btnDelete.addEventListener('click', () => handleDeleteTodo(todo.id, todo.title));

    return card;
}

// Calculate Due Date Status
function formatDueDate(dueDateStr) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const [year, month, day] = dueDateStr.split('-').map(Number);
    const dueDate = new Date(year, month - 1, day);
    dueDate.setHours(0, 0, 0, 0);

    const diffDays = Math.round((dueDate - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
        return { text: `${dueDateStr} (${Math.abs(diffDays)}일 지남)`, className: 'due-overdue' };
    } else if (diffDays === 0) {
        return { text: '오늘 마감!', className: 'due-today' };
    } else if (diffDays === 1) {
        return { text: '내일 마감 (D-1)', className: 'due-today' };
    } else {
        return { text: `${dueDateStr} (D-${diffDays})`, className: '' };
    }
}

// API: Handle Add Todo
async function handleAddTodo(e) {
    e.preventDefault();

    const title = elements.todoTitleInput.value.trim();
    if (!title) return;

    const payload = {
        title: title,
        category: elements.todoCategoryInput.value.trim() || '업무',
        priority: elements.todoPriorityInput.value,
        due_date: elements.todoDueDateInput.value || null,
        description: elements.todoDescInput.value.trim()
    };

    try {
        const res = await fetch('/api/todos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            elements.todoTitleInput.value = '';
            elements.todoDescInput.value = '';
            elements.todoDueDateInput.value = '';
            showToast('할일이 등록되었습니다! 🎉', 'success');
            fetchStats();
            fetchTodos();
        } else {
            showToast(data.error || '등록 실패', 'error');
        }
    } catch (err) {
        console.error('할일 추가 실패:', err);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
    }
}

// API: Handle Toggle Todo
async function handleToggleTodo(id) {
    try {
        const res = await fetch(`/api/todos/${id}/toggle`, {
            method: 'PATCH'
        });
        const data = await res.json();

        if (data.success) {
            const isCompleted = data.todo.completed === 1;
            showToast(isCompleted ? '할일을 완료했습니다! 👏' : '진행 중으로 변경되었습니다.', 'info');
            fetchStats();
            fetchTodos();
        } else {
            showToast(data.error || '상태 변경 실패', 'error');
        }
    } catch (err) {
        console.error('토글 실패:', err);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
    }
}

// API: Handle Delete Todo
async function handleDeleteTodo(id, title) {
    if (!confirm(`"${title}" 항목을 삭제하시겠습니까?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/todos/${id}`, {
            method: 'DELETE'
        });
        const data = await res.json();

        if (data.success) {
            showToast('할일이 삭제되었습니다.', 'info');
            fetchStats();
            fetchTodos();
        } else {
            showToast(data.error || '삭제 실패', 'error');
        }
    } catch (err) {
        console.error('삭제 실패:', err);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
    }
}

// Edit Modal Functions
function openEditModal(todo) {
    state.editingTodo = todo;
    elements.editTodoId.value = todo.id;
    elements.editTitleInput.value = todo.title;
    elements.editCategoryInput.value = todo.category || '업무';
    elements.editPriorityInput.value = todo.priority || 'medium';
    elements.editDueDateInput.value = todo.due_date || '';
    elements.editDescInput.value = todo.description || '';

    elements.editModal.classList.remove('hidden');
    elements.editTitleInput.focus();
}

function closeEditModal() {
    elements.editModal.classList.add('hidden');
    state.editingTodo = null;
}

async function handleSaveEdit(e) {
    e.preventDefault();
    const id = elements.editTodoId.value;
    if (!id) return;

    const payload = {
        title: elements.editTitleInput.value.trim(),
        category: elements.editCategoryInput.value.trim() || '업무',
        priority: elements.editPriorityInput.value,
        due_date: elements.editDueDateInput.value || null,
        description: elements.editDescInput.value.trim()
    };

    try {
        const res = await fetch(`/api/todos/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.success) {
            closeEditModal();
            showToast('성공적으로 수정되었습니다!', 'success');
            fetchStats();
            fetchTodos();
        } else {
            showToast(data.error || '수정 실패', 'error');
        }
    } catch (err) {
        console.error('수정 실패:', err);
        showToast('서버 통신 오류가 발생했습니다.', 'error');
    }
}

// Toast Notification
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    } else if (type === 'error') {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
    } else {
        iconSvg = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 250);
    }, 2800);
}

// Helper: Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
