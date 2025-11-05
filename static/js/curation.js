// Data Curation UI JavaScript

const API_BASE = 'http://localhost:8001/api';

let tasks = [];
let schemas = [];
let stats = {};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    loadSchemas();
    loadStats();
    loadTasks();
});

// ============================================================================
// Data Loading
// ============================================================================

async function loadSchemas() {
    try {
        const response = await fetch(`${API_BASE}/schemas`);
        schemas = await response.json();
        
        const select = document.getElementById('schema-filter');
        schemas.forEach(schema => {
            const option = document.createElement('option');
            option.value = schema.type;
            option.textContent = schema.name;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading schemas:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        stats = await response.json();
        
        document.getElementById('total-tasks').textContent = stats.total_tasks || 0;
        document.getElementById('gold-stars').textContent = stats.gold_star_count || 0;
        
        const completionRate = stats.total_tasks > 0 
            ? Math.round((stats.gold_star_count / stats.total_tasks) * 100)
            : 0;
        document.getElementById('completion-rate').textContent = `${completionRate}%`;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadTasks() {
    const schemaType = document.getElementById('schema-filter').value;
    const statusFilter = document.getElementById('status-filter').value;
    
    showLoading();
    
    try {
        let url = `${API_BASE}/tasks?page=1&page_size=100`;
        if (schemaType) {
            url += `&schema_type=${schemaType}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        tasks = data.tasks || [];
        
        // Apply status filter
        if (statusFilter === 'gold') {
            tasks = tasks.filter(t => t.is_gold_star);
        } else if (statusFilter === 'not-gold') {
            tasks = tasks.filter(t => !t.is_gold_star);
        }
        
        renderTasks();
        updateStatusBar();
    } catch (error) {
        console.error('Error loading tasks:', error);
        showError('Failed to load tasks');
    }
}

// ============================================================================
// Rendering
// ============================================================================

function renderTasks() {
    const container = document.getElementById('task-list');
    
    if (tasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>No tasks found</h2>
                <p>Try adjusting your filters or import some batch results</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = tasks.map(task => `
        <div class="task-item ${task.is_gold_star ? 'gold-star' : ''}" 
             data-task-id="${task.id}"
             onclick="selectTask(${task.id})">
            <div class="task-header">
                <div class="task-id">Task #${task.id}</div>
                <div class="task-badges">
                    ${task.is_gold_star ? '<span class="badge badge-gold">⭐ Gold Star</span>' : ''}
                    <span class="badge badge-schema">${task.schema_type || 'unknown'}</span>
                </div>
            </div>
            
            <div class="task-content">
                ${renderTaskData(task)}
            </div>
            
            <div class="task-actions">
                <button class="btn btn-small ${task.is_gold_star ? 'btn-secondary' : 'btn-gold'}" 
                        onclick="event.stopPropagation(); toggleGoldStar(${task.id})">
                    ${task.is_gold_star ? '☆ Remove Gold Star' : '⭐ Mark as Gold Star'}
                </button>
                <button class="btn btn-secondary btn-small" 
                        onclick="event.stopPropagation(); viewInLabelStudio(${task.id})">
                    📝 Edit in Label Studio
                </button>
                <button class="btn btn-secondary btn-small" 
                        onclick="event.stopPropagation(); viewDetails(${task.id})">
                    👁️ View Details
                </button>
            </div>
        </div>
    `).join('');
}

function renderTaskData(task) {
    const data = task.data || {};
    const fields = Object.entries(data).slice(0, 3); // Show first 3 fields
    
    if (fields.length === 0) {
        return '<p style="color: #a0aec0; font-size: 13px;">No data available</p>';
    }
    
    return fields.map(([key, value]) => `
        <div class="task-field">
            <div class="task-field-label">${formatFieldName(key)}</div>
            <div class="task-field-value">${truncateText(String(value), 150)}</div>
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
// Task Actions
// ============================================================================

async function toggleGoldStar(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    const newStatus = !task.is_gold_star;
    
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}/gold-star`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_gold_star: newStatus })
        });
        
        if (!response.ok) throw new Error('Failed to update gold star status');
        
        task.is_gold_star = newStatus;
        renderTasks();
        loadStats();
        setStatus(newStatus ? 'Marked as gold star ⭐' : 'Removed gold star');
    } catch (error) {
        console.error('Error toggling gold star:', error);
        setStatus('Error updating gold star status');
    }
}

function viewInLabelStudio(taskId) {
    // Open Label Studio in new tab
    window.open(`http://localhost:4115/tasks/${taskId}`, '_blank');
}

function viewDetails(taskId) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    
    // Create a modal or detailed view
    alert(`Task #${taskId}\n\nSchema: ${task.schema_type}\nGold Star: ${task.is_gold_star}\n\nData:\n${JSON.stringify(task.data, null, 2)}`);
}

function selectTask(taskId) {
    // Remove previous selection
    document.querySelectorAll('.task-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Add selection to clicked task
    const taskElement = document.querySelector(`[data-task-id="${taskId}"]`);
    if (taskElement) {
        taskElement.classList.add('selected');
    }
}

async function exportGoldStars() {
    const schemaType = document.getElementById('schema-filter').value;
    
    try {
        const response = await fetch(`${API_BASE}/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                schema_type: schemaType || null,
                format: 'jsonl',
                gold_stars_only: true
            })
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        const data = await response.json();
        
        // Download the file
        const blob = new Blob([data.content], { type: 'application/jsonl' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        a.click();
        URL.revokeObjectURL(url);
        
        setStatus(`Exported ${data.count} gold star tasks`);
    } catch (error) {
        console.error('Error exporting:', error);
        setStatus('Error exporting gold stars');
    }
}

// ============================================================================
// UI Helpers
// ============================================================================

function showLoading() {
    document.getElementById('task-list').innerHTML = '<div class="loading">Loading tasks...</div>';
}

function showError(message) {
    document.getElementById('task-list').innerHTML = `
        <div class="empty-state">
            <h2>Error</h2>
            <p>${message}</p>
        </div>
    `;
}

function setStatus(message) {
    document.getElementById('status-message').textContent = message;
}

function updateStatusBar() {
    document.getElementById('task-count').textContent = `${tasks.length} tasks loaded`;
}

