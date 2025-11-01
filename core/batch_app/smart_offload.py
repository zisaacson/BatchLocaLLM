"""
Smart CPU Offload System

Dynamically adjusts CPU offload based on:
1. Available GPU memory (real-time monitoring)
2. Model requirements
3. Current GPU utilization
4. Performance targets

This enables running larger models on consumer GPUs by intelligently
offloading weights to CPU RAM when needed.
"""

import subprocess
import re
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from core.batch_app.logging_config import get_logger

logger = get_logger(__name__)


def get_gpu_memory_info() -> Dict[str, float]:
    """
    Get current GPU memory usage via nvidia-smi.
    
    Returns:
        Dictionary with total, used, and free memory in GB
    """
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse output: "total,used,free" in MB
        line = result.stdout.strip().split('\n')[0]  # First GPU
        total_mb, used_mb, free_mb = map(float, line.split(','))
        
        return {
            'total_gb': total_mb / 1024,
            'used_gb': used_mb / 1024,
            'free_gb': free_mb / 1024,
            'utilization': used_mb / total_mb
        }
    except Exception as e:
        logger.error(f"Failed to get GPU memory info: {e}")
        # Fallback to RTX 4080 defaults
        return {
            'total_gb': 16.0,
            'used_gb': 0.0,
            'free_gb': 16.0,
            'utilization': 0.0
        }


def calculate_optimal_offload(
    model_size_gb: float,
    kv_cache_gb: float,
    vllm_overhead_gb: float,
    available_vram_gb: Optional[float] = None,
    target_utilization: float = 0.90,
    min_throughput_multiplier: float = 0.5
) -> Dict[str, Any]:
    """
    Calculate optimal CPU offload strategy.
    
    Strategies:
    1. No offload (best performance)
    2. Partial offload (balance memory/speed)
    3. Aggressive offload (maximize model size)
    
    Args:
        model_size_gb: Model weights size
        kv_cache_gb: KV cache size
        vllm_overhead_gb: vLLM engine overhead
        available_vram_gb: Available VRAM (auto-detected if None)
        target_utilization: Target GPU memory utilization (0.0-1.0)
        min_throughput_multiplier: Minimum acceptable throughput (0.0-1.0)
        
    Returns:
        Dictionary with offload strategy and recommendations
    """
    # Get current GPU memory
    if available_vram_gb is None:
        gpu_info = get_gpu_memory_info()
        available_vram_gb = gpu_info['free_gb']
        total_vram_gb = gpu_info['total_gb']
    else:
        total_vram_gb = available_vram_gb
    
    # Calculate total memory needed
    total_needed = model_size_gb + kv_cache_gb + vllm_overhead_gb
    
    # Target memory budget (leave some headroom)
    target_budget = total_vram_gb * target_utilization
    
    # Strategy 1: No offload
    if total_needed <= target_budget:
        return {
            'strategy': 'no_offload',
            'cpu_offload_gb': 0.0,
            'gpu_memory_gb': total_needed,
            'expected_throughput_multiplier': 1.0,
            'recommendation': '✅ Model fits on GPU without offload',
            'vllm_flags': []
        }
    
    # Strategy 2: Partial offload (offload just enough to fit)
    memory_deficit = total_needed - target_budget
    
    if memory_deficit <= model_size_gb:
        # Offload portion of model weights
        cpu_offload_gb = memory_deficit + 1.0  # +1 GB buffer
        offload_ratio = cpu_offload_gb / model_size_gb
        
        # Throughput penalty scales with offload ratio
        # Empirical: 30% offload = ~30% slower, 50% offload = ~60% slower
        throughput_multiplier = 1.0 - (offload_ratio * 1.2)
        throughput_multiplier = max(throughput_multiplier, min_throughput_multiplier)
        
        if throughput_multiplier >= min_throughput_multiplier:
            return {
                'strategy': 'partial_offload',
                'cpu_offload_gb': round(cpu_offload_gb, 2),
                'gpu_memory_gb': round(total_needed - cpu_offload_gb, 2),
                'expected_throughput_multiplier': round(throughput_multiplier, 3),
                'recommendation': f'⚙️ Partial offload ({int(offload_ratio*100)}% of weights) - {int((1-throughput_multiplier)*100)}% slower',
                'vllm_flags': [f'--cpu-offload-gb {cpu_offload_gb:.2f}']
            }
    
    # Strategy 3: Aggressive offload (offload most/all weights)
    # Keep KV cache + overhead on GPU, offload all weights
    cpu_offload_gb = model_size_gb
    gpu_memory_gb = kv_cache_gb + vllm_overhead_gb
    
    # Check if this fits
    if gpu_memory_gb <= target_budget:
        # Aggressive offload: ~95% slower
        throughput_multiplier = 0.05
        
        return {
            'strategy': 'aggressive_offload',
            'cpu_offload_gb': round(cpu_offload_gb, 2),
            'gpu_memory_gb': round(gpu_memory_gb, 2),
            'expected_throughput_multiplier': throughput_multiplier,
            'recommendation': '🔴 Aggressive offload (all weights) - ~95% slower. Consider cloud GPU.',
            'vllm_flags': [f'--cpu-offload-gb {cpu_offload_gb:.2f}']
        }
    
    # Strategy 4: Impossible (even with full offload, KV cache doesn't fit)
    return {
        'strategy': 'impossible',
        'cpu_offload_gb': 0.0,
        'gpu_memory_gb': total_needed,
        'expected_throughput_multiplier': 0.0,
        'recommendation': '❌ Model too large even with CPU offload. Reduce context length or use cloud GPU.',
        'vllm_flags': []
    }


