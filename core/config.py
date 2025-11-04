"""
Centralized configuration management for vLLM Batch Server.

All environment variables and configuration settings are defined here.
This provides a single source of truth for all configuration values.

Usage:
    from config import settings
    
    # Access configuration
    print(settings.BATCH_API_PORT)
    print(settings.LABEL_STUDIO_URL)
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment variables can be set in:
    - .env file (for local development)
    - System environment (for production)
    - Docker/Kubernetes configs
    """
    
    # ========================================================================
    # Application Info
    # ========================================================================
    APP_NAME: str = "vLLM Batch Server"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # ========================================================================
    # Batch API Server
    # ========================================================================
    BATCH_API_HOST: str = "0.0.0.0"
    BATCH_API_PORT: int = 4080
    BATCH_API_WORKERS: int = 1
    BATCH_API_RELOAD: bool = True  # Auto-reload on code changes (dev only)
    
    # ========================================================================
    # Curation API Server
    # ========================================================================
    CURATION_API_HOST: str = "0.0.0.0"
    CURATION_API_PORT: int = 8001
    CURATION_API_WORKERS: int = 1
    CURATION_API_RELOAD: bool = True
    
    # ========================================================================
    # Integration/Static Server
    # ========================================================================
    INTEGRATION_SERVER_HOST: str = "0.0.0.0"
    INTEGRATION_SERVER_PORT: int = 4081
    
    # ========================================================================
    # Label Studio
    # ========================================================================
    LABEL_STUDIO_URL: str = "http://localhost:4115"
    LABEL_STUDIO_API_KEY: Optional[str] = None
    LABEL_STUDIO_PROJECT_ID: Optional[int] = None
    LABEL_STUDIO_TIMEOUT: int = 30  # Request timeout in seconds
    LABEL_STUDIO_MAX_RETRIES: int = 3
    LABEL_STUDIO_RETRY_BACKOFF: int = 1  # Backoff factor (1s, 2s, 4s, ...)
    LABEL_STUDIO_POOL_CONNECTIONS: int = 10  # Connection pool size
    LABEL_STUDIO_POOL_MAXSIZE: int = 20  # Max connections in pool
    
    # ========================================================================
    # Database - PostgreSQL (Production-grade)
    # ========================================================================
    DATABASE_URL: str = "postgresql://vllm_batch_user:vllm_batch_password_dev@localhost:5432/vllm_batch"
    DATABASE_ECHO: bool = False  # Log SQL queries (dev only)
    DATABASE_POOL_SIZE: int = 5  # Connection pool size
    DATABASE_MAX_OVERFLOW: int = 10  # Max connections beyond pool_size
    DATABASE_POOL_TIMEOUT: int = 30  # Timeout for getting connection from pool
    DATABASE_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour

    # Legacy SQLite support (deprecated - will be removed)
    DATABASE_DIR: str = "data/database"
    DATABASE_NAME: str = "batch_jobs.db"

    @property
    def LEGACY_SQLITE_URL(self) -> str:
        """Legacy SQLite database URL (for migration only)"""
        db_path = Path(self.DATABASE_DIR) / self.DATABASE_NAME
        return f"sqlite:///{db_path}"
    
    # ========================================================================
    # Storage Paths
    # ========================================================================
    DATA_DIR: str = "data"
    BATCHES_DIR: str = "data/batches"
    INPUT_DIR: str = "data/batches/input"
    OUTPUT_DIR: str = "data/batches/output"
    LOGS_DIR: str = "data/batches/logs"
    FILES_DIR: str = "data/files"
    MODELS_DIR: str = "models"
    BENCHMARKS_DIR: str = "benchmarks/results"
    
    # ========================================================================
    # Batch Processing
    # ========================================================================
    MAX_REQUESTS_PER_JOB: int = 50000  # OpenAI limit
    MAX_QUEUE_DEPTH: int = 20  # Max concurrent jobs
    MAX_TOTAL_QUEUED_REQUESTS: int = 1000000  # Max total requests across all queued jobs
    BATCH_EXPIRY_HOURS: int = 24  # Batch expiry time in hours
    WORKER_POLL_INTERVAL: int = 5  # Seconds between job checks
    WORKER_HEARTBEAT_INTERVAL: int = 30  # Seconds between heartbeats
    CHUNK_SIZE: int = 5000  # Process N requests at a time (proven safe from benchmarks)

    # GPU Health Thresholds
    GPU_MEMORY_THRESHOLD: float = 95.0  # Max GPU memory % before rejecting jobs
    GPU_TEMP_THRESHOLD: float = 85.0  # Max GPU temp (C) before rejecting jobs

    # vLLM Default Parameters
    DEFAULT_MAX_MODEL_LEN: int = 4096  # Default context window
    DEFAULT_MAX_TOKENS: int = 2000  # Default max output tokens
    
    # ========================================================================
    # Auto-Import to Curation
    # ========================================================================
    AUTO_IMPORT_TO_CURATION: bool = True
    CURATION_API_URL: str = "http://localhost:8001"
    
    # ========================================================================
    # Webhooks
    # ========================================================================
    WEBHOOK_TIMEOUT: int = 30  # Request timeout in seconds
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_DELAY: int = 5  # Seconds between retries
    WEBHOOK_SECRET: str | None = None  # Secret key for HMAC-SHA256 signatures (set in .env for security)
    
    # ========================================================================
    # vLLM Engine
    # ========================================================================
    DEFAULT_MODEL: str = "google/gemma-2-2b-it"
    GPU_MEMORY_UTILIZATION: float = 0.90
    MAX_MODEL_LEN: int = 8192
    TENSOR_PARALLEL_SIZE: int = 1
    TRUST_REMOTE_CODE: bool = True
    
    # ========================================================================
    # Monitoring
    # ========================================================================
    PROMETHEUS_PORT: int = 4022
    PROMETHEUS_URL: str = "http://localhost:4022"
    GRAFANA_PORT: int = 3000
    GRAFANA_URL: str = "http://localhost:3000"

    # Enable/disable monitoring features
    ENABLE_PROMETHEUS: bool = True
    ENABLE_GPU_MONITORING: bool = True

    # Sentry Error Tracking
    SENTRY_DSN: Optional[str] = None  # Set to enable Sentry error tracking
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # 10% of transactions for performance monitoring
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1  # 10% of transactions for profiling
    ENABLE_SENTRY: bool = False  # Auto-enabled if SENTRY_DSN is set
    
    # ========================================================================
    # Logging
    # ========================================================================
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: Optional[str] = None  # If set, log to file

    # ========================================================================
    # Curation UI Defaults
    # ========================================================================
    DEFAULT_PAGE_SIZE: int = 50  # Default items per page
    MAX_PAGE_SIZE: int = 100  # Maximum items per page
    MIN_AGREEMENT_SCORE: float = 0.8  # Minimum agreement for gold-star export
    LABEL_STUDIO_HEALTH_TIMEOUT: int = 5  # Timeout for health checks

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    ENABLE_RATE_LIMITING: bool = False  # Enable/disable rate limiting globally
    RATE_LIMIT_BATCHES: str = "10/minute"  # Rate limit for POST /v1/batches
    RATE_LIMIT_FILES: str = "20/minute"  # Rate limit for POST /v1/files

    # ========================================================================
    # Security
    # ========================================================================
    API_KEY: Optional[str] = None  # If set, require API key for requests
    CORS_ORIGINS: str = "*"  # CORS allowed origins (comma-separated or "*")
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"  # CORS allowed methods (comma-separated or "*")
    CORS_ALLOW_HEADERS: str = "*"  # CORS allowed headers (comma-separated or "*")
    
    # ========================================================================
    # External Services (for integrations)
    # ========================================================================
    ARIS_APP_URL: Optional[str] = None  # e.g., http://your-app-server:4000
    ARIS_WEBHOOK_URL: Optional[str] = None  # e.g., http://your-app-server:4000/api/ml/batch/webhook

    # ========================================================================
    # Feature Flags
    # ========================================================================
    ENABLE_AUTO_IMPORT: bool = True
    ENABLE_WEBHOOKS: bool = True
    ENABLE_BENCHMARKING: bool = True
    ENABLE_STATIC_SERVER: bool = True

    # ========================================================================
    # Properties (computed values)
    # ========================================================================

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [x.strip() for x in self.CORS_ORIGINS.split(",")]

    @property
    def cors_methods_list(self) -> list[str]:
        """Parse CORS_ALLOW_METHODS into a list"""
        if self.CORS_ALLOW_METHODS == "*":
            return ["*"]
        return [x.strip() for x in self.CORS_ALLOW_METHODS.split(",")]

    @property
    def cors_headers_list(self) -> list[str]:
        """Parse CORS_ALLOW_HEADERS into a list"""
        if self.CORS_ALLOW_HEADERS == "*":
            return ["*"]
        return [x.strip() for x in self.CORS_ALLOW_HEADERS.split(",")]

    # Pydantic V2 configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env file
    )

    def create_directories(self) -> None:
        """Create all required directories"""
        dirs = [
            self.DATA_DIR,
            self.BATCHES_DIR,
            self.INPUT_DIR,
            self.OUTPUT_DIR,
            self.LOGS_DIR,
            self.FILES_DIR,
            self.MODELS_DIR,
            self.BENCHMARKS_DIR,
            self.DATABASE_DIR,
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def get_service_urls(self) -> dict[str, str]:
        """Get all service URLs for display"""
        return {
            "batch_api": f"http://localhost:{self.BATCH_API_PORT}",
            "curation_ui": f"http://localhost:{self.CURATION_API_PORT}",
            "label_studio": self.LABEL_STUDIO_URL,
            "integration": f"http://localhost:{self.INTEGRATION_SERVER_PORT}",
            "prometheus": self.PROMETHEUS_URL,
            "grafana": self.GRAFANA_URL,
        }
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"


# ============================================================================
# Global Settings Instance
# ============================================================================

# Create global settings instance
settings = Settings()

# Create required directories on import
settings.create_directories()


# ============================================================================
# Helper Functions
# ============================================================================

def get_settings() -> Settings:
    """
    Get settings instance.
    
    Useful for dependency injection in FastAPI:
        @app.get("/")
        def root(settings: Settings = Depends(get_settings)):
            return {"port": settings.BATCH_API_PORT}
    """
    return settings


def print_config() -> None:
    """Print current configuration (for debugging)"""
    print("=" * 60)
    print(f"{settings.APP_NAME} v{settings.APP_VERSION}")
    print("=" * 60)
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Batch API: http://{settings.BATCH_API_HOST}:{settings.BATCH_API_PORT}")
    print(f"Curation UI: http://{settings.CURATION_API_HOST}:{settings.CURATION_API_PORT}")
    print(f"Label Studio: {settings.LABEL_STUDIO_URL}")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Default Model: {settings.DEFAULT_MODEL}")
    print(f"GPU Memory: {settings.GPU_MEMORY_UTILIZATION * 100}%")
    print("=" * 60)


if __name__ == "__main__":
    # Print configuration when run directly
    print_config()
    
    # Print service URLs
    print("\nService URLs:")
    for name, url in settings.get_service_urls().items():
        print(f"  {name:20s}: {url}")

