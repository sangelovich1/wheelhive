"""Discord-object-wrapped guild id lists. Isolated here so non-Discord
processes (e.g. the web app) can import `constants` without discord.py."""
import discord

from constants import DEV_GUILDS, GUILDS

GUILD_IDS = [discord.Object(id=i) for i in GUILDS]
DEV_GUILD_IDS = [discord.Object(id=i) for i in DEV_GUILDS]
