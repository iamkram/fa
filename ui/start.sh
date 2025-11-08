#!/bin/bash

# FA AI UI Startup Script

echo "🚀 Starting FA AI Assistant UI"
echo "================================"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
fi

# Check if backend is running
echo "🔍 Checking if backend server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend server is running"
else
    echo "⚠️  Warning: Backend server is not running on http://localhost:8000"
    echo "   Please start the backend server in another terminal:"
    echo "   cd src/interactive/api && python fastapi_server.py"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "🌐 Starting Next.js development server..."
echo "   UI will be available at: http://localhost:3000"
echo ""

npm run dev
