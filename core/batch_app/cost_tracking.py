"""
Cost Tracking for vLLM Batch Server

Tracks token usage and calculates costs based on model pricing.
Supports custom pricing models and budget alerts.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


# Pricing per 1M tokens (input/output)
# Based on typical cloud LLM pricing
DEFAULT_PRICING = {
    # Small models (3-4B)
    'small': {
        'input_per_1m': 0.10,
        'output_per_1m': 0.30
    },
    # Medium models (7-12B)
    'medium': {
        'input_per_1m': 0.25,
        'output_per_1m': 0.75
    },
    # Large models (20B+)
    'large': {
        'input_per_1m': 0.50,
        'output_per_1m': 1.50
    }
}


def get_model_tier(model_id: str) -> str:
    """
    Determine model tier from model ID.
    
    Args:
        model_id: Model identifier
    
    Returns:
        Tier: 'small', 'medium', or 'large'
    """
    import re
    
    # Extract parameter count from model ID
    size_match = re.search(r'(\d+)B', model_id, re.IGNORECASE)
    if not size_match:
        return 'medium'  # Default
    
    param_count = int(size_match.group(1))
    
    if param_count <= 4:
        return 'small'
    elif param_count <= 12:
        return 'medium'
    else:
        return 'large'


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model_id: str,
    custom_pricing: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """
    Calculate cost for a request.
    
    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        model_id: Model identifier
        custom_pricing: Optional custom pricing (input_per_1m, output_per_1m)
    
    Returns:
        Cost breakdown
    """
    if custom_pricing:
        input_price = custom_pricing.get('input_per_1m', 0)
        output_price = custom_pricing.get('output_per_1m', 0)
    else:
        tier = get_model_tier(model_id)
        pricing = DEFAULT_PRICING[tier]
        input_price = pricing['input_per_1m']
        output_price = pricing['output_per_1m']
    
    # Calculate costs
    input_cost = (prompt_tokens / 1_000_000) * input_price
    output_cost = (completion_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost
    
    return {
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
        'input_price_per_1m': input_price,
        'output_price_per_1m': output_price
    }


def calculate_batch_cost(
    results: List[Dict[str, Any]],
    model_id: str,
    custom_pricing: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate total cost for a batch of results.
    
    Args:
        results: List of batch results
        model_id: Model identifier
        custom_pricing: Optional custom pricing
    
    Returns:
        Batch cost summary
    """
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_requests = 0
    
    for result in results:
        if 'error' in result and result['error']:
            continue
        
        usage = result.get('response', {}).get('body', {}).get('usage', {})
        total_prompt_tokens += usage.get('prompt_tokens', 0)
        total_completion_tokens += usage.get('completion_tokens', 0)
        total_requests += 1
    
    cost = calculate_cost(
        total_prompt_tokens,
        total_completion_tokens,
        model_id,
        custom_pricing
    )
    
    return {
        'total_requests': total_requests,
        'total_prompt_tokens': total_prompt_tokens,
        'total_completion_tokens': total_completion_tokens,
        'total_tokens': total_prompt_tokens + total_completion_tokens,
        'input_cost': cost['input_cost'],
        'output_cost': cost['output_cost'],
        'total_cost': cost['total_cost'],
        'cost_per_request': cost['total_cost'] / total_requests if total_requests > 0 else 0,
        'pricing': {
            'input_per_1m': cost['input_price_per_1m'],
            'output_per_1m': cost['output_price_per_1m']
        }
    }


