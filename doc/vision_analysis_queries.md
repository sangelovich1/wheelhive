# Vision Analysis Queries

SQL queries and Python code to leverage extracted image data from Discord messages.

## Overview

The `harvested_messages.extracted_data` column contains JSON with:
- `raw_text`: Full OCR text extraction
- `image_type`: Classification (trade_execution, account_summary, technical_analysis, other, error)
- `tickers`: List of ticker symbols mentioned
- `sentiment`: Bullish, bearish, or neutral
- `trades`: Structured trade data (if detected)
- `account_value`: Account balance (if account_summary)
- `daily_pnl`: Daily profit/loss (if account_summary)

## Quick Stats Queries

### 1. Image Analysis Coverage
```sql
-- Overall image analysis stats
SELECT
    COUNT(*) as total_images,
    SUM(CASE WHEN extracted_data IS NOT NULL THEN 1 ELSE 0 END) as analyzed,
    ROUND(100.0 * SUM(CASE WHEN extracted_data IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_analyzed
FROM harvested_messages
WHERE has_attachments = 1;
```

### 2. Image Type Distribution
```sql
-- Breakdown by image type
SELECT
    json_extract(extracted_data, '$.image_type') as image_type,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM harvested_messages
WHERE extracted_data IS NOT NULL
GROUP BY image_type
ORDER BY count DESC;
```

### 3. Sentiment Analysis
```sql
-- Community sentiment breakdown
SELECT
    json_extract(extracted_data, '$.sentiment') as sentiment,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM harvested_messages
WHERE extracted_data IS NOT NULL
GROUP BY sentiment
ORDER BY count DESC;
```

## Ticker-Based Queries

### 4. Most Mentioned Tickers (from images)
```sql
-- Top tickers mentioned in trading images
WITH ticker_mentions AS (
    SELECT
        username,
        channel_name,
        timestamp,
        json_extract(extracted_data, '$.tickers') as tickers_json
    FROM harvested_messages
    WHERE extracted_data IS NOT NULL
    AND json_extract(extracted_data, '$.image_type') = 'trade_execution'
),
expanded_tickers AS (
    SELECT
        username,
        channel_name,
        timestamp,
        value as ticker
    FROM ticker_mentions, json_each(ticker_mentions.tickers_json)
    WHERE value NOT IN ('TEXT', 'ID', 'SOLD', 'OCT', 'MAX', 'YTD', 'AM', 'PM', 'ET', 'RH', 'IBKR', 'SHS', 'EXP', 'ETHU', 'CDT', 'BOT', 'BUY', 'SELL', 'USD', 'SPX')
)
SELECT
    ticker,
    COUNT(*) as mentions,
    COUNT(DISTINCT username) as unique_users
FROM expanded_tickers
GROUP BY ticker
ORDER BY mentions DESC
LIMIT 20;
```

### 5. Ticker Sentiment Analysis
```sql
-- Sentiment breakdown for a specific ticker (e.g., META)
WITH ticker_sentiment AS (
    SELECT
        json_extract(extracted_data, '$.sentiment') as sentiment,
        timestamp
    FROM harvested_messages, json_each(json_extract(extracted_data, '$.tickers'))
    WHERE extracted_data IS NOT NULL
    AND value = 'META'  -- Change ticker here
)
SELECT
    sentiment,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM ticker_sentiment
GROUP BY sentiment
ORDER BY count DESC;
```

### 6. Hot Tickers (Last 7 Days)
```sql
-- Trending tickers from recent trading images
WITH recent_tickers AS (
    SELECT
        value as ticker,
        timestamp
    FROM harvested_messages, json_each(json_extract(extracted_data, '$.tickers'))
    WHERE extracted_data IS NOT NULL
    AND json_extract(extracted_data, '$.image_type') = 'trade_execution'
    AND timestamp >= date('now', '-7 days')
    AND value NOT IN ('TEXT', 'ID', 'SOLD', 'OCT', 'MAX', 'YTD', 'AM', 'PM', 'ET', 'RH', 'IBKR')
)
SELECT
    ticker,
    COUNT(*) as mentions_last_7d,
    COUNT(DISTINCT DATE(timestamp)) as active_days
FROM recent_tickers
GROUP BY ticker
HAVING mentions_last_7d >= 3
ORDER BY mentions_last_7d DESC, active_days DESC
LIMIT 15;
```

## User Activity Queries

