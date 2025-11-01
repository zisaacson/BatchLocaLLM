#!/usr/bin/env python3
"""
Migration script to create model_registry table.

This table tracks all models available in the system, their test results,
and benchmark data for the model management UI.

Run this before starting the updated API.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.batch_app.database import SessionLocal, engine, ModelRegistry
from models.registry import list_models

def migrate():
    """Create model_registry table and populate with existing models."""
    print("🔄 Creating model_registry table...")
    
    db = SessionLocal()
    
    try:
        # Create table
        ModelRegistry.__table__.create(engine, checkfirst=True)
        print("✅ Table created")
        
        # Check if we need to populate
        existing_count = db.query(ModelRegistry).count()
        if existing_count > 0:
            print(f"ℹ️  Table already has {existing_count} models")
            return
        
        # Populate with existing models from registry
        print("📝 Populating with existing models...")
        existing_models = list_models()
        
        for model_config in existing_models:
            db_model = ModelRegistry(
                model_id=model_config.model_id,
                name=model_config.name,
                size_gb=model_config.size_gb,
                estimated_memory_gb=model_config.estimated_memory_gb,
                max_model_len=model_config.max_model_len,
                gpu_memory_utilization=model_config.gpu_memory_utilization,
                enable_prefix_caching=model_config.enable_prefix_caching,
                chunked_prefill_enabled=model_config.chunked_prefill_enabled,
                rtx4080_compatible=model_config.rtx4080_compatible,
                requires_hf_auth=model_config.requires_hf_auth,
                status=model_config.status,
                throughput_tokens_per_sec=model_config.throughput_tokens_per_sec,
                throughput_requests_per_sec=model_config.throughput_requests_per_sec,
            )
            db.add(db_model)
            print(f"   ✓ {model_config.name}")
        
        db.commit()
        print(f"✅ Populated {len(existing_models)} models")
        
        # Verify
        result = db.execute(text("""
            SELECT model_id, name, status 
            FROM model_registry
            ORDER BY created_at
        """))
        
        print("\n📊 Current models in registry:")
        for row in result:
            print(f"   - {row[1]} ({row[0]}) - {row[2]}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

