#!/usr/bin/env python3
"""
WheelHive CLI

Modern command-line interface built with Click.
Provides administrative commands and forces clean architecture patterns.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.

Usage:
    python src/cli.py --help
    python src/cli.py channels list
    python src/cli.py channels add --guild-id 123 --channel-id 456 --channel-name "test" --category sentiment
"""

import logging
import sys

import click

# Local application imports
import constants as const
import util
from cli.admin import admin
from cli.analytics import analytics
from cli.brokerage import brokerage

# Import command groups
from cli.channels import channels
from cli.knowledge import knowledge
from cli.llm import llm
from cli.messages import messages
from cli.reports import reports
from cli.scanner import scanner
from cli.tickers import tickers
from cli.tutor import tutor
from cli.tx import tx
from cli.watchlist import watchlist
from db import Db
from providers.market_data_factory import MarketDataFactory


# Initialize logging for CLI application
util.setup_logger(name=None, level="INFO", console=True, log_file=const.CMDS_LOG_FILE)
logger = logging.getLogger(__name__)


@click.group()
@click.option("--in-memory", is_flag=True, help="Use in-memory database (for testing)")
@click.pass_context
def cli(ctx, in_memory):
    """
    WheelHive Command Line Interface

    Manage trading data, generate reports, configure channels, and more.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Initialize database
    db = Db(in_memory=in_memory)
    ctx.obj["db"] = db

    # Initialize market data factory
    MarketDataFactory.set_db(db)

    db_type = "in-memory" if in_memory else f"persistent ({const.DATABASE_PATH})"
    logger.info(f"Initializing WheelHive CLI with {db_type} database")


# Register command groups
cli.add_command(channels)
cli.add_command(watchlist)
cli.add_command(tickers)
cli.add_command(tx)
cli.add_command(admin)
cli.add_command(brokerage)
cli.add_command(reports)
cli.add_command(analytics)
cli.add_command(messages)
cli.add_command(llm)
cli.add_command(scanner)
cli.add_command(tutor)
cli.add_command(knowledge)


# Add version command
@cli.command()
def version():
    """Show version information"""
    click.echo(f"WheelHive CLI v{const.VERSION}")
    click.echo(f"Author: {const.AUTHOR}")
    click.echo(f"Contributors: {const.CONTRIBUTORS}")


if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        click.secho(f"\n✗ Fatal error: {e}\n", fg="red", err=True)
        sys.exit(1)
