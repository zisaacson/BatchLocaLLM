"""
Core integrations module.

Provides integration with external systems:
- Aristotle database (conquest management)
- Label Studio (annotation and curation)
"""

from .aristotle_db import (
    get_aristotle_db,
    mark_conquest_as_victory,
    create_gold_star_rating,
    sync_gold_star_to_aristotle,
    Conquest,
    MLAnalysisRating,
)

__all__ = [
    'get_aristotle_db',
    'mark_conquest_as_victory',
    'create_gold_star_rating',
    'sync_gold_star_to_aristotle',
    'Conquest',
    'MLAnalysisRating',
]

