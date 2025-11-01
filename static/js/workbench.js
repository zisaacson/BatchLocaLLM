/**
 * Unified Dataset Workbench
 * 
 * Integrates:
 * - Dataset upload & management
 * - Model running & live progress
 * - Side-by-side result comparison
 * - Inline annotation (golden/fix/wrong)
 * - Label Studio backend integration
 * - WebSocket live updates
 */

const API_BASE = 'http://localhost:4080/admin';
const LABEL_STUDIO_BASE = 'http://localhost:4015/api';

// State
let currentDataset = null;
let selectedModels = new Set();
let availableModels = [];
let datasets = [];
let results = [];
let activeJobs = [];
let ws = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadDatasets();
    loadModels();
    connectWebSocket();
    startPolling();
});

/**
 * Load datasets
 */
async function loadDatasets() {
    try {
        const response = await fetch(`${API_BASE}/datasets`);
        const data = await response.json();
        datasets = data.datasets || [];
        renderDatasets();
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
        container.innerHTML = '<p style="color: #718096; font-size: 13px;">No datasets</p>';
        return;
    }
    
    container.innerHTML = datasets.map(ds => `
        <div class="dataset-item ${currentDataset?.id === ds.id ? 'active' : ''}" 
             onclick="selectDataset('${ds.id}')">
            <div class="dataset-name">${ds.name}</div>
            <div class="dataset-meta">${ds.count.toLocaleString()} requests</div>
        </div>
    `).join('');
}

/**
 * Select dataset
 */
async function selectDataset(datasetId) {
    const dataset = datasets.find(d => d.id === datasetId);
    if (!dataset) return;
    
    currentDataset = dataset;
    renderDatasets();
    
    document.getElementById('dataset-title').textContent = 
        `${dataset.name} (${dataset.count.toLocaleString()} candidates)`;
    
    // Load results for this dataset
    await loadResults();
    
    // Update UI
    updateRunButton();
}

/**
 * Load available models
 */
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/models`);
        const data = await response.json();
        availableModels = data.models || [];
        renderModelSelector();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

/**
 * Render model selector chips
 */
function renderModelSelector() {
    const container = document.getElementById('model-selector');
    
    if (availableModels.length === 0) {
        container.innerHTML = '<p style="color: #718096; font-size: 13px;">No models available</p>';
        return;
    }
    
    container.innerHTML = availableModels.map(model => {
        const isSelected = selectedModels.has(model.model_id);
        const status = getModelStatus(model.model_id);
        
        let chipClass = 'model-chip';
        if (isSelected) chipClass += ' selected';
        if (status === 'running') chipClass += ' running';
        if (status === 'completed') chipClass += ' completed';
        
        return `
            <div class="${chipClass}" onclick="toggleModel('${model.model_id}')">
                ${model.name}
                ${status === 'running' ? ' ⏱️' : ''}
                ${status === 'completed' ? ' ✅' : ''}
            </div>
        `;
    }).join('');
}

/**
 * Get model status for current dataset
 */
function getModelStatus(modelId) {
    if (!currentDataset) return null;
    
    const job = activeJobs.find(j => 
        j.model_id === modelId && j.dataset_id === currentDataset.id
    );
    
    if (job) {
        return job.status === 'running' ? 'running' : 'completed';
    }
    
    // Check if we have results
    const hasResults = results.some(r => r.models[modelId]);
    return hasResults ? 'completed' : null;
}

/**
 * Toggle model selection
 */
function toggleModel(modelId) {
    if (selectedModels.has(modelId)) {
        selectedModels.delete(modelId);
    } else {
        selectedModels.add(modelId);
    }
    
    renderModelSelector();
    updateRunButton();
}

/**
 * Update run button state
 */
function updateRunButton() {
    const btn = document.getElementById('run-models');
    btn.disabled = !currentDataset || selectedModels.size === 0;
}

/**
 * Run selected models
 */
document.getElementById('run-models').addEventListener('click', async () => {
    if (!currentDataset || selectedModels.size === 0) return;
    
    for (const modelId of selectedModels) {
        try {
            const response = await fetch(`${API_BASE}/benchmarks/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_id: modelId,
                    dataset_id: currentDataset.id
                })
            });
            
            if (!response.ok) throw new Error('Failed to start benchmark');
            
            const data = await response.json();
            console.log(`Started benchmark: ${data.benchmark_id}`);
            
        } catch (error) {
            alert(`Failed to start ${modelId}: ${error.message}`);
        }
    }
    
    // Reload active jobs
    await loadActiveJobs();
});

