#!/usr/bin/env python3
"""
Migrate existing benchmark results to standardized structure.
Creates metadata and organizes files properly.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import re

# Existing results to migrate
RESULTS_TO_MIGRATE = [
    {
        'model_id': 'qwen-3-4b',
        'model_name': 'Qwen 3-4B',
        'hf_id': 'Qwen/Qwen3-4B-Instruct-2507',
        'results_file': 'qwen3_4b_5k_offline_results.jsonl',
        'log_file': 'qwen3_4b_5k_offline.log',
        'dataset': 'batch_5k.jsonl',
        'size': '4B',
        'vram_gb': 7.6,
        'timestamp': '2024-10-28T14:33:00Z'
    },
    {
        'model_id': 'gemma-3-4b',
        'model_name': 'Gemma 3-4B',
        'hf_id': 'google/gemma-3-4b-it',
        'results_file': 'benchmarks/raw/vllm-native-gemma3-4b-5000-2025-10-28.jsonl',
        'log_file': None,  # No log file found
        'dataset': 'batch_5k.jsonl',
        'size': '4B',
        'vram_gb': 8.6,
        'timestamp': '2024-10-28T08:40:00Z'
    },
    {
        'model_id': 'llama-3.2-3b',
        'model_name': 'Llama 3.2-3B',
        'hf_id': 'meta-llama/Llama-3.2-3B-Instruct',
        'results_file': 'llama32_3b_5k_results.jsonl',
        'log_file': 'llama32_3b_5k_batch.log',
        'dataset': 'batch_5k.jsonl',
        'size': '3B',
        'vram_gb': 6.0,
        'timestamp': '2024-10-28T12:00:00Z'
    },
    {
        'model_id': 'llama-3.2-1b',
        'model_name': 'Llama 3.2-1B',
        'hf_id': 'meta-llama/Llama-3.2-1B-Instruct',
        'results_file': 'llama32_1b_5k_results.jsonl',
        'log_file': 'llama32_1b_test.log',
        'dataset': 'batch_5k.jsonl',
        'size': '1B',
        'vram_gb': 2.5,
        'timestamp': '2024-10-28T10:47:00Z'
    }
]

def parse_log_metrics(log_file):
    """Extract metrics from log file."""
    if not log_file or not Path(log_file).exists():
        return None
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Pattern: Running batch:  100% Completed | 5000/5000 [24:35<00:00,  3.39req/s]
    progress_lines = re.findall(
        r'Running batch:\s+(\d+)% Completed \| (\d+)/(\d+) \[([^\]]+)<([^\]]+),\s+([\d.]+)req/s\]',
        content
    )
    
    if not progress_lines:
        return None
    
    last = progress_lines[-1]
    percent, completed, total, elapsed, remaining, req_per_sec = last
    
    return {
        'completed': int(completed),
        'total': int(total),
        'req_per_sec': float(req_per_sec),
        'elapsed': elapsed
    }

def analyze_results(results_file):
    """Analyze results file for success/error counts."""
    if not Path(results_file).exists():
        return None
    
    total = 0
    success = 0
    errors = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    
    with open(results_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                result = json.loads(line)
                total += 1
                
                status_code = result.get('response', {}).get('status_code')
                if status_code == 200:
                    success += 1
                    usage = result.get('response', {}).get('body', {}).get('usage', {})
                    total_prompt_tokens += usage.get('prompt_tokens', 0)
                    total_completion_tokens += usage.get('completion_tokens', 0)
                else:
                    errors += 1
            except:
                errors += 1
    
    return {
        'total': total,
        'success': success,
        'errors': errors,
        'success_rate': (success / total * 100) if total > 0 else 0,
        'avg_prompt_tokens': total_prompt_tokens // total if total > 0 else 0,
        'avg_completion_tokens': total_completion_tokens // total if total > 0 else 0
    }

def extract_evaluation_criteria(dataset_file):
    """Extract evaluation criteria from first request in dataset."""
    if not Path(dataset_file).exists():
        return {}
    
    with open(dataset_file, 'r') as f:
        first_line = f.readline()
        if not first_line.strip():
            return {}
        
        try:
            request = json.loads(first_line)
            messages = request.get('body', {}).get('messages', [])
            
            # Find system message with criteria
            for msg in messages:
                if msg.get('role') == 'system':
                    content = msg.get('content', '')
                    return {
                        'full_prompt': content,
                        'has_educational_pedigree': 'Educational Pedigree' in content,
                        'has_company_pedigree': 'Company Pedigree' in content,
                        'has_trajectory': 'Trajectory' in content,
                        'has_is_software_engineer': 'Is Software Engineer' in content
                    }
        except:
            pass
    
    return {}

def migrate_results():
    """Migrate all existing results to new structure."""
    results_dir = Path('results')
    results_dir.mkdir(exist_ok=True)
    
    metadata_registry = {
        'runs': [],
        'datasets': {},
        'models': {}
    }
    
    print("🔄 Migrating existing benchmark results...")
    print()
    
    for config in RESULTS_TO_MIGRATE:
        model_id = config['model_id']
        model_name = config['model_name']
        results_file = config['results_file']
        
        print(f"📦 Processing {model_name}...")
        
        # Check if results file exists
        if not Path(results_file).exists():
            print(f"  ⚠️  Results file not found: {results_file}")
            continue
        
        # Create model directory
        model_dir = results_dir / model_id
        model_dir.mkdir(exist_ok=True)
        
        # Generate run ID
        timestamp_str = config['timestamp'].replace(':', '').replace('-', '').replace('Z', '')[:15]
        run_id = f"{model_id}-batch_5k-{timestamp_str}"
        
        # Copy results file
        new_results_file = model_dir / f"batch_5k_{timestamp_str}.jsonl"
        shutil.copy2(results_file, new_results_file)
        print(f"  ✅ Copied results to {new_results_file}")
        
        # Copy log file if exists
        new_log_file = None
        if config['log_file'] and Path(config['log_file']).exists():
            new_log_file = model_dir / f"batch_5k_{timestamp_str}.log"
            shutil.copy2(config['log_file'], new_log_file)
            print(f"  ✅ Copied log to {new_log_file}")
        
        # Analyze results
        results_analysis = analyze_results(results_file)
        log_metrics = parse_log_metrics(config['log_file'])
        
        # Create metadata
        run_metadata = {
            'run_id': run_id,
            'model': {
                'name': model_name,
                'id': config['hf_id'],
                'size': config['size'],
                'vram_gb': config['vram_gb']
            },
            'dataset': {
                'name': config['dataset'],
                'count': results_analysis['total'] if results_analysis else 0,
                'criteria': extract_evaluation_criteria(config['dataset'])
            },
            'execution': {
                'started_at': config['timestamp'],
                'req_per_sec': log_metrics['req_per_sec'] if log_metrics else None,
                'elapsed': log_metrics['elapsed'] if log_metrics else None
            },
            'results': results_analysis or {},
            'files': {
                'results': str(new_results_file),
                'log': str(new_log_file) if new_log_file else None,
                'input': config['dataset']
            }
        }
        
        # Save individual metadata
        meta_file = model_dir / f"batch_5k_{timestamp_str}.meta.json"
        with open(meta_file, 'w') as f:
            json.dump(run_metadata, f, indent=2)
        print(f"  ✅ Created metadata {meta_file}")
        
        # Add to registry
        metadata_registry['runs'].append({
            'run_id': run_id,
            'model': model_name,
            'dataset': config['dataset'],
            'status': 'completed' if results_analysis and results_analysis['success'] > 0 else 'failed',
            'timestamp': config['timestamp'],
            'results_file': str(new_results_file),
            'success_rate': results_analysis['success_rate'] if results_analysis else 0
        })
        
        # Update models registry
        if model_id not in metadata_registry['models']:
            metadata_registry['models'][model_id] = {
                'name': model_name,
                'hf_id': config['hf_id'],
                'runs': 0
            }
        metadata_registry['models'][model_id]['runs'] += 1
        
        print()
    
    # Add dataset info
    dataset_criteria = extract_evaluation_criteria('batch_5k.jsonl')
    metadata_registry['datasets']['batch_5k.jsonl'] = {
        'count': 5000,
        'prompt_version': 'candidate_evaluation_v1',
        'created': '2024-10-27T10:00:00Z',
        'criteria': dataset_criteria
    }
    
    # Save central registry
    registry_file = results_dir / 'metadata.json'
    with open(registry_file, 'w') as f:
        json.dump(metadata_registry, f, indent=2)
    
    print(f"✅ Created central registry: {registry_file}")
    print()
    print("=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"Total runs migrated: {len(metadata_registry['runs'])}")
    print(f"Models: {len(metadata_registry['models'])}")
    print(f"Datasets: {len(metadata_registry['datasets'])}")
    print()
    print("✅ Migration complete!")

if __name__ == '__main__':
    migrate_results()

