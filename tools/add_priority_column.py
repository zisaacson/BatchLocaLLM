"""
Database migration: Add priority column to batch_jobs table.

This migration adds a priority field to support priority queue processing:
- -1 = low priority (testing/benchmarking)
-  0 = normal priority (default)
-  1 = high priority (production)

Run with: python tools/add_priority_column.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.batch_app.database import SessionLocal, engine


def add_priority_column():
    """Add priority column to batch_jobs table."""
    db = SessionLocal()
    
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='batch_jobs' AND column_name='priority'
        """))
        
        if result.fetchone():
            print("✅ Priority column already exists")
            return
        
        # Add priority column with default value 0 (normal priority)
        print("Adding priority column to batch_jobs table...")
        db.execute(text("""
            ALTER TABLE batch_jobs 
            ADD COLUMN priority INTEGER DEFAULT 0 NOT NULL
        """))
        db.commit()
        
        print("✅ Priority column added successfully")
        print("   - Default value: 0 (normal priority)")
        print("   - All existing jobs now have priority=0")
        
    except Exception as e:
        print(f"❌ Error adding priority column: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Add Priority Column")
    print("=" * 60)
    
    add_priority_column()
    
    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)

