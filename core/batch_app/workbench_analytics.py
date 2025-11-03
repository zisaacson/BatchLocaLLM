"""
Workbench Analytics Module

Provides advanced analytics and reporting for benchmark results:
- Benchmark history viewer
- Quality metrics dashboard
- Export comparison reports
- Automated quality scoring
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.batch_app.database import Benchmark, ModelRegistry
from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


def get_benchmark_history(
    db: Session,
    model_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get benchmark history with filtering and pagination.
    
    Args:
        db: Database session
        model_id: Filter by model ID
        dataset_id: Filter by dataset ID
        start_date: Filter by start date
        end_date: Filter by end date
        status: Filter by status (running, completed, failed, cancelled)
        limit: Maximum results to return
        offset: Offset for pagination
    
    Returns:
        Paginated benchmark history
    """
    # Build query
    query = db.query(Benchmark)
    
    # Apply filters
    if model_id:
        query = query.filter(Benchmark.model_id == model_id)
    if dataset_id:
        query = query.filter(Benchmark.dataset_id == dataset_id)
    if start_date:
        query = query.filter(Benchmark.created_at >= start_date)
    if end_date:
        query = query.filter(Benchmark.created_at <= end_date)
    if status:
        query = query.filter(Benchmark.status == status)
    
    # Get total count
    total_count = query.count()
    
    # Apply sorting and pagination
    query = query.order_by(Benchmark.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    # Execute
    benchmarks = query.all()
    
    # Enrich with model names
    results = []
    for b in benchmarks:
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == b.model_id).first()
        
        # Calculate duration
        duration = None
        if b.started_at and b.completed_at:
            duration = (b.completed_at - b.started_at).total_seconds()
        elif b.started_at:
            duration = (datetime.now() - b.started_at).total_seconds()
        
        results.append({
            'id': b.id,
            'model_id': b.model_id,
            'model_name': model.name if model else b.model_id,
            'dataset_id': b.dataset_id,
            'status': b.status,
            'created_at': b.created_at.isoformat() if b.created_at else None,
            'started_at': b.started_at.isoformat() if b.started_at else None,
            'completed_at': b.completed_at.isoformat() if b.completed_at else None,
            'duration_seconds': duration,
            'progress': b.progress,
            'completed': b.completed,
            'total': b.total,
            'throughput': b.throughput,
            'eta_seconds': b.eta_seconds,
            'has_results': bool(b.results_file and Path(b.results_file).exists())
        })
    
    return {
        'benchmarks': results,
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'has_more': (offset + len(results)) < total_count
    }


