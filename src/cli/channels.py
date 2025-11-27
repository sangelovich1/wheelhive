"""
Channel Management Commands

Commands for configuring which Discord channels to harvest messages from.
Uses Click framework for clean, modern CLI interface.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click

from guild_channels import GuildChannels


logger = logging.getLogger(__name__)


@click.group()
def channels():
    """Manage message analysis channels"""


@channels.command("list")
@click.option("--guild-id", type=int, help="Guild ID (omit to list all guilds)")
@click.pass_context
def list_channels(ctx, guild_id):
    """List channels configured for message analysis"""
    db = ctx.obj["db"]
    guild_channels = GuildChannels(db)

    try:
        if guild_id:
            # List channels for specific guild
            channels = guild_channels.get_channels_for_guild(guild_id)

            if not channels:
                click.echo(f"\nNo channels configured for guild {guild_id}\n")
                return

            click.echo(f"\n{'=' * 80}")
            click.echo(f"  CHANNELS FOR GUILD {guild_id}")
            click.echo(f"{'=' * 80}\n")

            sentiment_channels = [c for c in channels if c[2] == "sentiment"]
            news_channels = [c for c in channels if c[2] == "news"]

            if sentiment_channels:
                click.secho("SENTIMENT CHANNELS (Community discussions):", fg="cyan", bold=True)
                for channel_id, channel_name, _, subcategory in sentiment_channels:
                    subcategory_label = f", {subcategory}" if subcategory else ""
                    click.echo(f"  • {channel_name:<30} (ID: {channel_id}{subcategory_label})")
                click.echo()

            if news_channels:
                click.secho("NEWS CHANNELS (Announcements):", fg="yellow", bold=True)
                for channel_id, channel_name, _, subcategory in news_channels:
                    subcategory_label = f", {subcategory}" if subcategory else ""
                    click.echo(f"  • {channel_name:<30} (ID: {channel_id}{subcategory_label})")
                click.echo()

        else:
            # List all channels across all guilds
            query = """
                SELECT guild_id, channel_id, channel_name, category, subcategory
                FROM guild_channels
                WHERE enabled = 1
                ORDER BY guild_id, category, channel_name
            """
            all_channels = db.query_parameterized(query)

            if not all_channels:
                click.echo("\nNo channels configured in any guild\n")
                return

            click.echo(f"\n{'=' * 80}")
            click.echo("  ALL CONFIGURED CHANNELS")
            click.echo(f"{'=' * 80}\n")

            # Group by guild
            current_guild = None
            for guild_id, channel_id, channel_name, category, subcategory in all_channels:
                if current_guild != guild_id:
                    if current_guild is not None:
                        click.echo()
                    click.secho(f"Guild {guild_id}:", fg="blue", bold=True)
                    current_guild = guild_id

                category_label = "sentiment" if category == "sentiment" else "news"
                subcategory_label = f", {subcategory}" if subcategory else ""
                click.echo(
                    f"  • {channel_name:<30} (ID: {channel_id}, {category_label}{subcategory_label})"
                )

            click.echo()

    except Exception as e:
        logger.error(f"Error listing channels: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing channels: {e}\n", fg="red", err=True)
        ctx.exit(1)


@channels.command("add")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--channel-id", type=int, required=True, help="Channel ID")
@click.option("--channel-name", required=True, help="Channel name")
@click.option(
    "--category",
    type=click.Choice(["sentiment", "news"]),
    required=True,
    help="Channel category (sentiment or news)",
)
@click.option(
    "--subcategory",
    type=str,
    help="Channel subcategory (e.g., 'feed' for bot-posted news, 'harvest' for external feeds)",
)
@click.pass_context
def add_channel(ctx, guild_id, channel_id, channel_name, category, subcategory):
    """Add a channel for message analysis"""
    db = ctx.obj["db"]
    guild_channels = GuildChannels(db)

    try:
        guild_channels.add_channel(
            guild_id=guild_id,
            channel_id=channel_id,
            channel_name=channel_name,
            category=category,
            subcategory=subcategory,
        )

        category_label = "Sentiment" if category == "sentiment" else "News"
        click.secho("\n✓ Channel Added", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Channel: {channel_name} (ID: {channel_id})")
        click.echo(f"  Category: {category_label}")
        if subcategory:
            click.echo(f"  Subcategory: {subcategory}")
        click.echo("\nThe bot will now analyze messages from this channel.\n")

    except Exception as e:
        logger.error(f"Error adding channel: {e}", exc_info=True)
        click.secho(f"\n✗ Error adding channel: {e}\n", fg="red", err=True)
        ctx.exit(1)


@channels.command("rm")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--channel-id", type=int, required=True, help="Channel ID")
@click.pass_context
def rm_channel(ctx, guild_id, channel_id):
    """Remove a channel from message analysis"""
    db = ctx.obj["db"]
    guild_channels = GuildChannels(db)

    try:
        guild_channels.remove_channel(guild_id=guild_id, channel_id=channel_id)

        click.secho("\n✓ Channel Removed", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Channel ID: {channel_id}")
        click.echo("\nThe bot will no longer analyze messages from this channel.\n")

    except Exception as e:
        logger.error(f"Error removing channel: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing channel: {e}\n", fg="red", err=True)
        ctx.exit(1)
