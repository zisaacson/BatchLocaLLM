"""
Parser for HuggingFace model page content.

Extracts model configuration from copy/pasted HuggingFace model pages.
"""

import re
from typing import Any, Dict, Optional, TypedDict


class ModelConfig(TypedDict, total=False):
    """Type definition for parsed model configuration"""
    model_id: Optional[str]
    vllm_serve_command: Optional[str]
    installation_notes: Optional[str]
    requires_hf_auth: bool
    is_gguf: bool
    is_quantized: bool
    quantization_type: Optional[str]
    estimated_size_gb: Optional[float]


def parse_huggingface_content(content: str) -> Dict[str, Any]:
    """
    Parse copy/pasted HuggingFace model page content.

    Extracts:
    - Model ID from vllm serve command
    - Installation commands
    - vLLM serve command
    - Special parameters (quantization, GGUF, etc.)

    Args:
        content: Raw text from HuggingFace model page

    Returns:
        Dictionary with parsed model configuration
    """
    result: Dict[str, Any] = {
        "model_id": None,
        "vllm_serve_command": None,
        "installation_notes": None,
        "requires_hf_auth": False,
        "is_gguf": False,
        "is_quantized": False,
        "quantization_type": None,
        "estimated_size_gb": None
    }

    # Check if content is just a URL
    url_pattern = r'https?://huggingface\.co/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)'
    url_match = re.search(url_pattern, content.strip())
    if url_match:
        result["model_id"] = url_match.group(1)
        result["vllm_serve_command"] = f'vllm serve "{url_match.group(1)}"'

    # Extract vLLM serve command
    if not result["model_id"]:
        vllm_serve_pattern = r'vllm serve\s+"([^"]+)"'
        vllm_match = re.search(vllm_serve_pattern, content)
        if vllm_match:
            result["model_id"] = vllm_match.group(1)
            result["vllm_serve_command"] = f'vllm serve "{vllm_match.group(1)}"'

    # Alternative: look for model ID in quotes
    if not result["model_id"]:
        model_id_pattern = r'"([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)"'
        model_matches = re.findall(model_id_pattern, content)
        if model_matches:
            # Filter out URLs and common false positives
            for match in model_matches:
                if '/' in match and not match.startswith('http'):
                    result["model_id"] = match
                    break
    
    # Extract installation commands
    install_commands = []
    
    # Check for HF auth
    if "hf auth login" in content.lower() or "huggingface-cli login" in content.lower():
        result["requires_hf_auth"] = True
        install_commands.append("hf auth login")
    
    # Check for pip install
    pip_pattern = r'pip install\s+([^\n]+)'
    pip_matches = re.findall(pip_pattern, content)
    if pip_matches:
        install_commands.extend([f"pip install {cmd.strip()}" for cmd in pip_matches])
    
    if install_commands:
        result["installation_notes"] = "\n".join(install_commands)
    
    # Detect GGUF format
    if result["model_id"] and "gguf" in result["model_id"].lower():
        result["is_gguf"] = True
    
    # Detect quantization
    quant_patterns = {
        "q4_0": "Q4_0",
        "q4_1": "Q4_1",
        "q5_0": "Q5_0",
        "q5_1": "Q5_1",
        "q8_0": "Q8_0",
        "qat": "QAT",
        "awq": "AWQ",
        "gptq": "GPTQ",
        "int4": "INT4",
        "int8": "INT8"
    }
    
    model_id_lower = (result["model_id"] or "").lower()
    for pattern, quant_type in quant_patterns.items():
        if pattern in model_id_lower:
            result["is_quantized"] = True
            result["quantization_type"] = quant_type
            break
    
    # Estimate size from model name
    size_patterns = {
        r'(\d+)b': lambda x: float(x),  # "12b" -> 12
        r'(\d+)\.(\d+)b': lambda x: float(f"{x[0]}.{x[1]}"),  # "1.5b" -> 1.5
    }
    
    for pattern, converter in size_patterns.items():
        match = re.search(pattern, model_id_lower)
        if match:
            try:
                params_b = converter(match.groups() if len(match.groups()) > 1 else match.group(1))
                
                # Estimate size based on quantization
                if result["is_quantized"]:
                    if result["quantization_type"] in ["Q4_0", "Q4_1", "INT4"]:
                        # 4-bit: ~0.5 GB per billion params
                        result["estimated_size_gb"] = params_b * 0.5
                    elif result["quantization_type"] in ["Q8_0", "INT8"]:
                        # 8-bit: ~1 GB per billion params
                        result["estimated_size_gb"] = params_b * 1.0
                    else:
                        # Conservative estimate
                        result["estimated_size_gb"] = params_b * 0.75
                else:
                    # FP16: ~2 GB per billion params
                    result["estimated_size_gb"] = params_b * 2.0
                
                break
            except:
                pass
    
    return result


