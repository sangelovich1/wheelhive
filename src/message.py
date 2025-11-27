"""
Message model

Represents a harvested Discord message from community channels for knowledge base

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
from datetime import datetime

import util


class Message:
    """Single harvested Discord message"""

    def __init__(
        self,
        message_id: int,
        guild_id: int,
        channel_name: str,
        username: str,
        content: str,
        timestamp: str,
        attachment_urls: list[str] | None = None,
        extracted_data: str | None = None,
        category: str = "sentiment",
        is_deleted: bool = False,
        deleted_at: str | None = None,
        harvested_at: str | None = None,
        sentiment: str | None = None,
        sentiment_confidence: float | None = None,
        sentiment_reasoning: str | None = None,
        sentiment_analyzed_at: str | None = None,
        tickers: list[str] | None = None
    ):
        """
        Initialize a message

        Args:
            message_id: Discord message ID
            guild_id: Discord guild (server) ID
            channel_name: Channel name (e.g., 'stock-options', 'stock-chat')
            username: Discord username of author
            content: Message text content
            timestamp: Message creation timestamp (ISO format)
            attachment_urls: List of attachment URLs (images, files)
            extracted_data: JSON string of structured data from vision analysis
            category: Message category ('sentiment' or 'news')
            is_deleted: Whether message was deleted
            deleted_at: When message was deleted (ISO format)
            harvested_at: When message was captured (ISO format)
            tickers: List of ticker symbols from message_tickers table
        """
        self.message_id = message_id
        self.guild_id = guild_id
        self.channel_name = channel_name
        self.username = username
        self.content = content
        self.timestamp = timestamp
        self.attachment_urls = attachment_urls or []
        self.extracted_data = extracted_data
        self.category = category
        self.is_deleted = is_deleted
        self.deleted_at = deleted_at
        self.harvested_at = harvested_at or datetime.utcnow().isoformat()
        self.sentiment = sentiment
        self.sentiment_confidence = sentiment_confidence
        self.sentiment_reasoning = sentiment_reasoning
        self.sentiment_analyzed_at = sentiment_analyzed_at
        self.tickers: list[str] = tickers or []

    def to_tuple(self) -> tuple:
        """Convert to tuple for database insertion"""
        # Convert attachment_urls list to JSON string for storage
        attachments_json = json.dumps(self.attachment_urls) if self.attachment_urls else None
        has_attachments = len(self.attachment_urls) > 0

        return (
            self.message_id,
            self.guild_id,
            self.channel_name,
            self.username,
            self.content,
            self.timestamp,
            has_attachments,
            attachments_json,
            self.extracted_data,
            self.category,
            self.is_deleted,
            self.deleted_at,
            self.harvested_at
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON export"""
        return {
            "message_id": self.message_id,
            "guild_id": self.guild_id,
            "channel_name": self.channel_name,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp,
            "attachment_urls": self.attachment_urls,
            "extracted_data": self.extracted_data,
            "category": self.category,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at,
            "harvested_at": self.harvested_at
        }

    def get_trades(self) -> list[dict]:
        """
        Extract and normalize trades from extracted_data

        Returns:
            List of trade dictionaries with normalized field names and message metadata
        """
        if not self.extracted_data:
            return []

        try:
            extracted = json.loads(self.extracted_data)
            trades = extracted.get("trades", [])

            if not trades:
                return []

            # Extract metadata once
            confidence = extracted.get("extraction_metadata", {}).get("confidence", 0.0)
            extraction_source = extracted.get("image_type", "text")

            # Build normalized trade objects
            normalized_trades = []
            for trade in trades:
                trade_obj = {
                    "username": self.username,
                    "channel": self.channel_name,
                    "posted_at": self.timestamp,
                    "message_id": self.message_id,
                    "operation": trade.get("operation"),
                    "quantity": trade.get("quantity"),
                    "ticker": trade.get("ticker"),
                    "expiration": trade.get("expiration"),
                    "strike": trade.get("strike"),
                    "option_type": trade.get("option_type"),
                    "premium": trade.get("premium"),
                    "confidence": confidence,
                    "extraction_source": extraction_source
                }
                normalized_trades.append(trade_obj)

            return normalized_trades

        except (json.JSONDecodeError, KeyError):
            # Silently return empty list on parse errors
            return []

    @classmethod
    def from_discord_message(cls, discord_message, category: str = "sentiment") -> "Message":
        """
        Create Message from discord.Message object

        Args:
            discord_message: discord.Message object
            category: Channel category ('sentiment' or 'news'), defaults to 'sentiment'

        Returns:
            Message instance
        """
        # Extract attachment URLs
        attachment_urls = [att.url for att in discord_message.attachments] if discord_message.attachments else []

        # Get channel name and normalize it (remove emoji prefixes/suffixes for CLI usability)
        raw_channel_name = discord_message.channel.name if hasattr(discord_message.channel, "name") else "unknown"
        channel_name = util.normalize_channel_name(raw_channel_name)

        return cls(
            message_id=discord_message.id,
            guild_id=discord_message.guild.id if discord_message.guild else 0,
            channel_name=channel_name,
            username=discord_message.author.name,
            content=discord_message.content,
            timestamp=discord_message.created_at.isoformat(),
            attachment_urls=attachment_urls,
            category=category,
            is_deleted=False,
            deleted_at=None
        )

    def __repr__(self) -> str:
        return f"Message(id={self.message_id}, channel={self.channel_name}, user={self.username}, deleted={self.is_deleted})"

    def __str__(self) -> str:
        deleted_str = " [DELETED]" if self.is_deleted else ""
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.timestamp} | {self.channel_name} | {self.username}: {content_preview}{deleted_str}"

    def get_all_tickers(self, validator=None) -> set[str]:
        """
        Extract tickers from ALL available data sources in this message.

        Sources (in priority order):
        1. Trades from vision extraction (most reliable - parsed from screenshots)
        2. Combined text from message content + OCR text

        NOTE: Does NOT extract from sentiment reasoning (prone to LLM hallucination)

        Args:
            validator: Optional TickerValidator instance (will import if not provided)

        Returns:
            Set of valid ticker symbols found in message
        """
        from ticker_validator import TickerValidator

        # Get validator instance
        if validator is None:
            # Import here to avoid circular dependency
            from db import Db
            db = Db(in_memory=False)  # Use persistent database
            validator = TickerValidator.get_instance(db)

        all_tickers = set()

        # Source 1: Tickers from trades in extracted_data (MOST RELIABLE)
        if self.extracted_data:
            try:
                # Parse extracted_data if it's a JSON string
                if isinstance(self.extracted_data, str):
                    data = json.loads(self.extracted_data)
                else:
                    data = self.extracted_data

                # Extract and VALIDATE tickers from trades array
                if data.get("trades"):
                    for trade in data["trades"]:
                        ticker = trade.get("ticker")
                        if ticker and validator.is_valid(ticker.upper()):
                            all_tickers.add(ticker.upper())

                # Extract and VALIDATE tickers from tickers array
                # (news articles populate this, needs validation)
                if data.get("tickers"):
                    for ticker in data["tickers"]:
                        if ticker and validator.is_valid(ticker.upper()):
                            all_tickers.add(ticker.upper())

            except (json.JSONDecodeError, TypeError):
                # Extracted data is malformed, skip
                pass

        # Source 2: Text-based extraction from message content + OCR
        text_parts = []

        if self.content:
            text_parts.append(self.content)

        if self.extracted_data:
            try:
                if isinstance(self.extracted_data, str):
                    data = json.loads(self.extracted_data)
                else:
                    data = self.extracted_data

                # Get raw OCR text
                if data.get("raw_text"):
                    text_parts.append(data["raw_text"])

            except (json.JSONDecodeError, TypeError):
                pass

        # Extract and validate from combined text
        if text_parts:
            combined_text = " ".join(text_parts)
            text_tickers = validator.extract_and_validate(combined_text)
            all_tickers.update(text_tickers)

        # NOTE: Deliberately NOT extracting from sentiment_reasoning
        # LLM-generated reasoning is prone to hallucination

        return all_tickers
