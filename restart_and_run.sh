#!/bin/bash
# Restart MCP Server and Run Discord Bot
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

# Wait for service to start
sleep 2

# Check if service started successfully
if systemctl is-active --quiet mcp_server.service; then
    echo "  ✓ MCP server restarted successfully"
else
    echo "  ✗ ERROR: MCP server failed to start"
    echo ""
    sudo systemctl status mcp_server.service --no-pager
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
