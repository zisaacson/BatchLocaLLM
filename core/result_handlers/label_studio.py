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
    - Support for schema-driven validation
    
    Example metadata:
    {
        "label_studio_project_id": 123,
        "schema_type": "chat_completion",
        "source": "my_app"
    }
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Label Studio handler with client."""
        super().__init__(config)

        # Initialize Label Studio client if configured
        url = self.config.get('url') or os.getenv('LABEL_STUDIO_URL')
        api_key = self.config.get('api_key') or os.getenv('LABEL_STUDIO_API_KEY')

        self.client: Optional[Any] = None
        if url and api_key:
            try:
                from core.batch_app.label_studio_integration import LabelStudioClient
                self.client = LabelStudioClient(url, api_key)
            except ImportError:
                logger.warning("Label Studio integration not available")

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

            # Get LLM response text
            llm_response = body.get('choices', [{}])[0].get('message', {}).get('content', '')

            # ✅ NEW: Parse conquest data from messages
            conquest_data = self._parse_conquest_from_messages(input_messages, metadata.get('schema_type', 'generic'))

            # ✅ NEW: Extract conquest metadata
            conquest_id = metadata.get('conquest_id') or custom_id
            philosopher = metadata.get('philosopher', 'unknown@example.com')
            domain = metadata.get('domain', 'default')

            # Build task data with STRUCTURED conquest data
            task_data = {
                "custom_id": custom_id,
                "batch_id": batch_id,
                "conquest_id": conquest_id,  # ✅ ADDED for bidirectional sync
                "philosopher": philosopher,   # ✅ ADDED for bidirectional sync
                "domain": domain,             # ✅ ADDED for bidirectional sync
                "schema_type": metadata.get('schema_type', 'generic'),
                "model": body.get('model', 'unknown'),

                # ✅ ADDED: Structured conquest data
                **conquest_data,  # name, role, location, work_history, education, etc.

                # LLM response
                "llm_response": llm_response,
            }

            # Add metadata
            task_meta = {
                "batch_id": batch_id,
                "custom_id": custom_id,
                "conquest_id": conquest_id,  # ✅ ADDED
                "philosopher": philosopher,   # ✅ ADDED
                "domain": domain,             # ✅ ADDED
                "source": metadata.get('source', 'vllm_batch'),
                "created_at": metadata.get('completed_at'),
            }

            # Schema-driven pre-labeling
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
            schema_type: Type of schema (e.g., 'candidate_evaluation', 'generic')

        Returns:
            Label Studio prediction object or None if parsing fails
        """
        import json
        import re

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

            # Schema-specific parsing
            if schema_type == 'candidate_evaluation':
                return self._parse_candidate_evaluation(data)
            elif schema_type == 'chat_completion':
                return self._parse_chat_completion(data)
            else:
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
                    "score": 0.8
                }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f"Failed to parse LLM response for pre-labeling: {e}")
            return None

    def _parse_candidate_evaluation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse candidate evaluation schema.

        Expected fields:
        - recommendation: Strong Yes/Yes/Maybe/No/Strong No
        - trajectory_rating: Exceptional/Strong/Good/Average/Weak
        - company_pedigree: Exceptional/Strong/Good/Average/Weak
        - educational_pedigree: Exceptional/Strong/Good/Average/Weak
        - is_software_engineer: bool
        - reasoning: str
        """
        result = []

        # Recommendation (choices)
        if 'recommendation' in data:
            result.append({
                "from_name": "recommendation",
                "to_name": "candidate",
                "type": "choices",
                "value": {
                    "choices": [data['recommendation']]
                }
            })

        # Trajectory rating (choices)
        if 'trajectory_rating' in data:
            result.append({
                "from_name": "trajectory_rating",
                "to_name": "candidate",
                "type": "choices",
                "value": {
                    "choices": [data['trajectory_rating']]
                }
            })

        # Company pedigree (choices)
        if 'company_pedigree' in data:
            result.append({
                "from_name": "company_pedigree",
                "to_name": "candidate",
                "type": "choices",
                "value": {
                    "choices": [data['company_pedigree']]
                }
            })

        # Educational pedigree (choices)
        if 'educational_pedigree' in data:
            result.append({
                "from_name": "educational_pedigree",
                "to_name": "candidate",
                "type": "choices",
                "value": {
                    "choices": [data['educational_pedigree']]
                }
            })

        # Is software engineer (checkbox)
        if 'is_software_engineer' in data:
            result.append({
                "from_name": "is_software_engineer",
                "to_name": "candidate",
                "type": "choices",
                "value": {
                    "choices": ["Yes"] if data['is_software_engineer'] else []
                }
            })

        # Reasoning (textarea)
        if 'reasoning' in data:
            result.append({
                "from_name": "reasoning",
                "to_name": "candidate",
                "type": "textarea",
                "value": {
                    "text": [data['reasoning']]
                }
            })

        return {
            "result": result,
            "score": 0.85  # Confidence score
        }

    def _parse_chat_completion(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse generic chat completion schema.

        Just stores the response as text.
        """
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

    def _parse_conquest_from_messages(self, messages: List[Dict[str, Any]], schema_type: str) -> Dict[str, Any]:
        """
        Parse conquest data from messages array.

        Extracts structured data based on schema type.
        This is critical for:
        - Displaying questions in curation UI
        - Showing candidate/entity information
        - Enabling bidirectional sync (needs conquest_id, philosopher, domain)

        Args:
            messages: Array of chat messages (system, user, assistant)
            schema_type: Type of schema (e.g., 'candidate_evaluation', 'generic')

        Returns:
            Dictionary with parsed conquest data
        """
        result = {
            "name": "Unknown",
            "role": "",
            "location": "",
            "work_history": [],
            "education": [],
            "system_prompt": "",
            "user_prompt": ""
        }

        if not messages or len(messages) < 2:
            return result

        # Extract system prompt
        if messages[0].get("role") == "system":
            result["system_prompt"] = messages[0].get("content", "")

        # Extract user prompt
        user_message_idx = 1 if messages[0].get("role") == "system" else 0
        if len(messages) > user_message_idx and messages[user_message_idx].get("role") == "user":
            user_content = messages[user_message_idx].get("content", "")
            result["user_prompt"] = user_content

            # Parse candidate data from user prompt based on schema type
            if schema_type == "candidate_evaluation":
                result.update(self._parse_candidate_from_prompt(user_content))
            elif schema_type == "cartographer":
                result.update(self._parse_cartographer_from_prompt(user_content))
            elif schema_type == "cv_parsing":
                result.update(self._parse_cv_from_prompt(user_content))
            # Add more schema types as needed

        return result

    def _parse_candidate_from_prompt(self, user_content: str) -> Dict[str, Any]:
        """
        Parse candidate data from user prompt.

        Extracts:
        - Name
        - Current role
        - Location
        - Work history
        - Education
        """
        result = {}

        # Extract name
        name_match = re.search(r"(?:Name|Candidate):\s*(.+?)(?:\n|$)", user_content, re.IGNORECASE)
        if name_match:
            result["name"] = name_match.group(1).strip()

        # Extract role
        role_match = re.search(r"(?:Current Role|Role|Title):\s*(.+?)(?:\n|$)", user_content, re.IGNORECASE)
        if role_match:
            result["role"] = role_match.group(1).strip()

        # Extract location
        location_match = re.search(r"Location:\s*(.+?)(?:\n|$)", user_content, re.IGNORECASE)
        if location_match:
            result["location"] = location_match.group(1).strip()

        # Extract work history (look for section between "Work History:" and next section)
        work_match = re.search(
            r"Work History:\s*(.+?)(?:\n\n|Education:|Skills:|$)",
            user_content,
            re.DOTALL | re.IGNORECASE
        )
        if work_match:
            work_text = work_match.group(1).strip()
            # Split by newlines and filter empty lines
            work_lines = [line.strip() for line in work_text.split("\n") if line.strip()]
            result["work_history"] = work_lines[:10]  # Limit to 10 positions

        # Extract education (look for section after "Education:")
        edu_match = re.search(
            r"Education:\s*(.+?)(?:\n\n|Skills:|$)",
            user_content,
            re.DOTALL | re.IGNORECASE
        )
        if edu_match:
            edu_text = edu_match.group(1).strip()
            # Split by newlines and filter empty lines
            edu_lines = [line.strip() for line in edu_text.split("\n") if line.strip()]
            result["education"] = edu_lines[:5]  # Limit to 5 entries

        return result

    def _parse_cartographer_from_prompt(self, user_content: str) -> Dict[str, Any]:
        """Parse cartographer conquest data from user prompt."""
        # Implement cartographer-specific parsing
        return {}

    def _parse_cv_from_prompt(self, user_content: str) -> Dict[str, Any]:
        """Parse CV parsing conquest data from user prompt."""
        # Implement CV parsing-specific parsing
        return {}

    def export_annotations(
        self,
        project_id: int,
        only_completed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Export annotations from Label Studio.

        Args:
            project_id: Label Studio project ID
            only_completed: Only export completed annotations

        Returns:
            List of exported annotations
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return []

            # Get all tasks with annotations
            tasks = self.client.get_tasks(project_id)

            exported = []
            for task in tasks:
                # Skip if no annotations
                if not task.get('annotations'):
                    continue

                # Skip if not completed (if filter enabled)
                if only_completed and not task.get('is_labeled'):
                    continue

                # Extract annotation data
                for annotation in task['annotations']:
                    exported.append({
                        'task_id': task['id'],
                        'data': task['data'],
                        'annotation': annotation,
                        'created_at': annotation.get('created_at'),
                        'updated_at': annotation.get('updated_at'),
                        'completed_by': annotation.get('completed_by')
                    })

            logger.info(f"Exported {len(exported)} annotations from project {project_id}")
            return exported

        except Exception as e:
            logger.error(f"Error exporting annotations: {e}")
            raise

    def export_curated_data(
        self,
        project_id: int
    ) -> List[Dict[str, Any]]:
        """
        Export curated data in training-ready format.

        Converts Label Studio annotations back to training data format.

        Args:
            project_id: Label Studio project ID

        Returns:
            List of curated training examples
        """
        try:
            annotations = self.export_annotations(project_id, only_completed=True)

            curated = []
            for item in annotations:
                # Extract input data
                input_data = item['data'].get('input', {})

                # Extract corrected/validated output from annotation
                annotation_result = item['annotation'].get('result', [])

                # Reconstruct training example
                example = {
                    'input': input_data,
                    'output': self._reconstruct_output(annotation_result),
                    'metadata': {
                        'task_id': item['task_id'],
                        'annotated_at': item['updated_at'],
                        'annotated_by': item['completed_by']
                    }
                }

                curated.append(example)

            logger.info(f"Exported {len(curated)} curated examples from project {project_id}")
            return curated

        except Exception as e:
            logger.error(f"Error exporting curated data: {e}")
            raise

    def _reconstruct_output(self, annotation_result: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reconstruct output from Label Studio annotation result."""
        output: Dict[str, Any] = {}

        for item in annotation_result:
            from_name = item.get('from_name')
            if from_name is None:
                continue

            value = item.get('value', {})

            # Extract value based on type
            if 'choices' in value:
                output[str(from_name)] = value['choices'][0] if value['choices'] else None
            elif 'rating' in value:
                output[str(from_name)] = value['rating']
            elif 'text' in value:
                output[str(from_name)] = value['text'][0] if value['text'] else None
            elif 'number' in value:
                output[str(from_name)] = value['number']

        return output

    def create_multi_model_task(
        self,
        project_id: int,
        input_data: Dict[str, Any],
        model_responses: Dict[str, str],
        schema_type: str = 'chat_completion'
    ) -> int:
        """
        Create a Label Studio task with predictions from multiple models.

        Useful for comparing model outputs side-by-side.

        Args:
            project_id: Label Studio project ID
            input_data: Input data (prompt, messages, etc.)
            model_responses: Dict mapping model names to their responses
            schema_type: Schema type for parsing

        Returns:
            Task ID
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return 0

            # Create task data with all model responses
            task_data = {
                'input': input_data,
                'models': list(model_responses.keys())
            }

            # Add each model's response as a separate field
            for model_name, response in model_responses.items():
                task_data[f'response_{model_name}'] = response

            # Create task
            task = self.client.create_task(
                project_id=project_id,
                data=task_data
            )

            task_id = task['id']

            # Create predictions for each model
            for model_name, response in model_responses.items():
                # Parse response
                try:
                    if response.strip().startswith('{'):
                        data = json.loads(response)
                    else:
                        # Extract JSON from markdown
                        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
                        if json_match:
                            data = json.loads(json_match.group(1))
                        else:
                            data = {'response': response}
                except json.JSONDecodeError:
                    data = {'response': response}

                # Create prediction
                prediction = self._create_predictions(response, schema_type)

                if prediction:
                    # Add model name to prediction
                    prediction['model_version'] = model_name

                    # Create prediction in Label Studio
                    self.client.create_prediction(
                        task_id=task_id,
                        result=prediction['result'],
                        score=prediction.get('score', 0.5),
                        model_version=model_name
                    )

            logger.info(f"Created multi-model task {task_id} with {len(model_responses)} model predictions")
            task_id_int: int = int(task_id) if isinstance(task_id, (int, str)) else 0
            return task_id_int

        except Exception as e:
            logger.error(f"Error creating multi-model task: {e}")
            raise

    def suggest_next_tasks(
        self,
        project_id: int,
        strategy: str = 'uncertainty',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Active learning: Suggest next tasks to label based on strategy.

        Strategies:
        - uncertainty: Tasks with lowest prediction confidence
        - disagreement: Tasks where models disagree most
        - random: Random unlabeled tasks

        Args:
            project_id: Label Studio project ID
            strategy: Selection strategy
            limit: Number of tasks to suggest

        Returns:
            List of suggested tasks
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return []

            # Get all unlabeled tasks
            tasks = self.client.get_tasks(project_id)
            unlabeled = [t for t in tasks if not t.get('is_labeled')]

            if not unlabeled:
                return []

            # Apply strategy
            if strategy == 'uncertainty':
                # Sort by lowest prediction score
                scored_tasks = []
                for task in unlabeled:
                    predictions = task.get('predictions', [])
                    if predictions:
                        # Get lowest score
                        min_score = min(p.get('score', 1.0) for p in predictions)
                        scored_tasks.append((task, min_score))
                    else:
                        scored_tasks.append((task, 0.0))

                # Sort by score (ascending)
                scored_tasks.sort(key=lambda x: x[1])
                suggested = [t[0] for t in scored_tasks[:limit]]

            elif strategy == 'disagreement':
                # Sort by model disagreement
                scored_tasks = []
                for task in unlabeled:
                    predictions = task.get('predictions', [])
                    if len(predictions) >= 2:
                        # Calculate disagreement (variance in scores)
                        scores = [p.get('score', 0.5) for p in predictions]
                        variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
                        scored_tasks.append((task, variance))
                    else:
                        scored_tasks.append((task, 0.0))

                # Sort by variance (descending)
                scored_tasks.sort(key=lambda x: x[1], reverse=True)
                suggested = [t[0] for t in scored_tasks[:limit]]

            else:  # random
                import random
                suggested = random.sample(unlabeled, min(limit, len(unlabeled)))

            logger.info(f"Suggested {len(suggested)} tasks using {strategy} strategy")
            return suggested

        except Exception as e:
            logger.error(f"Error suggesting tasks: {e}")
            raise

    def get_annotation_quality_metrics(self, project_id: int) -> Dict[str, Any]:
        """
        Calculate annotation quality metrics.

        Metrics:
        - Inter-annotator agreement
        - Annotation speed
        - Completion rate
        - Quality scores

        Args:
            project_id: Label Studio project ID

        Returns:
            Quality metrics
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return {}

            # Get all tasks
            tasks = self.client.get_tasks(project_id)

            total_tasks = len(tasks)
            labeled_tasks = sum(1 for t in tasks if t.get('is_labeled'))
            completion_rate = labeled_tasks / total_tasks if total_tasks > 0 else 0.0

            # Calculate inter-annotator agreement
            # (for tasks with multiple annotations)
            multi_annotated = [t for t in tasks if len(t.get('annotations', [])) >= 2]

            agreement_scores = []
            for task in multi_annotated:
                annotations = task['annotations']
                # Compare first two annotations
                if len(annotations) >= 2:
                    ann1 = annotations[0]['result']
                    ann2 = annotations[1]['result']

                    # Calculate agreement (simple: same number of labels)
                    agreement = 1.0 if len(ann1) == len(ann2) else 0.5
                    agreement_scores.append(agreement)

            avg_agreement = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.0

            # Calculate annotation speed
            annotation_times = []
            for task in tasks:
                for ann in task.get('annotations', []):
                    if ann.get('created_at') and ann.get('updated_at'):
                        from datetime import datetime
                        created = datetime.fromisoformat(ann['created_at'].replace('Z', '+00:00'))
                        updated = datetime.fromisoformat(ann['updated_at'].replace('Z', '+00:00'))
                        duration = (updated - created).total_seconds()
                        if duration > 0:
                            annotation_times.append(duration)

            avg_annotation_time = sum(annotation_times) / len(annotation_times) if annotation_times else 0.0

            return {
                'project_id': project_id,
                'total_tasks': total_tasks,
                'labeled_tasks': labeled_tasks,
                'unlabeled_tasks': total_tasks - labeled_tasks,
                'completion_rate': round(completion_rate, 3),
                'inter_annotator_agreement': round(avg_agreement, 3),
                'avg_annotation_time_seconds': round(avg_annotation_time, 1),
                'multi_annotated_tasks': len(multi_annotated)
            }

        except Exception as e:
            logger.error(f"Error calculating quality metrics: {e}")
            raise

    def bulk_import_tasks(
        self,
        project_id: int,
        tasks_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Bulk import tasks to Label Studio.

        Args:
            project_id: Label Studio project ID
            tasks_data: List of task data dictionaries

        Returns:
            Import results
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return {"created": 0, "errors": ["Client not initialized"]}

            created_tasks = []
            errors = []

            for i, task_data in enumerate(tasks_data):
                try:
                    task = self.client.create_task(
                        project_id=project_id,
                        data=task_data
                    )
                    created_tasks.append(task['id'])
                except Exception as e:
                    errors.append({
                        'index': i,
                        'error': str(e)
                    })

            logger.info(f"Bulk imported {len(created_tasks)} tasks with {len(errors)} errors")

            return {
                'total_attempted': len(tasks_data),
                'successful': len(created_tasks),
                'failed': len(errors),
                'task_ids': created_tasks,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"Error bulk importing tasks: {e}")
            raise

    def mark_ground_truth(self, annotation_id: int, is_ground_truth: bool = True):
        """
        Mark an annotation as ground truth (gold standard).

        Ground truth annotations are used for:
        - Model evaluation (calculate accuracy vs known-good labels)
        - Annotator training (show examples of perfect annotations)
        - Quality metrics (track how well annotators match ground truth)
        - Active learning (prioritize tasks that differ from ground truth)

        Args:
            annotation_id: Label Studio annotation ID
            is_ground_truth: True to mark as ground truth, False to unmark

        Returns:
            Updated annotation data
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return {}

            # Update annotation with ground_truth flag
            annotation = self.client.update_annotation(
                annotation_id=annotation_id,
                ground_truth=is_ground_truth
            )

            logger.info(f"Marked annotation {annotation_id} as ground_truth={is_ground_truth}")
            return annotation

        except Exception as e:
            logger.error(f"Error marking ground truth: {e}")
            raise

    def get_ground_truth_annotations(self, project_id: int):
        """
        Get all ground truth annotations for a project.

        Args:
            project_id: Label Studio project ID

        Returns:
            List of ground truth annotations
        """
        try:
            if not self.client:
                logger.error("Label Studio client not initialized")
                return []

            # Get all annotations for project filtered by ground_truth
            annotations = self.client.get_annotations(
                project_id=project_id,
                filters={'ground_truth': True}
            )

            logger.info(f"Retrieved {len(annotations)} ground truth annotations from project {project_id}")
            return annotations

        except Exception as e:
            logger.error(f"Error getting ground truth annotations: {e}")
            raise

    def calculate_accuracy_vs_ground_truth(self, project_id: int, model_predictions: List[Dict]):
        """
        Calculate model accuracy against ground truth annotations.

        Args:
            project_id: Label Studio project ID
            model_predictions: List of model predictions with format:
                [
                    {
                        "task_id": 123,
                        "prediction": {
                            "recommendation": "yes",
                            "trajectory_rating": "strong",
                            ...
                        }
                    },
                    ...
                ]

        Returns:
            {
                "total_ground_truth": 10,
                "total_predictions": 10,
                "matched": 8,
                "overall_accuracy": 0.85,
                "field_accuracy": {
                    "recommendation": 0.90,
                    "trajectory_rating": 0.80,
                    ...
                },
                "confusion_matrix": {...}
            }
        """
        try:
            ground_truth = self.get_ground_truth_annotations(project_id)

            if not ground_truth:
                return {
                    "error": "No ground truth annotations found",
                    "accuracy": 0.0
                }

            # Build ground truth lookup by task_id
            gt_by_task = {}
            for gt in ground_truth:
                task_id = gt.get('task')
                if task_id:
                    # Extract ground truth values from result
                    result = gt.get('result', [])
                    gt_values = {}
                    for item in result:
                        from_name = item.get('from_name')
                        value = item.get('value', {})

                        if item.get('type') == 'choices':
                            gt_values[from_name] = value.get('choices', [])[0] if value.get('choices') else None
                        elif item.get('type') == 'textarea':
                            gt_values[from_name] = value.get('text', [''])[0] if value.get('text') else None

                    gt_by_task[task_id] = gt_values

            # Match predictions to ground truth
            matched_count = 0
            field_matches = {}
            field_totals = {}

            for pred in model_predictions:
                task_id = pred.get('task_id')
                prediction = pred.get('prediction', {})

                if task_id not in gt_by_task:
                    continue

                matched_count += 1
                gt_values = gt_by_task[task_id]

                # Compare each field
                for field_name, pred_value in prediction.items():
                    if field_name not in field_matches:
                        field_matches[field_name] = 0
                        field_totals[field_name] = 0

                    field_totals[field_name] += 1

                    # Normalize values for comparison (lowercase, strip whitespace)
                    pred_normalized = str(pred_value).lower().strip() if pred_value else ""
                    gt_normalized = str(gt_values.get(field_name, "")).lower().strip()

                    if pred_normalized == gt_normalized:
                        field_matches[field_name] += 1

            # Calculate field-level accuracy
            field_accuracy = {}
            for field_name in field_totals:
                if field_totals[field_name] > 0:
                    field_accuracy[field_name] = field_matches[field_name] / field_totals[field_name]
                else:
                    field_accuracy[field_name] = 0.0

            # Calculate overall accuracy (average of all field accuracies)
            overall_accuracy = sum(field_accuracy.values()) / len(field_accuracy) if field_accuracy else 0.0

            return {
                "total_ground_truth": len(ground_truth),
                "total_predictions": len(model_predictions),
                "matched": matched_count,
                "overall_accuracy": round(overall_accuracy, 3),
                "field_accuracy": {k: round(v, 3) for k, v in field_accuracy.items()},
                "field_totals": field_totals,
                "field_matches": field_matches
            }

        except Exception as e:
            logger.error(f"Error calculating accuracy: {e}")
            raise

