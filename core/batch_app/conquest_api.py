"""
Conquest API Endpoints for vLLM Batch Server

Provides read-only access to conquest data from Aristotle PostgreSQL database.
Allows viewing and annotating conquests from the vLLM web app.

ARCHITECTURE:
- Connects to Aristotle PostgreSQL database (localhost:4002)
- Read-only queries for conquest data
- Annotation sync to Label Studio
- No write access to conquest data (read-only viewer)

ENDPOINTS:
- GET /v1/conquests - List conquests with filtering
- GET /v1/conquests/{id} - Get conquest details
- POST /v1/conquests/{id}/annotate - Create annotation (syncs to Label Studio)
"""

import os
from datetime import datetime
from typing import List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import enum

from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)

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
# DATABASE MODELS (Read-Only)
# ============================================================================

class ConquestStatus(str, enum.Enum):
    DRAFT = 'DRAFT'
    DOWNLOADING_INFO = 'DOWNLOADING_INFO'
    ANALYZING = 'ANALYZING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

class ConquestResult(str, enum.Enum):
    PENDING = 'PENDING'
    VICTORY = 'VICTORY'
    DEFEAT = 'DEFEAT'
    NEUTRAL = 'NEUTRAL'

class ConquestType(str, enum.Enum):
    CANDIDATE = 'CANDIDATE'
    CARTOGRAPHER = 'CARTOGRAPHER'
    CV_PARSING = 'CV_PARSING'
    SLACK_ANALYSIS = 'SLACK_ANALYSIS'
    EMAIL_RESPONSE = 'EMAIL_RESPONSE'
    EIDOS_DISCOVERY = 'EIDOS_DISCOVERY'
    CUSTOM = 'CUSTOM'

class Conquest(Base):
    """Read-only model for Conquest table"""
    __tablename__ = 'Conquest'

    id = Column(String, primary_key=True)
    aristotleId = Column('aristotleId', String)
    conquestType = Column('conquestType', SQLEnum(ConquestType))
    title = Column(String)
    description = Column(Text)
    eidosId = Column('eidosId', String)
    fineTunedModelId = Column('fineTunedModelId', String)
    status = Column(SQLEnum(ConquestStatus))
    result = Column(SQLEnum(ConquestResult))
    resultNotes = Column('resultNotes', Text)
    useAsExample = Column('useAsExample', Boolean)
    evaluatedBy = Column('evaluatedBy', String)
    evaluatedAt = Column('evaluatedAt', DateTime)
    startedAt = Column('startedAt', DateTime)
    completedAt = Column('completedAt', DateTime)
    executionTimeMs = Column('executionTimeMs', Integer)
    philosopher = Column(String)
    domain = Column(String)
    createdAt = Column('createdAt', DateTime)
    updatedAt = Column('updatedAt', DateTime)

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class ConquestListItem(BaseModel):
    """Conquest list item (summary)"""
    id: str
    title: str
    conquestType: str
    status: str
    result: str
    useAsExample: bool
    evaluatedBy: Optional[str] = None
    evaluatedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    executionTimeMs: Optional[int] = None
    philosopher: str
    domain: str
    createdAt: datetime

    class Config:
        from_attributes = True

class ConquestDetail(BaseModel):
    """Conquest detail (full)"""
    id: str
    aristotleId: Optional[str] = None
    conquestType: str
    title: str
    description: Optional[str] = None
    eidosId: Optional[str] = None
    fineTunedModelId: Optional[str] = None
    status: str
    result: str
    resultNotes: Optional[str] = None
    useAsExample: bool
    evaluatedBy: Optional[str] = None
    evaluatedAt: Optional[datetime] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    executionTimeMs: Optional[int] = None
    philosopher: str
    domain: str
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True

class ConquestListResponse(BaseModel):
    """Response for list conquests endpoint"""
    conquests: List[ConquestListItem]
    total: int
    limit: int
    offset: int

class AnnotationRequest(BaseModel):
    """Request to annotate a conquest"""
    isGoldStar: bool = Field(description="Mark as gold star for training")
    rating: int = Field(ge=1, le=5, description="Quality rating (1-5 stars)")
    feedback: Optional[str] = Field(None, description="Feedback text")
    improvementNotes: Optional[str] = Field(None, description="Improvement notes")

