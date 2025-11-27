# LLM Test Queries for MCP Server
## Testing Portfolio Analysis and Market Data Integration

---

## 1. Basic Yahoo Finance Tools Testing

### Query 1.1: Get Options Expiration Dates
```
What are the available options expiration dates for TSLA? Show me at least the next 5-10 expiration dates.
```
**Tests:** `get_option_expiration_dates` tool

### Query 1.2: Get Dividend History
```
Show me the dividend history for AAPL over the last 2 years. Has the dividend been growing?
```
**Tests:** `get_stock_actions` tool with action_type="dividends"

### Query 1.3: Get Financial Statement
```
Get the annual income statement for NVDA. What was the revenue and net income for the most recent year?
```
**Tests:** `get_financial_statement` tool

### Query 1.4: Get Institutional Holders
```
Who are the top institutional holders of SPY? Show me the institutional ownership data.
```
**Tests:** `get_holder_info` tool with holder_type="institutional"

### Query 1.5: Get Analyst Recommendations
```
What are the current analyst recommendations for MSFT? Are analysts bullish or bearish?
```
**Tests:** `get_analyst_recommendations` tool

### Query 1.6: Get Historical Prices
```
Get the historical daily prices for GOOGL over the last month. What's the trend?
```
**Tests:** `get_historical_stock_prices` tool

### Query 1.7: Get Detailed Options Chain
```
Show me the detailed options chain for QQQ expiring on the next monthly expiration.
How many call and put contracts are available?
```
**Tests:** `get_detailed_option_chain` and `get_option_expiration_dates` tools

---

## 2. Portfolio Analysis Queries

### Query 2.1: My Current Positions
```
Show me all my current open positions. What tickers do I have exposure to and what's my
profit/loss on each position?
```
**Tests:** `get_current_positions` and `get_portfolio_overview` tools

### Query 2.2: Portfolio with Live Market Data
```
Get my current positions and look up the current market price for each ticker.
Calculate my unrealized P&L based on current prices.
```
**Tests:** Integration of `get_current_positions` + `get_stock_quote`

### Query 2.3: Trading Performance Analysis
```
Analyze my trading performance for the last 6 months. What's my win rate, average profit per trade,
and total P&L? Which symbols have been most profitable?
```
**Tests:** `get_user_statistics` and `get_symbol_statistics` tools

### Query 2.4: Compare Trading Periods
```
Compare my trading performance between Q1 2025 and Q2 2025. Has my performance improved?
```
**Tests:** `compare_periods` tool

### Query 2.5: Account Comparison
```
I have multiple accounts. Compare the performance across all my accounts. Which account
has the best returns?
```
**Tests:** `compare_accounts` tool

---

## 3. Advanced Portfolio Analysis with Fundamental Data

### Query 3.1: Position Analysis with Dividends
```
For all tickers in my current portfolio, check which ones pay dividends. Show me the
dividend yield and payment history for each dividend-paying position.
```
**Tests:** Integration of `get_current_positions` + `get_stock_actions` + `get_stock_info`

### Query 3.2: Portfolio Holdings Deep Dive
```
I want to analyze my top 3 positions by dollar amount. For each position:
1. Get current price and my average cost
2. Get institutional ownership
3. Get analyst recommendations
4. Get recent news
5. Calculate my unrealized P&L

Provide a comprehensive analysis.
```
**Tests:** Multiple tools: `get_current_positions`, `get_stock_quote`, `get_holder_info`,
`get_analyst_recommendations`, `get_market_news`

### Query 3.3: Financial Health Check
```
For my current stock positions (not options), get the annual income statement and balance
sheet. Are any of my holdings showing declining revenue or high debt?
```
**Tests:** `get_current_positions` + `get_financial_statement` integration

### Query 3.4: Earnings Analysis
```
Look at my current positions and get the quarterly income statements for each.
Which companies are showing strong revenue growth quarter-over-quarter?
```
**Tests:** `get_current_positions` + `get_financial_statement` with period="quarterly"

