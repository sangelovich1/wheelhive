"""
List all channels in configured guilds to find channel IDs

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import discord
import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import constants as const

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'\nLogged in as {client.user}\n')
    print("=" * 80)

    for guild in client.guilds:
        print(f"\nGuild: {guild.name} (ID: {guild.id})")
        print("-" * 80)

        # List text channels
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]

        for channel in sorted(text_channels, key=lambda ch: ch.name):
            # Check if already in KNOWLEDGEBASE_CHANNELS
            monitored = "✓ MONITORED" if channel.id in const.KNOWLEDGEBASE_CHANNELS else ""
            print(f"  #{channel.name:<40} ID: {channel.id}  {monitored}")

    print("\n" + "=" * 80)
    print("\nCurrently monitored channels:")
    for channel_id, channel_name in const.KNOWLEDGEBASE_CHANNELS.items():
        print(f"  {channel_id}: '{channel_name}'")

    await client.close()

# Run the client
if const.TOKEN is None:
    raise ValueError("DISCORD_TOKEN environment variable not set")
client.run(const.TOKEN)
