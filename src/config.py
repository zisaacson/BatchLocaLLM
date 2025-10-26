"""
Configuration management for vLLM Batch Server

Loads configuration from environment variables with sensible defaults.
Uses pydantic-settings for validation and type safety.
"""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Model Configuration
    # =========================================================================

    model_name: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct",
        description="Hugging Face model name or local path",
    )

    model_revision: str = Field(
        default="main",
        description="Model revision (branch/tag/commit)",
    )

    hf_token: Optional[str] = Field(
        default=None,
        description="Hugging Face API token for gated models",
    )

    trust_remote_code: bool = Field(
        default=False,
        description="Trust remote code from model repository",
    )

    # =========================================================================
    # GPU Configuration
    # =========================================================================

    tensor_parallel_size: int = Field(
        default=1,
        ge=1,
        description="Number of GPUs for tensor parallelism",
    )

    gpu_memory_utilization: float = Field(
        default=0.9,
        ge=0.1,
        le=1.0,
        description="Fraction of GPU memory to use",
    )

    max_model_len: int = Field(
        default=8192,
        ge=128,
        description="Maximum context length",
    )

    dtype: str = Field(
        default="auto",
        description="Data type for model weights (auto, float16, bfloat16, float32)",
    )

    quantization: Optional[str] = Field(
        default=None,
        description="Quantization method (awq, gptq, squeezellm, fp8)",
    )

    # =========================================================================
    # Batch Processing Configuration
    # =========================================================================

    max_num_seqs: int = Field(
        default=256,
        ge=1,
        description="Maximum number of sequences in a batch",
    )

    max_concurrent_batches: int = Field(
        default=4,
        ge=1,
        description="Maximum number of concurrent batch jobs",
    )

    max_batch_file_size_mb: int = Field(
        default=500,
        ge=1,
        description="Maximum batch file size in MB",
    )

    max_requests_per_batch: int = Field(
        default=50000,
        ge=1,
        description="Maximum number of requests per batch",
    )

    batch_completion_timeout_hours: int = Field(
        default=24,
        ge=1,
        description="Batch completion timeout in hours",
    )

    # =========================================================================
    # Prefix Caching Configuration
    # =========================================================================

    enable_prefix_caching: bool = Field(
        default=True,
        description="Enable automatic prefix caching",
    )

    prefix_cache_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction of KV cache to reserve for prefixes",
    )

    # =========================================================================
    # Server Configuration
    # =========================================================================

    host: str = Field(
        default="0.0.0.0",
        description="Server host",
    )

    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Server port",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="API key for authentication (optional)",
    )

    enable_cors: bool = Field(
        default=True,
        description="Enable CORS",
    )

    cors_origins: str = Field(
        default="*",
        description="Allowed CORS origins (comma-separated)",
    )

    log_level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    json_logging: bool = Field(
        default=True,
        description="Enable structured JSON logging",
    )

    # =========================================================================
    # Storage Configuration
    # =========================================================================

    storage_path: str = Field(
        default="/data/batches",
        description="Path to store batch jobs and results",
    )

    database_path: str = Field(
        default="/data/vllm_batch.db",
        description="Path to SQLite database",
    )

    cleanup_after_days: int = Field(
        default=7,
        ge=1,
        description="Delete completed jobs after N days",
    )

    # =========================================================================
    # Performance Tuning
    # =========================================================================

    enable_cuda_graph: bool = Field(
        default=True,
        description="Enable CUDA graph optimization",
    )

    swap_space_gb: int = Field(
        default=4,
        ge=0,
        description="Swap space for CPU offloading (GB)",
    )

    block_size: int = Field(
        default=16,
        ge=8,
        description="Block size for paged attention",
    )

    max_parallel_loading_workers: int = Field(
        default=4,
        ge=1,
        description="Maximum number of parallel loading workers",
    )

    # =========================================================================
    # Monitoring & Observability
    # =========================================================================

    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics",
    )

    metrics_port: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Prometheus metrics port",
    )

    enable_health_checks: bool = Field(
        default=True,
        description="Enable health check endpoints",
    )

    # =========================================================================
    # Advanced vLLM Options
    # =========================================================================

    disable_log_stats: bool = Field(
        default=False,
        description="Disable vLLM stats logging",
    )

    disable_log_requests: bool = Field(
        default=False,
        description="Disable vLLM request logging",
    )

    enable_chunked_prefill: bool = Field(
        default=True,
        description="Enable chunked prefill",
    )

    max_num_batched_tokens: int = Field(
        default=8192,
        ge=128,
        description="Maximum number of batched tokens",
    )

    scheduler_delay: float = Field(
        default=0.0,
        ge=0.0,
        description="Scheduler delay in seconds",
    )

    # =========================================================================
    # Development & Debugging
    # =========================================================================

    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    log_requests: bool = Field(
        default=False,
        description="Log all requests/responses",
    )

    detailed_errors: bool = Field(
        default=True,
        description="Include detailed error messages",
    )

    # =========================================================================
    # Validators
    # =========================================================================

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("dtype")
    @classmethod
    def validate_dtype(cls, v: str) -> str:
        """Validate dtype"""
        valid_dtypes = ["auto", "float16", "bfloat16", "float32"]
        if v not in valid_dtypes:
            raise ValueError(f"Invalid dtype: {v}. Must be one of {valid_dtypes}")
        return v


# Global settings instance
settings = Settings()