---

## 4. Options Strategy Analysis

### Query 4.1: Scan for New Opportunities
```
Scan the options chain for MSTU with expiration in 30-45 days. Find puts with delta
between 0.20 and 0.35. What premiums are available?
```
**Tests:** `scan_options_chain` tool

### Query 4.2: Extrinsic Value Analysis
```
I'm looking at selling puts on TSLL. Calculate the extrinsic value for the 10 strike
and 11 strike puts expiring in the next monthly expiration. Which has better time decay?
```
**Tests:** `calculate_extrinsic_value` and `get_option_expiration_dates` tools

### Query 4.3: Probability of Profit
```
Calculate the probability of profit for selling a put on AAPL at the 180 strike
expiring in 30 days. Current stock price is around 225.
```
**Tests:** `calculate_probability_of_profit` tool

### Query 4.4: Historical Volatility Context
```
Get the historical prices for NVDA over the last 3 months and calculate if recent
volatility is higher or lower than average. Then scan for options opportunities.
```
**Tests:** `get_historical_stock_prices` + `scan_options_chain` integration

---

## 5. Community Knowledge Integration

### Query 5.1: Community Sentiment
```
What tickers is the community talking about most this month? Show me the trending
tickers and how many mentions each has.
```
**Tests:** `get_trending_tickers` tool

### Query 5.2: Community Knowledge Search
```
Search the community messages for discussions about MSTU. What strategies are people using?
What price targets are mentioned?
```
**Tests:** `query_community_knowledge` or `get_community_messages` tool

### Query 5.3: Compare Community vs My Trades
```
What are the top 5 trending tickers in the community? Do I have any positions in these tickers?
If not, should I consider them based on community sentiment?
```
**Tests:** Integration of `get_trending_tickers` + `get_current_positions` + `get_stock_info`

---

## 6. Risk Analysis Queries

### Query 6.1: Concentration Risk
```
Analyze my portfolio concentration. What percentage of my total portfolio is in each ticker?
Do I have over-concentration in any single stock or sector?
```
**Tests:** `get_portfolio_overview` and `get_current_positions` tools

### Query 6.2: Position Greeks Analysis
```
For all my open options positions, get the current options chain data and calculate
total portfolio delta, theta, and gamma. Am I too directional or theta-positive?
```
**Tests:** `get_current_positions` + `get_detailed_option_chain` integration

### Query 6.3: Dividend Risk
```
For my stock positions, check the dividend history. Have any companies cut or suspended
dividends recently? This could signal financial trouble.
```
**Tests:** `get_current_positions` + `get_stock_actions` with action_type="dividends"

---

## 7. Comparison and Benchmarking

### Query 7.1: Compare to Market
```
Get historical prices for SPY over the last 6 months. Calculate SPY's return.
Then get my portfolio return for the same period. Am I beating the market?
```
**Tests:** `get_historical_stock_prices` + `get_user_statistics` + `calculate_roi`

### Query 7.2: Symbol Performance Comparison
```
I trade multiple tickers. Compare the statistics for TSLL, MSTU, and CONL. Which has given
me the best returns? Which has the highest win rate?
```
**Tests:** `get_symbol_statistics` and `compare_symbols` tools

### Query 7.3: Technical vs Fundamental
```
For AAPL, get:
1. RSI and moving averages (technical)
2. Institutional ownership (fundamental)
3. Analyst recommendations (fundamental)
4. My trading performance on this ticker

Is there alignment between technicals, fundamentals, and my results?
```
**Tests:** Multiple tools: `get_rsi`, `get_moving_averages`, `get_holder_info`,
`get_analyst_recommendations`, `get_symbol_statistics`

---

## 8. Watchlist and Research

