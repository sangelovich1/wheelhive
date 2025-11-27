"""
Quick script to check if bot can access a specific channel

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

# Channel to check
TARGET_CHANNEL_ID = 1422938781845295286

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'\nLogged in as {client.user}\n')
    print("=" * 80)
    print(f"Checking access to channel ID: {TARGET_CHANNEL_ID}")
    print("=" * 80 + "\n")

    # Try to get the channel
    channel = client.get_channel(TARGET_CHANNEL_ID)

    if channel is None:
        print(f"❌ Channel {TARGET_CHANNEL_ID} not found or bot doesn't have access")
        print("\nPossible reasons:")
        print("  - Channel doesn't exist")
        print("  - Bot is not in the guild")
        print("  - Bot lacks permission to view the channel")
    elif isinstance(channel, (discord.DMChannel, discord.GroupChannel)):
        print(f"❌ Channel {TARGET_CHANNEL_ID} is a private channel")
    else:
        # Type narrowing for mypy - channel is now a guild channel
        print(f"✓ Channel found!")
        print(f"  Name: #{channel.name}")  # type: ignore[union-attr]
        print(f"  Guild: {channel.guild.name} (ID: {channel.guild.id})")  # type: ignore[union-attr]
        print(f"  Type: {channel.type}")  # type: ignore[union-attr]

        # Check if it's already in KNOWLEDGEBASE_CHANNELS
        if TARGET_CHANNEL_ID in const.KNOWLEDGEBASE_CHANNELS:
            print(f"\n✓ Already in KNOWLEDGEBASE_CHANNELS as '{const.KNOWLEDGEBASE_CHANNELS[TARGET_CHANNEL_ID]}'")
        else:
            print(f"\n⚠ Not yet in KNOWLEDGEBASE_CHANNELS")
            print(f"\nTo add this channel to message harvesting, add this line to constants.py:")
            print(f"  {TARGET_CHANNEL_ID}: '{channel.name}',")  # type: ignore[union-attr]

    print("\n" + "=" * 80)
    print("\nCurrently monitored channels:")
    for channel_id, channel_name in const.KNOWLEDGEBASE_CHANNELS.items():
        ch = client.get_channel(channel_id)
        status = "✓" if ch else "❌"
        print(f"  {status} {channel_id}: '{channel_name}'")

    await client.close()

# Run the client
if const.TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")
client.run(const.TOKEN)
