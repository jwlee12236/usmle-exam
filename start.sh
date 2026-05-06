#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== USMLE Exam Practice ==="
echo ""

# Kill any leftover processes on our ports
lsof -ti:8002,5174 | xargs kill -9 2>/dev/null || true

# --- Backend ---
echo "[1/2] Starting backend (FastAPI on port 8002)..."
cd "$ROOT/backend"

if [ ! -d "venv" ]; then
  echo "  Creating Python virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

# Create static dirs
mkdir -p static/images uploads

uvicorn main:app --host 0.0.0.0 --port 8002 --reload &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# --- Frontend ---
echo "[2/2] Starting frontend (React on port 5174)..."
cd "$ROOT/frontend"

if [ ! -d "node_modules" ]; then
  echo "  Installing npm packages..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

echo ""
echo "✓ App running at: http://localhost:5174"
echo "  API docs:       http://localhost:8002/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
