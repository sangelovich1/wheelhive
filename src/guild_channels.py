"""
Guild Channels Model

Stores configuration for channels to analyze messages from, by guild.
Replaces hardcoded KNOWLEDGEBASE_CHANNELS and CHANNEL_CATEGORIES constants.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging

# Local application imports
from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)


class GuildChannels:
    """Manage guild channel configuration for message analysis."""

    def __init__(self, db: Db) -> None:
        self.db = db
        self.tablename = "guild_channels"
        self.create_table()

    def create_table(self) -> None:
        """Create guild_channels table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS guild_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL,
            category TEXT DEFAULT 'sentiment',
            subcategory TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, channel_id)
        )
        """
        self.db.create_table(query)

        # Add subcategory column if it doesn't exist (migration)
        cursor = self.db.query_parameterized("PRAGMA table_info(guild_channels)")
        existing_columns = {row[1] for row in cursor}

        if "subcategory" not in existing_columns:
            self.db.execute("ALTER TABLE guild_channels ADD COLUMN subcategory TEXT")
            logger.info("Added subcategory column to guild_channels table")

        logger.info(f"Table {self.tablename} created/verified")

    def add_channel(
        self,
        guild_id: int,
        channel_id: int,
        channel_name: str,
        category: str = "sentiment",
        subcategory: str | None = None,
    ) -> None:
        """
        Add a channel to the guild configuration.

        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID
            channel_name: Human-readable channel name
            category: Channel category ('sentiment' or 'news')
            subcategory: Channel subcategory (e.g., 'feed' for bot-posted news, 'harvest' for external feeds)
        """
        query = """
        INSERT OR REPLACE INTO guild_channels
        (guild_id, channel_id, channel_name, category, subcategory, enabled)
        VALUES (?, ?, ?, ?, ?, 1)
        """
        try:
            self.db.insert(query, (guild_id, channel_id, channel_name, category, subcategory))
            subcategory_info = f" (subcategory: {subcategory})" if subcategory else ""
            logger.info(
                f"Added channel {channel_name} ({channel_id}) for guild {guild_id}{subcategory_info}"
            )
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            raise

    def get_channels_for_guild(self, guild_id: int) -> list[tuple]:
        """
        Get all enabled channels for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of tuples: (channel_id, channel_name, category, subcategory)
        """
        query = """
        SELECT channel_id, channel_name, category, subcategory
        FROM guild_channels
        WHERE guild_id = ? AND enabled = 1
        """
        return self.db.query_parameterized(query, (guild_id,))

    def get_all_channel_ids(self) -> list[int]:
        """
        Get all enabled channel IDs across all guilds.

        Returns:
            List of channel IDs
        """
        query = """
        SELECT channel_id
        FROM guild_channels
        WHERE enabled = 1
        """
        rows = self.db.query_parameterized(query)
        return [row[0] for row in rows]

    def get_channel_category(self, channel_id: int) -> str | None:
        """
        Get the category for a specific channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            Category string ('sentiment' or 'news') or None if not found
        """
        query = """
        SELECT category
        FROM guild_channels
        WHERE channel_id = ? AND enabled = 1
        """
        rows = self.db.query_parameterized(query, (channel_id,))
        return rows[0][0] if rows else None

    def remove_channel(self, guild_id: int, channel_id: int) -> None:
        """
        Remove a channel from guild configuration (soft delete by disabling).

        Args:
            guild_id: Discord guild ID
            channel_id: Discord channel ID
        """
        query = """
        UPDATE guild_channels
        SET enabled = 0
        WHERE guild_id = ? AND channel_id = ?
        """
        self.db.execute(query, (guild_id, channel_id))
        self.db.connection.commit()
        logger.info(f"Disabled channel {channel_id} for guild {guild_id}")

    def get_channels_by_category(self, guild_id: int, category: str) -> list[tuple]:
        """
        Get channels for a guild filtered by category.

        Args:
            guild_id: Discord guild ID
            category: Channel category ('sentiment' or 'news')

        Returns:
            List of tuples: (channel_id, channel_name)
        """
        query = """
        SELECT channel_id, channel_name
        FROM guild_channels
        WHERE guild_id = ? AND category = ? AND enabled = 1
        """
        return self.db.query_parameterized(query, (guild_id, category))


def setup_legacy_channels(db: Db) -> None:
    """
    One-time setup function to migrate hardcoded channels to database.

    Run this once to populate the guild_channels table with legacy configuration.
    After running, you can comment this out or delete the call.

    Legacy channels from constants.py (guild 850508033041760256):
    - stock-options (sentiment)
    - stock-chat (sentiment)
    - darkminer-moves (sentiment)
    - news (news)
    """
    guild_channels = GuildChannels(db)

    # Legacy guild ID
    guild_id = 850508033041760256

    # Add legacy channels
    channels = [
        (guild_id, 1415355798216773653, "stock-options", "sentiment"),
        (guild_id, 1419414710255747072, "stock-chat", "sentiment"),
        (guild_id, 1415354946899017820, "darkminer-moves", "sentiment"),
        (guild_id, 1422938781845295286, "news", "news"),
    ]

    for guild_id, channel_id, name, category in channels:
        try:
            guild_channels.add_channel(guild_id, channel_id, name, category)
            logger.info(f"Migrated channel: {name} ({channel_id})")
        except Exception as e:
            logger.warning(f"Channel {name} may already exist: {e}")

    print("✓ Legacy channels migrated to database")


def main():
    """Test the guild channels model."""
    from db import Db

    db = Db()

    # Run one-time setup (COMPLETED - commented out to prevent duplicate entries)
    # setup_legacy_channels(db)

    # Test retrieval
    guild_channels = GuildChannels(db)
    print("\nAll channel IDs:", guild_channels.get_all_channel_ids())
    print(
        "\nChannels for guild 850508033041760256:",
        guild_channels.get_channels_for_guild(850508033041760256),
    )
    print(
        "\nCategory for channel 1422938781845295286:",
        guild_channels.get_channel_category(1422938781845295286),
    )


if __name__ == "__main__":
    main()
