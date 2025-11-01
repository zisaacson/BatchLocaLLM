/**
 * Benchmark Runner UI
 * 
 * Features:
 * - Upload test datasets
 * - Run any model on any dataset
 * - Live progress tracking
 * - View results (live and post-completion)
 */

const API_BASE = 'http://localhost:4080/admin';

// State
let datasets = [];
let models = [];
let activeBenchmarks = [];
let completedBenchmarks = [];
let selectedDataset = null;
let pollInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    loadModels();
    loadDatasets();
    loadBenchmarks();
    startPolling();
});

/**
 * Setup file upload (drag & drop + click)
 */
function setupFileUpload() {
    const uploadArea = document.getElementById('file-upload');
    const fileInput = document.getElementById('file-input');

    uploadArea.addEventListener('click', () => fileInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.jsonl')) {
            uploadDataset(file);
        } else {
            alert('Please upload a .jsonl file');
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            uploadDataset(file);
        }
    });
}

/**
 * Upload dataset to server
 */
async function uploadDataset(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/datasets/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Upload failed');
        
        const data = await response.json();
        alert(`✅ Uploaded ${data.name} (${data.count} requests)`);
        loadDatasets();
    } catch (error) {
        alert('❌ Upload failed: ' + error.message);
    }
}

/**
 * Load available datasets
 */
async function loadDatasets() {
    try {
        const response = await fetch(`${API_BASE}/datasets`);
        const data = await response.json();
        datasets = data.datasets || [];
        renderDatasets();
        updateDatasetSelect();
    } catch (error) {
        console.error('Failed to load datasets:', error);
    }
}

/**
 * Render dataset list
 */
