#!/bin/bash
# Start the Batch Scheduler for nightly 2 AM runs

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p logs

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "🌙 Starting FA AI System Batch Scheduler"
echo "📅 Schedule: Daily at 2:00 AM local time"
echo "📁 Project root: $PROJECT_ROOT"
echo "📝 Logs: $PROJECT_ROOT/logs/batch_scheduler.log"
echo ""

# Run the scheduler
PYTHONPATH=$PROJECT_ROOT python3 src/batch/scheduler/batch_scheduler.py