class AnnotationResponse(BaseModel):
    """Response for annotation endpoint"""
    success: bool
    message: str
    conquestId: str
    annotationId: Optional[str] = None

# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/v1/conquests", tags=["conquests"])

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=ConquestListResponse)
async def list_conquests(
    status: Optional[str] = Query(None, description="Filter by status"),
    result: Optional[str] = Query(None, description="Filter by result"),
    conquestType: Optional[str] = Query(None, description="Filter by conquest type"),
    useAsExample: Optional[bool] = Query(None, description="Filter by useAsExample"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    List conquests with optional filtering
    
    Query Parameters:
    - status: Filter by status (DRAFT, ANALYZING, COMPLETED, FAILED, CANCELLED)
    - result: Filter by result (PENDING, VICTORY, DEFEAT, NEUTRAL)
    - conquestType: Filter by type (CANDIDATE, CARTOGRAPHER, etc.)
    - useAsExample: Filter by useAsExample flag
    - limit: Max results (default 100, max 1000)
    - offset: Pagination offset (default 0)
    """
    db = next(get_db())
    
    try:
        # Build query
        query = db.query(Conquest)
        
        # Apply filters
        if status:
            query = query.filter(Conquest.status == status)
        if result:
            query = query.filter(Conquest.result == result)
        if conquestType:
            query = query.filter(Conquest.conquestType == conquestType)
        if useAsExample is not None:
            query = query.filter(Conquest.useAsExample == useAsExample)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        conquests = query.order_by(Conquest.createdAt.desc()).limit(limit).offset(offset).all()
        
        logger.info(f"Listed {len(conquests)} conquests (total: {total})", extra={
            "status": status,
            "result": result,
            "conquestType": conquestType,
            "useAsExample": useAsExample,
            "limit": limit,
            "offset": offset
        })
        
        return ConquestListResponse(
            conquests=[ConquestListItem.from_orm(c) for c in conquests],
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Failed to list conquests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list conquests: {str(e)}")
    finally:
        db.close()

@router.get("/{conquest_id}", response_model=ConquestDetail)
async def get_conquest(conquest_id: str):
    """
    Get conquest details by ID
    
    Path Parameters:
    - conquest_id: Conquest ID
    """
    db = next(get_db())
    
    try:
        conquest = db.query(Conquest).filter(Conquest.id == conquest_id).first()
        
        if not conquest:
            raise HTTPException(status_code=404, detail=f"Conquest not found: {conquest_id}")
        
        logger.info(f"Retrieved conquest {conquest_id}")
        
        return ConquestDetail.from_orm(conquest)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conquest {conquest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get conquest: {str(e)}")
    finally:
        db.close()

@router.post("/{conquest_id}/annotate", response_model=AnnotationResponse)
async def annotate_conquest(conquest_id: str, annotation: AnnotationRequest):
    """
    Annotate a conquest (creates annotation in Label Studio)
    
    Path Parameters:
    - conquest_id: Conquest ID
    
    Request Body:
    - isGoldStar: Mark as gold star for training
    - rating: Quality rating (1-5 stars)
    - feedback: Optional feedback text
    - improvementNotes: Optional improvement notes
    
    Note: This endpoint creates an annotation in Label Studio.
    The annotation will sync back to Aristotle via webhook.
    """
    db = next(get_db())
    
    try:
        # Verify conquest exists
        conquest = db.query(Conquest).filter(Conquest.id == conquest_id).first()
        
        if not conquest:
            raise HTTPException(status_code=404, detail=f"Conquest not found: {conquest_id}")
        
        # TODO: Create annotation in Label Studio
        # For now, just log the annotation
        logger.info(f"Annotation created for conquest {conquest_id}", extra={
            "isGoldStar": annotation.isGoldStar,
            "rating": annotation.rating,
            "feedback": annotation.feedback
        })
        
        return AnnotationResponse(
            success=True,
            message="Annotation created successfully (Label Studio integration pending)",
            conquestId=conquest_id,
            annotationId=None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to annotate conquest {conquest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to annotate conquest: {str(e)}")
    finally:
        db.close()

