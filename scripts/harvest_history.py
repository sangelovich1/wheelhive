"""
Historical message harvester - Fetch last N days of messages from Discord channels

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
sys.path.insert(0, 'src')

import asyncio
import discord
from datetime import datetime, timedelta
import logging

import constants as const
from db import Db
from messages import Messages
from message import Message
from guild_channels import GuildChannels

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
db = Db()
messages_db = Messages(db)
guild_channels_db = GuildChannels(db)


async def harvest_channel_history(client, channel_id: int, channel_name: str, days: int = 7):
    """
    Harvest message history from a Discord channel

    Args:
        client: Discord client
        channel_id: Discord channel ID
        channel_name: Channel name for logging
        days: Number of days to look back
    """
    try:
        channel = client.get_channel(channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found")
            return 0, 0

        logger.info(f"Harvesting #{channel.name} (ID: {channel_id})")

        # Calculate date threshold
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(f"Fetching messages since {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        harvested = 0
        skipped = 0
        errors = 0

        # Determine if this is a news channel
        channel_category = guild_channels_db.get_channel_category(channel_id)
        is_news_channel = channel_category == 'news'

        # Fetch messages after cutoff date
        async for discord_msg in channel.history(limit=None, after=cutoff_date):
            try:
                # Skip bot messages UNLESS it's a news channel (news often comes from bots)
                if discord_msg.author.bot and not is_news_channel:
                    continue

                # Skip slash commands
                if discord_msg.content.startswith('/'):
                    continue

                # Create Message object
                msg = Message.from_discord_message(discord_msg)

                # Insert with ticker extraction (disabled for news channels - too many false positives)
                success = messages_db.insert(msg, extract_tickers=not is_news_channel)

                if success:
                    harvested += 1
                    if harvested % 10 == 0:  # Progress indicator
                        logger.info(f"  Processed {harvested} messages...")
                else:
                    skipped += 1  # Already exists

            except Exception as e:
                errors += 1
                logger.error(f"Error processing message {discord_msg.id}: {e}")

        logger.info(f"Completed #{channel.name}: {harvested} new, {skipped} existing, {errors} errors")
        return harvested, skipped

    except Exception as e:
        logger.error(f"Error accessing channel {channel_id}: {e}")
        return 0, 0


async def main(days: int = 7):
    """
    Main harvest function

    Args:
        days: Number of days to look back (default: 7)
    """
    # Setup Discord client with minimal intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"Logged in as {client.user}")

        # Get all enabled channel IDs from database
        all_channel_ids = guild_channels_db.get_all_channel_ids()
        logger.info(f"Harvesting last {days} days from {len(all_channel_ids)} channels")
        logger.info("=" * 80)

        total_harvested = 0
        total_skipped = 0

        # Process each configured channel
        for channel_id in all_channel_ids:
            # Get channel info from Discord
            channel = client.get_channel(channel_id)
            # PrivateChannel doesn't have .name attribute, use getattr with default
            channel_name = getattr(channel, 'name', f"Unknown-{channel_id}") if channel else f"Unknown-{channel_id}"

            harvested, skipped = await harvest_channel_history(
                client, channel_id, channel_name, days
            )
            total_harvested += harvested
            total_skipped += skipped

        logger.info("=" * 80)
        logger.info(f"Harvest complete!")
        logger.info(f"  New messages harvested: {total_harvested}")
        logger.info(f"  Existing messages skipped: {total_skipped}")
        logger.info(f"  Total messages in database: {messages_db.count()}")

        # Show ticker stats per guild (data isolation)
        if const.GUILDS:
            for guild_id in const.GUILDS:
                ticker_stats = messages_db.get_ticker_stats(guild_id=guild_id, limit=20)
                if ticker_stats:
                    logger.info(f"\nTop 20 mentioned tickers (Guild {guild_id}):")
                    for ticker, count in ticker_stats:
                        logger.info(f"  ${ticker}: {count} messages")

        # Close client and cleanup connections
        await client.close()
        # Give time for cleanup
        await asyncio.sleep(0.5)

    # Connect to Discord
    try:
        if const.TOKEN is None:
            raise ValueError("DISCORD_TOKEN environment variable not set")
        await client.start(const.TOKEN)
    except KeyboardInterrupt:
        logger.info("Harvest interrupted by user")
    finally:
        if not client.is_closed():
            await client.close()
        # Give time for cleanup
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Harvest historical Discord messages")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )

    args = parser.parse_args()

    if args.days < 1 or args.days > 90:
        print("Error: Days must be between 1 and 90")
        sys.exit(1)

    print(f"Starting historical harvest for last {args.days} days...")
    print("This may take a few minutes depending on message volume.")
    print()

    asyncio.run(main(args.days))
