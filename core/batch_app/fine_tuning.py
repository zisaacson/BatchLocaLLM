"""
Fine-tuning API endpoints.

Provides REST API for:
- Dataset export from gold star examples
- Training job management
- Model deployment
- A/B testing

This is the generic OSS fine-tuning system.
For Aris-specific conquest features, see integrations/aris/
"""

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.batch_app.database import (
    get_db,
    FineTunedModel,
    TrainingJob,
    ModelComparison,
    DeploymentHistory
)
from core.training.dataset_exporter import DatasetExporter
from core.training.unsloth_backend import UnslothBackend
from core.training.base import TrainingConfig, BackendType
from core.config import settings
from core.batch_app.model_loader import model_loader, ModelLoadError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/fine-tuning", tags=["fine-tuning"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ExportDatasetRequest(BaseModel):
    """Request to export gold star dataset."""
    user_email: str = Field(..., description="User email")
    schema_type: str | None = Field(None, description="Optional schema type filter")
    format: str = Field("chatml", description="Export format (chatml, alpaca, openai)")
    limit: int | None = Field(None, description="Optional limit on samples")


class ExportDatasetResponse(BaseModel):
    """Response from dataset export."""
    dataset_path: str
    sample_count: int
    format: str


class CreateTrainingJobRequest(BaseModel):
    """Request to create training job."""
    user_email: str
    base_model: str
    dataset_path: str | None = None  # If None, will export from gold stars
    schema_type: str | None = None
    backend: str = "unsloth"

    # Training config
    num_epochs: int = 3
    batch_size: int = 4
    learning_rate: float = 2e-4
    use_qlora: bool = False


class TrainingJobResponse(BaseModel):
    """Training job response."""
    id: str
    job_id: str
    user_email: str
    base_model: str
    backend: str
    status: str
    progress: float
    current_epoch: int | None
    total_epochs: int | None
    training_loss: float | None
    started_at: str | None
    estimated_completion: str | None
    created_at: str


class DeployModelRequest(BaseModel):
    """Request to deploy model."""
    model_id: str
    deployment_config: dict[str, Any] | None = None
    notes: str | None = None


class CompareModelsRequest(BaseModel):
    """Request to compare models."""
    base_model_id: str | None = None  # If None, use base model
    fine_tuned_model_id: str
    test_prompts: list[str]


class ABTestRequest(BaseModel):
    """Request to run A/B test."""
    base_model_id: str
    fine_tuned_model_id: str
    test_prompts: list[str]


