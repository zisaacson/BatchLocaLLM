"""
Aristotle Database Integration

Provides write access to Aristotle PostgreSQL database for syncing gold stars and VICTORY conquests.
This module enables bidirectional sync between Label Studio and Aristotle.

ARCHITECTURE:
- Connects to Aristotle PostgreSQL database (localhost:4002)
- Write operations for conquest.result and ml_analysis_rating
- Used by webhook handlers to sync gold stars

TABLES:
- Conquest: Main conquest table with result field
- ml_analysis_rating: Gold star ratings and feedback
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

# Connect to Aristotle PostgreSQL database
ARISTOTLE_DB_URL = os.getenv(
    'ARISTOTLE_DATABASE_URL',
    'postgresql://postgres:postgres@localhost:4002/aristotle_dev'
)

engine = create_engine(ARISTOTLE_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================================
# DATABASE MODELS
# ============================================================================

class MLAnalysisRating(Base):
    """
    Gold star ratings for conquests.
    
    This table stores human ratings and feedback for conquest analyses.
    When is_gold_star=true, the conquest is marked as high-quality training data.
    """
    __tablename__ = 'ml_analysis_rating'
    
    id = Column(String, primary_key=True)
    conquest_analysis_id = Column(String, nullable=False)  # FK to Conquest.id
    analysis_type = Column(String, nullable=False)  # 'conquest_analysis'
    
    # Rating fields
    rating = Column(Integer, nullable=True)  # 1-5 stars
    feedback = Column(Text, nullable=True)
    
    # Gold star flag
    is_gold_star = Column(Boolean, default=False, nullable=False)
    use_as_sample_response = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    philosopher = Column(String, nullable=False)  # User email
    domain = Column(String, nullable=False)  # Organization domain
    
    # Label Studio integration
    label_studio_task_id = Column(Integer, nullable=True)
    label_studio_annotation_id = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Conquest(Base):
    """
    Main conquest table.
    
    Stores conquest metadata including result field (PENDING, VICTORY, DEFEAT, NEUTRAL).
    """
    __tablename__ = 'Conquest'
    
    id = Column(String, primary_key=True)
    aristotleId = Column('aristotleId', String)
    conquestType = Column('conquestType', String)
    title = Column(String)
    description = Column(Text)
    
    # Result field - synced with gold stars
    result = Column(String, nullable=False, default='PENDING')  # PENDING, VICTORY, DEFEAT, NEUTRAL
    resultNotes = Column('resultNotes', Text)
    useAsExample = Column('useAsExample', Boolean, default=False)
    
    # Evaluation metadata
    evaluatedBy = Column('evaluatedBy', String)
    evaluatedAt = Column('evaluatedAt', DateTime)
    
    # Status
    status = Column(String, nullable=False, default='DRAFT')
    
    # Metadata
    philosopher = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    
    # Timestamps
    createdAt = Column('createdAt', DateTime, default=lambda: datetime.now(timezone.utc))
    updatedAt = Column('updatedAt', DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_aristotle_db() -> Session:
    """Get Aristotle database session."""
    return SessionLocal()


def mark_conquest_as_victory(
    conquest_id: str,
    evaluated_by: str,
    result_notes: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """
    Mark a conquest as VICTORY.
    
    Args:
        conquest_id: Conquest ID
        evaluated_by: User who marked it as victory
        result_notes: Optional notes about the victory
        db: Optional database session (creates new one if not provided)
    
    Returns:
        True if successful, False otherwise
    """
    should_close = db is None
    if db is None:
        db = get_aristotle_db()
    
    try:
        conquest = db.query(Conquest).filter(Conquest.id == conquest_id).first()
        
        if not conquest:
            logger.error(f"Conquest not found: {conquest_id}")
            return False
        
        # Update conquest result
        conquest.result = 'VICTORY'
        conquest.resultNotes = result_notes
        conquest.useAsExample = True
        conquest.evaluatedBy = evaluated_by
        conquest.evaluatedAt = datetime.now(timezone.utc)
        conquest.updatedAt = datetime.now(timezone.utc)
        
        db.commit()
        logger.info(f"✅ Marked conquest {conquest_id} as VICTORY")
        return True
        
    except Exception as e:
        logger.error(f"Failed to mark conquest as VICTORY: {e}")
        db.rollback()
        return False
    finally:
        if should_close:
            db.close()


def create_gold_star_rating(
    conquest_id: str,
    philosopher: str,
    domain: str,
    rating: int = 5,
    feedback: Optional[str] = None,
    label_studio_task_id: Optional[int] = None,
    label_studio_annotation_id: Optional[int] = None,
    db: Optional[Session] = None
) -> Optional[str]:
    """
    Create a gold star rating for a conquest.
    
    Args:
        conquest_id: Conquest ID
        philosopher: User email
        domain: Organization domain
        rating: Quality rating (1-5 stars)
        feedback: Optional feedback text
        label_studio_task_id: Label Studio task ID
        label_studio_annotation_id: Label Studio annotation ID
        db: Optional database session
    
    Returns:
        Rating ID if successful, None otherwise
    """
    should_close = db is None
    if db is None:
        db = get_aristotle_db()
    
    try:
        # Check if rating already exists
        existing = db.query(MLAnalysisRating).filter(
            MLAnalysisRating.conquest_analysis_id == conquest_id,
            MLAnalysisRating.philosopher == philosopher,
            MLAnalysisRating.domain == domain
        ).first()
        
        if existing:
            # Update existing rating
            existing.is_gold_star = True
            existing.use_as_sample_response = True
            existing.rating = rating
            existing.feedback = feedback
            existing.label_studio_task_id = label_studio_task_id
            existing.label_studio_annotation_id = label_studio_annotation_id
            existing.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            logger.info(f"✅ Updated gold star rating for conquest {conquest_id}")
            return existing.id
        
        # Create new rating
        rating_id = f"rating_{uuid.uuid4().hex[:12]}"
        
        new_rating = MLAnalysisRating(
            id=rating_id,
            conquest_analysis_id=conquest_id,
            analysis_type='conquest_analysis',
            rating=rating,
            feedback=feedback,
            is_gold_star=True,
            use_as_sample_response=True,
            philosopher=philosopher,
            domain=domain,
            label_studio_task_id=label_studio_task_id,
            label_studio_annotation_id=label_studio_annotation_id
        )
        
        db.add(new_rating)
        db.commit()
        
        logger.info(f"✅ Created gold star rating {rating_id} for conquest {conquest_id}")
        return rating_id
        
    except Exception as e:
        logger.error(f"Failed to create gold star rating: {e}")
        db.rollback()
        return None
    finally:
        if should_close:
            db.close()


def sync_gold_star_to_aristotle(
    conquest_id: str,
    philosopher: str,
    domain: str,
    rating: int = 5,
    feedback: Optional[str] = None,
    evaluated_by: Optional[str] = None,
    label_studio_task_id: Optional[int] = None,
    label_studio_annotation_id: Optional[int] = None
) -> bool:
    """
    Complete sync: Mark conquest as VICTORY and create gold star rating.
    
    This is the main function called by webhook handlers to sync gold stars
    from Label Studio to Aristotle.
    
    Args:
        conquest_id: Conquest ID
        philosopher: User email
        domain: Organization domain
        rating: Quality rating (1-5 stars)
        feedback: Optional feedback text
        evaluated_by: User who marked it as gold star
        label_studio_task_id: Label Studio task ID
        label_studio_annotation_id: Label Studio annotation ID
    
    Returns:
        True if successful, False otherwise
    """
    db = get_aristotle_db()
    
    try:
        # 1. Mark conquest as VICTORY
        victory_success = mark_conquest_as_victory(
            conquest_id=conquest_id,
            evaluated_by=evaluated_by or philosopher,
            result_notes=feedback,
            db=db
        )
        
        if not victory_success:
            return False
        
        # 2. Create gold star rating
        rating_id = create_gold_star_rating(
            conquest_id=conquest_id,
            philosopher=philosopher,
            domain=domain,
            rating=rating,
            feedback=feedback,
            label_studio_task_id=label_studio_task_id,
            label_studio_annotation_id=label_studio_annotation_id,
            db=db
        )
        
        if not rating_id:
            return False
        
        logger.info(f"🎉 Successfully synced gold star to Aristotle: conquest={conquest_id}, rating={rating_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync gold star to Aristotle: {e}")
        return False
    finally:
        db.close()

