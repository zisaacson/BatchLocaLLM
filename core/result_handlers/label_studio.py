"""
Label Studio result handler.

Automatically imports batch results to Label Studio for curation.
This is an optional handler that requires Label Studio configuration.

Use case:
- Review LLM outputs for quality
- Correct errors in responses
- Mark gold-star examples for training
- Export curated datasets (ICL, fine-tuning)
"""

import os
import requests
from typing import List, Dict, Any
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
    - Support for schema-driven validation
    
    Example metadata:
    {
        "label_studio_project_id": 123,
        "schema_type": "chat_completion",
        "source": "my_app"
    }
    """
    
    def name(self) -> str:
        return "label_studio"
    
    def enabled(self) -> bool:
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
            metadata: Batch metadata (may contain project_id, schema_type)
            
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
            
            # Build task data
            task_data = {
                "custom_id": custom_id,
                "batch_id": batch_id,
                "input_messages": input_messages,
                "llm_response": body.get('choices', [{}])[0].get('message', {}).get('content', ''),
                "model": body.get('model', 'unknown'),
                "schema_type": metadata.get('schema_type', 'generic'),
            }
            
            # Add metadata
            task_meta = {
                "batch_id": batch_id,
                "custom_id": custom_id,
                "source": metadata.get('source', 'vllm_batch'),
                "created_at": metadata.get('completed_at'),
            }
            
            tasks.append({
                "data": task_data,
                "meta": task_meta
            })
        
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

