"""
Watchlist Management Commands

Commands for managing user watchlists (symbols to track for scanning).
Uses Click framework for clean, modern CLI interface.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re

import click

from watchlists import Watchlists


logger = logging.getLogger(__name__)


@click.group()
def watchlist():
    """Manage user watchlists"""


@watchlist.command("list")
@click.option("--username", required=True, help="Username")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_watchlist(ctx, username, guild_id):
    """List watchlist symbols for a user"""
    db = ctx.obj["db"]
    watchlists = Watchlists(db)

    try:
        # Use as_str() method for consistent multi-column formatting
        table_str = watchlists.as_str(username, guild_id=guild_id, symbols_per_row=5)

        if table_str == "Watchlist is empty.":
            click.echo(f"\n{username}'s watchlist is empty")
            click.secho("\n💡 Tip: Use 'watchlist add' to add symbols", fg="yellow")
            return

        # Count symbols for header
        symbols_list = watchlists.list_symbols(username, guild_id=guild_id)
        count_str = f"({len(symbols_list)} symbol{'s' if len(symbols_list) != 1 else ''})"

        click.echo(f"\n{username}'s Watchlist {count_str}:")
        if guild_id:
            click.echo(f"Guild: {guild_id}")
        click.echo(table_str)
        click.echo()

    except Exception as e:
        logger.error(f"Error listing watchlist: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing watchlist: {e}\n", fg="red", err=True)
        ctx.exit(1)


@watchlist.command("add")
@click.option("--username", required=True, help="Username")
@click.option("--symbols", required=True, help="Symbol(s) to add (space or comma separated)")
@click.option("--guild-id", type=int, help="Guild ID")
@click.pass_context
def add_symbols(ctx, username, symbols, guild_id):
    """Add symbols to watchlist"""
    db = ctx.obj["db"]
    watchlists = Watchlists(db)

    try:
        # Parse space or comma delimited list
        symbols_list = re.split(r"[,\s]+", symbols.strip())

        added = []
        skipped = []

        for symbol in symbols_list:
            if not symbol:  # Skip empty strings
                continue

            try:
                watchlists.add(username, symbol.upper(), guild_id=guild_id)
                added.append(symbol.upper())
            except Exception:
                skipped.append(symbol.upper())

        # Print results
        if added:
            click.secho(f"✓ Added: {', '.join(added)}", fg="green")
        if skipped:
            click.secho(f"⊘ Already in watchlist: {', '.join(skipped)}", fg="yellow")
        if not added and not skipped:
            click.secho("No symbols provided", fg="red")

    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}", exc_info=True)
        click.secho(f"\n✗ Error adding to watchlist: {e}\n", fg="red", err=True)
        ctx.exit(1)


@watchlist.command("rm")
@click.option("--username", required=True, help="Username")
@click.option("--symbols", required=True, help="Symbol(s) to remove (space or comma separated)")
@click.option("--guild-id", type=int, help="Guild ID")
@click.pass_context
def rm_symbol(ctx, username, symbols, guild_id):
    """Remove symbol(s) from watchlist"""
    db = ctx.obj["db"]
    watchlists = Watchlists(db)

    try:
        # Parse space or comma delimited list
        symbols_list = re.split(r"[,\s]+", symbols.strip())

        removed = []
        not_found = []

        for symbol in symbols_list:
            if not symbol:  # Skip empty strings
                continue

            count = watchlists.remove(username, symbol.upper(), guild_id=guild_id)
            if count > 0:
                removed.append(symbol.upper())
            else:
                not_found.append(symbol.upper())

        # Print results
        if removed:
            click.secho(f"✓ Removed: {', '.join(removed)}", fg="green")
        if not_found:
            click.secho(f"⊘ Not in watchlist: {', '.join(not_found)}", fg="yellow")
        if not removed and not not_found:
            click.secho("No symbols provided", fg="red")

    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing from watchlist: {e}\n", fg="red", err=True)
        ctx.exit(1)
