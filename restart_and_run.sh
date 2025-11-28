#!/bin/bash
# Restart WheelHive Services (API + Discord Bot)
# Usage: ./restart_and_run.sh [--dev]
#   --dev   Run bot directly in foreground (for development)
#   (none)  Restart systemd services (for production)

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

DEV_MODE=false
if [ "$1" = "--dev" ]; then
    DEV_MODE=true
fi

echo "=========================================="
if [ "$DEV_MODE" = true ]; then
    echo "Starting WheelHive (Development Mode)"
else
    echo "Restarting WheelHive Services"
fi
echo "=========================================="
echo ""

# Step 1: Restart WheelHive API
echo "→ Restarting WheelHive API..."
sudo systemctl restart wheelhive-api.service

sleep 2

if systemctl is-active --quiet wheelhive-api.service; then
    echo "  ✓ WheelHive API restarted successfully"
else
    echo "  ✗ ERROR: WheelHive API failed to start"
    sudo systemctl status wheelhive-api.service --no-pager
    exit 1
fi

echo ""

if [ "$DEV_MODE" = true ]; then
    # Development: Stop service and run bot directly
    echo "→ Stopping WheelHive service (if running)..."
    sudo systemctl stop wheelhive.service 2>/dev/null || true
    echo "  ✓ Service stopped"
    echo ""
    echo "→ Starting Discord bot in foreground..."
    echo "  (Press Ctrl+C to stop)"
    echo ""
    echo "=========================================="
    echo ""

    # Activate virtual environment and run bot
    source .bot_venv/bin/activate
    python src/bot.py
else
    # Production: Restart systemd service
    echo "→ Restarting WheelHive Discord Bot..."
    sudo systemctl restart wheelhive.service

    sleep 2

    if systemctl is-active --quiet wheelhive.service; then
        echo "  ✓ WheelHive Discord Bot restarted successfully"
    else
        echo "  ✗ ERROR: WheelHive Discord Bot failed to start"
        sudo systemctl status wheelhive.service --no-pager
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "All services restarted successfully!"
    echo ""
    echo "View logs:"
    echo "  Bot: journalctl -u wheelhive -f"
    echo "  API: journalctl -u wheelhive-api -f"
    echo "=========================================="
fi
