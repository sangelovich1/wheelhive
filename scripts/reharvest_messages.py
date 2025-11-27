#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-harvest specific Discord messages to refresh expired CDN URLs

Fetches messages from Discord API and updates their attachment URLs in the database.
Useful for QC when old image URLs have expired.

Usage:
    # Re-harvest specific message IDs
    python scripts/reharvest_messages.py 1234567890 9876543210

    # Re-harvest all messages with images from a channel
    python scripts/reharvest_messages.py --channel "💸darkminer-moves" --days 30

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
import asyncio
import json
from typing import List, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db import Db
import discord
import constants as const


async def fetch_message_from_discord(
    client: discord.Client,
    channel_id: int,
    message_id: int
) -> Optional[discord.Message]:
    """
    Fetch a specific message from Discord API.

    Args:
        client: Discord client
        channel_id: Channel ID
        message_id: Message ID

    Returns:
        Discord Message object or None if not found
    """
    try:
        channel = client.get_channel(channel_id)
        if not channel:
            print(f"ERROR: Channel {channel_id} not found")
            return None

        # Type guard for text-based channels
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            print(f"ERROR: Channel {channel_id} is not a text channel")
            return None

        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        print(f"ERROR: Message {message_id} not found in channel {channel_id}")
        return None
    except discord.Forbidden:
        print(f"ERROR: No permission to access message {message_id}")
        return None
    except Exception as e:
        print(f"ERROR: Failed to fetch message {message_id}: {e}")
        return None


async def update_message_attachments(db: Db, message: discord.Message) -> bool:
    """
    Update attachment URLs for a message in the database.

    Args:
        db: Database connection
        message: Discord message

    Returns:
        True if updated successfully
    """
    try:
        # Extract attachment URLs
        attachment_urls = [att.url for att in message.attachments]

        if not attachment_urls:
            print(f"  No attachments found for message {message.id}")
            return False

        # Update database
        query = """
        UPDATE harvested_messages
        SET attachment_urls = ?
        WHERE message_id = ?
        """

        db.execute(query, (json.dumps(attachment_urls), message.id))

        print(f"  ✓ Updated {len(attachment_urls)} attachment URL(s)")
        return True

    except Exception as e:
        print(f"  ERROR: Failed to update database: {e}")
        return False


async def reharvest_specific_messages(
    client: discord.Client,
    db: Db,
    message_ids: List[int]
) -> int:
    """
    Re-harvest specific message IDs.

    Args:
        client: Discord client
        db: Database connection
        message_ids: List of message IDs to re-harvest

    Returns:
        Number of messages successfully updated
    """
    print(f"Re-harvesting {len(message_ids)} specific messages...")
    print()

    updated_count = 0

    for message_id in message_ids:
        print(f"Fetching message {message_id}...")

        # Get channel ID from database
        query = "SELECT channel_name, guild_id FROM harvested_messages WHERE message_id = ?"
        result = db.query_parameterized(query, (message_id,))

        if not result:
            print(f"  ERROR: Message {message_id} not found in database")
            continue

        channel_name, guild_id = result[0]

        # Get channel ID from guild_channels - try exact match first, then strip emoji
        query = "SELECT channel_id FROM guild_channels WHERE guild_id = ? AND channel_name = ?"
        result = db.query_parameterized(query, (guild_id, channel_name))

        if not result:
            # Try stripping emoji prefix
            import re
            channel_name_stripped = re.sub(r'^[^\w-]+', '', channel_name)
            result = db.query_parameterized(query, (guild_id, channel_name_stripped))

            if not result:
                print(f"  ERROR: Channel '{channel_name}' not found in guild_channels")
                continue

        channel_id = result[0][0]

        # Fetch from Discord
        message = await fetch_message_from_discord(client, channel_id, message_id)

        if message:
            if await update_message_attachments(db, message):
                updated_count += 1

        print()

    return updated_count


