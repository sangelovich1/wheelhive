"""
Messages collection

Manages harvested Discord messages for community knowledge base.
Stores messages with extracted ticker symbols for LLM context augmentation.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

import pandas as pd

from brokers.basetableprocessor import BaseTableProcessor
from db import Db
from message import Message
from providers.market_data_factory import MarketDataFactory
from ticker import Ticker
from tickers import Tickers


logger = logging.getLogger(__name__)


class Messages(BaseTableProcessor):
    """Collection of harvested Discord messages"""

    def __init__(self, db: Db) -> None:
        self.tickers = Tickers(db)  # Initialize before super().__init__ which calls create_table()
        self._invalid_ticker_cache: set[str] = (
            set()
        )  # Cache of known invalid tickers (instance-level)
        super().__init__(db, "harvested_messages")

    def create_table(self) -> None:
        """Create harvested_messages and message_tickers tables if they don't exist"""

        # Main messages table
        messages_query = """
        CREATE TABLE IF NOT EXISTS harvested_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE NOT NULL,
            guild_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            has_attachments BOOLEAN DEFAULT 0,
            attachment_urls TEXT,
            extracted_data TEXT,
            category TEXT DEFAULT 'sentiment',
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at TEXT,
            harvested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sentiment TEXT,
            sentiment_confidence REAL,
            sentiment_reasoning TEXT,
            sentiment_analyzed_at TIMESTAMP
        )
        """
        self.db.create_table(messages_query)

        # Add sentiment columns if they don't exist (check first to avoid warning spam)
        cursor = self.db.query_parameterized("PRAGMA table_info(harvested_messages)")
        existing_columns = {row[1] for row in cursor}

        if "sentiment" not in existing_columns:
            self.db.execute("ALTER TABLE harvested_messages ADD COLUMN sentiment TEXT")
        if "sentiment_confidence" not in existing_columns:
            self.db.execute("ALTER TABLE harvested_messages ADD COLUMN sentiment_confidence REAL")
        if "sentiment_reasoning" not in existing_columns:
            self.db.execute("ALTER TABLE harvested_messages ADD COLUMN sentiment_reasoning TEXT")
        if "sentiment_analyzed_at" not in existing_columns:
            self.db.execute(
                "ALTER TABLE harvested_messages ADD COLUMN sentiment_analyzed_at TIMESTAMP"
            )

        # Tickers extraction table
        tickers_query = """
        CREATE TABLE IF NOT EXISTS message_tickers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            FOREIGN KEY (message_id) REFERENCES harvested_messages(message_id),
            UNIQUE(message_id, ticker)
        )
        """
        self.db.create_table(tickers_query)

        # Per-ticker sentiment table
        ticker_sentiment_query = """
        CREATE TABLE IF NOT EXISTS message_ticker_sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY(message_id) REFERENCES harvested_messages(message_id) ON DELETE CASCADE,
            UNIQUE(message_id, ticker)
        )
        """
        self.db.create_table(ticker_sentiment_query)

        # Create indexes for performance
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_channel_timestamp ON harvested_messages(channel_name, timestamp DESC)"
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON message_tickers(ticker)")
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_guild_channel ON harvested_messages(guild_id, channel_name)"
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_username ON harvested_messages(username)")
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_id ON harvested_messages(message_id)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_ticker_sentiment ON message_ticker_sentiment(ticker, sentiment)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_ticker ON message_ticker_sentiment(message_id)"
        )

    @classmethod
    def headers(cls) -> list:
        return [
            "ID",
            "Message ID",
            "Channel",
            "Username",
            "Content Preview",
            "Timestamp",
            "Attachments",
            "Deleted",
        ]

    def _validate_ticker_via_api(self, ticker: str) -> bool:
        """
        Validate ticker via market data API and auto-add if valid.

        Uses instance-level cache to avoid repeated API calls for known invalid tickers.

        Args:
            ticker: Ticker symbol to validate

        Returns:
            True if ticker is valid (auto-added to database)
        """
        # Check cache first - skip API call if we know it's invalid
        if ticker in self._invalid_ticker_cache:
            logger.debug(f"Skipping cached invalid ticker: {ticker}")
            return False

        try:
            # Query market data with automatic fallback
            info = MarketDataFactory.get_stock_info_with_fallback(ticker)

            # Check if ticker is valid (has basic info)
            if info and info.get("symbol") == ticker:
                # Auto-add to database as community-discovered ticker
                new_ticker = Ticker(
                    ticker=ticker,
                    company_name=info.get("company_name"),
                    exchange="COMMUNITY-AUTO",  # Mark as auto-discovered
                    sector=None,  # Not all providers have sector info
                    is_active=True,
                )
                self.tickers.insert(new_ticker)
                logger.debug(f"Auto-added ticker via API: {ticker} - {new_ticker.company_name}")
                return True

        except Exception as e:
            logger.debug(f"API validation failed for {ticker}: {e}")

        # Cache the invalid ticker to avoid future API calls
        self._invalid_ticker_cache.add(ticker)
        logger.debug(
            f"Cached invalid ticker: {ticker} (cache size: {len(self._invalid_ticker_cache)})"
        )
        return False

    def _extract_tickers(self, content: str) -> set[str]:
        """
        Extract ticker symbols from message content and validate

        Validation process:
        1. Filter out blacklisted words (common false positives)
        2. Check against ticker database (fast)
        3. If not found, validate via yfinance API (auto-add if valid)
        4. Return only validated tickers

        Args:
            content: Message text content

        Returns:
            Set of valid ticker symbols found in message
        """
        # Blacklist of common false positives
        # Single letters, months, option terminology, common words
        blacklist = {
            # Single letters (except known single-letter tickers)
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
            "T",
            "U",
            "V",
            "W",
            "X",
            "Y",
            "Z",
            # Months
            "JAN",
            "FEB",
            "MAR",
            "APR",
            "MAY",
            "JUN",
            "JUL",
            "AUG",
            "SEP",
            "OCT",
            "NOV",
            "DEC",
            # Option terminology
            "PUT",
            "PUTS",
            "CALL",
            "CALLS",
            "CC",
            "CS",
            "CSP",
            "BTO",
            "STO",
            "BTC",
            "STC",
            "ITM",
            "OTM",
            "ATM",
            "DTE",
            "IV",
            "PM",
            "AM",
            # Common words
            "AND",
            "OR",
            "THE",
            "FOR",
            "AT",
            "TO",
            "IN",
            "ON",
            "IS",
            "IT",
            "AS",
            "BY",
            "OF",
            "AN",
            "MY",
            "SO",
            "IF",
            "UP",
            "NO",
            "GO",
            "DO",
            "ME",
            "WE",
            "HE",
            "BE",
            "ALL",
            "OUT",
            "NEW",
            "OLD",
            "BIG",
            "TOP",
            "HOT",
            "LOW",
            "HIGH",
            "WEEK",
            "EACH",
            # Trading terms (excluding BULL which is a real ticker)
            "LONG",
            "SHORT",
            "ROLL",
            "WIN",
            "LOSS",
            "GAIN",
            "BEAR",
            # Tech/service acronyms (not tickers)
            "AWS",
            "API",
            "SDK",
            "IDE",
            "SQL",
            "HTTP",
            "HTML",
            "CSS",
            "JSON",
            "XML",
            "REST",
            "SOAP",
            "SMTP",
            "FTP",
            "SSH",
            "VPN",
            "DNS",
            "IP",
            "TCP",
            "UDP",
            # Common acronyms
            "USA",
            "EU",
            "UK",
            "US",
            "CA",
            "TX",
            "NY",
            "FL",
            "IL",
            "OH",
            "FAQ",
            "ASAP",
            "RSVP",
            "ETA",
            "FYI",
            "LOL",
            "OMG",
            "WTF",
            "BTW",
            "GM",
            "GN",
            "GL",
            "GG",
            "HQ",
            "HR",
            "PR",
            "IR",
            # Common false positives from Discord
            "GOT",
            "NEED",
            "WHEN",
            "LIKE",
            "JUST",
            "ABOUT",
            "FROM",
            "WITH",
            "THAT",
            "BEEN",
            "HAVE",
            "WILL",
            "THEY",
            "THEM",
            "THAN",
            "THEN",
            "THIS",
            "WHAT",
            "YEAH",
            "WELL",
            "STILL",
            "EVEN",
            "MUCH",
            "SOME",
            "BACK",
            "ALSO",
            "ONLY",
        }

        # Regex pattern for potential ticker symbols (2-5 uppercase letters)
        # Changed from 1-5 to 2-5 to reduce single-letter false positives
        pattern = r"\b[A-Z]{2,5}\b"

        potential_tickers = set(re.findall(pattern, content))

        # Remove blacklisted terms
        potential_tickers = potential_tickers - blacklist

        # Filter to only valid tickers
        valid_tickers = set()
        for ticker in potential_tickers:
            # First check our database (fast)
            if self.tickers.is_valid_ticker(ticker):
                valid_tickers.add(ticker)
                logger.debug(f"Found valid ticker (DB): {ticker}")
            # If not in database, validate via API and auto-add
            elif self._validate_ticker_via_api(ticker):
                valid_tickers.add(ticker)
                logger.debug(f"Found valid ticker (API): {ticker}")
            else:
                logger.debug(f"Skipping invalid ticker: {ticker}")

        return valid_tickers

    def _should_skip_ocr(self, message: Message) -> bool:
        """
        Determine if OCR should be skipped based on message content

        Args:
            message: Message object

        Returns:
            True if message likely contains non-trading content
        """
        content = message.content.lower().strip()

        # Blacklist for meme/reaction content
        blacklist = {
            "lol",
            "lmao",
            "lmfao",
            "rotfl",
            "rofl",
            "haha",
            "hahaha",
            "dead",
            "ded",
            "fr fr",
            "ngl",
            "tbh",
            "imo",
            "imho",
            "pov:",
            "nobody:",
            "literally nobody",
            "when you",
            "be like",
            "me when",
            "mood",
            "vibes",
            "same energy",
            "nice",
            "cool",
            "sweet",
            "dope",
            "based",
            "cringe",
        }

        # Skip if no text content (image might still have value)
        if not content:
            return False

        # Skip if message is very short and only contains blacklisted phrases
        if len(content) < 50:
            for blacklisted in blacklist:
                if blacklisted in content:
                    return True

        # Skip if message is ONLY a URL (likely a meme share)
        if content.startswith(("http://", "https://")) and " " not in content:
            return True

        # Skip if message has no actual words (just emoji)
        word_count = len([c for c in content if c.isalnum() or c.isspace()])
        if word_count < 5:
            return True

        return False

    def _is_blacklisted_ocr_text(self, ocr_text: str) -> bool:
        """
        Check if OCR text should be discarded based on blacklist

        Args:
            ocr_text: Extracted text from OCR

        Returns:
            True if text contains blacklisted content
        """
        text = ocr_text.lower()

        # Minimum length - very short text is probably not useful
        if len(text) < 15:
            return True

        # OCR blacklist
        blacklist = {
            # Social media watermarks
            "twitter.com",
            "instagram.com",
            "facebook.com",
            "tiktok.com",
            "reddit.com",
            "discord.gg",
            # Meme sites
            "imgflip",
            "memegenerator",
            "quickmeme",
            "makeameme",
            # Spam indicators
            "click here to",
            "limited time offer",
            "act now",
            "verify your account",
            "unusual activity detected",
            # UI elements
            "share",
            "like",
            "subscribe",
            "follow me",
        }

        # Check against blacklist
        for blacklisted in blacklist:
            if blacklisted in text:
                logger.debug(f"OCR text blacklisted: contains '{blacklisted}'")
                return True

        # If text is mostly non-ASCII (emoji, special chars), probably not useful
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
        if ascii_ratio < 0.7:
            logger.debug(f"OCR text blacklisted: low ASCII ratio ({ascii_ratio:.2f})")
            return True

        return False

    def insert(self, message: Message, extract_tickers: bool = True) -> bool:  # type: ignore[override]
        """
        Insert a message into the database

        Args:
            message: Message object to insert
            extract_tickers: Whether to extract and store tickers

        Returns:
            True if successful, False if message already exists
        """
        # Check if message already exists
        existing = self.db.query_parameterized(
            "SELECT 1 FROM harvested_messages WHERE message_id = ?", (message.message_id,)
        )

        if existing:
            logger.debug(f"Message {message.message_id} already exists, skipping")
            return False

        # Note: Image processing is now done separately via --process-images flag
        # This allows us to apply Pydantic validators during parsing
        # Legacy OCR code has been removed in favor of vision_strategy.py

        # Insert message
        query = """
        INSERT INTO harvested_messages
        (message_id, guild_id, channel_name, username, content, timestamp,
         has_attachments, attachment_urls, extracted_data, category, is_deleted, deleted_at, harvested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.db.execute(query, message.to_tuple())

        # Condensed log message with key metadata
        content_preview = (
            message.content[:50] + "..." if len(message.content) > 50 else message.content
        )
        logger.debug(
            f'Harvested: id={message.message_id} channel={message.channel_name} user={message.username} content="{content_preview}"'
        )

        # Extract and store tickers if enabled
        if extract_tickers:
            tickers = self._extract_tickers(message.content)
            if tickers:
                self._insert_tickers(message.message_id, tickers)

        return True

    def _insert_tickers(self, message_id: int, tickers: set[str]) -> int:
        """
        Insert extracted tickers for a message

        Args:
            message_id: Discord message ID
            tickers: Set of ticker symbols

        Returns:
            Number of tickers inserted
        """
        query = """
        INSERT OR IGNORE INTO message_tickers (message_id, ticker)
        VALUES (?, ?)
        """

        count = 0
        for ticker in tickers:
            self.db.execute(query, (message_id, ticker))
            count += 1

        if count > 0:
            ticker_list = ", ".join(sorted(tickers))
            logger.debug(f"Extracted tickers for message {message_id}: {ticker_list}")

        return count

    def mark_deleted(self, message_id: int) -> bool:
        """
        Mark a message as deleted

        Args:
            message_id: Discord message ID

        Returns:
            True if message was found and marked deleted
        """
        deleted_at = datetime.utcnow().isoformat()

        query = """
        UPDATE harvested_messages
        SET is_deleted = 1, deleted_at = ?
        WHERE message_id = ?
        """

        self.db.execute(query, (deleted_at, message_id))

        # Check if update affected any rows
        result = self.db.query_parameterized(
            "SELECT 1 FROM harvested_messages WHERE message_id = ? AND is_deleted = 1",
            (message_id,),
        )

        success = len(result) > 0
        if success:
            logger.info(f"Marked message {message_id} as deleted")

        return success

    def get_message(self, message_id: int) -> Message | None:
        """
        Get a single message by ID.

        Args:
            message_id: Discord message ID

        Returns:
            Message object or None if not found
        """
        query = """
        SELECT message_id, guild_id, channel_name, username, content,
               timestamp, has_attachments, attachment_urls, extracted_data,
               is_deleted, deleted_at, harvested_at, category,
               sentiment, sentiment_confidence, sentiment_reasoning, sentiment_analyzed_at
        FROM harvested_messages
        WHERE message_id = ?
        """

        results = self.db.query_parameterized(query, (message_id,))

        if results:
            return self._rows_to_messages(results)[0]
        return None

    def update_sentiment(
        self, message_id: int, sentiment: str, confidence: float, reasoning: str
    ) -> bool:
        """
        Update sentiment analysis results for a message.

        NOTE: This method NO LONGER updates tickers. Tickers are now extracted
        by calling update_tickers() after sentiment analysis completes.
        This prevents LLM hallucination from polluting ticker data.

        Args:
            message_id: Discord message ID
            sentiment: Sentiment label (bullish/bearish/neutral)
            confidence: Confidence score (0.0-1.0)
            reasoning: LLM reasoning for the sentiment

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Update sentiment fields only
            cursor = self.db.execute(
                """
                UPDATE harvested_messages
                SET sentiment = ?,
                    sentiment_confidence = ?,
                    sentiment_reasoning = ?,
                    sentiment_analyzed_at = CURRENT_TIMESTAMP
                WHERE message_id = ?
                """,
                (sentiment, confidence, reasoning, message_id),
            )

            # Tickers are now handled by update_tickers() method
            # which extracts from actual message data, not LLM output

            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update sentiment for message {message_id}: {e}", exc_info=True)
            return False

    def get_by_ticker(
        self, ticker: str, limit: int = 50, guild_id: int | None = None
    ) -> list[Message]:
        """
        Get messages mentioning a specific ticker

        Args:
            ticker: Ticker symbol
            limit: Maximum messages to return
            guild_id: Filter by Discord guild/server ID (None for all guilds)

        Returns:
            List of Message objects
        """
        where_parts = ["t.ticker = ?"]
        params: list[Any] = [ticker.upper()]

        if guild_id is not None:
            where_parts.append("m.guild_id = ?")
            params.append(guild_id)

        where_clause = " AND ".join(where_parts)

        query = f"""
        SELECT m.message_id, m.guild_id, m.channel_name, m.username, m.content,
               m.timestamp, m.has_attachments, m.attachment_urls, m.extracted_data,
               m.is_deleted, m.deleted_at, m.harvested_at
        FROM harvested_messages m
        JOIN message_tickers t ON m.message_id = t.message_id
        WHERE {where_clause}
        ORDER BY m.timestamp DESC
        LIMIT ?
        """

        params.append(limit)
        results = self.db.query_parameterized(query, tuple(params))

        return self._rows_to_messages(results)

    def get_by_user(
        self, username: str, limit: int = 50, include_deleted: bool = False
    ) -> list[Message]:
        """
        Get messages from a specific user

        Args:
            username: Discord username
            limit: Maximum messages to return
            include_deleted: Whether to include deleted messages

        Returns:
            List of Message objects ordered by timestamp (most recent first)
        """
        where_parts = ["username = ?"]
        params: list[Any] = [username]

        if not include_deleted:
            where_parts.append("is_deleted = 0")

        where_clause = " AND ".join(where_parts)

        query = f"""
        SELECT message_id, guild_id, channel_name, username, content,
               timestamp, has_attachments, attachment_urls, extracted_data,
               is_deleted, deleted_at, harvested_at
        FROM harvested_messages
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
        """

        params.append(limit)
        results = self.db.query_parameterized(query, tuple(params))

        return self._rows_to_messages(results)

    def get_recent(
        self,
        channel_name: str | None = None,
        limit: int = 50,
        include_deleted: bool = False,
        guild_id: int | None = None,
        category: str | None = None,
    ) -> list[Message]:
        """
        Get recent messages

        Args:
            channel_name: Filter by channel (None for all channels)
            limit: Maximum messages to return
            include_deleted: Whether to include deleted messages
            guild_id: Filter by Discord guild/server ID (None for all guilds)
            category: Filter by message category ('sentiment' or 'news')

        Returns:
            List of Message objects
        """
        where_parts = []
        params: list[Any] = []

        if guild_id is not None:
            where_parts.append("guild_id = ?")
            params.append(guild_id)

        if channel_name:
            where_parts.append("channel_name = ?")
            params.append(channel_name)

        if category:
            where_parts.append("category = ?")
            params.append(category)

        if not include_deleted:
            where_parts.append("is_deleted = 0")

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        query = f"""
        SELECT message_id, guild_id, channel_name, username, content,
               timestamp, has_attachments, attachment_urls, extracted_data,
               is_deleted, deleted_at, harvested_at, category,
               sentiment, sentiment_confidence, sentiment_reasoning, sentiment_analyzed_at
        FROM harvested_messages
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ?
        """

        params.append(limit)
        results = self.db.query_parameterized(query, tuple(params))

        return self._rows_to_messages(results)

    def _rows_to_messages(self, rows: list[tuple]) -> list[Message]:
        """Convert database rows to Message objects"""
        messages = []
        for row in rows:
            # Parse attachment_urls JSON
            attachment_urls = json.loads(row[7]) if row[7] else []

            message = Message(
                message_id=row[0],
                guild_id=row[1],
                channel_name=row[2],
                username=row[3],
                content=row[4],
                timestamp=row[5],
                attachment_urls=attachment_urls,
                extracted_data=row[8],  # JSON string stored as-is
                is_deleted=bool(row[9]),
                deleted_at=row[10],
                harvested_at=row[11],
                category=row[12] if len(row) > 12 else "sentiment",
                sentiment=row[13] if len(row) > 13 else None,
                sentiment_confidence=row[14] if len(row) > 14 else None,
                sentiment_reasoning=row[15] if len(row) > 15 else None,
                sentiment_analyzed_at=row[16] if len(row) > 16 else None,
            )

            # Fetch tickers for this message
            ticker_results = self.db.query_parameterized(
                "SELECT ticker FROM message_tickers WHERE message_id = ?", (message.message_id,)
            )
            message.tickers = [row[0] for row in ticker_results]

            messages.append(message)

        return messages

    def count(self, channel_name: str | None = None, include_deleted: bool = False) -> int:
        """
        Count messages in database

        Args:
            channel_name: Filter by channel
            include_deleted: Include deleted messages

        Returns:
            Count of messages
        """
        where_parts = []
        params = []

        if channel_name:
            where_parts.append("channel_name = ?")
            params.append(channel_name)

        if not include_deleted:
            where_parts.append("is_deleted = 0")

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        query = f"SELECT COUNT(*) FROM harvested_messages {where_clause}"

        if params:
            result = self.db.query_parameterized(query, tuple(params))
        else:
            result = self.db.query(query, None)

        return result[0][0] if result else 0

    def count_by_ticker(self, ticker: str) -> int:
        """
        Count messages mentioning a ticker

        Args:
            ticker: Ticker symbol

        Returns:
            Count of messages
        """
        query = """
        SELECT COUNT(DISTINCT message_id)
        FROM message_tickers
        WHERE ticker = ?
        """

        result = self.db.query_parameterized(query, (ticker.upper(),))
        return result[0][0] if result else 0

    def count_by_user(self, username: str, include_deleted: bool = False) -> int:
        """
        Count messages from a specific user

        Args:
            username: Discord username
            include_deleted: Include deleted messages

        Returns:
            Count of messages
        """
        where_parts = ["username = ?"]
        params = [username]

        if not include_deleted:
            where_parts.append("is_deleted = 0")

        where_clause = " AND ".join(where_parts)

        query = f"SELECT COUNT(*) FROM harvested_messages WHERE {where_clause}"

        result = self.db.query_parameterized(query, tuple(params))
        return result[0][0] if result else 0

    def get_channel_stats(self) -> dict:
        """
        Get statistics by channel

        Returns:
            Dictionary with channel statistics
        """
        query = """
        SELECT channel_name,
               COUNT(*) as total,
               SUM(CASE WHEN is_deleted = 0 THEN 1 ELSE 0 END) as active,
               SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END) as deleted
        FROM harvested_messages
        GROUP BY channel_name
        ORDER BY total DESC
        """

        results = self.db.query(query, None)

        stats = {}
        for row in results:
            stats[row[0]] = {"total": row[1], "active": row[2], "deleted": row[3]}

        return stats

    def get_ticker_stats(self, guild_id: int, limit: int = 20) -> list[tuple]:
        """
        Get top mentioned tickers

        Args:
            guild_id: Guild ID to filter by (required for data isolation)
            limit: Number of tickers to return

        Returns:
            List of (ticker, count) tuples
        """
        query = f"""
        SELECT mt.ticker, COUNT(*) as mentions
        FROM message_tickers mt
        JOIN harvested_messages hm ON mt.message_id = hm.message_id
        JOIN valid_tickers vt ON mt.ticker = vt.ticker
        LEFT JOIN ticker_blacklist bl ON mt.ticker = bl.term
        WHERE hm.guild_id = ?
          AND bl.term IS NULL
        GROUP BY mt.ticker
        ORDER BY mentions DESC
        LIMIT {limit}
        """
        return self.db.query_parameterized(query, (guild_id,))

    def get_ticker_stats_as_dict(self, guild_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get top mentioned tickers as list of dictionaries.

        Follows the standardized data export pattern for JSON/MCP serialization.

        Args:
            guild_id: Guild ID to filter by (required for data isolation)
            limit: Number of tickers to return

        Returns:
            List of dicts with 'ticker' and 'mentions' keys
            Example: [{"ticker": "MSTU", "mentions": 45}, {"ticker": "TSLL", "mentions": 32}]
        """
        ticker_stats = self.get_ticker_stats(guild_id, limit)
        return [{"ticker": ticker, "mentions": count} for ticker, count in ticker_stats]

    def get_user_stats(self, username: str, limit: int = 20) -> dict:
        """
        Get statistics for a specific user

        Args:
            username: Discord username
            limit: Number of top tickers to include

        Returns:
            Dictionary with user statistics including:
            - total_messages: Total message count
            - active_messages: Non-deleted message count
            - deleted_messages: Deleted message count
            - top_tickers: List of (ticker, count) tuples
            - channels: List of (channel_name, count) tuples
        """
        # Get message counts
        total_query = "SELECT COUNT(*) FROM harvested_messages WHERE username = ?"
        total_result = self.db.query_parameterized(total_query, (username,))
        total_messages = total_result[0][0] if total_result else 0

        active_query = (
            "SELECT COUNT(*) FROM harvested_messages WHERE username = ? AND is_deleted = 0"
        )
        active_result = self.db.query_parameterized(active_query, (username,))
        active_messages = active_result[0][0] if active_result else 0

        deleted_messages = total_messages - active_messages

        # Get top tickers mentioned by user
        tickers_query = f"""
        SELECT t.ticker, COUNT(*) as mentions
        FROM message_tickers t
        JOIN harvested_messages m ON t.message_id = m.message_id
        WHERE m.username = ?
        GROUP BY t.ticker
        ORDER BY mentions DESC
        LIMIT {limit}
        """
        top_tickers = self.db.query_parameterized(tickers_query, (username,))

        # Get channels user has posted in
        channels_query = """
        SELECT channel_name, COUNT(*) as posts
        FROM harvested_messages
        WHERE username = ?
        GROUP BY channel_name
        ORDER BY posts DESC
        """
        channels = self.db.query_parameterized(channels_query, (username,))

        return {
            "username": username,
            "total_messages": total_messages,
            "active_messages": active_messages,
            "deleted_messages": deleted_messages,
            "top_tickers": top_tickers,
            "channels": channels,
        }

    def as_df(
        self,
        channel_name: str | None = None,  # type: ignore[override]
        limit: int | None = None,
        include_deleted: bool = False,
    ) -> pd.DataFrame:
        """
        Get messages as DataFrame

        Args:
            channel_name: Filter by channel
            limit: Optional row limit
            include_deleted: Include deleted messages

        Returns:
            DataFrame of messages
        """
        where_parts = []
        params = []

        if channel_name:
            where_parts.append("channel_name = ?")
            params.append(channel_name)

        if not include_deleted:
            where_parts.append("is_deleted = 0")

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"""
        SELECT id, message_id, channel_name, username,
               SUBSTR(content, 1, 100) as content_preview,
               timestamp, has_attachments, is_deleted
        FROM harvested_messages
        {where_clause}
        ORDER BY timestamp DESC
        {limit_clause}
        """

        if params:
            results = self.db.query_parameterized(query, tuple(params))
        else:
            results = self.db.query(query, None)

        if not results:
            return pd.DataFrame(columns=self.headers())

        df = pd.DataFrame(results, columns=self.headers())
        return df

    def update_extracted_data(self, message_id: int, extracted_data: dict) -> bool:
        """
        Update extracted_data for a message (called by background vision workers)

        This method is called asynchronously by the ImageProcessingQueue workers
        after vision analysis completes. It stores the structured extraction
        results in the database.

        Args:
            message_id: Discord message ID to update
            extracted_data: Dictionary with vision analysis results:
                {
                    'raw_text': str,
                    'image_type': 'trade_execution' | 'account_summary' | 'technical_analysis' | 'other' | 'error',
                    'trades': [...],
                    'tickers': ['AAPL', 'TSLA'],
                    'sentiment': 'bullish' | 'bearish' | 'neutral',
                    'account_value': float (optional),
                    'daily_pnl': float (optional)
                }

        Returns:
            True if updated successfully, False if message not found

        Note:
            This method is thread-safe for SQLite (called from async workers)
        """
        try:
            # Serialize to JSON
            data_json = json.dumps(extracted_data)

            # Update database using db.execute()
            cursor = self.db.execute(
                "UPDATE harvested_messages SET extracted_data = ? WHERE message_id = ?",
                (data_json, message_id),
            )

            # Check if update succeeded
            if cursor.rowcount > 0:
                logger.debug(f"Updated extracted_data for message {message_id}")
                return True
            logger.warning(f"Message {message_id} not found for update")
            return False

        except Exception as e:
            logger.error(
                f"Error updating extracted_data for message {message_id}: {e}", exc_info=True
            )
            return False

    def get_trending_tickers(
        self,
        days: int = 7,
        min_mentions: int = 3,
        limit: int = 20,
        noise_words: list[str] | None = None,
        guild_id: int | None = None,
    ) -> list[tuple]:
        """
        Get trending tickers from message_tickers table (validated, normalized)

        Args:
            days: Number of days to analyze (default: 7)
            min_mentions: Minimum mentions to show (default: 3)
            limit: Maximum number of tickers to return (default: 20)
            noise_words: Deprecated (kept for compatibility, filtering now via ticker_blacklist)
            guild_id: Optional guild ID to filter by (default: None = all guilds)

        Returns:
            List of (ticker, mentions, active_days) tuples, sorted by mentions DESC
        """
        # NOTE: noise_words parameter is deprecated - filtering now handled by ticker_blacklist
        # and ticker validation during message processing. Kept for backward compatibility.

        guild_filter = f"AND hm.guild_id = {guild_id}" if guild_id else ""

        query = f"""
        SELECT
            mt.ticker,
            COUNT(DISTINCT mt.message_id) as mentions,
            COUNT(DISTINCT DATE(hm.timestamp)) as active_days
        FROM message_tickers mt
        JOIN harvested_messages hm ON mt.message_id = hm.message_id
        WHERE hm.timestamp >= date('now', '-{days} days')
        {guild_filter}
        GROUP BY mt.ticker
        HAVING mentions >= {min_mentions}
        ORDER BY mentions DESC, active_days DESC
        LIMIT {limit}
        """

        return self.db.query(query)

    def get_ticker_sentiment_stats(self, ticker: str) -> dict:
        """
        Get sentiment analysis statistics for a specific ticker from images

        Args:
            ticker: Stock symbol (case-insensitive)

        Returns:
            Dict with sentiment breakdown and recent messages:
            {
                'ticker': str,
                'total_mentions': int,
                'sentiment_breakdown': {'bullish': int, 'bearish': int, 'neutral': int},
                'avg_confidence': float,
                'recent_messages': List[dict]
            }
        """
        ticker = ticker.upper()

        # Query messages mentioning this ticker from vision analysis
        query = """
        SELECT
            message_id,
            timestamp,
            username,
            channel_name,
            json_extract(extracted_data, '$.sentiment') as sentiment,
            json_extract(extracted_data, '$.image_type') as image_type,
            json_extract(extracted_data, '$.trades') as trades_json
        FROM harvested_messages
        WHERE extracted_data IS NOT NULL
        AND json_extract(extracted_data, '$.image_type') = 'trade_execution'
        AND EXISTS (
            SELECT 1 FROM json_each(json_extract(extracted_data, '$.tickers'))
            WHERE value = ?
        )
        ORDER BY timestamp DESC
        LIMIT 50
        """

        rows = self.db.query_parameterized(query, (ticker,))

        if not rows:
            return {
                "ticker": ticker,
                "total_mentions": 0,
                "sentiment_breakdown": {"bullish": 0, "bearish": 0, "neutral": 0},
                "avg_confidence": 0.0,
                "recent_messages": [],
            }

        # Aggregate sentiment
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        recent_messages = []

        for row in rows:
            message_id, timestamp, username, channel_name, sentiment, image_type, trades_json = row

            if sentiment:
                sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

            # Parse trades to find ticker-specific info
            trades = json.loads(trades_json) if trades_json else []
            ticker_trades = [t for t in trades if t.get("ticker") == ticker]

            recent_messages.append(
                {
                    "message_id": message_id,
                    "timestamp": timestamp,
                    "username": username,
                    "channel_name": channel_name,
                    "sentiment": sentiment,
                    "trades": ticker_trades,
                }
            )

        return {
            "ticker": ticker,
            "total_mentions": len(rows),
            "sentiment_breakdown": sentiment_counts,
            "avg_confidence": 0.0,  # Not tracked in extracted_data currently
            "recent_messages": recent_messages,
        }

    def get_vision_processing_stats(self) -> dict:
        """
        Get statistics about vision processing (OCR/analysis success rates)

        Returns:
            Dict with vision processing statistics:
            {
                'total_messages': int,
                'messages_with_images': int,
                'messages_processed': int,
                'success_rate': float,
                'avg_processing_time_ms': float,
                'image_types': {'trade_execution': int, 'account_summary': int, ...},
                'models_used': {'claude-3-5-haiku': int, ...}
            }
        """
        # Total messages
        total_query = "SELECT COUNT(*) FROM harvested_messages"
        total_messages = self.db.query(total_query)[0][0]

        # Messages with attachments
        with_images_query = "SELECT COUNT(*) FROM harvested_messages WHERE has_attachments = 1"
        messages_with_images = self.db.query(with_images_query)[0][0]

        # Messages successfully processed (have extracted_data)
        processed_query = "SELECT COUNT(*) FROM harvested_messages WHERE extracted_data IS NOT NULL"
        messages_processed = self.db.query(processed_query)[0][0]

        # Success rate
        success_rate = (
            (messages_processed / messages_with_images * 100) if messages_with_images > 0 else 0.0
        )

        # Average processing time (from extraction_metadata)
        avg_time_query = """
        SELECT AVG(CAST(json_extract(extracted_data, '$.extraction_metadata.processing_time_ms') AS REAL))
        FROM harvested_messages
        WHERE extracted_data IS NOT NULL
        AND json_extract(extracted_data, '$.extraction_metadata.processing_time_ms') IS NOT NULL
        """
        avg_time_result = self.db.query(avg_time_query)[0][0]
        avg_processing_time_ms = float(avg_time_result) if avg_time_result else 0.0

        # Image types breakdown
        image_types_query = """
        SELECT
            json_extract(extracted_data, '$.image_type') as image_type,
            COUNT(*) as count
        FROM harvested_messages
        WHERE extracted_data IS NOT NULL
        GROUP BY image_type
        """
        image_types_rows = self.db.query(image_types_query)
        image_types = {row[0]: row[1] for row in image_types_rows if row[0]}

        # Models used
        models_query = """
        SELECT
            json_extract(extracted_data, '$.extraction_metadata.model_used') as model,
            COUNT(*) as count
        FROM harvested_messages
        WHERE extracted_data IS NOT NULL
        AND json_extract(extracted_data, '$.extraction_metadata.model_used') IS NOT NULL
        GROUP BY model
        """
        models_rows = self.db.query(models_query)
        models_used = {row[0]: row[1] for row in models_rows if row[0]}

        return {
            "total_messages": total_messages,
            "messages_with_images": messages_with_images,
            "messages_processed": messages_processed,
            "success_rate": success_rate,
            "avg_processing_time_ms": avg_processing_time_ms,
            "image_types": image_types,
            "models_used": models_used,
        }

    def get_overall_stats(self) -> dict:
        """
        Get comprehensive statistics about harvested messages

        Returns:
            Dict with overall statistics:
            {
                'total_messages': int,
                'messages_by_channel': dict,
                'messages_by_category': dict,
                'messages_with_sentiment': int,
                'sentiment_breakdown': dict,
                'top_tickers': List[tuple],
                'top_users': List[tuple],
                'date_range': {'oldest': str, 'newest': str}
            }
        """
        # Total messages
        total_query = "SELECT COUNT(*) FROM harvested_messages WHERE is_deleted = 0"
        total_messages = self.db.query(total_query)[0][0]

        # Messages by channel
        channel_query = """
        SELECT channel_name, COUNT(*) as count
        FROM harvested_messages
        WHERE is_deleted = 0
        GROUP BY channel_name
        ORDER BY count DESC
        """
        messages_by_channel = {row[0]: row[1] for row in self.db.query(channel_query)}

        # Messages by category
        category_query = """
        SELECT category, COUNT(*) as count
        FROM harvested_messages
        WHERE is_deleted = 0
        GROUP BY category
        ORDER BY count DESC
        """
        messages_by_category = {row[0]: row[1] for row in self.db.query(category_query)}

        # Messages with sentiment
        sentiment_count_query = (
            "SELECT COUNT(*) FROM harvested_messages WHERE sentiment IS NOT NULL"
        )
        messages_with_sentiment = self.db.query(sentiment_count_query)[0][0]

        # Sentiment breakdown
        sentiment_query = """
        SELECT sentiment, COUNT(*) as count
        FROM harvested_messages
        WHERE sentiment IS NOT NULL
        GROUP BY sentiment
        ORDER BY count DESC
        """
        sentiment_breakdown = {row[0]: row[1] for row in self.db.query(sentiment_query)}

        # Top tickers (from message_tickers table)
        top_tickers_query = """
        SELECT ticker, COUNT(*) as mentions
        FROM message_tickers
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT 10
        """
        top_tickers = self.db.query(top_tickers_query)

        # Top users
        top_users_query = """
        SELECT username, COUNT(*) as message_count
        FROM harvested_messages
        WHERE is_deleted = 0
        GROUP BY username
        ORDER BY message_count DESC
        LIMIT 10
        """
        top_users = self.db.query(top_users_query)

        # Date range
        date_range_query = """
        SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
        FROM harvested_messages
        WHERE is_deleted = 0
        """
        date_range_row = self.db.query(date_range_query)[0]
        date_range = {"oldest": date_range_row[0], "newest": date_range_row[1]}

        return {
            "total_messages": total_messages,
            "messages_by_channel": messages_by_channel,
            "messages_by_category": messages_by_category,
            "messages_with_sentiment": messages_with_sentiment,
            "sentiment_breakdown": sentiment_breakdown,
            "top_tickers": top_tickers,
            "top_users": top_users,
            "date_range": date_range,
        }

    def get_message_tickers(self, message_id: int) -> list[str]:
        """
        Get list of tickers associated with a message from message_tickers table.

        This returns Stage 1 ticker extraction (text-based regex + validation).
        Does not include tickers from vision analysis (those are in extracted_data).

        Args:
            message_id: Discord message ID

        Returns:
            List of ticker symbols (e.g., ['AAPL', 'TSLA'])
        """
        query = """
        SELECT ticker
        FROM message_tickers
        WHERE message_id = ?
        ORDER BY ticker
        """

        results = self.db.query_parameterized(query, (message_id,))

        if not results:
            return []

        return [row[0] for row in results]

    def update_tickers(self, message_id: int) -> bool:
        """
        Update tickers for a message by extracting from ALL available data.

        This should be called AFTER:
        - Vision extraction completes (extracted_data updated)
        - Sentiment analysis completes (sentiment fields updated)

        The message entity knows how to extract tickers from all its data sources.

        Args:
            message_id: Discord message ID

        Returns:
            True if tickers updated successfully
        """
        from ticker_validator import TickerValidator

        try:
            # Get message with all current data
            msg = self.get_message(message_id)
            if not msg:
                logger.warning(f"Message {message_id} not found for ticker update")
                return False

            # Get validator singleton
            validator = TickerValidator.get_instance(self.db)

            # Extract tickers from all sources (message knows how)
            tickers = msg.get_all_tickers(validator)

            # REPLACE tickers in database (message has complete data now)
            # Delete existing associations
            self.db.execute("DELETE FROM message_tickers WHERE message_id = ?", (message_id,))

            # Insert new associations
            inserted = 0
            for ticker in tickers:
                self.db.execute(
                    "INSERT OR IGNORE INTO message_tickers (message_id, ticker) VALUES (?, ?)",
                    (message_id, ticker),
                )
                inserted += 1

            if inserted > 0:
                ticker_list = ", ".join(sorted(tickers))
                logger.info(f"Updated tickers for message {message_id}: {ticker_list}")
            else:
                logger.debug(f"No tickers found for message {message_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to update tickers for message {message_id}: {e}", exc_info=True)
            return False
