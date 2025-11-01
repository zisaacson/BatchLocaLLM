"""
Database migration: Add workbench tables

Adds:
- datasets: Uploaded JSONL datasets
- benchmarks: Model runs on datasets
- annotations: Golden examples, fixes, flags
"""

from core.batch_app.database import Base, engine, SessionLocal
from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


def migrate():
    """Create workbench tables."""
    logger.info("Creating workbench tables...")
    
    # Import models to register them
    from core.batch_app.database import Dataset, Benchmark, Annotation
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ Workbench tables created successfully!")
    
    # Verify tables exist
    db = SessionLocal()
    try:
        # Test queries
        datasets = db.query(Dataset).count()
        benchmarks = db.query(Benchmark).count()
        annotations = db.query(Annotation).count()
        
        logger.info(f"Datasets: {datasets}")
        logger.info(f"Benchmarks: {benchmarks}")
        logger.info(f"Annotations: {annotations}")
        
    finally:
        db.close()


if __name__ == "__main__":
    migrate()

