#!/bin/bash

# FA AI System - Interactive Server Launcher
# Starts the FastAPI server for Phase 3 interactive queries

set -e

echo "🚀 Starting FA AI Interactive Server..."
echo ""

# Check if in correct directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

# Check if Docker services are running
echo "📦 Checking Docker services..."
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Docker services not running. Starting..."
    docker-compose up -d
    echo "✅ Docker services started"
    sleep 3
else
    echo "✅ Docker services running"
fi

# Check database connection
echo "🗄️  Checking database..."
python3 -c "from src.shared.database.connection import db_manager; db_manager.get_session().__enter__()" 2>/dev/null && echo "✅ Database connected" || echo "⚠️  Database connection issue"

# Check Redis connection
echo "📮 Checking Redis..."
python3 -c "from src.shared.utils.redis_client import redis_session_manager; redis_session_manager.client.ping()" 2>/dev/null && echo "✅ Redis connected" || echo "⚠️  Redis connection issue"

echo ""
echo "================================================"
echo "🤖 FA AI Interactive Server Starting..."
echo "================================================"
echo ""
echo "API Endpoints:"
echo "  - REST API:    http://localhost:8000/query"
echo "  - WebSocket:   ws://localhost:8000/ws/{session_id}"
echo "  - Health:      http://localhost:8000/health"
echo "  - Docs:        http://localhost:8000/docs"
echo ""
echo "Test UI:"
echo "  Open: ui/test-interface/index.html"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Load environment variables from .env
set -a
source .env
set +a

# Set PYTHONPATH and start the server
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
cd "$(pwd)"
python3 -m uvicorn src.interactive.api.fastapi_server:app --host 0.0.0.0 --port 8000
