"""
Administrative Commands

Administrative commands for database queries and bulk operations.
Use with caution - some operations like delete-all are destructive.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import json
import logging
import time
from typing import Any

import click
from tabulate import tabulate

import constants as const
import util
from deposits import Deposits
from df_stats import DFStats
from dividends import Dividends
from guild_channels import GuildChannels
from messages import Messages
from ollama_client import OllamaClient
from shares import Shares
from system_settings import get_settings
from tickers import Tickers
from trades import Trades
from vision_strategy import analyze_text_trades, analyze_trading_image


logger = logging.getLogger(__name__)


@click.group()
def admin():
    """Administrative database operations"""


@admin.command("list-users")
@click.pass_context
def list_users(ctx):
    """List all users in the database"""
    db = ctx.obj["db"]

    try:
        users = db.get_users()

        if not users:
            click.secho("\nNo users found in database\n", fg="yellow")
            return

        users_list = [[user] for user in users]
        table_str = tabulate(users_list, headers=["Username"], tablefmt="psql", stralign="left")

        click.echo()
        click.echo(table_str)
        click.echo(f"\nTotal users: {len(users)}")
        click.echo()

    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing users: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("list-guilds")
@click.pass_context
def list_guilds(ctx):
    """List all guilds with configured channels and activity statistics"""
    db = ctx.obj["db"]

    try:
        guild_channels = GuildChannels(db)

        # Get all distinct guild IDs from guild_channels table
        query = """
        SELECT DISTINCT guild_id
        FROM guild_channels
        WHERE enabled = 1
        ORDER BY guild_id
        """
        guild_rows = db.query_parameterized(query)

        if not guild_rows:
            click.secho("\nNo guilds found with configured channels\n", fg="yellow")
            return

        # Build table data with statistics for each guild
        table_data = []
        for (guild_id,) in guild_rows:
            # Get channel counts
            channels = guild_channels.get_channels_for_guild(guild_id)
            total_channels = len(channels)

            # Count by category
            sentiment_channels = guild_channels.get_channels_by_category(guild_id, "sentiment")
            news_channels = guild_channels.get_channels_by_category(guild_id, "news")

            # Get trade count for this guild (may be 0 if table doesn't exist)
            try:
                trade_query = "SELECT COUNT(*) FROM trades WHERE guild_id = ?"
                trade_count = db.query_parameterized(trade_query, (guild_id,))
                trades = trade_count[0][0] if trade_count else 0
            except Exception:
                trades = 0

            # Get message count for this guild (may be 0 if table doesn't exist)
            try:
                msg_query = "SELECT COUNT(*) FROM messages WHERE guild_id = ?"
                msg_count = db.query_parameterized(msg_query, (guild_id,))
                messages = msg_count[0][0] if msg_count else 0
            except Exception:
                messages = 0

            table_data.append(
                [
                    str(guild_id),
                    total_channels,
                    len(sentiment_channels),
                    len(news_channels),
                    f"{trades:,}",
                    f"{messages:,}",
                ]
            )

        # Display results
        headers = ["Guild ID", "Channels", "Sentiment", "News", "Trades", "Messages"]
        table_str = tabulate(table_data, headers=headers, tablefmt="psql", stralign="left")

        click.echo()
        click.echo("=" * 80)
        click.secho("CONFIGURED GUILDS", bold=True)
        click.echo("=" * 80)
        click.echo(table_str)
        click.echo("=" * 80)
        click.echo(f"Total guilds: {len(guild_rows)}")
        click.echo()

    except Exception as e:
        logger.error(f"Error listing guilds: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing guilds: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("list-accounts")
@click.option("--username", required=True, help="Username")
@click.pass_context
def list_accounts(ctx, username):
    """List all accounts for a user"""
    db = ctx.obj["db"]

    try:
        # Get all accounts using shared utility function
        accounts = util.get_user_accounts(db, username)

        if not accounts:
            click.secho(f"\nNo accounts found for user '{username}'\n", fg="yellow")
            return

        # Format as table
        table_data = [[account] for account in accounts]
        table_str = tabulate(table_data, headers=["Account"], tablefmt="psql", stralign="left")

        click.echo()
        click.echo(f"Accounts for user '{username}':")
        click.echo(table_str)
        click.echo(f"\nTotal accounts: {len(accounts)}")
        click.secho("💡 Tip: Use 'ALL' in commands to query all accounts at once", fg="cyan")
        click.echo()

    except Exception as e:
        logger.error(f"Error listing accounts: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing accounts: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("list-symbols")
@click.option("--username", help="Filter by username")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_symbols(ctx, username, account, guild_id):
    """List distinct symbols from all transactions"""
    db = ctx.obj["db"]

    try:
        # Build WHERE clause
        where_parts = []
        if username:
            where_parts.append(f'username="{username}"')
        if account:
            where_parts.append(f'account="{account}"')
        if guild_id:
            where_parts.append(f"guild_id={guild_id}")

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        # Query distinct symbols from trades table
        query = f"SELECT DISTINCT symbol FROM trades {where_clause} ORDER BY symbol"
        rows = db.query(query, None)

        if not rows:
            click.secho("\nNo symbols found\n", fg="yellow")
            return

        table_str = tabulate(rows, headers=["Symbol"], tablefmt="psql", stralign="left")

        click.echo()
        if username or account or guild_id:
            filters = []
            if username:
                filters.append(f"Username: {username}")
            if account:
                filters.append(f"Account: {account}")
            if guild_id:
                filters.append(f"Guild: {guild_id}")
            click.echo(f"Symbols ({', '.join(filters)}):")
        else:
            click.echo("All symbols:")

        click.echo(table_str)
        click.echo(f"\nTotal symbols: {len(rows)}")
        click.echo()

    except Exception as e:
        logger.error(f"Error listing symbols: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing symbols: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("populate-tickers")
@click.pass_context
def populate_tickers(ctx):
    """Populate tickers from Wikipedia (S&P 500 + DOW 30)"""
    db = ctx.obj["db"]
    tickers = Tickers(db)

    try:
        click.echo()
        click.secho("📊 TICKER POPULATION", bold=True)
        click.echo("=" * 60)
        click.echo("Fetching ticker data from Wikipedia...")
        click.echo("Sources: S&P 500 and DOW Jones Industrial Average")
        click.echo("=" * 60)
        click.echo()

        stats = tickers.populate_from_wikipedia()

        click.echo("=" * 60)
        click.secho("POPULATION RESULTS", bold=True)
        click.echo("=" * 60)
        click.echo(f"S&P 500 tickers inserted: {stats['sp500']:,}")
        click.echo(f"DOW 30 tickers inserted:  {stats['dow']:,}")
        click.echo(f"Total active tickers:     {stats['total']:,}")

        if stats["errors"]:
            click.echo()
            click.secho("Errors encountered:", fg="yellow")
            for error in stats["errors"]:
                click.echo(f"  - {error}")

        click.echo("=" * 60)
        click.secho("\n✓ Ticker population complete", fg="green", bold=True)
        click.echo()

    except Exception as e:
        logger.error(f"Error populating tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error populating tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("team-stats")
@click.option(
    "--report", type=click.Choice(["options_by_yearmonth"]), required=True, help="Report type"
)
@click.option("--username", help="Filter by username")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def team_stats(ctx, report, username, account, guild_id):
    """Show team-wide trading statistics"""
    db = ctx.obj["db"]

    try:
        logger.info(
            f"Showing team_stats report: {report}, user: {username}, account: {account}, guild_id: {guild_id}"
        )

        df_stats = DFStats(db)
        df_stats.load(username, account=account, guild_id=guild_id)

        if report == "options_by_yearmonth":
            table_str = df_stats.options_by_yearmonth()

            click.echo()
            click.echo("=" * 80)
            click.secho("TEAM STATISTICS - OPTIONS BY YEAR/MONTH", bold=True)
            if username:
                click.echo(f"User: {username}")
            if account:
                click.echo(f"Account: {account}")
            if guild_id:
                click.echo(f"Guild: {guild_id}")
            click.echo("=" * 80)
            click.echo()
            click.echo(table_str)
            click.echo()
            click.echo("=" * 80)
            click.echo()
        else:
            logger.warning(f"Report {report} not found")
            click.secho(f"\n✗ Report '{report}' not found\n", fg="red")
            click.echo("Available reports: options_by_yearmonth")
            ctx.exit(1)

    except Exception as e:
        logger.error(f"Error showing team_stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing team statistics: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("message-stats")
@click.pass_context
def message_stats(ctx):
    """Show message harvesting statistics (system-wide)"""
    db = ctx.obj["db"]

    try:
        messages = Messages(db)
        logger.info("Showing message harvesting statistics")

        # Overall stats
        total = messages.count(include_deleted=True)
        active = messages.count(include_deleted=False)
        deleted = total - active

        click.echo()
        click.echo("=" * 80)
        click.secho("MESSAGE HARVESTING STATISTICS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total messages:   {total:,}")
        click.echo(f"Active messages:  {active:,}")
        click.echo(f"Deleted messages: {deleted:,}")
        click.echo()

        # Channel breakdown
        channel_stats = messages.get_channel_stats()
        if channel_stats:
            click.secho("MESSAGES BY CHANNEL:", bold=True)
            click.echo("=" * 80)

            table_data = []
            for channel_name, stats in channel_stats.items():
                table_data.append(
                    [
                        channel_name,
                        f"{stats['total']:,}",
                        f"{stats['active']:,}",
                        f"{stats['deleted']:,}",
                    ]
                )

            click.echo(
                tabulate(
                    table_data, headers=["Channel", "Total", "Active", "Deleted"], tablefmt="psql"
                )
            )
            click.echo("=" * 80)

        click.echo()

    except Exception as e:
        logger.error(f"Error showing message stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing message stats: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("delete-all")
@click.option("--username", required=True, help="Username of transaction owner")
@click.option("--account", required=True, help="Account name (required for safety)")
@click.confirmation_option(
    prompt="⚠️  This will delete ALL transactions for this user+account. Are you sure?"
)
@click.pass_context
def delete_all(ctx, username, account):
    """Delete all transactions for a user and account (DANGEROUS)"""
    db = ctx.obj["db"]

    trades = Trades(db)
    dividends = Dividends(db)
    shares = Shares(db)
    deposits = Deposits(db)

    try:
        logger.warning(f"Deleting all transactions for user {username} account {account}")

        # Delete from all transaction tables
        options_cnt = trades.delete_all(username, account)
        dividends_cnt = dividends.delete_all(username, account)
        shares_cnt = shares.delete_all(username, account)
        deposits_cnt = deposits.delete_all(username, account)

        total = options_cnt + dividends_cnt + shares_cnt + deposits_cnt

        # Display results
        click.echo()
        click.echo("=" * 60)
        click.secho("DELETION SUMMARY", bold=True)
        click.echo("=" * 60)
        click.echo(f"User:              {username}")
        click.echo(f"Account:           {account}")
        click.echo()
        click.echo(f"Options deleted:   {options_cnt}")
        click.echo(f"Dividends deleted: {dividends_cnt}")
        click.echo(f"Shares deleted:    {shares_cnt}")
        click.echo(f"Deposits deleted:  {deposits_cnt}")
        click.echo("=" * 60)
        click.secho(f"Total deleted:     {total}", bold=True)
        click.echo("=" * 60)
        click.echo()

        if total > 0:
            click.secho(f"✓ Successfully deleted {total} transactions", fg="green", bold=True)
        else:
            click.secho("No transactions found to delete", fg="yellow")

        logger.info(
            f"Deleted {options_cnt} options, {dividends_cnt} dividends, "
            f"{shares_cnt} shares, {deposits_cnt} deposits"
        )

    except Exception as e:
        logger.error(f"Error deleting transactions: {e}", exc_info=True)
        click.secho(f"\n✗ Error deleting transactions: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("add-model")
@click.option("--model-key", required=True, help='Model key (e.g., "claude-opus")')
@click.option(
    "--litellm-model", required=True, help='LiteLLM model string (e.g., "claude-opus-4-5-20250929")'
)
@click.option("--display-name", required=True, help='Display name (e.g., "Claude Opus 4.5")')
@click.option("--description", required=True, help="Description of model capabilities")
@click.option(
    "--cost-tier", type=click.Choice(["free", "budget", "premium"]), required=True, help="Cost tier"
)
@click.option("--quality", type=int, required=True, help="Quality rating 1-10")
@click.option(
    "--speed",
    type=click.Choice(["very-fast", "fast", "medium", "slow"]),
    required=True,
    help="Speed rating",
)
@click.option("--tool-calling/--no-tool-calling", default=True, help="Supports tool calling")
@click.option(
    "--provider", required=True, help='Provider name (e.g., "anthropic", "openai", "ollama")'
)
@click.option("--active/--inactive", default=True, help="Is active")
@click.option("--default/--no-default", default=False, help="Set as system default")
@click.pass_context
def add_model(
    ctx,
    model_key,
    litellm_model,
    display_name,
    description,
    cost_tier,
    quality,
    speed,
    tool_calling,
    provider,
    active,
    default,
):
    """
    Add or update an LLM model in the database.

    This is an administrative command for managing the LLM model registry.
    Models can be added, updated, activated, or deactivated.
    """
    from llm_models import LLMModel, LLMModels

    db = ctx.obj["db"]
    llm_models = LLMModels(db)

    try:
        # Create model object
        model = LLMModel(
            model_key=model_key,
            litellm_model=litellm_model,
            display_name=display_name,
            description=description,
            cost_tier=cost_tier,
            quality=quality,
            speed=speed,
            tool_calling=tool_calling,
            provider=provider,
            is_active=active,
            is_default=default,
        )

        # Add model to database
        llm_models.add_model(model)

        click.echo()
        click.secho("✓ Model added successfully", fg="green", bold=True)
        click.echo()
        click.echo("=" * 60)
        click.echo(f"Model Key:     {model_key}")
        click.echo(f"Display Name:  {display_name}")
        click.echo(f"Provider:      {provider}")
        click.echo(f"Cost Tier:     {cost_tier}")
        click.echo(f"Quality:       {quality}/10")
        click.echo(f"Speed:         {speed}")
        click.echo(f"Tool Calling:  {'✓' if tool_calling else '✗'}")
        click.echo(f"Active:        {'✓' if active else '✗'}")
        click.echo(f"Default:       {'✓' if default else '✗'}")
        click.echo("=" * 60)
        click.echo()

        logger.info(f"Added model: {model_key}")

    except Exception as e:
        logger.error(f"Error adding model: {e}", exc_info=True)
        click.secho(f"\n✗ Error adding model: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("rm-model")
@click.argument("model_key")
@click.confirmation_option(prompt="⚠️  This will deactivate the model (soft delete). Continue?")
@click.pass_context
def rm_model(ctx, model_key):
    """
    Remove (deactivate) an LLM model.

    MODEL_KEY: The model key to remove (e.g., 'claude-sonnet')

    This is a soft delete - the model is marked inactive but not removed
    from the database. Cannot remove the default model.
    """
    from llm_models import LLMModels

    db = ctx.obj["db"]
    llm_models = LLMModels(db)

    try:
        # Check if model exists
        model = llm_models.get_model(model_key)
        if not model:
            click.secho(f"\n✗ Model not found: {model_key}\n", fg="red", err=True)
            ctx.exit(1)
            return  # Helps mypy understand flow

        # Check if it's the default
        if model.is_default:
            click.secho(f"\n✗ Cannot remove default model: {model_key}", fg="red", err=True)
            click.echo("Set a new default model first with 'admin set-default-model'\n")
            ctx.exit(1)

        # Soft delete
        success = llm_models.delete_model(model_key)

        if success:
            click.echo()
            click.secho(f"✓ Model deactivated: {model_key}", fg="green", bold=True)
            click.echo(f"  Display Name: {model.display_name}")
            click.echo()
            logger.info(f"Deactivated model: {model_key}")
        else:
            click.secho(f"\n✗ Failed to deactivate model: {model_key}\n", fg="red", err=True)
            ctx.exit(1)

    except Exception as e:
        logger.error(f"Error removing model: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing model: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("set-default-model")
@click.argument("model_key")
@click.pass_context
def set_default_model(ctx, model_key):
    """
    Set the system-wide default LLM model.

    MODEL_KEY: The model key to set as default (e.g., 'ollama-qwen-32b')

    This becomes the default for all users who haven't set a preference.
    Only one model can be the default at a time.
    """
    from llm_models import LLMModels

    db = ctx.obj["db"]
    llm_models = LLMModels(db)

    try:
        # Check if model exists
        model = llm_models.get_model(model_key)
        if not model:
            click.secho(f"\n✗ Model not found: {model_key}\n", fg="red", err=True)
            click.echo("Run 'cli.py llm list-models' to see available models.")
            ctx.exit(1)
            return  # Helps mypy understand flow

        if not model.is_active:
            click.secho(
                f"\n✗ Cannot set inactive model as default: {model_key}\n", fg="red", err=True
            )
            ctx.exit(1)

        # Set as default
        success = llm_models.set_default_model(model_key)

        if success:
            click.echo()
            click.secho("✓ Default model updated", fg="green", bold=True)
            click.echo()
            click.echo("=" * 60)
            click.echo(f"Model Key:     {model.model_key}")
            click.echo(f"Display Name:  {model.display_name}")
            click.echo(f"Provider:      {model.provider}")
            click.echo(f"Quality:       {model.quality}/10")
            click.echo("=" * 60)
            click.echo()
            logger.info(f"Set default model to: {model_key}")
        else:
            click.secho("\n✗ Failed to set default model\n", fg="red", err=True)
            ctx.exit(1)

    except Exception as e:
        logger.error(f"Error setting default model: {e}", exc_info=True)
        click.secho(f"\n✗ Error setting default model: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("metrics")
@click.option("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
@click.option(
    "--type",
    type=click.Choice(["commands", "llm", "mcp", "users", "trends", "errors"]),
    default="commands",
    help="Type of metrics to view (default: commands)",
)
@click.option("--export", help="Export to CSV file (optional)")
@click.pass_context
def metrics(ctx, days, type, export):
    """
    View bot usage metrics and statistics.

    Displays comprehensive metrics about bot usage including:
    - commands: Most used commands
    - llm: LLM usage statistics
    - mcp: MCP tool usage
    - users: User activity
    - trends: Usage trends over time
    - errors: Error rates and types

    Examples:
      cli.py admin metrics --days 30 --type commands
      cli.py admin metrics --type users --export users.csv
    """
    from metrics import MetricsTracker

    db = ctx.obj["db"]

    try:
        click.echo()
        click.echo("📊 Analyzing bot usage metrics...")
        click.echo(f"   Period: Last {days} days")
        click.echo(f"   Type: {type}")
        click.echo()

        metrics_tracker = MetricsTracker(db)

        # Get metrics based on type
        if type == "commands":
            data = metrics_tracker.get_command_stats(days=days)
            click.echo("=" * 80)
            click.secho("COMMAND USAGE STATISTICS", bold=True)
            click.echo("=" * 80)
            if data:
                table_data = [[cmd, count, f"{pct:.1f}%"] for cmd, count, pct in data]
                click.echo(
                    tabulate(
                        table_data, headers=["Command", "Count", "Percentage"], tablefmt="psql"
                    )
                )
            else:
                click.echo("No command data available")

        elif type == "llm":
            data = metrics_tracker.get_llm_stats(days=days)  # type: ignore[attr-defined]
            click.echo("=" * 80)
            click.secho("LLM USAGE STATISTICS", bold=True)
            click.echo("=" * 80)
            if data:
                click.echo(tabulate(data, headers="keys", tablefmt="psql"))
            else:
                click.echo("No LLM usage data available")

        elif type == "mcp":
            data = metrics_tracker.get_mcp_tool_stats(days=days)  # type: ignore[assignment]
            click.echo("=" * 80)
            click.secho("MCP TOOL USAGE STATISTICS", bold=True)
            click.echo("=" * 80)
            if data:
                table_data = [[tool, count] for tool, count in data]  # type: ignore[misc]
                click.echo(tabulate(table_data, headers=["Tool", "Count"], tablefmt="psql"))
            else:
                click.echo("No MCP tool usage data available")

        elif type == "users":
            data = metrics_tracker.get_user_activity(days=days)
            click.echo("=" * 80)
            click.secho("USER ACTIVITY STATISTICS", bold=True)
            click.echo("=" * 80)
            if data:
                table_data = [[user, commands, f"{pct:.1f}%"] for user, commands, pct in data]
                click.echo(
                    tabulate(
                        table_data, headers=["User", "Commands", "Percentage"], tablefmt="psql"
                    )
                )
            else:
                click.echo("No user activity data available")

        elif type == "trends":
            trends_data = metrics_tracker.get_daily_activity(days=days)
            click.echo("=" * 80)
            click.secho("DAILY ACTIVITY TRENDS", bold=True)
            click.echo("=" * 80)
            if trends_data:
                table_data = [
                    [date, commands, llm_calls, f"${cost:.2f}"]
                    for date, commands, llm_calls, cost in trends_data
                ]
                click.echo(
                    tabulate(
                        table_data,
                        headers=["Date", "Commands", "LLM Calls", "Cost"],
                        tablefmt="psql",
                    )
                )
            else:
                click.echo("No trend data available")

        elif type == "errors":
            data = metrics_tracker.get_error_summary(days=days)  # type: ignore[assignment]
            click.echo("=" * 80)
            click.secho("ERROR SUMMARY", bold=True)
            click.echo("=" * 80)
            if data:
                table_data = [[cmd, error_type, count] for cmd, error_type, count in data]
                click.echo(
                    tabulate(
                        table_data, headers=["Command", "Error Type", "Count"], tablefmt="psql"
                    )
                )
            else:
                click.echo("No error data available")

        click.echo("=" * 80)
        click.echo()

        # Export if requested
        if export and data:
            import pandas as pd

            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])
            df.to_csv(export, index=False)
            click.secho(f"✓ Exported to: {export}", fg="green")
            click.echo()

    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}", exc_info=True)
        click.secho(f"\n✗ Error retrieving metrics: {e}\n", fg="red", err=True)
        ctx.exit(1)


async def _process_harvested_messages(
    db, process_images: bool, analyze_sentiment: bool, vision_model: str | None = None
):
    """
    Post-process harvested messages with vision extraction and/or sentiment analysis.

    This helper function runs after harvest completes to ensure historical data
    is fully processed with the new Pydantic validators.

    Args:
        db: Database instance
        process_images: Whether to process images with vision model
        analyze_sentiment: Whether to analyze sentiment
        vision_model: Optional vision model override
    """
    click.echo()
    click.echo("=" * 80)
    click.secho("POST-PROCESSING", bold=True)
    click.echo("=" * 80)

    # Image processing
    if process_images:
        click.echo()
        click.secho("🔍 Processing images with vision model...", fg="cyan", bold=True)

        settings = get_settings(db)
        model_to_use = vision_model or settings.get(const.SETTING_VISION_OCR_MODEL)

        # Query messages with images that haven't been processed yet
        query = """
            SELECT message_id, attachment_urls
            FROM harvested_messages
            WHERE has_attachments = 1
            AND attachment_urls IS NOT NULL
            AND attachment_urls != ''
            AND (extracted_data IS NULL OR extracted_data = '')
            ORDER BY timestamp DESC
        """
        rows = db.query(query, None)

        if not rows:
            click.echo("  No unprocessed images found")
        else:
            click.echo(f"  Found {len(rows)} messages with unprocessed images")

            stats = {
                "total": 0,
                "successful": 0,
                "errors": 0,
                "trades_found": 0,
                "validation_passed": 0,
                "validation_failed": 0,
            }

            for idx, (message_id, attachment_urls_str) in enumerate(rows, 1):
                try:
                    urls = json.loads(attachment_urls_str)
                except json.JSONDecodeError:
                    continue

                if not urls:
                    continue

                # Process first image
                url = urls[0]

                try:
                    # Analyze image with vision model
                    result = await analyze_trading_image(url, ocr_model=model_to_use)

                    stats["total"] += 1

                    if result.get("image_type") == "error":
                        stats["errors"] += 1
                    else:
                        stats["successful"] += 1

                        # Count trades (these were validated by Pydantic!)
                        if result.get("trades"):
                            stats["trades_found"] += len(result["trades"])
                            stats["validation_passed"] += len(result["trades"])

                        # Update database
                        db.query_parameterized(
                            """
                            UPDATE harvested_messages
                            SET extracted_data = ?
                            WHERE message_id = ?
                        """,
                            (json.dumps(result), message_id),
                        )

                    # Progress indicator
                    if idx % 10 == 0:
                        click.echo(f"    Processed {idx}/{len(rows)} images...")

                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Error processing image {url}: {e}")

            # Print results
            click.echo()
            click.secho("  Image Processing Results:", bold=True)
            click.echo(f"    Total processed:  {stats['total']}")
            click.echo(f"    Successful:       {stats['successful']}")
            click.echo(f"    Errors:           {stats['errors']}")
            click.echo(f"    Trades extracted: {stats['trades_found']} (all validated ✓)")
            click.echo()

    # Sentiment analysis
    if analyze_sentiment:
        click.echo()
        click.secho("💭 Analyzing sentiment...", fg="cyan", bold=True)

        # Query messages without sentiment analysis
        query = """
            SELECT message_id, content
            FROM harvested_messages
            WHERE (sentiment IS NULL OR sentiment = '')
            AND content != ''
            ORDER BY timestamp DESC
            LIMIT 100
        """
        rows = db.query(query, None)

        if not rows:
            click.echo("  No messages need sentiment analysis")
        else:
            click.echo(f"  Analyzing {len(rows)} messages...")

            from sentiment_analyzer import SentimentAnalyzer

            analyzer = SentimentAnalyzer(db)

            analyzed = 0
            for message_id, content in rows:
                try:
                    # Analyze sentiment (this updates the database)
                    analyzer.analyze_message(message_id)  # type: ignore[attr-defined]
                    analyzed += 1

                    if analyzed % 25 == 0:
                        click.echo(f"    Analyzed {analyzed}/{len(rows)} messages...")

                except Exception as e:
                    logger.error(f"Error analyzing sentiment for message {message_id}: {e}")

            click.echo(f"  ✓ Analyzed {analyzed} messages")
            click.echo()

    click.echo("=" * 80)
    click.secho("✓ Post-processing complete!", fg="green", bold=True)
    click.echo("=" * 80)
    click.echo()


@admin.command("harvest")
@click.option(
    "--days", type=int, default=7, help="Number of days of history to harvest (default: 7)"
)
@click.option("--channel", help="Only harvest from specific channel name")
@click.option("--guild-id", type=int, help="Only harvest from specific guild")
@click.pass_context
def harvest(ctx, days, channel, guild_id):
    """
    Harvest Discord message history into the database.

    Fetches messages from configured channels and stores them in harvested_messages
    table. Messages are stored WITHOUT processing - use separate commands for
    post-processing:

    Post-Processing Commands:
      admin batch-analyze-images: Extract trades from images (applies Pydantic validators)
      messages analyze-sentiment: Analyze sentiment for messages

    Examples:
      # Harvest messages only
      cli.py admin harvest --days 30
      cli.py admin harvest --days 7 --channel "darkminer-moves"
      cli.py admin harvest --days 1 --guild-id 1349592236375019520

      # Then process separately
      cli.py admin batch-analyze-images --limit 1000 --update-db
      cli.py messages analyze-sentiment --days 30 --update-db
    """
    import discord
    from discord.ext import commands as discord_commands

    try:
        # Get Discord token
        token = const.TOKEN
        if not token:
            click.secho("\n✗ Error: DISCORD_TOKEN not found in environment\n", fg="red", err=True)
            click.secho("💡 Add DISCORD_TOKEN to your .env file\n", fg="cyan")
            ctx.exit(1)

        click.echo()
        click.secho("🌾 MESSAGE HARVESTER", bold=True)
        click.echo("=" * 80)
        click.echo(f"Days to harvest: {days}")
        if channel:
            click.echo(f"Channel filter:  {channel}")
        if guild_id:
            click.echo(f"Guild filter:    {guild_id}")
        click.echo("=" * 80)
        click.echo()

        # Create Discord bot instance
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True

        bot = discord_commands.Bot(command_prefix="!", intents=intents)
        db = ctx.obj["db"]
        messages_obj = Messages(db)

        harvest_stats = {
            "total_messages": 0,
            "new_messages": 0,
            "channels_processed": 0,
            "errors": 0,
        }

        @bot.event
        async def on_ready():
            """Run harvest when bot is ready"""
            try:
                click.secho(f"✓ Connected as {bot.user}", fg="green")
                click.echo()

                guild_channels = GuildChannels(db)

                # Get guilds to harvest
                if guild_id:
                    guilds = [bot.get_guild(guild_id)]
                    if not guilds[0]:
                        click.secho(f"✗ Guild {guild_id} not found or bot not member", fg="red")
                        await bot.close()
                        return
                else:
                    guilds = bot.guilds  # type: ignore[assignment]

                # Process each guild
                for guild in guilds:
                    if not guild:
                        continue

                    click.echo(f"Processing guild: {guild.name} ({guild.id})")

                    # Get configured channels for this guild
                    channels = guild_channels.get_channels_for_guild(guild.id)

                    if not channels:
                        click.secho(f"  No configured channels for guild {guild.id}", fg="yellow")
                        continue

                    # Filter by channel name if specified
                    if channel:
                        channels = [
                            ch for ch in channels if ch[1] == channel
                        ]  # ch[1] is channel_name

                    if not channels:
                        click.secho(f"  Channel '{channel}' not found in guild", fg="yellow")
                        continue

                    # Harvest each channel
                    # channels is list of tuples: (channel_id, channel_name, category)
                    for ch_config in channels:
                        channel_id, channel_name, category = ch_config
                        discord_channel = bot.get_channel(channel_id)

                        if not discord_channel:
                            click.secho(f"  ✗ Channel {channel_name} not accessible", fg="red")
                            harvest_stats["errors"] += 1
                            continue

                        click.echo(f"  Harvesting #{channel_name}...")
                        click.echo(f"    Channel ID: {channel_id}")
                        click.echo(f"    Channel type: {type(discord_channel).__name__}")

                        try:
                            # Calculate time window
                            from datetime import datetime, timedelta, timezone

                            after_date = datetime.now(timezone.utc) - timedelta(days=days)
                            click.echo(f"    After date: {after_date.isoformat()}")

                            msg_count = 0
                            new_count = 0

                            # Fetch messages
                            async for msg in discord_channel.history(limit=None, after=after_date):  # type: ignore[union-attr]
                                if msg_count == 0:
                                    click.echo(
                                        f"    First message found: {msg.id} at {msg.created_at.isoformat()}"
                                    )
                                harvest_stats["total_messages"] += 1
                                msg_count += 1

                                # Store message
                                from message import Message as MsgClass

                                message_obj = MsgClass.from_discord_message(msg, category=category)

                                is_new = messages_obj.insert(message_obj)
                                if is_new:
                                    harvest_stats["new_messages"] += 1
                                    new_count += 1

                            harvest_stats["channels_processed"] += 1
                            click.secho(f"    ✓ {msg_count} messages ({new_count} new)", fg="green")

                        except Exception as e:
                            click.secho(f"    ✗ Error: {e}", fg="red")
                            harvest_stats["errors"] += 1
                            logger.error(
                                f"Error harvesting channel {channel_name}: {e}", exc_info=True
                            )

                # Print summary
                click.echo()
                click.echo("=" * 80)
                click.secho("HARVEST SUMMARY", bold=True)
                click.echo("=" * 80)
                click.echo(f"Channels processed: {harvest_stats['channels_processed']}")
                click.echo(f"Total messages:     {harvest_stats['total_messages']:,}")
                click.echo(f"New messages:       {harvest_stats['new_messages']:,}")
                click.echo(f"Errors:             {harvest_stats['errors']}")
                click.echo("=" * 80)
                click.echo()

                if harvest_stats["new_messages"] > 0:
                    click.secho(
                        f"✓ Harvest complete! {harvest_stats['new_messages']} new messages stored",
                        fg="green",
                        bold=True,
                    )
                else:
                    click.secho("✓ Harvest complete (no new messages)", fg="green")

                click.echo()
                click.secho("💡 Next steps:", fg="cyan")
                click.echo(
                    "  1. Process images:   admin batch-analyze-images --limit 1000 --update-db"
                )
                click.echo(
                    "  2. Analyze sentiment: messages analyze-sentiment --days 30 --update-db"
                )
                click.echo()

            except Exception as e:
                click.secho(f"\n✗ Harvest error: {e}\n", fg="red", err=True)
                logger.error(f"Harvest error: {e}", exc_info=True)
            finally:
                await bot.close()

        # Run bot
        bot.run(token, log_handler=None)  # type: ignore[arg-type]

    except Exception as e:
        logger.error(f"Error running harvest: {e}", exc_info=True)
        click.secho(f"\n✗ Error running harvest: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("batch-analyze-images")
@click.option("--limit", type=int, default=100, help="Number of images to analyze (default: 100)")
@click.option("--update-db", is_flag=True, help="Update database with extracted_data")
@click.option("--force", is_flag=True, help="Re-process already processed images")
@click.option("--quiet", is_flag=True, help="Suppress per-image output, show only summary")
@click.option(
    "--model",
    default=None,
    help="Vision model to use (default: from VISION_OCR_MODEL in constants)",
)
@click.option(
    "--api-base", default=None, help="Ollama API base URL (e.g., http://yoda.local:11434)"
)
@click.pass_context
def batch_analyze_images(ctx, limit, update_db, force, quiet, model, api_base):
    """
    Batch analyze Discord message images with vision model.

    Processes images from harvested messages and extracts structured trading data
    (ticker symbols, trades, sentiment, etc.). Generates detailed analysis report
    with success rate, performance, and cost estimation.

    Examples:
      cli.py admin batch-analyze-images --limit 100
      cli.py admin batch-analyze-images --limit 50 --update-db
      cli.py admin batch-analyze-images --model ollama/llava:13b --limit 10
      cli.py admin batch-analyze-images --model claude-sonnet-4-5-20250929 --limit 100
    """
    db = ctx.obj["db"]

    try:
        # Use default model from system settings if not specified
        settings = get_settings(db)
        model = model or settings.get(const.SETTING_VISION_OCR_MODEL)

        # Get messages with images (include content for text+image merging)
        if force:
            # Process all images (including already processed)
            query = """
                SELECT message_id, attachment_urls, content
                FROM harvested_messages
                WHERE has_attachments = 1
                AND attachment_urls IS NOT NULL
                AND attachment_urls != ''
                ORDER BY timestamp DESC
                LIMIT ?
            """
        else:
            # Process only unprocessed images
            query = """
                SELECT message_id, attachment_urls, content
                FROM harvested_messages
                WHERE has_attachments = 1
                AND attachment_urls IS NOT NULL
                AND attachment_urls != ''
                AND (extracted_data IS NULL OR extracted_data = '' OR extracted_data = '{}')
                ORDER BY timestamp DESC
                LIMIT ?
            """
        rows = db.query_parameterized(query, (limit,))

        if not rows:
            click.echo()
            click.secho("✗ No messages with images found in database", fg="yellow")
            click.secho("💡 Tip: Run harvest first: cli.py admin harvest --days 30", fg="cyan")
            click.echo()
            return

        messages = rows

        click.echo()
        click.secho("🔍 BATCH IMAGE ANALYSIS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Images to process: {len(messages)}")
        click.echo(f"Vision model:      {model}")
        click.echo(f"Update database:   {'Yes' if update_db else 'No'}")
        click.echo(f"Force reprocess:   {'Yes' if force else 'No (unprocessed only)'}")
        click.echo("=" * 80)
        click.echo()

        # Track results
        stats: dict[str, Any] = {
            "total": 0,
            "successful": 0,
            "errors": 0,
            "trades_found": 0,
            "tickers_found": 0,
            "total_time": 0.0,
            "image_types": {},
            "sentiments": {"bullish": 0, "bearish": 0, "neutral": 0},
            "sample_trades": [],
        }

        async def process_images():
            """Process all images asynchronously"""
            for idx, (message_id, attachment_urls_str, message_content) in enumerate(messages, 1):
                # Parse attachment URLs
                try:
                    urls = json.loads(attachment_urls_str)
                except json.JSONDecodeError:
                    click.echo(f"  [{idx}/{len(messages)}] Skipping - invalid attachment_urls")
                    continue

                if not urls:
                    continue

                # Use first image URL
                url = urls[0]

                # Process trades from both text and images (matching live bot behavior)
                start = time.time()

                text_data = None
                image_data = None

                # Step 1: Parse text-based trades if present (same logic as image_processing_queue.py)
                has_text = bool(message_content and len(message_content.strip()) >= 10)
                if has_text:
                    text_data = await analyze_text_trades(message_content)

                # Step 2: Parse image-based trades
                image_data = await analyze_trading_image(url, ocr_model=model, api_base=api_base)

                # Step 3: Merge results (same logic as image_processing_queue.py)
                if text_data and image_data:
                    # Both sources - merge trades
                    result = image_data.copy()
                    result["trades"] = text_data.get("trades", []) + image_data.get("trades", [])
                    result["tickers"] = list(
                        set(text_data.get("tickers", []) + image_data.get("tickers", []))
                    )
                    result["raw_text"] = (
                        f"{message_content}\n\n--- IMAGE OCR ---\n{image_data.get('raw_text', '')}"
                    )
                elif text_data:
                    # Text only
                    result = text_data
                elif image_data:
                    # Image only
                    result = image_data
                else:
                    result = {"image_type": "error", "trades": [], "tickers": []}

                elapsed = time.time() - start

                # Update stats
                stats["total"] += 1
                stats["total_time"] += elapsed

                if result.get("image_type") == "error":
                    stats["errors"] += 1
                else:
                    stats["successful"] += 1

                # Track image type
                img_type = result.get("image_type", "unknown")
                stats["image_types"][img_type] = stats["image_types"].get(img_type, 0) + 1

                # Track sentiment
                sentiment = result.get("sentiment", "neutral")
                stats["sentiments"][sentiment] += 1

                # Track trades and tickers
                if result.get("trades"):
                    stats["trades_found"] += len(result["trades"])
                    # Keep first 5 trade samples
                    if len(stats["sample_trades"]) < 5:
                        stats["sample_trades"].append({"url": url, "result": result})

                if result.get("tickers"):
                    stats["tickers_found"] += len(result["tickers"])

                # Update database if requested
                if update_db and result.get("image_type") != "error":
                    db.query_parameterized(
                        """
                        UPDATE harvested_messages
                        SET extracted_data = ?
                        WHERE message_id = ?
                    """,
                        (json.dumps(result), message_id),
                    )

                # Progress indicator (verbose or quiet)
                if not quiet:
                    # Verbose mode: show per-image details
                    trades_count = len(result.get("trades", []))
                    tickers = result.get("tickers", [])

                    status = f"  [{idx}/{len(messages)}] {img_type:20s} | {elapsed:4.1f}s"

                    if trades_count > 0:
                        status += f" | {trades_count} trades"
                    if tickers:
                        status += f" | {', '.join(tickers[:3])}"

                    click.echo(status)
                # Quiet mode: just show progress dots
                elif idx % 10 == 0 or idx == len(messages):
                    click.echo(f"Progress: {idx}/{len(messages)}", nl=False)
                    click.echo("\r", nl=False)

        # Run async processing
        asyncio.run(process_images())

        # Print analysis report
        click.echo()
        click.echo("=" * 80)
        click.secho("ANALYSIS REPORT", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Overall statistics
        success_pct = (stats["successful"] / stats["total"] * 100) if stats["total"] > 0 else 0
        error_pct = (stats["errors"] / stats["total"] * 100) if stats["total"] > 0 else 0

        click.secho("OVERALL STATISTICS:", bold=True)
        click.echo(f"  Total processed:  {stats['total']}")
        click.echo(f"  Successful:       {stats['successful']} ({success_pct:.1f}%)")
        click.echo(f"  Errors:           {stats['errors']} ({error_pct:.1f}%)")
        click.echo(f"  Trades extracted: {stats['trades_found']}")
        click.echo(f"  Tickers found:    {stats['tickers_found']}")
        click.echo()

        # Performance
        avg_time = stats["total_time"] / stats["total"] if stats["total"] > 0 else 0
        click.secho("PERFORMANCE:", bold=True)
        click.echo(f"  Total time:       {stats['total_time']:.2f} seconds")
        click.echo(f"  Average/image:    {avg_time:.2f} seconds")
        click.echo(f"  Est. 1,110 imgs:  {avg_time * 1110 / 60:.1f} minutes")
        click.echo()

        # Cost estimation (Claude Sonnet 4.5: $0.003/image)
        cost_per_image = 0.003
        click.secho("COST ESTIMATION (Claude Sonnet 4.5):", bold=True)
        click.echo(f"  This batch:       ${stats['total'] * cost_per_image:.2f}")
        click.echo(f"  Full 1,110 imgs:  ${1110 * cost_per_image:.2f}")
        click.echo()

        # Image type distribution
        if stats["image_types"]:
            click.secho("IMAGE TYPES:", bold=True)
            for img_type, count in sorted(
                stats["image_types"].items(), key=lambda x: x[1], reverse=True
            ):
                pct = count / stats["total"] * 100
                click.echo(f"  {img_type.replace('_', ' ').title():20s}: {count:3d} ({pct:5.1f}%)")
            click.echo()

        # Sentiment distribution
        click.secho("SENTIMENT:", bold=True)
        for sentiment, count in sorted(
            stats["sentiments"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = count / stats["total"] * 100
            click.echo(f"  {sentiment.title():20s}: {count:3d} ({pct:5.1f}%)")
        click.echo()

        # Sample trades
        if stats["sample_trades"]:
            click.secho("SAMPLE EXTRACTIONS:", bold=True)
            sample: dict[str, Any]
            for i, sample in enumerate(stats["sample_trades"], 1):
                result: dict[str, Any] = sample["result"]
                click.echo(f"\n  Sample #{i}:")
                click.echo(f"    Type:      {result.get('image_type')}")
                click.echo(f"    Sentiment: {result.get('sentiment')}")
                if result.get("tickers"):
                    click.echo(f"    Tickers:   {', '.join(result['tickers'])}")

                for j, trade in enumerate(result.get("trades", [])[:2], 1):
                    click.echo(
                        f"    Trade {j}:   {trade.get('operation')} {trade.get('contracts')}x "
                        f"{trade.get('symbol')} ${trade.get('strike')}{trade.get('option_type')} "
                        f"@ ${trade.get('premium')}"
                    )

        click.echo()
        click.echo("=" * 80)

        if update_db:
            click.secho(
                f"\n✓ Analysis complete! Database updated with {stats['successful']} results\n",
                fg="green",
                bold=True,
            )
        else:
            click.secho(
                "\n✓ Analysis complete! (use --update-db to persist results)\n",
                fg="green",
                bold=True,
            )

    except Exception as e:
        logger.error(f"Error in batch analysis: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("batch-analyze-text")
@click.option(
    "--limit", type=int, default=100, help="Number of text messages to analyze (default: 100)"
)
@click.option("--update-db", is_flag=True, help="Update database with extracted_data")
@click.option("--force", is_flag=True, help="Re-process already processed messages")
@click.option("--quiet", is_flag=True, help="Suppress per-message output, show only summary")
@click.option(
    "--model",
    default=None,
    help="LLM model to use (default: from TRADE_PARSING_MODEL in constants)",
)
@click.option(
    "--api-base", default=None, help="Ollama API base URL (e.g., http://yoda.local:11434)"
)
@click.pass_context
def batch_analyze_text(ctx, limit, update_db, force, quiet, model, api_base):
    """
    Batch analyze text-only Discord messages with trade parsing.

    Processes text messages (without images) from harvested messages and extracts
    structured trading data using the latest parsing improvements. This is useful
    for reprocessing historical messages after improvements to the parser.

    Examples:
      cli.py admin batch-analyze-text --limit 100
      cli.py admin batch-analyze-text --limit 500 --update-db --force
      cli.py admin batch-analyze-text --model ollama/qwen2.5-coder:7b --limit 1000
    """
    db = ctx.obj["db"]

    try:
        # Use default model from system settings if not specified
        settings = get_settings(db)
        model = model or settings.get(const.SETTING_TRADE_PARSING_MODEL)

        # Get text-only messages (no images, has content >= 10 chars)
        if force:
            # Process all text messages (including already processed)
            query = """
                SELECT message_id, content
                FROM harvested_messages
                WHERE content IS NOT NULL
                AND length(trim(content)) >= 10
                AND (has_attachments = 0 OR has_attachments IS NULL
                     OR attachment_urls IS NULL OR attachment_urls = '')
                ORDER BY timestamp DESC
                LIMIT ?
            """
        else:
            # Process only unprocessed text messages
            query = """
                SELECT message_id, content
                FROM harvested_messages
                WHERE content IS NOT NULL
                AND length(trim(content)) >= 10
                AND (has_attachments = 0 OR has_attachments IS NULL
                     OR attachment_urls IS NULL OR attachment_urls = '')
                AND (extracted_data IS NULL OR extracted_data = '' OR extracted_data = '{}')
                ORDER BY timestamp DESC
                LIMIT ?
            """
        rows = db.query_parameterized(query, (limit,))

        if not rows:
            click.echo()
            click.secho("✗ No text-only messages found in database", fg="yellow")
            click.secho("💡 Tip: Run harvest first: cli.py admin harvest --days 30", fg="cyan")
            click.echo()
            return

        messages = rows

        click.echo()
        click.secho("🔍 BATCH TEXT ANALYSIS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Messages to process: {len(messages)}")
        click.echo(f"Parsing model:       {model}")
        click.echo(f"Update database:     {'Yes' if update_db else 'No'}")
        click.echo(f"Force reprocess:     {'Yes' if force else 'No (unprocessed only)'}")
        click.echo("=" * 80)
        click.echo()

        # Track results
        stats: dict[str, Any] = {
            "total": 0,
            "successful": 0,
            "errors": 0,
            "trades_found": 0,
            "tickers_found": 0,
            "total_time": 0.0,
            "sample_trades": [],
        }

        async def process_text_messages():
            """Process all text messages asynchronously"""
            for idx, (message_id, message_content) in enumerate(messages, 1):
                if not message_content or len(message_content.strip()) < 10:
                    continue

                # Parse text trades using analyze_text_trades
                start = time.time()
                result = await analyze_text_trades(message_content)
                elapsed = time.time() - start

                # Update stats
                stats["total"] += 1
                stats["total_time"] += elapsed

                if result.get("image_type") == "error":
                    stats["errors"] += 1
                else:
                    stats["successful"] += 1

                # Track trades and tickers
                if result.get("trades"):
                    stats["trades_found"] += len(result["trades"])
                    # Keep first 5 trade samples
                    if len(stats["sample_trades"]) < 5:
                        stats["sample_trades"].append({"message_id": message_id, "result": result})

                if result.get("tickers"):
                    stats["tickers_found"] += len(result["tickers"])

                # Update database if requested
                if update_db and result.get("image_type") != "error":
                    db.query_parameterized(
                        """
                        UPDATE harvested_messages
                        SET extracted_data = ?
                        WHERE message_id = ?
                    """,
                        (json.dumps(result), message_id),
                    )

                # Progress indicator (verbose or quiet)
                if not quiet:
                    # Verbose mode: show per-message details
                    trades_count = len(result.get("trades", []))
                    tickers = result.get("tickers", [])

                    status = f"  [{idx}/{len(messages)}] {message_id} | {elapsed:4.2f}s"

                    if trades_count > 0:
                        status += f" | {trades_count} trades"
                    if tickers:
                        status += f" | {', '.join(tickers[:3])}"

                    click.echo(status)
                # Quiet mode: just show progress dots
                elif idx % 50 == 0 or idx == len(messages):
                    click.echo(f"Progress: {idx}/{len(messages)}", nl=False)
                    click.echo("\r", nl=False)

        # Run async processing
        asyncio.run(process_text_messages())

        # Print analysis report
        click.echo()
        click.echo("=" * 80)
        click.secho("ANALYSIS REPORT", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Overall statistics
        success_pct = (stats["successful"] / stats["total"] * 100) if stats["total"] > 0 else 0
        error_pct = (stats["errors"] / stats["total"] * 100) if stats["total"] > 0 else 0

        click.secho("OVERALL STATISTICS:", bold=True)
        click.echo(f"  Total processed:  {stats['total']}")
        click.echo(f"  Successful:       {stats['successful']} ({success_pct:.1f}%)")
        click.echo(f"  Errors:           {stats['errors']} ({error_pct:.1f}%)")
        click.echo(f"  Trades extracted: {stats['trades_found']}")
        click.echo(f"  Tickers found:    {stats['tickers_found']}")
        click.echo()

        # Performance
        avg_time = stats["total_time"] / stats["total"] if stats["total"] > 0 else 0
        click.secho("PERFORMANCE:", bold=True)
        click.echo(f"  Total time:       {stats['total_time']:.2f} seconds")
        click.echo(f"  Average/message:  {avg_time:.2f} seconds")

        # Get total text-only message count for estimation
        total_query = """
            SELECT COUNT(*) FROM harvested_messages
            WHERE content IS NOT NULL
            AND length(trim(content)) >= 10
            AND (has_attachments = 0 OR has_attachments IS NULL
                 OR attachment_urls IS NULL OR attachment_urls = '')
        """
        total_count = db.query_parameterized(total_query)[0][0]
        click.echo(f"  Est. all {total_count} msgs: {avg_time * total_count / 60:.1f} minutes")
        click.echo()

        # Sample trades
        if stats["sample_trades"]:
            click.secho("SAMPLE EXTRACTIONS:", bold=True)
            sample: dict[str, Any]
            for i, sample in enumerate(stats["sample_trades"], 1):
                result: dict[str, Any] = sample["result"]
                click.echo(f"\n  Sample #{i} (message {sample['message_id']}):")
                if result.get("tickers"):
                    click.echo(f"    Tickers:   {', '.join(result['tickers'])}")

                for j, trade in enumerate(result.get("trades", [])[:2], 1):
                    click.echo(
                        f"    Trade {j}:   {trade.get('operation')} {trade.get('contracts')}x "
                        f"{trade.get('symbol')} ${trade.get('strike')}{trade.get('option_type')} "
                        f"@ ${trade.get('premium')}"
                    )

        click.echo()
        click.echo("=" * 80)

        if update_db:
            click.secho(
                f"\n✓ Analysis complete! Database updated with {stats['successful']} results\n",
                fg="green",
                bold=True,
            )
        else:
            click.secho(
                "\n✓ Analysis complete! (use --update-db to persist results)\n",
                fg="green",
                bold=True,
            )

    except Exception as e:
        logger.error(f"Error in batch text analysis: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("ollama-models")
@click.option("--vision-only", is_flag=True, help="Show only vision-capable models")
@click.option("--url", default=None, help="Ollama server URL (default: from system settings)")
@click.pass_context
def ollama_models(ctx, vision_only, url):
    """
    List available Ollama models

    Shows all models available on the Ollama server, including size and metadata.
    Use --vision-only to filter for vision-capable models (llava, minicpm-v, etc.)
    """
    try:
        client = OllamaClient(base_url=url)

        # Check server availability first
        click.echo(f"Connecting to Ollama server at {client.base_url}...")
        if not client.is_available():
            click.secho(
                f"\n✗ Ollama server not available at {client.base_url}\n", fg="red", err=True
            )
            click.echo("Make sure Ollama is running and the URL is correct.")
            return

        click.secho("✓ Connected\n", fg="green")

        # Fetch models
        if vision_only:
            models = client.list_vision_models()
            title = "VISION-CAPABLE MODELS"
        else:
            models = client.list_models()
            title = "ALL MODELS"

        if not models:
            if vision_only:
                click.secho("\nNo vision models found on Ollama server\n", fg="yellow")
                click.echo("Available vision models: llava, minicpm-v, bakllava, moondream")
                click.echo("Install with: ollama pull llava:13b")
            else:
                click.secho("\nNo models found on Ollama server\n", fg="yellow")
            return

        # Format table
        table_data = []
        for model in models:
            name = model.get("name", "unknown")
            size_bytes = model.get("size", 0)
            size_str = client.format_model_size(size_bytes)
            modified = model.get("modified_at", "")

            # Format modified date
            if modified:
                try:
                    from dateutil import parser

                    dt = parser.parse(modified)
                    modified_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    modified_str = modified[:16] if len(modified) > 16 else modified
            else:
                modified_str = "unknown"

            table_data.append([name, size_str, modified_str])

        # Print table
        click.echo(f"{title} ({len(models)} found)")
        click.echo("=" * 80)
        headers = ["Model Name", "Size", "Last Modified"]
        table_str = tabulate(table_data, headers=headers, tablefmt="psql")
        click.echo(table_str)
        click.echo()

        # Show current vision model setting
        settings = get_settings()
        current_vision_model = settings.get(const.SETTING_VISION_OCR_MODEL)
        ollama_base_url = settings.get(const.SETTING_OLLAMA_BASE_URL)
        click.echo(f"Current VISION_OCR_MODEL setting: {current_vision_model}")
        click.echo(f"Current OLLAMA_BASE_URL: {ollama_base_url}")

        if vision_only and models:
            click.echo()
            click.secho("To use a vision model for image harvesting:", fg="cyan")
            click.echo("  1. Update VISION_OCR_MODEL in constants.py")
            click.echo("  2. Example: VISION_OCR_MODEL = 'ollama/llava:13b'")
            click.echo("  3. Set VISION_API_BASE = None (for Ollama models)")

        click.echo()

    except Exception as e:
        logger.error(f"Error listing Ollama models: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("ollama-info")
@click.argument("model_name")
@click.option("--url", default=None, help="Ollama server URL (default: from system settings)")
@click.pass_context
def ollama_info(ctx, model_name, url):
    """
    Get detailed information about a specific Ollama model

    Shows model configuration, parameters, and template information.

    Example: python src/cli.py admin ollama-info llava:13b
    """
    try:
        client = OllamaClient(base_url=url)

        # Check server availability
        if not client.is_available():
            click.secho(
                f"\n✗ Ollama server not available at {client.base_url}\n", fg="red", err=True
            )
            return

        # Get model info
        click.echo(f"Fetching info for model: {model_name}")
        info = client.get_model_info(model_name)

        if not info:
            click.secho(f"\n✗ Model '{model_name}' not found\n", fg="red", err=True)
            click.echo("Use 'admin ollama-models' to see available models")
            return

        # Print model info
        click.echo()
        click.secho(f"MODEL: {model_name}", bold=True)
        click.echo("=" * 80)

        # Basic info
        if "modelfile" in info:
            click.echo("\nModelfile:")
            click.echo("-" * 80)
            click.echo(info["modelfile"])

        if "parameters" in info:
            click.echo("\nParameters:")
            click.echo("-" * 80)
            click.echo(info["parameters"])

        if "template" in info:
            click.echo("\nTemplate:")
            click.echo("-" * 80)
            click.echo(info["template"][:500])  # Truncate if very long
            if len(info["template"]) > 500:
                click.echo("... (truncated)")

        # Show all other keys
        ignore_keys = {"modelfile", "parameters", "template"}
        other_data = {k: v for k, v in info.items() if k not in ignore_keys}

        if other_data:
            click.echo("\nOther Info:")
            click.echo("-" * 80)
            for key, value in other_data.items():
                if isinstance(value, (dict, list)):
                    click.echo(f"{key}: {json.dumps(value, indent=2)}")
                else:
                    click.echo(f"{key}: {value}")

        click.echo()

    except Exception as e:
        logger.error(f"Error getting model info: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("ollama-pull")
@click.argument("model_name")
@click.option("--url", default=None, help="Ollama server URL (default: from system settings)")
@click.pass_context
def ollama_pull(ctx, model_name, url):
    """
    Pull (download) a model from Ollama registry

    Downloads the specified model to the Ollama server with progress tracking.

    Examples:
        python src/cli.py admin ollama-pull llama3.2-vision:11b
        python src/cli.py admin ollama-pull granite3.2-vision:2b
        python src/cli.py admin ollama-pull minicpm-v
        python src/cli.py admin ollama-pull moondream
    """
    try:
        client = OllamaClient(base_url=url)

        # Check server availability
        if not client.is_available():
            click.secho(
                f"\n✗ Ollama server not available at {client.base_url}\n", fg="red", err=True
            )
            return

        click.echo(f"Pulling model: {model_name}")
        click.echo(f"Server: {client.base_url}")
        click.echo()

        # Track progress
        last_status = None
        last_digest = None

        for progress in client.pull_model(model_name, stream=True):
            status = progress.get("status", "")

            # Show status changes
            if status != last_status:
                if last_status:
                    click.echo()  # New line for new status
                click.echo(f"{status}...", nl=False)
                last_status = status

            # Show download progress
            if "total" in progress and "completed" in progress:
                total = progress["total"]
                completed = progress["completed"]
                digest = progress.get("digest", "")

                if total > 0:
                    pct = (completed / total) * 100
                    completed_mb = completed / (1024**2)
                    total_mb = total / (1024**2)

                    # Only update if digest changed (new layer)
                    if digest != last_digest:
                        if last_digest:
                            click.echo()  # New line for new layer
                        click.echo(f"\n  [{digest[:12]}] ", nl=False)
                        last_digest = digest

                    # Progress bar
                    bar_width = 40
                    filled = int(bar_width * completed / total)
                    bar = "█" * filled + "░" * (bar_width - filled)
                    click.echo(
                        f"\r  [{digest[:12]}] {bar} {pct:5.1f}% ({completed_mb:.1f}/{total_mb:.1f} MB)",
                        nl=False,
                    )

        click.echo()
        click.echo()
        click.secho(f"✓ Successfully pulled {model_name}\n", fg="green", bold=True)

        # Show model info
        models = client.list_models()
        for model in models:
            if model_name in model.get("name", ""):
                size_str = client.format_model_size(model.get("size", 0))
                click.echo(f"Model size: {size_str}")
                break

    except KeyboardInterrupt:
        click.echo()
        click.secho("\n✗ Pull cancelled by user\n", fg="yellow")
        click.echo("Note: Cancelled pulls can be resumed by running the command again")
        ctx.exit(1)
    except Exception as e:
        logger.error(f"Error pulling model: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("ollama-pull-vision-models")
@click.option("--url", default=None, help="Ollama server URL (default: from system settings)")
@click.pass_context
def ollama_pull_vision_models(ctx, url):
    """
    Pull all recommended vision models for testing

    Downloads the top 4 vision models for OCR comparison:
    - llama3.2-vision:11b (7-8 GB)
    - granite3.2-vision:2b (2 GB)
    - minicpm-v (5-6 GB)
    - moondream (1.7 GB)

    Total download size: ~16-18 GB
    """
    models_to_pull = [
        ("llama3.2-vision:11b", "~7-8 GB", "State-of-the-art, complex documents"),
        ("granite3.2-vision:2b", "~2 GB", "Document OCR specialist"),
        ("minicpm-v", "~5-6 GB", "High benchmarks, multilingual"),
        ("moondream", "~1.7 GB", "OCR-focused, edge optimized"),
    ]

    try:
        client = OllamaClient(base_url=url)

        # Check server availability
        if not client.is_available():
            click.secho(
                f"\n✗ Ollama server not available at {client.base_url}\n", fg="red", err=True
            )
            return

        # Show plan
        click.echo("VISION MODEL DOWNLOAD PLAN")
        click.echo("=" * 80)
        for model_name, size, description in models_to_pull:
            click.echo(f"  • {model_name:<25} {size:<12} {description}")
        click.echo()
        click.echo("Estimated total download: ~16-18 GB")
        click.echo(f"Server: {client.base_url}")
        click.echo()

        # Confirm
        click.confirm("Proceed with download?", abort=True)
        click.echo()

        # Pull each model
        for idx, (model_name, size, description) in enumerate(models_to_pull, 1):
            click.echo(f"[{idx}/{len(models_to_pull)}] Pulling {model_name}...")
            click.echo(f"       {description}")
            click.echo()

            # Invoke pull command for this model
            ctx.invoke(ollama_pull, model_name=model_name, url=url)
            click.echo()

        click.secho("=" * 80, fg="green")
        click.secho("✓ All vision models downloaded successfully!", fg="green", bold=True)
        click.secho("=" * 80, fg="green")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. List models: python src/cli.py admin ollama-models --vision-only")
        click.echo("  2. Run tests:   python scripts/compare_vision_models.py --single-url <url>")
        click.echo()

    except click.Abort:
        click.echo()
        click.secho("✗ Download cancelled\n", fg="yellow")
    except Exception as e:
        logger.error(f"Error pulling vision models: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-list")
@click.option("--category", help="Filter by category (llm, features, market, etc.)")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
@click.pass_context
def settings_list(ctx, category, format):
    """
    List all system settings.

    Examples:
      cli.py admin settings-list
      cli.py admin settings-list --category llm
      cli.py admin settings-list --format json
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        if format == "json":
            # JSON output
            if category:
                data = settings.get_by_category(category)
                click.echo(json.dumps(data, indent=2))
            else:
                data = settings.get_all_as_dict()
                click.echo(json.dumps(data, indent=2))
        else:
            # Table output
            click.echo()
            if category:
                condition = f"category = '{category}'"
                click.secho(f"SYSTEM SETTINGS - Category: {category}", bold=True)
            else:
                condition = None
                click.secho("SYSTEM SETTINGS - All", bold=True)

            click.echo("=" * 120)

            df = settings.as_df(filter=condition)
            if df.empty:
                click.secho("No settings found\n", fg="yellow")
            else:
                # Format output for display
                table_str = tabulate(
                    df.values, headers=settings.headers(), tablefmt="psql", stralign="left"
                )
                click.echo(table_str)
                click.echo()
                click.secho(f"Total: {len(df)} settings\n", fg="green")

    except Exception as e:
        logger.error(f"Error listing settings: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-get")
