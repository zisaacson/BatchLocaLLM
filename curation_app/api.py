"""
Curation API Server

FastAPI backend for the unified conquest curation system.
Integrates Label Studio backend with vLLM batch server.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import logging
from pathlib import Path
import json
import re
from datetime import datetime

from config import settings
from .label_studio_client import LabelStudioClient
from .conquest_schemas import get_registry, ConquestSchema

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Conquest Curation API",
    description="Beautiful web interface for curating all conquest types",
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
app.mount("/static", StaticFiles(directory="static"), name="static")

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
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/ready")
async def ready():
    """Readiness check - verifies Label Studio connection"""
    try:
        # Try to connect to Label Studio
        # This will raise an exception if Label Studio is not available
        response = label_studio.session.get(
            f"{label_studio.base_url}/api/health",
            timeout=5
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
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


# ============================================================================
# Pydantic Models
# ============================================================================

class CreateTaskRequest(BaseModel):
    """Request to create a new curation task"""
    conquest_type: str
    data: dict[str, any]
    llm_prediction: dict[str, any] | None = None
    model_version: str | None = None


class SubmitAnnotationRequest(BaseModel):
    """Request to submit an annotation"""
    task_id: int
    result: dict[str, any]
    time_spent_seconds: float | None = None


class ExportRequest(BaseModel):
    """Request to export gold-star dataset"""
    conquest_type: str
    format: str = "icl"  # "icl" or "finetuning"
    min_agreement: float = 0.8
    min_annotations: int = 1


class BulkImportRequest(BaseModel):
    """Request to bulk import vLLM batch results"""
    batch_id: str
    conquest_type: str
    results: list[dict[str, any]]
    model_version: str | None = None


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the main curation UI"""
    return FileResponse("static/conquest-curation.html")


@app.get("/api/schemas")
async def list_schemas() -> list[dict[str, any]]:
    """List all available conquest schemas"""
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


@app.get("/api/schemas/{conquest_type}")
async def get_schema(conquest_type: str) -> ConquestSchema:
    """Get a specific conquest schema"""
    schema = schema_registry.get_schema(conquest_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {conquest_type}")
    return schema


@app.get("/api/schemas/{conquest_type}/prompt")
async def get_schema_prompt(conquest_type: str) -> dict[str, Any]:
    """
    Get conquest schema in LLM-friendly prompt format.

    This endpoint returns a formatted prompt that LLMs can use to understand
    what data to extract and what format to return.

    Perfect for:
    - Building system prompts
    - Few-shot learning examples
    - Fine-tuning datasets
    """
    schema = schema_registry.get_schema(conquest_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {conquest_type}")

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
    example = {}
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
        "conquest_type": conquest_type,
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

    This is called when vLLM batch server completes a conquest.
    """
    # Validate schema exists
    schema = schema_registry.get_schema(request.conquest_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown conquest type: {request.conquest_type}")

    # Validate task data
    if not schema_registry.validate_task_data(request.conquest_type, request.data):
        raise HTTPException(status_code=400, detail="Invalid task data")

    # Add conquest type to data
    task_data = {
        **request.data,
        "conquest_type": request.conquest_type
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
    # Note: We need to get or create a project for this conquest type
    project_id = await get_or_create_project(request.conquest_type)

    task = label_studio.create_task(
        project_id=project_id,
        data=task_data,
        predictions=predictions,
        meta={"conquest_type": request.conquest_type}
    )

    logger.info(f"Created task {task['id']} for conquest type {request.conquest_type}")
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
    import re

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
        request: Batch results with conquest type and model version

    Returns:
        Import statistics
    """
    # Validate schema exists
    schema = schema_registry.get_schema(request.conquest_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown conquest type: {request.conquest_type}")

    logger.info(f"Bulk importing {len(request.results)} results for {request.conquest_type}")

    # Get or create project
    project_id = await get_or_create_project(request.conquest_type)

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
                "conquest_type": request.conquest_type,
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
                    "conquest_type": request.conquest_type,
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
        "conquest_type": request.conquest_type,
        "total_results": len(request.results),
        "created_count": len(created_tasks),
        "skipped_count": skipped_count,
        "task_ids": created_tasks[:100],  # Return first 100 IDs
        "curation_url": f"http://localhost:8001?conquest_type={request.conquest_type}"
    }


@app.get("/api/tasks")
async def list_tasks(
    conquest_type: (str) | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
) -> dict[str, Any]:
    """List tasks with optional filtering"""
    if conquest_type:
        project_id = await get_or_create_project(conquest_type)
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
    # Get task to determine conquest type
    task = label_studio.get_task(request.task_id)
    conquest_type = task['data'].get('conquest_type')
    
    if not conquest_type:
        raise HTTPException(status_code=400, detail="Task missing conquest_type")
    
    # Validate annotation
    if not schema_registry.validate_annotation(conquest_type, request.result):
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
    # Get project for this conquest type
    project_id = await get_or_create_project(request.conquest_type)
    
    # Get gold-star tasks
    gold_star_tasks = label_studio.get_gold_star_tasks(
        project_id=project_id,
        min_agreement=request.min_agreement,
        min_annotations=request.min_annotations
    )
    
    # Export to requested format
    if request.format == "icl":
        examples = schema_registry.export_to_icl(gold_star_tasks, request.conquest_type)
    elif request.format == "finetuning":
        examples = schema_registry.export_to_finetuning(gold_star_tasks, request.conquest_type)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export format: {request.format}")
    
    return {
        "conquest_type": request.conquest_type,
        "format": request.format,
        "count": len(examples),
        "min_agreement": request.min_agreement,
        "examples": examples
    }


@app.get("/api/stats")
async def get_stats(conquest_type: (str) | None = None) -> dict[str, Any]:
    """Get curation statistics"""
    if conquest_type:
        project_id = await get_or_create_project(conquest_type)
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
        "conquest_type": conquest_type,
        "total_tasks": total_tasks,
        "annotated_tasks": annotated_tasks,
        "pending_tasks": pending_tasks,
        "average_agreement": avg_agreement,
        "gold_star_tasks": len([a for a in agreements if a >= 0.8])
    }


# ============================================================================
# Helper Functions
# ============================================================================

# In-memory project cache (in production, use database)
_project_cache: dict[str, int] = {}

async def get_or_create_project(conquest_type: str) -> int:
    """Get or create Label Studio project for a conquest type"""
    if conquest_type in _project_cache:
        return _project_cache[conquest_type]
    
    # Get schema
    schema = schema_registry.get_schema(conquest_type)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Unknown conquest type: {conquest_type}")
    
    # Generate Label Studio config
    label_config = schema_registry.generate_label_studio_config(schema)
    
    # Create project
    project = label_studio.create_project(
        title=f"{schema.name} Curation",
        description=schema.description,
        label_config=label_config
    )
    
    _project_cache[conquest_type] = project['id']
    logger.info(f"Created Label Studio project {project['id']} for {conquest_type}")
    
    return project['id']


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

