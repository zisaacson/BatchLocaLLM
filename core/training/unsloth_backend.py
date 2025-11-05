"""
Unsloth training backend implementation.

Provides fast LoRA/QLoRA fine-tuning using Unsloth (2x faster than HuggingFace).
Generates training scripts and monitors progress.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from core.training.base import (
    FineTuningBackend,
    BackendType,
    TrainingConfig,
    TrainingStatus,
    TrainingMetrics
)

logger = logging.getLogger(__name__)


class UnslothBackend(FineTuningBackend):
    """
    Unsloth training backend.
    
    Generates Python training scripts using Unsloth library and
    monitors training progress via log files.
    """
    
    def __init__(self, workspace_dir: Path | None = None):
        """
        Initialize Unsloth backend.
        
        Args:
            workspace_dir: Directory for training scripts and outputs
        """
        super().__init__(BackendType.UNSLOTH)
        self.workspace_dir = workspace_dir or Path("data/training")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Track active jobs
        self.active_jobs: dict[str, dict[str, Any]] = {}
    
    def validate_config(self, config: TrainingConfig) -> tuple[bool, str | None]:
        """Validate training configuration."""
        # Check dataset exists
        if not config.dataset_path.exists():
            return False, f"Dataset not found: {config.dataset_path}"
        
        # Check dataset is not empty
        with open(config.dataset_path) as f:
            first_line = f.readline()
            if not first_line:
                return False, "Dataset is empty"
        
        # Validate hyperparameters
        if config.num_epochs < 1:
            return False, "num_epochs must be >= 1"
        
        if config.batch_size < 1:
            return False, "batch_size must be >= 1"
        
        if config.learning_rate <= 0:
            return False, "learning_rate must be > 0"
        
        return True, None
    
    def prepare_training(self, config: TrainingConfig) -> Path:
        """
        Generate Unsloth training script.
        
        Returns:
            Path to generated training script
        """
        script_path = self.workspace_dir / f"train_{int(time.time())}.py"
        
        # Generate training script
        script_content = self._generate_training_script(config)
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        logger.info(f"Generated training script: {script_path}")
        return script_path
    
    def _generate_training_script(self, config: TrainingConfig) -> str:
        """Generate Unsloth training script content."""
        return f'''#!/usr/bin/env python3
"""
Auto-generated Unsloth training script.
Generated at: {time.strftime("%Y-%m-%d %H:%M:%S")}
"""

import json
import torch
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

# Configuration
BASE_MODEL = "{config.base_model}"
OUTPUT_DIR = "{config.output_dir}"
DATASET_PATH = "{config.dataset_path}"
MAX_SEQ_LENGTH = {config.max_seq_length}
LOAD_IN_4BIT = {str(config.use_qlora).lower()}

# LoRA configuration
LORA_R = {config.lora_r}
LORA_ALPHA = {config.lora_alpha}
LORA_DROPOUT = {config.lora_dropout}

# Training configuration
NUM_EPOCHS = {config.num_epochs}
BATCH_SIZE = {config.batch_size}
GRADIENT_ACCUMULATION_STEPS = {config.gradient_accumulation_steps}
LEARNING_RATE = {config.learning_rate}
WARMUP_STEPS = {config.warmup_steps}

print("🚀 Starting Unsloth fine-tuning...")
print(f"Base model: {{BASE_MODEL}}")
print(f"Dataset: {{DATASET_PATH}}")
print(f"Output: {{OUTPUT_DIR}}")

# Load model with Unsloth
print("\\n📦 Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,  # Auto-detect
    load_in_4bit=LOAD_IN_4BIT,
)

# Add LoRA adapters
print("\\n🔧 Adding LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing=True,
    random_state={config.seed},
)

# Load dataset
print("\\n📊 Loading dataset...")
dataset = load_dataset("json", data_files=str(DATASET_PATH), split="train")
print(f"Dataset size: {{len(dataset)}} samples")

# Format dataset for ChatML
def formatting_func(examples):
    texts = []
    for messages in examples["messages"]:
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(text)
    return {{"text": texts}}

dataset = dataset.map(formatting_func, batched=True)

# Training arguments
print("\\n⚙️  Setting up training...")
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
    learning_rate=LEARNING_RATE,
    warmup_steps=WARMUP_STEPS,
    logging_steps={config.logging_steps},
    save_steps={config.save_steps},
    eval_steps={config.eval_steps},
    fp16={str(config.fp16).lower()},
    bf16={str(config.bf16).lower()},
    optim="adamw_8bit",
    weight_decay={config.weight_decay},
    max_grad_norm={config.max_grad_norm},
    seed={config.seed},
    report_to="none",  # Disable wandb/tensorboard
)

# Create trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    args=training_args,
)

# Train
print("\\n🏋️  Training started...")
print("=" * 60)
trainer.train()
print("=" * 60)
print("\\n✅ Training completed!")

# Save model
print(f"\\n💾 Saving model to {{OUTPUT_DIR}}...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("\\n🎉 Fine-tuning complete!")
print(f"Model saved to: {{OUTPUT_DIR}}")
'''
    
    def start_training(self, script_path: Path) -> str:
        """
        Start training job.
        
        Returns:
            Job ID for monitoring
        """
        job_id = f"unsloth_{int(time.time())}"
        log_path = self.workspace_dir / f"{job_id}.log"
        
        # Start training process
        process = subprocess.Popen(
            ["python", str(script_path)],
            stdout=open(log_path, 'w'),
            stderr=subprocess.STDOUT,
            cwd=str(script_path.parent)
        )
        
        # Track job
        self.active_jobs[job_id] = {
            'process': process,
            'script_path': script_path,
            'log_path': log_path,
            'started_at': time.time(),
            'status': TrainingStatus.RUNNING
        }
        
        logger.info(f"Started training job {job_id} (PID: {process.pid})")
        return job_id
    
    def get_status(self, job_id: str) -> TrainingStatus:
        """Get current training status."""
        if job_id not in self.active_jobs:
            return TrainingStatus.FAILED
        
        job = self.active_jobs[job_id]
        process = job['process']
        
        # Check if process is still running
        if process.poll() is None:
            return TrainingStatus.RUNNING
        
        # Process finished - check exit code
        if process.returncode == 0:
            job['status'] = TrainingStatus.COMPLETED
            return TrainingStatus.COMPLETED
        else:
            job['status'] = TrainingStatus.FAILED
            return TrainingStatus.FAILED
    
    def get_metrics(self, job_id: str) -> TrainingMetrics | None:
        """Get current training metrics from log file."""
        if job_id not in self.active_jobs:
            return None
        
        job = self.active_jobs[job_id]
        log_path = job['log_path']
        
        if not log_path.exists():
            return None
        
        # Parse log file for metrics
        # This is a simplified version - real implementation would parse
        # actual training logs for loss, epoch, step, etc.
        try:
            with open(log_path) as f:
                lines = f.readlines()
            
            # Look for training progress in logs
            # Format: "{'loss': 0.234, 'learning_rate': 2e-4, 'epoch': 1.5}"
            current_epoch = 0
            current_step = 0
            training_loss = None
            learning_rate = None
            
            for line in reversed(lines[-100:]):  # Check last 100 lines
                if "'epoch':" in line:
                    try:
                        # Extract epoch from log line
                        import re
                        match = re.search(r"'epoch':\s*([\d.]+)", line)
                        if match:
                            current_epoch = int(float(match.group(1)))
                        
                        match = re.search(r"'loss':\s*([\d.]+)", line)
                        if match:
                            training_loss = float(match.group(1))
                        
                        match = re.search(r"'learning_rate':\s*([\d.e-]+)", line)
                        if match:
                            learning_rate = float(match.group(1))
                        
                        break
                    except:
                        pass
            
            elapsed = time.time() - job['started_at']
            
            return TrainingMetrics(
                current_epoch=current_epoch,
                total_epochs=3,  # From config
                current_step=current_step,
                total_steps=100,  # Estimate
                progress=min(100, (current_epoch / 3) * 100),
                training_loss=training_loss,
                validation_loss=None,
                learning_rate=learning_rate,
                elapsed_seconds=elapsed,
                estimated_remaining_seconds=None,
                samples_per_second=None,
                tokens_per_second=None
            )
        except Exception as e:
            logger.error(f"Error parsing metrics: {e}")
            return None
    
    def cancel_training(self, job_id: str) -> bool:
        """Cancel training job."""
        if job_id not in self.active_jobs:
            return False
        
        job = self.active_jobs[job_id]
        process = job['process']
        
        try:
            process.terminate()
            process.wait(timeout=10)
            job['status'] = TrainingStatus.CANCELLED
            logger.info(f"Cancelled training job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False
    
    def export_model(self, job_id: str, output_path: Path) -> bool:
        """Export trained model (already saved during training)."""
        # Unsloth saves model during training, so just verify it exists
        if output_path.exists():
            logger.info(f"Model already exported to {output_path}")
            return True
        return False
    
    def cleanup(self, job_id: str) -> None:
        """Clean up training artifacts."""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            
            # Remove from active jobs
            del self.active_jobs[job_id]
            
            logger.info(f"Cleaned up job {job_id}")
    
    def get_logs(self, job_id: str) -> str | None:
        """Get training logs."""
        if job_id not in self.active_jobs:
            return None
        
        job = self.active_jobs[job_id]
        log_path = job['log_path']
        
        if not log_path.exists():
            return None
        
        with open(log_path) as f:
            return f.read()