def generate_model_name(model_id: str) -> str:
    """
    Generate a human-readable model name from model ID.
    
    Examples:
        "google/gemma-3-12b-it-qat-q4_0-gguf" -> "Gemma 3 12B (Q4_0 GGUF)"
        "allenai/OLMo-2-1124-7B-Instruct" -> "OLMo 2 7B Instruct"
    
    Args:
        model_id: HuggingFace model ID
        
    Returns:
        Human-readable name
    """
    # Remove organization prefix
    name = model_id.split('/')[-1]
    
    # Extract key components
    parts = []
    
    # Model family (Gemma, OLMo, Llama, etc.)
    family_match = re.search(r'(gemma|olmo|llama|qwen|gpt)', name, re.IGNORECASE)
    if family_match:
        family = family_match.group(1).capitalize()
        parts.append(family)
    
    # Version number
    version_match = re.search(r'[-_](\d+(?:\.\d+)?)', name)
    if version_match:
        parts.append(version_match.group(1))
    
    # Parameter count
    param_match = re.search(r'(\d+(?:\.\d+)?)[bB]', name)
    if param_match:
        params = param_match.group(1)
        parts.append(f"{params}B")
    
    # Quantization
    quant_match = re.search(r'(q\d+_\d+|qat|awq|gptq|int\d+)', name, re.IGNORECASE)
    if quant_match:
        quant = quant_match.group(1).upper()
        
        # Check for GGUF
        if "gguf" in name.lower():
            parts.append(f"({quant} GGUF)")
        else:
            parts.append(f"({quant})")
    elif "gguf" in name.lower():
        parts.append("(GGUF)")
    
    # Instruction tuned
    if re.search(r'(instruct|it|chat)', name, re.IGNORECASE):
        if not any(p.lower() in ['instruct', 'it', 'chat'] for p in parts):
            parts.append("Instruct")
    
    return " ".join(parts) if parts else name


