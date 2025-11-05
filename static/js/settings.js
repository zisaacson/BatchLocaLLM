// Settings page JavaScript

const API_BASE = 'http://localhost:4080';

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    checkSystemdStatus();
    checkWorkerStatus();
    checkSystemStatus();
    
    // Auto-refresh every 5 seconds
    setInterval(() => {
        checkWorkerStatus();
        checkSystemStatus();
    }, 5000);
});

// Check if systemd services are installed and enabled
async function checkSystemdStatus() {
    try {
        const response = await fetch(`${API_BASE}/admin/systemd/status`);
        
        if (response.ok) {
            const data = await response.json();
            updateServiceStatus('api', data.api_server);
            updateServiceStatus('watchdog', data.watchdog);
        } else {
            // Services not installed - show instructions
            document.getElementById('install-instructions').style.display = 'block';
            updateServiceStatus('api', { enabled: false, active: false });
            updateServiceStatus('watchdog', { enabled: false, active: false });
        }
    } catch (error) {
        console.error('Error checking systemd status:', error);
        // Assume not installed
        document.getElementById('install-instructions').style.display = 'block';
        updateServiceStatus('api', { enabled: false, active: false });
        updateServiceStatus('watchdog', { enabled: false, active: false });
    }
}

// Update service status display
function updateServiceStatus(service, status) {
    const statusBadge = document.getElementById(`${service}-status`);
    const toggleBtn = document.getElementById(`${service}-toggle`);
    
    if (status.enabled && status.active) {
        statusBadge.textContent = 'Active';
        statusBadge.className = 'status-badge active';
        toggleBtn.textContent = 'Disable';
        toggleBtn.className = 'btn btn-danger';
    } else if (status.enabled && !status.active) {
        statusBadge.textContent = 'Enabled (Not Running)';
        statusBadge.className = 'status-badge unknown';
        toggleBtn.textContent = 'Start';
        toggleBtn.className = 'btn btn-success';
    } else {
        statusBadge.textContent = 'Disabled';
        statusBadge.className = 'status-badge inactive';
        toggleBtn.textContent = 'Enable';
        toggleBtn.className = 'btn btn-primary';
    }
}

// Toggle service (enable/disable/start/stop)
async function toggleService(service) {
    const serviceName = service === 'api' ? 'vllm-api-server' : 'vllm-watchdog';
    const statusBadge = document.getElementById(`${service}-status`);
    const currentStatus = statusBadge.textContent;
    
    let action;
    if (currentStatus === 'Active') {
        action = 'disable';
    } else if (currentStatus === 'Enabled (Not Running)') {
        action = 'start';
    } else {
        action = 'enable';
    }
    
    try {
        const response = await fetch(`${API_BASE}/admin/systemd/${serviceName}/${action}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showAlert('success', `Service ${action}d successfully!`);
            setTimeout(checkSystemdStatus, 1000);
        } else {
            const error = await response.json();
            showAlert('error', `Failed to ${action} service: ${error.detail}`);
        }
    } catch (error) {
        console.error(`Error ${action}ing service:`, error);
        showAlert('error', `Error: ${error.message}`);
    }
}

// Check worker status
async function checkWorkerStatus() {
    try {
        const response = await fetch(`${API_BASE}/admin/worker/status`);
        
        if (response.ok) {
            const data = await response.json();
            
            // Update worker status badge
            const workerStatus = document.getElementById('worker-status');
            if (data.healthy) {
                workerStatus.textContent = 'Healthy';
                workerStatus.className = 'status-badge active';
            } else {
                workerStatus.textContent = 'Offline';
                workerStatus.className = 'status-badge inactive';
            }
            
            // Update metrics
            document.getElementById('restart-count').textContent = data.restart_count || 0;
            
            if (data.last_heartbeat) {
                const seconds = Math.floor(data.heartbeat_age_seconds);
                document.getElementById('last-heartbeat').textContent = `${seconds}s ago`;
            } else {
                document.getElementById('last-heartbeat').textContent = 'Never';
            }
            
            if (data.uptime_seconds) {
                const hours = Math.floor(data.uptime_seconds / 3600);
                const minutes = Math.floor((data.uptime_seconds % 3600) / 60);
                document.getElementById('uptime').textContent = `${hours}h ${minutes}m`;
            } else {
                document.getElementById('uptime').textContent = 'N/A';
            }
        }
    } catch (error) {
        console.error('Error checking worker status:', error);
    }
}

// Check system status (GPU, model, etc.)
async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/admin/worker/status`);
        
        if (response.ok) {
            const data = await response.json();
            
            // Update GPU metrics
            if (data.gpu_memory_percent !== undefined) {
                document.getElementById('gpu-memory').textContent = `${data.gpu_memory_percent.toFixed(1)}%`;
            }
            
            if (data.gpu_utilization !== undefined) {
                document.getElementById('gpu-util').textContent = `${data.gpu_utilization}%`;
            }
            
            // Update loaded model
            if (data.loaded_model) {
                const modelName = data.loaded_model.split('/').pop();
                document.getElementById('loaded-model').textContent = modelName;
            } else {
                document.getElementById('loaded-model').textContent = 'None';
            }
        }
    } catch (error) {
        console.error('Error checking system status:', error);
    }
}

// Restart worker
async function restartWorker() {
    if (!confirm('Are you sure you want to restart the worker? This will interrupt any running jobs.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/admin/worker/restart`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showAlert('success', 'Worker restart initiated. It will be back online in ~30 seconds.');
            setTimeout(checkWorkerStatus, 2000);
        } else {
            const error = await response.json();
            showAlert('error', `Failed to restart worker: ${error.detail}`);
        }
    } catch (error) {
        console.error('Error restarting worker:', error);
        showAlert('error', `Error: ${error.message}`);
    }
}

// Refresh all status
function refreshStatus() {
    const icon = document.getElementById('refresh-icon');
    icon.innerHTML = '<span class="loading"></span>';
    
    checkSystemdStatus();
    checkWorkerStatus();
    checkSystemStatus();
    
    setTimeout(() => {
        icon.textContent = '🔄';
    }, 1000);
}

// Show alert message
function showAlert(type, message) {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-warning';
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert ${alertClass}`;
    alertDiv.textContent = message;
    
    const container = document.querySelector('.settings-container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

