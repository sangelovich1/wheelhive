"""
Async wrappers for Messages database operations

This module provides async wrappers around the synchronous Messages class
to prevent blocking the async event loop during database operations.

Pattern:
- Sync operations: messages.py (Messages class)
- Async wrappers: messages_async.py (MessagesAsync class)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from message import Message
from messages import Messages


class MessagesAsync:
    """Async wrapper for Messages database operations"""

    def __init__(self, messages: Messages, executor: ThreadPoolExecutor | None = None):
        """
        Initialize async wrapper

        Args:
            messages: Synchronous Messages instance
            executor: ThreadPoolExecutor for running blocking ops (uses default if None)
        """
        self.messages = messages
        self.executor = executor

    async def insert(
        self,
        message: Message,
        extract_tickers: bool = True
    ) -> bool:
        """
        Insert a message into the database (async)

        Args:
            message: Message object to insert
            extract_tickers: Whether to extract and store tickers

        Returns:
            True if successful, False if message already exists
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.insert,
            message,
            extract_tickers
        )

    async def update_extracted_data(self, message_id: int, extracted_data: dict) -> bool:
        """
        Update extracted_data field for a message (async)

        Args:
            message_id: Discord message ID
            extracted_data: Vision/trade analysis results

        Returns:
            True if successful, False if message not found
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.update_extracted_data,
            message_id,
            extracted_data
        )

    async def update_sentiment(
        self,
        message_id: int,
        sentiment: str,
        confidence: float,
        reasoning: str
    ) -> bool:
        """
        Update sentiment analysis results for a message (async)

        Args:
            message_id: Discord message ID
            sentiment: Sentiment label (bullish/bearish/neutral)
            confidence: Confidence score (0.0-1.0)
            reasoning: LLM reasoning

        Returns:
            True if successful, False if message not found
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.update_sentiment,
            message_id,
            sentiment,
            confidence,
            reasoning
        )

    async def mark_deleted(self, message_id: int) -> bool:
        """
        Mark a message as deleted (async)

        Args:
            message_id: Discord message ID

        Returns:
            True if successful, False if message not found
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.mark_deleted,
            message_id
        )

    async def get_message(self, message_id: int) -> Message | None:
        """
        Get a single message by ID (async)

        Args:
            message_id: Discord message ID

        Returns:
            Message object or None if not found
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_message,
            message_id
        )

    async def get_by_ticker(self, ticker: str, limit: int = 50) -> list[Message]:
        """
        Get messages mentioning a specific ticker (async)

        Args:
            ticker: Stock symbol
            limit: Maximum number of messages to return

        Returns:
            List of Message objects
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_by_ticker,
            ticker,
            limit
        )

    async def get_by_user(
        self,
        username: str,
        limit: int = 50,
        include_deleted: bool = False
    ) -> list[Message]:
        """
        Get messages from a specific user (async)

        Args:
            username: Discord username
            limit: Maximum number of messages to return
            include_deleted: Whether to include deleted messages

        Returns:
            List of Message objects
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_by_user,
            username,
            limit,
            include_deleted
        )

    async def get_recent(
        self,
        channel_name: str | None = None,
        limit: int = 50,
        include_deleted: bool = False,
        category: str | None = None
    ) -> list[Message]:
        """
        Get recent messages (async)

        Args:
            channel_name: Filter by channel name
            limit: Maximum number of messages to return
            include_deleted: Whether to include deleted messages
            category: Filter by category (sentiment/news/earnings)

        Returns:
            List of Message objects
        """
        loop = asyncio.get_event_loop()
        # Note: category parameter not supported by Messages.get_recent
        return await loop.run_in_executor(
            self.executor,
            lambda: self.messages.get_recent(channel_name, limit, include_deleted)
        )

    async def count(
        self,
        channel_name: str | None = None,
        include_deleted: bool = False,
        category: str | None = None
    ) -> int:
        """
        Count messages (async)

        Args:
            channel_name: Filter by channel name
            include_deleted: Whether to include deleted messages
            category: Filter by category

        Returns:
            Number of messages
        """
        loop = asyncio.get_event_loop()
        # Note: category parameter not supported by Messages.count
        return await loop.run_in_executor(
            self.executor,
            lambda: self.messages.count(channel_name, include_deleted)
        )

    async def count_by_ticker(self, ticker: str) -> int:
        """
        Count messages mentioning a ticker (async)

        Args:
            ticker: Stock symbol

        Returns:
            Number of messages
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.count_by_ticker,
            ticker
        )

    async def count_by_user(self, username: str, include_deleted: bool = False) -> int:
        """
        Count messages from a user (async)

        Args:
            username: Discord username
            include_deleted: Whether to include deleted messages

        Returns:
            Number of messages
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.count_by_user,
            username,
            include_deleted
        )

    async def get_channel_stats(self) -> dict:
        """
        Get statistics by channel (async)

        Returns:
            Dict mapping channel_name -> message count
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_channel_stats
        )

    async def get_ticker_stats(self, limit: int = 20) -> list[tuple]:
        """
        Get ticker mention statistics (async)

        Args:
            limit: Maximum number of tickers to return

        Returns:
            List of (ticker, mention_count) tuples
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_ticker_stats,
            limit
        )

    async def update_tickers(self, message_id: int) -> bool:
        """
        Update tickers for a message (async)

        Args:
            message_id: Discord message ID

        Returns:
            True if updated successfully
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.update_tickers,
            message_id
        )

    async def get_user_stats(self, username: str, limit: int = 20) -> dict:
        """
        Get statistics for a specific user (async)

        Args:
            username: Discord username
            limit: Maximum number of tickers to return

        Returns:
            Dict with user statistics
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.messages.get_user_stats,
            username,
            limit
        )