function renderDatasets() {
    const container = document.getElementById('dataset-list');
    
    if (datasets.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = datasets.map(ds => `
        <div class="dataset-card ${selectedDataset === ds.id ? 'selected' : ''}" 
             onclick="selectDataset('${ds.id}')">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong>${ds.name}</strong>
                    <div style="font-size: 12px; color: #718096; margin-top: 4px;">
                        ${ds.count} requests • Uploaded ${new Date(ds.uploaded_at).toLocaleDateString()}
                    </div>
                </div>
                <button class="btn" style="padding: 6px 12px; font-size: 12px;" 
                        onclick="event.stopPropagation(); deleteDataset('${ds.id}')">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

/**
 * Select dataset
 */
function selectDataset(datasetId) {
    selectedDataset = datasetId;
    renderDatasets();
    updateDatasetSelect();
    updateRunButton();
}

/**
 * Update dataset dropdown
 */
function updateDatasetSelect() {
    const select = document.getElementById('dataset-select');
    select.innerHTML = datasets.length === 0 
        ? '<option value="">No datasets uploaded</option>'
        : datasets.map(ds => 
            `<option value="${ds.id}" ${selectedDataset === ds.id ? 'selected' : ''}>
                ${ds.name} (${ds.count} requests)
            </option>`
          ).join('');
    
    select.addEventListener('change', (e) => {
        selectedDataset = e.target.value;
        updateRunButton();
    });
}

/**
 * Load available models
 */
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/models`);
        const data = await response.json();
        models = data.models || [];
        updateModelSelect();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

/**
 * Update model dropdown
 */
function updateModelSelect() {
    const select = document.getElementById('model-select');
    select.innerHTML = models.length === 0
        ? '<option value="">No models available</option>'
        : models.map(m => 
            `<option value="${m.model_id}">${m.name}</option>`
          ).join('');
    
    select.addEventListener('change', updateRunButton);
}

/**
 * Update run button state
 */
function updateRunButton() {
    const btn = document.getElementById('run-benchmark');
    const modelSelect = document.getElementById('model-select');
    const datasetSelect = document.getElementById('dataset-select');
    
    const canRun = modelSelect.value && datasetSelect.value;
    btn.disabled = !canRun;
}

/**
 * Run benchmark
 */
document.getElementById('run-benchmark').addEventListener('click', async () => {
    const modelId = document.getElementById('model-select').value;
    const datasetId = document.getElementById('dataset-select').value;
    
    if (!modelId || !datasetId) return;
    
    try {
        const response = await fetch(`${API_BASE}/benchmarks/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model_id: modelId,
                dataset_id: datasetId
            })
        });
        
        if (!response.ok) throw new Error('Failed to start benchmark');
        
        const data = await response.json();
        alert(`✅ Benchmark started: ${data.benchmark_id}`);
        loadBenchmarks();
    } catch (error) {
        alert('❌ Failed to start benchmark: ' + error.message);
    }
});

/**
 * Load benchmarks
 */
async function loadBenchmarks() {
    try {
        const response = await fetch(`${API_BASE}/benchmarks`);
        const data = await response.json();
        
        activeBenchmarks = data.benchmarks.filter(b => b.status === 'running');
        completedBenchmarks = data.benchmarks.filter(b => b.status === 'completed');
        
        renderActiveBenchmarks();
        renderCompletedBenchmarks();
    } catch (error) {
        console.error('Failed to load benchmarks:', error);
    }
}

/**
 * Render active benchmarks
 */
function renderActiveBenchmarks() {
    const container = document.getElementById('active-benchmarks');
    
    if (activeBenchmarks.length === 0) {
        container.innerHTML = '<p style="color: #718096;">No active benchmarks</p>';
        return;
    }
    
    container.innerHTML = activeBenchmarks.map(b => `
        <div class="benchmark-card">
            <div class="benchmark-header">
                <div>
                    <strong>${b.model_name}</strong> on <strong>${b.dataset_name}</strong>
                    <div style="font-size: 12px; color: #718096; margin-top: 4px;">
                        Started ${new Date(b.started_at).toLocaleTimeString()}
                    </div>
                </div>
                <span class="benchmark-status status-running">⏱️ Running</span>
            </div>
            
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${b.progress}%"></div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Progress</div>
                    <div class="metric-value">${b.completed}/${b.total}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Throughput</div>
                    <div class="metric-value">${b.throughput.toFixed(1)} tok/s</div>
                </div>
                <div class="metric">
                    <div class="metric-label">ETA</div>
                    <div class="metric-value">${formatTime(b.eta_seconds)}</div>
                </div>
            </div>
        </div>
    `).join('');
}

/**
 * Render completed benchmarks
 */
function renderCompletedBenchmarks() {
    const container = document.getElementById('completed-benchmarks');
    
    if (completedBenchmarks.length === 0) {
        container.innerHTML = '<p style="color: #718096;">No completed benchmarks</p>';
        return;
    }
    
    container.innerHTML = completedBenchmarks.map(b => `
        <div class="benchmark-card">
            <div class="benchmark-header">
                <div>
                    <strong>${b.model_name}</strong> on <strong>${b.dataset_name}</strong>
                    <div style="font-size: 12px; color: #718096; margin-top: 4px;">
                        Completed ${new Date(b.completed_at).toLocaleString()}
                    </div>
                </div>
                <span class="benchmark-status status-completed">✅ Completed</span>
            </div>
            
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-label">Total Time</div>
                    <div class="metric-value">${formatTime(b.total_time_seconds)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Throughput</div>
                    <div class="metric-value">${b.throughput.toFixed(1)} tok/s</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Requests</div>
                    <div class="metric-value">${b.total}</div>
                </div>
            </div>
            
            <button class="btn btn-primary" style="margin-top: 15px;" 
                    onclick="viewResults('${b.benchmark_id}')">
                📊 View Results
            </button>
        </div>
    `).join('');
}

/**
 * View benchmark results
 */
function viewResults(benchmarkId) {
    window.location.href = `/static/benchmark-results.html?id=${benchmarkId}`;
}

/**
 * Delete dataset
 */
async function deleteDataset(datasetId) {
    if (!confirm('Delete this dataset?')) return;
    
    try {
        await fetch(`${API_BASE}/datasets/${datasetId}`, { method: 'DELETE' });
        loadDatasets();
    } catch (error) {
        alert('Failed to delete dataset');
    }
}

/**
 * Format seconds to human readable time
 */
function formatTime(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${(seconds / 3600).toFixed(1)}h`;
}

/**
 * Start polling for updates
 */
function startPolling() {
    pollInterval = setInterval(() => {
        if (activeBenchmarks.length > 0) {
            loadBenchmarks();
        }
    }, 2000); // Poll every 2 seconds
}

