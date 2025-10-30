"""
Webhook notification system for batch job completion.

Sends HTTP POST callbacks when jobs complete/fail.
Includes retry logic with exponential backoff.
"""

import requests
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from .database import BatchJob


def send_webhook(
    batch_job: BatchJob,
    db: Session,
    max_retries: int = 3,
    timeout: int = 30
) -> bool:
    """
    Send webhook notification for batch job completion.
    
    Args:
        batch_job: The completed batch job
        db: Database session
        max_retries: Maximum number of retry attempts
        timeout: Request timeout in seconds
        
    Returns:
        True if webhook sent successfully, False otherwise
    """
    if not batch_job.webhook_url:
        return True  # No webhook configured, consider it success
    
    # Build webhook payload (Parasail/OpenAI compatible format)
    payload = {
        "id": batch_job.batch_id,
        "object": "batch",
        "endpoint": "/v1/chat/completions",
        "status": batch_job.status,
        "created_at": int(batch_job.created_at.timestamp()) if batch_job.created_at else None,
        "completed_at": int(batch_job.completed_at.timestamp()) if batch_job.completed_at else None,
        "request_counts": {
            "total": batch_job.total_requests,
            "completed": batch_job.completed_requests,
            "failed": batch_job.failed_requests
        },
        "metadata": json.loads(batch_job.metadata_json) if batch_job.metadata_json else {},
        "output_file_url": f"/v1/batches/{batch_job.batch_id}/results" if batch_job.status == "completed" else None,
        "error_file_url": f"/v1/batches/{batch_job.batch_id}/errors" if batch_job.failed_requests > 0 else None
    }
    
    # Retry logic with exponential backoff
    for attempt in range(max_retries):
        try:
            batch_job.webhook_attempts = attempt + 1
            batch_job.webhook_last_attempt = datetime.utcnow()
            
            response = requests.post(
                batch_job.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
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
    
    # All retries failed
    batch_job.webhook_status = "failed"
    db.commit()
    print(f"❌ Webhook failed after {max_retries} attempts for batch {batch_job.batch_id}")
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

