#!/usr/bin/env python3
"""Update OLMo 2 7B to use Q4_0 GGUF instead of FP16."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.batch_app.database import ModelRegistry, Base

# Database setup
DATABASE_URL = "sqlite:///./batch_server.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def main():
    # Create tables if they don't exist
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if OLMo 2 7B Q4_0 GGUF already exists
        existing = db.query(ModelRegistry).filter(
            ModelRegistry.model_id == "bartowski/OLMo-2-1124-7B-Instruct-GGUF"
        ).first()

        if existing:
            print(f"✅ OLMo 2 7B Q4_0 GGUF already exists:")
            print(f"   Model ID: {existing.model_id}")
            print(f"   Size: {existing.size_gb} GB")
            print(f"   Estimated memory: {existing.estimated_memory_gb} GB")
            print(f"   CPU offload: {existing.cpu_offload_gb} GB")
            return

        # Add OLMo 2 7B Q4_0 GGUF
        model = ModelRegistry(
            model_id="bartowski/OLMo-2-1124-7B-Instruct-GGUF",
            name="OLMo 2 7B Q4_0 GGUF",
            size_gb=4.23,
            estimated_memory_gb=11.5,  # 4.23 model + 3.22 KV cache + 2.0 overhead + 2 GB buffer
            max_model_len=8192,
            gpu_memory_utilization=0.95,
            cpu_offload_gb=0.0,  # No offload needed!
            enable_prefix_caching=True,
            chunked_prefill_enabled=True,
            rtx4080_compatible=True,
            requires_hf_auth=False,
            status='untested'
        )

        db.add(model)
        db.commit()

        print("\n✅ Added OLMo 2 7B Q4_0 GGUF:")
        print(f"   Model ID: {model.model_id}")
        print(f"   Name: {model.name}")
        print(f"   Size: {model.size_gb} GB")
        print(f"   Estimated memory: {model.estimated_memory_gb} GB")
        print(f"   CPU offload: {model.cpu_offload_gb} GB")
        print(f"   RTX 4080 compatible: {model.rtx4080_compatible}")

    finally:
        db.close()

if __name__ == "__main__":
    main()

