"""
Metrics calculator for model evaluation.

Calculates quality, performance, and efficiency metrics for fine-tuned models.
"""

import logging
import statistics
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """Quality metrics for model evaluation."""
    
    win_rate: float  # % of times model beats baseline
    gold_star_rate: float  # % of outputs rated as gold star
    avg_rating: float  # Mean rating (1-5)
    consistency_score: float  # 1 - (std_dev / mean) - higher is better
    task_accuracy: float | None = None  # Task-specific accuracy
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'win_rate': self.win_rate,
            'gold_star_rate': self.gold_star_rate,
            'avg_rating': self.avg_rating,
            'consistency_score': self.consistency_score,
            'task_accuracy': self.task_accuracy
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for model evaluation."""
    
    tokens_per_second: float
    latency_ms: int  # Time to first token
    throughput: float  # Requests per second
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tokens_per_second': self.tokens_per_second,
            'latency_ms': self.latency_ms,
            'throughput': self.throughput
        }


@dataclass
class EfficiencyMetrics:
    """Efficiency metrics for model evaluation."""
    
    model_size_mb: int
    vram_usage_gb: float
    cost_per_1m_tokens: float | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'model_size_mb': self.model_size_mb,
            'vram_usage_gb': self.vram_usage_gb,
            'cost_per_1m_tokens': self.cost_per_1m_tokens
        }


class MetricsCalculator:
    """
    Calculate evaluation metrics for fine-tuned models.
    
    Provides methods to calculate quality, performance, and efficiency metrics.
    """
    
    @staticmethod
    def calculate_win_rate(
        base_model_wins: int,
        fine_tuned_wins: int,
        ties: int
    ) -> float:
        """
        Calculate win rate for fine-tuned model.
        
        Win rate = (fine_tuned_wins + 0.5 * ties) / total_comparisons
        """
        total = base_model_wins + fine_tuned_wins + ties
        if total == 0:
            return 0.0
        
        return ((fine_tuned_wins + 0.5 * ties) / total) * 100
    
    @staticmethod
    def calculate_gold_star_rate(
        gold_star_count: int,
        total_outputs: int
    ) -> float:
        """Calculate percentage of outputs rated as gold star."""
        if total_outputs == 0:
            return 0.0
        
        return (gold_star_count / total_outputs) * 100
    
    @staticmethod
    def calculate_avg_rating(ratings: list[int]) -> float:
        """Calculate average rating."""
        if not ratings:
            return 0.0
        
        return statistics.mean(ratings)
    
    @staticmethod
    def calculate_consistency_score(ratings: list[int]) -> float:
        """
        Calculate consistency score.
        
        Consistency = 1 - (std_dev / mean)
        Higher score = more consistent outputs
        """
        if not ratings or len(ratings) < 2:
            return 1.0
        
        mean = statistics.mean(ratings)
        if mean == 0:
            return 0.0
        
        std_dev = statistics.stdev(ratings)
        consistency = 1 - (std_dev / mean)
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, consistency))
    
    @staticmethod
    def calculate_quality_metrics(
        ratings: list[int],
        gold_star_count: int,
        base_model_wins: int = 0,
        fine_tuned_wins: int = 0,
        ties: int = 0,
        task_accuracy: float | None = None
    ) -> QualityMetrics:
        """
        Calculate comprehensive quality metrics.
        
        Args:
            ratings: List of ratings (1-5)
            gold_star_count: Number of gold star ratings
            base_model_wins: Number of times base model won
            fine_tuned_wins: Number of times fine-tuned model won
            ties: Number of ties
            task_accuracy: Optional task-specific accuracy
        
        Returns:
            QualityMetrics object
        """
        total_outputs = len(ratings)
        
        return QualityMetrics(
            win_rate=MetricsCalculator.calculate_win_rate(
                base_model_wins, fine_tuned_wins, ties
            ),
            gold_star_rate=MetricsCalculator.calculate_gold_star_rate(
                gold_star_count, total_outputs
            ),
            avg_rating=MetricsCalculator.calculate_avg_rating(ratings),
            consistency_score=MetricsCalculator.calculate_consistency_score(ratings),
            task_accuracy=task_accuracy
        )
    
    @staticmethod
    def calculate_performance_metrics(
        total_tokens: int,
        total_time_seconds: float,
        latency_ms: int,
        total_requests: int
    ) -> PerformanceMetrics:
        """
        Calculate performance metrics.
        
        Args:
            total_tokens: Total tokens generated
            total_time_seconds: Total time in seconds
            latency_ms: Time to first token in milliseconds
            total_requests: Total number of requests
        
        Returns:
            PerformanceMetrics object
        """
        tokens_per_second = total_tokens / total_time_seconds if total_time_seconds > 0 else 0
        throughput = total_requests / total_time_seconds if total_time_seconds > 0 else 0
        
        return PerformanceMetrics(
            tokens_per_second=tokens_per_second,
            latency_ms=latency_ms,
            throughput=throughput
        )
    
    @staticmethod
    def calculate_efficiency_metrics(
        model_size_mb: int,
        vram_usage_gb: float,
        cost_per_1m_tokens: float | None = None
    ) -> EfficiencyMetrics:
        """
        Calculate efficiency metrics.
        
        Args:
            model_size_mb: Model size in megabytes
            vram_usage_gb: VRAM usage in gigabytes
            cost_per_1m_tokens: Optional cost per 1M tokens
        
        Returns:
            EfficiencyMetrics object
        """
        return EfficiencyMetrics(
            model_size_mb=model_size_mb,
            vram_usage_gb=vram_usage_gb,
            cost_per_1m_tokens=cost_per_1m_tokens
        )
    
    @staticmethod
    def compare_models(
        base_metrics: dict[str, Any],
        fine_tuned_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compare two models and calculate improvement percentages.
        
        Args:
            base_metrics: Base model metrics
            fine_tuned_metrics: Fine-tuned model metrics
        
        Returns:
            Dictionary with comparison results
        """
        comparison = {}
        
        for key in base_metrics:
            base_value = base_metrics[key]
            fine_tuned_value = fine_tuned_metrics.get(key)
            
            if base_value is None or fine_tuned_value is None:
                comparison[key] = {
                    'base': base_value,
                    'fine_tuned': fine_tuned_value,
                    'improvement': None
                }
                continue
            
            # Calculate improvement percentage
            if base_value == 0:
                improvement = 0.0
            else:
                improvement = ((fine_tuned_value - base_value) / base_value) * 100
            
            comparison[key] = {
                'base': base_value,
                'fine_tuned': fine_tuned_value,
                'improvement': improvement,
                'better': fine_tuned_value > base_value
            }
        
        return comparison

