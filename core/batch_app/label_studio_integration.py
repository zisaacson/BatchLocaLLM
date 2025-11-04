"""
Label Studio Integration for Pre-labeling and Active Learning

Features:
1. Pre-labeling: Auto-populate Label Studio tasks with model predictions
2. Active Learning: Surface uncertain examples for human review
3. Export: Export curated datasets in Label Studio format
"""

import json
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


class LabelStudioClient:
    """Client for Label Studio API integration."""

    def __init__(self, base_url: str = "http://localhost:4115", api_key: Optional[str] = None):
        """
        Initialize Label Studio client.

        Args:
            base_url: Label Studio server URL
            api_key: API key for authentication (optional for local dev)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers['Authorization'] = f'Token {api_key}'

    def create_project(self, name: str, description: str, label_config: str) -> Dict[str, Any]:
        """
        Create a new Label Studio project.

        Args:
            name: Project name
            description: Project description
            label_config: Label Studio XML configuration

        Returns:
            Project metadata
        """
        response = requests.post(
            f"{self.base_url}/api/projects",
            headers=self.headers,
            json={
                "title": name,
                "description": description,
                "label_config": label_config
            }
        )
        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result

    def import_tasks(self, project_id: int, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Import tasks into a Label Studio project.

        Args:
            project_id: Label Studio project ID
            tasks: List of tasks to import

        Returns:
            Import result metadata
        """
        response = requests.post(
            f"{self.base_url}/api/projects/{project_id}/import",
            headers=self.headers,
            json=tasks
        )
        response.raise_for_status()
        result: Dict[str, Any] = response.json()
        return result

    def create_prediction(
        self,
        task_id: int,
        result: List[Dict[str, Any]],
        score: Optional[float] = None,
        model_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a prediction (pre-label) for a task.

        Args:
            task_id: Label Studio task ID
            result: Prediction result in Label Studio format
            score: Confidence score (0-1)
            model_version: Model version that generated prediction

        Returns:
            Prediction metadata
        """
        payload = {
            "task": task_id,
            "result": result
        }
        if score is not None:
            payload["score"] = score
        if model_version:
            payload["model_version"] = model_version

        response = requests.post(
            f"{self.base_url}/api/predictions",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        prediction_result: Dict[str, Any] = response.json()
        return prediction_result

    def get_tasks(self, project_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Get tasks from a project.

        Args:
            project_id: Label Studio project ID
            filters: Optional filters (e.g., {"completed": False})

        Returns:
            List of tasks
        """
        params = filters or {}
        response = requests.get(
            f"{self.base_url}/api/projects/{project_id}/tasks",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        result: List[Dict[str, Any]] = response.json()
        return result

    def export_annotations(self, project_id: int, export_type: str = "JSON") -> List[Dict[str, Any]]:
        """
        Export annotations from a project.

        Args:
            project_id: Label Studio project ID
            export_type: Export format (JSON, CSV, etc.)

        Returns:
            Exported annotations
        """
        response = requests.get(
            f"{self.base_url}/api/projects/{project_id}/export",
            headers=self.headers,
            params={"exportType": export_type}
        )
        response.raise_for_status()
        result: List[Dict[str, Any]] = response.json()
        return result


def create_candidate_evaluation_task(
    candidate_id: str,
    candidate_data: Dict[str, Any],
    model_prediction: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a Label Studio task for candidate evaluation.

    Args:
        candidate_id: Unique candidate ID
        candidate_data: Candidate information (name, title, company, etc.)
        model_prediction: Optional model prediction to pre-populate

    Returns:
        Label Studio task format
    """
    task: Dict[str, Any] = {
        "data": {
            "candidate_id": candidate_id,
            "name": candidate_data.get("name", ""),
            "title": candidate_data.get("title", ""),
            "company": candidate_data.get("company", ""),
            "experience": candidate_data.get("experience", ""),
            "education": candidate_data.get("education", "")
        }
    }

    # Add pre-labeling if model prediction provided
    if model_prediction:
        predictions_list: List[Dict[str, Any]] = [
            {
                "result": [
                    {
                        "from_name": "recommendation",
                        "to_name": "candidate",
                        "type": "choices",
                    "value": {
                        "choices": [model_prediction.get("recommendation", "Maybe")]
                    }
                },
                {
                    "from_name": "trajectory_rating",
                    "to_name": "candidate",
                    "type": "rating",
                    "value": {
                        "rating": model_prediction.get("trajectory_rating", 3)
                    }
                },
                {
                    "from_name": "company_pedigree",
                    "to_name": "candidate",
                    "type": "rating",
                    "value": {
                        "rating": model_prediction.get("company_pedigree", 3)
                    }
                },
                {
                    "from_name": "educational_pedigree",
                    "to_name": "candidate",
                    "type": "rating",
                    "value": {
                        "rating": model_prediction.get("educational_pedigree", 3)
                    }
                }
            ],
            "score": model_prediction.get("confidence", 0.5),
            "model_version": model_prediction.get("model_name", "unknown")
        }]
        task["predictions"] = predictions_list

    return task


def calculate_uncertainty_score(model_outputs: List[Dict[str, Any]]) -> float:
    """
    Calculate uncertainty score for active learning.

    Uses disagreement between models as a proxy for uncertainty.
    Higher score = more uncertain = should be reviewed by human.

    Args:
        model_outputs: List of model predictions for same candidate

    Returns:
        Uncertainty score (0-1, higher = more uncertain)
    """
    if len(model_outputs) < 2:
        return 0.0

    # Count disagreements across different fields
    disagreements = 0
    total_comparisons = 0

    fields = ["recommendation", "trajectory_rating", "company_pedigree", "educational_pedigree"]

    for field in fields:
        values = [output.get(field) for output in model_outputs if field in output]
        if len(values) < 2:
            continue

        # Count unique values
        unique_values = len(set(str(v) for v in values))
        if unique_values > 1:
            disagreements += 1
        total_comparisons += 1

    if total_comparisons == 0:
        return 0.0

    return disagreements / total_comparisons


def select_tasks_for_review(
    results: List[Dict[str, Any]],
    max_tasks: int = 100,
    strategy: str = "uncertainty"
) -> List[Dict[str, Any]]:
    """
    Select tasks for human review using active learning.

    Args:
        results: List of candidate results with model outputs
        max_tasks: Maximum number of tasks to select
        strategy: Selection strategy ("uncertainty", "random", "disagreement")

    Returns:
        Selected tasks sorted by priority
    """
    if strategy == "uncertainty":
        # Calculate uncertainty for each result
        scored_results = []
        for result in results:
            model_outputs = result.get("model_outputs", [])
            uncertainty = calculate_uncertainty_score(model_outputs)
            scored_results.append({
                "result": result,
                "score": uncertainty
            })

        # Sort by uncertainty (highest first)
        def get_score(item: Dict[str, Any]) -> float:
            score = item.get("score", 0.0)
            return float(score) if isinstance(score, (int, float, str)) else 0.0

        scored_results.sort(key=get_score, reverse=True)

        # Return top N
        results_list: List[Dict[str, Any]] = []
        for item in scored_results[:max_tasks]:
            result_item = item.get("result")
            if isinstance(result_item, dict):
                results_list.append(result_item)
        return results_list

    elif strategy == "random":
        import random
        return random.sample(results, min(max_tasks, len(results)))

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def export_golden_dataset(
    annotations: List[Dict[str, Any]],
    output_path: Path,
    format: str = "jsonl"
) -> None:
    """
    Export golden dataset for training.

    Args:
        annotations: List of annotated examples
        output_path: Output file path
        format: Export format ("jsonl", "json")
    """
    if format == "jsonl":
        with open(output_path, "w") as f:
            for annotation in annotations:
                f.write(json.dumps(annotation) + "\n")
    elif format == "json":
        with open(output_path, "w") as f:
            json.dump(annotations, f, indent=2)
    else:
        raise ValueError(f"Unknown format: {format}")

    logger.info(f"Exported {len(annotations)} golden examples to {output_path}")

