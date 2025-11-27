"""
Discord Admin Commands

Slash commands for server administrators to manage bot configuration.
Includes channel management and FAQ knowledge base management.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from admin_faq_modal import AdminFAQModal
from db import Db
from faq_manager import FAQManager
from guild_channels import GuildChannels


logger = logging.getLogger(__name__)


class AdminCommands(commands.Cog):
    """Administrative commands for bot configuration."""

    # TODO: Guild restriction not working with Cogs - investigate
    # For now, relying on administrator=True permission check
    # __app_commands_guilds__ = [discord.Object(id=guild_id) for guild_id in const.DEV_GUILDS]

    def __init__(self, bot: commands.Bot, db: Db):
        self.bot = bot
        self.db = db
        self.guild_channels = GuildChannels(db)

    # ============================================================
    # Channel Management Commands
    # ============================================================

    @app_commands.command(name="channels_list", description="List all configured analysis channels")
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_list(self, interaction: discord.Interaction):
        """List all channels configured for message analysis."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return
            channels = self.guild_channels.get_channels_for_guild(guild_id)

            if not channels:
                embed = discord.Embed(
                    title="📋 Configured Channels",
                    description="No channels configured for analysis.",
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Use /channels_add to configure channels")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Separate by category
            sentiment_channels = [c for c in channels if c[2] == "sentiment"]
            news_channels = [c for c in channels if c[2] == "news"]

            embed = discord.Embed(
                title="📋 Configured Analysis Channels",
                description=f"Currently analyzing **{len(channels)}** channel(s) in this server",
                color=discord.Color.blue(),
            )

            if sentiment_channels:
                sentiment_list = "\n".join(
                    [f"• <#{ch[0]}> (`{ch[1]}`)" for ch in sentiment_channels]
                )
                embed.add_field(name="💬 Community Channels", value=sentiment_list, inline=False)

            if news_channels:
                news_list = "\n".join([f"• <#{ch[0]}> (`{ch[1]}`)" for ch in news_channels])
                embed.add_field(name="📰 News Channels", value=news_list, inline=False)

            embed.set_footer(text="Use /channels_add or /channels_remove to modify")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing channels: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error listing channels: {e!s}", ephemeral=True)

    @app_commands.command(name="channels_add", description="Add a channel for message analysis")
    @app_commands.describe(
        channel="The channel to analyze messages from",
        category="Channel type (community for discussions, news for announcements)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        category: Literal["community", "news"],
    ):
        """Add a channel for message analysis with validation."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id or not interaction.guild:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Validate bot permissions
            if not self.bot.user:
                await interaction.followup.send("❌ Bot user not available", ephemeral=True)
                return

            bot_member = interaction.guild.get_member(self.bot.user.id)
            if not bot_member:
                await interaction.followup.send(
                    "❌ Could not find bot member in guild", ephemeral=True
                )
                return

            channel_perms = channel.permissions_for(bot_member)

            if not channel_perms.read_messages:
                await interaction.followup.send(
                    f"❌ I don't have permission to read messages in {channel.mention}\n"
                    f"Please grant me `Read Messages` permission for that channel.",
                    ephemeral=True,
                )
                return

            if not channel_perms.read_message_history:
                await interaction.followup.send(
                    f"⚠️ Warning: I can read {channel.mention} but cannot read message history.\n"
                    f"Please grant me `Read Message History` permission for full functionality.",
                    ephemeral=True,
                )
                # Allow to continue - they might fix permissions later

            # Map user-friendly "community" to internal "sentiment"
            internal_category = "sentiment" if category == "community" else "news"

            # Add to database
            self.guild_channels.add_channel(
                guild_id=guild_id,
                channel_id=channel.id,
                channel_name=channel.name,
                category=internal_category,
            )

            # Success embed
            category_emoji = "💬" if category == "community" else "📰"
            category_label = "Community" if category == "community" else "News"

            embed = discord.Embed(
                title="✅ Channel Added",
                description=f"Now analyzing messages from {channel.mention}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(
                name="Category", value=f"{category_emoji} {category_label}", inline=True
            )
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.set_footer(text="Messages will be analyzed for trading insights")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Channel added by {interaction.user.name}: {channel.name} "
                f"({channel.id}) as {category}"
            )

        except Exception as e:
            logger.error(f"Error adding channel: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error adding channel: {e!s}", ephemeral=True)

    @app_commands.command(name="channels_remove", description="Remove a channel from analysis")
    @app_commands.describe(channel="The channel to stop analyzing")
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_remove(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove a channel from message analysis."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Check if channel is configured
            channels = self.guild_channels.get_channels_for_guild(guild_id)
            channel_ids = [c[0] for c in channels]

            if channel.id not in channel_ids:
                await interaction.followup.send(
                    f"ℹ️ {channel.mention} is not currently configured for analysis.", ephemeral=True
                )
                return

            # Remove from database
            self.guild_channels.remove_channel(guild_id=guild_id, channel_id=channel.id)

            # Success embed
            embed = discord.Embed(
                title="✅ Channel Removed",
                description=f"No longer analyzing messages from {channel.mention}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.set_footer(text="Use /channels_add to re-enable if needed")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Channel removed by {interaction.user.name}: {channel.name} ({channel.id})"
            )

        except Exception as e:
            logger.error(f"Error removing channel: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error removing channel: {e!s}", ephemeral=True)

    # ============================================================
    # FAQ Knowledge Base Management Commands
    # ============================================================

    @app_commands.command(name="faq_list", description="List all FAQs in knowledge base")
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_list(self, interaction: discord.Interaction):
        """List all FAQs for the current guild."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Get FAQs for this guild
            faq_mgr = FAQManager(guild_id=guild_id)
            faqs = await asyncio.to_thread(faq_mgr.list_faqs)

            if not faqs:
                embed = discord.Embed(
                    title="📋 FAQ Knowledge Base",
                    description="No FAQs found for this server.",
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Use /faq_add to create your first FAQ")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build paginated embed response
            embed = discord.Embed(
                title="📋 FAQ Knowledge Base",
                description=f"Currently tracking **{len(faqs)}** FAQ(s) for this server",
                color=discord.Color.blue(),
            )

            # Add FAQs as fields (max 25 fields per embed)
            for idx, faq in enumerate(faqs[:25], 1):  # Discord limit
                question = faq.get("question", "N/A")
                answer = faq.get("answer", "N/A")
                added_by = faq.get("added_by", "unknown")
                faq_id = faq.get("id", "unknown")

                # Truncate long answers for display
                if len(answer) > 150:
                    answer = answer[:147] + "..."

                field_value = f"**A:** {answer}\n" f"*Added by {added_by}*\n" f"ID: `{faq_id}`"

                # Truncate field value if too long (1024 char limit)
                if len(field_value) > 1024:
                    field_value = field_value[:1021] + "..."

                embed.add_field(name=f"{idx}. {question[:100]}", value=field_value, inline=False)

            if len(faqs) > 25:
                embed.set_footer(
                    text=f"Showing first 25 of {len(faqs)} FAQs. " f"Contact admin for full list."
                )
            else:
                embed.set_footer(text="Use /faq_add or /faq_remove to modify")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing FAQs: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error listing FAQs: {e!s}", ephemeral=True)

    @app_commands.command(name="faq_add", description="Add FAQ to knowledge base")
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_add(self, interaction: discord.Interaction):
        """Open modal for admins to add validated FAQ entries."""
        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a server", ephemeral=True
            )
            return

        # Create and configure modal
        modal = AdminFAQModal()
        modal.set_guild_id(interaction.guild_id)

        # Send modal to user
        await interaction.response.send_modal(modal)

    @app_commands.command(name="faq_remove", description="Remove FAQ from knowledge base")
    @app_commands.describe(faq_id="The FAQ ID to remove (use /faq_list to see IDs)")
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_remove(self, interaction: discord.Interaction, faq_id: str):
        """Remove FAQ from guild's vector store."""
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Remove FAQ
            faq_mgr = FAQManager(guild_id=guild_id)
            success = await asyncio.to_thread(faq_mgr.remove_faq, faq_id)

            if success:
                embed = discord.Embed(
                    title="✅ FAQ Removed",
                    description="Successfully removed FAQ from knowledge base",
                    color=discord.Color.green(),
                )
                embed.add_field(name="FAQ ID", value=f"`{faq_id}`", inline=False)
                embed.set_footer(text="Use /faq_list to see remaining FAQs")
                await interaction.followup.send(embed=embed, ephemeral=True)

                logger.info(
                    f"FAQ removed by {interaction.user.name}: {faq_id} " f"from guild {guild_id}"
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove FAQ `{faq_id}`.\n"
                    f"It may not exist or there was an error.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error removing FAQ {faq_id}: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error removing FAQ: {e!s}", ephemeral=True)

    # ============================================================
    # Error Handlers
    # ============================================================

    @channels_list.error
    @channels_add.error
    @channels_remove.error
    @faq_list.error
    @faq_add.error
    @faq_remove.error
    async def admin_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for admin commands."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need Administrator permissions to use this command.", ephemeral=True
            )
        else:
            logger.error(f"Admin command error: {error}", exc_info=True)
            message = f"❌ An error occurred: {error!s}"
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot, db: Db):
    """Register admin commands with the bot."""
    cog = AdminCommands(bot, db)

    logger.info(f"AdminCommands cog has {len(cog.__cog_app_commands__)} app commands")
    for cmd in cog.__cog_app_commands__:
        logger.info(f"  - Cog command: {cmd.name}")

    await bot.add_cog(cog)
    logger.info("Cog added to bot")

    # Check what commands are in the tree
    tree_commands = [c.name for c in bot.tree.get_commands()]
    logger.info(f"Bot tree has {len(tree_commands)} commands: {tree_commands}")
