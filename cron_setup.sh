#!/usr/bin/env bash
# Installs (or updates) a daily 10am cron job for the tracker.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"
TRACKER="$SCRIPT_DIR/tracker.py"
LOG="$SCRIPT_DIR/tracker.log"

CRON_LINE="0 10 * * * $PYTHON $TRACKER >> $LOG 2>&1"

# Write directly — avoids pipe-to-crontab issues on macOS
printf "%s\n" "$CRON_LINE" | crontab -

echo "Cron job installed:"
echo "  $CRON_LINE"
echo ""
echo "It will run every day at 10:00 AM."
echo "Output will be logged to: $LOG"
echo ""
echo "To remove it later, run:  bash cron_remove.sh"
