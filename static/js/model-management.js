/**
 * Model Management UI
 * 
 * Features:
 * - Add new models from HuggingFace
 * - Test models with live progress
 * - View benchmark results
 * - Delete models
 */

const API_BASE = 'http://localhost:4080/admin';

// State
let models = [];
let activeTests = new Set();
let pollInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    setupFormHandler();
    startPolling();
});

/**
 * Load all models from API
 */
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/models`);
        const data = await response.json();
        models = data.models;
        renderModels();
    } catch (error) {
        showToast('Failed to load models', 'error');
        console.error(error);
    }
}

/**
 * Render models grid
 */
function renderModels() {
    const grid = document.getElementById('models-grid');
    
    if (models.length === 0) {
        grid.innerHTML = '<p style="color: white; text-align: center;">No models yet. Add one above!</p>';
        return;
    }
    
    grid.innerHTML = models.map(model => `
        <div class="model-card" data-model-id="${model.model_id}">
            <div class="model-header">
                <div>
                    <h3 class="model-name">${model.name}</h3>
                    <div class="model-id">${model.model_id}</div>
                </div>
                <span class="status-badge status-${model.status}">${model.status}</span>
            </div>
            
            <div class="model-stats">
                <div class="stat">
                    <div class="stat-label">Size</div>
                    <div class="stat-value">${model.size_gb} GB</div>
                </div>
                <div class="stat">
                    <div class="stat-label">GPU Memory</div>
                    <div class="stat-value">${model.estimated_memory_gb} GB</div>
                </div>
                ${model.cpu_offload_gb > 0 ? `
                <div class="stat">
                    <div class="stat-label">CPU Offload</div>
                    <div class="stat-value">${model.cpu_offload_gb} GB</div>
                </div>
                ` : ''}
                ${model.throughput_tokens_per_sec ? `
                <div class="stat">
                    <div class="stat-label">Throughput</div>
                    <div class="stat-value">${model.throughput_tokens_per_sec.toFixed(1)} tok/s</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Latency</div>
                    <div class="stat-value">${model.avg_latency_ms.toFixed(0)} ms</div>
                </div>
                ` : ''}
            </div>
            
            ${activeTests.has(model.model_id) ? `
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-${model.model_id.replace('/', '-')}" style="width: 0%"></div>
                </div>
                <div class="log-viewer" id="logs-${model.model_id.replace('/', '-')}">
                    Loading...
                </div>
            ` : ''}
            
            <div class="model-actions">
                ${model.status !== 'testing' ? `
                    <button class="btn btn-primary" onclick="testModel('${model.model_id}', 1)">
                        Test (1 req)
                    </button>
                    <button class="btn btn-secondary" onclick="testModel('${model.model_id}', 100)">
                        Test (100 req)
                    </button>
                ` : `
                    <button class="btn btn-secondary" disabled>Testing...</button>
                `}
                <button class="btn btn-danger" onclick="deleteModel('${model.model_id}')">
                    Delete
                </button>
            </div>
        </div>
    `).join('');
}

/**
 * Validate HuggingFace model ID format
 */
function validateModelId(modelId) {
    // Format: username/model-name or organization/model-name
    const pattern = /^[a-zA-Z0-9_-]+\/[a-zA-Z0-9_.-]+$/;
    return pattern.test(modelId);
}

/**
 * Fetch model info from HuggingFace API
 */
async function fetchModelInfo(modelId) {
    try {
        const response = await fetch(`https://huggingface.co/api/models/${modelId}`);
        if (!response.ok) {
            throw new Error('Model not found on HuggingFace');
        }
        const data = await response.json();
        return {
            exists: true,
            size_gb: data.safetensors?.total || 0,
            tags: data.tags || [],
            pipeline_tag: data.pipeline_tag
        };
    } catch (error) {
        return { exists: false, error: error.message };
    }
}

/**
 * Auto-fill model info from HuggingFace
 */
async function autoFillModelInfo() {
    const modelIdInput = document.getElementById('model-id');
    const modelId = modelIdInput.value.trim();

    if (!modelId) {
        return;
    }

    // Validate format
    if (!validateModelId(modelId)) {
        showToast('Invalid model ID format. Use: username/model-name', 'error');
        return;
    }

    // Show loading state
    const submitBtn = document.querySelector('#add-model-form button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Fetching model info...';
    submitBtn.disabled = true;

    try {
        const info = await fetchModelInfo(modelId);

        if (!info.exists) {
            showToast(`Model not found: ${info.error}`, 'error');
            return;
        }

        // Auto-fill name if empty
        const nameInput = document.getElementById('model-name');
        if (!nameInput.value) {
            nameInput.value = modelId.split('/')[1];
        }

        // Auto-fill size if available
        if (info.size_gb > 0) {
            const sizeGb = (info.size_gb / (1024 ** 3)).toFixed(2);
            document.getElementById('size-gb').value = sizeGb;

            // Estimate memory (rough: 1.2x model size)
            const estimatedMemory = (parseFloat(sizeGb) * 1.2).toFixed(2);
            document.getElementById('memory-gb').value = estimatedMemory;
        }

        showToast('Model info loaded from HuggingFace!', 'success');
    } catch (error) {
        showToast(`Failed to fetch model info: ${error.message}`, 'error');
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

/**
 * Parse HuggingFace vLLM command from clipboard
 */
function parseVLLMCommand(text) {
    // Match patterns like:
    // vllm serve "google/gemma-3-4b-it"
    // vllm serve 'google/gemma-3-4b-it'
    // "model": "google/gemma-3-4b-it"
    const patterns = [
        /vllm\s+serve\s+["']([^"']+)["']/,
        /"model"\s*:\s*"([^"]+)"/,
        /'model'\s*:\s*'([^']+)'/
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (match) {
            return match[1];
        }
    }

    return null;
}

