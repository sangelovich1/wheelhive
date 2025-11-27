"""
Check the news channel for messages

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import discord
import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

import constants as const

NEWS_CHANNEL_ID = 1422938781845295286

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'\nLogged in as {client.user}\n')
    print("=" * 80)

    # Get the news channel
    channel = client.get_channel(NEWS_CHANNEL_ID)

    if channel is None:
        print(f"❌ Channel {NEWS_CHANNEL_ID} not found")
    elif isinstance(channel, (discord.DMChannel, discord.GroupChannel, discord.ForumChannel, discord.CategoryChannel)):
        print(f"❌ Channel {NEWS_CHANNEL_ID} is not a text channel")
    else:
        # Type narrowing for mypy - channel is now TextChannel or similar
        print(f"✓ Channel found: #{channel.name}")  # type: ignore[union-attr]
        print(f"  Guild: {channel.guild.name}")  # type: ignore[union-attr]
        print(f"  Type: {channel.type}")  # type: ignore[union-attr]
        print()

        # Check last 100 messages
        print("Checking last 100 messages in channel...")
        message_count = 0
        async for message in channel.history(limit=100):  # type: ignore[union-attr]
            message_count += 1
            print(f"  [{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author.name}: {message.content[:100]}")

        if message_count == 0:
            print("  ⚠️  Channel is empty - no messages found")
        else:
            print(f"\n✓ Found {message_count} messages in channel")

    await client.close()

# Run the client
if const.TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")
client.run(const.TOKEN)
