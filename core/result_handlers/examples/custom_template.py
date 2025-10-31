"""
Template: Custom Result Handler

Use this template to create your own result handler.

Steps:
1. Copy this file to result_handlers/my_handler.py
2. Rename the class to match your use case
3. Implement name(), enabled(), and handle() methods
4. Register in config.py or at runtime

Example use cases:
- Send results to your ML pipeline
- Insert into your application database
- Trigger downstream workflows
- Send notifications (email, Slack, etc.)
- Custom data transformations
"""

import os
from typing import List, Dict, Any
import logging

from result_handlers.base import ResultHandler

logger = logging.getLogger(__name__)


class CustomHandler(ResultHandler):
    """
    Custom result handler template.
    
    Replace this docstring with a description of what your handler does.
    
    Configuration:
    - List any environment variables or config options needed
    - Example: CUSTOM_API_URL, CUSTOM_API_KEY, etc.
    """
    
    def name(self) -> str:
        """
        Return the handler name.
        
        This name is used in logs and configuration.
        """
        return "custom_handler"  # Change this to your handler name
    
    def enabled(self) -> bool:
        """
        Check if this handler should run.
        
        Return True if:
        - Required configuration is present
        - Dependencies are available
        - Handler should process this batch
        
        Return False to skip this handler.
        """
        # Example: Check if API URL is configured
        api_url = os.getenv('CUSTOM_API_URL')
        return bool(api_url)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Process batch results.
        
        This method is called when a batch job completes.
        
        Args:
            batch_id: Unique batch identifier (e.g., "batch_abc123")
            results: List of result objects in JSONL format
                Each result has:
                - custom_id: User-provided identifier
                - response: LLM response with choices, usage, etc.
                - error: Error message (if request failed)
            metadata: User-provided metadata from batch submission
                May contain custom fields like:
                - source: Where the batch came from
                - user_id: Who submitted the batch
                - Any other custom fields
        
        Returns:
            True if processing successful, False otherwise
        """
        logger.info(f"Processing batch {batch_id} with {len(results)} results")
        
        # Example: Filter successful results
        successful_results = [r for r in results if 'error' not in r]
        failed_results = [r for r in results if 'error' in r]
        
        logger.info(f"Successful: {len(successful_results)}, Failed: {len(failed_results)}")
        
        # TODO: Implement your custom logic here
        # Examples:
        
        # 1. Send to your API
        # api_url = os.getenv('CUSTOM_API_URL')
        # response = requests.post(api_url, json={'batch_id': batch_id, 'results': results})
        
        # 2. Insert into your database
        # db.insert('results', {'batch_id': batch_id, 'data': results})
        
        # 3. Transform and save
        # transformed = [transform(r) for r in results]
        # save_to_file(f'output/{batch_id}.json', transformed)
        
        # 4. Trigger downstream workflow
        # workflow_engine.trigger('process_results', batch_id=batch_id)
        
        # 5. Send notification
        # slack.send_message(f"Batch {batch_id} completed with {len(results)} results")
        
        # Return True if successful, False if failed
        return True
    
    def on_error(self, error: Exception) -> None:
        """
        Called when handle() raises an exception.
        
        Override this to implement custom error handling.
        
        Args:
            error: The exception that was raised
        """
        logger.error(f"Custom handler failed: {error}")
        
        # Example: Send error notification
        # slack.send_message(f"⚠️ Handler failed: {error}")


# Example usage:
# 
# 1. Register at startup (in config.py or main.py):
# from result_handlers import register_handler
# from result_handlers.custom_template import CustomHandler
#
# handler = CustomHandler(config={'api_url': 'https://api.example.com'})
# register_handler(handler)
#
# 2. Or register dynamically:
# from result_handlers import get_registry
#
# registry = get_registry()
# registry.register(CustomHandler())

