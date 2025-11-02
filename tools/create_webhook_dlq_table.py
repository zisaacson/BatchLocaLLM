#!/usr/bin/env python3
"""
Database migration: Create webhook_dead_letter table.

Creates a table to track failed webhook deliveries for manual inspection and retry.

Run with:
    python tools/create_webhook_dlq_table.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from core.batch_app.database import SessionLocal, engine, Base, WebhookDeadLetter


def create_webhook_dlq_table():
    """Create webhook_dead_letter table if it doesn't exist."""
    db = SessionLocal()
    
    try:
        # Check if table exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'webhook_dead_letter'
            )
        """))
        table_exists = result.scalar()
        
        if table_exists:
            print("✅ webhook_dead_letter table already exists")
            return
        
        print(f"📝 Creating webhook_dead_letter table...")
        
        # Create table using SQLAlchemy
        Base.metadata.create_all(bind=engine, tables=[WebhookDeadLetter.__table__])
        
        print("  ✅ Created webhook_dead_letter table")
        print("✅ Migration complete!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration: Create Webhook Dead Letter Queue Table")
    print("=" * 60)
    create_webhook_dlq_table()

