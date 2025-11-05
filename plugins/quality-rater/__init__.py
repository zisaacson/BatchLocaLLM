"""
Quality Rater Plugin - Generic quality rating system for LLM outputs.

Supports multiple rating scales:
- Numeric (1-10)
- Categorical (Excellent/Good/Fair/Poor/Unusable)
- Binary (Accept/Reject)

Features:
- Gold star marking for exceptional examples
- Bulk rating operations
- Quality-based filtering and export
- Rating history tracking
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from core.plugins.base import RatingPlugin, ExportPlugin, UIPlugin


class QualityRaterPlugin(RatingPlugin, ExportPlugin, UIPlugin):
    """Generic quality rating plugin for any use case."""
    
    def __init__(self):
        self.id = "quality-rater"
        self.name = "Quality Rater"
        self.version = "1.0.0"
        
        # Load config from plugin.json
        self.rating_scales = {
            "numeric": {"min": 1, "max": 10, "step": 1},
            "categorical": ["Excellent", "Good", "Fair", "Poor", "Unusable"],
            "binary": ["Accept", "Reject"]
        }
        
        self.export_thresholds = {
            "high_quality": {"numeric": 7, "categorical": "Good", "binary": "Accept"},
            "low_quality": {"numeric": 4, "categorical": "Fair", "binary": "Reject"}
        }
    
    # ===== RatingPlugin Methods =====
    
    def get_rating_categories(self) -> Dict[str, List[str]]:
        """Return available rating categories."""
        return {
            "quality": self.rating_scales["categorical"],
            "numeric_quality": [str(i) for i in range(1, 11)],
            "binary_quality": self.rating_scales["binary"]
        }
    
    def validate_rating(self, rating: Dict[str, Any]) -> bool:
        """Validate a rating submission."""
        scale_type = rating.get("scale_type", "categorical")
        value = rating.get("value")
        
        if scale_type == "numeric":
            try:
                num_value = int(value)
                return 1 <= num_value <= 10
            except (ValueError, TypeError):
                return False
        
        elif scale_type == "categorical":
            return value in self.rating_scales["categorical"]
        
        elif scale_type == "binary":
            return value in self.rating_scales["binary"]
        
        return False
    
    def calculate_rating_score(self, rating: Dict[str, Any]) -> float:
        """Convert rating to numeric score (0-1) for comparison."""
        scale_type = rating.get("scale_type", "categorical")
        value = rating.get("value")
        
        if scale_type == "numeric":
            return int(value) / 10.0
        
        elif scale_type == "categorical":
            scale = self.rating_scales["categorical"]
            if value in scale:
                # Reverse index (Excellent=1.0, Unusable=0.0)
                return 1.0 - (scale.index(value) / (len(scale) - 1))
            return 0.5
        
        elif scale_type == "binary":
            return 1.0 if value == "Accept" else 0.0
        
        return 0.5
    
    def get_rating_display(self, rating: Dict[str, Any]) -> Dict[str, str]:
        """Get display properties for a rating."""
        scale_type = rating.get("scale_type", "categorical")
        value = rating.get("value")
        
        # Color mapping
        colors = {
            "Excellent": "green", "Accept": "green",
            "Good": "blue",
            "Fair": "yellow",
            "Poor": "orange",
            "Unusable": "red", "Reject": "red"
        }
        
        # Icon mapping
        icons = {
            "Excellent": "⭐", "Accept": "✅",
            "Good": "👍",
            "Fair": "👌",
            "Poor": "👎",
            "Unusable": "❌", "Reject": "❌"
        }
        
        if scale_type == "numeric":
            num_value = int(value)
            if num_value >= 9:
                color, icon = "green", "⭐"
            elif num_value >= 7:
                color, icon = "blue", "👍"
            elif num_value >= 4:
                color, icon = "yellow", "👌"
            else:
                color, icon = "red", "👎"
        else:
            color = colors.get(value, "gray")
            icon = icons.get(value, "•")
        
        return {
            "color": color,
            "icon": icon,
            "badge_class": f"badge-{color}",
            "text": str(value)
        }
    
    # ===== ExportPlugin Methods =====
    
    def export(self, tasks: List[Dict[str, Any]], format: str, options: Dict[str, Any]) -> bytes:
        """Export tasks filtered by quality."""
        scale_type = options.get("scale_type", "categorical")
        
        # Filter by quality threshold
        if format == "high-quality":
            threshold = self.export_thresholds["high_quality"][scale_type]
            filtered = self.filter_by_quality(tasks, threshold, scale_type, min_quality=True)
        elif format == "low-quality":
            threshold = self.export_thresholds["low_quality"][scale_type]
            filtered = self.filter_by_quality(tasks, threshold, scale_type, min_quality=False)
        else:  # all
            filtered = tasks
        
        # Export as JSONL
        import json
        lines = [json.dumps(task) for task in filtered]
        return "\n".join(lines).encode('utf-8')
    
    def get_export_formats(self) -> List[str]:
        """Return available export formats."""
        return ["high-quality", "low-quality", "all"]
    
    def filter_by_quality(
        self, 
        tasks: List[Dict[str, Any]], 
        threshold: Any, 
        scale_type: str,
        min_quality: bool = True
    ) -> List[Dict[str, Any]]:
        """Filter tasks by quality threshold."""
        filtered = []
        
        for task in tasks:
            rating = task.get("rating", {})
            if not rating:
                continue
            
            value = rating.get("value")
            task_scale = rating.get("scale_type", "categorical")
            
            if task_scale != scale_type:
                continue
            
            # Compare based on scale type
            if scale_type == "numeric":
                passes = (int(value) >= threshold) if min_quality else (int(value) <= threshold)
            elif scale_type == "categorical":
                scale = self.rating_scales["categorical"]
                value_idx = scale.index(value) if value in scale else -1
                threshold_idx = scale.index(threshold) if threshold in scale else -1
                passes = (value_idx <= threshold_idx) if min_quality else (value_idx >= threshold_idx)
            elif scale_type == "binary":
                passes = (value == threshold) if min_quality else (value != threshold)
            else:
                passes = False
            
            if passes:
                filtered.append(task)
        
        return filtered
    
    # ===== UIPlugin Methods =====
    
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """Return UI routes for this plugin."""
        return [
            {"path": "/quality-rater", "template": "plugins/quality-rater/ui/rating.html"},
            {"path": "/quality-dashboard", "template": "plugins/quality-rater/ui/dashboard.html"}
        ]
    
    def get_ui_components(self) -> List[Dict[str, str]]:
        """Return embeddable UI components."""
        return [
            {
                "id": "rating-widget",
                "template": "plugins/quality-rater/ui/components/rating-widget.html",
                "description": "Embeddable rating widget"
            },
            {
                "id": "quality-stats",
                "template": "plugins/quality-rater/ui/components/quality-stats.html",
                "description": "Quality statistics display"
            }
        ]
    
    # ===== Helper Methods =====
    
    def get_rating_statistics(self, tasks: List[Dict[str, Any]], scale_type: str = "categorical") -> Dict[str, Any]:
        """Calculate rating statistics for a set of tasks."""
        ratings = [task.get("rating", {}) for task in tasks if task.get("rating")]
        ratings = [r for r in ratings if r.get("scale_type") == scale_type]
        
        if not ratings:
            return {"total": 0, "distribution": {}, "average_score": 0.0}
        
        # Count distribution
        distribution = {}
        scores = []
        
        for rating in ratings:
            value = rating.get("value")
            distribution[value] = distribution.get(value, 0) + 1
            scores.append(self.calculate_rating_score(rating))
        
        return {
            "total": len(ratings),
            "distribution": distribution,
            "average_score": sum(scores) / len(scores) if scores else 0.0,
            "scale_type": scale_type
        }


# Plugin instance
plugin = QualityRaterPlugin()

