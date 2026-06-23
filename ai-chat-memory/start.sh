#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

source venv/bin/activate || { echo "Error: venv not found"; exit 1; }
export PYTHONPATH="$DIR"

kill $(lsof -ti:8000) 2>/dev/null
sleep 1

python scripts/migrate_db.py 2>/dev/null

setsid python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/aichat.log 2>&1 &

sleep 2

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║  🧠 AI Chat with Memory              ║"
echo "  ╠══════════════════════════════════════╣"
echo "  ║  http://localhost:8000                ║"
echo "  ║                                      ║"
echo "  ║  Fitur baru:                         ║"
echo "  ║  • Hapus percakapan (×)              ║"
echo "  ║  • Hapus pesan (hover → 🗑)          ║"
echo "  ║  • Export chat (📥)                  ║"
echo "  ║  • Cari percakapan (search)          ║"
echo "  ║  • Tombol stop (⏹)                   ║"
echo "  ║  • Tema gelap/terang (🌓)            ║"
echo "  ║  • Timestamp pesan                   ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

(sensible-browser "http://localhost:8000" 2>/dev/null || \
 xdg-open "http://localhost:8000" 2>/dev/null || \
 python -m webbrowser "http://localhost:8000" 2>/dev/null) &
