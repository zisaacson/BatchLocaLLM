#!/bin/bash
# Start the Batch API Server

echo "=================================="
echo "Starting Batch API Server"
echo "=================================="

# Activate virtual environment
source venv/bin/activate

# Start FastAPI server
python -m uvicorn batch_app.api_server:app --host 0.0.0.0 --port 8080 --reload

