/**
 * Candidate Curation UI - JavaScript
 * 
 * Handles loading, filtering, and curating candidate evaluations
 */

let allCandidates = [];
let filteredCandidates = [];

// Load candidates on page load
document.addEventListener('DOMContentLoaded', () => {
    loadCandidates();
    setupFilters();
});

async function loadCandidates() {
    try {
        const response = await fetch('/api/tasks?schema_type=candidate_evaluation');
        if (!response.ok) throw new Error('Failed to load candidates');
        
        const data = await response.json();
        allCandidates = data.tasks || [];
        
        applyFilters();
        updateStats();
    } catch (error) {
        console.error('Error loading candidates:', error);
        showError('Failed to load candidates');
    }
}

function setupFilters() {
    document.getElementById('filter-recommendation').addEventListener('change', applyFilters);
    document.getElementById('filter-gold-star').addEventListener('change', applyFilters);
}

function applyFilters() {
    const recFilter = document.getElementById('filter-recommendation').value;
    const goldStarFilter = document.getElementById('filter-gold-star').value;
    
    filteredCandidates = allCandidates.filter(candidate => {
        // Filter by recommendation
        if (recFilter) {
            const rec = candidate.result?.evaluation?.recommendation;
            if (rec !== recFilter) return false;
        }
        
        // Filter by gold star
        if (goldStarFilter) {
            const isGoldStar = candidate.is_gold_star || false;
            if (goldStarFilter === 'true' && !isGoldStar) return false;
            if (goldStarFilter === 'false' && isGoldStar) return false;
        }
        
        return true;
    });
    
    renderCandidates();
}

function renderCandidates() {
    const container = document.getElementById('candidate-list');
    
    if (filteredCandidates.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No candidates found</h3>
                <p>Try adjusting your filters</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = filteredCandidates.map(candidate => renderCandidateCard(candidate)).join('');
}

function renderCandidateCard(candidate) {
    const candidateData = candidate.result?.candidate || {};
    const evaluation = candidate.result?.evaluation || {};
    
    const name = candidateData.name || 'Unknown';
    const title = candidateData.title || '';
    const company = candidateData.company || '';
    const recommendation = evaluation.recommendation || '';
    const trajectory = evaluation.trajectory_rating || '';
    const isGoldStar = candidate.is_gold_star || false;
    
    const recBadgeClass = getBadgeClass(recommendation);
    const qualityBadgeClass = getQualityBadgeClass(trajectory);
    
    return `
        <div class="candidate-card ${isGoldStar ? 'gold-star' : ''}" data-task-id="${candidate.id}">
            <div class="candidate-header">
                <div class="candidate-info">
                    <h4>${name} ${isGoldStar ? '<span class="gold-star-icon">⭐</span>' : ''}</h4>
                    <p>${title}${company ? ' at ' + company : ''}</p>
                </div>
                <div class="rating-badges">
                    ${recommendation ? `<span class="badge ${recBadgeClass}">${recommendation}</span>` : ''}
                    ${trajectory ? `<span class="quality-badge quality-${trajectory.toLowerCase()}">${trajectory}</span>` : ''}
                </div>
            </div>
            
            ${evaluation.reasoning ? `
                <div style="margin-top: 12px; font-size: 14px; color: #6a737d; line-height: 1.5;">
                    ${evaluation.reasoning.substring(0, 200)}${evaluation.reasoning.length > 200 ? '...' : ''}
                </div>
            ` : ''}
            
            <div class="candidate-actions">
                <button class="btn ${isGoldStar ? 'btn-secondary' : 'btn-gold'}" 
                        onclick="toggleGoldStar('${candidate.id}', ${!isGoldStar})">
                    ${isGoldStar ? 'Remove Gold Star' : '⭐ Mark as Gold Star'}
                </button>
                <button class="btn btn-primary" onclick="viewDetails('${candidate.id}')">
                    View Details
                </button>
                <button class="btn btn-secondary" onclick="editInLabelStudio('${candidate.id}')">
                    Edit in Label Studio
                </button>
            </div>
        </div>
    `;
}

function getBadgeClass(recommendation) {
    const mapping = {
        'Strong Yes': 'badge-strong-yes',
        'Yes': 'badge-yes',
        'Maybe': 'badge-maybe',
        'No': 'badge-no',
        'Strong No': 'badge-strong-no'
    };
    return mapping[recommendation] || 'badge';
}

function getQualityBadgeClass(quality) {
    return `quality-${quality.toLowerCase()}`;
}

async function toggleGoldStar(taskId, isGoldStar) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/gold-star`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_gold_star: isGoldStar})
        });
        
        if (!response.ok) throw new Error('Failed to update gold star');
        
        // Update local data
        const candidate = allCandidates.find(c => c.id === taskId);
        if (candidate) {
            candidate.is_gold_star = isGoldStar;
        }
        
        applyFilters();
        updateStats();
        
        showToast(isGoldStar ? 'Marked as gold star ⭐' : 'Removed gold star', 'success');
    } catch (error) {
        console.error('Error toggling gold star:', error);
        showToast('Failed to update gold star', 'error');
    }
}

function viewDetails(taskId) {
    window.location.href = `/workbench?task=${taskId}`;
}

function editInLabelStudio(taskId) {
    const candidate = allCandidates.find(c => c.id === taskId);
    if (candidate && candidate.label_studio_task_id) {
        window.open(`http://localhost:4115/tasks/${candidate.label_studio_task_id}`, '_blank');
    } else {
        showToast('No Label Studio task found', 'error');
    }
}

async function exportData(format) {
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                schema_type: 'candidate_evaluation',
                format: format,
                plugin: 'candidate-evaluator'
            })
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `candidates_${format}_${Date.now()}.jsonl`;
        a.click();
        
        showToast(`Exported ${format} data`, 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Export failed', 'error');
    }
}

function updateStats() {
    const total = allCandidates.length;
    const goldStars = allCandidates.filter(c => c.is_gold_star).length;
    const strongYes = allCandidates.filter(c => 
        c.result?.evaluation?.recommendation === 'Strong Yes'
    ).length;
    const reviewed = allCandidates.filter(c => c.is_gold_star !== undefined).length;
    const completionRate = total > 0 ? Math.round((reviewed / total) * 100) : 0;
    
    document.getElementById('total-candidates').textContent = total;
    document.getElementById('gold-stars').textContent = goldStars;
    document.getElementById('strong-yes-count').textContent = strongYes;
    document.getElementById('completion-rate').textContent = `${completionRate}%`;
}

function showToast(message, type = 'info') {
    // Simple toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#667eea'};
        color: white;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-weight: 600;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function showError(message) {
    const container = document.getElementById('candidate-list');
    container.innerHTML = `
        <div class="empty-state">
            <h3>Error</h3>
            <p>${message}</p>
            <button class="btn btn-primary" onclick="loadCandidates()">Retry</button>
        </div>
    `;
}

