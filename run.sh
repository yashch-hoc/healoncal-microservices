#!/bin/bash

# Healoncal Run Script
# This script runs the application

echo "🚀 Starting Healoncal Application..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "⚠️  Please update .env file with your credentials before running"
fi

# Run the application
echo "🌐 Starting server on http://0.0.0.0:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo ""
uvicorn app.main_healoncal:app --reload --host 0.0.0.0 --port 8000