/**
 * Setup add model form handler
 */
function setupFormHandler() {
    const form = document.getElementById('add-model-form');
    const modelIdInput = document.getElementById('model-id');

    // Add paste event to parse HuggingFace vLLM commands
    modelIdInput.addEventListener('paste', (e) => {
        const pastedText = e.clipboardData.getData('text');
        const modelId = parseVLLMCommand(pastedText);

        if (modelId) {
            e.preventDefault();
            modelIdInput.value = modelId;
            showToast(`Parsed model ID: ${modelId}`, 'success');
            // Trigger auto-fill after a short delay
            setTimeout(() => autoFillModelInfo(), 100);
        }
    });

    // Add blur event to auto-fill model info
    modelIdInput.addEventListener('blur', autoFillModelInfo);

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const modelId = document.getElementById('model-id').value.trim();

        // Validate model ID
        if (!validateModelId(modelId)) {
            showToast('Invalid model ID format. Use: username/model-name', 'error');
            return;
        }

        const modelData = {
            model_id: modelId,
            name: document.getElementById('model-name').value,
            size_gb: parseFloat(document.getElementById('size-gb').value),
            estimated_memory_gb: parseFloat(document.getElementById('memory-gb').value),
            cpu_offload_gb: parseFloat(document.getElementById('cpu-offload-gb').value) || 0,
            max_model_len: 4096,
            gpu_memory_utilization: 0.90,
            enable_prefix_caching: true,
            chunked_prefill_enabled: true,
            rtx4080_compatible: true,
            requires_hf_auth: false
        };

        // Show loading state
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Adding model...';
        submitBtn.disabled = true;

        try {
            const response = await fetch(`${API_BASE}/models`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(modelData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to add model');
            }

            showToast('Model added successfully! Download will start automatically.', 'success');
            form.reset();
            loadModels();
        } catch (error) {
            showToast(error.message, 'error');
            console.error(error);
        } finally {
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    });
}

/**
 * Test a model
 */
async function testModel(modelId, numRequests) {
    try {
        const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelId)}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ num_requests: numRequests })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start test');
        }
        
        activeTests.add(modelId);
        showToast(`Started test for ${modelId} (${numRequests} requests)`, 'info');
        loadModels();
    } catch (error) {
        showToast(error.message, 'error');
        console.error(error);
    }
}

/**
 * Delete a model
 */
async function deleteModel(modelId) {
    // Better confirmation dialog
    const modelName = models.find(m => m.model_id === modelId)?.name || modelId;
    const confirmed = confirm(
        `⚠️ Delete model "${modelName}"?\n\n` +
        `This will:\n` +
        `• Remove the model from the registry\n` +
        `• Delete all downloaded model files\n` +
        `• Remove all benchmark results\n\n` +
        `This action cannot be undone.`
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelId)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete model');
        }

        showToast(`Model "${modelName}" deleted successfully`, 'success');
        loadModels();
    } catch (error) {
        showToast(`Failed to delete model: ${error.message}`, 'error');
        console.error(error);
    }
}

/**
 * Poll for test status updates
 */
function startPolling() {
    pollInterval = setInterval(async () => {
        if (activeTests.size === 0) return;
        
        for (const modelId of activeTests) {
            try {
                const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelId)}/status`);
                const status = await response.json();
                
                // Update progress bar
                const safeId = modelId.replace('/', '-');
                const progressBar = document.getElementById(`progress-${safeId}`);
                if (progressBar) {
                    progressBar.style.width = `${status.progress * 100}%`;
                }
                
                // Update logs
                const logsDiv = document.getElementById(`logs-${safeId}`);
                if (logsDiv && status.log_tail) {
                    logsDiv.innerHTML = status.log_tail
                        .map(line => `<div class="log-line">${escapeHtml(line)}</div>`)
                        .join('');
                    logsDiv.scrollTop = logsDiv.scrollHeight;
                }
                
                // Check if completed
                if (status.status === 'completed' || status.status === 'failed') {
                    activeTests.delete(modelId);
                    showToast(
                        status.status === 'completed' 
                            ? `Test completed for ${modelId}` 
                            : `Test failed for ${modelId}`,
                        status.status === 'completed' ? 'success' : 'error'
                    );
                    loadModels();
                }
            } catch (error) {
                console.error(`Failed to poll status for ${modelId}:`, error);
            }
        }
    }, 2000); // Poll every 2 seconds
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

