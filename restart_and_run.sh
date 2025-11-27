#!/bin/bash
#
# Restart MCP Server and Run Discord Bot
#
# This script restarts the MCP server systemctl service and then starts the Discord bot.
# Usage: ./restart_and_run.sh

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Restarting MCP Server and Running Bot"
echo "=========================================="
echo ""

# Step 1: Restart MCP server
echo "→ Restarting MCP server..."
sudo systemctl restart mcp_server.service

# Wait a moment for service to start
sleep 2

# Check if service started successfully
if systemctl is-active --quiet mcp_server.service; then
    echo "  ✓ MCP server restarted successfully"
else
    echo "  ✗ ERROR: MCP server failed to start"
    echo ""
    echo "Service status:"
    sudo systemctl status mcp_server.service --no-pager
    exit 1
fi

echo ""

# Step 2: Run the Discord bot
echo "→ Starting Discord bot..."
echo ""
echo "=========================================="
echo ""
# Remove the bot.log so we can monitor the latest
rm bot.log
# Activate virtual environment and run bot
source .bot_venv/bin/activate
python src/bot.py

# Note: The script will stay running while bot.py is running
# Press Ctrl+C to stop the bot
