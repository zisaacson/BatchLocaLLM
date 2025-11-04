#!/usr/bin/env python3
"""
Database migration: Add fine-tuning tables.

Creates tables for:
- fine_tuned_models: Model registry with metrics
- training_jobs: Training job tracking
- model_comparisons: A/B testing results
- deployment_history: Deployment tracking for rollback

Run with:
    python scripts/migrate_add_fine_tuning_tables.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.batch_app.database import engine, Base, FineTunedModel, TrainingJob, ModelComparison, DeploymentHistory


def migrate():
    """Create fine-tuning tables."""
    print("🔧 Creating fine-tuning tables...")
    
    # Create tables
    Base.metadata.create_all(engine, tables=[
        FineTunedModel.__table__,
        TrainingJob.__table__,
        ModelComparison.__table__,
        DeploymentHistory.__table__
    ])
    
    print("✅ Fine-tuning tables created successfully!")
    
    # Verify tables exist
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('fine_tuned_models', 'training_jobs', 'model_comparisons', 'deployment_history')
            ORDER BY table_name
        """))
        tables = [row[0] for row in result]
        
        print(f"\n📊 Created tables: {', '.join(tables)}")
        
        if len(tables) == 4:
            print("✅ All 4 tables created successfully!")
        else:
            print(f"⚠️  Warning: Expected 4 tables, found {len(tables)}")


if __name__ == "__main__":
    migrate()

