#!/usr/bin/env python3
"""Add progress tracking fields to BatchJob table."""

from sqlalchemy import text
from core.batch_app.database import engine

def migrate():
    """Add progress tracking fields."""
    
    with engine.connect() as conn:
        # Add tokens_processed field
        try:
            conn.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN tokens_processed BIGINT DEFAULT 0
            """))
            print("✅ Added tokens_processed column")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️  tokens_processed column already exists")
            else:
                raise
        
        # Add current_throughput field (real-time tok/s)
        try:
            conn.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN current_throughput FLOAT DEFAULT 0.0
            """))
            print("✅ Added current_throughput column")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️  current_throughput column already exists")
            else:
                raise
        
        # Add queue_position field
        try:
            conn.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN queue_position INTEGER DEFAULT NULL
            """))
            print("✅ Added queue_position column")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️  queue_position column already exists")
            else:
                raise
        
        # Add last_progress_update timestamp
        try:
            conn.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN last_progress_update TIMESTAMP DEFAULT NULL
            """))
            print("✅ Added last_progress_update column")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️  last_progress_update column already exists")
            else:
                raise
        
        # Add estimated_completion_time
        try:
            conn.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN estimated_completion_time TIMESTAMP DEFAULT NULL
            """))
            print("✅ Added estimated_completion_time column")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("⏭️  estimated_completion_time column already exists")
            else:
                raise
        
        conn.commit()
        print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()

