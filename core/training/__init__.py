"""
Fine-tuning training abstraction layer.

Provides backend-agnostic interface for model fine-tuning with support for:
- Unsloth (fast LoRA/QLoRA training)
- Axolotl (flexible training framework)
- OpenAI (cloud fine-tuning)
- HuggingFace (standard transformers)
"""

from core.training.base import (
    FineTuningBackend,
    TrainingConfig,
    TrainingStatus,
    TrainingMetrics,
    BackendType
)
from core.training.dataset_exporter import DatasetExporter
from core.training.metrics import MetricsCalculator

__all__ = [
    'FineTuningBackend',
    'TrainingConfig',
    'TrainingStatus',
    'TrainingMetrics',
    'BackendType',
    'DatasetExporter',
    'MetricsCalculator'
]

