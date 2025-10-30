#!/usr/bin/env python3
"""
Database migration script to add webhook and metadata columns.

Run this to upgrade existing database to support webhooks.
"""

import sqlite3
from pathlib import Path

# Try multiple possible database locations
DB_PATHS = [
    "data/database/batch_jobs.db",
    "data/batch_jobs.db",
    "data/vllm_batch.db"
]

def find_database():
    """Find the database file."""
    for path in DB_PATHS:
        if Path(path).exists():
            return path
    return None

DB_PATH = find_database()


def migrate():
    """Add webhook and metadata columns to batch_jobs table."""

    if not DB_PATH:
        print(f"❌ Database not found in any of these locations:")
        for path in DB_PATHS:
            print(f"   - {path}")
        print("   Run the API server first to create the database.")
        return

    print(f"📁 Found database at: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(batch_jobs)")
    columns = [row[1] for row in cursor.fetchall()]
    
    migrations_needed = []
    
    if 'webhook_url' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN webhook_url VARCHAR(512)")
    
    if 'webhook_status' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN webhook_status VARCHAR(32)")
    
    if 'webhook_attempts' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN webhook_attempts INTEGER DEFAULT 0")
    
    if 'webhook_last_attempt' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN webhook_last_attempt DATETIME")
    
    if 'webhook_error' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN webhook_error TEXT")
    
    if 'metadata_json' not in columns:
        migrations_needed.append("ALTER TABLE batch_jobs ADD COLUMN metadata_json TEXT")
    
    if not migrations_needed:
        print("✅ Database is already up to date!")
        conn.close()
        return
    
    print(f"🔧 Running {len(migrations_needed)} migrations...")
    
    for migration in migrations_needed:
        print(f"   {migration}")
        cursor.execute(migration)
    
    conn.commit()
    conn.close()
    
    print("✅ Database migration complete!")


if __name__ == "__main__":
    migrate()

