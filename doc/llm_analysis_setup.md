# LLM Analysis Setup Guide

This guide explains how to set up and use AI-powered portfolio analysis in the Options Bot.

## Architecture

The LLM analysis system connects to **two MCP servers** to provide comprehensive insights:

1. **Trading MCP Server (port 8000)**: Your trading database
   - Historical trades, positions, statistics
   - Portfolio performance, P&L data
   - Account and symbol analytics

2. **Yahoo Finance MCP Server (port 8001)**: Live market data
   - Real-time stock prices
   - Options chains with Greeks (Delta, Theta, IV)
   - Market news and analyst ratings
   - Historical price data

## Environment Configuration

Add these variables to your `.env` file:

```bash
# Required for Claude API (testing/development)
ANTHROPIC_API_KEY=sk-ant-...

# LLM Provider Selection
LLM_PROVIDER=claude           # Options: 'claude' or 'ollama'

# Claude Configuration
LLM_MODEL_CLAUDE=claude-3-5-sonnet-20241022

# Ollama Configuration (for production)
LLM_MODEL_OLLAMA=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

## Installation

1. **Install dependencies:**
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Ensure MCP servers are running:**

   **Trading MCP (port 8000):**
   ```bash
   cd /path/to/wheelhive
   source .venv/bin/activate
   python src/mcp/mcp_server.py
   ```

   **Yahoo Finance MCP (port 8001):**
   ```bash
   # Already running as systemd service
   systemctl status yahoo-finance-mcp  # Check status
   ```

3. **Verify MCP servers are accessible:**
   ```bash
   curl http://localhost:8000/
   curl http://localhost:8001/
   ```

## Usage

### Discord Bot (DM Commands)

Send a Direct Message to the bot with these commands:

- **`!help`** - Show available commands
- **`!analyze`** - Comprehensive portfolio review
- **`!opportunities`** - Find trading opportunities based on open positions
- **`!ask <question>`** - Ask any custom question about your portfolio

**Examples:**
```
!analyze
!opportunities
!ask What are my best performing symbols this month?
!ask Should I roll my MSTU puts?
```

### Command Line Interface

Use the same functionality from the command line:

```bash
source .venv/bin/activate

# Comprehensive portfolio analysis
python src/cmds.py analyze --username sangelovich

# Find trading opportunities
python src/cmds.py opportunities --username sangelovich

# Ask custom questions
python src/cmds.py ask --username sangelovich --question "What are my riskiest positions?"
```

## What the LLM Can Do

The AI agent can:

✅ **Query your trading database** - Historical trades, performance, statistics
✅ **Fetch live market data** - Current prices, options chains, Greeks
✅ **Analyze positions** - Compare entry prices vs current market
✅ **Find opportunities** - Suggest rolls, closures, new trades
✅ **Calculate risk** - Assess portfolio concentration and exposure
✅ **Answer questions** - Any query about your trading activity

## Example Analysis Flow

When you run `!opportunities`, the LLM:

1. Calls `trading_get_current_positions` to see your open trades
2. For each position (e.g., MSTU 8P expiring 11/15):
   - Calls `yfinance_get_stock_info` to get current MSTU price
   - Calls `yfinance_get_option_expiration_dates` to find available dates
   - Calls `yfinance_get_option_chain` to get Greeks and market prices
3. Compares your entry premium vs current market
4. Recommends specific actions with strikes and expirations

**Sample Output:**
```
Based on your current positions, here are my recommendations:

1. MSTU 8P (11/15 expiration) - 2 contracts
   • Entry premium: $0.16/share ($32 total)
   • Current market: $0.08/share
   • Current stock price: $12.45
   • Delta: -0.15, Days to expiration: 3

   RECOMMENDATION: Let expire worthless for full profit
   RATIONALE: Stock well above strike, theta decay working in your favor

2. TSLL 10.5P (11/22 expiration) - 10 contracts
   • Entry premium: $0.11/share ($110 total)
   • Current market: $0.25/share
   • Current stock price: $9.80
   • Delta: -0.45, Days to expiration: 10

   RECOMMENDATION: Consider rolling to 12/20 9P @ $0.15 credit
   RATIONALE: Stock approaching strike, roll down and out to collect more premium
```

## Switching to Ollama (Production)

To use a completely private local LLM:

1. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Download a model:**
   ```bash
   ollama pull llama3.2
   ```

3. **Update `.env`:**
   ```bash
   LLM_PROVIDER=ollama
   ```

4. **Test:**
   ```bash
   python src/cmds.py analyze --username sangelovich
   ```

**Note:** Ollama doesn't support tool calling natively like Claude does, so the analysis quality may be lower. The system will fetch portfolio data upfront and include it in the prompt.

## Troubleshooting

### "Error: Unable to connect to MCP server"
- Check if MCP servers are running:
  ```bash
  curl http://localhost:8000/
  curl http://localhost:8001/
  ```
- Restart services if needed

### "Error: ANTHROPIC_API_KEY not set"
- Add your API key to `.env`
- Get a key from: https://console.anthropic.com/

### "Analysis incomplete: reached maximum iterations"
- Try asking a more specific question
- Break complex queries into smaller parts

### Discord "Message too long" error
- The bot automatically splits long responses
- Try narrowing your query (e.g., filter by symbol)

## Cost Considerations

**Claude API:**
- Sonnet 4.5: ~$3 per million input tokens, $15 per million output tokens
- Typical analysis: 10K-50K tokens (~$0.10-$0.50 per query)
- Good for development and testing

**Ollama:**
- Completely free
- Runs locally on your hardware
- No API calls, fully private
- Recommended for production use

## Security Notes

- Never commit `.env` file to git
- API keys are sensitive - treat like passwords
- MCP servers should only be accessible locally (localhost)
- Consider using Ollama for production to avoid external API calls
