"""
Brokerage Import/Export Commands

Commands for importing brokerage CSV files and exporting transaction data.
Supports Fidelity, Robinhood, Schwab, and IBKR formats with auto-detection.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click

from bot_downloads import BotDownloads
from bot_upload_identifier import BotUploadIdentifier, BrokerageType
from bot_uploads import BotUploads
from deposits import Deposits
from dividends import Dividends
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)


@click.group()
def brokerage():
    """Import/export brokerage transactions"""


@brokerage.command("upload")
@click.option("--username", required=True, help="Username")
@click.option("--file", "fname", required=True, type=click.Path(exists=True), help="Path to CSV file")
@click.option("--account", default="default", help='Account name (default: "default")')
@click.option("--append", is_flag=True, help="Append to existing data (default: replace date range)")
@click.option("--guild-id", type=int, help="Guild ID")
@click.option("--format", type=click.Choice(["fidelity", "robinhood", "schwab", "ibkr"]),
              help="Broker format (auto-detects if not specified)")
@click.pass_context
def upload(ctx, username, fname, account, append, guild_id, format):
    """Import transactions from brokerage CSV file"""
    db = ctx.obj["db"]

    trades = Trades(db)
    dividends = Dividends(db)
    shares = Shares(db)
    deposits = Deposits(db)

    try:
        # Auto-detect format if not specified
        if format is None:
            click.echo("🔍 Auto-detecting brokerage format...")
            identifier = BotUploadIdentifier()
            brokerage_type, confidence = identifier.identify(fname)

            if brokerage_type == BrokerageType.UNKNOWN:
                logger.error(f"Unable to auto-detect format for {fname} (confidence: {confidence:.1%})")
                click.echo()
                click.secho(f"✗ Unable to auto-detect brokerage format (confidence: {confidence:.1%})", fg="red")
                click.echo("\nPlease specify the format using --format parameter")
                click.secho("Supported formats: fidelity, robinhood, schwab, ibkr", fg="cyan")
                ctx.exit(1)

            detected_format = brokerage_type.value
            logger.info(f"Auto-detected format: {detected_format} with {confidence:.1%} confidence")
            click.secho(f"✓ Detected format: {detected_format.capitalize()} ({confidence:.1%} confidence)", fg="green")
            click.echo()
        else:
            detected_format = format
            logger.info(f"Using specified format: {detected_format}")
            click.echo(f"Using format: {detected_format.capitalize()}")
            click.echo()

        logger.info(f"Upload - username: {username}, format: {detected_format}, "
                   f"append: {append}, account: {account}, guild_id: {guild_id}")

        # Process upload
        click.echo(f"📤 Importing transactions for {username}...")
        uploader = BotUploads(fname, detected_format, trades, dividends, shares, deposits)
        status, msg = uploader.process(username, append, account=account, guild_id=guild_id)

        logger.info(f"Upload status: {status}, message: {msg}")

        # Display results
        click.echo()
        click.echo("=" * 60)
        click.secho("IMPORT RESULTS", bold=True)
        click.echo("=" * 60)

        # Handle both boolean and string status
        if isinstance(status, bool):
            status_str = "Success" if status else "Failed"
            click.echo(f"Status:  {status_str}")
        else:
            status_str = str(status)
            click.echo(f"Status:  {status_str}")

        click.echo(f"Details: {msg}")
        click.echo("=" * 60)

        # Check success - handle both boolean and string
        is_success = status if isinstance(status, bool) else (str(status).lower() == "success")

        if is_success:
            click.secho("\n✓ Import complete", fg="green", bold=True)
        else:
            click.secho("\n⚠ Import completed with issues", fg="yellow")

        click.echo()

    except Exception as e:
        logger.error(f"Error uploading transactions: {e}", exc_info=True)
        click.secho(f"\n✗ Error uploading transactions: {e}\n", fg="red", err=True)
        ctx.exit(1)


@brokerage.command("download")
@click.option("--username", required=True, help="Username")
@click.option("--account", help="Filter by account (optional)")
@click.pass_context
def download(ctx, username, account):
    """Export transactions to CSV zip file"""
    db = ctx.obj["db"]

    trades = Trades(db)
    dividends = Dividends(db)
    shares = Shares(db)
    deposits = Deposits(db)

    try:
        logger.info(f"Download - username: {username}, account: {account}")

        click.echo()
        click.echo(f"📥 Exporting transactions for {username}...")
        if account:
            click.echo(f"   Account: {account}")
        else:
            click.echo("   All accounts")
        click.echo()

        downloader = BotDownloads(trades, dividends, shares, deposits)
        zipfile = downloader.process(username, account=account)

        logger.info(f"Download complete: {zipfile}")

        click.echo("=" * 60)
        click.secho("EXPORT COMPLETE", bold=True, fg="green")
        click.echo("=" * 60)
        click.echo(f"File: {zipfile}")
        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error downloading transactions: {e}", exc_info=True)
        click.secho(f"\n✗ Error downloading transactions: {e}\n", fg="red", err=True)
        ctx.exit(1)
