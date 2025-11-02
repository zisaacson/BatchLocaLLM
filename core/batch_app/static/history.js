// Job History Viewer
let currentPage = 0;
const pageSize = 50;
let currentFilters = {
    status: '',
    model: ''
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadJobs();
    setupEventListeners();
});

function setupEventListeners() {
    // Filter changes
    document.getElementById('filterStatus').addEventListener('change', (e) => {
        currentFilters.status = e.target.value;
        currentPage = 0;
        loadJobs();
    });

    document.getElementById('filterModel').addEventListener('change', (e) => {
        currentFilters.model = e.target.value;
        currentPage = 0;
        loadJobs();
    });

    // Pagination
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            loadJobs();
        }
    });

    document.getElementById('nextPage').addEventListener('click', () => {
        currentPage++;
        loadJobs();
    });

    // Close modal on background click
    document.getElementById('jobModal').addEventListener('click', (e) => {
        if (e.target.id === 'jobModal') {
            closeModal();
        }
    });
}

async function loadStats() {
    try {
        const response = await fetch('/v1/jobs/stats');
        const data = await response.json();

        document.getElementById('totalJobs').textContent = data.total_jobs.toLocaleString();
        document.getElementById('successRate').textContent = (data.success_rate * 100).toFixed(1) + '%';
        document.getElementById('avgDuration').textContent = data.avg_duration.toFixed(1);
        document.getElementById('totalRequests').textContent = data.total_requests.toLocaleString();

        // Populate model filter
        const modelSelect = document.getElementById('filterModel');
        Object.keys(data.by_model).forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            modelSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function loadJobs() {
    const loading = document.getElementById('loading');
    const table = document.getElementById('jobsTable');
    const pagination = document.getElementById('pagination');

    loading.style.display = 'block';
    table.style.display = 'none';
    pagination.style.display = 'none';

    try {
        const params = new URLSearchParams({
            limit: pageSize,
            offset: currentPage * pageSize
        });

        if (currentFilters.status) {
            params.append('status', currentFilters.status);
        }
        if (currentFilters.model) {
            params.append('model', currentFilters.model);
        }

        const response = await fetch(`/v1/jobs/history?${params}`);
        const data = await response.json();

        renderJobs(data.jobs);
        updatePagination(data);

        loading.style.display = 'none';
        table.style.display = 'table';
        pagination.style.display = 'flex';
    } catch (error) {
        console.error('Failed to load jobs:', error);
        loading.innerHTML = '<p style="color: #f56565;">Failed to load jobs. Please try again.</p>';
    }
}

function renderJobs(jobs) {
    const tbody = document.getElementById('jobsTableBody');
    tbody.innerHTML = '';

    jobs.forEach(job => {
        const row = document.createElement('tr');
        row.onclick = () => showJobDetails(job.batch_id);

        row.innerHTML = `
            <td><code>${job.batch_id}</code></td>
            <td><span class="status-badge status-${job.status}">${job.status}</span></td>
            <td>${job.model || 'N/A'}</td>
            <td>${job.completed_requests}/${job.total_requests}</td>
            <td>${job.duration ? job.duration.toFixed(1) + 's' : '-'}</td>
            <td>${job.throughput ? job.throughput.toFixed(2) + ' req/s' : '-'}</td>
            <td>${formatTimestamp(job.created_at)}</td>
        `;

        tbody.appendChild(row);
    });
}

function updatePagination(data) {
    const info = document.getElementById('paginationInfo');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');

    const start = data.offset + 1;
    const end = Math.min(data.offset + data.limit, data.total);
    info.textContent = `Showing ${start}-${end} of ${data.total}`;

    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = !data.has_more;
}

async function showJobDetails(batchId) {
    const modal = document.getElementById('jobModal');
    const details = document.getElementById('jobDetails');

    modal.classList.add('active');
    details.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading job details...</p></div>';

    try {
        const response = await fetch(`/v1/batches/${batchId}`);
        const job = await response.json();

        const duration = job.completed_at && job.created_at 
            ? job.completed_at - job.created_at 
            : null;

        const throughput = duration && duration > 0 && job.request_counts?.completed > 0
            ? (job.request_counts.completed / duration).toFixed(2)
            : null;

        details.innerHTML = `
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Batch ID</label>
                    <div class="value"><code>${job.id}</code></div>
                </div>
                <div class="detail-item">
                    <label>Status</label>
                    <div class="value"><span class="status-badge status-${job.status}">${job.status}</span></div>
                </div>
                <div class="detail-item">
                    <label>Model</label>
                    <div class="value">${job.model || 'N/A'}</div>
                </div>
                <div class="detail-item">
                    <label>Endpoint</label>
                    <div class="value">${job.endpoint}</div>
                </div>
                <div class="detail-item">
                    <label>Total Requests</label>
                    <div class="value">${job.request_counts.total}</div>
                </div>
                <div class="detail-item">
                    <label>Completed Requests</label>
                    <div class="value">${job.request_counts.completed}</div>
                </div>
                <div class="detail-item">
                    <label>Failed Requests</label>
                    <div class="value">${job.request_counts.failed}</div>
                </div>
                <div class="detail-item">
                    <label>Priority</label>
                    <div class="value">${job.priority || 0}</div>
                </div>
                <div class="detail-item">
                    <label>Created At</label>
                    <div class="value">${formatTimestamp(job.created_at)}</div>
                </div>
                <div class="detail-item">
                    <label>Completed At</label>
                    <div class="value">${job.completed_at ? formatTimestamp(job.completed_at) : '-'}</div>
                </div>
                <div class="detail-item">
                    <label>Duration</label>
                    <div class="value">${duration ? duration.toFixed(1) + 's' : '-'}</div>
                </div>
                <div class="detail-item">
                    <label>Throughput</label>
                    <div class="value">${throughput ? throughput + ' req/s' : '-'}</div>
                </div>
                <div class="detail-item">
                    <label>Input File</label>
                    <div class="value"><code>${job.input_file_id}</code></div>
                </div>
                <div class="detail-item">
                    <label>Output File</label>
                    <div class="value">${job.output_file_id ? '<code>' + job.output_file_id + '</code>' : '-'}</div>
                </div>
                <div class="detail-item">
                    <label>Error File</label>
                    <div class="value">${job.error_file_id ? '<code>' + job.error_file_id + '</code>' : '-'}</div>
                </div>
                <div class="detail-item">
                    <label>Webhook</label>
                    <div class="value">${job.webhook_url ? '✅ Configured' : '❌ None'}</div>
                </div>
            </div>
            ${job.errors ? `
                <div style="margin-top: 20px; padding: 15px; background: #fed7d7; border-radius: 8px;">
                    <label style="display: block; color: #742a2a; font-weight: 600; margin-bottom: 10px;">Error Details</label>
                    <pre style="color: #742a2a; font-size: 12px; overflow-x: auto;">${JSON.stringify(JSON.parse(job.errors), null, 2)}</pre>
                </div>
            ` : ''}
            ${job.metadata ? `
                <div style="margin-top: 20px; padding: 15px; background: #f7fafc; border-radius: 8px;">
                    <label style="display: block; color: #4a5568; font-weight: 600; margin-bottom: 10px;">Metadata</label>
                    <pre style="color: #2d3748; font-size: 12px; overflow-x: auto;">${JSON.stringify(JSON.parse(job.metadata), null, 2)}</pre>
                </div>
            ` : ''}
            ${job.queue_info ? `
                <div style="margin-top: 20px; padding: 15px; background: #bee3f8; border-radius: 8px;">
                    <label style="display: block; color: #2c5282; font-weight: 600; margin-bottom: 10px;">Queue Information</label>
                    <div style="color: #2c5282; font-size: 14px;">
                        <p><strong>Position:</strong> ${job.queue_info.position || 'N/A'}</p>
                        <p><strong>Jobs Ahead:</strong> ${job.queue_info.jobs_ahead || 0}</p>
                        <p><strong>ETA:</strong> ${job.queue_info.estimated_completion_time || 'N/A'}</p>
                    </div>
                </div>
            ` : ''}
        `;
    } catch (error) {
        console.error('Failed to load job details:', error);
        details.innerHTML = '<p style="color: #f56565;">Failed to load job details. Please try again.</p>';
    }
}

function closeModal() {
    document.getElementById('jobModal').classList.remove('active');
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

// Auto-refresh every 30 seconds
setInterval(() => {
    loadStats();
    loadJobs();
}, 30000);