def get_quality_metrics_dashboard(db: Session, benchmark_ids: List[str]):
    """
    Generate quality metrics dashboard for multiple benchmarks.
    
    Compares quality across benchmarks:
    - Response quality scores
    - Consistency metrics
    - Error analysis
    - Token efficiency
    
    Args:
        db: Database session
        benchmark_ids: List of benchmark IDs to analyze
    
    Returns:
        Quality metrics dashboard data
    """
    dashboard = []
    
    for benchmark_id in benchmark_ids:
        bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not bm or not bm.results_file or not Path(bm.results_file).exists():
            continue
        
        # Load results
        results = []
        with open(bm.results_file, 'r') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))
        
        if not results:
            continue
        
        # Get model name
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
        model_name = model.name if model else bm.model_id
        
        # Calculate quality metrics
        total_responses = len(results)
        successful_responses = sum(1 for r in results if not r.get('error'))
        error_count = total_responses - successful_responses
        error_rate = error_count / total_responses if total_responses > 0 else 0.0
        
        # Response length analysis
        response_lengths = []
        for r in results:
            if not r.get('error'):
                content = r.get('response', {}).get('body', {}).get('choices', [{}])[0].get('message', {}).get('content', '')
                response_lengths.append(len(content))
        
        avg_response_length = sum(response_lengths) / len(response_lengths) if response_lengths else 0
        min_response_length = min(response_lengths) if response_lengths else 0
        max_response_length = max(response_lengths) if response_lengths else 0
        
        # Token usage analysis
        total_prompt_tokens = 0
        total_completion_tokens = 0
        for r in results:
            if not r.get('error'):
                usage = r.get('response', {}).get('body', {}).get('usage', {})
                total_prompt_tokens += usage.get('prompt_tokens', 0)
                total_completion_tokens += usage.get('completion_tokens', 0)
        
        avg_prompt_tokens = total_prompt_tokens / successful_responses if successful_responses > 0 else 0
        avg_completion_tokens = total_completion_tokens / successful_responses if successful_responses > 0 else 0
        
        # Token efficiency (completion tokens per prompt token)
        token_efficiency = avg_completion_tokens / avg_prompt_tokens if avg_prompt_tokens > 0 else 0
        
        # Automated quality scoring
        quality_score = calculate_quality_score(
            error_rate=error_rate,
            avg_response_length=avg_response_length,
            token_efficiency=token_efficiency,
            throughput=bm.throughput or 0
        )
        
        dashboard.append({
            'benchmark_id': benchmark_id,
            'model_id': bm.model_id,
            'model_name': model_name,
            'dataset_id': bm.dataset_id,
            'response_metrics': {
                'total_responses': total_responses,
                'successful_responses': successful_responses,
                'error_count': error_count,
                'error_rate': round(error_rate, 4),
                'avg_response_length': round(avg_response_length, 1),
                'min_response_length': min_response_length,
                'max_response_length': max_response_length
            },
            'token_metrics': {
                'total_prompt_tokens': total_prompt_tokens,
                'total_completion_tokens': total_completion_tokens,
                'avg_prompt_tokens': round(avg_prompt_tokens, 1),
                'avg_completion_tokens': round(avg_completion_tokens, 1),
                'token_efficiency': round(token_efficiency, 3)
            },
            'performance_metrics': {
                'throughput': bm.throughput,
                'duration_seconds': (bm.completed_at - bm.started_at).total_seconds() if bm.started_at and bm.completed_at else None
            },
            'quality_score': quality_score
        })
    
    # Sort by quality score (descending)
    dashboard.sort(key=lambda x: x['quality_score'], reverse=True)
    
    return {
        'total_benchmarks': len(dashboard),
        'dashboard': dashboard,
        'summary': {
            'best_quality': dashboard[0]['model_name'] if dashboard else None,
            'avg_quality_score': sum(d['quality_score'] for d in dashboard) / len(dashboard) if dashboard else 0,
            'avg_error_rate': sum(d['response_metrics']['error_rate'] for d in dashboard) / len(dashboard) if dashboard else 0
        }
    }


def calculate_quality_score(
    error_rate: float,
    avg_response_length: float,
    token_efficiency: float,
    throughput: float
) -> float:
    """
    Calculate automated quality score (0-100).
    
    Scoring formula:
    - Error rate: 40 points (lower is better)
    - Response completeness: 30 points (based on length)
    - Token efficiency: 20 points
    - Throughput: 10 points
    
    Args:
        error_rate: Error rate (0.0-1.0)
        avg_response_length: Average response length in characters
        token_efficiency: Completion tokens per prompt token
        throughput: Requests per second
    
    Returns:
        Quality score (0-100)
    """
    score = 0.0
    
    # Error rate score (40 points max)
    # 0% error = 40 points, 100% error = 0 points
    error_score = (1.0 - error_rate) * 40
    score += error_score
    
    # Response completeness score (30 points max)
    # Based on response length (200-500 chars is ideal)
    if avg_response_length >= 200 and avg_response_length <= 500:
        completeness_score = 30
    elif avg_response_length < 200:
        completeness_score = (avg_response_length / 200) * 30
    else:
        # Penalize overly long responses
        completeness_score = max(0, 30 - ((avg_response_length - 500) / 100))
    score += completeness_score
    
    # Token efficiency score (20 points max)
    # 0.5-1.5 ratio is ideal
    if token_efficiency >= 0.5 and token_efficiency <= 1.5:
        efficiency_score = 20
    elif token_efficiency < 0.5:
        efficiency_score = (token_efficiency / 0.5) * 20
    else:
        efficiency_score = max(0, 20 - ((token_efficiency - 1.5) * 5))
    score += efficiency_score
    
    # Throughput score (10 points max)
    # 10+ req/s = 10 points, 0 req/s = 0 points
    throughput_score = min(10, (throughput / 10) * 10)
    score += throughput_score

    return round(score, 2)


