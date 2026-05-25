#!/usr/bin/env bash
# Installs (or updates) a daily 9am cron job for the tracker.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"
TRACKER="$SCRIPT_DIR/tracker.py"
LOG="$SCRIPT_DIR/tracker.log"
CRON_TAG="# freetour-tracker"

CRON_LINE="0 9 * * * $PYTHON $TRACKER >> $LOG 2>&1 $CRON_TAG"

# Remove any old entry, then add the new one
(crontab -l 2>/dev/null | grep -v "$CRON_TAG"; echo "$CRON_LINE") | crontab -

echo "Cron job installed:"
echo "  $CRON_LINE"
echo ""
echo "It will run every day at 9:00 AM."
echo "Output will be logged to: $LOG"
echo ""
echo "To remove it later, run:  bash cron_remove.sh"
