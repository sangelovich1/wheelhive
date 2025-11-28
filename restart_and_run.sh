#!/bin/bash
# Restart WheelHive API and Run Discord Bot
# Usage: ./restart_and_run.sh

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Restarting WheelHive API and Running Bot"
echo "=========================================="
echo ""

# Step 1: Restart WheelHive API
echo "→ Restarting WheelHive API..."
sudo systemctl restart wheelhive-api.service

# Wait for service to start
sleep 2

# Check if service started successfully
if systemctl is-active --quiet wheelhive-api.service; then
    echo "  ✓ WheelHive API restarted successfully"
else
    echo "  ✗ ERROR: WheelHive API failed to start"
    echo ""
    sudo systemctl status wheelhive-api.service --no-pager
    exit 1
fi

echo ""

# Step 2: Run the Discord bot
echo "→ Starting Discord bot..."
echo ""
echo "=========================================="
echo ""

# Activate virtual environment and run bot
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

python src/bot.py

# Note: Script stays running while bot.py runs
# Press Ctrl+C to stop