### Query 8.1: Watchlist Analysis
```
Show me my watchlist. For each ticker on my watchlist:
1. Get current price
2. Get analyst recommendations
3. Check if options are available and liquid
4. Show community sentiment

Help me prioritize which to trade next.
```
**Tests:** `query_watchlist` + multiple integration tools

### Query 8.2: New Ticker Research
```
I'm considering adding GOOGL to my portfolio. Provide a comprehensive analysis:
1. Current price and 52-week range
2. Institutional ownership
3. Analyst recommendations
4. Recent financial performance (quarterly revenue growth)
5. Dividend history
6. Available options expiration dates and liquidity
7. Community mentions and sentiment

Should I add it to my watchlist?
```
**Tests:** Comprehensive integration of market data and fundamental tools

### Query 8.3: Sector Rotation
```
Get the top institutional holdings for QQQ (tech sector) and compare to my current
tech positions. Am I aligned with institutional money or contrarian?
```
**Tests:** `get_holder_info` + `get_current_positions` integration

---

## 9. Trade Planning Queries

### Query 9.1: Entry Point Analysis
```
I want to sell puts on TSLA. Get the historical prices for the last 2 weeks and identify
support levels. Then scan the options chain for puts at those strikes. What premiums
are available?
```
**Tests:** `get_historical_stock_prices` + `scan_options_chain` integration

### Query 9.2: Exit Strategy
```
I have an open position in MSTU. Get the current price, my entry price, and calculate
my unrealized P&L. Based on the stock's 50-day moving average and RSI, should I close
or hold?
```
**Tests:** `get_current_positions` + `get_stock_quote` + `get_moving_averages` + `get_rsi`

### Query 9.3: Roll Decision
```
I have puts expiring soon on TSLL. Get the expiration dates, current options chain for
this month and next month. Calculate the credit I could get from rolling to next month.
Is it worth rolling or should I let them expire?
```
**Tests:** `get_current_positions` + `get_option_expiration_dates` + `get_detailed_option_chain`

---

## 10. Portfolio Optimization

### Query 10.1: Rebalancing Analysis
```
Analyze my portfolio allocation. Compare my current holdings to their institutional
ownership levels. Should I increase or decrease any positions to better align with
smart money?
```
**Tests:** `get_current_positions` + `get_holder_info` integration

### Query 10.2: Income Optimization
```
I want to maximize dividend income. For my current stock positions, show dividend yields.
For my cash/buying power, recommend high-yield dividend stocks with strong institutional
backing and positive analyst ratings.
```
**Tests:** Multiple tools for comprehensive dividend income strategy

### Query 10.3: Risk-Adjusted Returns
```
Calculate the ROI for each of my accounts. Get the historical volatility (via historical
prices) for my top positions. Which account has the best risk-adjusted returns?
```
**Tests:** `compare_accounts` + `calculate_roi` + `get_historical_stock_prices`

---

## Test Execution Tips

1. **Start Simple**: Begin with queries 1.1-1.7 to verify individual tools work
2. **Build Complexity**: Move to integration queries (2.x, 3.x)
3. **Test Edge Cases**: Try tickers with no dividends, no options, delisted stocks
4. **Verify Data Quality**: Check that financial data is recent and accurate
5. **Performance Testing**: Time the responses for complex multi-tool queries

## Expected Response Times

- Simple queries (single tool): < 2 seconds
- Integration queries (2-3 tools): 2-5 seconds
- Complex analysis (5+ tools): 5-10 seconds
- Heavy financial data queries: May take longer due to API rate limits

## Success Criteria

✅ All 7 Yahoo Finance tools respond correctly
✅ Integration queries combine data from multiple sources
✅ Error handling works (invalid tickers, missing data)
✅ Portfolio analysis provides actionable insights
✅ Community knowledge integrates with market data
✅ No timeouts or crashes on complex queries

---

**Generated:** 2025-10-20
**MCP Server Version:** 1.0.0 (31 tools)
**Total Test Queries:** 33
