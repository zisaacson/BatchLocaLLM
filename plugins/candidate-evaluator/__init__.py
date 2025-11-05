"""
Candidate Evaluator Plugin

Provides comprehensive candidate evaluation workflow with:
- Structured candidate data parsing
- Categorical rating system
- Custom curation UI
- Quality-based export filtering
"""

from core.plugins.base import (
    Plugin,
    SchemaPlugin,
    ParserPlugin,
    UIPlugin,
    ExportPlugin,
    RatingPlugin,
)
from typing import Any, Dict, List
import re
import json


class CandidateEvaluatorPlugin(
    SchemaPlugin,
    ParserPlugin,
    UIPlugin,
    ExportPlugin,
    RatingPlugin
):
    """
    Complete candidate evaluation plugin
    
    Combines schema, parser, UI, export, and rating functionality
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rating_categories = config.get("rating_categories", {})
        self.rating_display = config.get("rating_display", {})
        self.export_thresholds = config.get("export_thresholds", {})
    
    # Plugin base methods
    
    def get_id(self) -> str:
        return "candidate-evaluator"
    
    def get_name(self) -> str:
        return "Candidate Evaluator"
    
    # SchemaPlugin methods
    
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for candidate evaluation"""
        return {
            "type": "object",
            "properties": {
                "candidate": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "company": {"type": "string"},
                        "linkedin_url": {"type": "string"}
                    },
                    "required": ["name"]
                },
                "evaluation": {
                    "type": "object",
                    "properties": {
                        "recommendation": {
                            "enum": self.rating_categories.get("recommendation", [])
                        },
                        "trajectory_rating": {
                            "enum": self.rating_categories.get("trajectory", [])
                        },
                        "company_pedigree": {
                            "enum": self.rating_categories.get("company_pedigree", [])
                        },
                        "educational_pedigree": {
                            "enum": self.rating_categories.get("educational_pedigree", [])
                        },
                        "is_software_engineer": {"type": "boolean"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["recommendation"]
                }
            }
        }
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate candidate data against schema"""
        if "candidate" not in data:
            return False
        if "name" not in data["candidate"]:
            return False
        if "evaluation" in data:
            rec = data["evaluation"].get("recommendation")
            if rec and rec not in self.rating_categories.get("recommendation", []):
                return False
        return True
    
    # ParserPlugin methods
    
    def parse_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured candidate data
        
        Handles multiple formats:
        - Markdown with **Candidate:** headers
        - JSON responses
        - Plain text with patterns
        """
        # Try JSON first
        try:
            data = json.loads(response)
            if "candidate" in data or "evaluation" in data:
                return data
        except:
            pass
        
        # Parse markdown/text format
        result = {
            "candidate": {},
            "evaluation": {}
        }
        
        # Extract candidate info
        name_match = re.search(r'\*\*(?:Candidate|Name):\*\*\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if name_match:
            result["candidate"]["name"] = name_match.group(1).strip()
        
        title_match = re.search(r'\*\*Title:\*\*\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if title_match:
            result["candidate"]["title"] = title_match.group(1).strip()
        
        company_match = re.search(r'\*\*Company:\*\*\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if company_match:
            result["candidate"]["company"] = company_match.group(1).strip()
        
        linkedin_match = re.search(r'\*\*LinkedIn:\*\*\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        if linkedin_match:
            result["candidate"]["linkedin_url"] = linkedin_match.group(1).strip()
        
        # Extract ratings
        rec_pattern = r'(?:Recommendation|Overall):\s*(Strong Yes|Yes|Maybe|No|Strong No)'
        rec_match = re.search(rec_pattern, response, re.IGNORECASE)
        if rec_match:
            result["evaluation"]["recommendation"] = rec_match.group(1)
        
        traj_pattern = r'(?:Trajectory|Career Trajectory):\s*(Exceptional|Strong|Good|Average|Weak)'
        traj_match = re.search(traj_pattern, response, re.IGNORECASE)
        if traj_match:
            result["evaluation"]["trajectory_rating"] = traj_match.group(1)
        
        comp_pattern = r'Company Pedigree:\s*(Exceptional|Strong|Good|Average|Weak)'
        comp_match = re.search(comp_pattern, response, re.IGNORECASE)
        if comp_match:
            result["evaluation"]["company_pedigree"] = comp_match.group(1)
        
        edu_pattern = r'Educational Pedigree:\s*(Exceptional|Strong|Good|Average|Weak)'
        edu_match = re.search(edu_pattern, response, re.IGNORECASE)
        if edu_match:
            result["evaluation"]["educational_pedigree"] = edu_match.group(1)
        
        # Extract software engineer flag
        se_pattern = r'(?:is_software_engineer|Software Engineer):\s*(true|false|yes|no)'
        se_match = re.search(se_pattern, response, re.IGNORECASE)
        if se_match:
            value = se_match.group(1).lower()
            result["evaluation"]["is_software_engineer"] = value in ["true", "yes"]
        
        # Extract reasoning
        reasoning_match = re.search(r'(?:Reasoning|Explanation):\s*(.+?)(?:\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            result["evaluation"]["reasoning"] = reasoning_match.group(1).strip()
        
        return result
    
    def extract_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract display fields for table view"""
        candidate = data.get("candidate", {})
        evaluation = data.get("evaluation", {})
        
        return {
            "name": candidate.get("name", "Unknown"),
            "title": candidate.get("title", ""),
            "company": candidate.get("company", ""),
            "recommendation": evaluation.get("recommendation", ""),
            "trajectory": evaluation.get("trajectory_rating", ""),
            "is_software_engineer": evaluation.get("is_software_engineer", False)
        }
    
    # UIPlugin methods
    
    def get_ui_routes(self) -> List[Dict[str, str]]:
        """Return UI routes provided by this plugin"""
        return [
            {"path": "/candidate-curation", "file": "ui/curation.html"},
            {"path": "/candidate-table", "file": "ui/table-view.html"}
        ]
    
    def get_ui_components(self) -> List[str]:
        """Return UI component IDs"""
        return [
            "candidate-card",
            "rating-widget",
            "candidate-table-row"
        ]
    
    # ExportPlugin methods
    
    def export(self, tasks: List[Dict[str, Any]], format: str, **kwargs) -> str:
        """Export tasks in specified format with quality filtering"""
        threshold_config = self.export_thresholds.get(format, {})
        min_rec = threshold_config.get("min_recommendation")
        
        # Filter by recommendation if threshold specified
        if min_rec:
            filtered_tasks = self.filter_by_recommendation(tasks, min_rec)
        else:
            filtered_tasks = tasks
        
        # Export as JSONL
        lines = []
        for task in filtered_tasks:
            lines.append(json.dumps(task))
        
        return "\n".join(lines)
    
    def get_export_formats(self) -> List[Dict[str, Any]]:
        """Return supported export formats"""
        return [
            {
                "id": "icl",
                "name": "In-Context Learning",
                "description": self.export_thresholds["icl"]["description"]
            },
            {
                "id": "finetuning",
                "name": "Fine-tuning Dataset",
                "description": self.export_thresholds["finetuning"]["description"]
            },
            {
                "id": "raw",
                "name": "Raw Data",
                "description": self.export_thresholds["raw"]["description"]
            }
        ]
    
    def filter_by_recommendation(self, tasks: List[Dict[str, Any]], min_rec: str) -> List[Dict[str, Any]]:
        """Filter tasks by minimum recommendation level"""
        rec_order = self.rating_categories.get("recommendation", [])
        if min_rec not in rec_order:
            return tasks
        
        min_index = rec_order.index(min_rec)
        
        filtered = []
        for task in tasks:
            rec = task.get("result", {}).get("evaluation", {}).get("recommendation")
            if rec and rec in rec_order:
                if rec_order.index(rec) <= min_index:
                    filtered.append(task)
        
        return filtered
    
    # RatingPlugin methods
    
    def get_rating_categories(self) -> Dict[str, List[str]]:
        """Return rating categories"""
        return self.rating_categories
    
    def validate_rating(self, category: str, value: str) -> bool:
        """Validate rating value"""
        categories = self.rating_categories.get(category, [])
        return value in categories
    
    def get_rating_display(self, category: str, value: str) -> Dict[str, str]:
        """Get display properties for rating"""
        display_config = self.rating_display.get(category, {}).get(value, {})
        return {
            "color": display_config.get("color", "#6c757d"),
            "icon": display_config.get("icon", ""),
            "label": value,
            "badge_class": display_config.get("badge_class", "")
        }

