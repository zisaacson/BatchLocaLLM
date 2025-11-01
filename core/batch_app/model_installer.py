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
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from .model_parser import parse_huggingface_content, estimate_memory_requirements
from .smart_offload import calculate_optimal_offload
from .database import ModelRegistry, SessionLocal


class ModelInstaller:
    """Handles complete model installation flow."""
    
    def __init__(self, models_dir: Path = Path("./models")):
        self.models_dir = models_dir
        self.models_dir.mkdir(exist_ok=True)
    
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
        
        if not parsed['success']:
            return {
                'success': False,
                'error': parsed.get('error', 'Failed to parse model information')
            }
        
        # Estimate memory requirements
        memory = estimate_memory_requirements(
            model_id=parsed['model_id'],
            quantization=parsed.get('quantization_type'),
            model_size_gb=parsed.get('model_size_gb')
        )
        
        # Calculate CPU offload
        offload = calculate_optimal_offload(
            model_size_gb=memory['model_size_gb'],
            kv_cache_gb=memory['kv_cache_gb'],
            overhead_gb=memory['overhead_gb']
        )
        
        # Estimate throughput
        throughput = self._estimate_throughput(
            model_size_gb=memory['model_size_gb'],
            cpu_offload_gb=offload['cpu_offload_gb']
        )
        
        # Get comparison to existing models
        comparison = self._compare_to_existing(throughput)
        
        # Determine quality tier (rough heuristic based on size)
        quality_stars = self._estimate_quality(memory['model_size_gb'])
        
        return {
            'success': True,
            'model_id': parsed['model_id'],
            'model_name': parsed.get('model_name', parsed['model_id']),
            'quantization': parsed.get('quantization_type', 'Unknown'),
            'will_fit': offload['strategy'] != 'impossible',
            'fits_without_offload': offload['cpu_offload_gb'] == 0,
            'memory': {
                'total_gb': memory['total_memory_gb'],
                'model_gb': memory['model_size_gb'],
                'kv_cache_gb': memory['kv_cache_gb'],
                'overhead_gb': memory['overhead_gb'],
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
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Download and install a model.
        
        Args:
            model_id: HuggingFace model ID (e.g., "bartowski/OLMo-2-7B-Q4_0")
            gguf_file: Specific GGUF file to download
            progress_callback: Function to call with progress updates
        
        Returns:
            Installation result with model info
        """
        try:
            # Create model directory
            model_dir = self.models_dir / model_id.replace('/', '_')
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Download using huggingface-cli
            if progress_callback:
                progress_callback({'status': 'downloading', 'progress': 0})
            
            cmd = [
                'huggingface-cli', 'download',
                model_id,
                '--include', gguf_file,
                '--local-dir', str(model_dir)
            ]
            
            # Run download
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Monitor progress
            for line in process.stdout:
                if progress_callback and '%' in line:
                    # Parse progress from output
                    try:
                        pct = float(line.split('%')[0].split()[-1])
                        progress_callback({'status': 'downloading', 'progress': pct})
                    except:
                        pass
            
            process.wait()
            
            if process.returncode != 0:
                return {
                    'success': False,
                    'error': 'Download failed'
                }
            
            # Verify file exists
            gguf_path = model_dir / gguf_file
            if not gguf_path.exists():
                return {
                    'success': False,
                    'error': f'Downloaded file not found: {gguf_path}'
                }
            
            if progress_callback:
                progress_callback({'status': 'complete', 'progress': 100})
            
            return {
                'success': True,
                'model_id': model_id,
                'local_path': str(gguf_path),
                'file_size_gb': gguf_path.stat().st_size / (1024**3)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
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
        # TODO: Implement actual benchmarking
        # For now, return mock data
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