/**
 * Load results for current dataset
 */
async function loadResults() {
    if (!currentDataset) return;
    
    try {
        const response = await fetch(
            `${API_BASE}/workbench/results?dataset_id=${currentDataset.id}`
        );
        const data = await response.json();
        results = data.results || [];
        renderResults();
        updateStats();
    } catch (error) {
        console.error('Failed to load results:', error);
    }
}

/**
 * Render results grid
 */
function renderResults() {
    const container = document.getElementById('results-container');
    
    if (results.length === 0) {
        container.innerHTML = '<p style="color: #718096; text-align: center; padding: 40px;">No results yet. Run a model to see results.</p>';
        return;
    }
    
    container.innerHTML = results.slice(0, 50).map(result => `
        <div class="result-card">
            <div class="candidate-header">
                <div class="candidate-info">
                    <h4>${result.candidate_name || result.candidate_id}</h4>
                    <p>${result.candidate_title || ''}</p>
                </div>
                <div class="candidate-actions">
                    <button class="icon-btn golden ${result.is_golden ? 'active' : ''}" 
                            onclick="toggleGolden('${result.candidate_id}')">
                        ⭐
                    </button>
                    <button class="icon-btn" onclick="editResult('${result.candidate_id}')">
                        ✏️
                    </button>
                    <button class="icon-btn" onclick="markWrong('${result.candidate_id}')">
                        ❌
                    </button>
                </div>
            </div>
            
            <div class="model-grid">
                ${renderModelResults(result)}
            </div>
        </div>
    `).join('');
}

/**
 * Render model results for a candidate
 */
