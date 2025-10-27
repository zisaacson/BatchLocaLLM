#!/usr/bin/env python3
"""
Analyze batch processing results

Usage:
    python analyze_results.py results.jsonl

Outputs:
    - Summary statistics
    - Score distribution
    - Error analysis
    - Performance metrics
    - CSV export
"""

import json
import sys
import csv
from collections import Counter
from typing import List, Dict, Optional

def load_results(jsonl_file: str) -> List[Dict]:
    """Load results from JSONL file"""
    results = []
    with open(jsonl_file, 'r') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

def analyze_results(results: List[Dict]) -> Dict:
    """Analyze batch results"""
    
    total = len(results)
    successful = 0
    failed = 0
    scores = []
    errors = []
    
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    
    for result in results:
        if result.get('error'):
            failed += 1
            errors.append({
                'custom_id': result['custom_id'],
                'error': result['error']
            })
        elif result.get('response'):
            successful += 1
            
            # Extract score
            try:
                content = result['response']['body']['choices'][0]['message']['content']
                score = float(content.strip())
                scores.append(score)
            except (ValueError, KeyError, IndexError):
                scores.append(None)
            
            # Extract token usage
            try:
                usage = result['response']['body']['usage']
                total_prompt_tokens += usage['prompt_tokens']
                total_completion_tokens += usage['completion_tokens']
                total_tokens += usage['total_tokens']
            except KeyError:
                pass
    
    # Calculate statistics
    valid_scores = [s for s in scores if s is not None]
    
    analysis = {
        'total': total,
        'successful': successful,
        'failed': failed,
        'success_rate': (successful / total * 100) if total > 0 else 0,
        'scores': {
            'count': len(valid_scores),
            'min': min(valid_scores) if valid_scores else None,
            'max': max(valid_scores) if valid_scores else None,
            'mean': sum(valid_scores) / len(valid_scores) if valid_scores else None,
            'distribution': Counter(valid_scores)
        },
        'tokens': {
            'total_prompt': total_prompt_tokens,
            'total_completion': total_completion_tokens,
            'total': total_tokens,
            'avg_prompt': total_prompt_tokens / successful if successful > 0 else 0,
            'avg_completion': total_completion_tokens / successful if successful > 0 else 0,
            'avg_total': total_tokens / successful if successful > 0 else 0
        },
        'errors': errors
    }
    
    return analysis

def print_summary(analysis: Dict):
    """Print analysis summary"""
    
    print("="*80)
    print("BATCH RESULTS ANALYSIS")
    print("="*80)
    
    # Overall stats
    print(f"\n📊 Overall Statistics:")
    print(f"   Total requests: {analysis['total']:,}")
    print(f"   Successful: {analysis['successful']:,} ({analysis['success_rate']:.2f}%)")
    print(f"   Failed: {analysis['failed']:,}")
    
    # Score statistics
    if analysis['scores']['count'] > 0:
        print(f"\n🎯 Score Statistics:")
        print(f"   Count: {analysis['scores']['count']:,}")
        print(f"   Min: {analysis['scores']['min']:.1f}")
        print(f"   Max: {analysis['scores']['max']:.1f}")
        print(f"   Mean: {analysis['scores']['mean']:.2f}")
        
        # Score distribution
        print(f"\n📈 Score Distribution:")
        dist = analysis['scores']['distribution']
        for score in sorted(dist.keys()):
            count = dist[score]
            pct = (count / analysis['scores']['count']) * 100
            bar = '█' * int(pct / 2)
            print(f"   {score:4.1f}: {count:6,} ({pct:5.1f}%) {bar}")
    
    # Token statistics
    print(f"\n🪙 Token Usage:")
    print(f"   Total prompt tokens: {analysis['tokens']['total_prompt']:,}")
    print(f"   Total completion tokens: {analysis['tokens']['total_completion']:,}")
    print(f"   Total tokens: {analysis['tokens']['total']:,}")
    print(f"   Avg prompt tokens/request: {analysis['tokens']['avg_prompt']:.1f}")
    print(f"   Avg completion tokens/request: {analysis['tokens']['avg_completion']:.1f}")
    
    # Calculate savings
    if analysis['successful'] > 0:
        baseline_tokens = analysis['successful'] * analysis['tokens']['avg_prompt']
        actual_tokens = analysis['tokens']['total_prompt']
        savings_pct = ((baseline_tokens - actual_tokens) / baseline_tokens) * 100 if baseline_tokens > 0 else 0
        
        print(f"\n💡 Token Optimization:")
        print(f"   Baseline (no optimization): {baseline_tokens:,.0f} prompt tokens")
        print(f"   Actual (with optimization): {actual_tokens:,} prompt tokens")
        print(f"   Token savings: {savings_pct:.1f}%")
    
    # Error analysis
    if analysis['failed'] > 0:
        print(f"\n❌ Errors ({analysis['failed']} total):")
        error_types = Counter([e['error'].get('type', 'unknown') for e in analysis['errors']])
        for error_type, count in error_types.most_common():
            print(f"   {error_type}: {count}")
        
        # Show first 5 errors
        print(f"\n   First {min(5, len(analysis['errors']))} errors:")
        for error in analysis['errors'][:5]:
            print(f"   - {error['custom_id']}: {error['error'].get('message', 'Unknown error')[:80]}")

def export_to_csv(results: List[Dict], output_file: str):
    """Export results to CSV"""
    
    print(f"\n💾 Exporting to CSV: {output_file}")
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'candidate_id',
            'score',
            'status',
            'error_message',
            'prompt_tokens',
            'completion_tokens',
            'total_tokens'
        ])
        writer.writeheader()
        
        for result in results:
            row = {
                'candidate_id': result['custom_id'],
                'score': None,
                'status': 'error' if result.get('error') else 'success',
                'error_message': None,
                'prompt_tokens': None,
                'completion_tokens': None,
                'total_tokens': None
            }
            
            if result.get('error'):
                row['error_message'] = result['error'].get('message', 'Unknown error')
            elif result.get('response'):
                try:
                    content = result['response']['body']['choices'][0]['message']['content']
                    row['score'] = float(content.strip())
                except (ValueError, KeyError, IndexError):
                    row['score'] = None
                
                try:
                    usage = result['response']['body']['usage']
                    row['prompt_tokens'] = usage['prompt_tokens']
                    row['completion_tokens'] = usage['completion_tokens']
                    row['total_tokens'] = usage['total_tokens']
                except KeyError:
                    pass
            
            writer.writerow(row)
    
    print(f"✅ Exported {len(results):,} results to {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python analyze_results.py results.jsonl [output.csv]")
        print()
        print("Examples:")
        print("  python analyze_results.py batch_output.jsonl")
        print("  python analyze_results.py batch_output.jsonl scores.csv")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Load results
    print(f"Loading results from {jsonl_file}...")
    results = load_results(jsonl_file)
    print(f"✅ Loaded {len(results):,} results")
    
    # Analyze
    analysis = analyze_results(results)
    
    # Print summary
    print_summary(analysis)
    
    # Export to CSV
    if csv_file:
        export_to_csv(results, csv_file)
    else:
        # Auto-generate CSV filename
        csv_file = jsonl_file.replace('.jsonl', '.csv')
        export_to_csv(results, csv_file)

if __name__ == "__main__":
    main()

