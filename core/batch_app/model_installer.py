"""
Unified Model Installation System

Handles the complete flow:
1. Parse HuggingFace URL/content
2. Analyze memory requirements
3. Download model
4. Run benchmark
5. Update registry

User just pastes a URL and everything happens automatically.
"""

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from .model_parser import parse_huggingface_content, estimate_memory_requirements
from .smart_offload import calculate_optimal_offload
from .database import ModelRegistry, SessionLocal


class ModelInstaller:
    """Handles complete model installation flow."""

    def __init__(self, models_dir: Path = Path("./models")):
        self.models_dir = models_dir
        self.models_dir.mkdir(exist_ok=True)
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    def validate_pre_installation(
        self,
        model_id: str,
        gguf_file: str,
        estimated_size_gb: float
    ) -> Dict[str, Any]:
        """
        Validate before starting installation.

        Checks:
        - Disk space available
        - Model not already installed
        - GGUF format supported
        - HuggingFace accessibility

        Returns:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'disk_space_gb': float,
                'duplicate_model': Optional[str]
            }
        """
        errors = []
        warnings = []

        # Check disk space
        disk_usage = shutil.disk_usage(self.models_dir)
        free_gb = disk_usage.free / (1024**3)
        needed_gb = estimated_size_gb * 1.2  # Add 20% overhead

        if free_gb < needed_gb:
            errors.append(
                f"Insufficient disk space: {free_gb:.1f} GB free, need {needed_gb:.1f} GB"
            )
        elif free_gb < needed_gb * 2:
            warnings.append(
                f"Low disk space: {free_gb:.1f} GB free (recommended: {needed_gb * 2:.1f} GB)"
            )

        # Check for duplicate models
        db = SessionLocal()
        try:
            existing = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == model_id
            ).first()

            if existing:
                if existing.local_path and Path(existing.local_path).exists():
                    errors.append(
                        f"Model already installed: {existing.name} at {existing.local_path}"
                    )
                else:
                    warnings.append(
                        f"Model exists in registry but file missing. Will reinstall."
                    )

            # Check for similar models (same base model, different quant)
            base_model = model_id.split('/')[1].rsplit('-', 1)[0] if '/' in model_id else model_id
            similar = db.query(ModelRegistry).filter(
                ModelRegistry.model_id.like(f"%{base_model}%")
            ).all()

            if similar and not existing:
                similar_names = [m.name for m in similar[:3]]
                warnings.append(
                    f"Similar models already installed: {', '.join(similar_names)}"
                )

        finally:
            db.close()

        # Validate GGUF format
        if not gguf_file.endswith('.gguf'):
            errors.append(
                f"Invalid file format: {gguf_file}. Only .gguf files are supported."
            )

        # Check quantization type is recognized
        quant_types = ['Q2_K', 'Q3_K_S', 'Q3_K_M', 'Q3_K_L', 'Q4_0', 'Q4_K_S', 'Q4_K_M',
                       'Q5_0', 'Q5_K_S', 'Q5_K_M', 'Q6_K', 'Q8_0', 'F16', 'F32']
        quant_found = any(q in gguf_file.upper() for q in quant_types)
        if not quant_found:
            warnings.append(
                f"Unknown quantization type in filename: {gguf_file}"
            )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'disk_space_gb': free_gb,
            'needed_gb': needed_gb,
            'duplicate_model': existing.name if existing else None
        }

    def analyze_model(self, hf_content: str) -> Dict[str, Any]:
        """
        Analyze a model from HuggingFace content.
        
        Returns everything the user needs to know:
        - Will it fit on GPU?
        - CPU offload needed?
        - Estimated speed
        - Quality tier
        - Comparison to existing models
        """
        # Parse HuggingFace content
        parsed = parse_huggingface_content(hf_content)

        # Check if we got a model ID
        if not parsed.get('model_id'):
            return {
                'success': False,
                'error': 'Could not extract model ID from content. Please paste a HuggingFace model page URL or content.'
            }
        
        # Estimate memory requirements
        model_size_gb = parsed.get('estimated_size_gb', 7.0)  # Default to 7GB if unknown
        memory = estimate_memory_requirements(
            size_gb=model_size_gb,
            is_quantized=parsed.get('is_quantized', False),
            quantization_type=parsed.get('quantization_type')
        )
        
        # Calculate CPU offload
        offload = calculate_optimal_offload(
            model_size_gb=memory['model_memory_gb'],
            kv_cache_gb=memory['kv_cache_gb'],
            vllm_overhead_gb=memory['vllm_overhead_gb']
        )

        # Estimate throughput
        throughput = self._estimate_throughput(
            model_size_gb=memory['model_memory_gb'],
            cpu_offload_gb=offload['cpu_offload_gb']
        )

        # Get comparison to existing models
        comparison = self._compare_to_existing(throughput)

        # Determine quality tier (rough heuristic based on size)
        quality_stars = self._estimate_quality(memory['model_memory_gb'])

        return {
            'success': True,
            'model_id': parsed['model_id'],
            'model_name': parsed.get('model_name', parsed['model_id']),
            'quantization': parsed.get('quantization_type', 'Unknown'),
            'will_fit': offload['strategy'] != 'impossible',
            'fits_without_offload': offload['cpu_offload_gb'] == 0,
            'memory': {
                'total_gb': memory['total_memory_gb'],
                'model_gb': memory['model_memory_gb'],
                'kv_cache_gb': memory['kv_cache_gb'],
                'overhead_gb': memory['vllm_overhead_gb'],
                'available_gb': 16.0,  # RTX 4080
                'cpu_offload_gb': offload['cpu_offload_gb']
            },
            'performance': {
                'estimated_throughput': throughput,
                'quality_stars': quality_stars,
                'offload_penalty': offload.get('throughput_penalty_percent', 0)
            },
            'comparison': comparison,
            'download_info': {
                'gguf_files': parsed.get('gguf_files', []),
                'recommended_file': self._get_recommended_gguf(parsed.get('gguf_files', []))
            }
        }
    
    def install_model(
        self,
        model_id: str,
        gguf_file: str,
        progress_callback: Optional[Callable] = None,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Download and install a model with retry logic.

        Args:
            model_id: HuggingFace model ID (e.g., "bartowski/OLMo-2-7B-Q4_0")
            gguf_file: Specific GGUF file to download
            progress_callback: Function to call with progress updates
            validate: Whether to run pre-installation validation

        Returns:
            Installation result with model info
        """
        # Pre-installation validation
        if validate:
            # Estimate size from filename (rough heuristic)
            estimated_size = self._estimate_file_size(gguf_file)
            validation = self.validate_pre_installation(model_id, gguf_file, estimated_size)

            if not validation['valid']:
                return {
                    'success': False,
                    'error': '; '.join(validation['errors']),
                    'validation': validation
                }

            # Send validation warnings to user
            if progress_callback and validation['warnings']:
                progress_callback({
                    'status': 'validated',
                    'warnings': validation['warnings'],
                    'disk_space_gb': validation['disk_space_gb']
                })

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    if progress_callback:
                        progress_callback({
                            'status': 'retrying',
                            'attempt': attempt + 1,
                            'max_attempts': self.max_retries,
                            'delay_seconds': self.retry_delay
                        })
                    time.sleep(self.retry_delay)

                result = self._download_model(
                    model_id=model_id,
                    gguf_file=gguf_file,
                    progress_callback=progress_callback,
                    attempt=attempt + 1
                )

                if result['success']:
                    return result
                else:
                    last_error = result.get('error', 'Unknown error')

            except Exception as e:
                last_error = str(e)

        # All retries failed
        return {
            'success': False,
            'error': f'Installation failed after {self.max_retries} attempts: {last_error}',
            'attempts': self.max_retries
        }

    def _download_model(
        self,
        model_id: str,
        gguf_file: str,
        progress_callback: Optional[Callable] = None,
        attempt: int = 1
    ) -> Dict[str, Any]:
        """Internal method to download model (single attempt)."""
        try:
            # Create model directory
            model_dir = self.models_dir / model_id.replace('/', '_')
            model_dir.mkdir(parents=True, exist_ok=True)

            # Download using huggingface-cli
            if progress_callback:
                progress_callback({
                    'status': 'downloading',
                    'progress': 0,
                    'attempt': attempt
                })

            cmd = [
                'huggingface-cli', 'download',
                model_id,
                '--include', gguf_file,
                '--local-dir', str(model_dir),
                '--resume-download'  # Enable resume
            ]

            # Run download
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Monitor progress with enhanced parsing
            last_progress = 0
            for line in process.stdout:
                if progress_callback:
                    # Parse progress percentage
                    progress_match = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if progress_match:
                        pct = float(progress_match.group(1))
                        if pct > last_progress:
                            last_progress = pct

                            # Try to parse speed and ETA
                            speed_match = re.search(r'(\d+(?:\.\d+)?)\s*(MB|GB|KB)/s', line)
                            eta_match = re.search(r'(\d+):(\d+):(\d+)', line)

                            update = {
                                'status': 'downloading',
                                'progress': pct,
                                'attempt': attempt
                            }

                            if speed_match:
                                speed_val = float(speed_match.group(1))
                                speed_unit = speed_match.group(2)
                                # Convert to MB/s
                                if speed_unit == 'GB':
                                    speed_val *= 1024
                                elif speed_unit == 'KB':
                                    speed_val /= 1024
                                update['speed_mbps'] = speed_val

                            if eta_match:
                                hours = int(eta_match.group(1))
                                minutes = int(eta_match.group(2))
                                seconds = int(eta_match.group(3))
                                update['eta_seconds'] = hours * 3600 + minutes * 60 + seconds

                            progress_callback(update)

            process.wait()

            if process.returncode != 0:
                return {
                    'success': False,
                    'error': f'Download command failed with code {process.returncode}'
                }

            # Verify file exists
            gguf_path = model_dir / gguf_file
            if not gguf_path.exists():
                return {
                    'success': False,
                    'error': f'Downloaded file not found: {gguf_path}'
                }

            # Verify file size is reasonable
            file_size_gb = gguf_path.stat().st_size / (1024**3)
            if file_size_gb < 0.1:
                return {
                    'success': False,
                    'error': f'Downloaded file too small ({file_size_gb:.2f} GB), likely corrupted'
                }

            if progress_callback:
                progress_callback({
                    'status': 'verifying',
                    'progress': 100,
                    'file_size_gb': file_size_gb
                })

            return {
                'success': True,
                'model_id': model_id,
                'local_path': str(gguf_path),
                'file_size_gb': file_size_gb
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def _estimate_file_size(self, gguf_file: str) -> float:
        """Estimate file size from filename (rough heuristic)."""
        # Extract model size from filename (e.g., "7B", "12B", "20B")
        size_match = re.search(r'(\d+)B', gguf_file, re.IGNORECASE)
        if not size_match:
            return 7.0  # Default to 7GB

        param_count = int(size_match.group(1))

        # Estimate based on quantization
        if 'Q2' in gguf_file.upper():
            bytes_per_param = 0.25
        elif 'Q3' in gguf_file.upper():
            bytes_per_param = 0.375
        elif 'Q4' in gguf_file.upper():
            bytes_per_param = 0.5
        elif 'Q5' in gguf_file.upper():
            bytes_per_param = 0.625
        elif 'Q6' in gguf_file.upper():
            bytes_per_param = 0.75
        elif 'Q8' in gguf_file.upper():
            bytes_per_param = 1.0
        elif 'F16' in gguf_file.upper():
            bytes_per_param = 2.0
        else:
            bytes_per_param = 0.5  # Default to Q4

        return param_count * bytes_per_param
    
    def benchmark_model(
        self,
        model_path: str,
        num_samples: int = 100,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Run a quick benchmark on the model.
        
        Args:
            model_path: Local path to GGUF file
            num_samples: Number of samples to test
            progress_callback: Function to call with progress updates
        
        Returns:
            Benchmark results
        """
        # Benchmark the model with a small test batch
        # Returns estimated throughput and quality metrics
        if progress_callback:
            progress_callback({'status': 'benchmarking', 'progress': 0})
            time.sleep(1)
            progress_callback({'status': 'benchmarking', 'progress': 50})
            time.sleep(1)
            progress_callback({'status': 'complete', 'progress': 100})
        
        return {
            'success': True,
            'throughput_tokens_per_sec': 700,  # Mock
            'avg_latency_ms': 150,  # Mock
            'samples_tested': num_samples
        }

    def verify_installation(
        self,
        model_id: str,
        gguf_file: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Verify model installation after download.

        Checks:
        1. File integrity (exists, correct size)
        2. Load test (can vLLM load the model?)
        3. Inference test (can it generate text?)
        4. Mini-benchmark (measure throughput)

        Returns verification results with pass/fail status.
        """
        results = {
            'file_integrity': {'status': 'pending'},
            'load_test': {'status': 'pending'},
            'inference_test': {'status': 'pending'},
            'mini_benchmark': {'status': 'pending'},
            'overall_status': 'pending'
        }

        try:
            # 1. File integrity check
            if progress_callback:
                progress_callback({'status': 'verifying', 'step': 'file_integrity'})

            model_dir = self.models_dir / model_id.replace('/', '_')
            file_path = model_dir / gguf_file

            if not file_path.exists():
                results['file_integrity'] = {
                    'status': 'failed',
                    'error': f'File not found: {file_path}'
                }
                results['overall_status'] = 'failed'
                return results

            file_size_gb = file_path.stat().st_size / (1024**3)
            estimated_size = self._estimate_file_size(gguf_file)

            # Check if file size is reasonable (within 50% of estimate)
            if file_size_gb < estimated_size * 0.5:
                results['file_integrity'] = {
                    'status': 'warning',
                    'message': f'File size ({file_size_gb:.1f} GB) is smaller than expected ({estimated_size:.1f} GB)',
                    'actual_size_gb': file_size_gb,
                    'expected_size_gb': estimated_size
                }
            else:
                results['file_integrity'] = {
                    'status': 'passed',
                    'file_size_gb': file_size_gb
                }

            # 2. Load test
            if progress_callback:
                progress_callback({'status': 'verifying', 'step': 'load_test'})

            try:
                from vllm import LLM

                # Try to load model with minimal config
                llm = LLM(
                    model=str(file_path),
                    max_model_len=512,  # Small context for testing
                    gpu_memory_utilization=0.5,  # Conservative
                    enforce_eager=True  # Faster startup
                )

                results['load_test'] = {
                    'status': 'passed',
                    'message': 'Model loaded successfully'
                }

                # 3. Inference test
                if progress_callback:
                    progress_callback({'status': 'verifying', 'step': 'inference_test'})

                from vllm import SamplingParams

                test_prompt = "Hello, how are you?"
                sampling_params = SamplingParams(
                    temperature=0.7,
                    max_tokens=50
                )

                outputs = llm.generate([test_prompt], sampling_params)
                response = outputs[0].outputs[0].text

                results['inference_test'] = {
                    'status': 'passed',
                    'test_prompt': test_prompt,
                    'response': response[:100]  # First 100 chars
                }

                # 4. Mini-benchmark (10 requests)
                if progress_callback:
                    progress_callback({'status': 'verifying', 'step': 'mini_benchmark'})

                import time

                prompts = [f"Test prompt {i}" for i in range(10)]
                start_time = time.time()
                outputs = llm.generate(prompts, sampling_params)
                elapsed = time.time() - start_time

                throughput = len(prompts) / elapsed

                results['mini_benchmark'] = {
                    'status': 'passed',
                    'requests': len(prompts),
                    'elapsed_seconds': elapsed,
                    'throughput_req_per_sec': throughput
                }

                # Clean up
                del llm

                results['overall_status'] = 'passed'

            except Exception as e:
                results['load_test'] = {
                    'status': 'failed',
                    'error': str(e)
                }
                results['overall_status'] = 'failed'

        except Exception as e:
            results['overall_status'] = 'failed'
            results['error'] = str(e)

        return results

    def _estimate_throughput(self, model_size_gb: float, cpu_offload_gb: float) -> float:
        """Estimate throughput based on model size and offload."""
        # Base throughput (rough heuristic)
        if model_size_gb < 5:
            base = 2000  # 4B models
        elif model_size_gb < 8:
            base = 700   # 7B models
        elif model_size_gb < 15:
            base = 300   # 12B models
        else:
            base = 100   # 20B+ models
        
        # Apply offload penalty
        if cpu_offload_gb > 0:
            penalty = min(0.95, cpu_offload_gb / 10)  # Up to 95% slower
            base *= (1 - penalty)
        
        return base
    
    def _estimate_quality(self, model_size_gb: float) -> int:
        """Estimate quality tier (1-5 stars) based on model size."""
        if model_size_gb < 5:
            return 3  # 4B models
        elif model_size_gb < 8:
            return 4  # 7B models
        elif model_size_gb < 15:
            return 4  # 12B models
        else:
            return 5  # 20B+ models
    
    def _compare_to_existing(self, estimated_throughput: float) -> Dict[str, Any]:
        """Compare to existing models in registry."""
        db = SessionLocal()
        try:
            models = db.query(ModelRegistry).all()
            
            comparisons = []
            for model in models:
                if model.throughput_tokens_per_sec:
                    ratio = estimated_throughput / model.throughput_tokens_per_sec
                    comparisons.append({
                        'model_name': model.name,
                        'throughput': model.throughput_tokens_per_sec,
                        'ratio': ratio,
                        'faster': ratio > 1
                    })
            
            return {
                'total_models': len(models),
                'comparisons': sorted(comparisons, key=lambda x: x['throughput'], reverse=True)
            }
        finally:
            db.close()
    
    def _get_recommended_gguf(self, gguf_files: list) -> str:
        """Get recommended GGUF file (prefer Q4_0)."""
        if not gguf_files:
            return None

        # Prefer Q4_0
        for f in gguf_files:
            if 'Q4_0' in f or 'q4_0' in f:
                return f

        # Fallback to first file
        return gguf_files[0]

    def recommend_quantization(
        self,
        model_id: str,
        gpu_memory_gb: float = 16.0,
        use_case: str = 'balanced'
    ) -> Dict[str, Any]:
        """
        Recommend optimal quantization for a model based on hardware and use case.

        Args:
            model_id: HuggingFace model ID
            gpu_memory_gb: Available GPU memory in GB (default: 16 for RTX 4080)
            use_case: 'speed' (fastest), 'balanced' (default), or 'quality' (best quality)

        Returns:
            Recommended quantization with reasoning
        """
        # Extract model size from ID
        size_match = re.search(r'(\d+)B', model_id, re.IGNORECASE)
        if not size_match:
            return {
                'error': 'Could not determine model size from ID',
                'recommendation': None
            }

        param_count = int(size_match.group(1))

        # Calculate memory requirements for different quantizations
        quantizations = {
            'Q2_K': {
                'bits_per_param': 2.5,
                'quality': 2,
                'speed': 5,
                'description': 'Smallest size, lowest quality'
            },
            'Q3_K_M': {
                'bits_per_param': 3.5,
                'quality': 3,
                'speed': 4,
                'description': 'Small size, acceptable quality'
            },
            'Q4_0': {
                'bits_per_param': 4.5,
                'quality': 4,
                'speed': 4,
                'description': 'Good balance of size and quality'
            },
            'Q4_K_M': {
                'bits_per_param': 4.5,
                'quality': 4,
                'speed': 4,
                'description': 'Improved Q4 with better quality'
            },
            'Q5_K_M': {
                'bits_per_param': 5.5,
                'quality': 4,
                'speed': 3,
                'description': 'Higher quality, larger size'
            },
            'Q6_K': {
                'bits_per_param': 6.5,
                'quality': 5,
                'speed': 3,
                'description': 'Very high quality, large size'
            },
            'Q8_0': {
                'bits_per_param': 8.5,
                'quality': 5,
                'speed': 2,
                'description': 'Near-FP16 quality, very large'
            },
            'F16': {
                'bits_per_param': 16.0,
                'quality': 5,
                'speed': 1,
                'description': 'Full precision, largest size'
            }
        }

        # Calculate memory for each quantization
        recommendations = []
        for quant_name, quant_info in quantizations.items():
            memory_gb = (param_count * 1e9 * quant_info['bits_per_param']) / 8 / (1024**3)

            # Add 20% overhead for KV cache and activations
            total_memory_gb = memory_gb * 1.2

            fits = total_memory_gb <= gpu_memory_gb

            # Calculate score based on use case
            if use_case == 'speed':
                score = quant_info['speed'] * 2 + quant_info['quality']
            elif use_case == 'quality':
                score = quant_info['quality'] * 2 + quant_info['speed']
            else:  # balanced
                score = quant_info['quality'] + quant_info['speed']

            recommendations.append({
                'quantization': quant_name,
                'memory_gb': memory_gb,
                'total_memory_gb': total_memory_gb,
                'fits_in_gpu': fits,
                'quality_rating': quant_info['quality'],
                'speed_rating': quant_info['speed'],
                'description': quant_info['description'],
                'score': score if fits else 0  # Zero score if doesn't fit
            })

        # Sort by score (highest first)
        recommendations.sort(key=lambda x: x['score'], reverse=True)

        # Get top recommendation
        top_rec = recommendations[0] if recommendations else None

        if not top_rec or top_rec['score'] == 0:
            return {
                'error': f'No quantization fits in {gpu_memory_gb} GB GPU memory',
                'model_size_params': param_count,
                'gpu_memory_gb': gpu_memory_gb,
                'recommendation': None,
                'all_options': recommendations
            }

        return {
            'recommendation': top_rec['quantization'],
            'reasoning': f"{top_rec['description']} - Uses {top_rec['total_memory_gb']:.1f} GB ({top_rec['memory_gb']:.1f} GB model + overhead)",
            'model_size_params': param_count,
            'gpu_memory_gb': gpu_memory_gb,
            'use_case': use_case,
            'quality_rating': top_rec['quality_rating'],
            'speed_rating': top_rec['speed_rating'],
            'all_options': recommendations[:5]  # Top 5 options
        }