def get_usage_summary(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    model_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get usage summary for a time period.
    
    Args:
        db: Database session
        start_date: Start date (optional)
        end_date: End date (optional)
        model_id: Filter by model (optional)
    
    Returns:
        Usage summary with costs
    """
    from core.batch_app.database import BatchJob
    
    # Build query
    query = db.query(BatchJob).filter(BatchJob.status == 'completed')
    
    if start_date:
        query = query.filter(BatchJob.completed_at >= int(start_date.timestamp()))
    
    if end_date:
        query = query.filter(BatchJob.completed_at <= int(end_date.timestamp()))
    
    if model_id:
        query = query.filter(BatchJob.model == model_id)
    
    jobs = query.all()
    
    # Calculate totals
    total_jobs = len(jobs)
    total_requests = sum(job.completed_requests for job in jobs)
    total_tokens = sum(job.total_tokens or 0 for job in jobs)
    
    # Estimate costs (we don't have prompt/completion breakdown in BatchJob)
    # Assume 70% prompt, 30% completion as rough estimate
    estimated_prompt_tokens = int(total_tokens * 0.7)
    estimated_completion_tokens = int(total_tokens * 0.3)
    
    # Calculate cost for each model
    costs_by_model = {}
    for job in jobs:
        if job.model not in costs_by_model:
            costs_by_model[job.model] = {
                'jobs': 0,
                'requests': 0,
                'tokens': 0,
                'cost': 0.0
            }
        
        job_tokens = job.total_tokens or 0
        job_prompt = int(job_tokens * 0.7)
        job_completion = int(job_tokens * 0.3)

        model_name = job.model if job.model else "unknown"
        cost = calculate_cost(job_prompt, job_completion, model_name)
        
        costs_by_model[job.model]['jobs'] += 1
        costs_by_model[job.model]['requests'] += job.completed_requests
        costs_by_model[job.model]['tokens'] += job_tokens
        costs_by_model[job.model]['cost'] += cost['total_cost']
    
    total_cost = sum(m['cost'] for m in costs_by_model.values())
    
    return {
        'period': {
            'start': start_date.isoformat() if start_date else None,
            'end': end_date.isoformat() if end_date else None
        },
        'total_jobs': total_jobs,
        'total_requests': total_requests,
        'total_tokens': total_tokens,
        'estimated_prompt_tokens': estimated_prompt_tokens,
        'estimated_completion_tokens': estimated_completion_tokens,
        'total_cost': total_cost,
        'cost_per_request': total_cost / total_requests if total_requests > 0 else 0,
        'cost_per_1k_tokens': (total_cost / total_tokens * 1000) if total_tokens > 0 else 0,
        'by_model': costs_by_model
    }


def check_budget_alert(
    current_cost: float,
    budget_limit: float,
    alert_threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Check if budget alert should be triggered.
    
    Args:
        current_cost: Current spending
        budget_limit: Budget limit
        alert_threshold: Alert when spending reaches this % of budget (default: 80%)
    
    Returns:
        Alert status
    """
    usage_pct = current_cost / budget_limit if budget_limit > 0 else 0
    
    return {
        'current_cost': current_cost,
        'budget_limit': budget_limit,
        'usage_pct': usage_pct,
        'remaining': budget_limit - current_cost,
        'alert': usage_pct >= alert_threshold,
        'alert_threshold': alert_threshold,
        'status': 'critical' if usage_pct >= 1.0 else 'warning' if usage_pct >= alert_threshold else 'ok'
    }


def estimate_batch_cost(
    num_requests: int,
    avg_prompt_tokens: int,
    avg_completion_tokens: int,
    model_id: str,
    custom_pricing: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Estimate cost for a batch before running.
    
    Args:
        num_requests: Number of requests
        avg_prompt_tokens: Average prompt tokens per request
        avg_completion_tokens: Average completion tokens per request
        model_id: Model identifier
        custom_pricing: Optional custom pricing
    
    Returns:
        Cost estimate
    """
    total_prompt = num_requests * avg_prompt_tokens
    total_completion = num_requests * avg_completion_tokens
    
    cost = calculate_cost(total_prompt, total_completion, model_id, custom_pricing)
    
    return {
        'num_requests': num_requests,
        'total_prompt_tokens': total_prompt,
        'total_completion_tokens': total_completion,
        'total_tokens': total_prompt + total_completion,
        'estimated_cost': cost['total_cost'],
        'cost_per_request': cost['total_cost'] / num_requests,
        'pricing': {
            'input_per_1m': cost['input_price_per_1m'],
            'output_per_1m': cost['output_price_per_1m']
        }
    }

