// Enhanced Dataset Workbench JavaScript

let tasks = [];
let selectedTasks = new Set();
let currentFocusIndex = -1;

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadDatasets();
    setupKeyboardShortcuts();
});

// ============================================================================
// Data Loading
// ============================================================================

async function loadDatasets() {
    try {
        const response = await fetch('/api/datasets');
        const datasets = await response.json();
        
        const select = document.getElementById('dataset-select');
        select.innerHTML = '<option value="">Select a dataset...</option>';
        
        datasets.forEach(dataset => {
            const option = document.createElement('option');
            option.value = dataset.id;
            option.textContent = `${dataset.name} (${dataset.task_count} tasks)`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading datasets:', error);
        setStatus('Error loading datasets');
    }
}

async function loadDataset() {
    const datasetId = document.getElementById('dataset-select').value;
    if (!datasetId) {
        showEmptyState();
        return;
    }

    showLoading();
    
    try {
        const response = await fetch(`/api/datasets/${datasetId}/tasks`);
        tasks = await response.json();
        
        renderTasks();
        updateCounts();
        setStatus(`Loaded ${tasks.length} tasks`);
    } catch (error) {
        console.error('Error loading dataset:', error);
        setStatus('Error loading dataset');
        showEmptyState();
    }
}

// ============================================================================
// Rendering
// ============================================================================

function renderTasks() {
    const grid = document.getElementById('task-grid');
    const loading = document.getElementById('loading');
    const emptyState = document.getElementById('empty-state');
    
    loading.style.display = 'none';
    
    if (tasks.length === 0) {
        emptyState.style.display = 'block';
        grid.innerHTML = '';
        return;
    }
    
    emptyState.style.display = 'none';
    
    grid.innerHTML = tasks.map((task, index) => `
        <div class="task-card ${selectedTasks.has(task.id) ? 'selected' : ''}" 
             data-task-id="${task.id}" 
             data-index="${index}"
             onclick="toggleTaskSelection('${task.id}', event)">
            <div class="task-header">
                <div class="task-id">Task #${task.id}</div>
                <div class="task-actions">
                    <input type="checkbox" 
                           class="checkbox" 
                           ${selectedTasks.has(task.id) ? 'checked' : ''}
                           onclick="event.stopPropagation(); toggleTaskSelection('${task.id}', event)">
                    <button class="btn btn-icon btn-small" onclick="event.stopPropagation(); editTask('${task.id}')">✏️</button>
                    <button class="btn btn-icon btn-small" onclick="event.stopPropagation(); toggleGoldStar('${task.id}')">
                        ${task.is_gold_star ? '⭐' : '☆'}
                    </button>
                </div>
            </div>
            
            <div class="task-content">
                ${renderTaskFields(task)}
            </div>
            
            <div class="task-footer">
                ${task.is_gold_star ? '<span class="gold-star-badge active">⭐ Gold Star</span>' : '<span class="gold-star-badge">☆ Not starred</span>'}
                <span style="font-size: 11px; color: #a0aec0;">${new Date(task.created_at).toLocaleDateString()}</span>
            </div>
        </div>
    `).join('');
}

function renderTaskFields(task) {
    const fields = Object.entries(task.data || {})
        .filter(([key]) => !['id', 'created_at', 'updated_at'].includes(key))
        .slice(0, 3); // Show first 3 fields
    
    return fields.map(([key, value]) => `
        <div class="task-field">
            <div class="task-field-label">${formatFieldName(key)}</div>
            <div class="task-field-value editable" 
                 contenteditable="false"
                 data-task-id="${task.id}"
                 data-field="${key}"
                 onblur="saveFieldEdit(this)"
                 onkeydown="handleFieldKeydown(event, this)">
                ${truncateText(String(value), 100)}
            </div>
        </div>
    `).join('');
}

function formatFieldName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

// ============================================================================
// Task Selection
// ============================================================================

function toggleTaskSelection(taskId, event) {
    if (event && event.shiftKey && currentFocusIndex >= 0) {
        // Shift+click: select range
        const clickedIndex = parseInt(event.currentTarget.dataset.index);
        const start = Math.min(currentFocusIndex, clickedIndex);
        const end = Math.max(currentFocusIndex, clickedIndex);
        
        for (let i = start; i <= end; i++) {
            selectedTasks.add(tasks[i].id);
        }
    } else {
        // Regular click: toggle selection
        if (selectedTasks.has(taskId)) {
            selectedTasks.delete(taskId);
        } else {
            selectedTasks.add(taskId);
        }
    }
    
    if (event) {
        currentFocusIndex = parseInt(event.currentTarget.dataset.index);
    }
    
    renderTasks();
    updateCounts();
}

function selectAll() {
    tasks.forEach(task => selectedTasks.add(task.id));
    renderTasks();
    updateCounts();
    setStatus(`Selected all ${tasks.length} tasks`);
}

function deselectAll() {
    selectedTasks.clear();
    renderTasks();
    updateCounts();
    setStatus('Deselected all tasks');
}

// ============================================================================
// Inline Editing
// ============================================================================

function editTask(taskId) {
    const card = document.querySelector(`[data-task-id="${taskId}"]`);
    const editableFields = card.querySelectorAll('.task-field-value.editable');
    
    editableFields.forEach(field => {
        field.contentEditable = 'true';
        field.classList.add('editing');
    });
    
    if (editableFields.length > 0) {
        editableFields[0].focus();
    }
    
    setStatus('Editing task - press Enter to save, Esc to cancel');
}

function saveFieldEdit(element) {
    const taskId = element.dataset.taskId;
    const field = element.dataset.field;
    const newValue = element.textContent.trim();
    
    element.contentEditable = 'false';
    element.classList.remove('editing');
    
    // TODO: Send update to server
    console.log(`Saving ${field} for task ${taskId}:`, newValue);
    setStatus('Changes saved');
}

function handleFieldKeydown(event, element) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        element.blur();
    } else if (event.key === 'Escape') {
        event.preventDefault();
        element.textContent = element.dataset.originalValue || element.textContent;
        element.blur();
    }
}

