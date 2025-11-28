# WheelHive API

REST API server providing access to the options trading database via the Model Context Protocol (MCP).

## Overview

The WheelHive API exposes a FastAPI-based REST API that allows external applications (like Open WebUI or other AI assistants) to query and interact with the options trading data stored in `trades.db`.

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
python src/mcp/wheelhive_api.py
```

The server will start on `http://0.0.0.0:8000`

### Systemd Service Setup

#### Install the Service
```bash
# 1. Copy the service file
sudo cp src/mcp/wheelhive-api.service /etc/systemd/system/

# 2. Edit paths if needed
sudo nano /etc/systemd/system/wheelhive-api.service

# 3. Reload systemd
sudo systemctl daemon-reload

# 4. Enable and start
sudo systemctl enable wheelhive-api
sudo systemctl start wheelhive-api

# 5. Check status
sudo systemctl status wheelhive-api
```

#### Service Management
```bash
sudo systemctl stop wheelhive-api
sudo systemctl restart wheelhive-api
sudo systemctl disable wheelhive-api

# View logs
sudo journalctl -u wheelhive-api -f
sudo journalctl -u wheelhive-api -n 100
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

## Security Features

The systemd service includes security hardening:
- `NoNewPrivileges=true` - Prevents privilege escalation
- `PrivateTmp=true` - Isolated /tmp directory
- `ProtectSystem=strict` - Read-only system directories
- `ProtectHome=read-only` - Read-only home directories
- `ReadWritePaths` - Only project directory is writable

## Logging

View logs via systemd journal:
```bash
sudo journalctl -u wheelhive-api -f
```

## Integration with Open WebUI

1. Configure Open WebUI to use the API at `http://localhost:8000`
2. The server provides OpenAPI schema at `/docs` for automatic tool discovery
3. All endpoints support CORS for browser-based access

## Troubleshooting

### Service won't start
```bash
sudo systemctl status wheelhive-api
sudo journalctl -u wheelhive-api -n 50

# Common issues:
# - Virtual environment not found: Check PATH in service file
# - Database locked: Close other connections to trades.db
# - Port 8000 in use: Change port in wheelhive_api.py
```

### Database errors
```bash
ls -la trades.db
sqlite3 trades.db "SELECT COUNT(*) FROM trades;"
```

## Development

```bash
# Edit the API
vim src/mcp/wheelhive_api.py

# Restart service
sudo systemctl restart wheelhive-api

# Watch logs
sudo journalctl -u wheelhive-api -f
```

## Files

- `wheelhive_api.py` - Main API server application
- `wheelhive-api.service` - Systemd service configuration
- `README.md` - This documentation