def export_comparison_report(
    db: Session,
    benchmark_ids: List[str],
    format: str = 'json'
) -> Dict[str, Any]:
    """
    Export detailed comparison report for benchmarks.

    Args:
        db: Database session
        benchmark_ids: List of benchmark IDs to compare
        format: Export format (json, csv, markdown)

    Returns:
        Comparison report data
    """
    from core.batch_app.result_comparison import compare_responses

    # Get quality metrics
    quality_dashboard = get_quality_metrics_dashboard(db, benchmark_ids)

    # Load all results for detailed comparison
    benchmark_results = {}
    for benchmark_id in benchmark_ids:
        bm = db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not bm or not bm.results_file or not Path(bm.results_file).exists():
            continue

        # Load results
        results = []
        with open(bm.results_file, 'r') as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

        # Get model name
        model = db.query(ModelRegistry).filter(ModelRegistry.model_id == bm.model_id).first()
        model_name = model.name if model else bm.model_id

        benchmark_results[benchmark_id] = {
            'model_name': model_name,
            'model_id': bm.model_id,
            'results': results
        }

    # Generate pairwise comparisons
    comparisons = []
    benchmark_list = list(benchmark_results.keys())
    for i in range(len(benchmark_list)):
        for j in range(i + 1, len(benchmark_list)):
            bm_a_id = benchmark_list[i]
            bm_b_id = benchmark_list[j]

            bm_a = benchmark_results[bm_a_id]
            bm_b = benchmark_results[bm_b_id]

            # Compare responses
            comparison = compare_responses(
                results_a=bm_a['results'],
                results_b=bm_b['results'],
                model_a_name=bm_a['model_name'],
                model_b_name=bm_b['model_name']
            )

            comparisons.append({
                'benchmark_a_id': bm_a_id,
                'benchmark_b_id': bm_b_id,
                'model_a': bm_a['model_name'],
                'model_b': bm_b['model_name'],
                'comparison': comparison
            })

    # Build report
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_benchmarks': len(benchmark_ids),
        'quality_dashboard': quality_dashboard,
        'pairwise_comparisons': comparisons,
        'summary': {
            'best_quality_model': quality_dashboard['summary']['best_quality'],
            'avg_quality_score': quality_dashboard['summary']['avg_quality_score'],
            'total_comparisons': len(comparisons)
        }
    }

    # Format output
    if format == 'markdown':
        return _format_report_markdown(report)
    elif format == 'csv':
        return _format_report_csv(report)
    else:
        return report


def _format_report_markdown(report: Dict[str, Any]) -> str:
    """Format comparison report as Markdown."""
    md = f"# Benchmark Comparison Report\n\n"
    md += f"**Generated**: {report['generated_at']}\n\n"
    md += f"**Total Benchmarks**: {report['total_benchmarks']}\n\n"

    # Quality Dashboard
    md += "## Quality Dashboard\n\n"
    md += "| Model | Quality Score | Error Rate | Avg Response Length | Throughput |\n"
    md += "|-------|---------------|------------|---------------------|------------|\n"

    for item in report['quality_dashboard']['dashboard']:
        md += f"| {item['model_name']} | {item['quality_score']} | {item['response_metrics']['error_rate']:.2%} | {item['response_metrics']['avg_response_length']:.0f} | {item['performance_metrics']['throughput']:.2f} |\n"

    md += "\n"

    # Pairwise Comparisons
    md += "## Pairwise Comparisons\n\n"
    for comp in report['pairwise_comparisons']:
        md += f"### {comp['model_a']} vs {comp['model_b']}\n\n"
        md += f"- **Agreement Rate**: {comp['comparison']['agreement_rate']:.2%}\n"
        md += f"- **Identical Responses**: {comp['comparison']['identical']}\n"
        md += f"- **Different Responses**: {comp['comparison']['different']}\n\n"

    # Summary
    md += "## Summary\n\n"
    md += f"- **Best Quality Model**: {report['summary']['best_quality_model']}\n"
    md += f"- **Average Quality Score**: {report['summary']['avg_quality_score']:.2f}\n"

    return md


def _format_report_csv(report: Dict[str, Any]) -> str:
    """Format comparison report as CSV."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Model', 'Quality Score', 'Error Rate', 'Avg Response Length', 'Throughput'])

    # Data
    for item in report['quality_dashboard']['dashboard']:
        writer.writerow([
            item['model_name'],
            item['quality_score'],
            item['response_metrics']['error_rate'],
            item['response_metrics']['avg_response_length'],
            item['performance_metrics']['throughput']
        ])

    return output.getvalue()


