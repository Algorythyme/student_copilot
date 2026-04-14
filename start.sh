#!/bin/bash
echo "=============================================="
echo "🛡️ student_copilot - Sovereign AI Tutor Startup"
echo "=============================================="

echo "[1] Checking for Redis..."
echo "Reminder: Please ensure Redis is running remotely or locally."
echo ""

# Start Backend in background
echo "[2] Starting Backend (uvicorn via root main.py)..."
if [ -d "venv" ]; then
    # Activate script for either windows-like git bash or linux
    source venv/Scripts/activate 2>/dev/null || source venv/bin/activate
fi
python main.py &
BACKEND_PID=$!

# Start Frontend in background
echo "[3] Starting Frontend (React/Vite)..."
cd frontend || exit
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=============================================="
echo "✅ Both services are booting up in the background."
echo "🌐 Backend API: http://localhost:8000"
echo "🌐 Frontend UI: http://localhost:5173"
echo "=============================================="
echo "Press Ctrl+C to shut down both services."

# Trap Ctrl+C to kill the background processes cleanly
trap "echo 'Shutting down services...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT

wait
