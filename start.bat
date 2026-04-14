@echo off
echo ==============================================
echo student_copilot - Sovereign AI Tutor Boot Sequence
echo ==============================================

echo [1] Reminder: Ensure Redis is running locally (Port 6379) or remote REDIS_URL is configured.
echo.

echo [2] Booting Backend (Uvicorn) in background...
REM For development with auto-reload, use: start /B python main.py --reload
start /B python main.py

echo.
echo [3] Booting Frontend (Vite) in foreground...
cd frontend
npm run dev
cd ..
