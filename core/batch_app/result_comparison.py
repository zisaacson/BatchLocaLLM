"""
Result Comparison Tools for Workbench

Provides advanced comparison features:
- Diff viewer for model responses
- Unique answer finder
- Quality metrics
- Agreement analysis
"""

import json
import difflib
from typing import List, Dict, Any, Set, cast
from collections import Counter

from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


def compare_responses(
    results_a: List[Dict[str, Any]],
    results_b: List[Dict[str, Any]],
    model_a_name: str,
    model_b_name: str
) -> Dict[str, Any]:
    """
    Compare responses from two models.
    
    Args:
        results_a: Results from model A
        results_b: Results from model B
        model_a_name: Name of model A
        model_b_name: Name of model B
    
    Returns:
        Comparison analysis with diffs, unique answers, and metrics
    """
    # Index results by custom_id
    results_a_dict = {r.get('custom_id'): r for r in results_a}
    results_b_dict = {r.get('custom_id'): r for r in results_b}
    
    # Find common custom_ids
    common_ids = set(results_a_dict.keys()) & set(results_b_dict.keys())
    
    if not common_ids:
        return {
            'error': 'No common requests found between models',
            'total_a': len(results_a),
            'total_b': len(results_b)
        }
    
    # Compare each pair
    comparisons = []
    identical_count = 0
    different_count = 0
    
    for custom_id in common_ids:
        result_a = results_a_dict[custom_id]
        result_b = results_b_dict[custom_id]
        
        # Extract responses
        response_a = _extract_response_text(result_a)
        response_b = _extract_response_text(result_b)
        
        # Check if identical
        is_identical = response_a == response_b
        
        if is_identical:
            identical_count += 1
        else:
            different_count += 1
        
        # Generate diff
        diff = _generate_diff(response_a, response_b)
        
        comparisons.append({
            'custom_id': custom_id,
            'identical': is_identical,
            'response_a': response_a,
            'response_b': response_b,
            'diff': diff,
            'length_a': len(response_a),
            'length_b': len(response_b)
        })
    
    # Calculate agreement rate
    agreement_rate = identical_count / len(common_ids) if common_ids else 0
    
    return {
        'model_a': model_a_name,
        'model_b': model_b_name,
        'total_compared': len(common_ids),
        'identical': identical_count,
        'different': different_count,
        'agreement_rate': agreement_rate,
        'comparisons': comparisons
    }


def find_unique_answers(
    results_list: List[Any],
    model_names: List[str]
) -> Dict[str, Any]:
    """
    Find unique answers across multiple models.
    
    Identifies cases where one model gives a different answer than all others.
    Useful for finding interesting examples for in-context learning.
    
    Args:
        results_list: List of result sets (one per model)
        model_names: Names of models
    
    Returns:
        Analysis of unique answers
    """
    if len(results_list) < 2:
        return {'error': 'Need at least 2 models to compare'}
    
    # Index all results by custom_id
    results_by_id: Dict[str, Dict[str, str]] = {}
    for i, results in enumerate(results_list):
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            custom_id = result.get('custom_id')
            if custom_id and custom_id not in results_by_id:
                results_by_id[custom_id] = {}
            if custom_id:
                results_by_id[custom_id][model_names[i]] = _extract_response_text(result)
    
    # Find unique answers
    unique_cases = []
    
    for custom_id, responses in results_by_id.items():
        if len(responses) < len(model_names):
            continue  # Skip if not all models have responses
        
        # Count unique responses
        response_counts = Counter(responses.values())
        
        # Find models with unique responses (count == 1)
        for model_name, response in responses.items():
            if response_counts[response] == 1:
                # This model has a unique answer
                other_responses = [r for m, r in responses.items() if m != model_name]
                
                unique_cases.append({
                    'custom_id': custom_id,
                    'unique_model': model_name,
                    'unique_response': response,
                    'other_responses': list(set(other_responses)),
                    'total_models': len(responses),
                    'agreement_count': len(responses) - 1
                })
    
    return {
        'total_requests': len(results_by_id),
        'unique_cases': len(unique_cases),
        'unique_rate': len(unique_cases) / len(results_by_id) if results_by_id else 0,
        'cases': unique_cases
    }