async def reharvest_channel_messages(
    client: discord.Client,
    db: Db,
    guild_id: int,
    channel_name: str,
    days: int
) -> int:
    """
    Re-harvest all messages with images from a channel.

    Args:
        client: Discord client
        db: Database connection
        guild_id: Guild ID
        channel_name: Channel name
        days: Look back N days

    Returns:
        Number of messages successfully updated
    """
    print(f"Re-harvesting messages from #{channel_name} (last {days} days)...")
    print()

    # Get channel ID - try exact match first, then strip emoji prefix
    query = "SELECT channel_id FROM guild_channels WHERE guild_id = ? AND channel_name = ?"
    result = db.query_parameterized(query, (guild_id, channel_name))

    if not result:
        # Try stripping emoji prefix (💸darkminer-moves -> darkminer-moves)
        import re
        channel_name_stripped = re.sub(r'^[^\w-]+', '', channel_name)
        result = db.query_parameterized(query, (guild_id, channel_name_stripped))

        if not result:
            print(f"ERROR: Channel '{channel_name}' not found in guild_channels")
            print(f"Available channels:")
            all_channels = db.query_parameterized(
                "SELECT channel_name FROM guild_channels WHERE guild_id = ?",
                (guild_id,)
            )
            for row in all_channels:
                print(f"  - {row[0]}")
            return 0

    channel_id = result[0][0]

    # Get messages with images
    query = """
    SELECT message_id
    FROM harvested_messages
    WHERE guild_id = ?
      AND channel_name = ?
      AND has_attachments = 1
      AND timestamp >= datetime('now', '-' || ? || ' days')
    ORDER BY timestamp DESC
    """

    results = db.query_parameterized(query, (guild_id, channel_name, days))
    message_ids = [row[0] for row in results]

    print(f"Found {len(message_ids)} messages with attachments")
    print()

    return await reharvest_specific_messages(client, db, message_ids)


async def main():
    """Main script entry point."""

    if len(sys.argv) < 2:
        print("Usage:")
        print("  # Re-harvest specific message IDs")
        print("  python scripts/reharvest_messages.py <message_id1> <message_id2> ...")
        print()
        print("  # Re-harvest all messages with images from a channel")
        print("  python scripts/reharvest_messages.py --channel CHANNEL_NAME --days N")
        print()
        print("Examples:")
        print("  python scripts/reharvest_messages.py 1234567890 9876543210")
        print('  python scripts/reharvest_messages.py --channel "💸darkminer-moves" --days 30')
        sys.exit(1)

    # Initialize database
    db = Db(in_memory=False)

    # Initialize Discord client
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.messages = True
    intents.guild_messages = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Connected to Discord as {client.user}")
        print()

        try:
            # Parse arguments
            if sys.argv[1] == '--channel':
                # Channel mode
                if len(sys.argv) < 4:
                    print("ERROR: --channel requires CHANNEL_NAME and --days N")
                    await client.close()
                    return

                channel_name = sys.argv[2]

                if sys.argv[3] != '--days':
                    print("ERROR: Expected --days after channel name")
                    await client.close()
                    return

                days = int(sys.argv[4])
                guild_id = int(os.environ.get('GUILD_ID', '1405962109262757980'))

                updated = await reharvest_channel_messages(client, db, guild_id, channel_name, days)

            else:
                # Specific message IDs mode
                message_ids = [int(arg) for arg in sys.argv[1:]]
                updated = await reharvest_specific_messages(client, db, message_ids)

            print("=" * 80)
            print(f"✓ Successfully updated {updated} message(s)")
            print("=" * 80)

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

        await client.close()

    # Run Discord client
    token = os.environ.get('DISCORD_TOKEN') or const.TOKEN
    if not token:
        print("ERROR: DISCORD_TOKEN not set")
        return
    await client.start(token)


if __name__ == '__main__':
    asyncio.run(main())
