"""
Label Studio API Client

Wrapper around Label Studio REST API for task/annotation management.
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings

logger = logging.getLogger(__name__)


class LabelStudioClient:
    """Client for Label Studio API with connection pooling and retry logic"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.LABEL_STUDIO_URL).rstrip('/')
        self.api_key = api_key or settings.LABEL_STUDIO_API_KEY

        # Create session with connection pooling
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=settings.LABEL_STUDIO_MAX_RETRIES,
            backoff_factor=settings.LABEL_STUDIO_RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP codes
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )

        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=settings.LABEL_STUDIO_POOL_CONNECTIONS,
            pool_maxsize=settings.LABEL_STUDIO_POOL_MAXSIZE
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default timeout
        self.timeout = settings.LABEL_STUDIO_TIMEOUT

        # Set authorization header
        if self.api_key:
            self.session.headers.update({
                'Authorization': f'Token {self.api_key}'
            })

    def create_project(self, title: str, description: str = "", label_config: str = "") -> dict[str, Any]:
        """Create a new Label Studio project"""
        response = self.session.post(
            f"{self.base_url}/api/projects",
            json={
                "title": title,
                "description": description,
                "label_config": label_config
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_project(self, project_id: int) -> dict[str, Any]:
        """Get project details"""
        response = self.session.get(
            f"{self.base_url}/api/projects/{project_id}",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def create_task(
        self,
        project_id: int,
        data: dict[str, Any],
        predictions: (list[dict[str, Any]]) | None = None,
        meta: (dict[str, Any]) | None = None
    ) -> dict[str, Any]:
        """
        Create a task with optional LLM predictions
        
        Args:
            project_id: Label Studio project ID
            data: Task data (candidate info, etc.)
            predictions: LLM predictions to pre-fill
            meta: Additional metadata
        
        Returns:
            Created task object
        """
        task_data = {
            "data": data,
            "project": project_id
        }

        if predictions:
            task_data["predictions"] = predictions

        if meta:
            task_data["meta"] = meta

        response = self.session.post(
            f"{self.base_url}/api/tasks",
            json=task_data,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id: int) -> dict[str, Any]:
        """Get task by ID"""
        response = self.session.get(
            f"{self.base_url}/api/tasks/{task_id}",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_tasks(
        self,
        project_id: int,
        filters: (dict[str, Any]) | None = None,
        page: int = 1,
        page_size: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get tasks with optional filters
        
        Args:
            project_id: Project ID
            filters: Filter criteria (e.g., {"agreement_score__gte": 0.8})
            page: Page number
            page_size: Results per page
        
        Returns:
            List of tasks
        """
        params = {
            "project": project_id,
            "page": page,
            "page_size": page_size
        }

        if filters:
            params.update(filters)

        response = self.session.get(
            f"{self.base_url}/api/tasks",
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def create_annotation(
        self,
        task_id: int,
        result: list[dict[str, Any]],
        completed_by: (int) | None = None,
        lead_time: (float) | None = None
    ) -> dict[str, Any]:
        """
        Create an annotation (human's response)
        
        Args:
            task_id: Task ID
            result: Annotation result
            completed_by: User ID who completed it
            lead_time: Time spent in seconds
        
        Returns:
            Created annotation object
        """
        annotation_data = {
            "task": task_id,
            "result": result,
            "was_cancelled": False
        }

        if completed_by:
            annotation_data["completed_by"] = completed_by

        if lead_time:
            annotation_data["lead_time"] = lead_time

        response = self.session.post(
            f"{self.base_url}/api/annotations",
            json=annotation_data,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def get_annotations(self, task_id: int) -> list[dict[str, Any]]:
        """Get all annotations for a task"""
        response = self.session.get(
            f"{self.base_url}/api/tasks/{task_id}/annotations",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def update_annotation(
        self,
        annotation_id: int,
        result: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Update an existing annotation"""
        response = self.session.patch(
            f"{self.base_url}/api/annotations/{annotation_id}",
            json={"result": result},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def update_task(
        self,
        task_id: int,
        data: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Update a task's data or metadata"""
        update_payload = {}
        if data is not None:
            update_payload['data'] = data
        if meta is not None:
            update_payload['meta'] = meta

        response = self.session.patch(
            f"{self.base_url}/api/tasks/{task_id}",
            json=update_payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def delete_task(self, task_id: int) -> None:
        """Delete a task"""
        response = self.session.delete(
            f"{self.base_url}/api/tasks/{task_id}",
            timeout=self.timeout
        )
        response.raise_for_status()

    def export_tasks(
        self,
        project_id: int,
        export_type: str = "JSON",
        filters: (dict[str, Any]) | None = None
    ) -> list[dict[str, Any]]:
        """
        Export tasks in various formats
        
        Args:
            project_id: Project ID
            export_type: Export format (JSON, CSV, COCO, etc.)
            filters: Filter criteria
        
        Returns:
            Exported data
        """
        params = {"exportType": export_type}

        if filters:
            params.update(filters)

        response = self.session.get(
            f"{self.base_url}/api/projects/{project_id}/export",
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def calculate_agreement(
        self,
        task_id: int,
        prediction_result: dict[str, Any],
        annotation_result: dict[str, Any]
    ) -> float:
        """
        Calculate agreement score between LLM prediction and human annotation
        
        Returns:
            Agreement score (0.0 to 1.0)
        """
        # Simple agreement: count matching fields
        matches = 0
        total = 0

        for key in prediction_result:
            if key in annotation_result:
                total += 1
                if prediction_result[key] == annotation_result[key]:
                    matches += 1

        return matches / total if total > 0 else 0.0

    def get_gold_star_tasks(
        self,
        project_id: int,
        min_agreement: float = 0.8,
        min_annotations: int = 1
    ) -> list[dict[str, Any]]:
        """
        Get high-quality tasks for training data

        Returns tasks that are either:
        1. Manually marked as gold-star (meta.gold_star = True), OR
        2. Have high agreement between LLM prediction and human annotation

        Args:
            project_id: Project ID
            min_agreement: Minimum agreement score (for automatic gold-star)
            min_annotations: Minimum number of annotations

        Returns:
            List of gold-star tasks with agreement_score field
        """
        all_tasks = self.get_tasks(project_id, page_size=1000)
        gold_star = []

        for task in all_tasks:
            # Check for manual gold-star flag
            meta = task.get('meta', {})
            if meta.get('gold_star') is True:
                # Manually marked as gold-star
                task['agreement_score'] = 1.0  # Perfect score for manual gold-star
                task['gold_star_type'] = 'manual'
                gold_star.append(task)
                continue

            # Check for automatic gold-star (high agreement)
            annotations = task.get('annotations', [])
            predictions = task.get('predictions', [])

            if len(annotations) < min_annotations:
                continue

            if not predictions:
                continue

            # Calculate agreement between first prediction and first annotation
            prediction_result = predictions[0].get('result', {})
            annotation_result = annotations[0].get('result', {})

            agreement = self.calculate_agreement(
                task['id'],
                prediction_result,
                annotation_result
            )

            if agreement >= min_agreement:
                task['agreement_score'] = agreement
                task['gold_star_type'] = 'automatic'
                gold_star.append(task)

        return gold_star