// ============================================================================
// Bulk Operations
// ============================================================================

async function bulkGoldStar() {
    if (selectedTasks.size === 0) {
        alert('No tasks selected');
        return;
    }
    
    if (!confirm(`Mark ${selectedTasks.size} tasks as gold stars?`)) {
        return;
    }
    
    setStatus(`Marking ${selectedTasks.size} tasks as gold stars...`);
    
    // TODO: Send bulk update to server
    for (const taskId of selectedTasks) {
        const task = tasks.find(t => t.id === taskId);
        if (task) {
            task.is_gold_star = true;
        }
    }
    
    renderTasks();
    setStatus(`Marked ${selectedTasks.size} tasks as gold stars`);
}

async function bulkDelete() {
    if (selectedTasks.size === 0) {
        alert('No tasks selected');
        return;
    }
    
    if (!confirm(`Delete ${selectedTasks.size} tasks? This cannot be undone.`)) {
        return;
    }
    
    setStatus(`Deleting ${selectedTasks.size} tasks...`);
    
    // TODO: Send bulk delete to server
    tasks = tasks.filter(task => !selectedTasks.has(task.id));
    selectedTasks.clear();
    
    renderTasks();
    updateCounts();
    setStatus(`Deleted ${selectedTasks.size} tasks`);
}

async function toggleGoldStar(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    task.is_gold_star = !task.is_gold_star;
    
    // TODO: Send update to server
    console.log(`Toggling gold star for task ${taskId}:`, task.is_gold_star);
    
    renderTasks();
    updateCounts();
    setStatus(task.is_gold_star ? 'Marked as gold star' : 'Removed gold star');
}

// ============================================================================
// Keyboard Shortcuts
// ============================================================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if typing in an input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.isContentEditable) {
            return;
        }
        
        // Ctrl+A: Select all
        if (e.ctrlKey && e.key === 'a') {
            e.preventDefault();
            selectAll();
        }
        
        // Esc: Deselect all
        if (e.key === 'Escape') {
            deselectAll();
        }
        
        // Ctrl+G: Mark as gold star
        if (e.ctrlKey && e.key === 'g') {
            e.preventDefault();
            bulkGoldStar();
        }
        
        // Delete: Delete selected
        if (e.key === 'Delete') {
            bulkDelete();
        }
        
        // Ctrl+R: Refresh
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            loadDataset();
        }
        
        // ?: Show shortcuts
        if (e.key === '?') {
            showShortcuts();
        }
        
        // Arrow keys: Navigate
        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
            e.preventDefault();
            navigateTasks(e.key === 'ArrowUp' ? -1 : 1);
        }
        
        // Space: Toggle selection
        if (e.key === ' ') {
            e.preventDefault();
            if (currentFocusIndex >= 0 && currentFocusIndex < tasks.length) {
                toggleTaskSelection(tasks[currentFocusIndex].id);
            }
        }
    });
}

function navigateTasks(direction) {
    if (tasks.length === 0) return;
    
    currentFocusIndex += direction;
    if (currentFocusIndex < 0) currentFocusIndex = 0;
    if (currentFocusIndex >= tasks.length) currentFocusIndex = tasks.length - 1;
    
    const card = document.querySelector(`[data-index="${currentFocusIndex}"]`);
    if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.style.outline = '2px solid #667eea';
        setTimeout(() => card.style.outline = '', 1000);
    }
}

// ============================================================================
// UI Helpers
// ============================================================================

function updateCounts() {
    document.getElementById('selection-count').textContent = `${selectedTasks.size} selected`;
    document.getElementById('task-count').textContent = `${tasks.length} tasks`;
    
    const goldStarCount = tasks.filter(t => t.is_gold_star).length;
    document.getElementById('gold-star-count').textContent = `${goldStarCount} gold stars`;
}

function setStatus(message) {
    document.getElementById('status-message').textContent = message;
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('task-grid').innerHTML = '';
}

function showEmptyState() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
    document.getElementById('task-grid').innerHTML = '';
}

function showShortcuts() {
    document.getElementById('shortcuts-modal').classList.add('active');
}

function hideShortcuts() {
    document.getElementById('shortcuts-modal').classList.remove('active');
}

