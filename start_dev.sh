#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK="$ROOT/backend"
FRONT="$ROOT/frontend"

# Start backend
cd "$BACK"
python -m venv .venv >/dev/null 2>&1 || true
source .venv/bin/activate
pip install -r requirements.txt -q
uvicorn app:app --reload --port 8000 &
BACK_PID=$!

# Start frontend
cd "$FRONT"
if command -v pnpm >/dev/null 2>&1; then
  pnpm install
  pnpm dev -- --host 0.0.0.0 &
else
  npm install
  npm run dev -- --host 0.0.0.0 &
fi
FRONT_PID=$!

echo "Backend PID=$BACK_PID"
echo "Frontend PID=$FRONT_PID"
echo "✅ Both running. Frontend: http://localhost:5173  Backend: http://localhost:8000"
wait
