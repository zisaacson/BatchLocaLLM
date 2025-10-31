"""
Centralized logging configuration for vLLM Batch Server.

Provides structured logging with JSON output, request tracing, and
integration with Prometheus/Grafana/Loki.

Usage:
    from core.batch_app.logging_config import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing batch", extra={"batch_id": "batch_123", "requests": 5000})
"""

import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from core.config import settings


class StructuredFormatter(logging.Formatter):
    """
    JSON structured logging formatter.
    
    Outputs logs in JSON format for easy parsing by Loki/Grafana.
    Includes timestamp, level, message, and custom fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json
        
        # Base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add environment
        log_entry["environment"] = settings.ENVIRONMENT
        
        # Add request ID if available (from context)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        # Add batch ID if available
        if hasattr(record, "batch_id"):
            log_entry["batch_id"] = record.batch_id
        
        # Add custom fields from extra={}
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


class RequestContextFilter(logging.Filter):
    """
    Add request context to log records.
    
    Automatically adds request_id and batch_id to all logs
    if they're available in the context.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to record."""
        # Try to get request context from thread-local storage
        try:
            from contextvars import ContextVar
            
            # These would be set by middleware/worker
            request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
            batch_id_var: ContextVar[Optional[str]] = ContextVar("batch_id", default=None)
            
            request_id = request_id_var.get()
            batch_id = batch_id_var.get()
            
            if request_id:
                record.request_id = request_id
            if batch_id:
                record.batch_id = batch_id
                
        except Exception:
            pass  # Context not available, skip
        
        return True


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    structured: bool = True
) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        structured: Use JSON structured logging (default: True)
    """
    # Get log level from settings or parameter
    log_level = level or settings.LOG_LEVEL
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get log file from settings or parameter
    log_file_path = log_file or settings.LOG_FILE
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_int)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(settings.LOG_FORMAT)
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_int)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestContextFilter())
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file_path:
        from pathlib import Path
        
        # Create log directory if needed
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(log_level_int)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RequestContextFilter())
        root_logger.addHandler(file_handler)
    
    # Silence noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("vllm").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    
    Example:
        logger = get_logger(__name__)
        logger.info("Processing batch", extra={"batch_id": "batch_123"})
    """
    return logging.getLogger(name)


# Context management for request tracing
from contextvars import ContextVar

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
batch_id_var: ContextVar[Optional[str]] = ContextVar("batch_id", default=None)


def set_request_context(request_id: Optional[str] = None, batch_id: Optional[str] = None) -> None:
    """
    Set request context for logging.
    
    Args:
        request_id: Request ID to track
        batch_id: Batch ID to track
    
    Example:
        set_request_context(request_id="req_123", batch_id="batch_456")
        logger.info("Processing")  # Will include request_id and batch_id
    """
    if request_id:
        request_id_var.set(request_id)
    if batch_id:
        batch_id_var.set(batch_id)


def clear_request_context() -> None:
    """Clear request context."""
    request_id_var.set(None)
    batch_id_var.set(None)


# Example usage
if __name__ == "__main__":
    # Setup logging
    setup_logging(level="INFO", structured=True)
    
    # Get logger
    logger = get_logger(__name__)
    
    # Log without context
    logger.info("Server starting")
    
    # Log with context
    set_request_context(request_id="req_123", batch_id="batch_456")
    logger.info("Processing batch", extra={"requests": 5000, "model": "gemma-3-4b"})
    
    # Log error
    try:
        raise ValueError("Test error")
    except Exception as e:
        logger.error("Failed to process", exc_info=True, extra={"error": str(e)})
    
    # Clear context
    clear_request_context()
    logger.info("Batch complete")

