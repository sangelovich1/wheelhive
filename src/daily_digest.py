"""
Daily Digest Generator

Creates daily and weekly community digests with:
- Market sentiment context (VIX, Fear & Greed, etc.)
- LLM-generated narrative summary
- Trending tickers from community discussions
- Scanner opportunities
- Community activity statistics

Friday digests are more comprehensive, covering the full week.
Length-limited to fit in one Discord message/page.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import constants as const
from db import Db
from llm_provider import create_llm_provider
from market_sentiment import MarketSentiment
from messages import Messages
from providers.market_data_factory import MarketDataFactory
from tickers import Tickers


logger = logging.getLogger(__name__)


class DailyDigest:
    """Generate daily and weekly community digests."""

    # Length limits for one-page display
    MAX_LINES_DAILY = 80  # ~1-2 pages for daily digest (increased for verbose narratives)
    MAX_LINES_WEEKLY = (
        200  # ~2-3 pages for weekly digest (increased for verbose narratives with formatting)
    )

    def __init__(
        self,
        db: Db,
        guild_id: int | None = None,
        enable_llm: bool = True,
        llm_temperature: float = 1.0,
        llm_model: str | None = None,
    ):
        """
        Initialize the daily digest generator.

        Args:
            db: Database instance
            guild_id: Discord guild (server) ID to filter messages (optional, defaults to first guild in const.GUILDS)
            enable_llm: Whether to generate LLM narrative summaries (default: True)
            llm_temperature: LLM temperature for narrative generation (0.0-2.0, default: 1.0)
                           Lower = more focused/conservative, Higher = more creative/colorful
            llm_model: Model key to use for LLM (optional, defaults to database default model)
        """
        self.db = db
        self.guild_id = guild_id or (const.GUILDS[0] if const.GUILDS else None)
        self.messages = Messages(db)
        self.tickers_db = Tickers(db)
        self.market_sentiment = MarketSentiment()
        self.enable_llm = enable_llm
        self.llm_temperature = llm_temperature
        # Create LLM provider with optional model override
        self.llm_provider = create_llm_provider(model_key=llm_model) if enable_llm else None

    def generate_digest(self, date: datetime | None = None) -> str:
        """
        Generate a community digest for the specified date.

        Always generates a rolling 7-day digest for better signal-to-noise ratio
        and more meaningful pattern detection from vision trade data.

        Args:
            date: Date to generate digest for (defaults to today)

        Returns:
            Formatted digest string (7-day rolling window)
        """
        if date is None:
            date = datetime.now()

        # Always use 7-day rolling window format for better insights
        return self._generate_weekly_digest(date)

    def _generate_daily_digest(self, date: datetime) -> str:
        """
        Generate daily digest (24-hour period).

        Args:
            date: Date to generate digest for

        Returns:
            Formatted digest string
        """
        day_name = date.strftime("%A")  # e.g., "Monday"
        date_str = date.strftime("%B %d, %Y")  # e.g., "October 20, 2025"

        lines = []
        lines.append(f"# 📊 DAILY DIGEST - {day_name}, {date_str}")
        lines.append("")

        # Market sentiment context
        market_context = self._get_market_context()
        if market_context:
            lines.extend(market_context)
            lines.append("")

        # Get trending tickers (last 24 hours)
        trending = self._get_trending_tickers(days=1, limit=5)

        if trending:
            lines.append("🔥 Trending Tickers (last 24h):")
            for ticker, count, sentiment in trending:
                emoji = self._sentiment_emoji(sentiment)
                lines.append(f"  {emoji} ${ticker} ({count} mentions)")
            lines.append("")
        else:
            lines.append("🔥 Trending Tickers: No activity in last 24 hours")
            lines.append("")

        # Community activity stats
        activity = self._get_community_activity(days=1)

        # Generate LLM narrative summary
        llm_narrative = self._generate_llm_narrative(
            trending=trending, activity=activity, market_context=market_context, is_weekly=False
        )
        if llm_narrative:
            lines.extend(llm_narrative)
            lines.append("")

        # Generate news summary
        news_summary = self._generate_news_summary(days=1, is_weekly=False)
        if news_summary:
            lines.extend(news_summary)
            lines.append("")

        # Get most active options from actual community trades
        active_options = self._get_most_active_options(days=1, limit=3, end_date=date)
        if active_options:
            lines.append("📈 Most Active Options (today):")
            for opt in active_options:
                traders_text = "trader" if opt["traders"] == 1 else "traders"
                lines.append(
                    f"  • {opt['primary_operation']} {opt['contracts']}x "
                    f"{opt['ticker']} {opt['strike']}{opt['type']} {opt['expiration']} "
                    f"({opt['traders']} {traders_text})"
                )
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("*Generated by WheelHive* 🤖")

        # Trim to fit one page
        lines = self._trim_to_max_lines(lines, self.MAX_LINES_DAILY)

        return "\n".join(lines)

    def _generate_weekly_digest(self, date: datetime) -> str:
        """
        Generate comprehensive weekly digest (Monday-Friday).

        Args:
            date: Friday date to generate digest for

        Returns:
            Formatted digest string
        """
        date_str = date.strftime("%B %d, %Y")  # e.g., "October 18, 2025"

        lines = []
        lines.append(f"# 📊 WEEKLY DIGEST - Week Ending {date_str}")
        lines.append("")

        # Market sentiment context
        market_context = self._get_market_context()
        if market_context:
            lines.extend(market_context)
            lines.append("")

        # Get trending tickers (last 7 days for full week view)
        trending = self._get_trending_tickers(days=7, limit=10)

        if trending:
            lines.append("🔥 Top Trending Tickers (this week):")
            for i, (ticker, count, sentiment) in enumerate(trending, 1):
                emoji = self._sentiment_emoji(sentiment)
                lines.append(f"  {i}. {emoji} ${ticker} ({count} mentions)")
            lines.append("")
        else:
            lines.append("🔥 Top Trending Tickers: No activity this week")
            lines.append("")

        # Weekly activity stats
        activity = self._get_community_activity(days=7)

        # Generate LLM narrative summary
        llm_narrative = self._generate_llm_narrative(
            trending=trending, activity=activity, market_context=market_context, is_weekly=True
        )
        if llm_narrative:
            lines.extend(llm_narrative)
            lines.append("")

        # Generate news summary
        news_summary = self._generate_news_summary(days=7, is_weekly=True)
        if news_summary:
            lines.extend(news_summary)
            lines.append("")

        # Get most active options from actual community trades
        active_options = self._get_most_active_options(days=7, limit=5, end_date=date)
        if active_options:
            lines.append("📈 Most Active Options (this week):")
            for i, opt in enumerate(active_options, 1):
                traders_text = "trader" if opt["traders"] == 1 else "traders"
                lines.append(
                    f"  {i}. {opt['primary_operation']} {opt['contracts']}x "
                    f"{opt['ticker']} {opt['strike']}{opt['type']} {opt['expiration']} "
                    f"({opt['traders']} {traders_text})"
                )
            lines.append("")

        # Footer
        lines.append("=" * 50)
        lines.append("*Generated by WheelHive* 🤖")

        # Trim to fit one page
        lines = self._trim_to_max_lines(lines, self.MAX_LINES_WEEKLY)

        return "\n".join(lines)

    def _get_trading_activity_from_images(self, days: int) -> dict[str, Any]:
        """
        Extract actual trading activity from vision-analyzed images.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with trading activity data including operations, tickers, and examples
        """
        try:
            import json

            query = """
                SELECT extracted_data, username
                FROM harvested_messages
                WHERE extracted_data IS NOT NULL
                    AND timestamp >= datetime('now', ?)
                    AND guild_id = ?
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id))

            if not results:
                return {}

            # Aggregate trade data
            total_trades = 0
            operations: dict[str, int] = {}
            ticker_trades = {}  # ticker -> {trade_count, sentiment, examples}
            sentiment_split = {"bullish": 0, "bearish": 0, "neutral": 0}

            for row in results:
                data_json, username = row[0], row[1]
                try:
                    data = json.loads(data_json)
                except:
                    continue

                # Count trades
                trades = data.get("trades", [])
                total_trades += len(trades)

                # Aggregate operations (STO, BTC, BTO, STC)
                for trade in trades:
                    # Prefer direct operation field (new format), fallback to deriving from action+position_effect (legacy)
                    op = trade.get("operation")
                    if not op:
                        # Legacy format: derive from action+position_effect
                        action = trade.get("action", "")  # "BUY" or "SELL"
                        effect = trade.get("position_effect", "")  # "OPEN" or "CLOSE"
                        if action and effect:
                            op = f"{action[0]}{effect[0]}O"  # e.g., "STO", "BTC"
                        else:
                            op = "UNKNOWN"

                    operations[op] = operations.get(op, 0) + 1

                # Track tickers from actual trades (not OCR tickers list which has false positives)
                for trade in trades:
                    # Try new format first, fall back to old format
                    ticker = trade.get("ticker") or trade.get("symbol")
                    if not ticker:
                        continue

                    if ticker not in ticker_trades:
                        ticker_trades[ticker] = {
                            "trade_count": 0,
                            "sentiment": data.get("sentiment", "neutral"),
                            "examples": [],
                        }

                    ticker_trades[ticker]["trade_count"] += 1

                    # Store example trades (limit to 2 per ticker)
                    # Support both new Pydantic and old format
                    if len(ticker_trades[ticker]["examples"]) < 2:
                        action = trade.get("action", "")
                        effect = trade.get("position_effect", "")
                        operation = (
                            f"{action[0]}{effect[0]}O"
                            if (action and effect)
                            else trade.get("operation", "UNKNOWN")
                        )

                        ticker_trades[ticker]["examples"].append(
                            {
                                "username": username,
                                "operation": operation,
                                "contracts": trade.get("quantity")
                                or trade.get("contracts"),  # New: quantity, Old: contracts
                                "strike": trade.get("strike"),
                                "option_type": trade.get("option_type"),
                                "premium": trade.get("premium"),
                                "expiration": trade.get("expiration"),  # New field from Pydantic
                                "source": trade.get("source", "unknown"),  # New field: text|image
                            }
                        )

                # Aggregate sentiment
                sentiment = data.get("sentiment", "neutral").lower()
                if sentiment in sentiment_split:
                    sentiment_split[sentiment] += 1

            # Sort tickers by trade count
            top_traded = []
            for ticker, info in sorted(
                ticker_trades.items(), key=lambda x: x[1]["trade_count"], reverse=True
            ):
                top_traded.append(
                    {
                        "ticker": ticker,
                        "trade_count": info["trade_count"],
                        "sentiment": info["sentiment"],
                        "examples": info["examples"],
                    }
                )

            return {
                "total_trades": total_trades,
                "operations": operations,
                "top_traded": top_traded[:10],  # Top 10 tickers
                "sentiment_split": sentiment_split,
            }

        except Exception as e:
            logger.error(f"Error getting trading activity from images: {e}", exc_info=True)
            return {}

    def _get_trending_tickers(self, days: int, limit: int) -> list[tuple[str, int, str]]:
        """
        Get trending tickers from community messages.

        Args:
            days: Number of days to look back
            limit: Maximum number of tickers to return

        Returns:
            List of tuples: (ticker, mention_count, sentiment)
        """
        try:
            query = """
                SELECT
                    mt.ticker,
                    COUNT(*) as mention_count,
                    'neutral' as sentiment
                FROM message_tickers mt
                JOIN harvested_messages hm ON mt.message_id = hm.message_id
                WHERE hm.timestamp >= datetime('now', ?)
                    AND hm.guild_id = ?
                GROUP BY mt.ticker
                ORDER BY mention_count DESC
                LIMIT ?
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id, limit))

            trending = []
            for row in results:
                ticker = row[0]
                count = row[1]
                sentiment = row[2]  # TODO: Calculate actual sentiment from message content
                trending.append((ticker, count, sentiment))

            return trending

        except Exception as e:
            logger.error(f"Error getting trending tickers: {e}", exc_info=True)
            return []

    def _get_ticker_company_names(self, tickers: list[str]) -> dict[str, str]:
        """
        Fetch actual company names for ticker symbols.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker symbol to company name
        """
        ticker_names = {}
        for ticker in tickers:
            try:
                info = MarketDataFactory.get_stock_info_with_fallback(ticker)
                company_name = info.get("company_name", ticker)
                ticker_names[ticker] = company_name
                logger.debug(f"Resolved {ticker} -> {company_name}")
            except Exception as e:
                logger.warning(f"Could not fetch company name for {ticker}: {e}")
                ticker_names[ticker] = ticker  # Fallback to ticker symbol
        return ticker_names

    def _get_most_active_options(
        self, days: int, limit: int = 5, end_date: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Get most actively traded options from vision-analyzed images.

        Args:
            days: Number of days to look back
            limit: Maximum number of options to return
            end_date: End date for the lookback period (defaults to now)

        Returns:
            List of most traded options with details
        """
        try:
            import json
            from collections import defaultdict
            from datetime import timedelta

            # Calculate date range
            if end_date is None:
                end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            query = """
                SELECT extracted_data, username
                FROM harvested_messages
                WHERE extracted_data IS NOT NULL
                    AND timestamp >= ?
                    AND timestamp <= ?
                    AND guild_id = ?
            """

            results = self.db.query_parameterized(
                query, (start_date.isoformat(), end_date.isoformat(), self.guild_id)
            )

            if not results:
                return []

            # Aggregate options by unique identifier (ticker + strike + type + exp)
            option_trades: defaultdict[str, dict[str, Any]] = defaultdict(
                lambda: {"contracts": 0, "operations": defaultdict(int), "usernames": set()}
            )

            for row in results:
                data_json, username = row[0], row[1]
                try:
                    data = json.loads(data_json)
                except:
                    continue

                trades = data.get("trades", [])
                for trade in trades:
                    # Only process options trades (not shares)
                    if not trade.get("option_type"):
                        continue

                    # Support both new Pydantic and old format
                    ticker = trade.get("ticker") or trade.get("symbol")
                    strike = trade.get("strike")
                    option_type = trade.get("option_type", "").upper()
                    expiration = trade.get("expiration", "")

                    # Get operation (prefer direct field, fallback to deriving from action+position_effect)
                    operation = trade.get("operation")
                    if not operation:
                        # Legacy format: derive from action+position_effect
                        action = trade.get("action", "")
                        effect = trade.get("position_effect", "")
                        if action and effect:
                            operation = f"{action[0]}{effect[0]}O"  # e.g., "STO", "BTC"
                        else:
                            operation = "UNKNOWN"

                    contracts = trade.get("quantity") or trade.get(
                        "contracts", 1
                    )  # New: quantity, Old: contracts

                    if not ticker or not strike or not option_type:
                        continue

                    # Create unique key for this option
                    option_key = f"{ticker}_{strike}{option_type}_{expiration}"

                    option_trades[option_key]["contracts"] += contracts
                    option_trades[option_key]["operations"][operation] += 1
                    option_trades[option_key]["usernames"].add(username)
                    option_trades[option_key]["ticker"] = ticker
                    option_trades[option_key]["strike"] = strike
                    option_trades[option_key]["type"] = option_type
                    option_trades[option_key]["expiration"] = expiration

            # Sort by total contracts and return top N
            sorted_options = sorted(
                option_trades.items(), key=lambda x: x[1]["contracts"], reverse=True
            )[:limit]

            # Format results
            formatted_results: list[dict[str, Any]] = []
            for option_key, info in sorted_options:
                # Get primary operation (most common)
                primary_op = (
                    max(info["operations"].items(), key=lambda x: x[1])[0]
                    if info["operations"]
                    else "TRADE"
                )

                formatted_results.append(
                    {
                        "ticker": info["ticker"],
                        "strike": info["strike"],
                        "type": info["type"],
                        "expiration": info["expiration"],
                        "contracts": info["contracts"],
                        "traders": len(info["usernames"]),
                        "primary_operation": primary_op,
                    }
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Error getting most active options: {e}", exc_info=True)
            return []

    def _get_community_activity(self, days: int) -> dict[str, Any]:
        """
        Get community activity statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary with activity stats
        """
        try:
            query = """
                SELECT
                    COUNT(*) as message_count,
                    COUNT(DISTINCT username) as unique_users,
                    COUNT(DISTINCT mt.ticker) as unique_tickers
                FROM harvested_messages hm
                LEFT JOIN message_tickers mt ON hm.message_id = mt.message_id
                WHERE hm.timestamp >= datetime('now', ?)
                    AND hm.guild_id = ?
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id))

            if results:
                row = results[0]
                return {
                    "message_count": row[0] or 0,
                    "unique_users": row[1] or 0,
                    "unique_tickers": row[2] or 0,
                    "avg_messages_per_day": (row[0] or 0) / days,
                }

            return {
                "message_count": 0,
                "unique_users": 0,
                "unique_tickers": 0,
                "avg_messages_per_day": 0,
            }

        except Exception as e:
            logger.error(f"Error getting community activity: {e}", exc_info=True)
            return {
                "message_count": 0,
                "unique_users": 0,
                "unique_tickers": 0,
                "avg_messages_per_day": 0,
            }

    def _get_news_messages(self, days: int, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get recent news messages from news channels.

        Args:
            days: Number of days to look back
            limit: Maximum number of messages to return

        Returns:
            List of dictionaries with news message data
        """
        try:
            query = """
                SELECT content, username, timestamp, channel_name
                FROM harvested_messages
                WHERE category = 'news'
                    AND timestamp >= datetime('now', ?)
                    AND guild_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id, limit))

            news_items = []
            for row in results:
                news_items.append(
                    {"content": row[0], "username": row[1], "timestamp": row[2], "channel": row[3]}
                )

            return news_items

        except Exception as e:
            logger.error(f"Error getting news messages: {e}", exc_info=True)
            return []

    def _generate_news_summary(self, days: int, is_weekly: bool = False) -> list[str]:
        """
        Generate LLM summary of news from news channels.

        Args:
            days: Number of days to look back
            is_weekly: Whether this is weekly digest (vs daily)

        Returns:
            List of formatted strings for news summary section
        """
        if not self.enable_llm or not self.llm_provider:
            return []

        try:
            news_items = self._get_news_messages(days, limit=20)

            if not news_items:
                return []

            period = "this week" if is_weekly else "the last 24 hours"
            news_text = "\n\n".join(
                [
                    f"- {item['content'][:200]}..."
                    if len(item["content"]) > 200
                    else f"- {item['content']}"
                    for item in news_items[:15]
                ]
            )

            word_limit = "300 words" if is_weekly else "200 words"
            prompt = f"""You are summarizing industry news and market updates from {period}.

News Items:
{news_text}

Write a detailed summary that:
1. Highlights the most important news themes or events WITH SPECIFIC DETAILS (company names, numbers, locations)
2. Focuses on market-moving information relevant to options traders
3. Identifies which sectors/tickers are being impacted
4. Keeps a professional and informative tone

FORMAT REQUIREMENTS:
- Organize into clear sections with headers (e.g., "Key Developments:", "Sector Impact:")
- Use bullet points for lists of companies or tickers
- Use paragraphs to explain each major news item
- Separate different news topics with blank lines

Keep it under {word_limit}. Be detailed and reference specific companies, events, and numbers from the news."""

            max_tokens = 600 if is_weekly else 400
            response = self.llm_provider.completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=self.llm_temperature,
            )

            summary = response.choices[0].message.content.strip()

            # Remove problematic markdown but keep bullets
            summary = summary.replace("## ", "").replace("### ", "").replace("#### ", "")
            summary = summary.replace("**", "")  # Remove bold
            summary = summary.replace("__", "")  # Remove underline

            # Format as digest section with proper paragraph/bullet handling
            lines = ["📰 Market News Highlights:"]

            # Split into paragraphs (preserve blank lines)
            paragraphs = summary.split("\n\n")

            for para_idx, paragraph in enumerate(paragraphs):
                if not paragraph.strip():
                    continue

                # Check if this paragraph contains bullet points
                para_lines = paragraph.split("\n")
                is_bullet_list = any(
                    line.strip().startswith(("- ", "• ", "* ")) for line in para_lines
                )

                if is_bullet_list:
                    # Handle bullet list (including any header lines before bullets)
                    for line in para_lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Convert markdown bullets to consistent format
                        if line.startswith("- ") or line.startswith("* "):
                            line = "• " + line[2:]
                            lines.append(f"  {line}")
                        else:
                            # Non-bullet line (likely a header or intro) - output as-is
                            lines.append(f"  {line}")
                else:
                    # Handle regular paragraph - wrap at 80 chars
                    words = paragraph.split()
                    current_line = "  "
                    for word in words:
                        if len(current_line) + len(word) + 1 > 80:
                            lines.append(current_line)
                            current_line = "  " + word
                        else:
                            current_line += (" " if current_line != "  " else "") + word
                    if current_line.strip():
                        lines.append(current_line)

                # Add blank line between paragraphs (except after last one)
                if para_idx < len(paragraphs) - 1:
                    lines.append("")

            return lines

        except Exception as e:
            logger.error(f"Error generating news summary: {e}", exc_info=True)
            return []

    def _get_top_users(self, days: int, limit: int) -> list[tuple[str, int]]:
        """
        Get most active users.

        Args:
            days: Number of days to look back
            limit: Maximum number of users to return

        Returns:
            List of tuples: (username, message_count)
        """
        try:
            query = """
                SELECT
                    username,
                    COUNT(*) as message_count
                FROM harvested_messages
                WHERE timestamp >= datetime('now', ?)
                    AND guild_id = ?
                GROUP BY username
                ORDER BY message_count DESC
                LIMIT ?
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id, limit))

            return [(row[0], row[1]) for row in results]

        except Exception as e:
            logger.error(f"Error getting top users: {e}", exc_info=True)
            return []

    def _get_channel_breakdown(self, days: int) -> dict[str, int]:
        """
        Get message count breakdown by channel.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary mapping channel name to message count
        """
        try:
            query = """
                SELECT
                    channel_name,
                    COUNT(*) as message_count
                FROM harvested_messages
                WHERE timestamp >= datetime('now', ?)
                    AND guild_id = ?
                GROUP BY channel_name
                ORDER BY message_count DESC
            """

            days_param = f"-{days} days"
            results = self.db.query_parameterized(query, (days_param, self.guild_id))

            return {row[0]: row[1] for row in results}

        except Exception as e:
            logger.error(f"Error getting channel breakdown: {e}", exc_info=True)
            return {}

    def _sentiment_emoji(self, sentiment: str) -> str:
        """
        Get emoji for sentiment.

        Args:
            sentiment: 'bullish', 'bearish', or 'neutral'

        Returns:
            Emoji string
        """
        sentiment_map = {"bullish": "🐂", "bearish": "🐻", "neutral": "➡️", "mixed": "🔄"}
        return sentiment_map.get(sentiment.lower(), "❓")

    def _get_market_context(self) -> list[str]:
        """
        Get market sentiment context for digest.

        Returns:
            List of formatted strings for market context section
        """
        lines = []
        lines.append("🌍 Market Context:")

        try:
            # Get all sentiment data
            sentiment_data = self.market_sentiment.get_all_sentiment_indicators()

            # VIX
            if sentiment_data.get("vix"):
                vix = sentiment_data["vix"]
                lines.append(f"  • VIX: {vix['price']:.1f} ({vix['interpretation']})")

            # Fear & Greed
            if sentiment_data.get("fear_and_greed"):
                fg = sentiment_data["fear_and_greed"]
                lines.append(f"  • Fear & Greed: {fg['value']}/100 ({fg['classification']})")

            # Treasury yield curve (condensed)
            if sentiment_data.get("treasury"):
                treasury = sentiment_data["treasury"]
                lines.append(
                    f"  • 10Y-2Y Spread: {treasury['spread']:+.2f}% ({treasury['spread_interpretation']})"
                )

            if len(lines) == 1:  # Only header, no data
                return []  # Skip section if no data available

        except Exception as e:
            logger.warning(f"Error fetching market context: {e}", exc_info=True)
            return []  # Skip section on error

        return lines

    def _generate_llm_narrative(
        self,
        trending: list[tuple[str, int, str]],
        activity: dict[str, Any],
        market_context: list[str],
        is_weekly: bool = False,
    ) -> list[str]:
        """
        Generate LLM narrative summary of digest data.

        Args:
            trending: List of (ticker, count, sentiment) tuples
            activity: Community activity statistics
            market_context: Market sentiment lines
            is_weekly: Whether this is weekly digest (vs daily)

        Returns:
            List of formatted strings for narrative section
        """
        if not self.enable_llm or not self.llm_provider:
            return []

        try:
            # Build context for LLM
            period = "this week" if is_weekly else "the last 24 hours"
            days = 7 if is_weekly else 1

            # Extract market sentiment summary
            market_summary = ""
            if market_context:
                market_summary = "\n".join(market_context)

            # Fetch actual company names for trending tickers
            ticker_names = {}
            if trending:
                ticker_symbols = [t[0] for t in trending[:10]]  # Get names for top 10
                ticker_names = self._get_ticker_company_names(ticker_symbols)

            # Build trending summary with actual company names
            trending_summary = ""
            if trending:
                ticker_lines = []
                for ticker, count, sentiment in trending[:10]:
                    company_name = ticker_names.get(ticker, ticker)
                    ticker_lines.append(f"  - {ticker} ({company_name}): {count} mentions")
                trending_summary = "Top tickers:\n" + "\n".join(ticker_lines)

            # Get vision-analyzed trade data
            trade_activity = self._get_trading_activity_from_images(days)

            # Build trade examples section from raw ticker activity
            trade_examples = ""
            if trade_activity and trade_activity.get("top_traded"):
                examples = []
                for ticker_info in trade_activity["top_traded"][:5]:  # Top 5 tickers
                    ticker = ticker_info["ticker"]
                    count = ticker_info["trade_count"]
                    sentiment = ticker_info["sentiment"]
                    examples.append(f"  - ${ticker}: {count} images posted, {sentiment} sentiment")

                if examples:
                    trade_examples = "Tickers from posted screenshots:\n" + "\n".join(examples[:5])

            # Build operations summary
            operations_summary = ""
            if trade_activity and trade_activity.get("operations"):
                ops = trade_activity["operations"]
                ops_text = ", ".join(
                    [
                        f"{count} {op}"
                        for op, count in sorted(ops.items(), key=lambda x: x[1], reverse=True)
                    ]
                )
                operations_summary = f"Operations: {ops_text}"

            # Build sentiment split
            sentiment_summary = ""
            if trade_activity and trade_activity.get("sentiment_split"):
                sent = trade_activity["sentiment_split"]
                total_sent = sum(sent.values())
                if total_sent > 0:
                    sentiment_summary = f"Sentiment: {sent['bullish']} bullish, {sent['bearish']} bearish, {sent['neutral']} neutral"

            # Create enhanced prompt with vision data
            word_limit = "300 words" if is_weekly else "200 words"
            prompt = f"""You are the voice of a vibrant options trading community.

MARKET CONTEXT:
{market_summary if market_summary else "Not available"}

TEXT DISCUSSIONS:
- {activity['message_count']} messages from {activity['unique_users']} users
- Top mentioned: {trending_summary}

{"ACTUAL TRADES (from posted screenshots):" if trade_examples else ""}
{f"- {trade_activity.get('total_trades', 0)} trades executed" if trade_activity else ""}
{f"- {operations_summary}" if operations_summary else ""}
{f"- {sentiment_summary}" if sentiment_summary else ""}

{trade_examples if trade_examples else ""}

Write a narrative that:
1. **Leads with the most interesting trade/pattern** - Tell the story
2. **Shows ACTUAL positions with specifics** - Reference the real trades posted above
3. **Connects market to behavior** - "VIX spike triggered profit-taking"
4. **Identifies strategy themes** - "Heavy premium selling" or "Wheeling crypto ETFs"
5. **Highlights standout moves** - Notable trades or patterns
6. **Uses numbers and names** - Actual premiums, strikes, P&L from trades above
7. **Maintains energetic insider tone** - Part of the group

VOICE:
- Be specific and data-driven, not vague
- Use trader lingo correctly - just say "STO", "BTO", "BTC", "STC" without explaining them
- If you must reference the full phrase, use the correct terminology:
  * STO = Sell To Open (NEVER "short to open", "short opens", or "short-term options")
  * BTO = Buy To Open
  * BTC = Buy To Close
  * STC = Sell To Close
- Reference usernames respectfully when discussing their trades
- Add insight - WHY these moves?

FORMAT:
- Opening hook (1-2 sentences on defining theme)
- Market context tied to decisions (1 para)
- Trade breakdowns with examples (1-2 paras)
- Strategy/sentiment analysis (1 para)
- Closing perspective (1-2 sentences)

Keep under {word_limit}. Make it worth reading."""

            # Call LLM for narrative (using basic completion, not MCP tools)
            max_tokens = 600 if is_weekly else 400  # More tokens for verbose, specific narratives
            response = self.llm_provider.completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=self.llm_temperature,
            )

            narrative = response.choices[0].message.content.strip()

            # Remove problematic markdown but keep bullets
            narrative = narrative.replace("## ", "").replace("### ", "").replace("#### ", "")
            narrative = narrative.replace("**", "")  # Remove bold
            narrative = narrative.replace("__", "")  # Remove underline

            # Format as digest section with proper paragraph/bullet handling
            lines = ["💭 Community Pulse:"]

            # Split into paragraphs (preserve blank lines)
            paragraphs = narrative.split("\n\n")

            for para_idx, paragraph in enumerate(paragraphs):
                if not paragraph.strip():
                    continue

                # Check if this paragraph contains bullet points
                para_lines = paragraph.split("\n")
                is_bullet_list = any(
                    line.strip().startswith(("- ", "• ", "* ")) for line in para_lines
                )

                if is_bullet_list:
                    # Handle bullet list (including any header lines before bullets)
                    for line in para_lines:
                        line = line.strip()
                        if not line:
                            continue
                        # Convert markdown bullets to consistent format
                        if line.startswith("- ") or line.startswith("* "):
                            line = "• " + line[2:]
                            lines.append(f"  {line}")
                        else:
                            # Non-bullet line (likely a header or intro) - output as-is
                            lines.append(f"  {line}")
                else:
                    # Handle regular paragraph - wrap at 80 chars
                    words = paragraph.split()
                    current_line = "  "
                    for word in words:
                        if len(current_line) + len(word) + 1 > 80:
                            lines.append(current_line)
                            current_line = "  " + word
                        else:
                            current_line += (" " if current_line != "  " else "") + word
                    if current_line.strip():
                        lines.append(current_line)

                # Add blank line between paragraphs (except after last one)
                if para_idx < len(paragraphs) - 1:
                    lines.append("")

            return lines

        except Exception as e:
            logger.warning(f"Error generating LLM narrative: {e}", exc_info=True)
            return []  # Skip narrative on error, don't fail entire digest

    def _trim_to_max_lines(self, lines: list[str], max_lines: int) -> list[str]:
        """
        Trim digest to fit within max line count.

        Removes optional sections in priority order:
        1. LLM narrative (nice-to-have)
        2. Scanner results (supplementary data)
        3. Channel breakdown (weekly only)
        4. Top users (weekly only)

        Args:
            lines: List of digest lines
            max_lines: Maximum number of lines

        Returns:
            Trimmed list of lines
        """
        if len(lines) <= max_lines:
            return lines

        # Try to identify and remove optional sections
        sections_to_try_removing = [
            "💭 Community Pulse:",
            "💰 Top Scanner Picks",
            "📺 Channel Activity:",
            "💬 Most Active Contributors:",
        ]

        result = lines.copy()

        for section_header in sections_to_try_removing:
            if len(result) <= max_lines:
                break

            # Find section
            section_start = None
            section_end = None

            for i, line in enumerate(result):
                if section_header in line:
                    section_start = i
                    # Find next section or end
                    for j in range(i + 1, len(result)):
                        if result[j] and (
                            result[j].startswith("🔥")
                            or result[j].startswith("💰")
                            or result[j].startswith("📈")
                            or result[j].startswith("💬")
                            or result[j].startswith("📺")
                            or result[j].startswith("💭")
                            or result[j].startswith("🌍")
                            or result[j].startswith("=")
                        ):
                            section_end = j
                            break
                    if section_end is None:
                        section_end = len(result) - 1  # Before footer
                    break

            if section_start is not None:
                # Remove section
                result = result[:section_start] + result[section_end:]
                logger.info(f"Trimmed section '{section_header}' to fit within {max_lines} lines")

        # If still too long, truncate with indicator
        if len(result) > max_lines:
            result = result[: max_lines - 1]
            result.append("*[Digest truncated to fit one page]*")
            logger.warning(f"Digest still too long after trimming, truncated to {max_lines} lines")

        return result

    def save_digest(self, digest_text: str, date: datetime | None = None) -> str:
        """
        Save digest to markdown file.

        Args:
            digest_text: The generated digest text
            date: Date of digest (defaults to today)

        Returns:
            Path to saved markdown file
        """
        if date is None:
            date = datetime.now()

        # Create daily_digest directory structure with guild organization
        # Format: daily_digest/guild_<guild_id>/YYYY-MM-DD/
        date_str = date.strftime("%Y-%m-%d")
        guild_folder = f"guild_{self.guild_id}" if self.guild_id else "unknown_guild"
        digest_dir = os.path.join(const.DAILY_DIGEST_DIR, guild_folder, date_str)
        os.makedirs(digest_dir, exist_ok=True)

        # Determine filename
        is_friday = date.weekday() == 4
        digest_type = "weekly" if is_friday else "daily"
        base_filename = f"{digest_type}_digest_{date_str}"

        # Save as markdown
        md_path = os.path.join(digest_dir, f"{base_filename}.md")

        with open(md_path, "w") as f:
            f.write(digest_text)

        logger.info(f"Saved digest to: {md_path}")
        return md_path