@click.option("--key", required=True, help="Setting key (e.g., llm.ollama_base_url)")
@click.pass_context
def settings_get(ctx, key):
    """
    Get a specific system setting.

    Examples:
      cli.py admin settings-get --key llm.ollama_base_url
      cli.py admin settings-get --key features.image_analysis_enabled
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        value = settings.get(key)

        if value is None:
            click.secho(f"\n✗ Setting '{key}' not found\n", fg="yellow")
            ctx.exit(1)

        click.echo()
        click.secho(f"Key: {key}", bold=True)
        click.echo(f"Value: {value}")
        click.echo(f"Type: {type(value).__name__}")
        click.echo()

    except Exception as e:
        logger.error(f"Error getting setting: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-set")
@click.option("--key", required=True, help="Setting key (e.g., llm.ollama_base_url)")
@click.option("--value", required=True, help="Setting value")
@click.option(
    "--value-type",
    type=click.Choice(["string", "int", "float", "bool", "json"]),
    help="Value type (auto-detected if not specified)",
)
@click.option("--category", help="Category (llm, features, market, etc.)")
@click.option("--description", help="Human-readable description")
@click.option("--username", default="admin", help="Username making the change (default: admin)")
@click.pass_context
def settings_set(ctx, key, value, value_type, category, description, username):
    """
    Set/update a system setting.

    Value type is auto-detected from the value string:
    - Integers: "123", "-456"
    - Floats: "1.5", "3.14"
    - Booleans: "true", "false", "yes", "no"
    - JSON: starts with { or [
    - String: everything else

    Examples:
      cli.py admin settings-set --key llm.ollama_base_url --value "http://jedi.local:11434" --category llm
      cli.py admin settings-set --key llm.temperature --value 0.7 --category llm
      cli.py admin settings-set --key features.image_analysis_enabled --value true --category features
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        # Auto-detect type if not specified
        if value_type:
            # Convert based on specified type
            if value_type == "int":
                typed_value = int(value)
            elif value_type == "float":
                typed_value = float(value)  # type: ignore[assignment]
            elif value_type == "bool":
                typed_value = value.lower() in ("true", "1", "yes")
            elif value_type == "json":
                typed_value = json.loads(value)
            else:
                typed_value = value
        else:
            # Auto-detect type
            typed_value = value
            # Try int
            try:
                typed_value = int(value)
            except ValueError:
                pass
            # Try float
            if isinstance(typed_value, str):
                try:
                    typed_value = float(value)
                except ValueError:
                    pass
            # Try bool
            if isinstance(typed_value, str):
                if value.lower() in ("true", "false", "yes", "no"):
                    typed_value = value.lower() in ("true", "yes")
            # Try JSON
            if isinstance(typed_value, str) and (value.startswith("{") or value.startswith("[")):
                try:
                    typed_value = json.loads(value)
                except json.JSONDecodeError:
                    pass

        # Set the value
        settings.set(
            key, typed_value, username=username, category=category, description=description
        )

        click.echo()
        click.secho("✓ Setting updated successfully", fg="green", bold=True)
        click.echo(f"  Key: {key}")
        click.echo(f"  Value: {typed_value}")
        click.echo(f"  Type: {type(typed_value).__name__}")
        if category:
            click.echo(f"  Category: {category}")
        click.echo(f"  Updated by: {username}")
        click.echo()

    except Exception as e:
        logger.error(f"Error setting value: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-delete")
@click.option("--key", required=True, help="Setting key to delete")
@click.confirmation_option(prompt="Are you sure you want to delete this setting?")
@click.pass_context
def settings_delete(ctx, key):
    """
    Delete a system setting.

    Examples:
      cli.py admin settings-delete --key llm.ollama_base_url
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        deleted = settings.delete_key(key)

        if deleted:
            click.echo()
            click.secho(f"✓ Setting '{key}' deleted successfully\n", fg="green", bold=True)
        else:
            click.secho(f"\n✗ Setting '{key}' not found\n", fg="yellow")
            ctx.exit(1)

    except Exception as e:
        logger.error(f"Error deleting setting: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-export")
@click.option("--output", required=True, help="Output JSON file path")
@click.pass_context
def settings_export(ctx, output):
    """
    Export all settings to JSON file.

    Examples:
      cli.py admin settings-export --output settings.json
      cli.py admin settings-export --output backup/settings_$(date +%Y%m%d).json
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        settings.export_to_json(output)

        click.echo()
        click.secho("✓ Settings exported successfully", fg="green", bold=True)
        click.echo(f"  Output: {output}")
        click.echo()

    except Exception as e:
        logger.error(f"Error exporting settings: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("settings-import")
@click.option("--input", "input_file", required=True, help="Input JSON file path")
@click.option("--username", default="admin", help="Username performing import (default: admin)")
@click.confirmation_option(prompt="This will overwrite existing settings. Continue?")
@click.pass_context
def settings_import(ctx, input_file, username):
    """
    Import settings from JSON file.

    WARNING: This will overwrite existing settings with the same keys.

    Examples:
      cli.py admin settings-import --input settings.json
      cli.py admin settings-import --input backup/settings_20251104.json --username steve
    """
    from system_settings import get_settings

    db = ctx.obj["db"]
    settings = get_settings(db)

    try:
        count = settings.import_from_json(input_file, username=username)

        click.echo()
        click.secho("✓ Settings imported successfully", fg="green", bold=True)
        click.echo(f"  Imported: {count} settings")
        click.echo(f"  From: {input_file}")
        click.echo(f"  By: {username}")
        click.echo()

        # Clear cache after bulk import
        settings.clear_cache()

    except Exception as e:
        logger.error(f"Error importing settings: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("faq-add")
@click.option("--guild-id", type=int, required=True, help="Guild ID for FAQ")
@click.option("--question", type=str, required=True, help="FAQ question")
@click.option("--answer", type=str, required=True, help="FAQ answer")
@click.option("--username", default="cli_admin", help="Admin username")
@click.option("--skip-validation", is_flag=True, help="Skip quality validation (not recommended)")
@click.pass_context
def faq_add(ctx, guild_id: int, question: str, answer: str, username: str, skip_validation: bool):
    """
    [DEPRECATED] Add FAQ to guild-specific knowledge base with validation.

    ⚠️  DEPRECATED: Use 'cli.py knowledge faq-add' instead.
    This command will be removed in a future version.

    This command adds a new FAQ entry to the guild's RAG vector store
    after validating its quality using an LLM.

    Examples:
      cli.py knowledge faq-add --guild-id 123 --question "What is delta?" --answer "Delta measures..."
      cli.py knowledge faq-add --guild-id 123 --question "..." --answer "..." --skip-validation
    """
    from faq_manager import FAQManager

    try:
        # Show deprecation warning
        click.secho("⚠️  DEPRECATION WARNING", fg="yellow", bold=True)
        click.echo("   'admin faq-add' is deprecated. Use 'knowledge faq-add' instead.")
        click.echo("   This command will be removed in a future version.")
        click.echo()
        click.echo(f"📚 Adding FAQ to guild {guild_id} knowledge base...")
        click.echo(f"   Question: {question[:60]}{'...' if len(question) > 60 else ''}")
        click.echo(f"   Answer length: {len(answer)} chars")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Step 1: Validate (unless skipped)
        if not skip_validation:
            click.echo("🔍 Validating FAQ quality...")
            validation_result = faq_mgr.validate_faq_quality(question, answer)

            # Display validation results
            click.echo(f"   Quality Score: {validation_result['score']:.1%}")
            click.echo(f"   Valid: {validation_result['is_valid']}")
            click.echo()

            if not validation_result["is_valid"]:
                click.secho("❌ VALIDATION FAILED", fg="red", bold=True)
                click.echo()
                click.echo("Issues:")
                for issue in validation_result["issues"]:
                    click.echo(f"  • {issue}")
                click.echo()

                if validation_result["suggestions"]:
                    click.echo("Suggestions:")
                    for sug in validation_result["suggestions"]:
                        click.echo(f"  • {sug}")
                    click.echo()

                click.echo(f"Reasoning: {validation_result.get('reasoning', 'N/A')}")
                click.echo()
                click.secho("FAQ not added. Please revise and try again.", fg="yellow")
                ctx.exit(1)

            # Show validation success
            click.secho("✓ Validation passed", fg="green")
            if validation_result["suggestions"]:
                click.echo("\nSuggestions for improvement:")
                for sug in validation_result["suggestions"][:3]:
                    click.echo(f"  • {sug}")
            click.echo()
        else:
            click.secho("⚠ Skipping validation (not recommended)", fg="yellow")
            click.echo()

        # Step 2: Add to vector DB
        click.echo("💾 Adding to vector database...")
        success = faq_mgr.add_faq_to_vector_db(question, answer, username)

        if not success:
            click.secho("\n✗ Failed to add FAQ to database\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ FAQ added successfully", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Added by: {username}")
        click.echo()

    except Exception as e:
        logger.error(f"Error adding FAQ: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("faq-list")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.pass_context
def faq_list(ctx, guild_id: int):
    """
    [DEPRECATED] List all FAQs in guild's knowledge base.

    ⚠️  DEPRECATED: Use 'cli.py knowledge faq-list' instead.

    Examples:
      cli.py knowledge faq-list --guild-id 123
    """
    from faq_manager import FAQManager

    try:
        click.secho("⚠️  DEPRECATION WARNING", fg="yellow", bold=True)
        click.echo("   'admin faq-list' is deprecated. Use 'knowledge faq-list' instead.")
        click.echo()
        click.echo(f"📚 Listing FAQs for guild {guild_id}...")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Get FAQs
        faqs = faq_mgr.list_faqs()

        if not faqs:
            click.secho("No FAQs found for this guild", fg="yellow")
            click.echo()
            return

        # Display FAQs
        click.echo("=" * 80)
        click.secho(f"GUILD {guild_id} FAQS ({len(faqs)} total)", bold=True)
        click.echo("=" * 80)
        click.echo()

        for i, faq in enumerate(faqs, 1):
            click.secho(f"FAQ #{i}", bold=True)
            click.echo(f"  Question: {faq['question']}")
            click.echo(
                f"  Answer: {faq['answer'][:100]}{'...' if len(faq['answer']) > 100 else ''}"
            )
            click.echo(f"  Added by: {faq['added_by']} on {faq['added_at']}")
            click.echo(f"  ID: {faq['id']}")
            click.echo()

    except Exception as e:
        logger.error(f"Error listing FAQs: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("faq-remove")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--faq-id", type=str, required=True, help="FAQ ID to remove")
@click.option("--confirm", is_flag=True, help="Confirm deletion without prompt")
@click.pass_context
def faq_remove(ctx, guild_id: int, faq_id: str, confirm: bool):
    """
    [DEPRECATED] Remove FAQ from guild's knowledge base.

    ⚠️  DEPRECATED: Use 'cli.py knowledge faq-remove' instead.

    Get FAQ IDs using: cli.py knowledge faq-list --guild-id <id>

    Examples:
      cli.py knowledge faq-remove --guild-id 123 --faq-id faq_123_2025-01-15_abc123
      cli.py knowledge faq-remove --guild-id 123 --faq-id <id> --confirm
    """
    from faq_manager import FAQManager

    try:
        click.secho("⚠️  DEPRECATION WARNING", fg="yellow", bold=True)
        click.echo("   'admin faq-remove' is deprecated. Use 'knowledge faq-remove' instead.")
        click.echo()
        click.echo(f"🗑️  Removing FAQ from guild {guild_id}...")
        click.echo(f"   FAQ ID: {faq_id}")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Get FAQ details first
        faqs = faq_mgr.list_faqs()
        faq_to_remove = None
        for faq in faqs:
            if faq["id"] == faq_id:
                faq_to_remove = faq
                break

        if not faq_to_remove:
            click.secho(f"✗ FAQ ID not found: {faq_id}", fg="red")
            click.echo()
            click.echo("Use 'cli.py admin faq-list --guild-id <id>' to see available FAQs")
            ctx.exit(1)

        # Show what will be deleted (faq_to_remove is guaranteed non-None here)
        assert faq_to_remove is not None
        click.echo("FAQ to be removed:")
        click.echo(f"  Question: {faq_to_remove['question']}")
        click.echo(f"  Answer: {faq_to_remove['answer'][:100]}...")
        click.echo(f"  Added by: {faq_to_remove['added_by']}")
        click.echo()

        # Confirm deletion unless --confirm flag used
        if not confirm:
            if not click.confirm("Are you sure you want to remove this FAQ?"):
                click.secho("Cancelled", fg="yellow")
                ctx.exit(0)

        # Remove FAQ
        success = faq_mgr.remove_faq(faq_id)

        if not success:
            click.secho("\n✗ Failed to remove FAQ\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ FAQ removed successfully", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Removed ID: {faq_id}")
        click.echo()

    except Exception as e:
        logger.error(f"Error removing FAQ: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("rag-stats")
@click.option("--days", default=30, help="Look back period in days (default: 30)")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.option("--doc-type", type=str, help="Filter by doc type (pdf, faq, etc.)")
@click.pass_context
def rag_stats(ctx, days: int, guild_id: int | None, doc_type: str | None):
    """
    View RAG knowledge source analytics.

    Shows which PDFs and FAQs are most frequently cited by the AI Assistant
    to help optimize the knowledge base.

    Examples:
      cli.py admin rag-stats --days 30
      cli.py admin rag-stats --guild-id 123 --doc-type faq
      cli.py admin rag-stats --days 7 --doc-type pdf
    """
    from rag_analytics import RAGAnalytics

    try:
        click.echo()
        click.echo("📊 RAG Knowledge Source Analytics")
        click.echo(f"   Period: Last {days} days")
        if guild_id:
            click.echo(f"   Guild: {guild_id}")
        if doc_type:
            click.echo(f"   Doc Type: {doc_type}")
        click.echo()

        analytics = RAGAnalytics(ctx.obj["db"])

        # Overall query stats
        query_stats = analytics.get_query_stats(days=days, guild_id=guild_id)

        click.echo("=" * 80)
        click.secho("QUERY STATISTICS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total Queries:        {query_stats['total_queries']}")
        click.echo(f"Unique Users:         {query_stats['unique_users']}")
        click.echo(f"Ask Queries:          {query_stats['ask_queries']}")
        click.echo(f"Explain Queries:      {query_stats['explain_queries']}")
        click.echo(f"Avg Results/Query:    {query_stats['avg_results_requested']}")
        click.echo()

        # Source usage stats
        source_stats = analytics.get_source_stats(days=days, guild_id=guild_id, doc_type=doc_type)

        if source_stats:
            click.echo("=" * 80)
            click.secho("TOP KNOWLEDGE SOURCES", bold=True)
            click.echo("=" * 80)

            table_data = []
            for i, stat in enumerate(source_stats[:20], 1):  # Top 20
                table_data.append(
                    [
                        i,
                        stat["source_file"][:40],  # Truncate long filenames
                        stat["doc_type"],
                        stat["times_cited"],
                        f"{stat['avg_distance']:.4f}",
                        f"{stat['avg_rank']:.1f}",
                        stat["best_rank"],
                        stat["unique_users"],
                    ]
                )

            headers = [
                "#",
                "Source File",
                "Type",
                "Citations",
                "Avg Dist",
                "Avg Rank",
                "Best",
                "Users",
            ]
            click.echo(tabulate(table_data, headers=headers, tablefmt="psql"))
            click.echo()
        else:
            click.secho("No source usage data found", fg="yellow")
            click.echo()

        # FAQ vs PDF effectiveness
        effectiveness = analytics.get_faq_effectiveness(days=days, guild_id=guild_id)

        if effectiveness:
            click.echo("=" * 80)
            click.secho("FAQ vs PDF EFFECTIVENESS", bold=True)
            click.echo("=" * 80)

            table_data = []
            for doc_type, stats in effectiveness.items():
                table_data.append(
                    [
                        doc_type,
                        stats["times_cited"],
                        f"{stats['avg_distance']:.4f}",
                        f"{stats['avg_rank']:.2f}",
                    ]
                )

            headers = ["Doc Type", "Citations", "Avg Distance", "Avg Rank"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="psql"))
            click.echo()

            # Interpretation
            click.secho("📌 Interpretation:", bold=True)
            click.echo("  • Lower distance = more relevant/similar to query")
            click.echo("  • Lower rank = appears higher in results (1 = top)")
            click.echo("  • More citations = used more frequently")
            click.echo()

        # Popular topics
        topics = analytics.get_popular_topics(days=days, guild_id=guild_id, limit=10)

        if topics:
            click.echo("=" * 80)
            click.secho("TOP 10 POPULAR TOPICS", bold=True)
            click.echo("=" * 80)

            table_data = []
            for i, topic in enumerate(topics, 1):
                table_data.append(
                    [
                        i,
                        topic["section"][:60],  # Truncate long sections
                        topic["times_cited"],
                        topic["unique_users"],
                    ]
                )

            headers = ["#", "Topic/Section", "Citations", "Users"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="psql"))
            click.echo()

    except Exception as e:
        logger.error(f"Error getting RAG stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("guild-vector-stats")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.pass_context
def guild_vector_stats(ctx, guild_id: int):
    """
    Show statistics for guild's vector database.

    Displays total documents, breakdown by type (FAQs, PDFs, etc.),
    and database path information.

    Examples:
      cli.py admin guild-vector-stats --guild-id 123456
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo("📊 Guild Vector Database Statistics")
        click.echo(f"   Guild ID: {guild_id}")
        click.echo()

        faq_mgr = FAQManager(guild_id=guild_id)
        stats = faq_mgr.get_guild_vector_stats()

        if "error" in stats:
            click.secho(f"✗ Error: {stats['error']}", fg="red")
            ctx.exit(1)

        if not stats.get("exists"):
            click.secho(f"⚠ No vector database exists for guild {guild_id}", fg="yellow")
            click.echo()
            click.echo("This guild has no RAG content yet.")
            click.echo("Content will be created when:")
            click.echo("  • Users add FAQs via /ai_assistant_add_faq")
            click.echo("  • Or admins add PDFs via vector store scripts")
            click.echo()
            return

        # Display stats
        click.echo("=" * 60)
        click.secho("DATABASE OVERVIEW", bold=True)
        click.echo("=" * 60)
        click.echo(f"Total Documents:  {stats['total_documents']}")
        click.echo(f"Path:             {stats['path']}")
        click.echo()

        # Breakdown by doc type
        if stats.get("by_doc_type"):
            click.echo("=" * 60)
            click.secho("CONTENT BREAKDOWN", bold=True)
            click.echo("=" * 60)

            table_data = []
            for doc_type, count in sorted(
                stats["by_doc_type"].items(), key=lambda x: x[1], reverse=True
            ):
                percentage = (
                    (count / stats["total_documents"] * 100) if stats["total_documents"] > 0 else 0
                )
                table_data.append([doc_type, count, f"{percentage:.1f}%"])

            headers = ["Doc Type", "Count", "Percentage"]
            click.echo(tabulate(table_data, headers=headers, tablefmt="psql"))
            click.echo()

    except Exception as e:
        logger.error(f"Error getting guild vector stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("guild-vector-purge-faqs")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--confirm", is_flag=True, help="Confirm purge without prompt")
@click.pass_context
def guild_vector_purge_faqs(ctx, guild_id: int, confirm: bool):
    """
    Remove ALL FAQs from guild's vector database.

    WARNING: This is destructive and cannot be undone!
    Only removes FAQs (doc_type='faq'), preserves PDFs and other content.

    Examples:
      cli.py admin guild-vector-purge-faqs --guild-id 123456
      cli.py admin guild-vector-purge-faqs --guild-id 123456 --confirm
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo(f"🗑️  Purging ALL FAQs from guild {guild_id}")
        click.echo()

        faq_mgr = FAQManager(guild_id=guild_id)

        # Get stats first
        stats = faq_mgr.get_guild_vector_stats()

        if not stats.get("exists"):
            click.secho(f"⚠ No vector database exists for guild {guild_id}", fg="yellow")
            click.echo()
            return

        faq_count = stats.get("faqs", 0)

        if faq_count == 0:
            click.secho(f"⚠ No FAQs found for guild {guild_id}", fg="yellow")
            click.echo()
            return

        # Show what will be deleted
        click.secho(f"⚠ WARNING: This will delete {faq_count} FAQs!", fg="yellow", bold=True)
        click.echo()
        click.echo(f"Total documents: {stats['total_documents']}")
        click.echo(f"FAQs to delete:  {faq_count}")
        click.echo(f"Will remain:     {stats['total_documents'] - faq_count}")
        click.echo()

        # Confirm deletion unless --confirm flag used
        if not confirm:
            click.secho("This action CANNOT be undone!", fg="red", bold=True)
            if not click.confirm(f"Are you sure you want to purge ALL {faq_count} FAQs?"):
                click.secho("Cancelled", fg="yellow")
                ctx.exit(0)

        # Purge FAQs
        click.echo()
        click.echo("Purging FAQs...")
        success = faq_mgr.purge_all_faqs()

        if not success:
            click.secho("\n✗ Failed to purge FAQs\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho(f"✓ Successfully purged {faq_count} FAQs", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Deleted: {faq_count} FAQs")
        click.echo(f"  Remaining: {stats['total_documents'] - faq_count} documents")
        click.echo()

    except Exception as e:
        logger.error(f"Error purging FAQs: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@admin.command("guild-vector-purge-all")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--confirm", is_flag=True, help="Confirm purge without prompt")
@click.pass_context
def guild_vector_purge_all(ctx, guild_id: int, confirm: bool):
    """
    Delete ENTIRE guild vector database (FAQs + PDFs + everything).

    WARNING: This is VERY destructive and cannot be undone!
    Deletes the entire guild-specific vector store directory.
    Use this to start fresh with new content.

    Examples:
      cli.py admin guild-vector-purge-all --guild-id 123456
      cli.py admin guild-vector-purge-all --guild-id 123456 --confirm
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo(f"💣 PURGING ENTIRE VECTOR DATABASE for guild {guild_id}")
        click.echo()

        faq_mgr = FAQManager(guild_id=guild_id)

        # Get stats first
        stats = faq_mgr.get_guild_vector_stats()

        if not stats.get("exists"):
            click.secho(f"⚠ No vector database exists for guild {guild_id}", fg="yellow")
            click.echo()
            return

        # Show what will be deleted
        click.secho("⚠ DANGER: This will delete ALL content!", fg="red", bold=True)
        click.echo()
        click.echo(f"Total documents: {stats['total_documents']}")
        click.echo(f"Database path:   {stats['path']}")
        click.echo()

        if stats.get("by_doc_type"):
            click.echo("Content to be deleted:")
            for doc_type, count in stats["by_doc_type"].items():
                click.echo(f"  • {doc_type}: {count}")
        click.echo()

        # Confirm deletion unless --confirm flag used
        if not confirm:
            click.secho("⚠ This will DELETE EVERYTHING and CANNOT be undone!", fg="red", bold=True)
            click.echo()
            click.echo("Type the guild ID to confirm deletion")
            confirmation = click.prompt(f"Enter guild ID ({guild_id}) to confirm")

            if str(confirmation) != str(guild_id):
                click.secho("Cancelled - guild ID did not match", fg="yellow")
                ctx.exit(0)

        # Purge entire database
        click.echo()
        click.echo("Purging entire vector database...")
        success = faq_mgr.purge_entire_guild_db()

        if not success:
            click.secho("\n✗ Failed to purge database\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ Successfully purged entire vector database", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Deleted: {stats['total_documents']} documents")
        click.echo(f"  Path removed: {stats['path']}")
        click.echo()
        click.echo("The guild now has a clean slate for new content.")
        click.echo()

    except Exception as e:
        logger.error(f"Error purging database: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)
