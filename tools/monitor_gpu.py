#!/usr/bin/env python3
"""
GPU Monitoring Tool for vLLM Benchmarks

Monitors GPU memory, utilization, and temperature during benchmark runs.
Saves metrics to a log file for analysis.

Usage:
    # Start monitoring in background
    python tools/monitor_gpu.py --output benchmarks/monitoring/vllm-5k-gpu.log --interval 1 &
    
    # Run your benchmark
    python benchmark_vllm_native.py batch_5k.jsonl output.jsonl
    
    # Stop monitoring (kill the process)
    pkill -f monitor_gpu.py
"""

import argparse
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path

def get_gpu_stats():
    """Query nvidia-smi for GPU stats."""
    try:
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=timestamp,memory.used,memory.total,utilization.gpu,utilization.memory,temperature.gpu,power.draw',
                '--format=csv,noheader,nounits'
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse output: timestamp, mem_used, mem_total, gpu_util, mem_util, temp, power
        parts = result.stdout.strip().split(', ')
        
        return {
            'timestamp': datetime.now().isoformat(),
            'memory_used_mb': int(parts[1]),
            'memory_total_mb': int(parts[2]),
            'memory_used_pct': round(int(parts[1]) / int(parts[2]) * 100, 1),
            'gpu_utilization_pct': int(parts[3]),
            'memory_utilization_pct': int(parts[4]),
            'temperature_c': int(parts[5]),
            'power_draw_w': float(parts[6])
        }
    except Exception as e:
        return {'error': str(e), 'timestamp': datetime.now().isoformat()}

def main():
    parser = argparse.ArgumentParser(description='Monitor GPU during benchmarks')
    parser.add_argument('--output', required=True, help='Output log file')
    parser.add_argument('--interval', type=float, default=1.0, help='Sampling interval in seconds (default: 1.0)')
    parser.add_argument('--summary', action='store_true', help='Print summary statistics')
    args = parser.parse_args()
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🔍 GPU Monitoring Started")
    print(f"📝 Logging to: {args.output}")
    print(f"⏱️  Interval: {args.interval}s")
    print(f"Press Ctrl+C to stop\n")
    
    samples = []
    
    try:
        with open(args.output, 'w') as f:
            # Write header
            f.write("# GPU Monitoring Log\n")
            f.write(f"# Started: {datetime.now().isoformat()}\n")
            f.write(f"# Interval: {args.interval}s\n\n")
            
            while True:
                stats = get_gpu_stats()
                samples.append(stats)
                
                # Write to file
                f.write(json.dumps(stats) + '\n')
                f.flush()
                
                # Print to console
                if 'error' not in stats:
                    print(f"[{stats['timestamp']}] "
                          f"MEM: {stats['memory_used_mb']:5d}/{stats['memory_total_mb']:5d} MB ({stats['memory_used_pct']:5.1f}%) | "
                          f"GPU: {stats['gpu_utilization_pct']:3d}% | "
                          f"TEMP: {stats['temperature_c']:3d}°C | "
                          f"PWR: {stats['power_draw_w']:6.1f}W")
                else:
                    print(f"[{stats['timestamp']}] ERROR: {stats['error']}")
                
                time.sleep(args.interval)
                
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")
        
        # Calculate summary statistics
        if samples and 'error' not in samples[0]:
            valid_samples = [s for s in samples if 'error' not in s]
            
            if valid_samples:
                mem_used = [s['memory_used_mb'] for s in valid_samples]
                mem_pct = [s['memory_used_pct'] for s in valid_samples]
                gpu_util = [s['gpu_utilization_pct'] for s in valid_samples]
                temps = [s['temperature_c'] for s in valid_samples]
                power = [s['power_draw_w'] for s in valid_samples]
                
                print("\n" + "=" * 80)
                print("📊 MONITORING SUMMARY")
                print("=" * 80)
                print(f"Duration:          {len(valid_samples) * args.interval:.1f}s ({len(valid_samples)} samples)")
                print(f"\nMemory Usage (MB):")
                print(f"  Min:             {min(mem_used):,} MB ({min(mem_pct):.1f}%)")
                print(f"  Max:             {max(mem_used):,} MB ({max(mem_pct):.1f}%)")
                print(f"  Avg:             {sum(mem_used)//len(mem_used):,} MB ({sum(mem_pct)/len(mem_pct):.1f}%)")
                print(f"\nGPU Utilization:")
                print(f"  Min:             {min(gpu_util)}%")
                print(f"  Max:             {max(gpu_util)}%")
                print(f"  Avg:             {sum(gpu_util)//len(gpu_util)}%")
                print(f"\nTemperature:")
                print(f"  Min:             {min(temps)}°C")
                print(f"  Max:             {max(temps)}°C")
                print(f"  Avg:             {sum(temps)//len(temps)}°C")
                print(f"\nPower Draw:")
                print(f"  Min:             {min(power):.1f}W")
                print(f"  Max:             {max(power):.1f}W")
                print(f"  Avg:             {sum(power)/len(power):.1f}W")
                print("=" * 80)
                
                # Save summary to file
                summary_file = output_path.with_suffix('.summary.json')
                summary = {
                    'duration_seconds': len(valid_samples) * args.interval,
                    'num_samples': len(valid_samples),
                    'memory_mb': {
                        'min': min(mem_used),
                        'max': max(mem_used),
                        'avg': sum(mem_used) // len(mem_used)
                    },
                    'memory_pct': {
                        'min': min(mem_pct),
                        'max': max(mem_pct),
                        'avg': round(sum(mem_pct) / len(mem_pct), 1)
                    },
                    'gpu_utilization_pct': {
                        'min': min(gpu_util),
                        'max': max(gpu_util),
                        'avg': sum(gpu_util) // len(gpu_util)
                    },
                    'temperature_c': {
                        'min': min(temps),
                        'max': max(temps),
                        'avg': sum(temps) // len(temps)
                    },
                    'power_w': {
                        'min': min(power),
                        'max': max(power),
                        'avg': round(sum(power) / len(power), 1)
                    }
                }
                
                with open(summary_file, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                print(f"\n✅ Summary saved: {summary_file}")

if __name__ == '__main__':
    main()

