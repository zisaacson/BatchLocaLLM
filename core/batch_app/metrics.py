"""
Prometheus metrics for vLLM Batch Server.

Provides comprehensive metrics for monitoring:
- Request duration and latency
- Queue depth and throughput
- Model loading times
- Chunk processing times
- Error rates

Usage:
    from core.batch_app.metrics import (
        request_duration,
        queue_depth,
        model_load_duration
    )
    
    # Track request duration
    with request_duration.labels(endpoint="/v1/batches").time():
        process_request()
    
    # Update queue depth
    queue_depth.set(len(pending_jobs))
    
    # Track model load time
    with model_load_duration.time():
        load_model()
"""

from prometheus_client import Counter, Gauge, Histogram, Summary

# ============================================================================
# Request Metrics
# ============================================================================

request_duration = Histogram(
    'vllm_request_duration_seconds',
    'Request processing duration in seconds',
    ['endpoint', 'method', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0]
)

request_count = Counter(
    'vllm_request_total',
    'Total number of requests',
    ['endpoint', 'method', 'status_code']
)

request_errors = Counter(
    'vllm_request_errors_total',
    'Total number of request errors',
    ['endpoint', 'method', 'error_type']
)

# ============================================================================
# Batch Job Metrics
# ============================================================================

batch_jobs_total = Counter(
    'vllm_batch_jobs_total',
    'Total number of batch jobs',
    ['status']  # queued, processing, completed, failed, cancelled
)

batch_jobs_active = Gauge(
    'vllm_batch_jobs_active',
    'Number of currently active batch jobs',
    ['status']
)

batch_processing_duration = Histogram(
    'vllm_batch_processing_duration_seconds',
    'Batch job processing duration in seconds',
    ['model'],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800]  # 1m to 8h
)

batch_requests_processed = Counter(
    'vllm_batch_requests_processed_total',
    'Total number of requests processed in batches',
    ['model', 'status']  # completed, failed
)

# ============================================================================
# Queue Metrics
# ============================================================================

queue_depth = Gauge(
    'vllm_queue_depth',
    'Number of jobs waiting in queue'
)

queue_wait_time = Histogram(
    'vllm_queue_wait_time_seconds',
    'Time jobs spend waiting in queue',
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

# ============================================================================
# Model Metrics
# ============================================================================

model_load_duration = Histogram(
    'vllm_model_load_duration_seconds',
    'Model loading duration in seconds',
    ['model'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)

model_loaded = Gauge(
    'vllm_model_loaded',
    'Whether a model is currently loaded (1=loaded, 0=not loaded)',
    ['model']
)

# ============================================================================
# Inference Metrics
# ============================================================================

inference_duration = Histogram(
    'vllm_inference_duration_seconds',
    'Inference duration per request',
    ['model'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

tokens_generated = Counter(
    'vllm_tokens_generated_total',
    'Total number of tokens generated',
    ['model']
)

throughput_tokens_per_second = Gauge(
    'vllm_throughput_tokens_per_second',
    'Current throughput in tokens per second',
    ['model']
)

# ============================================================================
# Chunk Processing Metrics
# ============================================================================

chunk_processing_duration = Histogram(
    'vllm_chunk_processing_duration_seconds',
    'Chunk processing duration in seconds',
    ['model'],
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800]
)

chunk_size = Histogram(
    'vllm_chunk_size',
    'Number of requests per chunk',
    buckets=[100, 500, 1000, 2500, 5000, 10000, 25000, 50000]
)

chunks_processed = Counter(
    'vllm_chunks_processed_total',
    'Total number of chunks processed',
    ['model', 'status']  # completed, failed
)

# ============================================================================
# GPU Metrics
# ============================================================================

gpu_memory_used_bytes = Gauge(
    'vllm_gpu_memory_used_bytes',
    'GPU memory used in bytes',
    ['gpu_id']
)

gpu_memory_total_bytes = Gauge(
    'vllm_gpu_memory_total_bytes',
    'Total GPU memory in bytes',
    ['gpu_id']
)

gpu_temperature_celsius = Gauge(
    'vllm_gpu_temperature_celsius',
    'GPU temperature in Celsius',
    ['gpu_id']
)

gpu_utilization_percent = Gauge(
    'vllm_gpu_utilization_percent',
    'GPU utilization percentage',
    ['gpu_id']
)

# ============================================================================
# Worker Metrics
# ============================================================================

worker_heartbeat_timestamp = Gauge(
    'vllm_worker_heartbeat_timestamp',
    'Timestamp of last worker heartbeat',
    ['worker_id']
)

worker_status = Gauge(
    'vllm_worker_status',
    'Worker status (1=active, 0=inactive)',
    ['worker_id', 'status']  # idle, processing
)

# ============================================================================
# File Metrics
# ============================================================================

files_uploaded = Counter(
    'vllm_files_uploaded_total',
    'Total number of files uploaded'
)

files_bytes_uploaded = Counter(
    'vllm_files_bytes_uploaded_total',
    'Total bytes of files uploaded'
)

# ============================================================================
# Error Metrics
# ============================================================================

errors_total = Counter(
    'vllm_errors_total',
    'Total number of errors',
    ['error_type', 'component']  # component: api, worker, model
)

failed_requests = Counter(
    'vllm_failed_requests_total',
    'Total number of failed requests',
    ['model', 'error_type']
)

# ============================================================================
# Latency Percentiles (Summary)
# ============================================================================

request_latency_summary = Summary(
    'vllm_request_latency_seconds',
    'Request latency summary with percentiles',
    ['endpoint']
)

batch_latency_summary = Summary(
    'vllm_batch_latency_seconds',
    'Batch processing latency summary with percentiles',
    ['model']
)

# ============================================================================
# Helper Functions
# ============================================================================

def track_request(endpoint: str, method: str, status_code: int, duration: float):
    """Track a request with all relevant metrics."""
    request_duration.labels(endpoint=endpoint, method=method, status_code=status_code).observe(duration)
    request_count.labels(endpoint=endpoint, method=method, status_code=status_code).inc()
    request_latency_summary.labels(endpoint=endpoint).observe(duration)


def track_batch_job(status: str, model: str = None, duration: float = None):
    """Track a batch job status change."""
    batch_jobs_total.labels(status=status).inc()
    
    if duration and model:
        batch_processing_duration.labels(model=model).observe(duration)
        batch_latency_summary.labels(model=model).observe(duration)


def track_error(error_type: str, component: str, endpoint: str = None, method: str = None):
    """Track an error."""
    errors_total.labels(error_type=error_type, component=component).inc()
    
    if endpoint and method:
        request_errors.labels(endpoint=endpoint, method=method, error_type=error_type).inc()


def update_queue_metrics(pending_count: int):
    """Update queue depth metric."""
    queue_depth.set(pending_count)


def update_gpu_metrics(gpu_id: str, memory_used: int, memory_total: int, temperature: float, utilization: float):
    """Update GPU metrics."""
    gpu_memory_used_bytes.labels(gpu_id=gpu_id).set(memory_used)
    gpu_memory_total_bytes.labels(gpu_id=gpu_id).set(memory_total)
    gpu_temperature_celsius.labels(gpu_id=gpu_id).set(temperature)
    gpu_utilization_percent.labels(gpu_id=gpu_id).set(utilization)