def optimize_for_batch_size(
    model_size_gb: float,
    available_vram_gb: float,
    target_batch_size: int = 100,
    context_length: int = 4096
) -> Dict[str, Any]:
    """
    Optimize offload strategy for a specific batch size.
    
    Larger batches need more KV cache, which may require more offload.
    This function finds the optimal balance.
    
    Args:
        model_size_gb: Model weights size
        available_vram_gb: Available VRAM
        target_batch_size: Desired batch size
        context_length: Context length
        
    Returns:
        Optimized configuration
    """
    from core.batch_app.model_parser import estimate_memory_requirements
    
    # Try different batch sizes to find optimal
    batch_sizes = [target_batch_size, target_batch_size // 2, target_batch_size // 4, 1]
    
    best_config = None
    best_throughput = 0
    
    for batch_size in batch_sizes:
        # Estimate memory for this batch size
        memory_est = estimate_memory_requirements(
            size_gb=model_size_gb,
            context_length=context_length,
            available_vram_gb=available_vram_gb,
            batch_size=batch_size
        )
        
        # Calculate effective throughput
        # throughput = batch_size * throughput_multiplier
        effective_throughput = batch_size * memory_est['expected_throughput_multiplier']
        
        if effective_throughput > best_throughput:
            best_throughput = effective_throughput
            best_config = {
                'batch_size': batch_size,
                'cpu_offload_gb': memory_est['cpu_offload_gb'],
                'expected_throughput_multiplier': memory_est['expected_throughput_multiplier'],
                'effective_throughput': effective_throughput,
                'recommendation': f'Optimal: batch_size={batch_size}, offload={memory_est["cpu_offload_gb"]:.1f}GB'
            }
    
    return best_config


def generate_optimized_vllm_command(
    model_id: str,
    model_size_gb: float,
    available_vram_gb: Optional[float] = None,
    context_length: int = 4096,
    batch_size: int = 100,
    enable_smart_offload: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Generate fully optimized vLLM command with smart offload.
    
    Args:
        model_id: HuggingFace model ID
        model_size_gb: Model size in GB
        available_vram_gb: Available VRAM (auto-detected if None)
        context_length: Maximum context length
        batch_size: Target batch size
        enable_smart_offload: Enable smart offload calculation
        
    Returns:
        Tuple of (vllm_command, optimization_info)
    """
    from core.batch_app.model_parser import estimate_memory_requirements
    
    # Get GPU info
    if available_vram_gb is None:
        gpu_info = get_gpu_memory_info()
        available_vram_gb = gpu_info['free_gb']
    
    # Estimate memory requirements
    memory_est = estimate_memory_requirements(
        size_gb=model_size_gb,
        context_length=context_length,
        available_vram_gb=available_vram_gb,
        batch_size=batch_size
    )
    
    # Calculate optimal offload if enabled
    if enable_smart_offload:
        offload_strategy = calculate_optimal_offload(
            model_size_gb=model_size_gb,
            kv_cache_gb=memory_est['kv_cache_gb'],
            vllm_overhead_gb=memory_est['vllm_overhead_gb'],
            available_vram_gb=available_vram_gb
        )
    else:
        offload_strategy = {
            'cpu_offload_gb': 0.0,
            'vllm_flags': []
        }
    
    # Build command
    cmd_parts = ['vllm', 'serve', f'"{model_id}"']
    
    # Add offload flags
    if offload_strategy['cpu_offload_gb'] > 0:
        cmd_parts.append(f"--cpu-offload-gb {offload_strategy['cpu_offload_gb']}")
    
    # Add standard flags
    cmd_parts.extend([
        f'--max-model-len {context_length}',
        '--gpu-memory-utilization 0.90',
        '--enable-prefix-caching',
        '--enable-chunked-prefill'
    ])
    
    command = ' '.join(cmd_parts)
    
    optimization_info = {
        'command': command,
        'memory_estimates': memory_est,
        'offload_strategy': offload_strategy,
        'available_vram_gb': available_vram_gb,
        'recommendations': memory_est.get('recommendations', [])
    }
    
    return command, optimization_info

