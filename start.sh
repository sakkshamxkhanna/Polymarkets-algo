#!/usr/bin/env bash
# PolyTrader dev startup — runs backend (FastAPI) + frontend (Next.js) together.
#
# Usage:  ./start.sh
# Logs:   ./logs/backend.log, ./logs/frontend.log
# Stop:   Ctrl+C (cleans up both processes)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

# Make `node` discoverable (Homebrew on Apple Silicon)
export PATH="/opt/homebrew/bin:$PATH"

BACKEND_PORT=8000
FRONTEND_PORT=3000

# ── Pre-flight: check the venv and node_modules exist ──────────────────────────
if [[ ! -x "$BACKEND/venv/bin/python3" ]]; then
  echo "✗ Backend venv missing. Create it with: python3 -m venv $BACKEND/venv"
  exit 1
fi
if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "✗ Frontend node_modules missing. Run: cd $FRONTEND && npm install"
  exit 1
fi

# ── Port-conflict handling ─────────────────────────────────────────────────────
# TODO: implement handle_port_conflict() — see request below.
handle_port_conflict() {
  local port=$1
  local label=$2
  local pid
  pid=$(lsof -ti:"$port" 2>/dev/null || true)
  if [[ -n "$pid" ]]; then
    local cmd
    cmd=$(ps -p "$pid" -o comm= 2>/dev/null || echo "?")
    echo "✗ Port $port ($label) in use by PID $pid ($cmd)"
    echo "  Run: kill $pid    # then re-run ./start.sh"
    exit 1
  fi
}

handle_port_conflict "$BACKEND_PORT" "backend"
handle_port_conflict "$FRONTEND_PORT" "frontend"

# ── Start backend ──────────────────────────────────────────────────────────────
echo "→ Starting backend on :$BACKEND_PORT"
(
  cd "$BACKEND"
  exec ./venv/bin/python3 main.py
) >"$LOGS/backend.log" 2>&1 &
BACKEND_PID=$!

# ── Start frontend ─────────────────────────────────────────────────────────────
echo "→ Starting frontend on :$FRONTEND_PORT"
(
  cd "$FRONTEND"
  exec npm run dev
) >"$LOGS/frontend.log" 2>&1 &
FRONTEND_PID=$!

# ── Cleanup on exit ────────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "⏻ Shutting down (backend=$BACKEND_PID, frontend=$FRONTEND_PID)"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo ""
echo "✓ Both services running."
echo "  backend  → http://localhost:$BACKEND_PORT  (logs: logs/backend.log)"
echo "  frontend → http://localhost:$FRONTEND_PORT (logs: logs/frontend.log)"
echo ""
echo "Tailing combined logs (Ctrl+C to stop everything)..."
echo "────────────────────────────────────────────────────────"

tail -f "$LOGS/backend.log" "$LOGS/frontend.log"
