#!/usr/bin/env python3
"""
Add GGUF-specific fields to ModelRegistry table.

Adds:
- local_path: Path to downloaded GGUF file
- quantization_type: Q4_0, Q2_K, FP16, etc.
"""

from sqlalchemy import text
from core.batch_app.database import SessionLocal

def migrate():
    """Add GGUF fields to model_registry table."""

    db = SessionLocal()

    try:
        # Check if columns already exist
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'model_registry'
        """))
        columns = [row[0] for row in result]

        # Add local_path if it doesn't exist
        if 'local_path' not in columns:
            print("Adding local_path column...")
            db.execute(text("""
                ALTER TABLE model_registry
                ADD COLUMN local_path VARCHAR(512)
            """))
            db.commit()
            print("✅ Added local_path column")
        else:
            print("⏭️  local_path column already exists")

        # Add quantization_type if it doesn't exist
        if 'quantization_type' not in columns:
            print("Adding quantization_type column...")
            db.execute(text("""
                ALTER TABLE model_registry
                ADD COLUMN quantization_type VARCHAR(32)
            """))
            db.commit()
            print("✅ Added quantization_type column")
        else:
            print("⏭️  quantization_type column already exists")

        print("\n✅ Migration complete!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

