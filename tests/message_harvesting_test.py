"""
Unit tests for message harvesting functionality.

Tests that would have caught the CHANNEL_CATEGORIES and KNOWLEDGEBASE_JSON_BACKUPS errors.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import the classes we're testing
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from message import Message
from messages import Messages
from db import Db
from ticker import Ticker


class TestMessageCreation:
    """Test Message object creation from Discord messages"""

    def test_from_discord_message_with_category(self):
        """Test that Message.from_discord_message accepts category parameter"""
        # Mock Discord message
        discord_msg = Mock()
        discord_msg.id = 12345
        discord_msg.guild = Mock()
        discord_msg.guild.id = 67890
        discord_msg.channel = Mock()
        discord_msg.channel.name = "test-channel"
        discord_msg.author = Mock()
        discord_msg.author.name = "testuser"
        discord_msg.content = "Test message content"
        discord_msg.created_at = datetime.now()
        discord_msg.attachments = []

        # Test with sentiment category
        msg = Message.from_discord_message(discord_msg, category='sentiment')
        assert msg.category == 'sentiment'
        assert msg.message_id == 12345
        assert msg.username == "testuser"

        # Test with news category
        msg = Message.from_discord_message(discord_msg, category='news')
        assert msg.category == 'news'

    def test_from_discord_message_default_category(self):
        """Test that Message.from_discord_message defaults to sentiment"""
        discord_msg = Mock()
        discord_msg.id = 12345
        discord_msg.guild = Mock()
        discord_msg.guild.id = 67890
        discord_msg.channel = Mock()
        discord_msg.channel.name = "test-channel"
        discord_msg.author = Mock()
        discord_msg.author.name = "testuser"
        discord_msg.content = "Test message"
        discord_msg.created_at = datetime.now()
        discord_msg.attachments = []

        # Test without passing category
        msg = Message.from_discord_message(discord_msg)
        assert msg.category == 'sentiment'


class TestMessageInsertion:
    """Test Messages.insert functionality"""

    def test_insert_does_not_require_knowledgebase_constant(self):
        """
        Test that Messages.insert works without KNOWLEDGEBASE_JSON_BACKUPS constant.

        This test would have caught the AttributeError we encountered.
        """
        # Create a test database in memory
        db = Db(':memory:')
        messages = Messages(db)

        # Create a mock message
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Test content",
            timestamp=datetime.now().isoformat(),
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        # This should NOT raise AttributeError about KNOWLEDGEBASE_JSON_BACKUPS
        try:
            result = messages.insert(msg, extract_tickers=False)
            assert result == True
        except AttributeError as e:
            if 'KNOWLEDGEBASE' in str(e):
                pytest.fail(f"Messages.insert still references removed KNOWLEDGEBASE constant: {e}")
            raise


class TestMessageToDict:
    """Test Message serialization"""

    def test_message_to_dict(self):
        """Test that Message can be serialized to dict"""
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Test content",
            timestamp=datetime.now().isoformat(),
            attachment_urls=["http://example.com/image.png"],
            category='news',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None,
            extracted_data='{"trades": [], "raw_text": "Extracted text"}'
        )

        msg_dict = msg.to_dict()

        assert msg_dict['message_id'] == 12345
        assert msg_dict['guild_id'] == 67890
        assert msg_dict['channel_name'] == "test-channel"
        assert msg_dict['username'] == "testuser"
        assert msg_dict['category'] == 'news'
        assert msg_dict['extracted_data'] == '{"trades": [], "raw_text": "Extracted text"}'

    def test_message_to_tuple(self):
        """Test that Message can be converted to tuple for database insertion"""
        timestamp = "2025-01-01T10:00:00"
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Test content",
            timestamp=timestamp,
            attachment_urls=["http://example.com/image.png", "http://example.com/image2.png"],
            category='news',
            is_deleted=False,
            deleted_at=None,
            harvested_at="2025-01-01T10:05:00",
            extracted_data='{"trades": [], "raw_text": "Extracted text"}'
        )

        msg_tuple = msg.to_tuple()

        # Verify tuple structure
        assert msg_tuple[0] == 12345  # message_id
        assert msg_tuple[1] == 67890  # guild_id
        assert msg_tuple[2] == "test-channel"  # channel_name
        assert msg_tuple[3] == "testuser"  # username
        assert msg_tuple[4] == "Test content"  # content
        assert msg_tuple[5] == timestamp  # timestamp
        assert msg_tuple[6] == True  # has_attachments
        assert '"http://example.com/image.png"' in msg_tuple[7]  # attachments_json
        assert msg_tuple[8] == '{"trades": [], "raw_text": "Extracted text"}'  # extracted_data
        assert msg_tuple[9] == 'news'  # category
        assert msg_tuple[10] == False  # is_deleted
        assert msg_tuple[11] is None  # deleted_at
        assert msg_tuple[12] == "2025-01-01T10:05:00"  # harvested_at

    def test_message_to_tuple_no_attachments(self):
        """Test to_tuple with no attachments"""
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Test content",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        msg_tuple = msg.to_tuple()
        assert msg_tuple[6] == False  # has_attachments should be False
        assert msg_tuple[7] is None  # attachments_json should be None

    def test_message_repr(self):
        """Test Message __repr__"""
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Test content",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        repr_str = repr(msg)
        assert "12345" in repr_str
        assert "test-channel" in repr_str
        assert "testuser" in repr_str
        assert "False" in repr_str

    def test_message_str(self):
        """Test Message __str__"""
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="This is a short message",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        str_repr = str(msg)
        assert "2025-01-01T10:00:00" in str_repr
        assert "test-channel" in str_repr
        assert "testuser" in str_repr
        assert "This is a short message" in str_repr
        assert "[DELETED]" not in str_repr

    def test_message_str_deleted(self):
        """Test Message __str__ when deleted"""
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content="Deleted message",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=True,
            deleted_at="2025-01-01T11:00:00",
            harvested_at=None
        )

        str_repr = str(msg)
        assert "[DELETED]" in str_repr

    def test_message_str_long_content(self):
        """Test Message __str__ with long content (should be truncated)"""
        long_content = "A" * 100
        msg = Message(
            message_id=12345,
            guild_id=67890,
            channel_name="test-channel",
            username="testuser",
            content=long_content,
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        str_repr = str(msg)
        assert "..." in str_repr
        assert len(str_repr) < len(long_content) + 100  # Should be truncated


class TestConstantsIntegrity:
    """Test that required constants exist"""

    def test_required_constants_exist(self):
        """Test that constants module has all required attributes"""
        import constants as const

        # These constants should exist
        assert hasattr(const, 'DATABASE_PATH')
        assert hasattr(const, 'UPLOADS_DIR')
        assert hasattr(const, 'DOWNLOADS_DIR')

        # These constants should NOT exist (removed features)
        assert not hasattr(const, 'CHANNEL_CATEGORIES'), "CHANNEL_CATEGORIES should be removed (use database)"
        assert not hasattr(const, 'KNOWLEDGEBASE_JSON_BACKUPS'), "KNOWLEDGEBASE_JSON_BACKUPS should be removed"
        assert not hasattr(const, 'KNOWLEDGEBASE_DIR'), "KNOWLEDGEBASE_DIR should be removed"


class TestMessageRetrieval:
    """Test message retrieval methods"""

    def setup_method(self):
        """Set up test database with sample messages"""
        self.db = Db(':memory:')
        self.messages = Messages(self.db)

        # Insert some test messages
        self.test_messages = [
            Message(
                message_id=1001,
                guild_id=100,
                channel_name="sentiment",
                username="user1",
                content="AAPL looks bullish",
                timestamp="2025-01-01T10:00:00",
                attachment_urls=[],
                category='sentiment',
                is_deleted=False,
                deleted_at=None,
                harvested_at=None
            ),
            Message(
                message_id=1002,
                guild_id=100,
                channel_name="technical",
                username="user2",
                content="TSLA breaking resistance",
                timestamp="2025-01-01T11:00:00",
                attachment_urls=[],
                category='technical',
                is_deleted=False,
                deleted_at=None,
                harvested_at=None
            ),
            Message(
                message_id=1003,
                guild_id=100,
                channel_name="sentiment",
                username="user1",
                content="Sold my NVDA position",
                timestamp="2025-01-01T12:00:00",
                attachment_urls=[],
                category='sentiment',
                is_deleted=False,
                deleted_at=None,
                harvested_at=None
            )
        ]

        for msg in self.test_messages:
            self.messages.insert(msg, extract_tickers=False)

    def test_get_recent(self):
        """Test retrieving recent messages"""
        recent = self.messages.get_recent(limit=10)
        assert len(recent) == 3
        # Should be in reverse chronological order
        assert recent[0].message_id == 1003

    def test_get_recent_by_channel(self):
        """Test retrieving recent messages filtered by channel"""
        recent = self.messages.get_recent(channel_name="sentiment", limit=10)
        assert len(recent) == 2
        for msg in recent:
            assert msg.channel_name == "sentiment"

    def test_get_by_user(self):
        """Test retrieving messages by user"""
        user_msgs = self.messages.get_by_user("user1", limit=10)
        assert len(user_msgs) == 2
        for msg in user_msgs:
            assert msg.username == "user1"

    def test_count(self):
        """Test counting messages"""
        total = self.messages.count()
        assert total == 3

    def test_count_by_channel(self):
        """Test counting messages by channel"""
        count = self.messages.count(channel_name="sentiment")
        assert count == 2

    def test_count_by_user(self):
        """Test counting messages by user"""
        count = self.messages.count_by_user("user1")
        assert count == 2


class TestMessageDeletion:
    """Test message deletion tracking"""

    def setup_method(self):
        """Set up test database"""
        self.db = Db(':memory:')
        self.messages = Messages(self.db)

        # Insert a test message
        msg = Message(
            message_id=2001,
            guild_id=200,
            channel_name="test",
            username="testuser",
            content="Test message",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )
        self.messages.insert(msg, extract_tickers=False)

    def test_mark_deleted(self):
        """Test marking message as deleted"""
        result = self.messages.mark_deleted(2001)
        assert result == True

        # Verify message is marked as deleted
        msgs = self.messages.get_recent(limit=10, include_deleted=True)
        assert len(msgs) == 1
        assert msgs[0].is_deleted == True
        assert msgs[0].deleted_at is not None

    def test_count_excludes_deleted(self):
        """Test that count excludes deleted messages by default"""
        # Mark message as deleted
        self.messages.mark_deleted(2001)

        # Count should exclude deleted
        count = self.messages.count(include_deleted=False)
        assert count == 0

        # Count with deleted included
        count_with_deleted = self.messages.count(include_deleted=True)
        assert count_with_deleted == 1


class TestTickerExtraction:
    """Test ticker extraction from messages"""

    def setup_method(self):
        """Set up test database"""
        self.db = Db(':memory:')
        self.messages = Messages(self.db)

        # Add some known tickers to the database
        self.messages.tickers.insert(Ticker(ticker="AAPL", company_name="Apple Inc", exchange="NASDAQ", sector=None, is_active=True))
        self.messages.tickers.insert(Ticker(ticker="TSLA", company_name="Tesla Inc", exchange="NASDAQ", sector=None, is_active=True))
        self.messages.tickers.insert(Ticker(ticker="NVDA", company_name="NVIDIA Corp", exchange="NASDAQ", sector=None, is_active=True))

    def test_extract_tickers_from_content(self):
        """Test extracting ticker symbols from message content"""
        content = "I'm bullish on AAPL and TSLA. NVDA looks good too."
        tickers = self.messages._extract_tickers(content)

        # Should find all three tickers
        assert "AAPL" in tickers
        assert "TSLA" in tickers
        assert "NVDA" in tickers

    def test_extract_tickers_filters_blacklist(self):
        """Test that blacklisted words are not extracted as tickers"""
        content = "I PUT a CALL order on this stock AND will get more."
        tickers = self.messages._extract_tickers(content)

        # Blacklisted words should not be in tickers
        assert "PUT" not in tickers
        assert "CALL" not in tickers
        assert "AND" not in tickers

    def test_extract_tickers_ignores_short_words(self):
        """Test that single letters are not extracted"""
        content = "I bought some stock today."
        tickers = self.messages._extract_tickers(content)

        # Single letter "I" should not be extracted
        assert "I" not in tickers

    def test_insert_with_ticker_extraction(self):
        """Test that insert method extracts and stores tickers"""
        msg = Message(
            message_id=3001,
            guild_id=300,
            channel_name="test",
            username="testuser",
            content="Buying AAPL calls today!",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )

        # Insert with ticker extraction enabled
        self.messages.insert(msg, extract_tickers=True)

        # Verify tickers were extracted and stored
        result = self.db.query_parameterized(
            "SELECT ticker FROM message_tickers WHERE message_id = ?",
            (3001,)
        )
        tickers = [row[0] for row in result]
        assert "AAPL" in tickers

    def test_get_by_ticker(self):
        """Test retrieving messages by ticker"""
        # Insert messages with tickers
        msg1 = Message(
            message_id=3002,
            guild_id=300,
            channel_name="test",
            username="user1",
            content="AAPL is going up",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )
        self.messages.insert(msg1, extract_tickers=True)

        msg2 = Message(
            message_id=3003,
            guild_id=300,
            channel_name="test",
            username="user2",
            content="AAPL earnings beat expectations",
            timestamp="2025-01-01T11:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )
        self.messages.insert(msg2, extract_tickers=True)

        # Retrieve messages about AAPL
        aapl_messages = self.messages.get_by_ticker("AAPL", limit=10)
        assert len(aapl_messages) == 2

    def test_count_by_ticker(self):
        """Test counting messages by ticker"""
        # Insert a message with ticker
        msg = Message(
            message_id=3004,
            guild_id=300,
            channel_name="test",
            username="user1",
            content="TSLA looking strong",
            timestamp="2025-01-01T10:00:00",
            attachment_urls=[],
            category='sentiment',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )
        self.messages.insert(msg, extract_tickers=True)

        count = self.messages.count_by_ticker("TSLA")
        assert count == 1


class TestChannelStats:
    """Test channel statistics"""

    def setup_method(self):
        """Set up test database with sample messages"""
        self.db = Db(':memory:')
        self.messages = Messages(self.db)

        # Insert messages in different channels
        channels = [
            ("sentiment", 3),
            ("technical", 2),
            ("news", 1)
        ]

        msg_id = 4000
        for channel, count in channels:
            for i in range(count):
                msg = Message(
                    message_id=msg_id,
                    guild_id=400,
                    channel_name=channel,
                    username=f"user{i}",
                    content=f"Message {msg_id}",
                    timestamp=f"2025-01-01T{10+i:02d}:00:00",
                    attachment_urls=[],
                    category=channel,
                    is_deleted=False,
                    deleted_at=None,
                    harvested_at=None
                )
                self.messages.insert(msg, extract_tickers=False)
                msg_id += 1

    def test_get_channel_stats(self):
        """Test getting statistics by channel"""
        stats = self.messages.get_channel_stats()

        # Should have entries for all channels
        assert "sentiment" in stats
        assert "technical" in stats
        assert "news" in stats

        # Check counts (get_channel_stats returns dict with total/active/deleted)
        assert stats["sentiment"]["total"] == 3
        assert stats["technical"]["total"] == 2
        assert stats["news"]["total"] == 1


class TestDataFrameConversion:
    """Test DataFrame conversion"""

    def setup_method(self):
        """Set up test database with sample messages"""
        self.db = Db(':memory:')
        self.messages = Messages(self.db)

        # Insert test messages
        for i in range(5):
            msg = Message(
                message_id=5000 + i,
                guild_id=500,
                channel_name="test",
                username=f"user{i}",
                content=f"Test message {i}",
                timestamp=f"2025-01-0{i+1}T10:00:00",
                attachment_urls=[],
                category='sentiment',
                is_deleted=False,
                deleted_at=None,
                harvested_at=None
            )
            self.messages.insert(msg, extract_tickers=False)

    def test_as_df(self):
        """Test converting messages to DataFrame"""
        df = self.messages.as_df()

        # Should have 5 rows
        assert len(df) == 5

        # Should have expected columns (matching headers())
        expected_columns = ['ID', 'Message ID', 'Channel', 'Username', 'Content Preview', 'Timestamp', 'Attachments', 'Deleted']
        assert list(df.columns) == expected_columns

    def test_as_df_filtered_by_channel(self):
        """Test DataFrame conversion with channel filter"""
        # Insert messages in different channels
        msg = Message(
            message_id=5100,
            guild_id=500,
            channel_name="other",
            username="user",
            content="Other channel message",
            timestamp="2025-01-10T10:00:00",
            attachment_urls=[],
            category='news',
            is_deleted=False,
            deleted_at=None,
            harvested_at=None
        )
        self.messages.insert(msg, extract_tickers=False)

        # Get DataFrame filtered by channel
        df = self.messages.as_df(channel_name="test")

        # Should only have messages from 'test' channel
        assert len(df) == 5
        assert all(df['Channel'] == 'test')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
