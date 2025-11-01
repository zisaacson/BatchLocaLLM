"""
Add Gemma 3 12B Q4_0 GGUF and GPT-OSS 20B to model registry.
"""

import sys
sys.path.insert(0, '/home/zack/Documents/augment-projects/Local/vllm-batch-server')

from core.batch_app.database import SessionLocal, ModelRegistry
from core.batch_app.model_parser import parse_and_prepare_model
from datetime import datetime, timezone

# Gemma 3 12B Q4_0 GGUF content
gemma3_12b_content = """
How to use from vLLM

hf auth login
Install from pip

pip install vllm

Load and run the model:
vllm serve "google/gemma-3-12b-it-qat-q4_0-gguf"

Call the server using curl:
curl -X POST "http://localhost:8000/v1/chat/completions" \\
    -H "Content-Type: application/json" \\
    --data '{
        "model": "google/gemma-3-12b-it-qat-q4_0-gguf",
        "messages": [{"role": "user", "content": "Hello!"}]
    }'
"""

# GPT-OSS 20B content (using llama.cpp based on your notes)
gptoss_20b_content = """
GPT-OSS 20B model

Model ID: gpt-oss/gpt-oss-20b-instruct

This is a 20B parameter model that requires special handling.
Based on Reddit recommendations, use llama.cpp with CPU offload:

llama.cpp flags:
--cpu-moe 36 (offload expert layers to CPU)
--n-gpu-layers 999 (offload as much as possible to GPU)

For vLLM (if supported):
vllm serve "gpt-oss/gpt-oss-20b-instruct"

pip install vllm
"""

def add_model_to_registry(content: str, model_name: str):
    """Add a model to the registry."""
    print(f"\n{'='*70}")
    print(f"Adding {model_name} to registry...")
    print('='*70)
    
    try:
        # Parse content
        config = parse_and_prepare_model(content)
        
        print(f"\n✅ Parsed configuration:")
        print(f"   Model ID: {config['model_id']}")
        print(f"   Name: {config['name']}")
        print(f"   Size: {config['size_gb']} GB")
        print(f"   Estimated Memory: {config['estimated_memory_gb']} GB")
        print(f"   RTX 4080 Compatible: {'✅ YES' if config['rtx4080_compatible'] else '❌ NO'}")
        print(f"   CPU Offload: {config['cpu_offload_gb']} GB")
        
        print(f"\n📋 Recommendations:")
        for rec in config.get('recommendations', []):
            print(f"   {rec}")
        
        print(f"\n🚀 vLLM Command:")
        print(f"   {config['vllm_serve_command']}")
        
        # Add to database
        db = SessionLocal()
        try:
            # Check if already exists
            existing = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == config['model_id']
            ).first()
            
            if existing:
                print(f"\n⚠️  Model already exists in registry, updating...")
                existing.name = config['name']
                existing.size_gb = config['size_gb']
                existing.estimated_memory_gb = config['estimated_memory_gb']
                existing.cpu_offload_gb = config['cpu_offload_gb']
                existing.rtx4080_compatible = config['rtx4080_compatible']
                existing.requires_hf_auth = config['requires_hf_auth']
            else:
                print(f"\n✅ Adding new model to registry...")
                model = ModelRegistry(
                    model_id=config['model_id'],
                    name=config['name'],
                    size_gb=config['size_gb'],
                    estimated_memory_gb=config['estimated_memory_gb'],
                    max_model_len=4096,
                    gpu_memory_utilization=0.90,
                    cpu_offload_gb=config['cpu_offload_gb'],
                    enable_prefix_caching=True,
                    chunked_prefill_enabled=True,
                    rtx4080_compatible=config['rtx4080_compatible'],
                    requires_hf_auth=config['requires_hf_auth']
                )
                db.add(model)
            
            db.commit()
            print(f"✅ Successfully added {config['name']} to registry!")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Failed to add model: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🚀 Adding Gemma 3 12B and GPT-OSS 20B to model registry")
    
    # Add Gemma 3 12B Q4_0 GGUF
    add_model_to_registry(gemma3_12b_content, "Gemma 3 12B Q4_0 GGUF")
    
    # Add GPT-OSS 20B
    add_model_to_registry(gptoss_20b_content, "GPT-OSS 20B")
    
    print("\n" + "="*70)
    print("✅ All models added!")
    print("="*70)
    
    # Show all models in registry
    print("\n📋 Current model registry:")
    db = SessionLocal()
    try:
        models = db.query(ModelRegistry).all()
        for model in models:
            compat = "✅" if model.rtx4080_compatible else "⚠️"
            offload = f" (CPU offload: {model.cpu_offload_gb}GB)" if model.cpu_offload_gb > 0 else ""
            print(f"   {compat} {model.name} - {model.size_gb}GB{offload}")
    finally:
        db.close()

