#!/bin/bash
#
# Start Batch Monitoring Dashboard
# Runs on port 8001
#

echo "🚀 Starting Batch Monitoring Dashboard..."

# Set Python path
export PYTHONPATH=/Users/markkenyon/fa-ai-system

# Start the server
cd /Users/markkenyon/fa-ai-system

python3 -m uvicorn src.batch.dashboard.api:app \
    --host 0.0.0.0 \
    --port 8001 \
    --reload \
    --log-level info

echo "✅ Batch Monitoring Dashboard started on http://localhost:8001/batch-dashboard"
