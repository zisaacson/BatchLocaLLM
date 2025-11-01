#!/usr/bin/env python3
"""Add FP16 models to registry (GGUF not supported by vLLM yet)."""

from core.batch_app.database import SessionLocal, ModelRegistry

def add_models():
    db = SessionLocal()
    
    try:
        # OLMo 2 7B FP16 (needs CPU offload)
        existing = db.query(ModelRegistry).filter(
            ModelRegistry.model_id == "allenai/OLMo-2-1124-7B-Instruct"
        ).first()
        
        if existing:
            print("⏭️  OLMo 2 7B already exists, updating...")
            existing.cpu_offload_gb = 8.0
            existing.gpu_memory_utilization = 0.85
            existing.max_model_len = 4096
            existing.rtx4080_compatible = True
            existing.estimated_memory_gb = 23.0
        else:
            print("Adding OLMo 2 7B FP16...")
            olmo = ModelRegistry(
                model_id="allenai/OLMo-2-1124-7B-Instruct",
                name="OLMo 2 7B",
                size_gb=14.0,
                cpu_offload_gb=8.0,
                gpu_memory_utilization=0.85,
                max_model_len=4096,
                enable_prefix_caching=True,
                chunked_prefill_enabled=True,
                rtx4080_compatible=True,
                estimated_memory_gb=23.0,
                throughput_tokens_per_sec=200.0,
            )
            db.add(olmo)
        
        db.commit()
        print("✅ OLMo 2 7B added/updated")
        
        # GPT-OSS 20B FP16 (needs heavy CPU offload)
        existing = db.query(ModelRegistry).filter(
            ModelRegistry.model_id == "openai/gpt-oss-20b"
        ).first()
        
        if existing:
            print("⏭️  GPT-OSS 20B already exists, updating...")
            existing.cpu_offload_gb = 25.0
            existing.gpu_memory_utilization = 0.85
            existing.max_model_len = 4096
            existing.rtx4080_compatible = True
            existing.estimated_memory_gb = 40.0
        else:
            print("Adding GPT-OSS 20B FP16...")
            gptoss = ModelRegistry(
                model_id="openai/gpt-oss-20b",
                name="GPT-OSS 20B",
                size_gb=40.0,
                cpu_offload_gb=25.0,
                gpu_memory_utilization=0.85,
                max_model_len=4096,
                enable_prefix_caching=True,
                chunked_prefill_enabled=True,
                rtx4080_compatible=True,
                estimated_memory_gb=40.0,
                throughput_tokens_per_sec=50.0,
            )
            db.add(gptoss)
        
        db.commit()
        print("✅ GPT-OSS 20B added/updated")
        
        print("\n✅ All FP16 models added!")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_models()

