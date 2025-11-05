"""
Curation API Server

FastAPI backend for the unified dataset curation system.
Integrates Label Studio backend with vLLM batch server.

This is the generic OSS curation API that works with any schema type.
For Aris-specific schema features, see integrations/aris/
"""

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import settings

from .schemas import TaskSchema
from . import get_registry
from .label_studio_client import LabelStudioClient

# Get the directory where this file is located
CURRENT_DIR = Path(__file__).parent
# Static files are in the root static/ directory (two levels up from core/curation/)
STATIC_DIR = CURRENT_DIR.parent.parent / "static"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Dataset Curation API",
    description="Beautiful web interface for curating datasets and managing models",
    version=settings.APP_VERSION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Initialize clients (uses settings from config)
label_studio = LabelStudioClient()

schema_registry = get_registry()


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health")
async def health():
    """Basic health check - returns 200 if service is running"""
    return {
        "status": "healthy",
        "service": "curation-api",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(UTC).isoformat()
    }


@app.get("/ready")
async def ready():
    """Readiness check - verifies Label Studio connection"""
    try:
        # Try to connect to Label Studio
        # This will raise an exception if Label Studio is not available
        response = label_studio.session.get(
            f"{label_studio.base_url}/api/health",
            timeout=settings.LABEL_STUDIO_HEALTH_TIMEOUT
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=503,
                detail=f"Label Studio not ready: {response.status_code}"
            )

        return {
            "status": "ready",
            "service": "curation-api",
            "label_studio": "connected",
            "schemas_loaded": len(schema_registry.list_schemas()),
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        ) from e


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateTaskRequest(BaseModel):
    """Request to create a new curation task"""
    schema_type: str
    data: dict[str, Any]
    llm_prediction: dict[str, Any] | None = None
    model_version: str | None = None


class SubmitAnnotationRequest(BaseModel):
    """Request to submit an annotation"""
    task_id: int
    result: dict[str, Any]
    time_spent_seconds: float | None = None


class ExportRequest(BaseModel):
    """Request to export gold-star dataset"""
    schema_type: str
    format: str = "icl"  # "icl" or "finetuning"
    min_agreement: float = settings.MIN_AGREEMENT_SCORE
    min_annotations: int = 1


class BulkImportRequest(BaseModel):
    """Request to bulk import vLLM batch results"""
    batch_id: str
    schema_type: str
    results: list[dict[str, Any]]
    model_version: str | None = None


class GoldStarRequest(BaseModel):
    """Request to mark task as gold-star"""
    is_gold_star: bool


