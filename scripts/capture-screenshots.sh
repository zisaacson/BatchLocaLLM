#!/bin/bash
# Screenshot Capture Helper Script
# This script opens all the URLs you need to screenshot in your browser

set -e

echo "🖼️  Screenshot Capture Helper"
echo "================================"
echo ""
echo "This script will open all the pages you need to screenshot."
echo "After each page opens, take a screenshot and save it to the specified location."
echo ""
echo "Press ENTER to continue..."
read

# Check if services are running
echo "Checking if services are running..."
if ! curl -s http://localhost:4080/health > /dev/null 2>&1; then
    echo "❌ Batch API not running on port 4080"
    echo "   Start with: ./scripts/start-services.sh"
    exit 1
fi

echo "✅ Services are running!"
echo ""

# Function to open URL and wait
open_and_wait() {
    local url=$1
    local name=$2
    local save_path=$3
    local instructions=$4
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📸 Screenshot: $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "URL: $url"
    echo "Save to: $save_path"
    echo ""
    echo "Instructions:"
    echo "$instructions"
    echo ""
    echo "Opening in browser..."
    
    # Open URL in default browser
    if command -v xdg-open > /dev/null; then
        xdg-open "$url" 2>/dev/null
    elif command -v open > /dev/null; then
        open "$url"
    else
        echo "Please open this URL manually: $url"
    fi
    
    echo ""
    echo "Press ENTER when you've saved the screenshot..."
    read
    echo ""
}

# 1. Swagger UI - API Documentation
open_and_wait \
    "http://localhost:4080/docs" \
    "Swagger UI - API Documentation" \
    "docs/screenshots/swagger-ui/api-docs.png" \
    "- Capture the full Swagger UI interface
- Show the list of endpoints (expand 'Batch Operations' section)
- Make sure the vLLM Batch Server title is visible
- Recommended size: 1920x1080 or full browser window"

# 2. Queue Monitor - Empty State
open_and_wait \
    "http://localhost:4080/queue" \
    "Queue Monitor - Empty State" \
    "docs/screenshots/queue-monitor/empty-state.png" \
    "- Capture the queue monitor with no jobs
- Show the 'No jobs in queue' message
- Make sure the header and stats are visible
- Recommended size: 1920x1080"

# 3. Queue Monitor - With Jobs (need to submit a job first)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📸 Screenshot: Queue Monitor - With Jobs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "First, let's submit a test batch job..."
echo ""

# Submit a test batch
BATCH_ID=$(curl -s -X POST http://localhost:4080/v1/batches \
    -H "Content-Type: application/json" \
    -d '{
        "input_file_id": "file-test-quickstart",
        "metadata": {"model": "google/gemma-3-4b-it"}
    }' | jq -r '.id')

if [ -n "$BATCH_ID" ]; then
    echo "✅ Submitted batch: $BATCH_ID"
    echo ""
    
    open_and_wait \
        "http://localhost:4080/queue" \
        "Queue Monitor - With Jobs" \
        "docs/screenshots/queue-monitor/with-jobs.png" \
        "- Capture the queue monitor with the test job
- Show job ID, status, model, progress
- Make sure the stats (total jobs, processing, etc.) are visible
- Recommended size: 1920x1080"
else
    echo "❌ Failed to submit batch job"
    echo "   You'll need to submit a job manually and screenshot the queue"
fi

# 4. Grafana - Dashboard
open_and_wait \
    "http://localhost:4220/d/vllm-batch-server/vllm-batch-server?orgId=1&refresh=5s" \
    "Grafana - Main Dashboard" \
    "docs/screenshots/grafana/main-dashboard.png" \
    "- Capture the main Grafana dashboard
- Show GPU metrics, job throughput, queue depth
- Make sure graphs have some data (may need to wait a bit)
- Recommended size: 1920x1080
- Login: admin/admin (if prompted)"

# 5. Label Studio - Projects
open_and_wait \
    "http://localhost:4115/projects" \
    "Label Studio - Projects List" \
    "docs/screenshots/label-studio/projects-list.png" \
    "- Capture the Label Studio projects page
- Show any existing projects
- Make sure the 'Create Project' button is visible
- Recommended size: 1920x1080
- Login with your credentials if prompted"

# 6. Label Studio - Project View (if project exists)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📸 Screenshot: Label Studio - Project View"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "If you have a project with data, open it and screenshot:"
echo "- The task list view"
echo "- An individual labeling task"
echo ""
echo "Save to: docs/screenshots/label-studio/project-view.png"
echo "         docs/screenshots/label-studio/labeling-interface.png"
echo ""
echo "Press ENTER to continue..."
read

# 7. Model Management UI
open_and_wait \
    "http://localhost:4080/models/install" \
    "Model Management - Installation UI" \
    "docs/screenshots/model-management/install-ui.png" \
    "- Capture the model installation interface
- Show the HuggingFace URL input field
- Show the 'Analyze Model' button
- Recommended size: 1920x1080"

# 8. Benchmark Results (if available)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📸 Screenshot: Benchmark Results"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "If you have benchmark results, screenshot them:"
echo "- Open any benchmark result files in benchmarks/results/"
echo "- Or run a quick benchmark and screenshot the output"
echo ""
echo "Save to: docs/screenshots/benchmarks/comparison.png"
echo ""
echo "Press ENTER to continue..."
read

# Done!
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Screenshot capture complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Screenshots should be saved in: docs/screenshots/"
echo ""
echo "Next steps:"
echo "1. Review all screenshots for quality"
echo "2. Resize/crop if needed (recommended: 1920x1080 or 1200x800)"
echo "3. Run: ./scripts/update-docs-with-screenshots.sh"
echo ""

