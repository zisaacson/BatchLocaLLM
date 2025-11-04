"""
Abstract base class for fine-tuning backends.

Provides a unified interface for different training frameworks:
- Unsloth: Fast LoRA/QLoRA training (2x faster than HuggingFace)
- Axolotl: Flexible training with many options
- OpenAI: Cloud-based fine-tuning
- HuggingFace: Standard transformers training
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class BackendType(str, Enum):
    """Supported training backends."""
    UNSLOTH = "unsloth"
    AXOLOTL = "axolotl"
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"


class TrainingStatus(str, Enum):
    """Training job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingConfig:
    """Training configuration."""
    
    # Model
    base_model: str
    output_dir: Path
    
    # Dataset
    dataset_path: Path
    validation_split: float = 0.1
    
    # Training hyperparameters
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-4
    warmup_steps: int = 10
    max_seq_length: int = 2048
    
    # LoRA/QLoRA parameters
    use_lora: bool = True
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    use_qlora: bool = False  # 4-bit quantization
    
    # Optimization
    gradient_accumulation_steps: int = 4
    gradient_checkpointing: bool = True
    fp16: bool = True
    bf16: bool = False
    
    # Logging
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    
    # Advanced
    seed: int = 42
    max_grad_norm: float = 1.0
    weight_decay: float = 0.01
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'base_model': self.base_model,
            'output_dir': str(self.output_dir),
            'dataset_path': str(self.dataset_path),
            'validation_split': self.validation_split,
            'num_epochs': self.num_epochs,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'warmup_steps': self.warmup_steps,
            'max_seq_length': self.max_seq_length,
            'use_lora': self.use_lora,
            'lora_r': self.lora_r,
            'lora_alpha': self.lora_alpha,
            'lora_dropout': self.lora_dropout,
            'use_qlora': self.use_qlora,
            'gradient_accumulation_steps': self.gradient_accumulation_steps,
            'gradient_checkpointing': self.gradient_checkpointing,
            'fp16': self.fp16,
            'bf16': self.bf16,
            'logging_steps': self.logging_steps,
            'save_steps': self.save_steps,
            'eval_steps': self.eval_steps,
            'seed': self.seed,
            'max_grad_norm': self.max_grad_norm,
            'weight_decay': self.weight_decay
        }


@dataclass
class TrainingMetrics:
    """Training metrics snapshot."""
    
    # Progress
    current_epoch: int
    total_epochs: int
    current_step: int
    total_steps: int
    progress: float  # 0-100
    
    # Loss
    training_loss: float | None = None
    validation_loss: float | None = None
    
    # Learning rate
    learning_rate: float | None = None
    
    # Timing
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    
    # Throughput
    samples_per_second: float | None = None
    tokens_per_second: float | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'current_epoch': self.current_epoch,
            'total_epochs': self.total_epochs,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'progress': self.progress,
            'training_loss': self.training_loss,
            'validation_loss': self.validation_loss,
            'learning_rate': self.learning_rate,
            'elapsed_seconds': self.elapsed_seconds,
            'estimated_remaining_seconds': self.estimated_remaining_seconds,
            'samples_per_second': self.samples_per_second,
            'tokens_per_second': self.tokens_per_second
        }


class FineTuningBackend(ABC):
    """
    Abstract base class for fine-tuning backends.
    
    Implementations must provide:
    - Training script generation
    - Job submission
    - Progress monitoring
    - Model export
    """
    
    def __init__(self, backend_type: BackendType):
        """Initialize backend."""
        self.backend_type = backend_type
    
    @abstractmethod
    def validate_config(self, config: TrainingConfig) -> tuple[bool, str | None]:
        """
        Validate training configuration.
        
        Returns:
            (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def prepare_training(self, config: TrainingConfig) -> Path:
        """
        Prepare training environment and scripts.
        
        Returns:
            Path to training script
        """
        pass
    
    @abstractmethod
    def start_training(self, script_path: Path) -> str:
        """
        Start training job.
        
        Returns:
            Job ID for monitoring
        """
        pass
    
    @abstractmethod
    def get_status(self, job_id: str) -> TrainingStatus:
        """Get current training status."""
        pass
    
    @abstractmethod
    def get_metrics(self, job_id: str) -> TrainingMetrics | None:
        """Get current training metrics."""
        pass
    
    @abstractmethod
    def cancel_training(self, job_id: str) -> bool:
        """
        Cancel training job.
        
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    def export_model(self, job_id: str, output_path: Path) -> bool:
        """
        Export trained model.
        
        Returns:
            True if exported successfully
        """
        pass
    
    @abstractmethod
    def cleanup(self, job_id: str) -> None:
        """Clean up training artifacts."""
        pass
    
    def get_logs(self, job_id: str) -> str | None:
        """
        Get training logs.
        
        Optional method - backends can override if they support log retrieval.
        """
        return None