class ABTestVoteRequest(BaseModel):
    """Request to record A/B test vote."""
    comparison_id: str
    winner: str  # 'base', 'fine_tuned', or 'tie'


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/datasets/export", response_model=ExportDatasetResponse)
async def export_dataset(request: ExportDatasetRequest):
    """
    Export gold star examples to training dataset.

    Fetches gold star examples from Label Studio or other data sources
    and exports to specified format (ChatML, Alpaca, or OpenAI).
    """
    try:
        # Get the dataset exporter from registry
        # OSS users: implement DatasetExporter interface for your data source
        # Aris users: use AristotleDatasetExporter from integrations/aris/
        from core.training.dataset_exporter import get_exporter

        exporter = get_exporter()

        output_dir = Path(settings.DATA_DIR) / "training_datasets"
        output_dir.mkdir(parents=True, exist_ok=True)

        dataset_path, sample_count = exporter.export_dataset(
            user_email=request.user_email,
            output_dir=output_dir,
            format=request.format,
            schema_type=request.schema_type,
            limit=request.limit
        )

        logger.info(f"Exported {sample_count} samples to {dataset_path}")

        return ExportDatasetResponse(
            dataset_path=str(dataset_path),
            sample_count=sample_count,
            format=request.format
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/jobs", response_model=TrainingJobResponse)
async def create_training_job(request: CreateTrainingJobRequest):
    """
    Create new training job.

    If dataset_path is not provided, will automatically export
    gold star examples for the user.
    """
    try:
        db = next(get_db())

        # Export dataset if not provided
        if not request.dataset_path:
            from core.training.dataset_exporter import get_exporter

            exporter = get_exporter()
            output_dir = Path(settings.DATA_DIR) / "training_datasets"
            output_dir.mkdir(parents=True, exist_ok=True)

            dataset_path, sample_count = exporter.export_dataset(
                user_email=request.user_email,
                output_dir=output_dir,
                format="chatml",
                schema_type=request.schema_type
            )
        else:
            dataset_path = Path(request.dataset_path)
            # Count samples
            with open(dataset_path) as f:
                sample_count = sum(1 for _ in f)
        
        # Create training config
        output_dir = Path(settings.DATA_DIR) / "fine_tuned_models" / f"ft_{int(datetime.now().timestamp())}"
        
        config = TrainingConfig(
            base_model=request.base_model,
            output_dir=output_dir,
            dataset_path=dataset_path,
            num_epochs=request.num_epochs,
            batch_size=request.batch_size,
            learning_rate=request.learning_rate,
            use_qlora=request.use_qlora
        )
        
        # Initialize backend
        backend = UnslothBackend()
        
        # Validate config
        is_valid, error = backend.validate_config(config)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # Prepare training
        script_path = backend.prepare_training(config)
        
        # Start training
        job_id = backend.start_training(script_path)
        
        # Create database record
        training_job = TrainingJob(
            id=str(uuid.uuid4()),
            job_id=job_id,
            user_email=request.user_email,
            domain="default",  # Generic placeholder - Aris integration can override
            base_model=request.base_model,
            backend=request.backend,
            config=config.to_dict(),
            dataset_path=str(dataset_path),
            sample_count=sample_count,
            dataset_types=[request.schema_type] if request.schema_type else None,
            status="running",
            progress=0,
            total_epochs=request.num_epochs,
            started_at=datetime.now(timezone.utc)
        )
        
        db.add(training_job)
        db.commit()
        db.refresh(training_job)
        
        logger.info(f"Created training job {training_job.id}")
        
        return TrainingJobResponse(**training_job.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating training job: {e}")
        raise HTTPException(status_code=500, detail=f"Job creation failed: {str(e)}")


@router.get("/jobs/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(job_id: str):
    """Get training job status and metrics."""
    try:
        db = next(get_db())
        
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Update status from backend
        backend = UnslothBackend()
        status = backend.get_status(job.job_id)
        metrics = backend.get_metrics(job.job_id)
        
        if metrics:
            job.progress = metrics.progress
            job.current_epoch = metrics.current_epoch
            job.training_loss = metrics.training_loss
            job.learning_rate = metrics.learning_rate
        
        job.status = status.value
        
        if status.value == "completed" and not job.completed_at:
            job.completed_at = datetime.now(timezone.utc)
        
        db.commit()
        db.refresh(job)
        
        return TrainingJobResponse(**job.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting training job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/cancel")
async def cancel_training_job(job_id: str):
    """Cancel training job."""
    try:
        db = next(get_db())
        
        job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        backend = UnslothBackend()
        success = backend.cancel_training(job.job_id)
        
        if success:
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
            return {"status": "cancelled", "job_id": job_id}
        else:
            raise HTTPException(status_code=500, detail="Failed to cancel job")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models(philosopher: str, domain: str):
    """List all fine-tuned models for user."""
    try:
        db = next(get_db())
        
        models = db.query(FineTunedModel).filter(
            FineTunedModel.philosopher == philosopher,
            FineTunedModel.domain == domain
        ).order_by(FineTunedModel.created_at.desc()).all()
        
        return [model.to_dict() for model in models]
    
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/deploy")
async def deploy_model(model_id: str, request: DeployModelRequest):
    """
    Deploy fine-tuned model to vLLM.

    This makes the model available for inference by:
    1. Validating model files exist
    2. Registering in model registry
    3. Updating deployment status
    4. Creating deployment history

    The vLLM worker will automatically load the model when processing jobs.
    """
    try:
        db = next(get_db())

        model = db.query(FineTunedModel).filter(FineTunedModel.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")

        # Deploy model using model loader
        try:
            deployment_result = model_loader.deploy_fine_tuned_model(
                model_id=model_id,
                deployment_config=request.deployment_config
            )
        except ModelLoadError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Create deployment history record
        deployment = DeploymentHistory(
            id=str(uuid.uuid4()),
            model_id=model_id,
            philosopher=model.philosopher,
            domain=model.domain,
            action="deploy",
            deployment_config=request.deployment_config,
            deployed_by=model.philosopher,
            notes=request.notes
        )

        db.add(deployment)
        db.commit()

        logger.info(f"Deployed model {model_id}")

        return {
            "status": "deployed",
            "model_id": model_id,
            "message": deployment_result.get("message"),
            "model_path": deployment_result.get("model_path")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deploying model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ab-test")
async def run_ab_test(request: ABTestRequest):
    """
    Run A/B test between base and fine-tuned model.

    Returns comparison ID and test results.
    """
    try:
        db = next(get_db())

        # Get fine-tuned model
        fine_tuned_model = db.query(FineTunedModel).filter(
            FineTunedModel.id == request.fine_tuned_model_id
        ).first()

        if not fine_tuned_model:
            raise HTTPException(status_code=404, detail="Fine-tuned model not found")

        # Create comparison record
        comparison = ModelComparison(
            id=str(uuid.uuid4()),
            base_model_id=request.base_model_id,
            fine_tuned_model_id=request.fine_tuned_model_id,
            philosopher=fine_tuned_model.philosopher,
            domain=fine_tuned_model.domain,
            test_prompts=request.test_prompts,
            base_wins=0,
            fine_tuned_wins=0,
            ties=0
        )

        db.add(comparison)
        db.commit()
        db.refresh(comparison)

        logger.info(f"Created A/B test comparison {comparison.id}")

        return {
            "comparison_id": comparison.id,
            "status": "ready",
            "test_prompts": request.test_prompts,
            "message": "A/B test created. Use the comparison UI to vote on responses."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating A/B test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ab-test/{comparison_id}/vote")
async def record_ab_test_vote(comparison_id: str, request: ABTestVoteRequest):
    """Record vote for A/B test."""
    try:
        db = next(get_db())

        comparison = db.query(ModelComparison).filter(
            ModelComparison.id == comparison_id
        ).first()

        if not comparison:
            raise HTTPException(status_code=404, detail="Comparison not found")

        # Update vote counts
        if request.winner == 'base':
            comparison.base_wins += 1
        elif request.winner == 'fine_tuned':
            comparison.fine_tuned_wins += 1
        elif request.winner == 'tie':
            comparison.ties += 1
        else:
            raise HTTPException(status_code=400, detail="Invalid winner value")

        comparison.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(comparison)

        # Calculate win rate
        total = comparison.base_wins + comparison.fine_tuned_wins + comparison.ties
        win_rate = ((comparison.fine_tuned_wins + 0.5 * comparison.ties) / total * 100) if total > 0 else 0

        return {
            "comparison_id": comparison_id,
            "base_wins": comparison.base_wins,
            "fine_tuned_wins": comparison.fine_tuned_wins,
            "ties": comparison.ties,
            "win_rate": round(win_rate, 2)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording vote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparisons")
async def list_comparisons(philosopher: str, domain: str):
    """List all model comparisons for user."""
    try:
        db = next(get_db())

        comparisons = db.query(ModelComparison).filter(
            ModelComparison.philosopher == philosopher,
            ModelComparison.domain == domain
        ).order_by(ModelComparison.created_at.desc()).all()

        return [comp.to_dict() for comp in comparisons]

    except Exception as e:
        logger.error(f"Error listing comparisons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/available")
async def list_available_models():
    """
    List all available models (base + fine-tuned).

    Returns models that can be used for inference.
    """
    try:
        db = next(get_db())
        models = model_loader.list_available_models(db)
        return {"models": models}

    except Exception as e:
        logger.error(f"Error listing available models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/active")
async def get_active_model():
    """
    Get the currently active model in vLLM worker.

    Returns the model ID that is currently loaded in memory.
    """
    try:
        db = next(get_db())
        active_model = model_loader.get_active_model(db)

        if not active_model:
            return {"active_model": None, "message": "No model currently loaded"}

        return {"active_model": active_model}

    except Exception as e:
        logger.error(f"Error getting active model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

