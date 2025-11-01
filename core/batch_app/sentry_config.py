"""
Sentry integration for error tracking and performance monitoring.

This module provides centralized Sentry configuration for the vLLM Batch Server.
It integrates with FastAPI, SQLAlchemy, and our custom logging/metrics.

Usage:
    from core.batch_app.sentry_config import init_sentry
    
    # In your application startup
    init_sentry()
"""

import logging
from typing import Optional
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

try:
    from core.config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    """
    Initialize Sentry SDK with FastAPI and SQLAlchemy integrations.
    
    Only initializes if SENTRY_DSN is set in environment.
    Automatically captures:
    - Unhandled exceptions
    - FastAPI request errors
    - SQLAlchemy query errors
    - Performance traces (sampled)
    - Profiling data (sampled)
    
    Environment Variables:
        SENTRY_DSN: Sentry project DSN (required)
        SENTRY_TRACES_SAMPLE_RATE: % of transactions to trace (default: 0.1)
        SENTRY_PROFILES_SAMPLE_RATE: % of transactions to profile (default: 0.1)
        ENVIRONMENT: Environment name (development, staging, production)
    """
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured - error tracking disabled")
        return

    try:
        # Configure logging integration
        # Capture ERROR and above, but don't send breadcrumbs for every log
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors and above as events
        )

        # Initialize Sentry
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",

            # Integrations
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint",  # Group by endpoint, not URL
                    failed_request_status_codes=[500, 501, 502, 503, 504, 505]
                ),
                SqlalchemyIntegration(),
                sentry_logging,
            ],

            # Performance Monitoring
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,

            # Additional options
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,  # Include stack traces in messages
            max_breadcrumbs=50,  # Keep last 50 breadcrumbs

            # Custom tags
            before_send=before_send_filter,
        )

        logger.info(
            "Sentry initialized",
            extra={
                "environment": settings.ENVIRONMENT,
                "traces_sample_rate": settings.SENTRY_TRACES_SAMPLE_RATE,
                "profiles_sample_rate": settings.SENTRY_PROFILES_SAMPLE_RATE
            }
        )

    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)


def before_send_filter(event: dict, hint: dict) -> Optional[dict]:
    """
    Filter and modify events before sending to Sentry.
    
    This allows us to:
    - Filter out noisy errors
    - Add custom tags/context
    - Scrub sensitive data
    - Drop events we don't care about
    
    Args:
        event: The event dictionary
        hint: Additional context about the event
        
    Returns:
        Modified event dict, or None to drop the event
    """
    # Add custom tags
    event.setdefault("tags", {})
    event["tags"]["service"] = "vllm-batch-server"

    # Filter out specific errors we don't care about
    if "exc_info" in hint:
        exc_type, exc_value, tb = hint["exc_info"]

        # Don't send client disconnection errors
        if exc_type.__name__ in ["ClientDisconnect", "ConnectionResetError"]:
            return None

        # Don't send 404 errors (not really errors)
        if "404" in str(exc_value):
            return None

    # Add request context if available
    if "request" in event:
        request = event["request"]

        # Add custom headers to context
        if "headers" in request:
            headers = request["headers"]
            if "X-Request-ID" in headers:
                event["tags"]["request_id"] = headers["X-Request-ID"]

    return event


def capture_exception(
    error: Exception,
    context: Optional[dict] = None,
    level: str = "error"
) -> None:
    """
    Manually capture an exception and send to Sentry.
    
    Use this for handled exceptions that you want to track.
    
    Args:
        error: The exception to capture
        context: Additional context to attach
        level: Severity level (error, warning, info)
        
    Example:
        try:
            process_batch(batch_id)
        except Exception as e:
            capture_exception(e, context={
                "batch_id": batch_id,
                "model": model_name
            })
    """
    if not settings.SENTRY_DSN:
        return

    with sentry_sdk.push_scope() as scope:
        # Set level
        scope.level = level

        # Add context
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        # Capture exception
        sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[dict] = None
) -> None:
    """
    Manually capture a message and send to Sentry.
    
    Use this for important events that aren't exceptions.
    
    Args:
        message: The message to capture
        level: Severity level (error, warning, info)
        context: Additional context to attach
        
    Example:
        capture_message(
            "Batch processing completed",
            level="info",
            context={
                "batch_id": batch_id,
                "duration": duration,
                "requests_processed": count
            }
        )
    """
    if not settings.SENTRY_DSN:
        return

    with sentry_sdk.push_scope() as scope:
        # Set level
        scope.level = level

        # Add context
        if context:
            for key, value in context.items():
                scope.set_context(key, value)

        # Capture message
        sentry_sdk.capture_message(message)


def set_user_context(user_id: str, email: Optional[str] = None) -> None:
    """
    Set user context for Sentry events.
    
    This helps track which users are experiencing errors.
    
    Args:
        user_id: Unique user identifier
        email: User email (optional)
        
    Example:
        set_user_context(user_id="user_123", email="user@example.com")
    """
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.set_user({
        "id": user_id,
        "email": email
    })


def set_batch_context(batch_id: str, model: str, requests: int) -> None:
    """
    Set batch processing context for Sentry events.
    
    This adds batch-specific context to all subsequent events.
    
    Args:
        batch_id: Batch job ID
        model: Model being used
        requests: Number of requests in batch
        
    Example:
        set_batch_context(
            batch_id="batch_abc123",
            model="google/gemma-3-4b-it",
            requests=5000
        )
    """
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.set_context("batch", {
        "batch_id": batch_id,
        "model": model,
        "requests": requests
    })


def clear_context() -> None:
    """
    Clear all Sentry context.
    
    Call this after processing a request/batch to avoid
    context leaking between requests.
    """
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.set_user(None)
    sentry_sdk.set_context("batch", None)


# Export main functions
__all__ = [
    "init_sentry",
    "capture_exception",
    "capture_message",
    "set_user_context",
    "set_batch_context",
    "clear_context"
]

