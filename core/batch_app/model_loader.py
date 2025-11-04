"""
vLLM Model Loader - Load fine-tuned models into vLLM for inference.

Provides functionality to:
- Load fine-tuned models into vLLM engine
- Switch between base and fine-tuned models
- Track active model in database
- Manage model lifecycle
"""

import logging
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from vllm import LLM

from core.batch_app.database import FineTunedModel, ModelRegistry, get_db
from core.config import settings

logger = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Raised when model loading fails."""
    pass


class VLLMModelLoader:
    """
    Load and manage fine-tuned models in vLLM.
    
    Architecture:
    - Fine-tuned models stored in data/fine_tuned_models/
    - vLLM loads models from HuggingFace format
    - Model switching requires worker restart
    - Active model tracked in database
    """
    
    def __init__(self):
        self.models_dir = Path("data/fine_tuned_models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def get_model_path(self, model_id: str) -> Path:
        """Get filesystem path for a fine-tuned model."""
        return self.models_dir / model_id
    
    def validate_model_exists(self, model_id: str, db: Session) -> FineTunedModel:
        """
        Validate that a fine-tuned model exists in database.
        
        Args:
            model_id: Fine-tuned model ID
            db: Database session
            
        Returns:
            FineTunedModel record
            
        Raises:
            ModelLoadError: If model not found
        """
        model = db.query(FineTunedModel).filter(
            FineTunedModel.id == model_id
        ).first()
        
        if not model:
            raise ModelLoadError(f"Model {model_id} not found in database")
        
        if model.status != "completed":
            raise ModelLoadError(
                f"Model {model_id} is not ready (status: {model.status})"
            )
        
        return model
    
    def validate_model_files(self, model_path: Path) -> bool:
        """
        Validate that model files exist on disk.
        
        Args:
            model_path: Path to model directory
            
        Returns:
            True if valid, False otherwise
        """
        if not model_path.exists():
            return False
        
        # Check for required files (HuggingFace format)
        required_files = [
            "config.json",
            "tokenizer_config.json"
        ]
        
        # At least one of these should exist
        model_files = [
            "pytorch_model.bin",
            "model.safetensors",
            "adapter_model.bin",  # LoRA adapter
            "adapter_model.safetensors"  # LoRA adapter (safetensors)
        ]
        
        # Check required files
        for file in required_files:
            if not (model_path / file).exists():
                logger.warning(f"Missing required file: {file}")
                return False
        
        # Check at least one model file exists
        has_model_file = any(
            (model_path / file).exists() for file in model_files
        )
        
        if not has_model_file:
            logger.warning("No model weights found")
            return False
        
        return True
    
    def load_model_into_vllm(
        self,
        model_path: str,
        gpu_memory_utilization: float = 0.9,
        max_model_len: Optional[int] = None
    ) -> LLM:
        """
        Load a model into vLLM engine.
        
        Args:
            model_path: Path to model (HuggingFace format or model ID)
            gpu_memory_utilization: GPU memory to use (0.0-1.0)
            max_model_len: Maximum sequence length
            
        Returns:
            vLLM LLM instance
            
        Raises:
            ModelLoadError: If loading fails
        """
        try:
            logger.info(f"Loading model into vLLM: {model_path}")
            
            # Load model with vLLM
            llm = LLM(
                model=model_path,
                gpu_memory_utilization=gpu_memory_utilization,
                max_model_len=max_model_len or 4096,
                trust_remote_code=True,
                dtype="auto"
            )
            
            logger.info(f"Successfully loaded model: {model_path}")
            return llm
            
        except Exception as e:
            logger.error(f"Failed to load model {model_path}: {e}")
            raise ModelLoadError(f"vLLM loading failed: {e}")
    
    def register_model_in_registry(
        self,
        model_id: str,
        model_name: str,
        base_model: str,
        db: Session
    ) -> ModelRegistry:
        """
        Register fine-tuned model in model registry.
        
        This makes the model available for inference via the batch API.
        
        Args:
            model_id: Fine-tuned model ID
            model_name: Display name
            base_model: Base model ID
            db: Database session
            
        Returns:
            ModelRegistry record
        """
        # Check if already registered
        existing = db.query(ModelRegistry).filter(
            ModelRegistry.model_id == model_id
        ).first()
        
        if existing:
            logger.info(f"Model {model_id} already in registry")
            return existing
        
        # Create registry entry
        registry_entry = ModelRegistry(
            model_id=model_id,
            name=model_name,
            size_gb=0.0,  # Will be calculated later
            status="ready",
            rtx4080_compatible=True,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(registry_entry)
        db.commit()
        db.refresh(registry_entry)
        
        logger.info(f"Registered model {model_id} in registry")
        return registry_entry
    
    def deploy_fine_tuned_model(
        self,
        model_id: str,
        deployment_config: Optional[dict] = None
    ) -> dict:
        """
        Deploy a fine-tuned model for inference.
        
        Steps:
        1. Validate model exists in database
        2. Validate model files on disk
        3. Register in model registry
        4. Update deployment status
        
        Note: Actual vLLM loading happens in worker when job is processed.
        Worker will detect the model in registry and load it.
        
        Args:
            model_id: Fine-tuned model ID
            deployment_config: Optional deployment configuration
            
        Returns:
            Deployment status dict
            
        Raises:
            ModelLoadError: If deployment fails
        """
        db = next(get_db())
        
        try:
            # Step 1: Validate model in database
            model = self.validate_model_exists(model_id, db)
            logger.info(f"Validated model {model_id} in database")
            
            # Step 2: Validate model files
            model_path = self.get_model_path(model_id)
            if not self.validate_model_files(model_path):
                raise ModelLoadError(
                    f"Model files not found or invalid at {model_path}"
                )
            logger.info(f"Validated model files at {model_path}")
            
            # Step 3: Register in model registry
            registry_entry = self.register_model_in_registry(
                model_id=model_id,
                model_name=model.name,
                base_model=model.base_model,
                db=db
            )
            
            # Step 4: Update deployment status
            model.status = "deployed"
            model.deployed_at = datetime.now(timezone.utc)
            if deployment_config:
                model.deployment_config = deployment_config
            
            db.commit()
            
            logger.info(f"Successfully deployed model {model_id}")
            
            return {
                "status": "deployed",
                "model_id": model_id,
                "model_path": str(model_path),
                "registry_id": registry_entry.model_id,
                "message": "Model deployed successfully. Worker will load it on next job."
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Deployment failed for {model_id}: {e}")
            raise ModelLoadError(f"Deployment failed: {e}")
    
    def get_active_model(self, db: Session) -> Optional[str]:
        """
        Get the currently active model ID.
        
        Returns:
            Model ID or None if no model active
        """
        from core.batch_app.database import WorkerHeartbeat
        
        heartbeat = db.query(WorkerHeartbeat).filter(
            WorkerHeartbeat.id == 1
        ).first()
        
        if heartbeat and heartbeat.loaded_model:
            return heartbeat.loaded_model
        
        return None
    
    def list_available_models(self, db: Session) -> list[dict]:
        """
        List all available models (base + fine-tuned).
        
        Returns:
            List of model dicts with metadata
        """
        models = []
        
        # Get base models from registry
        base_models = db.query(ModelRegistry).filter(
            ModelRegistry.status == "ready"
        ).all()
        
        for model in base_models:
            models.append({
                "id": model.model_id,
                "name": model.name,
                "type": "base",
                "status": model.status,
                "size_gb": model.size_gb
            })
        
        # Get fine-tuned models
        fine_tuned = db.query(FineTunedModel).filter(
            FineTunedModel.status.in_(["completed", "deployed"])
        ).all()
        
        for model in fine_tuned:
            models.append({
                "id": model.id,
                "name": model.name,
                "type": "fine_tuned",
                "base_model": model.base_model,
                "status": model.status,
                "version": model.version,
                "win_rate": float(model.win_rate) if model.win_rate else None,
                "deployed_at": model.deployed_at.isoformat() if model.deployed_at else None
            })
        
        return models


# Global instance
model_loader = VLLMModelLoader()

