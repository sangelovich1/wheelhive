"""
Transaction Management Commands

Commands for managing all transaction types (options, dividends, shares, deposits).
Provides consistent CRUD operations across all transaction tables.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click

from deposits import Deposits
from dividends import Dividends
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)


@click.group()
def tx():
    """Manage transactions (options, dividends, shares, deposits)"""


# ============================================================
# OPTIONS COMMANDS
# ============================================================

@tx.group("options")
def options():
    """Manage options trades"""


@options.command("list")
@click.option("--username", help="Filter by username")
@click.option("--symbol", help="Filter by symbol")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_options(ctx, username, symbol, account, guild_id):
    """List options trades"""
    db = ctx.obj["db"]
    trades = Trades(db)

    try:
        # Build filter condition
        filter_parts = []
        if symbol:
            filter_parts.append(f'symbol="{symbol}"')
        if account:
            filter_parts.append(f'account="{account}"')
        if guild_id:
            filter_parts.append(f"guild_id={guild_id}")
        filter_cond = " AND ".join(filter_parts) if filter_parts else None

        result = trades.styled_df(username, filter_cond)
        click.echo(result)

    except Exception as e:
        logger.error(f"Error listing options: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing options: {e}\n", fg="red", err=True)
        ctx.exit(1)


@options.command("get")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def get_option(ctx, username, tx_id):
    """Get single options trade by ID"""
    db = ctx.obj["db"]

    try:
        rows = db.query_parameterized(
            "SELECT * FROM trades WHERE username=? AND id=?",
            (username, tx_id)
        )

        if rows:
            click.echo()
            for row in rows:
                click.echo(row)
            click.echo()
        else:
            click.secho(f"\nNo options trade found with ID {tx_id} for user {username}\n", fg="yellow")

    except Exception as e:
        logger.error(f"Error getting options trade: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting options trade: {e}\n", fg="red", err=True)
        ctx.exit(1)


@options.command("rm")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def rm_option(ctx, username, tx_id):
    """Remove options trade by ID"""
    db = ctx.obj["db"]
    trades = Trades(db)

    try:
        count = trades.delete(username, tx_id)

        if count > 0:
            click.secho(f"✓ Removed {count} options trade", fg="green")
        else:
            click.secho(f"No options trade found with ID {tx_id}", fg="yellow")

    except Exception as e:
        logger.error(f"Error removing options trade: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing options trade: {e}\n", fg="red", err=True)
        ctx.exit(1)


# ============================================================
# DIVIDENDS COMMANDS
# ============================================================

@tx.group("dividends")
def dividends():
    """Manage dividend transactions"""


@dividends.command("list")
@click.option("--username", help="Filter by username")
@click.option("--symbol", help="Filter by symbol")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_dividends(ctx, username, symbol, account, guild_id):
    """List dividend transactions"""
    db = ctx.obj["db"]
    divs = Dividends(db)

    try:
        # Build filter condition
        filter_parts = []
        if symbol:
            filter_parts.append(f'symbol="{symbol}"')
        if account:
            filter_parts.append(f'account="{account}"')
        if guild_id:
            filter_parts.append(f"guild_id={guild_id}")
        filter_cond = " AND ".join(filter_parts) if filter_parts else None

        result = divs.styled_df(username, filter_cond)
        click.echo(result)

    except Exception as e:
        logger.error(f"Error listing dividends: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing dividends: {e}\n", fg="red", err=True)
        ctx.exit(1)


@dividends.command("get")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def get_dividend(ctx, username, tx_id):
    """Get single dividend by ID"""
    db = ctx.obj["db"]

    try:
        rows = db.query_parameterized(
            "SELECT * FROM dividends WHERE username=? AND id=?",
            (username, tx_id)
        )

        if rows:
            click.echo()
            for row in rows:
                click.echo(row)
            click.echo()
        else:
            click.secho(f"\nNo dividend found with ID {tx_id} for user {username}\n", fg="yellow")

    except Exception as e:
        logger.error(f"Error getting dividend: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting dividend: {e}\n", fg="red", err=True)
        ctx.exit(1)


@dividends.command("rm")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def rm_dividend(ctx, username, tx_id):
    """Remove dividend by ID"""
    db = ctx.obj["db"]
    divs = Dividends(db)

    try:
        count = divs.delete(username, tx_id)

        if count > 0:
            click.secho(f"✓ Removed {count} dividend", fg="green")
        else:
            click.secho(f"No dividend found with ID {tx_id}", fg="yellow")

    except Exception as e:
        logger.error(f"Error removing dividend: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing dividend: {e}\n", fg="red", err=True)
        ctx.exit(1)


# ============================================================
# SHARES COMMANDS
# ============================================================

@tx.group("shares")
def shares():
    """Manage share transactions"""


@shares.command("list")
@click.option("--username", help="Filter by username")
@click.option("--symbol", help="Filter by symbol")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_shares(ctx, username, symbol, account, guild_id):
    """List share transactions"""
    db = ctx.obj["db"]
    shares_obj = Shares(db)

    try:
        # Build filter condition
        filter_parts = []
        if symbol:
            filter_parts.append(f'symbol="{symbol}"')
        if account:
            filter_parts.append(f'account="{account}"')
        if guild_id:
            filter_parts.append(f"guild_id={guild_id}")
        filter_cond = " AND ".join(filter_parts) if filter_parts else None

        result = shares_obj.styled_df(username, filter_cond)
        click.echo(result)

    except Exception as e:
        logger.error(f"Error listing shares: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing shares: {e}\n", fg="red", err=True)
        ctx.exit(1)


@shares.command("get")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def get_share(ctx, username, tx_id):
    """Get single share transaction by ID"""
    db = ctx.obj["db"]

    try:
        rows = db.query_parameterized(
            "SELECT * FROM shares WHERE username=? AND id=?",
            (username, tx_id)
        )

        if rows:
            click.echo()
            for row in rows:
                click.echo(row)
            click.echo()
        else:
            click.secho(f"\nNo share transaction found with ID {tx_id} for user {username}\n", fg="yellow")

    except Exception as e:
        logger.error(f"Error getting share transaction: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting share transaction: {e}\n", fg="red", err=True)
        ctx.exit(1)


@shares.command("rm")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def rm_share(ctx, username, tx_id):
    """Remove share transaction by ID"""
    db = ctx.obj["db"]
    shares_obj = Shares(db)

    try:
        count = shares_obj.delete(username, tx_id)

        if count > 0:
            click.secho(f"✓ Removed {count} share transaction", fg="green")
        else:
            click.secho(f"No share transaction found with ID {tx_id}", fg="yellow")

    except Exception as e:
        logger.error(f"Error removing share transaction: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing share transaction: {e}\n", fg="red", err=True)
        ctx.exit(1)


# ============================================================
# DEPOSITS COMMANDS
# ============================================================

@tx.group("deposits")
def deposits():
    """Manage cash deposits/withdrawals"""


@deposits.command("list")
@click.option("--username", help="Filter by username")
@click.option("--account", help="Filter by account")
@click.option("--guild-id", type=int, help="Filter by guild ID")
@click.pass_context
def list_deposits(ctx, username, account, guild_id):
    """List cash deposits/withdrawals"""
    db = ctx.obj["db"]
    deposits_obj = Deposits(db)

    try:
        # Build filter condition (no symbol for deposits)
        filter_parts = []
        if account:
            filter_parts.append(f'account="{account}"')
        if guild_id:
            filter_parts.append(f"guild_id={guild_id}")
        filter_cond = " AND ".join(filter_parts) if filter_parts else None

        result = deposits_obj.as_str(username, filter_cond)
        click.echo(result)

    except Exception as e:
        logger.error(f"Error listing deposits: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing deposits: {e}\n", fg="red", err=True)
        ctx.exit(1)


@deposits.command("get")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def get_deposit(ctx, username, tx_id):
    """Get single deposit/withdrawal by ID"""
    db = ctx.obj["db"]

    try:
        rows = db.query_parameterized(
            "SELECT * FROM deposits WHERE username=? AND id=?",
            (username, tx_id)
        )

        if rows:
            click.echo()
            for row in rows:
                click.echo(row)
            click.echo()
        else:
            click.secho(f"\nNo deposit/withdrawal found with ID {tx_id} for user {username}\n", fg="yellow")

    except Exception as e:
        logger.error(f"Error getting deposit: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting deposit: {e}\n", fg="red", err=True)
        ctx.exit(1)


@deposits.command("rm")
@click.option("--username", required=True, help="Username")
@click.option("--id", "tx_id", type=int, required=True, help="Transaction ID")
@click.pass_context
def rm_deposit(ctx, username, tx_id):
    """Remove deposit/withdrawal by ID"""
    db = ctx.obj["db"]
    deposits_obj = Deposits(db)

    try:
        count = deposits_obj.delete(username, tx_id)

        if count > 0:
            click.secho(f"✓ Removed {count} deposit/withdrawal", fg="green")
        else:
            click.secho(f"No deposit/withdrawal found with ID {tx_id}", fg="yellow")

    except Exception as e:
        logger.error(f"Error removing deposit: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing deposit: {e}\n", fg="red", err=True)
        ctx.exit(1)
