# WheelHive MCP Server

This directory contains the MCP (Model Context Protocol) server implementation that provides API access to the options trading database.

## Overview

The MCP server exposes a FastAPI-based REST API that allows external applications (like Open WebUI or other AI assistants) to query and interact with the options trading data stored in `trades.db`.

## Features

- **17 Tools** for querying trades, shares, dividends, deposits, watchlists, and statistics
- **Account-based filtering** - Query data by specific accounts (e.g., "Joint", "Roth IRA")
- **Guild-based multi-tenancy** - Support for multiple Discord servers
- **Comprehensive statistics** - Monthly breakdowns, symbol analysis, portfolio overviews
- **RESTful API** - OpenAPI/Swagger documentation at `/docs`
- **CORS enabled** - Accessible from browser-based clients

## Running the Server

### Manual Start
```bash
# From project root directory
source .venv/bin/activate
python src/mcp/mcp_server.py
```

The server will start on `http://0.0.0.0:8000`

### Systemd Service Setup

The MCP server can run as a systemd service for automatic startup and monitoring.

#### Install the Service
```bash
# Set your project directory
export PROJECT_DIR=/path/to/wheelhive

# 1. Copy and edit the service file
sudo cp $PROJECT_DIR/src/mcp/mcp_server.service /etc/systemd/system/
sudo nano /etc/systemd/system/mcp_server.service  # Update paths

# 2. Reload systemd to recognize the new service
sudo systemctl daemon-reload

# 3. Enable the service to start on boot
sudo systemctl enable mcp_server

# 4. Start the service
sudo systemctl start mcp_server

# 5. Check the status
sudo systemctl status mcp_server
```

#### Service Management Commands
```bash
# Stop the service
sudo systemctl stop mcp_server

# Restart the service
sudo systemctl restart mcp_server

# Disable auto-start on boot
sudo systemctl disable mcp_server

# View recent logs
sudo journalctl -u mcp_server -n 100

# View logs in real-time
sudo journalctl -u mcp_server -f
```

## API Endpoints

### Core Endpoints
- `GET /` - Server information and capabilities
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger UI)

### MCP Protocol Endpoints
- `GET /tools/list` - List all available tools
- `POST /tools/call` - Execute a tool
- `GET /resources/list` - List all resources
- `POST /resources/read` - Read a resource
- `GET /prompts/list` - List all prompts
- `POST /prompts/get` - Get a prompt

### Direct Tool Endpoints (OpenAPI-compatible)
- `POST /tools/query_trades` - Query options trades
- `POST /tools/query_shares` - Query share transactions
- `POST /tools/query_dividends` - Query dividend payments
- `POST /tools/query_deposits` - Query deposits/withdrawals
- `POST /tools/query_watchlist` - Get watchlist symbols
- `POST /tools/add_to_watchlist` - Add symbol to watchlist
- `POST /tools/remove_from_watchlist` - Remove symbol from watchlist
- `POST /tools/get_user_statistics` - Get comprehensive trading statistics
- `POST /tools/get_symbol_statistics` - Get symbol-specific statistics
- `POST /tools/list_popular_symbols` - Get most traded symbols
- `POST /tools/get_portfolio_overview` - Get complete portfolio overview

## Available Tools

1. **query_trades** - Query options trades with filtering by symbol, date, account
2. **query_shares** - Query share buy/sell transactions
3. **query_dividends** - Query dividend payments
4. **query_deposits** - Query deposits and withdrawals
5. **query_watchlist** - Get user's watchlist symbols
6. **add_to_watchlist** - Add a symbol to watchlist
7. **remove_from_watchlist** - Remove a symbol from watchlist
8. **get_user_statistics** - Comprehensive monthly trading statistics
9. **get_symbol_statistics** - Symbol-specific aggregated data
10. **list_popular_symbols** - Most popular traded symbols
11. **get_portfolio_overview** - Complete portfolio with all transaction types
12. **compare_periods** - Compare two time periods
13. **compare_accounts** - Compare performance across accounts
14. **compare_symbols** - Compare performance across symbols
15. **calculate_roi** - Calculate return on investment
16. **list_user_accounts** - List all accounts for a user
17. **get_help** - Get help about available tools

## Configuration

- **Server Address**: `0.0.0.0:8000` (accessible from network)
- **Database**: `trades.db` (in project root)
- **Log File**: `mcp_server.log` (in project root)

## Security Features

The systemd service includes several security hardening measures:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Isolated /tmp directory
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=read-only` - Read-only home directories
- `ReadWritePaths` - Only project directory is writable

## Logging

Logs are written to:
1. **Application Log**: `mcp_server.log` in project root
2. **Systemd Journal**: View with `sudo journalctl -u mcp_server -f`

All HTTP requests are logged with:
- Method and path
- Query parameters
- Client IP address
- Response status code
- Request duration

## Integration with Open WebUI

To use with Open WebUI:
1. Configure Open WebUI to use the MCP server at `http://localhost:8000`
2. The server provides OpenAPI schema at `/docs` for automatic tool discovery
3. All endpoints support CORS for browser-based access

## Troubleshooting

### Service won't start
```bash
# Check service status and logs
sudo systemctl status mcp_server
sudo journalctl -u mcp_server -n 50

# Common issues:
# - Virtual environment not found: Check PATH in service file
# - Database locked: Close other connections to trades.db
# - Port 8000 in use: Change port in mcp_server.py
```

### Database errors
```bash
# Check database permissions
ls -la trades.db

# Ensure database exists and is readable
sqlite3 trades.db "SELECT COUNT(*) FROM trades;"
```

### View real-time logs
```bash
# Application logs
tail -f mcp_server.log

# Systemd logs
sudo journalctl -u mcp_server -f
```

## Development

To modify the MCP server:
1. Edit `src/mcp/mcp_server.py`
2. Restart the service: `sudo systemctl restart mcp_server`
3. View logs to verify: `sudo journalctl -u mcp_server -f`

For development with auto-reload:
```bash
# Run manually instead of as service
python src/mcp/mcp_server.py
# Server will auto-reload on file changes
```

## Files

- `mcp_server.py` - Main MCP server application
- `mcp_server.service` - Systemd service configuration (edit paths before use)
- `README.md` - This documentation file
