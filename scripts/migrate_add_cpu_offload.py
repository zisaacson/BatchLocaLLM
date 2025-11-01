#!/usr/bin/env python3
"""
Migration: Add cpu_offload_gb column to model_registry table
"""

from sqlalchemy import create_engine, text
from core.config import settings

def main():
    print("=" * 80)
    print("Migration: Add cpu_offload_gb to model_registry")
    print("=" * 80)
    print()
    
    # Connect to database
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Add cpu_offload_gb column
        print("Adding cpu_offload_gb column...")
        try:
            conn.execute(text("""
                ALTER TABLE model_registry 
                ADD COLUMN cpu_offload_gb FLOAT DEFAULT 0.0
            """))
            conn.commit()
            print("✅ Added cpu_offload_gb column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("⚠️  Column already exists, skipping")
            else:
                raise
        
        # Update OLMo 2 7B to use CPU offload
        print("\nUpdating OLMo 2 7B configuration...")
        result = conn.execute(text("""
            UPDATE model_registry 
            SET 
                cpu_offload_gb = 8.0,
                gpu_memory_utilization = 0.85,
                estimated_memory_gb = 14.0
            WHERE model_id = 'allenai/OLMo-2-1124-7B-Instruct'
        """))
        conn.commit()
        
        if result.rowcount > 0:
            print(f"✅ Updated OLMo 2 7B (cpu_offload_gb=8.0, gpu_util=0.85)")
        else:
            print("⚠️  OLMo 2 7B not found in registry")
        
        # Show updated config
        print("\nOLMo 2 7B configuration:")
        result = conn.execute(text("""
            SELECT model_id, gpu_memory_utilization, cpu_offload_gb, estimated_memory_gb
            FROM model_registry
            WHERE model_id = 'allenai/OLMo-2-1124-7B-Instruct'
        """))
        row = result.fetchone()
        if row:
            print(f"  Model: {row[0]}")
            print(f"  GPU Memory Util: {row[1]}")
            print(f"  CPU Offload: {row[2]} GB")
            print(f"  Est Memory: {row[3]} GB")
    
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    main()

