# MCP Server Reference Guide

**Options Trading Bot - Model Context Protocol Server**

This document provides a comprehensive reference for all tools, resources, and capabilities exposed to Large Language Models (LLMs) via the MCP (Model Context Protocol) server.

**Server Location:** `mcp/mcp_server.py`
**Port:** 8000 (default)
**Protocol:** HTTP/JSON
**Total Tools:** 34

---

## Table of Contents

1. [Overview](#overview)
2. [Portfolio & Trading Data Tools](#portfolio--trading-data-tools)
3. [Market Data Tools](#market-data-tools)
4. [Technical Analysis Tools](#technical-analysis-tools)
5. [Community Knowledge Tools](#community-knowledge-tools)
6. [Options Analysis Tools](#options-analysis-tools)
7. [Statistics & Reporting Tools](#statistics--reporting-tools)
8. [Watchlist Management Tools](#watchlist-management-tools)
9. [Utility Tools](#utility-tools)
10. [Resources](#resources)
11. [Prompts](#prompts)

---

## Overview

The MCP server provides LLMs with comprehensive access to:
- **Trading Database**: User trades, positions, P/L, portfolio analytics
- **Live Market Data**: Real-time prices, options chains, fundamentals, news
- **Technical Analysis**: RSI, MACD, Bollinger Bands, support/resistance, patterns
- **Community Intelligence**: Harvested Discord messages, trending tickers, sentiment
- **Options Analytics**: Greeks, extrinsic value, probability of profit, scanning

All tools enforce **username-based security** - users can only access their own data.

---

## Portfolio & Trading Data Tools

### `query_trades`
**Description:** Query user's options trades with flexible filtering
**Parameters:**
- `username` (required): Discord username
- `symbol` (optional): Filter by ticker (e.g., 'AAPL')
- `start_date` (optional): ISO date (YYYY-MM-DD)
- `end_date` (optional): ISO date (YYYY-MM-DD)
- `account` (optional): Filter by account/broker

**Returns:** List of trades with details: date, operation (STO/BTC/BTO/STC), contracts, symbol, expiration, strike, premium, total

**Example Use Cases:**
- "Show me all my TSLL trades from last month"
- "What trades did I make in my Robinhood account?"
- "Find all my SPY trades that expired in October"

---

### `query_shares`
**Description:** Query user's stock buy/sell transactions
**Parameters:**
- `username` (required)
- `symbol` (optional)
- `start_date` (optional)
- `end_date` (optional)
- `account` (optional)

**Returns:** List of share transactions: date, operation (BUY/SELL), quantity, symbol, price, total

**Example Use Cases:**
- "Show all my HOOD stock purchases"
- "When did I buy shares this year?"

---

### `query_dividends`
**Description:** Query user's dividend payments
**Parameters:**
- `username` (required)
- `symbol` (optional)
- `start_date` (optional)
- `end_date` (optional)
- `account` (optional)

**Returns:** List of dividends: date, symbol, amount

**Example Use Cases:**
- "How much did I earn in dividends this year?"
- "Show QQQI dividend payments"

---

### `query_deposits`
**Description:** Query user's deposits and withdrawals
**Parameters:**
- `username` (required)
- `start_date` (optional)
- `end_date` (optional)
- `account` (optional)

**Returns:** List of deposits/withdrawals: date, amount, type

**Example Use Cases:**
- "What's my total capital invested?"
- "Show all withdrawals this quarter"

---

### `get_current_positions`
**Description:** Get user's current open positions (unsettled trades)
**Parameters:**
- `username` (required)

**Returns:** List of open positions with:
- Symbol, strike, expiration, contracts
- Entry date, cost basis
- Current market value, P/L, P/L %
- Days held, days to expiration

**Example Use Cases:**
- "What positions do I currently have open?"
- "Show my MSTU positions"
- **Critical:** Always call this FIRST when analyzing portfolio or finding opportunities

---

### `get_portfolio_overview`
**Description:** Comprehensive portfolio summary
**Parameters:**
- `username` (required)

**Returns:**
- Total capital (deposits - withdrawals)
- Account value (realized + unrealized P/L)
- Total trades count
- Win rate
- Average P/L per trade
- Breakdown by symbol, account

**Example Use Cases:**
- "How is my portfolio doing overall?"
- "What's my win rate?"

---

### `get_user_statistics`
**Description:** Detailed trading statistics for a user
**Parameters:**
- `username` (required)

**Returns:**
- Trade counts by operation (STO/BTC/BTO/STC)
- Total premium collected vs. paid
- Realized and unrealized P/L
- Win/loss statistics
- Average trade metrics

**Example Use Cases:**
- "Analyze my trading performance"
- "How much premium have I collected?"

---

## Market Data Tools

### `get_historical_stock_prices`
**Description:** Get OHLCV historical price data
**Parameters:**
- `ticker` (required): Stock symbol
- `period` (optional): 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max (default: 1mo)
- `interval` (optional): 1m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo (default: 1d)

**Returns:** DataFrame with Open, High, Low, Close, Volume

**Example Use Cases:**
- "Get 6 months of daily prices for AAPL"
- "Show SPY intraday 5-minute data"

---

### `get_stock_actions`
**Description:** Get dividend and stock split history
**Parameters:**
- `ticker` (required)

**Returns:** Dividends, stock splits with dates and amounts

**Example Use Cases:**
- "When does JEPI pay dividends?"
- "Show TSLA stock split history"

---

### `get_financial_statement`
**Description:** Get financial statements (income, balance, cash flow)
**Parameters:**
- `ticker` (required)
- `statement_type` (optional): 'income', 'balance', 'cash' (default: income)
- `period` (optional): 'annual', 'quarterly' (default: annual)

**Returns:** Financial statement data with line items

**Example Use Cases:**
- "Show AAPL's latest income statement"
- "Get quarterly balance sheet for MSFT"

---

### `get_holder_info`
**Description:** Get institutional holders, mutual funds, insider transactions
**Parameters:**
- `ticker` (required)
- `holder_type` (optional): 'institutional', 'mutualfund', 'major', 'insider' (default: institutional)

**Returns:** Holder information and ownership percentages

**Example Use Cases:**
- "Who are the major institutional holders of NVDA?"
- "Show recent insider transactions for AAPL"

---

### `get_analyst_recommendations`
**Description:** Get analyst buy/sell/hold recommendations
**Parameters:**
- `ticker` (required)

**Returns:** Analyst ratings, price targets, upgrades/downgrades

**Example Use Cases:**
- "What do analysts say about TSLA?"
- "Show recommendation changes for HOOD"

---

### `get_market_sentiment`
**Description:** Get overall market sentiment indicators
**Parameters:** None

**Returns:**
- VIX (volatility index)
- Fear & Greed Index (0-100, custom VIX-based calculation)
- Crypto Fear & Greed Index
- Treasury yields (10Y, 2Y)
- Yield curve analysis

**Example Use Cases:**
- "What's the current market sentiment?"
- "Is VIX elevated?"
- "Should I be more defensive given current conditions?"

---

## Technical Analysis Tools

### `get_technical_analysis`
**Description:** Comprehensive technical analysis with 15+ indicators
**Parameters:**
- `ticker` (required)
- `period` (optional): 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y (default: 3mo)
- `interval` (optional): 1m, 5m, 15m, 30m, 60m, 1d, 1wk (default: 1d)
- `include_patterns` (optional): Boolean, detect chart patterns (default: true)

**Returns:**
- **Current Price:** Price, change, change %
- **Momentum Indicators:**
  - RSI (14) - overbought/oversold (0-100)
  - MACD - trend momentum with signal line
- **Trend Indicators:**
  - SMA (20, 50, 200) - moving averages
  - EMA (12) - exponential moving average
  - SMA Alignment - bullish/bearish/mixed
- **Volatility Indicators:**
  - Bollinger Bands (upper, middle, lower)
  - ATR (14) - average true range
- **Volume Analysis:**
  - Volume ratio (vs. 20-day average)
  - Unusual volume detection
- **Support/Resistance Levels:**
  - 3 key support levels
  - 3 key resistance levels
- **Chart Patterns:**
  - Double top (bearish reversal)
  - Double bottom (bullish reversal)
- **Interpretation:** Human-readable summary formatted for LLM consumption

**Example Use Cases:**
- "Analyze AAPL technically - is it overbought?"
- "Show me support and resistance for SPY"
- "Is TSLL forming a double bottom?"

---

### `get_technical_summary`
**Description:** Fast trading signals (optimized for speed, no patterns)
**Parameters:**
- `ticker` (required)

**Returns:**
- Overall signal: BULLISH / BEARISH / NEUTRAL
- Bullish signal count
- Bearish signal count
- Key signals list (RSI zone, MACD cross, SMA alignment, BB position)
- Current price info

**Example Use Cases:**
- "Quick check - is MSTU bullish or bearish right now?"
- "Scan my watchlist for bullish setups" (call for each ticker)

---

## Community Knowledge Tools

### `get_community_messages`
**Description:** Query harvested Discord messages (community discussions)
**Parameters:**
- `ticker` (optional): Filter by ticker mentions
- `channel` (optional): Filter by Discord channel
- `limit` (optional): Max messages to return (default: 50)
- `start_date` (optional): Messages after this date
- `end_date` (optional): Messages before this date

**Returns:** List of messages with:
- Username, channel
- Timestamp
- Content
- Tickers mentioned

**Example Use Cases:**
- "What is the community saying about MSTR?"
- "Show recent discussions in #trading channel"
- "Find messages mentioning both TSLL and leverage"

---

### `get_trending_tickers`
**Description:** Get most-discussed tickers in community
**Parameters:**
- `limit` (optional): Max tickers to return (default: 20)
- `days` (optional): Look back period (default: 7)

**Returns:** List of tickers with mention counts, sorted by popularity

**Example Use Cases:**
- "What tickers is the community buzzing about?"
- "Show top 10 trending symbols this week"
- **Critical:** Use this to discover what others are trading

---

### `get_community_channels`
**Description:** List available Discord channels in database
**Parameters:** None

**Returns:** List of channels with message counts

**Example Use Cases:**
- "Which channels are available?"
- "Where are most discussions happening?"

---

## Options Analysis Tools

### `scan_options_chain`
**Description:** Scan options chains for trade candidates
**Parameters:**
- `symbols` (required): List of tickers to scan
- `days_to_expiration_min` (optional): Minimum DTE (default: 0)
- `days_to_expiration_max` (optional): Maximum DTE (default: 45)
- `delta_min` (optional): Minimum delta (default: 0.15)
- `delta_max` (optional): Maximum delta (default: 0.35)
- `min_bid` (optional): Minimum bid price (default: 0.10)

**Returns:** List of option contracts matching criteria with:
- Symbol, strike, expiration, type (call/put)
- Bid, ask, last price
- Greeks: delta, gamma, theta, vega
- Implied volatility
- Open interest, volume

**Example Use Cases:**
- "Scan MSTU for weekly puts with 0.20-0.30 delta"
- "Find high-premium options expiring in 30-45 days"
- "Show me all TSLL options with >$0.50 premium"

---

### `get_detailed_option_chain`
**Description:** Get full options chain for a specific expiration
**Parameters:**
- `ticker` (required)
- `expiration_date` (required): ISO date (YYYY-MM-DD)
- `option_type` (optional): 'calls', 'puts', or 'both' (default: both)

**Returns:** Complete chain with all strikes and Greeks

**Example Use Cases:**
- "Show all HOOD options expiring Nov 14"
- "Get the full chain for SPY weekly expiration"

---

### `get_option_expiration_dates`
**Description:** Get available expiration dates for a ticker
**Parameters:**
- `ticker` (required)

**Returns:** List of expiration dates

**Example Use Cases:**
- "When do AAPL options expire?"
- "Show next 5 expirations for TSLA"

---

### `calculate_extrinsic_value`
**Description:** Calculate extrinsic (time) value for options
**Parameters:**
- `ticker` (required)
- `strikes` (required): Single strike or range (e.g., "33-44")

**Returns:** Intrinsic value, extrinsic value, total premium for each strike

**Example Use Cases:**
- "How much extrinsic value in COIN $33 calls?"
- "Compare extrinsic value across $120-130 strikes for HOOD"

---

### `calculate_probability_of_profit`
**Description:** Calculate POP (probability of profit) for options strategies
**Parameters:**
- `strategy` (required): 'short_put', 'short_call', 'iron_condor', 'vertical_spread'
- `ticker` (required)
- `strike` or other strategy-specific params

**Returns:** Probability of profit percentage based on current IV and price

**Example Use Cases:**
- "What's the POP of selling TSLL $10 put?"
- "Calculate POP for MSTU iron condor 12/14/16/18"

---

### `calculate_roi`
**Description:** Calculate ROI for options trades
**Parameters:**
- `premium` (required): Premium per contract
- `strike` (required): Strike price
- `contracts` (optional): Number of contracts (default: 1)

**Returns:** ROI percentage, capital required, max profit

**Example Use Cases:**
- "What ROI would I get selling $0.50 premium on $100 strike?"

---

## Statistics & Reporting Tools

### `get_symbol_statistics`
**Description:** Statistics for a specific symbol across all users
**Parameters:**
- `symbol` (required)

**Returns:**
- Total trades on this symbol
- Total premium collected/paid
- Win rate
- Average P/L
- Most active users

**Example Use Cases:**
- "How has the community done trading MSTR?"
- "Show stats for TSLL"

---

### `compare_symbols`
**Description:** Compare performance across multiple symbols
**Parameters:**
- `username` (required)
- `symbols` (optional): List of symbols to compare

**Returns:** Side-by-side comparison of P/L, trade count, win rate per symbol

**Example Use Cases:**
- "Compare my MSTU vs TSLL performance"
- "Which symbol has been most profitable for me?"

---

### `compare_accounts`
**Description:** Compare performance across brokerage accounts
**Parameters:**
- `username` (required)

**Returns:** Performance breakdown by account (Robinhood, Fidelity, Schwab, IBKR)

**Example Use Cases:**
- "How does my Robinhood account compare to Fidelity?"
- "Which broker am I doing better with?"

---

### `compare_periods`
**Description:** Compare performance across time periods
**Parameters:**
- `username` (required)
- `period1_start`, `period1_end`
- `period2_start`, `period2_end`

**Returns:** Comparison of P/L, trade count, win rate between periods

**Example Use Cases:**
- "Compare Q3 vs Q4 performance"
- "How am I doing this month vs last month?"

---

### `list_user_accounts`
**Description:** List all accounts/brokers a user has traded through
**Parameters:**
- `username` (required)

**Returns:** List of account names with trade counts

**Example Use Cases:**
- "Which accounts do I use?"

---

### `list_popular_symbols`
**Description:** Get most traded symbols (community-wide)
**Parameters:**
- `limit` (optional): Max symbols (default: 20)

**Returns:** Symbols ranked by trade count

**Example Use Cases:**
- "What are the most popular tickers?"
- "Show top 10 traded symbols"

---

## Watchlist Management Tools

### `query_watchlist`
**Description:** Get user's watchlist
**Parameters:**
- `username` (required)

**Returns:** List of symbols in watchlist with notes

**Example Use Cases:**
- "Show my watchlist"
- "What am I watching?"

---

### `add_to_watchlist`
**Description:** Add symbol to watchlist
**Parameters:**
- `username` (required)
- `symbol` (required)
- `notes` (optional): Free text notes

**Returns:** Success confirmation

**Example Use Cases:**
- "Add HOOD to my watchlist with note 'wait for pullback'"

---

### `remove_from_watchlist`
**Description:** Remove symbol from watchlist
**Parameters:**
- `username` (required)
- `symbol` (required)

**Returns:** Success confirmation

---

## Utility Tools

### `get_help`
**Description:** Get help information about available tools
**Parameters:** None

**Returns:** List of all tools with brief descriptions

---

## Resources

### `trades://schema`
**Description:** Database schema information for all tables
**URI:** trades://schema
**Returns:** Table definitions, column types, indexes

---

### `trades://users`
**Description:** List of all users in the system
**URI:** trades://users
**Returns:** All registered usernames

---

## Prompts

### `analyze_trading_performance`
**Description:** Generate a prompt for analyzing user's trading performance
**Arguments:**
- `username` (required)
- `time_period` (optional): e.g., "last month", "this year"

---

### `watchlist_analysis`
**Description:** Generate prompt for analyzing watchlist symbols
**Arguments:**
- `username` (required)

---

### `portfolio_overview`
**Description:** Generate comprehensive portfolio overview prompt
**Arguments:**
- `username` (required)

---

## LLM Analysis Workflow

### Recommended Tool Call Sequence

#### Portfolio Review
```
1. get_current_positions(username) - ALWAYS FIRST
2. get_market_sentiment() - Overall market context
3. For each position:
   - get_technical_analysis(ticker)
   - get_community_messages(ticker)
4. Provide recommendations
```

#### Find Trading Opportunities
```
1. get_current_positions(username) - See what user already has
2. get_trending_tickers() - What's popular
3. query_watchlist(username) - User's watchlist
4. For promising tickers:
   - get_technical_summary(ticker) - Fast bullish/bearish check
   - scan_options_chain([ticker]) - Find specific trades
5. get_technical_analysis(ticker) - Deep dive on best candidates
```

#### Community Sentiment Analysis
```
1. get_trending_tickers(limit=10)
2. get_community_messages(ticker=<ticker>, limit=50)
3. Analyze sentiment patterns
4. Cross-reference with user's positions
```

---

## Security & Data Access Rules

### Username Enforcement
- All `trading_*` tools require a `username` parameter
- LLM MUST use the authenticated user's username
- Attempting to access other users' data will be blocked

### Data Privacy
- Users can ONLY access their own:
  - Trades, positions, dividends, deposits
  - Statistics, P/L, account balances
  - Watchlists
- Market data and community messages are shared

---

## Technical Details

### Server Endpoint
```
Base URL: http://localhost:8000
Tools endpoint: /tools/list
Execute endpoint: /tools/call
```

### Response Format
```json
{
  "content": [
    {
      "type": "text",
      "text": "Human-readable result",
      "data": { "structured": "data" }
    }
  ],
  "isError": false
}
```

### Error Handling
- Tools return `isError: true` on failure
- Error messages are descriptive
- Missing data returns empty results, not errors

---

## Performance Characteristics

### Fast Tools (< 1 second)
- `get_current_positions`
- `query_trades`, `query_shares`, `query_dividends`
- `get_technical_summary`
- `get_community_messages`

### Moderate Tools (1-3 seconds)
- `get_technical_analysis` (without patterns)
- `get_market_sentiment`
- `scan_options_chain` (single symbol)

### Slow Tools (3-10 seconds)
- `get_technical_analysis` (with patterns)
- `scan_options_chain` (multiple symbols)
- `get_detailed_option_chain` (large chains)

### Recommendation
Use `get_technical_summary` for scanning multiple tickers, then `get_technical_analysis` for deep dives on promising candidates.

---

## Version History

- **v1.0.0** (2025-10-21): Added Technical Analysis tools (`get_technical_analysis`, `get_technical_summary`)
- **v0.9.0** (2025-10-20): Added Community Knowledge tools
- **v0.8.0** (2025-10-19): Initial MCP server implementation

---

## Support & Documentation

- **Main Documentation:** `/doc/options_bot.md`
- **Database Schema:** `/doc/database_schema.md`
- **Community Knowledge:** `/doc/community_knowledge_integration.md`
- **Technical Analysis:** Code in `src/ta_service.py`, `src/technical_analysis.py`
- **MCP Server Code:** `mcp/mcp_server.py`

---

**Last Updated:** 2025-10-21
