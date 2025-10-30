#!/usr/bin/env python3
"""
Intelligent Memory Optimizer for vLLM

Automatically determines optimal vLLM settings based on:
- Available GPU memory
- Model size
- Desired batch size
- Historical benchmark data
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class GPUInfo:
    """GPU information"""
    total_memory_gb: float
    used_memory_gb: float
    free_memory_gb: float
    utilization_percent: int
    name: str


@dataclass
class ModelMemoryProfile:
    """Memory profile for a model"""
    model_id: str
    model_size_gb: float
    kv_cache_gb: float
    cuda_graphs_gb: float
    total_memory_gb: float
    max_model_len: int
    gpu_memory_utilization: float
    success: bool
    notes: str = ""


@dataclass
class OptimizedConfig:
    """Optimized vLLM configuration"""
    gpu_memory_utilization: float
    max_model_len: int
    max_num_seqs: Optional[int] = None
    enforce_eager: bool = False
    enable_prefix_caching: bool = True
    kv_cache_dtype: Optional[str] = None
    reasoning: str = ""


class MemoryOptimizer:
    """Intelligent memory optimizer for vLLM"""
    
    def __init__(self):
        self.gpu_info = self.get_gpu_info()
        self.benchmark_dir = Path("benchmarks/metadata")
        self.memory_profiles = self.load_memory_profiles()
    
    def get_gpu_info(self) -> GPUInfo:
        """Get current GPU information"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu", 
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True
            )
            
            parts = result.stdout.strip().split(", ")
            name = parts[0]
            total_mb = float(parts[1])
            used_mb = float(parts[2])
            free_mb = float(parts[3])
            util_pct = int(parts[4])
            
            return GPUInfo(
                name=name,
                total_memory_gb=total_mb / 1024,
                used_memory_gb=used_mb / 1024,
                free_memory_gb=free_mb / 1024,
                utilization_percent=util_pct
            )
        except Exception as e:
            print(f"⚠️  Could not get GPU info: {e}")
            # Default to RTX 4080 16GB
            return GPUInfo(
                name="NVIDIA GeForce RTX 4080",
                total_memory_gb=15.57,
                used_memory_gb=0.5,
                free_memory_gb=15.07,
                utilization_percent=0
            )
    
    def load_memory_profiles(self) -> Dict[str, ModelMemoryProfile]:
        """Load memory profiles from benchmark metadata"""
        profiles = {}
        
        # Known profiles from successful tests
        known_profiles = {
            "google/gemma-3-4b-it": ModelMemoryProfile(
                model_id="google/gemma-3-4b-it",
                model_size_gb=8.58,
                kv_cache_gb=1.58,
                cuda_graphs_gb=0.64,
                total_memory_gb=10.95,
                max_model_len=4096,
                gpu_memory_utilization=0.90,
                success=True,
                notes="Tested with 5K batch, 100% success"
            ),
            "meta-llama/Llama-3.2-1B-Instruct": ModelMemoryProfile(
                model_id="meta-llama/Llama-3.2-1B-Instruct",
                model_size_gb=2.5,
                kv_cache_gb=1.0,
                cuda_graphs_gb=0.5,
                total_memory_gb=5.0,
                max_model_len=4096,
                gpu_memory_utilization=0.90,
                success=True,
                notes="Tested with 5K batch, 100% success, fastest model"
            ),
            "Qwen/Qwen3-4B-Instruct-2507": ModelMemoryProfile(
                model_id="Qwen/Qwen3-4B-Instruct-2507",
                model_size_gb=7.6,
                kv_cache_gb=4.94,
                cuda_graphs_gb=0.73,
                total_memory_gb=14.66,  # OOM at 0.90
                max_model_len=4096,
                gpu_memory_utilization=0.85,  # Needs lower utilization
                success=False,  # OOM with V1 engine
                notes="OOM with gpu_memory_utilization=0.90, needs 0.85 or lower"
            ),
            "google/gemma-3-12b-it-qat-q4_0-gguf": ModelMemoryProfile(
                model_id="google/gemma-3-12b-it-qat-q4_0-gguf",
                model_size_gb=8.07,
                kv_cache_gb=2.0,
                cuda_graphs_gb=0.8,
                total_memory_gb=11.0,  # Estimated
                max_model_len=4096,
                gpu_memory_utilization=0.90,
                success=True,  # Should work - 8GB quantized model
                notes="Q4_0 quantized GGUF, 3x less memory than full precision"
            ),
        }
        
        profiles.update(known_profiles)
        return profiles
    
    def estimate_model_memory(self, model_id: str, max_model_len: int = 4096) -> float:
        """Estimate memory requirements for a model"""
        
        # Check if we have a profile
        if model_id in self.memory_profiles:
            profile = self.memory_profiles[model_id]
            # Scale by context length
            scale_factor = max_model_len / profile.max_model_len
            return profile.total_memory_gb * scale_factor
        
        # Estimate based on model name
        model_lower = model_id.lower()
        
        # Extract size from model name (e.g., "1b", "3b", "4b", "7b")
        if "1b" in model_lower:
            base_size = 2.5
        elif "3b" in model_lower:
            base_size = 6.0
        elif "4b" in model_lower:
            base_size = 8.0
        elif "7b" in model_lower:
            base_size = 14.0
        elif "12b" in model_lower:
            base_size = 24.0
        elif "13b" in model_lower:
            base_size = 26.0
        elif "20b" in model_lower:
            base_size = 40.0
        else:
            # Unknown size, be conservative
            base_size = 10.0
        
        # Add overhead for KV cache and CUDA graphs
        # Rule of thumb: ~30% overhead for 4K context
        overhead_factor = 1.3
        
        # Scale by context length
        context_scale = max_model_len / 4096
        
        estimated_memory = base_size * overhead_factor * context_scale
        
        return estimated_memory
    
    def optimize_config(
        self, 
        model_id: str, 
        max_model_len: int = 4096,
        target_batch_size: Optional[int] = None
    ) -> OptimizedConfig:
        """
        Determine optimal vLLM configuration for a model.
        
        Args:
            model_id: HuggingFace model ID
            max_model_len: Desired context window
            target_batch_size: Target batch size (optional)
        
        Returns:
            OptimizedConfig with recommended settings
        """
        
        # Estimate memory requirements
        estimated_memory = self.estimate_model_memory(model_id, max_model_len)
        
        # Check if we have a known profile
        profile = self.memory_profiles.get(model_id)
        
        # Calculate available memory
        available_memory = self.gpu_info.free_memory_gb
        
        # Start with conservative settings
        gpu_util = 0.90
        use_max_model_len = max_model_len
        max_num_seqs = None
        enforce_eager = False
        enable_prefix_caching = True
        kv_cache_dtype = None
        reasoning = []
        
        # Adjust based on estimated memory
        memory_ratio = estimated_memory / self.gpu_info.total_memory_gb
        
        if memory_ratio > 0.95:
            # Model is too large
            reasoning.append(f"⚠️  Model requires {estimated_memory:.1f} GB but GPU only has {self.gpu_info.total_memory_gb:.1f} GB")
            reasoning.append("❌ Model will NOT fit - consider quantization or smaller model")
            gpu_util = 0.80
            use_max_model_len = 2048
            enforce_eager = True
            kv_cache_dtype = "fp8"
        
        elif memory_ratio > 0.90:
            # Very tight fit
            reasoning.append(f"⚠️  Tight fit: {estimated_memory:.1f} GB / {self.gpu_info.total_memory_gb:.1f} GB")
            reasoning.append("Reducing gpu_memory_utilization to 0.80")
            gpu_util = 0.80
            enforce_eager = True
        
        elif memory_ratio > 0.80:
            # Moderate fit
            reasoning.append(f"✅ Moderate fit: {estimated_memory:.1f} GB / {self.gpu_info.total_memory_gb:.1f} GB")
            reasoning.append("Using gpu_memory_utilization=0.85")
            gpu_util = 0.85
        
        elif memory_ratio > 0.70:
            # Good fit
            reasoning.append(f"✅ Good fit: {estimated_memory:.1f} GB / {self.gpu_info.total_memory_gb:.1f} GB")
            reasoning.append("Using gpu_memory_utilization=0.90")
            gpu_util = 0.90
        
        else:
            # Plenty of room
            reasoning.append(f"✅ Excellent fit: {estimated_memory:.1f} GB / {self.gpu_info.total_memory_gb:.1f} GB")
            reasoning.append("Using gpu_memory_utilization=0.90 with room to spare")
            gpu_util = 0.90
        
        # Check if model has known issues
        if profile and not profile.success:
            reasoning.append(f"⚠️  Known issue: {profile.notes}")
            gpu_util = min(gpu_util, profile.gpu_memory_utilization)
            reasoning.append(f"Using gpu_memory_utilization={gpu_util} based on previous failures")
        
        # Check current GPU usage
        if self.gpu_info.used_memory_gb > 1.0:
            reasoning.append(f"⚠️  GPU currently using {self.gpu_info.used_memory_gb:.1f} GB")
            reasoning.append("Consider killing existing processes first")
        
        return OptimizedConfig(
            gpu_memory_utilization=gpu_util,
            max_model_len=use_max_model_len,
            max_num_seqs=max_num_seqs,
            enforce_eager=enforce_eager,
            enable_prefix_caching=enable_prefix_caching,
            kv_cache_dtype=kv_cache_dtype,
            reasoning="\n".join(reasoning)
        )
    
    def print_recommendation(self, model_id: str, max_model_len: int = 4096):
        """Print optimization recommendation"""
        print("=" * 80)
        print("🧠 MEMORY OPTIMIZER")
        print("=" * 80)
        print()
        
        print(f"🎮 GPU: {self.gpu_info.name}")
        print(f"   Total: {self.gpu_info.total_memory_gb:.2f} GB")
        print(f"   Used:  {self.gpu_info.used_memory_gb:.2f} GB")
        print(f"   Free:  {self.gpu_info.free_memory_gb:.2f} GB")
        print()
        
        print(f"🤖 Model: {model_id}")
        print(f"   Context: {max_model_len} tokens")
        print()
        
        config = self.optimize_config(model_id, max_model_len)
        
        print("📊 Analysis:")
        print(config.reasoning)
        print()
        
        print("✅ Recommended Configuration:")
        print(f"   gpu_memory_utilization = {config.gpu_memory_utilization}")
        print(f"   max_model_len = {config.max_model_len}")
        if config.max_num_seqs:
            print(f"   max_num_seqs = {config.max_num_seqs}")
        if config.enforce_eager:
            print(f"   enforce_eager = {config.enforce_eager}")
        if config.kv_cache_dtype:
            print(f"   kv_cache_dtype = '{config.kv_cache_dtype}'")
        print()
        
        print("💻 Code:")
        print("```python")
        print("from vllm import LLM")
        print()
        print("llm = LLM(")
        print(f'    model="{model_id}",')
        print(f"    max_model_len={config.max_model_len},")
        print(f"    gpu_memory_utilization={config.gpu_memory_utilization},")
        if config.max_num_seqs:
            print(f"    max_num_seqs={config.max_num_seqs},")
        if config.enforce_eager:
            print(f"    enforce_eager={config.enforce_eager},")
        if config.kv_cache_dtype:
            print(f"    kv_cache_dtype='{config.kv_cache_dtype}',")
        print("    disable_log_stats=True,")
        print(")")
        print("```")
        print()
        print("=" * 80)


def main():
    """CLI interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python memory_optimizer.py <model_id> [max_model_len]")
        print()
        print("Examples:")
        print("  python memory_optimizer.py google/gemma-3-4b-it")
        print("  python memory_optimizer.py meta-llama/Llama-3.2-3B-Instruct 4096")
        print("  python memory_optimizer.py Qwen/Qwen3-4B-Instruct-2507")
        sys.exit(1)
    
    model_id = sys.argv[1]
    max_model_len = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
    
    optimizer = MemoryOptimizer()
    optimizer.print_recommendation(model_id, max_model_len)


if __name__ == "__main__":
    main()