def estimate_memory_requirements(
    size_gb: float,
    is_quantized: bool = False,
    quantization_type: Optional[str] = None,
    context_length: int = 4096,
    available_vram_gb: float = 16.0,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    Estimate GPU memory requirements for a model with detailed breakdown.

    Based on empirical testing:
    - vLLM V1 engine overhead: ~2-3 GB
    - KV cache scales with: model size, context length, batch size
    - CPU offload trades memory for speed (~100x slower)

    Args:
        size_gb: Model size in GB (weights only)
        is_quantized: Whether model is quantized
        quantization_type: Type of quantization (Q4_0, Q8_0, etc.)
        context_length: Maximum context length
        available_vram_gb: Available VRAM (default 16 GB for RTX 4080)
        batch_size: Expected batch size for inference

    Returns:
        Dictionary with detailed memory estimates and recommendations
    """
    # 1. Base model weights
    model_memory = size_gb

    # 2. KV cache estimation (more accurate formula)
    # KV cache size = 2 * num_layers * hidden_size * context_length * batch_size * bytes_per_element
    # Rough approximation based on model size:
    # - 1B params: ~0.3 GB per 1K context per 100 batch
    # - 4B params: ~0.5 GB per 1K context per 100 batch
    # - 7B params: ~0.8 GB per 1K context per 100 batch
    # - 12B params: ~1.2 GB per 1K context per 100 batch

    # Estimate params from size
    if is_quantized and quantization_type in ["Q4_0", "Q4_1", "INT4"]:
        params_b = size_gb / 0.5  # 4-bit: ~0.5 GB per B params
    elif is_quantized and quantization_type in ["Q8_0", "INT8"]:
        params_b = size_gb / 1.0  # 8-bit: ~1 GB per B params
    else:
        params_b = size_gb / 2.0  # FP16: ~2 GB per B params

    # KV cache scaling factor (GB per 1K context per 100 batch)
    kv_scale = params_b * 0.1  # Empirical: ~0.1 GB per B params per 1K context per 100 batch
    kv_cache = kv_scale * (context_length / 1000) * (batch_size / 100)

    # 3. vLLM V1 engine overhead
    # Based on empirical testing:
    # - Base engine: ~2 GB
    # - Scales slightly with model size: +0.5 GB per 10B params
    vllm_overhead = 2.0 + (params_b / 10.0) * 0.5

    # 4. Total memory needed
    total_memory = model_memory + kv_cache + vllm_overhead

    # 5. Check if fits on available VRAM
    fits_on_gpu = total_memory <= available_vram_gb

    # 6. Calculate CPU offload strategy
    cpu_offload_needed: float = 0.0
    cpu_offload_strategy = "none"
    expected_throughput_multiplier = 1.0

    if not fits_on_gpu:
        # Calculate how much to offload
        # Strategy: Offload model weights, keep KV cache on GPU
        memory_deficit = total_memory - available_vram_gb

        # Option 1: Offload just enough weights
        if memory_deficit <= model_memory:
            cpu_offload_needed = memory_deficit + 1.0  # +1 GB buffer
            cpu_offload_strategy = "partial"
            # Throughput penalty scales with offload ratio
            offload_ratio = cpu_offload_needed / model_memory
            expected_throughput_multiplier = 1.0 - (offload_ratio * 0.95)  # Up to 95% slower
        else:
            # Option 2: Offload all weights (extreme case)
            cpu_offload_needed = model_memory
            cpu_offload_strategy = "full"
            expected_throughput_multiplier = 0.01  # ~100x slower

    # 7. Alternative: Reduce context length to fit
    max_context_without_offload = None
    if not fits_on_gpu and kv_cache > 0:
        # Calculate max context that fits
        available_for_kv = available_vram_gb - model_memory - vllm_overhead
        if available_for_kv > 0:
            max_context_without_offload = int((available_for_kv / kv_scale) * 1000 * (100 / batch_size))

    # 8. Generate recommendations
    recommendations = []

    if fits_on_gpu:
        recommendations.append("✅ Model fits on GPU without CPU offload")
        recommendations.append(f"Expected throughput: ~{2000 if params_b <= 5 else 500 if params_b <= 10 else 100} tok/s")
    else:
        recommendations.append(f"⚠️ Model requires {cpu_offload_needed:.1f} GB CPU offload")
        recommendations.append(f"Expected throughput: ~{int(2000 * expected_throughput_multiplier)} tok/s ({int((1-expected_throughput_multiplier)*100)}% slower)")

        if max_context_without_offload and max_context_without_offload >= 2048:
            recommendations.append(f"💡 Alternative: Reduce context to {max_context_without_offload} to avoid CPU offload")

        if cpu_offload_strategy == "full":
            recommendations.append("🔴 Full CPU offload required - consider using cloud GPU instead")

    return {
        # Memory breakdown
        "model_memory_gb": round(model_memory, 2),
        "kv_cache_gb": round(kv_cache, 2),
        "vllm_overhead_gb": round(vllm_overhead, 2),
        "total_memory_gb": round(total_memory, 2),

        # Compatibility
        "fits_on_gpu": fits_on_gpu,
        "rtx4080_compatible": fits_on_gpu,  # Alias for backward compat

        # CPU offload
        "cpu_offload_gb": round(cpu_offload_needed, 2),
        "cpu_offload_strategy": cpu_offload_strategy,
        "expected_throughput_multiplier": round(expected_throughput_multiplier, 3),

        # Alternatives
        "max_context_without_offload": max_context_without_offload,

        # Recommendations
        "recommendations": recommendations,

        # Metadata
        "estimated_params_b": round(params_b, 1),
        "available_vram_gb": available_vram_gb,
        "context_length": context_length,
        "batch_size": batch_size
    }


def generate_vllm_command(
    model_id: str,
    cpu_offload_gb: float = 0,
    max_model_len: int = 4096,
    gpu_memory_utilization: float = 0.90,
    enable_prefix_caching: bool = True
) -> str:
    """
    Generate optimized vLLM command with all necessary flags.

    Args:
        model_id: HuggingFace model ID
        cpu_offload_gb: GB to offload to CPU (0 = no offload)
        max_model_len: Maximum context length
        gpu_memory_utilization: GPU memory utilization (0.0-1.0)
        enable_prefix_caching: Enable prefix caching

    Returns:
        Complete vLLM command ready to run
    """
    cmd_parts = ["vllm", "serve", f'"{model_id}"']

    # Add CPU offload if needed
    if cpu_offload_gb > 0:
        cmd_parts.append(f"--cpu-offload-gb {cpu_offload_gb}")

    # Add context length
    cmd_parts.append(f"--max-model-len {max_model_len}")

    # Add GPU memory utilization
    cmd_parts.append(f"--gpu-memory-utilization {gpu_memory_utilization}")

    # Add prefix caching
    if enable_prefix_caching:
        cmd_parts.append("--enable-prefix-caching")

    # Add chunked prefill (recommended for batch processing)
    cmd_parts.append("--enable-chunked-prefill")

    return " ".join(cmd_parts)


def parse_and_prepare_model(content: str, available_vram_gb: float = 16.0) -> Dict[str, Any]:
    """
    Parse HuggingFace content and prepare complete model configuration.
    
    This is the main function to use - it combines all parsing and estimation.
    
    Args:
        content: Raw text from HuggingFace model page
        
    Returns:
        Complete model configuration ready for AddModelRequest
    """
    # Parse content
    parsed = parse_huggingface_content(content)
    
    if not parsed["model_id"]:
        raise ValueError("Could not extract model ID from content")
    
    # Generate name
    name = generate_model_name(parsed["model_id"])
    
    # Estimate memory if we have size
    memory_estimates = {}
    if parsed["estimated_size_gb"]:
        memory_estimates = estimate_memory_requirements(
            size_gb=parsed["estimated_size_gb"],
            is_quantized=parsed["is_quantized"],
            quantization_type=parsed["quantization_type"],
            available_vram_gb=available_vram_gb
        )

    # Generate optimized vLLM command
    cpu_offload_gb = memory_estimates.get("cpu_offload_gb", 0.0)
    optimized_command = generate_vllm_command(
        model_id=parsed["model_id"],
        cpu_offload_gb=cpu_offload_gb
    )

    # Combine everything
    result = {
        "model_id": parsed["model_id"],
        "name": name,
        "size_gb": parsed["estimated_size_gb"] or 0.0,
        "estimated_memory_gb": memory_estimates.get("total_memory_gb", 0.0),
        "vllm_serve_command": optimized_command,  # Use optimized command
        "vllm_serve_command_original": parsed["vllm_serve_command"],  # Keep original
        "installation_notes": parsed["installation_notes"],
        "requires_hf_auth": parsed["requires_hf_auth"],
        "rtx4080_compatible": memory_estimates.get("fits_on_gpu", True),
        "cpu_offload_gb": cpu_offload_gb,

        # Additional metadata
        "is_gguf": parsed["is_gguf"],
        "is_quantized": parsed["is_quantized"],
        "quantization_type": parsed["quantization_type"],
        "memory_breakdown": memory_estimates,

        # Recommendations
        "recommendations": memory_estimates.get("recommendations", [])
    }

    return result