def main():
    """Test the daily digest generator with archival."""
    db = Db()
    digest_gen = DailyDigest(db, enable_llm=False)  # Disable LLM for testing

    today = datetime.now()

    print("=== GENERATING DAILY DIGEST ===")
    daily_text = digest_gen._generate_daily_digest(today)
    print(daily_text)
    print("\n" + "=" * 60 + "\n")

    print("=== GENERATING WEEKLY DIGEST ===")
    weekly_text = digest_gen._generate_weekly_digest(today)
    print(weekly_text)
    print("\n" + "=" * 60 + "\n")

    # Test archival
    print("=== SAVING DAILY DIGEST (Markdown) ===")
    md_path = digest_gen.save_digest(daily_text, today)
    print(f"Saved to: {md_path}")
    print()

    print("=== SAVING WEEKLY DIGEST (Markdown) ===")
    # Use a Friday for weekly
    friday = today - timedelta(days=(today.weekday() - 4) % 7)
    weekly_text_friday = digest_gen._generate_weekly_digest(friday)
    md_path_weekly = digest_gen.save_digest(weekly_text_friday, friday)
    print(f"Saved to: {md_path_weekly}")
    print()

    print("=== ARCHIVAL COMPLETE ===")
    print(f"Check {const.DAILY_DIGEST_DIR}/ for saved digests")


if __name__ == "__main__":
    main()
