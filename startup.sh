#!/bin/bash

echo "=== STARTUP SCRIPT ==="
echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la
echo "Content of main.py:"
cat main.py | head -20
echo "..."

echo "Trying to start main application..."
uvicorn main:app --host 0.0.0.0 --port $PORT || {
    echo "Failed to start main application. Trying debug version..."
    uvicorn debug_main:app --host 0.0.0.0 --port $PORT
} 