class BulkGoldStarRequest(BaseModel):
    """Request to mark multiple tasks as gold-star"""
    task_ids: list[int]
    is_gold_star: bool


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the main landing page"""
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"UI not found at {html_path}")
    return FileResponse(str(html_path))


@app.get("/api/schemas")
async def list_schemas() -> list[dict[str, Any]]:
    """List all available task schemas"""
    schemas = schema_registry.list_schemas()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "version": s.version,
            "questionCount": len(s.questions),
            "dataSourceCount": len(s.dataSources)
        }
        for s in schemas
    ]


@app.get("/api/schemas/{schema_type}")
async def get_schema(schema_type: str) -> TaskSchema:
    """Get a specific task schema"""
    schema = schema_registry.get_schema(schema_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {schema_type}")
    return schema


@app.get("/api/schemas/{schema_type}/prompt")
async def get_schema_prompt(schema_type: str) -> dict[str, Any]:
    """
    Get task schema in LLM-friendly prompt format.

    This endpoint returns a formatted prompt that LLMs can use to understand
    what data to extract and what format to return.

    Perfect for:
    - Building system prompts
    - Few-shot learning examples
    - Fine-tuning datasets
    """
    schema = schema_registry.get_schema(schema_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {schema_type}")

    # Build LLM-friendly prompt
    prompt_parts = [
        f"# {schema.name}",
        f"\n{schema.description}\n",
        "\n## Data Sources\n"
    ]

    # Add data sources
    for source in schema.dataSources:
        prompt_parts.append(f"- **{source.name}** ({source.type})")
        if source.required:
            prompt_parts.append(" [REQUIRED]")
        prompt_parts.append("\n")

    # Add questions/output format
    prompt_parts.append("\n## Output Format\n")
    prompt_parts.append("Respond with JSON containing:\n")

    for question in schema.questions:
        prompt_parts.append(f"\n### {question.id}")
        prompt_parts.append(f"\n- **Question**: {question.text}")
        prompt_parts.append(f"\n- **Type**: {question.type}")
        if question.options:
            prompt_parts.append(f"\n- **Options**: {', '.join(question.options)}")
        if question.required:
            prompt_parts.append("\n- **Required**: Yes")
        if question.helpText:
            prompt_parts.append(f"\n- **Help**: {question.helpText}")
        prompt_parts.append("\n")

    # Build example response
    from typing import Any
    example: dict[str, Any] = {}
    for question in schema.questions:
        if question.type == "choice" and question.options:
            example[question.id] = question.options[0]
        elif question.type == "rating" and question.options:
            example[question.id] = question.options[2] if len(question.options) > 2 else question.options[0]
        elif question.type == "boolean":
            example[question.id] = True
        elif question.type == "number":
            example[question.id] = 0
        elif question.type == "structured":
            example[question.id] = []
        else:
            example[question.id] = "Your answer here"

    # Add example to prompt
    prompt_parts.append("\n## Example Response\n")
    prompt_parts.append("```json\n")
    prompt_parts.append(json.dumps(example, indent=2))
    prompt_parts.append("\n```\n")

    return {
        "schema_type": schema_type,
        "schema_name": schema.name,
        "schema_description": schema.description,
        "prompt": "".join(prompt_parts),
        "example_response": example,
        "schema": schema.dict()
    }


@app.post("/api/tasks")
async def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    """
    Create a new curation task

    This is called when vLLM batch server completes a schema.
    """
    # Validate schema exists
    schema = schema_registry.get_schema(request.schema_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown schema type: {request.schema_type}")

    # Validate task data
    if not schema_registry.validate_task_data(request.schema_type, request.data):
        raise HTTPException(status_code=400, detail="Invalid task data")

    # Add schema type to data
    task_data = {
        **request.data,
        "schema_type": request.schema_type
    }

    # Prepare predictions if provided
    predictions = None
    if request.llm_prediction:
        predictions = [{
            "model_version": request.model_version or "unknown",
            "result": request.llm_prediction,
            "score": 1.0
        }]

    # Create task in Label Studio
    # Note: We need to get or create a project for this schema type
    project_id = await get_or_create_project(request.schema_type)

    task = label_studio.create_task(
        project_id=project_id,
        data=task_data,
        predictions=predictions,
        meta={"schema_type": request.schema_type}
    )

    logger.info(f"Created task {task['id']} for schema type {request.schema_type}")
    return task


def _parse_candidate_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Parse candidate data from messages array.

    Extracts:
    - Candidate name
    - Current role
    - Location
    - Work history
    - Education
    - System prompt
    - User prompt
    """

    result = {
        "name": "Unknown",
        "current_role": "",
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

    # Extract user prompt and parse candidate data
    if messages[1].get("role") == "user":
        user_content = messages[1].get("content", "")
        result["user_prompt"] = user_content

        # Parse candidate name
        name_match = re.search(r'\*\*Candidate:\*\*\s*(.+?)(?:\n|$)', user_content)
        if name_match:
            result["name"] = name_match.group(1).strip()

        # Parse current role
        role_match = re.search(r'\*\*Current Role:\*\*\s*(.+?)(?:\n|$)', user_content)
        if role_match:
            result["current_role"] = role_match.group(1).strip()

        # Parse location
        location_match = re.search(r'\*\*Location:\*\*\s*(.+?)(?:\n|$)', user_content)
        if location_match:
            result["location"] = location_match.group(1).strip()

        # Parse work history
        work_section = re.search(r'\*\*Work History:\*\*\s*\n((?:•.+?\n)+)', user_content)
        if work_section:
            work_lines = work_section.group(1).strip().split('\n')
            result["work_history"] = [
                line.strip().lstrip('•').strip()
                for line in work_lines
                if line.strip()
            ]

        # Parse education
        edu_section = re.search(r'\*\*Education:\*\*\s*\n((?:•.+\n?)+)', user_content, re.MULTILINE)
        if edu_section:
            edu_lines = edu_section.group(1).strip().split('\n')
            result["education"] = [
                line.strip().lstrip('•').strip()
                for line in edu_lines
                if line.strip() and line.strip().startswith('•')
            ]

    return result


@app.post("/api/tasks/bulk-import")
async def bulk_import_tasks(request: BulkImportRequest) -> dict[str, Any]:
    """
    Bulk import vLLM batch results into curation system.

    This is automatically called when a batch job completes,
    enabling you to view all results in the curation UI and
    mark gold-star examples for training datasets.

    Args:
        request: Batch results with schema type and model version

    Returns:
        Import statistics
    """
    # Validate schema exists
    schema = schema_registry.get_schema(request.schema_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown schema type: {request.schema_type}")

    logger.info(f"Bulk importing {len(request.results)} results for {request.schema_type}")

    # Get or create project
    project_id = await get_or_create_project(request.schema_type)

    # Import each result
    created_tasks = []
    skipped_count = 0

    for result in request.results:
        try:
            # Extract custom_id and response
            custom_id = result.get('custom_id', 'unknown')
            response_body = result.get('response', {}).get('body', {})

            # Get LLM response content
            choices = response_body.get('choices', [])
            if not choices:
                skipped_count += 1
                continue

            llm_content = choices[0].get('message', {}).get('content', '')

            # Parse LLM response (assuming JSON format)
            try:
                llm_prediction = json.loads(llm_content)
            except json.JSONDecodeError:
                # If not JSON, store as text
                llm_prediction = {"response": llm_content}

            # Get input data from request body (if available)
            request_body = result.get('request', {}).get('body', {})
            messages = request_body.get('messages', [])

            # Parse candidate data from user message
            candidate_data = _parse_candidate_from_messages(messages)

            # Build task data with parsed candidate info
            task_data = {
                "schema_type": request.schema_type,
                "batch_id": request.batch_id,
                "custom_id": custom_id,
                # Candidate information
                "candidate_name": candidate_data.get("name", "Unknown"),
                "current_role": candidate_data.get("current_role", ""),
                "location": candidate_data.get("location", ""),
                "work_history": candidate_data.get("work_history", []),
                "education": candidate_data.get("education", []),
                # System and user prompts (for training sets)
                "system_prompt": candidate_data.get("system_prompt", ""),
                "user_prompt": candidate_data.get("user_prompt", ""),
                # LLM response
                **llm_prediction  # Spread LLM prediction fields into task data
            }

            # Create predictions for pre-filling
            predictions = [{
                "model_version": request.model_version or "unknown",
                "result": llm_prediction,
                "score": 1.0
            }]

            # Create task in Label Studio
            task = label_studio.create_task(
                project_id=project_id,
                data=task_data,
                predictions=predictions,
                meta={
                    "schema_type": request.schema_type,
                    "batch_id": request.batch_id,
                    "custom_id": custom_id,
                    "auto_imported": True
                }
            )

            created_tasks.append(task['id'])

        except Exception as e:
            logger.warning(f"Failed to import result {custom_id}: {e}")
            skipped_count += 1
            continue

    logger.info(f"Bulk import complete: {len(created_tasks)} created, {skipped_count} skipped")

    return {
        "batch_id": request.batch_id,
        "schema_type": request.schema_type,
        "total_results": len(request.results),
        "created_count": len(created_tasks),
        "skipped_count": skipped_count,
        "task_ids": created_tasks[:100],  # Return first 100 IDs
        "curation_url": f"http://localhost:8001?schema_type={request.schema_type}"
    }


@app.get("/api/tasks")
async def list_tasks(
    schema_type: (str) | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)
) -> dict[str, Any]:
    """List tasks with optional filtering"""
    if schema_type:
        project_id = await get_or_create_project(schema_type)
        tasks = label_studio.get_tasks(
            project_id=project_id,
            page=page,
            page_size=page_size
        )
    else:
        # Get tasks from all projects
        # This is a simplified version - in production you'd aggregate across projects
        tasks = []

    return {
        "tasks": tasks,
        "page": page,
        "page_size": page_size,
        "total": len(tasks)
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int) -> dict[str, Any]:
    """Get a specific task"""
    task = label_studio.get_task(task_id)
    return task


@app.post("/api/annotations")
async def submit_annotation(request: SubmitAnnotationRequest) -> dict[str, Any]:
    """
    Submit a human annotation

    This is called when a human completes curation in the UI.
    """
    # Get task to determine schema type
    task = label_studio.get_task(request.task_id)
    schema_type = task['data'].get('schema_type')

    if not schema_type:
        raise HTTPException(status_code=400, detail="Task missing schema_type")

    # Validate annotation
    if not schema_registry.validate_annotation(schema_type, request.result):
        raise HTTPException(status_code=400, detail="Invalid annotation")

    # Create annotation in Label Studio
    annotation = label_studio.create_annotation(
        task_id=request.task_id,
        result=[request.result],  # Label Studio expects list of results
        lead_time=request.time_spent_seconds
    )

    # Calculate agreement with LLM prediction if available
    predictions = task.get('predictions', [])
    if predictions:
        prediction_result = predictions[0].get('result', {})
        agreement = label_studio.calculate_agreement(
            request.task_id,
            prediction_result,
            request.result
        )
        annotation['agreement_score'] = agreement
        logger.info(f"Annotation {annotation['id']} agreement: {agreement:.2f}")

    return annotation


@app.post("/api/export")
async def export_dataset(request: ExportRequest) -> dict[str, Any]:
    """
    Export gold-star dataset for training

    Returns high-quality examples where human agreed with LLM.
    """
    # Get project for this schema type
    project_id = await get_or_create_project(request.schema_type)

    # Get gold-star tasks
    gold_star_tasks = label_studio.get_gold_star_tasks(
        project_id=project_id,
        min_agreement=request.min_agreement,
        min_annotations=request.min_annotations
    )

    # Export to requested format
    if request.format == "icl":
        examples = schema_registry.export_to_icl(gold_star_tasks, request.schema_type)
    elif request.format == "finetuning":
        examples = schema_registry.export_to_finetuning(gold_star_tasks, request.schema_type)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export format: {request.format}")

    return {
        "schema_type": request.schema_type,
        "format": request.format,
        "count": len(examples),
        "min_agreement": request.min_agreement,
        "examples": examples
    }


@app.get("/api/stats")
async def get_stats(schema_type: (str) | None = None) -> dict[str, Any]:
    """Get curation statistics"""
    if schema_type:
        project_id = await get_or_create_project(schema_type)
        tasks = label_studio.get_tasks(project_id=project_id, page_size=1000)
    else:
        tasks = []

    total_tasks = len(tasks)
    annotated_tasks = len([t for t in tasks if t.get('annotations')])
    pending_tasks = total_tasks - annotated_tasks

    # Calculate average agreement
    agreements = []
    for task in tasks:
        predictions = task.get('predictions', [])
        annotations = task.get('annotations', [])

        if predictions and annotations:
            pred_result = predictions[0].get('result', {})
            ann_result = annotations[0].get('result', [{}])[0]
            agreement = label_studio.calculate_agreement(task['id'], pred_result, ann_result)
            agreements.append(agreement)

    avg_agreement = sum(agreements) / len(agreements) if agreements else 0.0

    return {
        "schema_type": schema_type,
        "total_tasks": total_tasks,
        "annotated_tasks": annotated_tasks,
        "pending_tasks": pending_tasks,
        "average_agreement": avg_agreement,
        "gold_star_tasks": len([a for a in agreements if a >= settings.MIN_AGREEMENT_SCORE])
    }


@app.post("/api/tasks/{task_id}/gold-star")
async def mark_gold_star(task_id: int, request: GoldStarRequest) -> dict[str, Any]:
    """
    Mark a task as gold-star (or unmark it).

    Gold-star tasks are high-quality examples suitable for training datasets.
    This allows manual curation beyond automatic agreement-based filtering.

    When marking as gold star, this can optionally sync to external databases:
    - Sets schema.result = 'VICTORY'
    - Creates ml_analysis_rating record with is_gold_star = true

    Args:
        task_id: Label Studio task ID
        request: Gold-star status (true/false)

    Returns:
        Updated task metadata
    """
    try:
        # Get current task
        task = label_studio.get_task(task_id)

        # Update metadata
        current_meta = task.get('meta', {})
        current_meta['gold_star'] = request.is_gold_star
        current_meta['gold_star_updated_at'] = datetime.now(UTC).isoformat()

        # Update task in Label Studio
        label_studio.update_task(
            task_id=task_id,
            meta=current_meta
        )

        logger.info(f"Task {task_id} gold-star set to {request.is_gold_star}")

        # ========================================================================
        # SYNC TO ARISTOTLE DATABASE
        # ========================================================================
        if request.is_gold_star:
            # Extract schema information from task data
            task_data = task.get('data', {})
            schema_id = task_data.get('schema_id') or task_data.get('id')
            user_email = task_data.get('user_email', 'unknown@example.com')
            domain = task_data.get('domain', 'default')

            # Optional: Sync to external database (e.g., Aristotle)
            # This is disabled by default for OSS. To enable:
            # 1. Set ENABLE_EXTERNAL_SYNC=true in .env
            # 2. Implement your own sync function in integrations/
            if schema_id and os.getenv("ENABLE_EXTERNAL_SYNC") == "true":
                logger.info(f"🌟 Syncing gold star to external database: schema={schema_id}")

                try:
                    # Example: Import your custom sync function
                    # from integrations.your_app.sync import sync_gold_star
                    #
                    # success = sync_gold_star(
                    #     schema_id=schema_id,
                    #     user_email=philosopher,
                    #     domain=domain,
                    #     rating=5,
                    #     feedback="Marked as gold star via curation UI",
                    #     label_studio_task_id=task_id
                    # )

                    logger.warning("External sync is enabled but no sync function is configured")
                    current_meta['external_sync_enabled'] = True
                    current_meta['external_sync_configured'] = False

                except Exception as e:
                    logger.error(f"❌ Error syncing gold star to external database: {e}", exc_info=True)
                    current_meta['external_synced'] = False
                    current_meta['external_sync_error'] = str(e)
            else:
                logger.warning(f"Task {task_id} missing schema_id, cannot sync to external database")

        return {
            "task_id": task_id,
            "gold_star": request.is_gold_star,
            "updated_at": current_meta['gold_star_updated_at'],
            "external_synced": current_meta.get('external_synced', False)
        }

    except Exception as e:
        logger.error(f"Failed to update gold-star for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update gold-star: {str(e)}") from e


@app.post("/api/tasks/bulk-gold-star")
async def bulk_mark_gold_star(request: BulkGoldStarRequest) -> dict[str, Any]:
    """
    Mark multiple tasks as gold-star (or unmark them).

    Useful for batch operations like "mark all high-agreement tasks as gold-star".

    Args:
        request: List of task IDs and gold-star status

    Returns:
        Update statistics
    """
    updated_count = 0
    failed_count = 0

    for task_id in request.task_ids:
        try:
            # Get current task
            task = label_studio.get_task(task_id)

            # Update metadata
            current_meta = task.get('meta', {})
            current_meta['gold_star'] = request.is_gold_star
            current_meta['gold_star_updated_at'] = datetime.now(UTC).isoformat()

            # Update task
            label_studio.update_task(task_id=task_id, meta=current_meta)
            updated_count += 1

        except Exception as e:
            logger.warning(f"Failed to update task {task_id}: {e}")
            failed_count += 1

    logger.info(f"Bulk gold-star update: {updated_count} updated, {failed_count} failed")

    return {
        "total_tasks": len(request.task_ids),
        "updated_count": updated_count,
        "failed_count": failed_count,
        "gold_star": request.is_gold_star
    }


# ============================================================================
# Helper Functions
# ============================================================================

# In-memory project cache (in production, use database)
_project_cache: dict[str, int] = {}

async def get_or_create_project(schema_type: str) -> int:
    """Get or create Label Studio project for a schema type"""
    if schema_type in _project_cache:
        return _project_cache[schema_type]

    # Get schema
    schema = schema_registry.get_schema(schema_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown schema type: {schema_type}")

    # Generate Label Studio config
    label_config = schema_registry.generate_label_studio_config(schema)

    # Create project
    project = label_studio.create_project(
        title=f"{schema.name} Curation",
        description=schema.description,
        label_config=label_config
    )

    _project_cache[schema_type] = project['id']
    logger.info(f"Created Label Studio project {project['id']} for {schema_type}")

    return project['id']


# ============================================================================
# Metrics & Analytics Endpoints
# ============================================================================

@app.get("/api/metrics/overview")
async def get_metrics_overview():
    """
    Get comprehensive metrics overview for the dashboard.

    Returns:
    - Total batches, tasks, gold stars
    - Model performance comparison
    - Quality distribution
    - Timeline data
    - Recent activity
    """
    from sqlalchemy import create_engine, text
    from core.config import settings

    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # Get batch statistics
        batch_stats = conn.execute(text("""
            SELECT
                COUNT(*) as total_batches,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_batches,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_batches,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_batches,
                SUM(total_requests) as total_requests,
                SUM(completed_requests) as completed_requests
            FROM batch_jobs
        """)).fetchone()

        # Get model performance stats
        model_stats = conn.execute(text("""
            SELECT
                model,
                COUNT(*) as batch_count,
                AVG(CASE
                    WHEN completed_at IS NOT NULL AND in_progress_at IS NOT NULL
                    THEN completed_at - in_progress_at
                    ELSE NULL
                END) as avg_duration_seconds,
                SUM(total_requests) as total_requests,
                SUM(completed_requests) as completed_requests
            FROM batch_jobs
            WHERE status = 'completed'
            GROUP BY model
            ORDER BY batch_count DESC
            LIMIT 10
        """)).fetchall()

        # Get recent batches
        recent_batches = conn.execute(text("""
            SELECT
                batch_id,
                model,
                status,
                total_requests,
                completed_requests,
                created_at,
                in_progress_at,
                completed_at
            FROM batch_jobs
            ORDER BY created_at DESC
            LIMIT 10
        """)).fetchall()

        # Get timeline data (batches per day for last 30 days)
        timeline = conn.execute(text("""
            SELECT
                DATE(to_timestamp(created_at)) as date,
                COUNT(*) as batch_count,
                SUM(total_requests) as request_count,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count
            FROM batch_jobs
            WHERE created_at >= EXTRACT(EPOCH FROM (CURRENT_DATE - INTERVAL '30 days'))
            GROUP BY DATE(to_timestamp(created_at))
            ORDER BY date ASC
        """)).fetchall()

    # Get Label Studio stats
    try:
        ls_client = LabelStudioClient()

        # Get all projects
        projects_response = ls_client.session.get(
            f"{ls_client.base_url}/api/projects",
            timeout=ls_client.timeout
        )
        projects_response.raise_for_status()
        projects = projects_response.json()

        total_tasks = 0
        total_annotations = 0
        gold_star_count = 0

        for project in projects:
            project_id = project['id']
            tasks = ls_client.get_tasks(project_id=project_id, page_size=1000)
            total_tasks += len(tasks)

            for task in tasks:
                annotations = task.get('annotations', [])
                total_annotations += len(annotations)

                # Check if task is marked as gold star
                meta = task.get('meta', {})
                if meta.get('gold_star'):
                    gold_star_count += 1

        label_studio_stats = {
            "total_projects": len(projects),
            "total_tasks": total_tasks,
            "total_annotations": total_annotations,
            "gold_star_count": gold_star_count
        }
    except Exception as e:
        logger.error(f"Error fetching Label Studio stats: {e}")
        label_studio_stats = {
            "total_projects": 0,
            "total_tasks": 0,
            "total_annotations": 0,
            "gold_star_count": 0,
            "error": str(e)
        }

    return {
        "batch_stats": {
            "total_batches": batch_stats[0] if batch_stats else 0,
            "completed_batches": batch_stats[1] if batch_stats else 0,
            "failed_batches": batch_stats[2] if batch_stats else 0,
            "in_progress_batches": batch_stats[3] if batch_stats else 0,
            "total_requests": batch_stats[4] if batch_stats else 0,
            "completed_requests": batch_stats[5] if batch_stats else 0
        },
        "model_performance": [
            {
                "model_id": row[0],
                "batch_count": row[1],
                "avg_duration_seconds": float(row[2]) if row[2] else 0,
                "total_requests": row[3],
                "completed_requests": row[4],
                "success_rate": (row[4] / row[3] * 100) if row[3] > 0 else 0
            }
            for row in model_stats
        ],
        "recent_batches": [
            {
                "id": row[0],
                "model_id": row[1],
                "status": row[2],
                "total_requests": row[3],
                "completed_requests": row[4],
                "created_at": datetime.fromtimestamp(row[5], UTC).isoformat() if row[5] else None,
                "started_at": datetime.fromtimestamp(row[6], UTC).isoformat() if row[6] else None,
                "completed_at": datetime.fromtimestamp(row[7], UTC).isoformat() if row[7] else None
            }
            for row in recent_batches
        ],
        "timeline": [
            {
                "date": row[0].isoformat() if row[0] else None,
                "batch_count": row[1],
                "request_count": row[2],
                "completed_count": row[3]
            }
            for row in timeline
        ],
        "label_studio": label_studio_stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

