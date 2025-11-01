#!/bin/bash
#
# Monitor Benchmark Progress
#
# Shows real-time status of running benchmarks
#

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

clear

echo "================================================================================"
echo "📊 Benchmark Monitor"
echo "================================================================================"
echo ""

# Check worker status
echo "🔧 Worker Status:"
if [ -f "worker.pid" ]; then
    WORKER_PID=$(cat worker.pid)
    if ps -p $WORKER_PID > /dev/null 2>&1; then
        echo "   ✅ Running (PID: $WORKER_PID)"
        
        # Get worker uptime
        WORKER_START=$(ps -p $WORKER_PID -o lstart=)
        echo "   Started: $WORKER_START"
    else
        echo "   ❌ Not running (stale PID file)"
    fi
else
    echo "   ❌ Not running (no PID file)"
fi
echo ""

# Check GPU status
echo "🎮 GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits | while read line; do
        MEM_USED=$(echo $line | cut -d',' -f1)
        MEM_TOTAL=$(echo $line | cut -d',' -f2)
        GPU_UTIL=$(echo $line | cut -d',' -f3)
        TEMP=$(echo $line | cut -d',' -f4)
        
        MEM_PERCENT=$((MEM_USED * 100 / MEM_TOTAL))
        
        echo "   Memory: ${MEM_USED} MB / ${MEM_TOTAL} MB (${MEM_PERCENT}%)"
        echo "   Utilization: ${GPU_UTIL}%"
        echo "   Temperature: ${TEMP}°C"
    done
else
    echo "   ⚠️  nvidia-smi not available"
fi
echo ""

# Check batch jobs
echo "📋 Batch Jobs:"
if curl -s http://localhost:4080/health > /dev/null 2>&1; then
    JOBS=$(curl -s http://localhost:4080/v1/batches 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "$JOBS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    jobs = data.get('data', [])
    
    if not jobs:
        print('   No jobs found')
    else:
        for job in jobs:
            status = job.get('status', 'unknown')
            model = job.get('request_counts', {}).get('model', 'unknown')
            total = job.get('request_counts', {}).get('total', 0)
            completed = job.get('request_counts', {}).get('completed', 0)
            failed = job.get('request_counts', {}).get('failed', 0)
            
            if total > 0:
                pct = (completed / total) * 100
            else:
                pct = 0
            
            print(f'   • {job[\"id\"][:8]}... ({status})')
            print(f'     Model: {model}')
            print(f'     Progress: {completed}/{total} ({pct:.1f}%)')
            if failed > 0:
                print(f'     Failed: {failed}')
except:
    print('   ⚠️  Could not parse job data')
"
    else
        echo "   ⚠️  Could not fetch jobs"
    fi
else
    echo "   ❌ API server not responding"
fi
echo ""

# Show recent worker logs
echo "📝 Recent Worker Logs (last 10 lines):"
if [ -f "logs/worker.log" ]; then
    tail -10 logs/worker.log | sed 's/^/   /'
else
    echo "   ⚠️  No worker log file"
fi
echo ""

echo "================================================================================"
echo "💡 Commands:"
echo "   • Watch this:     watch -n 5 ./scripts/monitor_benchmark.sh"
echo "   • Worker logs:    tail -f logs/worker.log"
echo "   • GPU monitor:    watch -n 1 nvidia-smi"
echo "   • Stop worker:    kill \$(cat worker.pid)"
echo "================================================================================"

