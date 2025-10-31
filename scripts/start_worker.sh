#!/bin/bash
# Start the Batch Worker

echo "=================================="
echo "Starting Batch Worker"
echo "=================================="

# Activate virtual environment
source venv/bin/activate

# Start worker
python -m core.batch_app.worker

