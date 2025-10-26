"""
Data models for vLLM Batch Server

OpenAI-compatible schemas for batch processing API.
100% compatible with OpenAI Batch API specification.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Batch Request Models (Input)
# =============================================================================


class ChatMessage(BaseModel):
    """Chat message in OpenAI format"""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionBody(BaseModel):
    """Chat completion request body"""

    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    stop: Optional[List[str]] = None
    n: Optional[int] = Field(default=1, ge=1)
    stream: Optional[bool] = False
    logprobs: Optional[bool] = False
    top_logprobs: Optional[int] = Field(default=None, ge=0, le=20)


class BatchRequestLine(BaseModel):
    """Single request in batch JSONL file"""

    custom_id: str = Field(
        ...,
        description="Unique identifier for this request (used to match results)",
    )
    method: Literal["POST"] = "POST"
    url: Literal["/v1/chat/completions"] = "/v1/chat/completions"
    body: ChatCompletionBody


# =============================================================================
# Batch Job Models
# =============================================================================


class BatchStatus(str, Enum):
    """Batch job status (OpenAI-compatible)"""

    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RequestCounts(BaseModel):
    """Request counts for batch job"""

    total: int = 0
    completed: int = 0
    failed: int = 0


class BatchJob(BaseModel):
    """Batch job metadata (OpenAI-compatible)"""

    id: str = Field(..., description="Batch job ID")
    object: Literal["batch"] = "batch"
    endpoint: str = "/v1/chat/completions"
    errors: Optional[Dict[str, Any]] = None
    input_file_id: str
    completion_window: str = "24h"
    status: BatchStatus
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    created_at: int = Field(..., description="Unix timestamp")
    in_progress_at: Optional[int] = None
    expires_at: Optional[int] = None
    finalizing_at: Optional[int] = None
    completed_at: Optional[int] = None
    failed_at: Optional[int] = None
    expired_at: Optional[int] = None
    cancelling_at: Optional[int] = None
    cancelled_at: Optional[int] = None
    request_counts: RequestCounts = Field(default_factory=RequestCounts)
    metadata: Optional[Dict[str, str]] = None


class BatchCreateRequest(BaseModel):
    """Request to create a new batch job"""

    input_file_id: str
    endpoint: Literal["/v1/chat/completions"] = "/v1/chat/completions"
    completion_window: Literal["24h"] = "24h"
    metadata: Optional[Dict[str, str]] = None


# =============================================================================
# File Models
# =============================================================================


class FileObject(BaseModel):
    """File metadata (OpenAI-compatible)"""

    id: str
    object: Literal["file"] = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: Literal["batch", "batch_output", "batch_error"] = "batch"


class FileUploadResponse(BaseModel):
    """Response from file upload"""

    id: str
    object: Literal["file"] = "file"
    bytes: int
    created_at: int
    filename: str
    purpose: Literal["batch"] = "batch"


# =============================================================================
# Batch Result Models (Output)
# =============================================================================


class ChatCompletionChoice(BaseModel):
    """Single completion choice"""

    index: int
    message: ChatMessage
    finish_reason: str
    logprobs: Optional[Dict[str, Any]] = None


class Usage(BaseModel):
    """Token usage statistics"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Chat completion response"""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage
    system_fingerprint: Optional[str] = None


class BatchResponseBody(BaseModel):
    """Response body in batch result"""

    status_code: int
    request_id: str
    body: ChatCompletionResponse


class BatchError(BaseModel):
    """Error in batch result"""

    message: str
    type: str
    code: str


class BatchResultLine(BaseModel):
    """Single result in batch output JSONL file"""

    id: str
    custom_id: str
    response: Optional[BatchResponseBody] = None
    error: Optional[BatchError] = None


# =============================================================================
# Health Check Models
# =============================================================================


class HealthStatus(str, Enum):
    """Health check status"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheck(BaseModel):
    """Health check response"""

    status: HealthStatus
    timestamp: datetime
    version: str = "0.1.0"
    model_loaded: bool = False
    active_batches: int = 0
    gpu_available: bool = False
    gpu_memory_used_gb: Optional[float] = None
    gpu_memory_total_gb: Optional[float] = None


# =============================================================================
# Error Models
# =============================================================================


class ErrorResponse(BaseModel):
    """Error response"""

    error: Dict[str, Any]


class ErrorDetail(BaseModel):
    """Detailed error information"""

    message: str
    type: str
    code: str
    param: Optional[str] = None

