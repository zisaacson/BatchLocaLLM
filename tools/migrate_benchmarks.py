#!/usr/bin/env python3
"""
Migrate old benchmark data to unified format.

Converts data from:
- benchmark_results/*.json (old format)
- benchmarks/metadata/*.json (metadata format)

To the new unified format.
"""

import json
import glob
from pathlib import Path
from datetime import datetime

def migrate_old_benchmark_results():
    """Migrate files from benchmark_results/ to unified format."""
    print("🔄 Migrating old benchmark_results/*.json files...")
    
    files = glob.glob('benchmark_results/*.json')
    migrated = 0
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Check if already in new format
            if isinstance(data, dict) and 'test_name' in data:
                print(f"  ✓ {filepath} - already in new format")
                continue
            
            # Handle array of results (old format)
            if isinstance(data, list):
                for item in data:
                    # Already has most fields, just ensure consistency
                    if 'test_name' not in item:
                        # Generate test name from model and mode
                        model_short = item.get('model', 'unknown').split('/')[-1]
                        mode = item.get('mode', 'unknown')
                        size = item.get('size', item.get('num_requests', 0))
                        item['test_name'] = f"{model_short}_{size}_{mode}"
                    
                    # Ensure all required fields exist
                    item.setdefault('num_requests', item.get('size', 0))
                    item.setdefault('successful_requests', item.get('num_requests', 0))
                    item.setdefault('failed_requests', 0)
                    item.setdefault('latency_p50_ms', 0)
                    item.setdefault('latency_p95_ms', 0)
                    item.setdefault('latency_p99_ms', 0)
                    item.setdefault('latency_min_ms', 0)
                    item.setdefault('latency_max_ms', 0)
                    item.setdefault('config', {})
                
                # Save back
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2)
                
                print(f"  ✓ {filepath} - migrated {len(data)} results")
                migrated += 1
        
        except Exception as e:
            print(f"  ✗ {filepath} - error: {e}")
    
    print(f"✅ Migrated {migrated} files\n")

def migrate_metadata_files():
    """Migrate files from benchmarks/metadata/ to benchmark_results/."""
    print("🔄 Migrating benchmarks/metadata/*.json files...")
    
    files = glob.glob('benchmarks/metadata/*.json')
    migrated = 0
    
    for filepath in files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extract test_id as test_name
            test_name = data.get('test_id', Path(filepath).stem)
            model = data.get('model', 'unknown')
            
            # Extract results
            results = data.get('results', {})
            
            # Create unified format
            unified = {
                'test_name': test_name,
                'model': model,
                'mode': data.get('platform', 'vllm_offline_batch').replace('vllm-native', 'offline_batch'),
                'timestamp': data.get('timestamp', datetime.now().isoformat()),
                
                # Timing
                'model_load_time_seconds': results.get('model_load_time_seconds', 0),
                'inference_time_seconds': results.get('inference_time_seconds', 0),
                'total_time_seconds': results.get('total_time_seconds', 0),
                
                # Requests
                'num_requests': data.get('test', {}).get('num_requests', 0),
                'successful_requests': results.get('success_count', 0),
                'failed_requests': results.get('failure_count', 0),
                'success_rate_pct': 100.0 if results.get('failure_count', 0) == 0 else 0.0,
                
                # Tokens
                'prompt_tokens': results.get('prompt_tokens', 0),
                'completion_tokens': results.get('completion_tokens', 0),
                'total_tokens': results.get('total_tokens', 0),
                'avg_prompt_tokens': 0,
                'avg_completion_tokens': 0,
                
                # Throughput
                'throughput_req_per_sec': results.get('throughput_requests_per_sec', 0),
                'throughput_tokens_per_sec': results.get('throughput_tokens_per_sec', 0),
                
                # Latency (not available in old format)
                'latency_p50_ms': 0,
                'latency_p95_ms': 0,
                'latency_p99_ms': 0,
                'latency_min_ms': 0,
                'latency_max_ms': 0,
                
                # Config
                'config': data.get('config', {}),
                'notes': f"Migrated from {filepath}"
            }
            
            # Calculate averages
            if unified['successful_requests'] > 0:
                unified['avg_prompt_tokens'] = unified['prompt_tokens'] / unified['successful_requests']
                unified['avg_completion_tokens'] = unified['completion_tokens'] / unified['successful_requests']
                unified['success_rate_pct'] = (unified['successful_requests'] / unified['num_requests']) * 100
            
            # Save to benchmark_results/
            output_file = f"benchmark_results/{test_name}_migrated.json"
            with open(output_file, 'w') as f:
                json.dump(unified, f, indent=2)
            
            print(f"  ✓ {filepath} -> {output_file}")
            migrated += 1
        
        except Exception as e:
            print(f"  ✗ {filepath} - error: {e}")
    
    print(f"✅ Migrated {migrated} metadata files\n")

def main():
    print("=" * 80)
    print("BENCHMARK DATA MIGRATION")
    print("=" * 80)
    print()
    
    # Create backup
    import shutil
    import time
    backup_dir = f"benchmark_results_backup_{int(time.time())}"
    print(f"📦 Creating backup: {backup_dir}/")
    shutil.copytree('benchmark_results', backup_dir, dirs_exist_ok=True)
    print()
    
    # Run migrations
    migrate_old_benchmark_results()
    migrate_metadata_files()
    
    print("=" * 80)
    print("✅ MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Check benchmark_results/ for migrated files")
    print("2. View at http://localhost:8001/benchmarks.html")
    print("3. Use benchmark_unified.py for all new benchmarks")
    print()
    print(f"Backup saved to: {backup_dir}/")

if __name__ == '__main__':
    main()

