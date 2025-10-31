#!/usr/bin/env python3
"""
Initialize PostgreSQL schema with SQLAlchemy 2.0 models.
"""

import sys
from batch_app.database import Base, engine, init_db

def main():
    """Create all tables in PostgreSQL."""
    print("=" * 80)
    print("PostgreSQL Schema Initialization")
    print("=" * 80)
    
    try:
        # Create all tables
        print("\nCreating tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n✅ Successfully created {len(tables)} tables:")
        for table in sorted(tables):
            columns = inspector.get_columns(table)
            print(f"   - {table} ({len(columns)} columns)")
        
        print("\n" + "=" * 80)
        print("✅ PostgreSQL schema initialized successfully!")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ Schema initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

