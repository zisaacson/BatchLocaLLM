#!/usr/bin/env python3
"""
Database migration: Add webhook configuration fields to batch_jobs table.

Adds:
- webhook_secret: Per-webhook HMAC secret for signature verification
- webhook_max_retries: Custom retry count per webhook
- webhook_timeout: Custom timeout in seconds per webhook
- webhook_events: Comma-separated list of events to subscribe to

Run with:
    python tools/add_webhook_fields.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from core.batch_app.database import SessionLocal, engine


def add_webhook_fields():
    """Add webhook configuration fields to batch_jobs table."""
    db = SessionLocal()
    
    try:
        # Check if columns already exist
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'batch_jobs' 
            AND column_name IN ('webhook_secret', 'webhook_max_retries', 'webhook_timeout', 'webhook_events')
        """))
        existing_columns = {row[0] for row in result}
        
        if len(existing_columns) == 4:
            print("✅ All webhook fields already exist in batch_jobs table")
            return
        
        print(f"📝 Adding webhook configuration fields to batch_jobs table...")
        
        # Add webhook_secret column
        if 'webhook_secret' not in existing_columns:
            db.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN webhook_secret VARCHAR(128)
            """))
            print("  ✅ Added webhook_secret column")
        
        # Add webhook_max_retries column
        if 'webhook_max_retries' not in existing_columns:
            db.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN webhook_max_retries INTEGER
            """))
            print("  ✅ Added webhook_max_retries column")
        
        # Add webhook_timeout column
        if 'webhook_timeout' not in existing_columns:
            db.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN webhook_timeout INTEGER
            """))
            print("  ✅ Added webhook_timeout column")
        
        # Add webhook_events column
        if 'webhook_events' not in existing_columns:
            db.execute(text("""
                ALTER TABLE batch_jobs 
                ADD COLUMN webhook_events VARCHAR(256)
            """))
            print("  ✅ Added webhook_events column")
        
        db.commit()
        print("✅ Migration complete!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Add Webhook Configuration Fields")
    print("=" * 60)
    add_webhook_fields()

