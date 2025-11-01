#!/usr/bin/env python3
"""Add OLMo 2 7B and GPT-OSS 20B GGUF models to the registry."""

from core.batch_app.database import SessionLocal, ModelRegistry
from pathlib import Path

def add_models():
    """Add GGUF models to registry."""
    
    db = SessionLocal()
    
    try:
        # OLMo 2 7B Q4_0
        olmo_path = Path("./models/olmo2-7b-q4/OLMo-2-1124-7B-Instruct-Q4_0.gguf")
        if not olmo_path.exists():
            print(f"❌ OLMo GGUF file not found: {olmo_path}")
        else:
            # Check if already exists
            existing = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == "bartowski/OLMo-2-1124-7B-Instruct-GGUF"
            ).first()
            
            if existing:
                print("⏭️  OLMo 2 7B already in registry, updating...")
                existing.local_path = str(olmo_path.absolute())
                existing.quantization_type = "Q4_0"
                existing.cpu_offload_gb = 0.0  # No offload needed
                existing.gpu_memory_utilization = 0.85
                existing.max_model_len = 4096
                existing.enable_prefix_caching = True
                existing.chunked_prefill_enabled = True
                existing.rtx4080_compatible = True
                existing.estimated_memory_gb = 6.5  # 4.23 GB model + 2.3 GB overhead
            else:
                print("Adding OLMo 2 7B to registry...")
                olmo = ModelRegistry(
                    model_id="bartowski/OLMo-2-1124-7B-Instruct-GGUF",
                    name="OLMo 2 7B Q4_0",
                    size_gb=4.0,
                    local_path=str(olmo_path.absolute()),
                    quantization_type="Q4_0",
                    cpu_offload_gb=0.0,
                    gpu_memory_utilization=0.85,
                    max_model_len=4096,
                    enable_prefix_caching=True,
                    chunked_prefill_enabled=True,
                    rtx4080_compatible=True,
                    estimated_memory_gb=6.5,
                    throughput_tokens_per_sec=450.0,
                )
                db.add(olmo)
            
            db.commit()
            print("✅ OLMo 2 7B added/updated")
        
        # GPT-OSS 20B Q4_0
        gptoss_path = Path("./models/gpt-oss-20b-q4/openai_gpt-oss-20b-Q4_0.gguf")
        if not gptoss_path.exists():
            print(f"❌ GPT-OSS GGUF file not found: {gptoss_path}")
        else:
            # Check if already exists
            existing = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == "bartowski/openai_gpt-oss-20b-GGUF"
            ).first()
            
            if existing:
                print("⏭️  GPT-OSS 20B already in registry, updating...")
                existing.local_path = str(gptoss_path.absolute())
                existing.quantization_type = "Q4_0"
                existing.cpu_offload_gb = 7.2  # Needs offload
                existing.gpu_memory_utilization = 0.85
                existing.max_model_len = 4096
                existing.enable_prefix_caching = True
                existing.chunked_prefill_enabled = True
                existing.rtx4080_compatible = True
                existing.estimated_memory_gb = 23.0  # 11.5 GB model + overhead
            else:
                print("Adding GPT-OSS 20B to registry...")
                gptoss = ModelRegistry(
                    model_id="bartowski/openai_gpt-oss-20b-GGUF",
                    name="GPT-OSS 20B Q4_0",
                    size_gb=11.0,
                    local_path=str(gptoss_path.absolute()),
                    quantization_type="Q4_0",
                    cpu_offload_gb=7.2,
                    gpu_memory_utilization=0.85,
                    max_model_len=4096,
                    enable_prefix_caching=True,
                    chunked_prefill_enabled=True,
                    rtx4080_compatible=True,
                    estimated_memory_gb=23.0,
                    throughput_tokens_per_sec=150.0,  # Slower due to offload
                )
                db.add(gptoss)
            
            db.commit()
            print("✅ GPT-OSS 20B added/updated")
        
        print("\n✅ All models added to registry!")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_models()

