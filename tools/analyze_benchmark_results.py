#!/usr/bin/env python3
"""
Analyze benchmark results from all models.
Compares speed, quality, and cost metrics.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def parse_log_file(log_file):
    """Extract timing and throughput metrics from log file."""
    if not Path(log_file).exists():
        return None
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Extract final progress line
    # Pattern: Running batch:  65% Completed | 3252/5000 [15:34<08:31,  3.42req/s]
    progress_lines = re.findall(r'Running batch:\s+(\d+)% Completed \| (\d+)/(\d+) \[([^\]]+)<([^\]]+),\s+([\d.]+)req/s\]', content)
    
    if not progress_lines:
        return None
    
    # Get the last progress line
    last_progress = progress_lines[-1]
    percent, completed, total, elapsed, remaining, req_per_sec = last_progress
    
    return {
        'completed': int(completed),
        'total': int(total),
        'percent': int(percent),
        'req_per_sec': float(req_per_sec),
        'elapsed': elapsed,
        'remaining': remaining
    }

def analyze_quality(results_file):
    """Analyze response quality from results file."""
    if not Path(results_file).exists():
        return None
    
    recommendations = defaultdict(int)
    total = 0
    errors = 0
    
    with open(results_file, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                result = json.loads(line)
                total += 1
                
                # Check for errors
                if result.get('error'):
                    errors += 1
                    continue
                
                # Extract recommendation from response
                content = result.get('response', {}).get('body', {}).get('choices', [{}])[0].get('message', {}).get('content', '')
                
                # Try to parse JSON response
                try:
                    response_json = json.loads(content)
                    rec = response_json.get('recommendation', 'Unknown')
                    recommendations[rec] += 1
                except:
                    # Try to extract recommendation from text
                    rec_match = re.search(r'"recommendation":\s*"([^"]+)"', content)
                    if rec_match:
                        recommendations[rec_match.group(1)] += 1
                    else:
                        recommendations['Parse Error'] += 1
            except Exception as e:
                errors += 1
    
    return {
        'total': total,
        'errors': errors,
        'recommendations': dict(recommendations),
        'success_rate': (total - errors) / total * 100 if total > 0 else 0
    }

def main():
    models = [
        {
            'name': 'Qwen 3-4B',
            'log': 'qwen3_4b_5k_offline.log',
            'results': 'qwen3_4b_5k_offline_results.jsonl',
            'size': '4B',
            'vram': '7.6 GB'
        },
        {
            'name': 'Gemma 3-4B',
            'log': 'gemma3_4b_5k_offline.log',
            'results': 'gemma3_4b_5k_offline_results.jsonl',
            'size': '4B',
            'vram': '8.6 GB'
        },
        {
            'name': 'Llama 3.2-3B',
            'log': 'llama32_3b_5k_offline.log',
            'results': 'llama32_3b_5k_offline_results.jsonl',
            'size': '3B',
            'vram': '6.0 GB'
        },
        {
            'name': 'Llama 3.2-1B',
            'log': 'llama32_1b_5k_offline.log',
            'results': 'llama32_1b_5k_offline_results.jsonl',
            'size': '1B',
            'vram': '2.5 GB'
        }
    ]
    
    print("=" * 80)
    print("📊 Benchmark Results Analysis")
    print("=" * 80)
    print()
    
    results = []
    
    for model in models:
        print(f"Analyzing {model['name']}...")

        # Parse log file
        timing = parse_log_file(model['log'])

        # Analyze quality
        quality = analyze_quality(model['results'])

        if timing and quality:
            print(f"  ✅ Found complete results for {model['name']}")
            results.append({
                'model': model,
                'timing': timing,
                'quality': quality
            })
        else:
            print(f"  ⏭️  Skipping {model['name']} (not complete yet)")
    
    if not results:
        print("❌ No results found. Run benchmarks first!")
        return
    
    print()
    print("=" * 80)
    print("⚡ Performance Comparison")
    print("=" * 80)
    print()
    print(f"{'Model':<20} {'Size':<8} {'VRAM':<10} {'Speed':<15} {'Completed':<12} {'Success Rate':<12}")
    print("-" * 80)
    
    for r in results:
        model = r['model']
        timing = r['timing']
        quality = r['quality']
        
        print(f"{model['name']:<20} {model['size']:<8} {model['vram']:<10} "
              f"{timing['req_per_sec']:.2f} req/s{'':<5} "
              f"{timing['completed']}/{timing['total']:<6} "
              f"{quality['success_rate']:.1f}%")
    
    print()
    print("=" * 80)
    print("📈 Throughput Estimates for 170K Candidates")
    print("=" * 80)
    print()
    print(f"{'Model':<20} {'Speed':<15} {'Time for 170K':<20} {'Requests/Hour':<15}")
    print("-" * 80)
    
    for r in results:
        model = r['model']
        timing = r['timing']
        
        req_per_sec = timing['req_per_sec']
        req_per_hour = req_per_sec * 3600
        hours_for_170k = 170000 / req_per_hour
        
        print(f"{model['name']:<20} {req_per_sec:.2f} req/s{'':<5} "
              f"{hours_for_170k:.1f} hours{'':<12} "
              f"{req_per_hour:.0f}")
    
    print()
    print("=" * 80)
    print("🎯 Quality Analysis")
    print("=" * 80)
    print()
    
    for r in results:
        model = r['model']
        quality = r['quality']
        
        print(f"\n{model['name']}:")
        print(f"  Total responses: {quality['total']}")
        print(f"  Errors: {quality['errors']}")
        print(f"  Success rate: {quality['success_rate']:.1f}%")
        print(f"  Recommendations:")
        
        for rec, count in sorted(quality['recommendations'].items(), key=lambda x: x[1], reverse=True):
            pct = count / quality['total'] * 100 if quality['total'] > 0 else 0
            print(f"    {rec}: {count} ({pct:.1f}%)")
    
    print()
    print("=" * 80)
    print("💡 Recommendations")
    print("=" * 80)
    print()
    
    # Find fastest model
    fastest = max(results, key=lambda r: r['timing']['req_per_sec'])
    print(f"⚡ Fastest: {fastest['model']['name']} ({fastest['timing']['req_per_sec']:.2f} req/s)")
    
    # Find highest quality (lowest error rate)
    best_quality = min(results, key=lambda r: r['quality']['errors'] / r['quality']['total'] if r['quality']['total'] > 0 else 1)
    print(f"🎯 Best Quality: {best_quality['model']['name']} ({best_quality['quality']['success_rate']:.1f}% success)")
    
    # Find best balance (speed * quality)
    best_balance = max(results, key=lambda r: r['timing']['req_per_sec'] * (r['quality']['success_rate'] / 100))
    print(f"⚖️  Best Balance: {best_balance['model']['name']}")
    
    print()

if __name__ == '__main__':
    main()