### 7. Top Image Posters
```sql
-- Users who post the most trading images
SELECT
    username,
    COUNT(*) as images_posted,
    SUM(CASE WHEN json_extract(extracted_data, '$.image_type') = 'trade_execution' THEN 1 ELSE 0 END) as trade_images,
    SUM(CASE WHEN json_extract(extracted_data, '$.image_type') = 'account_summary' THEN 1 ELSE 0 END) as account_images
FROM harvested_messages
WHERE extracted_data IS NOT NULL
GROUP BY username
ORDER BY images_posted DESC
LIMIT 20;
```

### 8. User Trading Activity Timeline
```sql
-- User's image posting pattern over time (e.g., darkminer)
SELECT
    DATE(timestamp) as date,
    COUNT(*) as images_posted,
    json_extract(extracted_data, '$.image_type') as image_type
FROM harvested_messages
WHERE username = 'darkminer'  -- Change username here
AND extracted_data IS NOT NULL
GROUP BY DATE(timestamp), image_type
ORDER BY date DESC
LIMIT 30;
```

## Account Summary Queries

### 9. Account Value Tracking
```sql
-- Track account values over time (from account screenshots)
SELECT
    username,
    DATE(timestamp) as date,
    json_extract(extracted_data, '$.account_value') as account_value,
    json_extract(extracted_data, '$.daily_pnl') as daily_pnl
FROM harvested_messages
WHERE extracted_data IS NOT NULL
AND json_extract(extracted_data, '$.image_type') = 'account_summary'
AND json_extract(extracted_data, '$.account_value') IS NOT NULL
ORDER BY username, date DESC;
```

### 10. Biggest Winners/Losers (from images)
```sql
-- Users with highest reported P&L in images
SELECT
    username,
    MAX(CAST(json_extract(extracted_data, '$.daily_pnl') as REAL)) as max_daily_pnl,
    DATE(timestamp) as date
FROM harvested_messages
WHERE extracted_data IS NOT NULL
AND json_extract(extracted_data, '$.daily_pnl') IS NOT NULL
GROUP BY username
ORDER BY max_daily_pnl DESC
LIMIT 10;
```

## Content Search Queries

### 11. Search Extracted Text
```sql
-- Full-text search in extracted image text (e.g., find "STO" mentions)
SELECT
    message_id,
    username,
    channel_name,
    DATE(timestamp) as date,
    json_extract(extracted_data, '$.raw_text') as extracted_text
FROM harvested_messages
WHERE extracted_data IS NOT NULL
AND json_extract(extracted_data, '$.raw_text') LIKE '%STO%'  -- Change search term
ORDER BY timestamp DESC
LIMIT 20;
```

### 12. Find Technical Analysis Images
```sql
-- Get all technical analysis charts/screenshots
SELECT
    username,
    DATE(timestamp) as date,
    json_extract(extracted_data, '$.tickers') as tickers,
    SUBSTR(json_extract(extracted_data, '$.raw_text'), 1, 150) as preview
FROM harvested_messages
WHERE extracted_data IS NOT NULL
AND json_extract(extracted_data, '$.image_type') = 'technical_analysis'
ORDER BY timestamp DESC;
```

## Community Insights

### 13. Bullish vs Bearish Community Sentiment (Last 30 Days)
```sql
-- Overall community sentiment trend
SELECT
    DATE(timestamp) as date,
    SUM(CASE WHEN json_extract(extracted_data, '$.sentiment') = 'bullish' THEN 1 ELSE 0 END) as bullish,
    SUM(CASE WHEN json_extract(extracted_data, '$.sentiment') = 'bearish' THEN 1 ELSE 0 END) as bearish,
    SUM(CASE WHEN json_extract(extracted_data, '$.sentiment') = 'neutral' THEN 1 ELSE 0 END) as neutral
FROM harvested_messages
WHERE extracted_data IS NOT NULL
AND timestamp >= date('now', '-30 days')
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

### 14. Channel Activity Comparison
```sql
-- Compare image posting across channels
SELECT
    channel_name,
    COUNT(*) as total_images,
    SUM(CASE WHEN json_extract(extracted_data, '$.image_type') = 'trade_execution' THEN 1 ELSE 0 END) as trade_images,
    ROUND(AVG(CASE
        WHEN json_extract(extracted_data, '$.sentiment') = 'bullish' THEN 1
        WHEN json_extract(extracted_data, '$.sentiment') = 'bearish' THEN -1
        ELSE 0
    END), 2) as sentiment_score