def calculate_quality_metrics(
    results: List[Dict[str, Any]],
    model_name: str
) -> Dict[str, Any]:
    """
    Calculate quality metrics for a model's results.
    
    Metrics:
    - Average response length
    - Response time distribution
    - Token usage
    - Error rate
    
    Args:
        results: Model results
        model_name: Model name
    
    Returns:
        Quality metrics
    """
    if not results:
        return {'error': 'No results provided'}
    
    total_responses = len(results)
    total_length = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    error_count = 0
    
    for result in results:
        # Check for errors
        if 'error' in result and result['error']:
            error_count += 1
            continue
        
        # Extract response
        response = _extract_response_text(result)
        total_length += len(response)
        
        # Extract token usage
        usage = result.get('response', {}).get('body', {}).get('usage', {})
        total_prompt_tokens += usage.get('prompt_tokens', 0)
        total_completion_tokens += usage.get('completion_tokens', 0)
    
    successful_responses = total_responses - error_count
    
    return {
        'model_name': model_name,
        'total_responses': total_responses,
        'successful_responses': successful_responses,
        'error_count': error_count,
        'error_rate': error_count / total_responses if total_responses > 0 else 0,
        'avg_response_length': total_length / successful_responses if successful_responses > 0 else 0,
        'total_prompt_tokens': total_prompt_tokens,
        'total_completion_tokens': total_completion_tokens,
        'total_tokens': total_prompt_tokens + total_completion_tokens,
        'avg_tokens_per_response': (total_prompt_tokens + total_completion_tokens) / successful_responses if successful_responses > 0 else 0
    }


def _extract_response_text(result: Dict[str, Any]) -> str:
    """Extract response text from result."""
    try:
        response = result.get('response', {})
        if not isinstance(response, dict):
            return ''
        body = response.get('body', {})
        if not isinstance(body, dict):
            return ''
        choices = body.get('choices', [])
        if not choices or not isinstance(choices, list):
            return ''
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return ''
        message = first_choice.get('message', {})
        if not isinstance(message, dict):
            return ''
        content = message.get('content', '')
        return str(content) if content else ''
    except (KeyError, IndexError, TypeError, AttributeError):
        return ''


def _generate_diff(text_a: str, text_b: str) -> List[str]:
    """Generate unified diff between two texts."""
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile='Model A',
        tofile='Model B',
        lineterm=''
    ))
    
    return diff


def calculate_agreement_matrix(
    results_list: List[Dict[str, Any]],
    model_names: List[str]
) -> Dict[str, Any]:
    """
    Calculate pairwise agreement matrix between models.
    
    Args:
        results_list: List of result sets (one per model)
        model_names: Names of models
    
    Returns:
        Agreement matrix and statistics
    """
    n_models = len(model_names)
    
    if n_models < 2:
        return {'error': 'Need at least 2 models'}
    
    # Initialize agreement matrix
    agreement_matrix = [[0.0 for _ in range(n_models)] for _ in range(n_models)]
    
    # Calculate pairwise agreement
    for i in range(n_models):
        for j in range(i, n_models):
            if i == j:
                agreement_matrix[i][j] = 1.0  # Perfect agreement with self
            else:
                # Extract results for each model
                model_i_results_raw = results_list[i] if isinstance(results_list[i], list) else []
                model_j_results_raw = results_list[j] if isinstance(results_list[j], list) else []

                # Ensure they are lists of dicts
                model_i_results: List[Dict[str, Any]] = [r for r in model_i_results_raw if isinstance(r, dict)]  # type: ignore[misc,unreachable]
                model_j_results: List[Dict[str, Any]] = [r for r in model_j_results_raw if isinstance(r, dict)]  # type: ignore[misc,unreachable]

                comparison = compare_responses(
                    model_i_results,
                    model_j_results,
                    model_names[i],
                    model_names[j]
                )
                
                agreement_rate = comparison.get('agreement_rate', 0)
                agreement_matrix[i][j] = agreement_rate
                agreement_matrix[j][i] = agreement_rate  # Symmetric
    
    return {
        'model_names': model_names,
        'agreement_matrix': agreement_matrix,
        'avg_agreement': sum(sum(row) for row in agreement_matrix) / (n_models * n_models)
    }

