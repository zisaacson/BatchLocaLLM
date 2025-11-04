/**
 * Fine-Tuning Dashboard JavaScript
 * 
 * Manages training jobs, datasets, and model deployment.
 */

// Configuration
const API_BASE = window.location.origin;
const REFRESH_INTERVAL = 5000; // 5 seconds

// State
let currentUser = {
    philosopher: 'user@example.com',  // Generic default user
    domain: 'default'  // Generic default domain
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    setInterval(refreshActiveJobs, REFRESH_INTERVAL);
});

// ============================================================================
// Dashboard Loading
// ============================================================================

async function loadDashboard() {
    await Promise.all([
        loadStats(),
        loadDatasets(),
        loadActiveJobs(),
        loadDeployedModels()
    ]);
}

async function loadStats() {
    try {
        // Load models to calculate stats
        const models = await fetch(`${API_BASE}/v1/fine-tuning/models?philosopher=${currentUser.philosopher}&domain=${currentUser.domain}`)
            .then(r => r.json());
        
        // Calculate stats
        const deployedModels = models.filter(m => m.status === 'deployed');
        const avgWinRate = deployedModels.length > 0
            ? (deployedModels.reduce((sum, m) => sum + (m.win_rate || 0), 0) / deployedModels.length).toFixed(1)
            : '0.0';
        
        document.getElementById('goldStarCount').textContent = '42'; // TODO: Get from API
        document.getElementById('activeJobsCount').textContent = '0'; // Will be updated by loadActiveJobs
        document.getElementById('deployedModelsCount').textContent = deployedModels.length;
        document.getElementById('avgWinRate').textContent = `${avgWinRate}%`;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadDatasets() {
    const container = document.getElementById('datasetsTable');
    
    // TODO: Implement dataset listing API
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📊</div>
            <p>No datasets exported yet</p>
            <p style="font-size: 14px; margin-top: 8px;">Click "Export Dataset" to create your first training dataset</p>
        </div>
    `;
}

async function loadActiveJobs() {
    const container = document.getElementById('activeJobsTable');
    
    try {
        // TODO: Implement job listing API
        // For now, show empty state
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🚀</div>
                <p>No active training jobs</p>
                <p style="font-size: 14px; margin-top: 8px;">Click "Start Training" to begin fine-tuning a model</p>
            </div>
        `;
        
        document.getElementById('activeJobsCount').textContent = '0';
    } catch (error) {
        console.error('Error loading active jobs:', error);
        container.innerHTML = '<p style="color: red;">Error loading jobs</p>';
    }
}

async function loadDeployedModels() {
    const container = document.getElementById('deployedModelsTable');
    
    try {
        const models = await fetch(`${API_BASE}/v1/fine-tuning/models?philosopher=${currentUser.philosopher}&domain=${currentUser.domain}`)
            .then(r => r.json());
        
        const deployedModels = models.filter(m => m.status === 'deployed');
        
        if (deployedModels.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">✅</div>
                    <p>No deployed models yet</p>
                    <p style="font-size: 14px; margin-top: 8px;">Complete a training job to deploy your first model</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Model</th>
                        <th>Version</th>
                        <th>Win Rate</th>
                        <th>Gold Star Rate</th>
                        <th>Deployed</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${deployedModels.map(model => `
                        <tr>
                            <td><strong>${model.name}</strong></td>
                            <td>${model.version}</td>
                            <td>${model.win_rate ? model.win_rate.toFixed(1) + '%' : '-'}</td>
                            <td>${model.gold_star_rate ? model.gold_star_rate.toFixed(1) + '%' : '-'}</td>
                            <td>${formatDate(model.deployed_at)}</td>
                            <td>
                                <button class="btn btn-secondary" onclick="compareModel('${model.id}')">Compare</button>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (error) {
        console.error('Error loading deployed models:', error);
        container.innerHTML = '<p style="color: red;">Error loading models</p>';
    }
}

async function refreshActiveJobs() {
    // Only refresh if there are active jobs
    const count = parseInt(document.getElementById('activeJobsCount').textContent);
    if (count > 0) {
        await loadActiveJobs();
    }
}

// ============================================================================
// Export Dataset Modal
// ============================================================================

function showExportModal() {
    document.getElementById('exportModal').style.display = 'block';
    document.getElementById('exportPhilosopher').value = currentUser.philosopher;
    document.getElementById('exportDomain').value = currentUser.domain;
}

function closeExportModal() {
    document.getElementById('exportModal').style.display = 'none';
}

document.getElementById('exportForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        philosopher: document.getElementById('exportPhilosopher').value,  // User email
        domain: document.getElementById('exportDomain').value,  // Project/domain
        conquest_type: document.getElementById('exportConquestType').value || null,  // Dataset type
        format: document.getElementById('exportFormat').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/v1/fine-tuning/datasets/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Export failed');
        }
        
        const result = await response.json();
        alert(`✅ Exported ${result.sample_count} samples to ${result.dataset_path}`);
        
        closeExportModal();
        loadDatasets();
    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    }
});

// ============================================================================
// Training Modal
// ============================================================================

function showTrainModal() {
    // TODO: Implement training modal
    alert('Training modal coming soon!');
}

// ============================================================================
// Model Actions
// ============================================================================

function compareModel(modelId) {
    window.location.href = `/model-comparison.html?model=${modelId}`;
}

// ============================================================================
// Utilities
// ============================================================================

function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return `${Math.floor(diffDays / 30)}mo ago`;
}

function formatProgress(progress) {
    return `
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${progress}%"></div>
        </div>
        <div style="font-size: 12px; color: #718096; margin-top: 4px;">${progress.toFixed(1)}%</div>
    `;
}

function formatStatus(status) {
    const statusClass = `status-${status.toLowerCase()}`;
    return `<span class="status-badge ${statusClass}">${status}</span>`;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('exportModal');
    if (event.target === modal) {
        closeExportModal();
    }
};

