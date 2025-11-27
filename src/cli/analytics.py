"""
Analytics Commands

Commands for quick trading analytics and statistics.
Console-based data analysis for personal and team insights.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click

from df_stats import DFStats


logger = logging.getLogger(__name__)


@click.group()
def analytics():
    """Trading analytics and statistics"""


@analytics.command("my-stats")
@click.option("--username", help="Filter by username")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def my_stats(ctx, username, account, guild_id):
    """Show personal trading statistics (current year)"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Showing my_stats for user: {username}, account: {account}, guild_id: {guild_id}")

        df_stats = DFStats(db)
        df_stats.load(username, account=account, guild_id=guild_id)
        table_str = df_stats.my_stats()

        click.echo()
        click.echo("=" * 80)
        click.secho("PERSONAL TRADING STATISTICS (CURRENT YEAR)", bold=True)
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

    except Exception as e:
        logger.error(f"Error showing my_stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing statistics: {e}\n", fg="red", err=True)
        ctx.exit(1)


@analytics.command("symbol-stats")
@click.option("--start-date", required=True, help="Start date in YYYY-MM-DD format")
@click.option("--end-date", required=True, help="End date in YYYY-MM-DD format")
@click.option("--username", help="Filter by username")
@click.pass_context
def symbol_stats(ctx, start_date, end_date, username):
    """Show per-symbol trading statistics for date range"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Showing symbol_stats from {start_date} to {end_date}, user: {username}")

        df_stats = DFStats(db)
        df_stats.load(username)
        df_stats.filter_by_date_range(start_date, end_date)

        df = df_stats.options_by_symbol()
        df = df_stats.compute_totals(df)
        df = df_stats.format_currency(df, ["STO", "BTC", "BTO", "STC", "Premium"])
        table_str = df_stats.as_table(df)

        click.echo()
        click.echo("=" * 80)
        click.secho("SYMBOL STATISTICS", bold=True)
        click.echo(f"Period: {start_date} to {end_date}")
        if username:
            click.echo(f"User: {username}")
        click.echo("=" * 80)
        click.echo()
        click.echo(table_str)
        click.echo()
        click.echo("=" * 80)
        click.echo()

    except Exception as e:
        logger.error(f"Error showing symbol_stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing symbol statistics: {e}\n", fg="red", err=True)
        ctx.exit(1)
