#!/usr/bin/env python3
"""
Monitor vLLM batch processing progress and alert if stuck.

Usage:
    python3 monitor_batch_progress.py qwen3_4b_5k_offline.log

Features:
- Tracks progress over time
- Alerts if no progress for 5 minutes
- Shows GPU utilization
- Estimates completion time
"""

import sys
import time
import re
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

def get_gpu_stats():
    """Get GPU utilization and memory usage."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            gpu_util, mem_used, mem_total, temp = result.stdout.strip().split(', ')
            return {
                'utilization': int(gpu_util),
                'memory_used': int(mem_used),
                'memory_total': int(mem_total),
                'temperature': int(temp)
            }
    except Exception as e:
        print(f"⚠️  Failed to get GPU stats: {e}")
    
    return None

def parse_progress(log_file):
    """Parse the latest progress from log file."""
    if not Path(log_file).exists():
        return None
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Find all progress lines
    # Pattern: Running batch:  65% Completed | 3252/5000 [15:34<08:31,  3.42req/s]
    progress_lines = re.findall(
        r'Running batch:\s+(\d+)% Completed \| (\d+)/(\d+) \[([^\]]+)<([^\]]+),\s+([\d.]+)req/s\]',
        content
    )
    
    if not progress_lines:
        return None
    
    # Get the last progress line
    last_progress = progress_lines[-1]
    percent, completed, total, elapsed, remaining, req_per_sec = last_progress
    
    return {
        'percent': int(percent),
        'completed': int(completed),
        'total': int(total),
        'elapsed': elapsed,
        'remaining': remaining,
        'req_per_sec': float(req_per_sec),
        'timestamp': datetime.now()
    }

def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 monitor_batch_progress.py <log_file>")
        print("Example: python3 monitor_batch_progress.py qwen3_4b_5k_offline.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    if not Path(log_file).exists():
        print(f"❌ Log file not found: {log_file}")
        sys.exit(1)
    
    print(f"🔍 Monitoring: {log_file}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⚠️  Will alert if no progress for 5 minutes")
    print()
    
    last_progress = None
    last_completed = 0
    stuck_since = None
    check_interval = 30  # Check every 30 seconds
    
    try:
        while True:
            # Parse current progress
            current_progress = parse_progress(log_file)
            
            if current_progress:
                completed = current_progress['completed']
                total = current_progress['total']
                percent = current_progress['percent']
                req_per_sec = current_progress['req_per_sec']
                
                # Check if progress has been made
                if completed > last_completed:
                    # Progress made!
                    last_completed = completed
                    stuck_since = None
                    
                    # Get GPU stats
                    gpu = get_gpu_stats()
                    
                    # Print status
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Progress: {completed}/{total} ({percent}%) | "
                          f"Speed: {req_per_sec:.2f} req/s | "
                          f"ETA: {current_progress['remaining']}", end="")
                    
                    if gpu:
                        print(f" | GPU: {gpu['utilization']}% | "
                              f"VRAM: {gpu['memory_used']}/{gpu['memory_total']} MB | "
                              f"Temp: {gpu['temperature']}°C")
                    else:
                        print()
                    
                    # Check if complete
                    if completed >= total:
                        print()
                        print("🎉 Batch processing complete!")
                        print(f"✅ Processed {total} requests")
                        print(f"⏱️  Total time: {current_progress['elapsed']}")
                        print(f"⚡ Average speed: {req_per_sec:.2f} req/s")
                        break
                
                else:
                    # No progress made
                    if stuck_since is None:
                        stuck_since = datetime.now()
                    
                    stuck_duration = (datetime.now() - stuck_since).total_seconds()
                    
                    if stuck_duration > 300:  # 5 minutes
                        print()
                        print("🚨 ALERT: No progress for 5 minutes!")
                        print(f"   Last completed: {completed}/{total} ({percent}%)")
                        print(f"   Stuck since: {stuck_since.strftime('%H:%M:%S')}")
                        print(f"   Duration: {format_time(int(stuck_duration))}")
                        
                        gpu = get_gpu_stats()
                        if gpu:
                            print(f"   GPU utilization: {gpu['utilization']}%")
                            if gpu['utilization'] < 50:
                                print("   ⚠️  GPU utilization is low - process may be stuck!")
                        
                        print()
                        print("   Recommended actions:")
                        print("   1. Check log file for errors")
                        print("   2. Check GPU status with nvidia-smi")
                        print("   3. Consider killing and restarting the process")
                        print()
                        
                        # Reset stuck timer to avoid spamming
                        stuck_since = datetime.now()
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"No progress for {format_time(int(stuck_duration))} "
                              f"(last: {completed}/{total})")
            
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for progress data...")
            
            # Wait before next check
            time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print()
        print("👋 Monitoring stopped by user")
        if last_completed > 0:
            print(f"   Last progress: {last_completed}/{current_progress['total']} ({current_progress['percent']}%)")

if __name__ == '__main__':
    main()

