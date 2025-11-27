#!/bin/bash
# Cron script to fetch POTUS schedule data
# Usage: Add to crontab, e.g.: 0 5 * * * /path/to/wheelhive/get_data.sh

cd "$(dirname "$0")"
source .venv/bin/activate
python src/ttracker.py