function renderModelResults(result) {
    const modelIds = Object.keys(result.models || {});
    
    if (modelIds.length === 0) {
        return '<p style="color: #718096; font-size: 13px;">No model results</p>';
    }
    
    return modelIds.map(modelId => {
        const modelResult = result.models[modelId];
        const model = availableModels.find(m => m.model_id === modelId);
        
        if (!modelResult) return '';
        
        const isDifferent = checkIfDifferent(result, modelId);
        
        return `
            <div class="model-result ${isDifferent ? 'highlight' : ''}">
                <div class="model-result-header">
                    <span class="model-name">${model?.name || modelId}</span>
                    <span class="model-status status-completed">✅</span>
                </div>
                
                <div class="evaluation-fields">
                    <div class="eval-field">
                        <span class="eval-label">Recommendation</span>
                        <span class="eval-value">${modelResult.recommendation || 'N/A'}</span>
                    </div>
                    <div class="eval-field">
                        <span class="eval-label">Trajectory</span>
                        <span class="eval-value">${modelResult.trajectory || 'N/A'}</span>
                    </div>
                    <div class="eval-field">
                        <span class="eval-label">Pedigree</span>
                        <span class="eval-value">${modelResult.pedigree || 'N/A'}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Check if model result differs from others
 */
function checkIfDifferent(result, modelId) {
    const modelIds = Object.keys(result.models || {});
    if (modelIds.length <= 1) return false;
    
    const thisResult = result.models[modelId];
    const otherResults = modelIds
        .filter(id => id !== modelId)
        .map(id => result.models[id]);
    
    return otherResults.some(other => 
        other.recommendation !== thisResult.recommendation
    );
}

/**
 * Toggle golden status
 */
async function toggleGolden(candidateId) {
    try {
        await fetch(`${LABEL_STUDIO_BASE}/tasks/${candidateId}/golden`, {
            method: 'POST'
        });
        
        // Update local state
        const result = results.find(r => r.candidate_id === candidateId);
        if (result) {
            result.is_golden = !result.is_golden;
            renderResults();
            updateStats();
        }
    } catch (error) {
        console.error('Failed to toggle golden:', error);
    }
}

/**
 * Edit result (opens Label Studio annotation interface)
 */
function editResult(candidateId) {
    // Open Label Studio in modal or new tab
    window.open(`${LABEL_STUDIO_BASE}/tasks/${candidateId}/edit`, '_blank');
}

/**
 * Mark result as wrong
 */
async function markWrong(candidateId) {
    try {
        await fetch(`${LABEL_STUDIO_BASE}/tasks/${candidateId}/flag`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ flag: 'wrong' })
        });
        
        alert('Marked as wrong. Will be surfaced for review.');
    } catch (error) {
        console.error('Failed to mark wrong:', error);
    }
}

/**
 * Update stats
 */
function updateStats() {
    document.getElementById('stat-total').textContent = results.length;
    document.getElementById('stat-completed').textContent = 
        results.filter(r => Object.keys(r.models || {}).length > 0).length;
    document.getElementById('stat-golden').textContent = 
        results.filter(r => r.is_golden).length;
    document.getElementById('stat-fixed').textContent = 
        results.filter(r => r.is_fixed).length;
}

/**
 * Load active jobs
 */
async function loadActiveJobs() {
    try {
        const response = await fetch(`${API_BASE}/benchmarks/active`);
        const data = await response.json();
        activeJobs = data.jobs || [];
        renderActiveJobs();
        renderModelSelector(); // Update model chips
    } catch (error) {
        console.error('Failed to load active jobs:', error);
    }
}

/**
 * Render active jobs
 */
function renderActiveJobs() {
    const container = document.getElementById('active-jobs');
    
    if (activeJobs.length === 0) {
        container.innerHTML = '<p style="color: #718096; font-size: 13px;">No active jobs</p>';
        return;
    }
    
    container.innerHTML = activeJobs.map(job => `
        <div class="progress-item">
            <div class="progress-header">
                <span style="font-weight: 500;">${job.model_name}</span>
                <span>${job.progress}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${job.progress}%"></div>
            </div>
            <div class="progress-meta">
                ${job.completed}/${job.total} • ${job.throughput.toFixed(1)} tok/s • ETA ${formatTime(job.eta_seconds)}
            </div>
        </div>
    `).join('');
}

/**
 * Connect WebSocket for live updates
 */
function connectWebSocket() {
    ws = new WebSocket('ws://localhost:4080/ws/workbench');
    
    ws.onmessage = (event) => {
        const update = JSON.parse(event.data);
        
        if (update.type === 'progress') {
            updateJobProgress(update);
        }
        
        if (update.type === 'result') {
            addNewResult(update);
        }
    };
    
    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        setTimeout(connectWebSocket, 5000);
    };
}

/**
 * Update job progress from WebSocket
 */
function updateJobProgress(update) {
    const job = activeJobs.find(j => j.benchmark_id === update.benchmark_id);
    if (job) {
        job.progress = update.progress;
        job.completed = update.completed;
        job.throughput = update.throughput;
        job.eta_seconds = update.eta_seconds;
        renderActiveJobs();
    }
}

/**
 * Add new result from WebSocket
 */
function addNewResult(update) {
    // Add to results array
    const existingIndex = results.findIndex(r => r.candidate_id === update.candidate_id);
    
    if (existingIndex >= 0) {
        // Update existing result
        if (!results[existingIndex].models) {
            results[existingIndex].models = {};
        }
        results[existingIndex].models[update.model_id] = update.response;
    } else {
        // Add new result
        results.push({
            candidate_id: update.candidate_id,
            candidate_name: update.candidate_name,
            candidate_title: update.candidate_title,
            models: {
                [update.model_id]: update.response
            }
        });
    }
    
    renderResults();
    updateStats();
}

/**
 * Format time
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
    setInterval(() => {
        if (activeJobs.length > 0) {
            loadActiveJobs();
        }
    }, 2000);
}

/**
 * Upload dataset
 */
function uploadDataset() {
    // Create file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.jsonl';

    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Validate file extension
        if (!file.name.endsWith('.jsonl')) {
            alert('Please upload a .jsonl file');
            return;
        }

        // Upload file
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(`${API_BASE}/datasets/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('Dataset uploaded:', data);

            // Reload datasets
            await loadDatasets();

            // Select the new dataset
            currentDataset = datasets.find(d => d.id === data.dataset_id);
            renderDatasets();
            loadResults();

        } catch (error) {
            console.error('Failed to upload dataset:', error);
            alert(`Failed to upload dataset: ${error.message}`);
        }
    };

    // Trigger file picker
    input.click();
}

/**
 * Show add model dialog
 */
function showAddModelDialog() {
    document.getElementById('add-model-dialog').style.display = 'block';
    document.getElementById('hf-content').value = '';
    document.getElementById('parse-result').style.display = 'none';
    document.getElementById('add-model-btn').style.display = 'none';
}

/**
 * Close add model dialog
 */
function closeAddModelDialog() {
    document.getElementById('add-model-dialog').style.display = 'none';
}

let parsedModelConfig = null;

/**
 * Parse HuggingFace content
 */
