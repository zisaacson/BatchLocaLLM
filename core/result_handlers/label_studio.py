"""
Generic Label Studio result handler.

Automatically imports batch results to Label Studio for curation.
This is an optional handler that requires Label Studio configuration.

Use case:
- Review LLM outputs for quality
- Correct errors in responses
- Mark high-quality examples for training
- Export curated datasets (ICL, fine-tuning)

For Aris-specific conquest parsing, see integrations/aris/result_handlers/label_studio_aris.py
"""

import os
import json
import re
import requests
from typing import List, Dict, Any, Optional
import logging

from .base import ResultHandler

logger = logging.getLogger(__name__)


class LabelStudioHandler(ResultHandler):
    """
    Import batch results to Label Studio for curation.
    
    Configuration (environment variables or config dict):
    - LABEL_STUDIO_URL: Label Studio server URL
    - LABEL_STUDIO_API_KEY: API key for authentication
    - LABEL_STUDIO_PROJECT_ID: Project ID (optional, can be per-batch)
    
    Features:
    - Auto-create tasks from batch results
    - Preserve custom_id for tracking
    - Include input prompts and LLM responses
    - Support for custom metadata via batch metadata
    
    Example metadata:
    {
        "label_studio_project_id": 123,
        "schema_type": "chat_completion",
        "source": "my_app",
        "task_data": {"custom_field": "value"},  # Custom fields for task data
        "task_meta": {"custom_meta": "value"}    # Custom fields for task meta
    }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Label Studio handler."""
        super().__init__(config)

    def name(self) -> str:
        return "label_studio"
    
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if Label Studio is configured."""
        url = self.config.get('url') or os.getenv('LABEL_STUDIO_URL')
        api_key = self.config.get('api_key') or os.getenv('LABEL_STUDIO_API_KEY')

        return bool(url and api_key)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Import results to Label Studio.
        
        Args:
            batch_id: Batch identifier
            results: List of batch results
            metadata: Batch metadata (may contain project_id, schema_type, task_data, task_meta)
            
        Returns:
            True if import successful, False otherwise
        """
        # Get configuration
        url = self.config.get('url') or os.getenv('LABEL_STUDIO_URL')
        api_key = self.config.get('api_key') or os.getenv('LABEL_STUDIO_API_KEY')
        project_id = (
            metadata.get('label_studio_project_id') or
            self.config.get('project_id') or
            os.getenv('LABEL_STUDIO_PROJECT_ID')
        )
        
        if not project_id:
            logger.warning("No Label Studio project_id specified, skipping import")
            return True  # Not an error, just no project configured
        
        # Convert results to Label Studio tasks
        tasks = []
        for result in results:
            # Skip failed results
            if 'error' in result:
                continue

            # Extract data
            custom_id = result.get('custom_id', 'unknown')
            response = result.get('response', {})
            body = response.get('body', {})

            # Get input messages
            input_messages = result.get('input', {}).get('messages', [])

            # Get LLM response text
            llm_response = body.get('choices', [{}])[0].get('message', {}).get('content', '')

            # Build task data (generic format)
            task_data = {
                "custom_id": custom_id,
                "batch_id": batch_id,
                "schema_type": metadata.get('schema_type', 'generic'),
                "model": body.get('model', 'unknown'),
                
                # Input prompt (first user message)
                "input_prompt": next((msg['content'] for msg in input_messages if msg.get('role') == 'user'), ''),
                
                # LLM response
                "llm_response": llm_response,
                
                # Additional metadata from batch
                **metadata.get('task_data', {})  # Allow custom fields via metadata
            }

            # Add metadata
            task_meta = {
                "batch_id": batch_id,
                "custom_id": custom_id,
                "source": metadata.get('source', 'vllm_batch'),
                "created_at": metadata.get('completed_at'),
                **metadata.get('task_meta', {})  # Allow custom meta fields
            }

            # Schema-driven pre-labeling (optional)
            # Parse LLM response and create predictions for Label Studio
            predictions = self._create_predictions(llm_response, metadata.get('schema_type', 'generic'))

            task: Dict[str, Any] = {
                "data": task_data,
                "meta": task_meta
            }

            # Add predictions if available
            if predictions:
                task["predictions"] = [predictions]

            tasks.append(task)
        
        if not tasks:
            logger.warning("No valid results to import to Label Studio")
            return True
        
        # Import to Label Studio
        try:
            logger.info(f"Importing {len(tasks)} tasks to Label Studio project {project_id}")
            
            response = requests.post(
                f"{url}/api/projects/{project_id}/import",
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "application/json"
                },
                json=tasks,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                result_data = response.json()
                task_count = result_data.get('task_count', len(tasks))
                logger.info(f"✅ Imported {task_count} tasks to Label Studio")
                logger.info(f"🌐 View at: {url}/projects/{project_id}")
                return True
            else:
                logger.error(f"❌ Label Studio import failed: {response.status_code} {response.text[:200]}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Label Studio import failed: {e}")
            return False

    def _create_predictions(self, llm_response: str, schema_type: str) -> Dict[str, Any] | None:
        """
        Create Label Studio predictions from LLM response.

        Parses structured LLM output and converts to Label Studio prediction format.
        This enables pre-labeling so humans can review/correct instead of labeling from scratch.

        Args:
            llm_response: Raw LLM response text
            schema_type: Type of schema (e.g., 'chat_completion', 'generic')

        Returns:
            Label Studio prediction object or None if parsing fails
        """
        try:
            # Try to parse as JSON first
            if llm_response.strip().startswith('{'):
                data = json.loads(llm_response)
            else:
                # Try to extract JSON from markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                else:
                    # No structured data found
                    return None

            # Generic schema - just store the parsed JSON
            return {
                "result": [{
                    "from_name": "response",
                    "to_name": "text",
                    "type": "textarea",
                    "value": {
                        "text": [json.dumps(data, indent=2)]
                    }
                }],
                "score": 0.7
            }

        except (json.JSONDecodeError, KeyError, IndexError):
            # Failed to parse - no predictions
            return None

    def on_error(self, error: Exception, batch_id: str, metadata: Dict[str, Any]) -> None:
        """Log Label Studio import errors."""
        logger.error(f"Label Studio handler error for batch {batch_id}: {error}")


# Example usage:
"""
# 1. Configure Label Studio
export LABEL_STUDIO_URL="http://localhost:8080"
export LABEL_STUDIO_API_KEY="your-api-key"
export LABEL_STUDIO_PROJECT_ID="123"

# 2. Enable handler in config
handlers:
  - name: label_studio
    enabled: true

# 3. Add custom metadata to batch request
{
    "custom_id": "task-1",
    "method": "POST",
    "url": "/v1/chat/completions",
    "body": {...},
    "metadata": {
        "label_studio_project_id": 123,
        "schema_type": "chat_completion",
        "task_data": {
            "user_id": "user@example.com",
            "domain": "my-project"
        },
        "task_meta": {
            "priority": "high"
        }
    }
}

# 4. Results will be automatically imported to Label Studio
"""

