"""
Batch Submitter Plugin - Web form for submitting batch jobs.

Features:
- File upload with validation
- Model selection from registry
- Priority and metadata configuration
- Real-time job queue viewing
- JSONL format validation
"""

from typing import Dict, List, Any, Optional
import json
from pathlib import Path

from core.plugins.base import UIPlugin, SchemaPlugin


class BatchSubmitterPlugin(UIPlugin, SchemaPlugin):
    """Plugin for batch job submission via web form."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.max_file_size_mb = config.get("max_file_size_mb", 100)
        self.supported_formats = config.get("supported_formats", ["jsonl", "json", "txt"])
        self.default_completion_window = config.get("default_completion_window", "24h")

    # ===== Plugin Base Methods =====

    def get_id(self) -> str:
        return "batch-submitter"

    def get_name(self) -> str:
        return "Batch Submitter"
    
    # ===== SchemaPlugin Methods =====
    
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for batch submission."""
        return {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Model ID to use for inference"
                },
                "input_file_id": {
                    "type": "string",
                    "description": "ID of uploaded input file"
                },
                "endpoint": {
                    "type": "string",
                    "enum": ["/v1/chat/completions"],
                    "default": "/v1/chat/completions"
                },
                "completion_window": {
                    "type": "string",
                    "enum": ["24h", "48h", "72h"],
                    "default": "24h"
                },
                "priority": {
                    "type": "integer",
                    "enum": [-1, 0, 1],
                    "default": 0,
                    "description": "Job priority: -1=low, 0=normal, 1=high"
                },
                "metadata": {
                    "type": "object",
                    "description": "Optional metadata for the batch job"
                }
            },
            "required": ["model", "input_file_id"]
        }
    
    def validate(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate batch submission data."""
        # Check required fields
        if "model" not in data:
            return False, "Model is required"
        
        if "input_file_id" not in data:
            return False, "Input file is required"
        
        # Validate priority
        priority = data.get("priority", 0)
        if priority not in [-1, 0, 1]:
            return False, "Priority must be -1, 0, or 1"
        
        # Validate completion window
        completion_window = data.get("completion_window", "24h")
        if completion_window not in ["24h", "48h", "72h"]:
            return False, "Completion window must be 24h, 48h, or 72h"
        
        return True, None
    
    # ===== UIPlugin Methods =====
    
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """Return UI routes for this plugin."""
        return [
            {"path": "/submit-batch", "template": "plugins/batch-submitter/ui/submit.html"},
            {"path": "/job-queue", "template": "plugins/batch-submitter/ui/queue.html"}
        ]
    
    def get_ui_components(self) -> List[str]:
        """Return embeddable UI component IDs."""
        return ["batch-form", "job-queue-viewer", "job-status"]

    def render_component(self, component_id: str, data: Dict[str, Any]) -> str:
        """Render a UI component with data."""
        if component_id == "batch-form":
            models = data.get("models", [])

            html = '<div class="batch-form">'
            html += '<form id="batch-submit-form">'
            html += '<div class="form-group">'
            html += '<label>Model:</label>'
            html += '<select name="model" required>'
            for model in models:
                html += f'<option value="{model}">{model}</option>'
            html += '</select>'
            html += '</div>'

            html += '<div class="form-group">'
            html += '<label>Input File (JSONL):</label>'
            html += f'<input type="file" name="file" accept=".jsonl" required />'
            html += f'<small>Max size: {self.max_file_size_mb}MB</small>'
            html += '</div>'

            html += '<div class="form-group">'
            html += '<label>Priority:</label>'
            html += '<select name="priority">'
            html += '<option value="1">High</option>'
            html += '<option value="0" selected>Normal</option>'
            html += '<option value="-1">Low</option>'
            html += '</select>'
            html += '</div>'

            html += '<button type="submit">Submit Batch Job</button>'
            html += '</form>'
            html += '</div>'

            return html

        elif component_id == "job-queue-viewer":
            jobs = data.get("jobs", [])

            html = '<div class="job-queue-viewer">'
            html += '<h3>Job Queue</h3>'
            html += '<table><thead><tr>'
            html += '<th>ID</th><th>Model</th><th>Status</th><th>Progress</th><th>Created</th>'
            html += '</tr></thead><tbody>'

            for job in jobs:
                status = job.get("status", "unknown")
                progress = job.get("progress", 0)

                html += '<tr>'
                html += f'<td>{job.get("id", "")[:8]}</td>'
                html += f'<td>{job.get("model", "")}</td>'
                html += f'<td><span class="status-{status}">{status}</span></td>'
                html += f'<td>{progress}%</td>'
                html += f'<td>{job.get("created_at", "")}</td>'
                html += '</tr>'

            html += '</tbody></table>'
            html += '</div>'

            return html

        elif component_id == "job-status":
            job = data.get("job", {})
            status = job.get("status", "unknown")
            progress = job.get("progress", 0)

            html = f'<div class="job-status status-{status}">'
            html += f'<div class="status-label">{status.upper()}</div>'
            html += f'<div class="progress-bar"><div class="progress-fill" style="width: {progress}%"></div></div>'
            html += f'<div class="progress-text">{progress}% complete</div>'
            html += '</div>'

            return html

        else:
            return f"<div>Component {component_id} not implemented</div>"

    # ===== File Validation Methods =====
    
    def validate_jsonl_file(self, file_path: str) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate JSONL file format and content.
        
        Returns:
            (is_valid, error_message, stats)
        """
        try:
            path = Path(file_path)
            
            # Check file size
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                return False, f"File too large: {size_mb:.1f}MB (max: {self.max_file_size_mb}MB)", None
            
            # Check file extension
            if path.suffix.lower() not in ['.jsonl', '.json']:
                return False, f"Invalid file format: {path.suffix} (expected .jsonl or .json)", None
            
            # Parse and validate JSONL
            requests = []
            line_num = 0
            
            with open(path, 'r') as f:
                for line in f:
                    line_num += 1
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    try:
                        req = json.loads(line)
                        requests.append(req)
                        
                        # Validate request structure
                        if "custom_id" not in req:
                            return False, f"Line {line_num}: Missing 'custom_id' field", None
                        
                        if "method" not in req or req["method"] != "POST":
                            return False, f"Line {line_num}: Invalid or missing 'method' field", None
                        
                        if "url" not in req or req["url"] != "/v1/chat/completions":
                            return False, f"Line {line_num}: Invalid or missing 'url' field", None
                        
                        if "body" not in req:
                            return False, f"Line {line_num}: Missing 'body' field", None
                        
                        body = req["body"]
                        if "messages" not in body:
                            return False, f"Line {line_num}: Missing 'messages' in body", None
                        
                    except json.JSONDecodeError as e:
                        return False, f"Line {line_num}: Invalid JSON - {str(e)}", None
            
            if not requests:
                return False, "File is empty or contains no valid requests", None
            
            # Calculate stats
            stats = {
                "total_requests": len(requests),
                "file_size_mb": size_mb,
                "unique_custom_ids": len(set(r["custom_id"] for r in requests))
            }
            
            # Check for duplicate custom_ids
            if stats["unique_custom_ids"] < stats["total_requests"]:
                return False, "Duplicate custom_id values found", stats
            
            return True, None, stats
            
        except Exception as e:
            return False, f"Error reading file: {str(e)}", None
    
    def get_file_preview(self, file_path: str, max_lines: int = 5) -> List[Dict[str, Any]]:
        """Get preview of first N requests from JSONL file."""
        try:
            requests = []
            with open(file_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    
                    line = line.strip()
                    if line:
                        try:
                            requests.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            
            return requests
        except Exception:
            return []
    
    # ===== Helper Methods =====
    
    def format_priority_label(self, priority: int) -> str:
        """Get human-readable priority label."""
        labels = {
            1: "High (Production)",
            0: "Normal",
            -1: "Low (Testing)"
        }
        return labels.get(priority, "Unknown")
    
    def estimate_completion_time(self, num_requests: int, model: str) -> Dict[str, Any]:
        """Estimate completion time based on request count and model."""
        # Rough estimates (tokens/sec varies by model)
        throughput_estimates = {
            "gemma-3-4b": 70,  # tok/s
            "llama-3.2-3b": 80,
            "qwen3-4b": 75,
            "default": 70
        }
        
        # Find matching throughput
        throughput = throughput_estimates.get("default")
        for key, value in throughput_estimates.items():
            if key in model.lower():
                throughput = value
                break
        
        # Estimate: ~200 tokens per request (input + output)
        total_tokens = num_requests * 200
        seconds = total_tokens / throughput
        
        return {
            "estimated_seconds": int(seconds),
            "estimated_minutes": round(seconds / 60, 1),
            "estimated_hours": round(seconds / 3600, 2),
            "throughput_tokens_per_sec": throughput
        }