FROM harvested_messages
WHERE extracted_data IS NOT NULL
GROUP BY channel_name
ORDER BY total_images DESC;
```

## Python Helper Functions

### Extract Tickers from Vision Data
```python
import sqlite3
import json

def get_trending_tickers(db_path='trades.db', days=7, min_mentions=3):
    """Get trending tickers from vision-analyzed images"""
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    query = """
    WITH recent_tickers AS (
        SELECT
            value as ticker,
            timestamp
        FROM harvested_messages, json_each(json_extract(extracted_data, '$.tickers'))
        WHERE extracted_data IS NOT NULL
        AND json_extract(extracted_data, '$.image_type') = 'trade_execution'
        AND timestamp >= date('now', '-' || ? || ' days')
        AND value NOT IN ('TEXT', 'ID', 'SOLD', 'OCT', 'MAX', 'YTD', 'AM', 'PM', 'ET', 'RH', 'IBKR')
    )
    SELECT
        ticker,
        COUNT(*) as mentions
    FROM recent_tickers
    GROUP BY ticker
    HAVING mentions >= ?
    ORDER BY mentions DESC
    """

    cursor.execute(query, (days, min_mentions))
    return cursor.fetchall()

# Usage:
# trending = get_trending_tickers(days=7, min_mentions=3)
# for ticker, mentions in trending:
#     print(f"{ticker}: {mentions} mentions")
```

### Get Sentiment for Ticker
```python
def get_ticker_sentiment(ticker, db_path='trades.db'):
    """Get sentiment breakdown for a specific ticker"""
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    query = """
    WITH ticker_messages AS (
        SELECT
            json_extract(extracted_data, '$.sentiment') as sentiment
        FROM harvested_messages, json_each(json_extract(extracted_data, '$.tickers'))
        WHERE extracted_data IS NOT NULL
        AND value = ?
    )
    SELECT
        sentiment,
        COUNT(*) as count
    FROM ticker_messages
    GROUP BY sentiment
    """

    cursor.execute(query, (ticker,))
    results = cursor.fetchall()

    total = sum(count for _, count in results)
    sentiment_pct = {
        sentiment: round(100.0 * count / total, 1)
        for sentiment, count in results
    }

    return sentiment_pct

# Usage:
# sentiment = get_ticker_sentiment('META')
# print(f"Bullish: {sentiment.get('bullish', 0)}%")
# print(f"Bearish: {sentiment.get('bearish', 0)}%")
```

### Search Image Text
```python
def search_image_text(search_term, db_path='trades.db', limit=20):
    """Search extracted text from images"""
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    query = """
    SELECT
        message_id,
        username,
        channel_name,
        DATE(timestamp) as date,
        json_extract(extracted_data, '$.image_type') as image_type,
        json_extract(extracted_data, '$.raw_text') as extracted_text
    FROM harvested_messages
    WHERE extracted_data IS NOT NULL
    AND json_extract(extracted_data, '$.raw_text') LIKE ?
    ORDER BY timestamp DESC
    LIMIT ?
    """

    cursor.execute(query, (f'%{search_term}%', limit))
    return cursor.fetchall()

# Usage:
# results = search_image_text('STO')
# for msg_id, user, channel, date, img_type, text in results:
#     print(f"[{date}] @{user} in #{channel}: {text[:100]}...")
```

## Integration with MCP Tools

The `get_community_messages` MCP tool already includes extracted_data in its output.

When the LLM queries community messages, it will see:
```
[2025-11-01] @user in stock-talk-options:
  Posted image of META trade

  [Image Analysis - trade_execution]
  Extracted: SOLD -2 META 100 (Weeklys) 10 OCT 25 680 PUT @2.70
  Tickers: META
  Sentiment: bearish
```

This allows the LLM to:
- Answer questions about community trades even if users posted images instead of text
- Provide ticker-specific insights from screenshots
- Track sentiment from trading images
- Discover trending plays from account screenshots

## Next Steps

1. Test queries on production data
2. Add to CLI as `python src/cli.py messages stats` command
3. Create visualization dashboard (matplotlib/plotly)
4. Add to daily digest report
5. Create MCP tools for vision-specific queries

---

Generated: 2025-11-01
Vision Model: Claude Sonnet 4.5
Total Images Analyzed: 1,110 (est.)
Cost: ~$3.33
