"""
News Feed Aggregator - Guild-Aware Article Fetcher

Fetches news from Finnhub API and RSS feeds, posts to Discord channels.
Guild-specific news based on community trading activity.
Automatically harvested by bot's on_message handler.

Leverages existing infrastructure:
- guild_channels table for channel configuration
- system_settings table for per-guild settings
- harvested_messages table for storage (via bot)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import discord
import feedparser

import constants as const
from db import Db
from guild_channels import GuildChannels
from providers.market_data_factory import MarketDataFactory
from system_settings import get_settings


logger = logging.getLogger(__name__)


class NewsArticle:
    """Represents a single news article"""

    def __init__(
        self,
        title: str,
        summary: str,
        url: str,
        source: str,
        published: str,
        ticker: str | None = None,
        sentiment: str | None = None,
    ):
        self.title = title
        self.summary = summary
        self.url = url
        self.source = source
        self.published = published
        self.ticker = ticker
        self.sentiment = sentiment

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published": self.published,
            "ticker": self.ticker,
            "sentiment": self.sentiment,
        }


class NewsFeedAggregator:
    """
    Guild-aware news aggregator
    Fetches from RSS + Finnhub and posts to Discord
    (Auto-harvested by bot's on_message handler)
    """

    # Default settings (can be overridden per-guild via SystemSettings)
    DEFAULT_UPDATE_FREQUENCY = 30  # minutes
    DEFAULT_MAX_ARTICLES = 10
    DEFAULT_TICKER_LIMIT = 8
    DEFAULT_ARTICLES_PER_TICKER = 2
    DEFAULT_RSS_ARTICLES_PER_FEED = 3

    # RSS feed sources
    RSS_FEEDS = {
        "cnbc_options": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "benzinga": "https://www.benzinga.com/feed",
        "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    }

    # Keywords for filtering relevant news
    WHEEL_KEYWORDS = [
        "options",
        "put",
        "call",
        "covered call",
        "cash-secured put",
        "theta",
        "premium",
        "wheel strategy",
        "assignment",
        "volatility",
        "earnings",
        "dividend",
        "strike",
        "expiration",
        "implied volatility",
        "options flow",
        "unusual activity",
        "delta",
        "gamma",
        "IV",
    ]

    def __init__(self, db: Db | None = None):
        """
        Initialize news aggregator

        Args:
            db: Database instance (creates new if None)
        """
        self.db = db if db else Db(in_memory=False)
        self.guild_channels = GuildChannels(self.db)
        self.settings = get_settings(self.db)

        # Initialize Finnhub provider
        self.finnhub = None
        try:
            self.finnhub = MarketDataFactory.get_provider("finnhub")
            logger.info("Initialized Finnhub provider for news")
        except Exception as e:
            logger.warning(f"Could not initialize Finnhub: {e}, using RSS only")

        # Track last seen articles per feed (prevent duplicates)
        self.last_seen: dict[str, str] = {}  # feed_name -> article_title

    # ===== Configuration Methods =====

    def is_news_enabled(self, guild_id: int) -> bool:
        """
        Check if guild has news enabled

        Args:
            guild_id: Discord guild ID

        Returns:
            True if guild has at least one news channel configured
        """
        news_channels = self.guild_channels.get_channels_by_category(guild_id, "news")
        return len(news_channels) > 0

    def get_update_frequency(self, guild_id: int) -> int:
        """
        Get update frequency for guild (minutes)

        Args:
            guild_id: Discord guild ID

        Returns:
            Update frequency in minutes
        """
        key = f"news.guild_{guild_id}.update_frequency_minutes"
        result = self.settings.get(key, default=self.DEFAULT_UPDATE_FREQUENCY)
        return int(result) if result is not None else self.DEFAULT_UPDATE_FREQUENCY

    def get_max_articles(self, guild_id: int) -> int:
        """
        Get max articles per update for guild

        Args:
            guild_id: Discord guild ID

        Returns:
            Maximum articles to post per update
        """
        key = f"news.guild_{guild_id}.max_articles"
        result = self.settings.get(key, default=self.DEFAULT_MAX_ARTICLES)
        return int(result) if result is not None else self.DEFAULT_MAX_ARTICLES

    def get_ticker_limit(self, guild_id: int) -> int:
        """
        Get max tickers to track for guild

        Args:
            guild_id: Discord guild ID

        Returns:
            Maximum tickers to fetch news for
        """
        key = f"news.guild_{guild_id}.ticker_limit"
        result = self.settings.get(key, default=self.DEFAULT_TICKER_LIMIT)
        return int(result) if result is not None else self.DEFAULT_TICKER_LIMIT

    def is_finnhub_enabled(self, guild_id: int) -> bool:
        """Check if Finnhub is enabled for guild"""
        key = f"news.guild_{guild_id}.enable_finnhub"
        result = self.settings.get(key, default=True)
        return bool(result) if result is not None else True

    def is_rss_enabled(self, guild_id: int) -> bool:
        """Check if RSS feeds are enabled for guild"""
        key = f"news.guild_{guild_id}.enable_rss"
        result = self.settings.get(key, default=True)
        return bool(result) if result is not None else True

    def get_news_channels(self, guild_id: int) -> list[int]:
        """
        Get news channel IDs for guild (where bot should POST news)

        Args:
            guild_id: Discord guild ID

        Returns:
            List of channel IDs configured as category='news' and subcategory='feed'
        """
        query = """
        SELECT channel_id
        FROM guild_channels
        WHERE guild_id = ? AND category = 'news' AND subcategory = 'feed' AND enabled = 1
        """
        rows = self.db.query_parameterized(query, (guild_id,))
        return [row[0] for row in rows]

    def set_guild_setting(
        self, guild_id: int, setting: str, value: Any, username: str = "admin"
    ) -> None:
        """
        Set a guild-specific news setting

        Args:
            guild_id: Discord guild ID
            setting: Setting name (e.g., 'update_frequency_minutes')
            value: Setting value
            username: User making the change
        """
        key = f"news.guild_{guild_id}.{setting}"
        self.settings.set(key, value, username=username, category="news")
        logger.info(f"Set {key} = {value} for guild {guild_id}")

    # ===== Data Fetching Methods =====

    def get_guild_tickers(self, guild_id: int, days: int = 7, limit: int = 10) -> list[str]:
        """
        Get guild's most traded tickers

        Args:
            guild_id: Discord guild ID
            days: Number of days to look back
            limit: Max tickers to return

        Returns:
            List of ticker symbols sorted by trade count
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime(const.ISO_DATE_FMT)

            query = """
                SELECT symbol, COUNT(*) as count
                FROM trades
                WHERE guild_id = ? AND date >= ? AND symbol IS NOT NULL
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT ?
            """

            results = self.db.query_parameterized(query, (guild_id, cutoff_date, limit))
            tickers = [row[0] for row in results]

            logger.debug(f"Guild {guild_id} tickers (last {days}d): {tickers}")
            return tickers

        except Exception as e:
            logger.error(f"Error fetching guild tickers: {e}")
            return []

    def is_relevant(self, text: str) -> bool:
        """
        Check if article is relevant to wheel traders

        Args:
            text: Article title + summary

        Returns:
            True if contains wheel strategy keywords
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.WHEEL_KEYWORDS)

    def fetch_finnhub_news(
        self, tickers: list[str], count_per_ticker: int = 2
    ) -> list[NewsArticle]:
        """
        Fetch ticker-specific news from Finnhub API

        Args:
            tickers: Ticker symbols
            count_per_ticker: Articles per ticker

        Returns:
            List of NewsArticle objects
        """
        if not self.finnhub or not tickers:
            return []

        articles = []

        for ticker in tickers:
            try:
                news_data = self.finnhub.get_news(ticker, count=count_per_ticker)

                for item in news_data:
                    article = NewsArticle(
                        title=item.get("headline", "No title"),
                        summary=item.get("summary", ""),
                        url=item.get("url", ""),
                        source=item.get("source", "Finnhub"),
                        published=item.get("published", ""),
                        ticker=ticker,
                        sentiment=item.get("sentiment"),
                    )
                    articles.append(article)

                logger.debug(f"Fetched {len(news_data)} Finnhub articles for {ticker}")

            except Exception as e:
                logger.error(f"Error fetching Finnhub news for {ticker}: {e}")

        return articles

    def fetch_rss_feed(
        self, feed_name: str, feed_url: str, max_articles: int = 10
    ) -> list[NewsArticle]:
        """
        Fetch news from single RSS feed

        Args:
            feed_name: Feed name (for tracking)
            feed_url: RSS feed URL
            max_articles: Max articles to fetch

        Returns:
            List of NewsArticle objects
        """
        try:
            feed = feedparser.parse(feed_url)
            articles = []

            for entry in feed.entries[:max_articles]:
                title = entry.get("title", "No title")
                summary = entry.get("summary", entry.get("description", ""))

                # Filter for relevance
                if not self.is_relevant(f"{title} {summary}"):
                    continue

                # Check for duplicates
                if feed_name in self.last_seen:
                    if self.last_seen[feed_name] == title:
                        break  # Stop at last seen

                article = NewsArticle(
                    title=title,
                    summary=summary,
                    url=entry.get("link", ""),
                    source=feed.feed.get("title", feed_name),
                    published=entry.get("published", ""),
                )
                articles.append(article)

            # Update last seen
            if articles:
                self.last_seen[feed_name] = articles[0].title

            logger.debug(f"Fetched {len(articles)} RSS articles from {feed_name}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
            return []

    def fetch_all_rss(self, max_per_feed: int = 5) -> list[NewsArticle]:
        """
        Fetch from all RSS feeds

        Args:
            max_per_feed: Max articles per feed

        Returns:
            Combined list of articles
        """
        all_articles = []

        for feed_name, feed_url in self.RSS_FEEDS.items():
            articles = self.fetch_rss_feed(feed_name, feed_url, max_per_feed)
            all_articles.extend(articles)

        return all_articles

    def fetch_guild_news(self, guild_id: int) -> list[NewsArticle]:
        """
        Fetch all news for a specific guild

        Args:
            guild_id: Discord guild ID

        Returns:
            List of unique articles (deduplicated by URL)
        """
        # Check if news enabled
        if not self.is_news_enabled(guild_id):
            logger.debug(f"News disabled for guild {guild_id} (no news channels configured)")
            return []

        articles = []

        # Get guild's tickers
        ticker_limit = self.get_ticker_limit(guild_id)
        guild_tickers = self.get_guild_tickers(guild_id, days=7, limit=ticker_limit)

        # 1. Finnhub ticker-specific news
        if self.is_finnhub_enabled(guild_id) and self.finnhub and guild_tickers:
            finnhub_articles = self.fetch_finnhub_news(
                guild_tickers, count_per_ticker=self.DEFAULT_ARTICLES_PER_TICKER
            )
            articles.extend(finnhub_articles)
            logger.info(f"Fetched {len(finnhub_articles)} Finnhub articles for guild {guild_id}")

        # 2. RSS general news
        if self.is_rss_enabled(guild_id):
            rss_articles = self.fetch_all_rss(max_per_feed=self.DEFAULT_RSS_ARTICLES_PER_FEED)
            articles.extend(rss_articles)
            logger.info(f"Fetched {len(rss_articles)} RSS articles for guild {guild_id}")

        # Remove duplicates by URL
        seen_urls = set()
        unique_articles = []
        for article in articles:
            if article.url and article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # Limit to max articles
        max_articles = self.get_max_articles(guild_id)
        unique_articles = unique_articles[:max_articles]

        logger.info(f"Total unique articles for guild {guild_id}: {len(unique_articles)}")
        return unique_articles

    # ===== Discord Posting Methods =====

    async def post_article_to_discord(
        self, channel: discord.TextChannel, article: NewsArticle
    ) -> discord.Message | None:
        """
        Post single article to Discord as embed
        (Will be auto-harvested by bot's on_message handler)

        Args:
            channel: Discord channel
            article: NewsArticle to post

        Returns:
            Posted message or None if failed
        """
        try:
            # Create embed
            embed = discord.Embed(
                title=article.title[:256],  # Discord limit
                description=article.summary[:400] + "..."
                if len(article.summary) > 400
                else article.summary,
                url=article.url,
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )

            # Add ticker tag if available
            if article.ticker:
                embed.add_field(name="Ticker", value=f"**{article.ticker}**", inline=True)

            # Add sentiment if available
            if article.sentiment:
                sentiment_emoji = (
                    "📈"
                    if article.sentiment == "positive"
                    else "📉"
                    if article.sentiment == "negative"
                    else "➡️"
                )
                embed.add_field(
                    name="Sentiment",
                    value=f"{sentiment_emoji} {article.sentiment.title()}",
                    inline=True,
                )

            embed.set_footer(text=f"Source: {article.source}")

            msg = await channel.send(embed=embed)
            logger.debug(f"Posted article: {article.title[:50]}...")
            return msg

        except Exception as e:
            logger.error(f"Error posting article to Discord: {e}")
            return None

    async def post_guild_news(self, channel: discord.TextChannel, guild_id: int) -> int:
        """
        Fetch and post guild-specific news to Discord channel

        Args:
            channel: Discord channel (should be configured as 'news' category)
            guild_id: Discord guild ID

        Returns:
            Number of articles posted
        """
        try:
            # Fetch guild-specific news
            articles = self.fetch_guild_news(guild_id)

            if not articles:
                logger.debug(f"No new articles to post for guild {guild_id}")
                return 0

            # Post each article directly (no header)
            posted_count = 0
            for article in articles:
                msg = await self.post_article_to_discord(channel, article)
                if msg:
                    posted_count += 1

            logger.info(f"Posted {posted_count} articles to #{channel.name} for guild {guild_id}")
            return posted_count

        except Exception as e:
            logger.error(f"Error posting guild news: {e}")
            try:
                await channel.send(f"❌ Error fetching news: {e}")
            except Exception:
                pass  # Channel might be inaccessible
            return 0

    async def update_all_guilds(self, bot_client: discord.Client) -> dict[int, int]:
        """
        Update news for all guilds that have news channels configured

        Args:
            bot_client: Discord bot client instance

        Returns:
            Dict mapping guild_id to number of articles posted
        """
        results = {}

        for guild in bot_client.guilds:
            try:
                # Get news channels for this guild
                news_channel_ids = self.get_news_channels(guild.id)

                if not news_channel_ids:
                    continue  # No news channels configured

                # Post to first news channel
                channel = bot_client.get_channel(news_channel_ids[0])
                if not channel:
                    logger.warning(
                        f"News channel {news_channel_ids[0]} not found for guild {guild.id}"
                    )
                    continue

                # Verify it's a text channel
                if not isinstance(channel, discord.TextChannel):
                    logger.warning(
                        f"Channel {news_channel_ids[0]} is not a TextChannel for guild {guild.id}"
                    )
                    continue

                # Post news
                count = await self.post_guild_news(channel, guild.id)
                results[guild.id] = count

            except Exception as e:
                logger.error(f"Error updating news for guild {guild.name} ({guild.id}): {e}")
                results[guild.id] = 0

        logger.info(f"Updated news for {len(results)} guilds")
        return results
