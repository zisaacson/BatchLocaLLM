/**
 * Conquest Viewer JavaScript
 * 
 * Handles conquest listing, filtering, and annotation
 */

// State
let conquests = [];
let currentPage = 0;
let totalConquests = 0;
const pageSize = 50;
let currentConquest = null;
let selectedRating = 0;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadConquests();
    
    // Add filter event listeners
    document.getElementById('statusFilter').addEventListener('change', loadConquests);
    document.getElementById('resultFilter').addEventListener('change', loadConquests);
    document.getElementById('typeFilter').addEventListener('change', loadConquests);
    document.getElementById('goldStarFilter').addEventListener('change', loadConquests);
});

// Load conquests from API
async function loadConquests() {
    const container = document.getElementById('conquestListContainer');
    container.innerHTML = '<div class="loading">Loading conquests...</div>';
    
    try {
        // Build query parameters
        const params = new URLSearchParams();
        params.append('limit', pageSize);
        params.append('offset', currentPage * pageSize);
        
        const status = document.getElementById('statusFilter').value;
        if (status) params.append('status', status);
        
        const result = document.getElementById('resultFilter').value;
        if (result) params.append('result', result);
        
        const type = document.getElementById('typeFilter').value;
        if (type) params.append('conquestType', type);
        
        const goldStar = document.getElementById('goldStarFilter').value;
        if (goldStar) params.append('useAsExample', goldStar);
        
        // Fetch conquests
        const response = await fetch(`/v1/conquests?${params}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        conquests = data.conquests;
        totalConquests = data.total;
        
        renderConquests();
        renderPagination();
    } catch (error) {
        console.error('Failed to load conquests:', error);
        container.innerHTML = `<div class="empty-state">❌ Failed to load conquests: ${error.message}</div>`;
    }
}

// Render conquest list
function renderConquests() {
    const container = document.getElementById('conquestListContainer');
    
    if (conquests.length === 0) {
        container.innerHTML = '<div class="empty-state">No conquests found</div>';
        return;
    }
    
    container.innerHTML = conquests.map(conquest => `
        <div class="conquest-item" onclick="viewConquest('${conquest.id}')">
            <div class="conquest-header">
                <div class="conquest-title">${escapeHtml(conquest.title)}</div>
                <div>
                    ${conquest.useAsExample ? '<span class="badge badge-gold-star">⭐ Gold Star</span>' : ''}
                    <span class="badge badge-${conquest.result.toLowerCase()}">${conquest.result}</span>
                    <span class="badge badge-${conquest.status.toLowerCase()}">${conquest.status}</span>
                </div>
            </div>
            <div class="conquest-meta">
                <span>Type: ${conquest.conquestType}</span>
                <span>Created: ${formatDate(conquest.createdAt)}</span>
                ${conquest.completedAt ? `<span>Completed: ${formatDate(conquest.completedAt)}</span>` : ''}
                ${conquest.executionTimeMs ? `<span>Duration: ${formatDuration(conquest.executionTimeMs)}</span>` : ''}
            </div>
        </div>
    `).join('');
}

// Render pagination
function renderPagination() {
    const container = document.getElementById('pagination');
    const totalPages = Math.ceil(totalConquests / pageSize);
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = `
        <button onclick="goToPage(0)" ${currentPage === 0 ? 'disabled' : ''}>First</button>
        <button onclick="goToPage(${currentPage - 1})" ${currentPage === 0 ? 'disabled' : ''}>Previous</button>
        <span>Page ${currentPage + 1} of ${totalPages}</span>
        <button onclick="goToPage(${currentPage + 1})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Next</button>
        <button onclick="goToPage(${totalPages - 1})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>Last</button>
    `;
}

// Go to page
function goToPage(page) {
    currentPage = page;
    loadConquests();
}

// View conquest details
async function viewConquest(conquestId) {
    try {
        const response = await fetch(`/v1/conquests/${conquestId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        currentConquest = await response.json();
        renderConquestDetail();
        document.getElementById('conquestModal').style.display = 'block';
    } catch (error) {
        console.error('Failed to load conquest:', error);
        alert(`Failed to load conquest: ${error.message}`);
    }
}

// Render conquest detail modal
function renderConquestDetail() {
    const conquest = currentConquest;
    document.getElementById('modalTitle').textContent = conquest.title;
    
    document.getElementById('modalBody').innerHTML = `
        <div class="detail-row">
            <div class="detail-label">ID</div>
            <div class="detail-value">${conquest.id}</div>
        </div>
        
        <div class="detail-row">
            <div class="detail-label">Type</div>
            <div class="detail-value">${conquest.conquestType}</div>
        </div>
        
        <div class="detail-row">
            <div class="detail-label">Status</div>
            <div class="detail-value">
                <span class="badge badge-${conquest.status.toLowerCase()}">${conquest.status}</span>
            </div>
        </div>
        
        <div class="detail-row">
            <div class="detail-label">Result</div>
            <div class="detail-value">
                <span class="badge badge-${conquest.result.toLowerCase()}">${conquest.result}</span>
                ${conquest.useAsExample ? '<span class="badge badge-gold-star">⭐ Gold Star</span>' : ''}
            </div>
        </div>
        
        ${conquest.description ? `
        <div class="detail-row">
            <div class="detail-label">Description</div>
            <div class="detail-value">${escapeHtml(conquest.description)}</div>
        </div>
        ` : ''}
        
        ${conquest.resultNotes ? `
        <div class="detail-row">
            <div class="detail-label">Result Notes</div>
            <div class="detail-value">${escapeHtml(conquest.resultNotes)}</div>
        </div>
        ` : ''}
        
        ${conquest.fineTunedModelId ? `
        <div class="detail-row">
            <div class="detail-label">Fine-Tuned Model</div>
            <div class="detail-value">${conquest.fineTunedModelId}</div>
        </div>
        ` : ''}
        
        <div class="detail-row">
            <div class="detail-label">Created</div>
            <div class="detail-value">${formatDate(conquest.createdAt)}</div>
        </div>
        
        ${conquest.completedAt ? `
        <div class="detail-row">
            <div class="detail-label">Completed</div>
            <div class="detail-value">${formatDate(conquest.completedAt)}</div>
        </div>
        ` : ''}
        
        ${conquest.executionTimeMs ? `
        <div class="detail-row">
            <div class="detail-label">Execution Time</div>
            <div class="detail-value">${formatDuration(conquest.executionTimeMs)}</div>
        </div>
        ` : ''}
        
        ${conquest.evaluatedBy ? `
        <div class="detail-row">
            <div class="detail-label">Evaluated By</div>
            <div class="detail-value">${conquest.evaluatedBy}</div>
        </div>
        ` : ''}
        
        <div class="annotation-form">
            <h3 style="margin-top: 0;">Annotate Conquest</h3>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" id="goldStarCheckbox">
                    Mark as Gold Star (use for training)
                </label>
            </div>
            
            <div class="form-group">
                <label>Quality Rating</label>
                <div class="rating-stars" id="ratingStars">
                    ${[1, 2, 3, 4, 5].map(i => `<span class="star" onclick="setRating(${i})">★</span>`).join('')}
                </div>
            </div>
            
            <div class="form-group">
                <label>Feedback</label>
                <textarea id="feedbackText" rows="3" placeholder="Enter feedback..."></textarea>
            </div>
            
            <div class="form-group">
                <label>Improvement Notes</label>
                <textarea id="improvementText" rows="3" placeholder="Enter improvement notes..."></textarea>
            </div>
            
            <div style="display: flex; gap: 10px;">
                <button class="btn btn-primary" onclick="submitAnnotation()">Submit Annotation</button>
                <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
            </div>
        </div>
    `;
}

// Set rating
function setRating(rating) {
    selectedRating = rating;
    const stars = document.querySelectorAll('.star');
    stars.forEach((star, index) => {
        if (index < rating) {
            star.classList.add('active');
        } else {
            star.classList.remove('active');
        }
    });
}

// Submit annotation
async function submitAnnotation() {
    if (selectedRating === 0) {
        alert('Please select a rating');
        return;
    }
    
    const annotation = {
        isGoldStar: document.getElementById('goldStarCheckbox').checked,
        rating: selectedRating,
        feedback: document.getElementById('feedbackText').value || null,
        improvementNotes: document.getElementById('improvementText').value || null
    };
    
    try {
        const response = await fetch(`/v1/conquests/${currentConquest.id}/annotate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(annotation)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const result = await response.json();
        alert('Annotation submitted successfully!');
        closeModal();
        loadConquests(); // Reload list
    } catch (error) {
        console.error('Failed to submit annotation:', error);
        alert(`Failed to submit annotation: ${error.message}`);
    }
}

// Close modal
function closeModal() {
    document.getElementById('conquestModal').style.display = 'none';
    currentConquest = null;
    selectedRating = 0;
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function formatDuration(ms) {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
    return `${(ms / 3600000).toFixed(1)}h`;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('conquestModal');
    if (event.target === modal) {
        closeModal();
    }
}

