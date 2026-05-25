#!/usr/bin/env bash
CRON_TAG="# freetour-tracker"
(crontab -l 2>/dev/null | grep -v "$CRON_TAG") | crontab -
echo "Freetour tracker cron job removed."
