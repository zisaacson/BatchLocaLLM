"""
Example: Webhook Handler

Sends batch results to HTTP webhook endpoint.

Use Cases:
- Notify external systems when batches complete
- Trigger downstream workflows
- Send results to Slack, Discord, etc.
- Integrate with Zapier, Make.com, n8n

Setup:
    1. Configure webhook URL
    2. Optionally add authentication headers
    3. Register handler in your application

Example Webhook Payload:
    {
        "batch_id": "batch_abc123",
        "status": "completed",
        "total_results": 100,
        "metadata": {
            "user_id": "user_123",
            "project": "my_project"
        },
        "results": [
            {
                "custom_id": "req_001",
                "response": {...}
            }
        ]
    }
"""

from typing import Dict, Any, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.result_handlers.base import ResultHandler, get_registry


class WebhookHandler(ResultHandler):
    """
    Generic webhook handler for batch results.
    
    Features:
    - Automatic retries with exponential backoff
    - Custom headers (for authentication)
    - Configurable payload format
    - Error handling and logging
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Required config
        self.webhook_url = self.config.get('webhook_url')
        if not self.webhook_url:
            raise ValueError("webhook_url is required in config")
        
        # Optional config
        self.headers = self.config.get('headers', {})
        self.timeout = self.config.get('timeout', 30)
        self.include_results = self.config.get('include_results', True)
        self.max_results = self.config.get('max_results', 100)
        
        # Setup session with retries
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
    
    def name(self) -> str:
        return "webhook_handler"
    
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Always enabled if webhook_url is configured."""
        return bool(self.webhook_url)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Send results to webhook.
        
        Args:
            batch_id: Batch identifier
            results: List of result dictionaries
            metadata: Batch metadata
            
        Returns:
            True if webhook call successful, False otherwise
        """
        try:
            # Prepare payload
            payload = {
                'batch_id': batch_id,
                'status': 'completed',
                'total_results': len(results),
                'metadata': metadata
            }
            
            # Optionally include results
            if self.include_results:
                payload['results'] = results[:self.max_results]
            
            # Send webhook
            response = self.session.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            self.logger.info(
                f"Webhook sent successfully",
                extra={
                    'batch_id': batch_id,
                    'url': self.webhook_url,
                    'status_code': response.status_code
                }
            )
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Webhook failed: {e}",
                extra={'batch_id': batch_id, 'url': self.webhook_url},
                exc_info=True
            )
            return False
    
    def on_error(self, error: Exception) -> None:
        """Log webhook errors."""
        self.logger.error(
            f"Webhook error: {error}",
            extra={'handler': self.name()},
            exc_info=True
        )


def register_webhook_handler():
    """
    Register webhook handler.
    
    Example configurations:
    """
    
    # Example 1: Simple webhook
    simple_webhook = WebhookHandler(config={
        'webhook_url': 'https://my-app.com/api/batch-complete',
        'priority': 50
    })
    
    # Example 2: Webhook with authentication
    auth_webhook = WebhookHandler(config={
        'webhook_url': 'https://my-app.com/api/batch-complete',
        'headers': {
            'Authorization': 'Bearer YOUR_API_KEY',
            'X-Custom-Header': 'value'
        },
        'priority': 50
    })
    
    # Example 3: Slack webhook
    slack_webhook = WebhookHandler(config={
        'webhook_url': 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        'include_results': False,  # Don't send full results to Slack
        'priority': 50
    })
    
    # Example 4: Discord webhook
    discord_webhook = WebhookHandler(config={
        'webhook_url': 'https://discord.com/api/webhooks/YOUR/WEBHOOK',
        'include_results': False,
        'priority': 50
    })
    
    # Register handler
    registry = get_registry()
    registry.register(simple_webhook)
    
    print(f"✅ Registered webhook handler: {simple_webhook.name()}")


# Example: Custom webhook handler for Slack
class SlackWebhookHandler(WebhookHandler):
    """
    Slack-specific webhook handler with formatted messages.
    """
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """Send Slack-formatted message."""
        try:
            # Format Slack message
            payload = {
                'text': f'✅ Batch {batch_id} completed!',
                'blocks': [
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f'*Batch Completed*\n\n'
                                    f'• Batch ID: `{batch_id}`\n'
                                    f'• Results: {len(results)}\n'
                                    f'• Project: {metadata.get("project", "N/A")}'
                        }
                    }
                ]
            }
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Slack webhook failed: {e}", exc_info=True)
            return False


# Example usage
if __name__ == '__main__':
    register_webhook_handler()
    
    # Test with sample data
    from core.result_handlers.base import get_registry
    
    registry = get_registry()
    
    sample_results = [
        {'custom_id': 'req_001', 'response': {'content': 'Result 1'}},
        {'custom_id': 'req_002', 'response': {'content': 'Result 2'}}
    ]
    
    sample_metadata = {
        'user_id': 'user_123',
        'project': 'test_project'
    }
    
    success = registry.process_results(
        batch_id='test_batch_001',
        results=sample_results,
        metadata=sample_metadata
    )
    
    print(f"✅ Webhook sent: {success}")

