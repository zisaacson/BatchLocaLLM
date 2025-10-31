/**
 * Label Studio API Client
 * 
 * Wrapper around the curation backend API.
 */

const API = {
    baseURL: '/api',
    
    /**
     * Make API request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return response.json();
    },
    
    /**
     * Get all conquest schemas
     */
    async getSchemas() {
        return this.request('/schemas');
    },
    
    /**
     * Get a specific conquest schema
     */
    async getSchema(conquestType) {
        return this.request(`/schemas/${conquestType}`);
    },
    
    /**
     * Get tasks
     */
    async getTasks(conquestType = null, page = 1, pageSize = 50) {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (conquestType) {
            params.append('conquest_type', conquestType);
        }
        return this.request(`/tasks?${params}`);
    },
    
    /**
     * Get a specific task
     */
    async getTask(taskId) {
        return this.request(`/tasks/${taskId}`);
    },
    
    /**
     * Create a new task
     */
    async createTask(conquestType, data, llmPrediction = null, modelVersion = null) {
        return this.request('/tasks', {
            method: 'POST',
            body: JSON.stringify({
                conquest_type: conquestType,
                data,
                llm_prediction: llmPrediction,
                model_version: modelVersion
            })
        });
    },
    
    /**
     * Submit an annotation
     */
    async submitAnnotation(taskId, result, timeSpentSeconds = null) {
        return this.request('/annotations', {
            method: 'POST',
            body: JSON.stringify({
                task_id: taskId,
                result,
                time_spent_seconds: timeSpentSeconds
            })
        });
    },
    
    /**
     * Export dataset
     */
    async exportDataset(conquestType, format = 'icl', minAgreement = 0.8, minAnnotations = 1) {
        return this.request('/export', {
            method: 'POST',
            body: JSON.stringify({
                conquest_type: conquestType,
                format,
                min_agreement: minAgreement,
                min_annotations: minAnnotations
            })
        });
    },
    
    /**
     * Get statistics
     */
    async getStats(conquestType = null) {
        const params = conquestType ? `?conquest_type=${conquestType}` : '';
        return this.request(`/stats${params}`);
    }
};

/**
 * Export modal functions
 */
function showExportModal() {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'flex';
    
    // Set up event listeners
    document.getElementById('modal-close').onclick = hideExportModal;
    document.getElementById('export-cancel').onclick = hideExportModal;
    document.getElementById('export-confirm').onclick = performExport;
}

function hideExportModal() {
    const modal = document.getElementById('export-modal');
    modal.style.display = 'none';
}

async function performExport() {
    if (!currentConquestType) {
        showToast('No conquest type selected', 'error');
        return;
    }
    
    const format = document.getElementById('export-format').value;
    const minAgreement = parseFloat(document.getElementById('export-min-agreement').value);
    const minAnnotations = parseInt(document.getElementById('export-min-annotations').value);
    
    try {
        showToast('Exporting dataset...', 'info');
        
        const result = await API.exportDataset(
            currentConquestType,
            format,
            minAgreement,
            minAnnotations
        );
        
        // Download as JSON file
        const blob = new Blob([JSON.stringify(result.examples, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentConquestType}_${format}_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        showToast(`Exported ${result.count} examples`, 'success');
        hideExportModal();
    } catch (error) {
        showToast('Export failed', 'error');
        console.error(error);
    }
}

// Make functions globally available
window.API = API;
window.showExportModal = showExportModal;
window.hideExportModal = hideExportModal;
window.performExport = performExport;

