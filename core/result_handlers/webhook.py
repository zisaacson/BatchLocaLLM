"""
Webhook result handler.

Sends HTTP POST notification when batch completes.
This is the default handler and is always enabled.
"""

import os
import requests
from typing import List, Dict, Any
import logging

from .base import ResultHandler

logger = logging.getLogger(__name__)


class WebhookHandler(ResultHandler):
    """
    Send webhook notification when batch completes.
    
    This handler sends an HTTP POST request to the webhook URL
    specified in the batch job metadata.
    
    Configuration:
    - Webhook URL is specified per-batch (not global)
    - Includes retry logic with exponential backoff
    - Timeout: 30 seconds
    - Max retries: 3
    
    Payload format (OpenAI-compatible):
    {
        "id": "batch_abc123",
        "object": "batch",
        "status": "completed",
        "created_at": 1234567890,
        "completed_at": 1234567900,
        "request_counts": {
            "total": 1000,
            "completed": 995,
            "failed": 5
        },
        "metadata": {...},
        "output_file_url": "/v1/batches/batch_abc123/results"
    }
    """
    
    def name(self) -> str:
        return "webhook"
    
    def enabled(self) -> bool:
        # Webhook handler is always enabled
        # Individual batches specify webhook_url in metadata
        return True
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Send webhook notification.
        
        Args:
            batch_id: Batch identifier
            results: Batch results (not included in webhook payload)
            metadata: Batch metadata (must contain 'webhook_url')
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        webhook_url = metadata.get('webhook_url')
        
        if not webhook_url:
            logger.debug("No webhook_url in metadata, skipping webhook")
            return True  # Not an error, just no webhook configured
        
        # Build payload
        payload = {
            "id": batch_id,
            "object": "batch",
            "status": metadata.get('status', 'completed'),
            "created_at": metadata.get('created_at'),
            "completed_at": metadata.get('completed_at'),
            "request_counts": {
                "total": len(results),
                "completed": sum(1 for r in results if 'error' not in r),
                "failed": sum(1 for r in results if 'error' in r)
            },
            "metadata": {k: v for k, v in metadata.items() if k not in ['webhook_url', 'status', 'created_at', 'completed_at']},
            "output_file_url": f"/v1/batches/{batch_id}/results"
        }
        
        # Send webhook with retry logic
        max_retries = self.config.get('max_retries', 3)
        timeout = self.config.get('timeout', 30)
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending webhook to {webhook_url} (attempt {attempt + 1}/{max_retries})")
                
                response = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout
                )
                
                if response.status_code in [200, 201, 202, 204]:
                    logger.info(f"✅ Webhook sent successfully to {webhook_url}")
                    return True
                else:
                    logger.warning(f"⚠️  Webhook returned {response.status_code}: {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️  Webhook timeout (attempt {attempt + 1}/{max_retries})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️  Webhook failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Exponential backoff (1s, 2s, 4s)
            if attempt < max_retries - 1:
                import time
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s...")
                time.sleep(backoff)
        
        logger.error(f"❌ Webhook failed after {max_retries} attempts")
        return False

