#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

source venv/bin/activate || { echo "Error: venv not found"; exit 1; }
export PYTHONPATH="$DIR"

kill $(lsof -ti:8000) 2>/dev/null
sleep 1

python scripts/migrate_db.py 2>/dev/null

setsid python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/aichat.log 2>&1 &

sleep 2

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  🧠 AI Chat with Memory              ║"
echo "  ╠══════════════════════════════════════╣"
printf "  ║  Buka: \e]8;;http://localhost:8000/static/index.html\e\\http://localhost:8000/static/index.html\e]8;;\e\\  ║\n"
echo "  ║                                      ║"
printf "  ║  Atau: \e]8;;http://localhost:8000\e\\http://localhost:8000\e]8;;\e\\                    ║\n"
echo "  ║                                      ║"
echo "  ║  Log:  tail -f /tmp/aichat.log       ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

(sensible-browser "http://localhost:8000/static/index.html" 2>/dev/null || \
 xdg-open "http://localhost:8000/static/index.html" 2>/dev/null || \
 python -m webbrowser "http://localhost:8000/static/index.html" 2>/dev/null) &
