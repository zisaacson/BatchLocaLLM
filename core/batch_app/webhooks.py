"""
Webhook notification system for batch job completion.

Sends HTTP POST callbacks when jobs complete/fail.
Includes retry logic with exponential backoff.
Supports HMAC-SHA256 signatures for security.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from core.config import settings
from .database import BatchJob, WebhookDeadLetter


def generate_webhook_signature(payload: dict, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: Webhook payload dictionary
        secret: Secret key for HMAC

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_webhook_signature(payload: dict, signature_header: str, secret: str, timestamp_header: str | None = None, max_age_seconds: int = 300) -> bool:
    """
    Verify HMAC-SHA256 signature for webhook payload.

    Args:
        payload: Webhook payload dictionary
        signature_header: Signature from X-Webhook-Signature header (format: "sha256=<hex>")
        secret: Secret key for HMAC verification
        timestamp_header: Optional timestamp from X-Webhook-Timestamp header
        max_age_seconds: Maximum age of webhook in seconds (default: 5 minutes)

    Returns:
        True if signature is valid and timestamp is recent, False otherwise
    """
    # Extract signature from header
    if not signature_header.startswith("sha256="):
        return False

    received_signature = signature_header[7:]  # Remove "sha256=" prefix

    # Generate expected signature
    expected_signature = generate_webhook_signature(payload, secret)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(received_signature, expected_signature):
        return False

    # Verify timestamp if provided (prevents replay attacks)
    if timestamp_header:
        try:
            webhook_timestamp = int(timestamp_header)
            current_timestamp = int(datetime.now(timezone.utc).timestamp())
            age = current_timestamp - webhook_timestamp

            if age > max_age_seconds or age < -60:  # Allow 1 minute clock skew
                return False
        except (ValueError, TypeError):
            return False

    return True


def send_webhook(
    batch_job: BatchJob,
    db: Session,
    max_retries: int | None = None,
    timeout: int | None = None
) -> bool:
    """
    Send webhook notification for batch job completion.

    Args:
        batch_job: The completed batch job
        db: Database session
        max_retries: Maximum number of retry attempts (uses job config or global default)
        timeout: Request timeout in seconds (uses job config or global default)

    Returns:
        True if webhook sent successfully, False otherwise
    """
    if not batch_job.webhook_url:
        return True  # No webhook configured, consider it success

    # Use job-specific config or global defaults
    max_retries = max_retries or batch_job.webhook_max_retries or settings.WEBHOOK_MAX_RETRIES
    timeout = timeout or batch_job.webhook_timeout or settings.WEBHOOK_TIMEOUT

    # Build webhook payload (Parasail/OpenAI compatible format)
    payload = {
        "id": batch_job.batch_id,
        "object": "batch",
        "endpoint": "/v1/chat/completions",
        "status": batch_job.status,
        "created_at": batch_job.created_at,  # Already Unix timestamp (int)
        "completed_at": batch_job.completed_at,  # Already Unix timestamp (int)
        "request_counts": {
            "total": batch_job.total_requests,
            "completed": batch_job.completed_requests,
            "failed": batch_job.failed_requests
        },
        "metadata": json.loads(batch_job.metadata_json) if batch_job.metadata_json else {},
        "output_file_url": f"/v1/batches/{batch_job.batch_id}/results" if batch_job.status == "completed" else None,
        "error_file_url": f"/v1/batches/{batch_job.batch_id}/errors" if batch_job.failed_requests > 0 else None
    }

    # Build headers
    headers = {"Content-Type": "application/json"}

    # Add HMAC signature if secret is configured
    secret = batch_job.webhook_secret or settings.WEBHOOK_SECRET
    if secret:
        signature = generate_webhook_signature(payload, secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"
        headers["X-Webhook-Timestamp"] = str(int(datetime.now(timezone.utc).timestamp()))

    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            batch_job.webhook_attempts = attempt + 1
            batch_job.webhook_last_attempt = datetime.now(timezone.utc)

            response = requests.post(
                batch_job.webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )

            if response.status_code in [200, 201, 202, 204]:
                batch_job.webhook_status = "sent"
                batch_job.webhook_error = None
                db.commit()
                print(f"✅ Webhook sent successfully for batch {batch_job.batch_id}")
                return True
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                batch_job.webhook_error = error_msg
                print(f"⚠️  Webhook failed (attempt {attempt + 1}/{max_retries}): {error_msg}")

        except requests.exceptions.Timeout:
            error_msg = f"Timeout after {timeout}s"
            batch_job.webhook_error = error_msg
            print(f"⚠️  Webhook timeout (attempt {attempt + 1}/{max_retries})")

        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)[:200]}"
            batch_job.webhook_error = error_msg
            print(f"⚠️  Webhook error (attempt {attempt + 1}/{max_retries}): {e}")

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            backoff = 2 ** attempt
            time.sleep(backoff)

    # All retries failed - add to dead letter queue
    batch_job.webhook_status = "failed"

    # Create dead letter entry
    dead_letter = WebhookDeadLetter(
        batch_id=batch_job.batch_id,
        webhook_url=batch_job.webhook_url,
        payload=json.dumps(payload),
        error_message=batch_job.webhook_error or "Unknown error",
        attempts=max_retries,
        last_attempt_at=datetime.now(timezone.utc)
    )
    db.add(dead_letter)
    db.commit()

    print(f"❌ Webhook failed after {max_retries} attempts for batch {batch_job.batch_id}")
    print(f"📝 Added to dead letter queue (ID: {dead_letter.id})")
    return False


def send_webhook_async(batch_id: str, webhook_url: str):
    """
    Send webhook asynchronously (non-blocking).

    This function can be called from the worker without blocking job processing.
    In production, you'd use Celery/RQ for this, but for now we'll use threading.
    """
    import threading

    from .database import SessionLocal

    def _send():
        db = SessionLocal()
        try:
            batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
            if batch_job:
                send_webhook(batch_job, db)
        finally:
            db.close()

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()

