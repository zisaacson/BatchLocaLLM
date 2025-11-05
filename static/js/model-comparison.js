/**
 * Model Comparison JavaScript
 * 
 * Handles side-by-side model comparison with metrics visualization and A/B testing.
 */

// Configuration
const API_BASE = window.location.origin;

// State
let currentUser = {
    user_email: 'user@example.com',  // Generic default user
    domain: 'default'  // Generic default domain
};

let selectedBaseModel = null;
let selectedFineTunedModel = null;
let qualityChart = null;
let performanceChart = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    
    // Check if model ID is in URL
    const urlParams = new URLSearchParams(window.location.search);
    const modelId = urlParams.get('model');
    if (modelId) {
        // Auto-select the fine-tuned model
        setTimeout(() => {
            document.getElementById('fineTunedModelSelect').value = modelId;
        }, 500);
    }
});

// ============================================================================
// Model Loading
// ============================================================================

async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/v1/fine-tuning/models?user_email=${currentUser.user_email}&domain=${currentUser.domain}`);
        const models = await response.json();
        
        // Populate base model selector (use base_model field)
        const baseModelSelect = document.getElementById('baseModelSelect');
        const baseModels = [...new Set(models.map(m => m.base_model))];
        baseModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            baseModelSelect.appendChild(option);
        });
        
        // Populate fine-tuned model selector
        const fineTunedSelect = document.getElementById('fineTunedModelSelect');
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = `${model.name} (v${model.version})`;
            fineTunedSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Error loading models:', error);
        alert('Failed to load models');
    }
}

// ============================================================================
// Comparison Loading
// ============================================================================

async function loadComparison() {
    const baseModelId = document.getElementById('baseModelSelect').value;
    const fineTunedModelId = document.getElementById('fineTunedModelSelect').value;
    
    if (!baseModelId || !fineTunedModelId) {
        alert('Please select both models to compare');
        return;
    }
    
    // Show loading state
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('comparisonResults').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    
    try {
        // Load fine-tuned model data
        const response = await fetch(`${API_BASE}/v1/fine-tuning/models?user_email=${currentUser.user_email}&domain=${currentUser.domain}`);
        const models = await response.json();
        
        const fineTunedModel = models.find(m => m.id === fineTunedModelId);
        
        if (!fineTunedModel) {
            throw new Error('Fine-tuned model not found');
        }
        
        selectedBaseModel = {
            name: baseModelId,
            win_rate: 0,
            gold_star_rate: 0,
            avg_rating: 0,
            consistency_score: 0,
            tokens_per_second: 0,
            latency_ms: 0,
            vram_usage_gb: 0,
            model_size_mb: 0
        };
        
        selectedFineTunedModel = fineTunedModel;
        
        // Display comparison
        displayComparison();
        
    } catch (error) {
        console.error('Error loading comparison:', error);
        alert('Failed to load comparison data');
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('emptyState').style.display = 'block';
    }
}

function displayComparison() {
    // Hide loading, show results
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('comparisonResults').style.display = 'block';
    
    // Update model names
    document.getElementById('baseModelName').textContent = selectedBaseModel.name;
    document.getElementById('fineTunedModelName').textContent = selectedFineTunedModel.name;
    
    // Display metrics
    displayMetrics('baseModelMetrics', selectedBaseModel);
    displayMetrics('fineTunedModelMetrics', selectedFineTunedModel);
    
    // Create charts
    createQualityChart();
    createPerformanceChart();
}

function displayMetrics(containerId, model) {
    const container = document.getElementById(containerId);
    
    const metrics = [
        { label: 'Win Rate', value: model.win_rate, unit: '%', higherBetter: true },
        { label: 'Gold Star Rate', value: model.gold_star_rate, unit: '%', higherBetter: true },
        { label: 'Avg Rating', value: model.avg_rating, unit: '/5', higherBetter: true },
        { label: 'Consistency', value: model.consistency_score, unit: '', higherBetter: true },
        { label: 'Tokens/Second', value: model.tokens_per_second, unit: '', higherBetter: true },
        { label: 'Latency', value: model.latency_ms, unit: 'ms', higherBetter: false },
        { label: 'VRAM Usage', value: model.vram_usage_gb, unit: 'GB', higherBetter: false },
        { label: 'Model Size', value: model.model_size_mb, unit: 'MB', higherBetter: false }
    ];
    
    container.innerHTML = metrics.map(metric => {
        const value = metric.value || 0;
        const formattedValue = typeof value === 'number' ? value.toFixed(2) : value;
        
        // Determine if this value is better than the other model
        let className = '';
        if (containerId === 'fineTunedModelMetrics' && selectedBaseModel) {
            const baseValue = selectedBaseModel[getMetricKey(metric.label)] || 0;
            if (metric.higherBetter) {
                className = value > baseValue ? 'better' : (value < baseValue ? 'worse' : '');
            } else {
                className = value < baseValue ? 'better' : (value > baseValue ? 'worse' : '');
            }
        }
        
        return `
            <div class="metric-row">
                <span class="metric-label">${metric.label}</span>
                <span class="metric-value ${className}">${formattedValue}${metric.unit}</span>
            </div>
        `;
    }).join('');
}

function getMetricKey(label) {
    const mapping = {
        'Win Rate': 'win_rate',
        'Gold Star Rate': 'gold_star_rate',
        'Avg Rating': 'avg_rating',
        'Consistency': 'consistency_score',
        'Tokens/Second': 'tokens_per_second',
        'Latency': 'latency_ms',
        'VRAM Usage': 'vram_usage_gb',
        'Model Size': 'model_size_mb'
    };
    return mapping[label];
}

// ============================================================================
// Charts
// ============================================================================

function createQualityChart() {
    const ctx = document.getElementById('qualityChart');
    
    if (qualityChart) {
        qualityChart.destroy();
    }
    
    qualityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Win Rate', 'Gold Star Rate', 'Avg Rating', 'Consistency'],
            datasets: [
                {
                    label: 'Base Model',
                    data: [
                        selectedBaseModel.win_rate || 0,
                        selectedBaseModel.gold_star_rate || 0,
                        (selectedBaseModel.avg_rating || 0) * 20, // Scale to 100
                        (selectedBaseModel.consistency_score || 0) * 100
                    ],
                    backgroundColor: 'rgba(156, 163, 175, 0.5)',
                    borderColor: 'rgba(156, 163, 175, 1)',
                    borderWidth: 2
                },
                {
                    label: 'Fine-Tuned Model',
                    data: [
                        selectedFineTunedModel.win_rate || 0,
                        selectedFineTunedModel.gold_star_rate || 0,
                        (selectedFineTunedModel.avg_rating || 0) * 20,
                        (selectedFineTunedModel.consistency_score || 0) * 100
                    ],
                    backgroundColor: 'rgba(102, 126, 234, 0.5)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y.toFixed(1) + '%';
                            return label;
                        }
                    }
                }
            }
        }
    });
}

function createPerformanceChart() {
    const ctx = document.getElementById('performanceChart');
    
    if (performanceChart) {
        performanceChart.destroy();
    }
    
    performanceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Tokens/Second', 'Latency (lower=better)', 'VRAM Usage (lower=better)'],
            datasets: [
                {
                    label: 'Base Model',
                    data: [
                        selectedBaseModel.tokens_per_second || 0,
                        selectedBaseModel.latency_ms || 0,
                        selectedBaseModel.vram_usage_gb || 0
                    ],
                    backgroundColor: 'rgba(156, 163, 175, 0.5)',
                    borderColor: 'rgba(156, 163, 175, 1)',
                    borderWidth: 2
                },
                {
                    label: 'Fine-Tuned Model',
                    data: [
                        selectedFineTunedModel.tokens_per_second || 0,
                        selectedFineTunedModel.latency_ms || 0,
                        selectedFineTunedModel.vram_usage_gb || 0
                    ],
                    backgroundColor: 'rgba(102, 126, 234, 0.5)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    position: 'top'
                }
            }
        }
    });
}

// ============================================================================
// A/B Testing
// ============================================================================

async function runABTest() {
    const container = document.getElementById('abTestResults');
    container.innerHTML = '<p style="color: #718096;">A/B testing feature coming soon! This will allow you to test both models with sample prompts and vote for better responses.</p>';
    
    // TODO: Implement A/B testing
    // 1. Load sample prompts from dataset
    // 2. Run inference on both models
    // 3. Display responses side-by-side
    // 4. Allow user to vote
    // 5. Track win/loss/tie statistics
}

