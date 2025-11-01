#!/usr/bin/env python3
"""
Migration script to add new columns to worker_heartbeat table.

New columns:
- loaded_model: Track what model is currently loaded in GPU
- model_loaded_at: When the model was loaded
- worker_pid: Process ID of the worker
- worker_started_at: When the worker process started

Run this before starting the updated worker/API.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.batch_app.database import SessionLocal, engine

def migrate():
    """Add new columns to worker_heartbeat table."""
    print("🔄 Migrating worker_heartbeat table...")
    
    db = SessionLocal()
    
    try:
        # Check if columns already exist
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'worker_heartbeat'
        """))
        existing_columns = {row[0] for row in result}
        
        migrations_needed = []
        
        # Check each new column
        if 'loaded_model' not in existing_columns:
            migrations_needed.append(
                "ALTER TABLE worker_heartbeat ADD COLUMN loaded_model VARCHAR(256)"
            )
        
        if 'model_loaded_at' not in existing_columns:
            migrations_needed.append(
                "ALTER TABLE worker_heartbeat ADD COLUMN model_loaded_at TIMESTAMP"
            )
        
        if 'worker_pid' not in existing_columns:
            migrations_needed.append(
                "ALTER TABLE worker_heartbeat ADD COLUMN worker_pid INTEGER"
            )
        
        if 'worker_started_at' not in existing_columns:
            migrations_needed.append(
                "ALTER TABLE worker_heartbeat ADD COLUMN worker_started_at TIMESTAMP"
            )
        
        if not migrations_needed:
            print("✅ All columns already exist. No migration needed.")
            return
        
        # Run migrations
        print(f"📝 Running {len(migrations_needed)} migrations...")
        for i, migration in enumerate(migrations_needed, 1):
            print(f"   {i}. {migration}")
            db.execute(text(migration))
        
        db.commit()
        print("✅ Migration complete!")
        
        # Verify
        result = db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'worker_heartbeat'
            ORDER BY ordinal_position
        """))
        
        print("\n📊 Current worker_heartbeat schema:")
        for row in result:
            print(f"   - {row[0]}: {row[1]}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