async function parseHuggingFaceContent() {
    const content = document.getElementById('hf-content').value.trim();

    if (!content) {
        alert('Please paste HuggingFace model page content');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/models/parse-huggingface`, {
            method: 'POST',
            headers: {
                'Content-Type': 'text/plain'
            },
            body: content
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to parse content');
        }

        const data = await response.json();
        parsedModelConfig = data.model_config;

        // Display parsed result
        const resultDiv = document.getElementById('parse-result-content');
        resultDiv.innerHTML = `
            <div style="display: grid; grid-template-columns: 200px 1fr; gap: 10px; font-size: 14px;">
                <strong>Model ID:</strong>
                <span>${parsedModelConfig.model_id}</span>

                <strong>Name:</strong>
                <span>${parsedModelConfig.name}</span>

                <strong>Size:</strong>
                <span>${parsedModelConfig.size_gb} GB</span>

                <strong>Estimated Memory:</strong>
                <span>${parsedModelConfig.estimated_memory_gb} GB</span>

                <strong>RTX 4080 Compatible:</strong>
                <span>${parsedModelConfig.rtx4080_compatible ? '✅ YES' : '❌ NO'}</span>

                <strong>CPU Offload Needed:</strong>
                <span>${parsedModelConfig.cpu_offload_gb} GB</span>

                <strong>Quantization:</strong>
                <span>${parsedModelConfig.is_quantized ? parsedModelConfig.quantization_type : 'None (FP16)'}</span>

                <strong>GGUF Format:</strong>
                <span>${parsedModelConfig.is_gguf ? 'Yes' : 'No'}</span>
            </div>

            <div style="margin-top: 15px;">
                <strong>📋 Recommendations:</strong>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    ${parsedModelConfig.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>

            <div style="margin-top: 15px;">
                <strong>🚀 Optimized vLLM Command:</strong>
                <pre style="background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px;">${parsedModelConfig.vllm_serve_command}</pre>
            </div>

            ${parsedModelConfig.installation_notes ? `
            <div style="margin-top: 15px;">
                <strong>📦 Installation:</strong>
                <pre style="background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px; overflow-x: auto; margin-top: 5px;">${parsedModelConfig.installation_notes}</pre>
            </div>
            ` : ''}
        `;

        document.getElementById('parse-result').style.display = 'block';
        document.getElementById('add-model-btn').style.display = 'inline-block';

    } catch (error) {
        console.error('Failed to parse HuggingFace content:', error);
        alert(`Failed to parse content: ${error.message}`);
    }
}

/**
 * Add parsed model to registry
 */
async function addParsedModel() {
    if (!parsedModelConfig) {
        alert('Please parse content first');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/models/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_id: parsedModelConfig.model_id,
                name: parsedModelConfig.name,
                size_gb: parsedModelConfig.size_gb,
                estimated_memory_gb: parsedModelConfig.estimated_memory_gb,
                cpu_offload_gb: parsedModelConfig.cpu_offload_gb,
                rtx4080_compatible: parsedModelConfig.rtx4080_compatible,
                requires_hf_auth: parsedModelConfig.requires_hf_auth,
                vllm_serve_command: parsedModelConfig.vllm_serve_command,
                installation_notes: parsedModelConfig.installation_notes,
                huggingface_url: null,
                max_model_len: 4096,
                gpu_memory_utilization: 0.90,
                enable_prefix_caching: true,
                chunked_prefill_enabled: true
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add model');
        }

        alert(`✅ Model added: ${parsedModelConfig.name}`);
        closeAddModelDialog();

        // Reload models
        await loadModels();

    } catch (error) {
        console.error('Failed to add model:', error);
        alert(`Failed to add model: ${error.message}`);
    }
}

/**
 * Add model
 */
function addModel() {
    window.location.href = '/static/model-management.html';
}

/**
 * Export golden dataset
 */
document.getElementById('export-golden').addEventListener('click', async () => {
    const golden = results.filter(r => r.is_golden);
    
    if (golden.length === 0) {
        alert('No golden examples marked yet!');
        return;
    }
    
    // Export to Label Studio format
    const exportData = golden.map(r => ({
        data: {
            candidate_id: r.candidate_id,
            candidate_name: r.candidate_name,
            candidate_title: r.candidate_title
        },
        predictions: Object.entries(r.models).map(([modelId, response]) => ({
            model_id: modelId,
            result: response
        }))
    }));
    
    // Download as JSON
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `golden_dataset_${currentDataset.name}_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    
    alert(`Exported ${golden.length} golden examples!`);
});

