#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Freetour Tracker — Setup ==="

# Create virtual environment
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing Python dependencies…"
pip install --upgrade pip -q
pip install playwright matplotlib pandas -q

echo "Installing Playwright browsers…"
playwright install chromium

echo ""
echo "=== Setup complete ==="
echo ""
echo "To run the tracker manually:"
echo "  cd $SCRIPT_DIR && .venv/bin/python tracker.py"
echo ""
echo "To set up the daily 9am cron job:"
echo "  bash cron_setup.sh"
