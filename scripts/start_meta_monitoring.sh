#!/bin/bash
#
# Start the meta-monitoring dashboard and API server
#

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Set Python path
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Start the server
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Meta-Monitoring Dashboard Server"
echo "=========================================="
echo "Dashboard: http://localhost:8001/dashboard/"
echo "API Docs:  http://localhost:8001/docs"
echo "Health:    http://localhost:8001/api/meta-monitoring/health"
echo "=========================================="

uvicorn src.meta_monitoring.app:app --host 0.0.0.0 --port 8001 --reload
