#!/bin/bash
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  🛑 Stopping AI Chat                 ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Kill backend server (uvicorn)
PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$PID" ]; then
  kill $PID 2>/dev/null
  echo "  ✅ Server (PID $PID) dimatikan"
else
  echo "  ℹ️  Server tidak berjalan"
fi

# Stop Docker services if running
if command -v docker &>/dev/null; then
  COMPOSE_FILE="/home/bhebz/Projects/asisten ai memory/ai-chat-memory/docker-compose.yml"
  if [ -f "$COMPOSE_FILE" ]; then
    docker compose -f "$COMPOSE_FILE" down 2>/dev/null && echo "  ✅ Docker services dimatikan" || true
  fi
fi

echo ""
echo "  Selesai."
echo ""
