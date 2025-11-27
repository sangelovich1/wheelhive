"""
Scanner Command Group

Options chain scanner for finding trading opportunities.
Scans PUT and CALL options based on delta, IV, volume, and other filters.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import os

import click

import constants as const
from db import Db
from scanner import Scanner
from scanner_renderer import ScannerRenderer
from watchlists import Watchlists


logger = logging.getLogger(__name__)


@click.group()
def scanner():
    """
    Options chain scanner for finding trading opportunities.

    Scan PUT and CALL options chains based on delta, IV, open interest,
    volume, and strike proximity filters to identify trade candidates.
    """


@scanner.command("puts")
@click.option("--symbols", help='Comma-separated symbols (e.g., "TSLA,AAPL"). Default: user watchlist')
@click.option("--username", help="Username for watchlist lookup (required if no symbols provided)")
@click.option("--guild-id", type=int, help="Guild ID for watchlist lookup")
@click.option("--delta-min", type=float, default=0.01, help="Minimum delta (default: 0.01)")
@click.option("--delta-max", type=float, default=0.30, help="Maximum delta (default: 0.30)")
@click.option("--max-days", type=int, default=7, help="Maximum days to expiration (default: 7)")
@click.option("--iv-min", type=float, default=15.0, help="Minimum implied volatility % (default: 15.0)")
@click.option("--oi-min", type=int, default=10, help="Minimum open interest (default: 10)")
@click.option("--volume-min", type=int, default=0, help="Minimum volume (default: 0)")
@click.option("--strike-proximity", type=float, default=0.40, help="Max distance from price % (default: 0.40)")
@click.option("--top-candidates", type=int, default=50, help="Number of results (default: 50)")
@click.option("--save-image/--no-save-image", default=True, help="Save results as PNG image")
@click.pass_context
def scan_puts(ctx, symbols, username, guild_id, delta_min, delta_max, max_days,
              iv_min, oi_min, volume_min, strike_proximity, top_candidates, save_image):
    """
    Scan PUT options for trading opportunities.

    Filters PUT options based on delta range, implied volatility, open interest,
    volume, and strike proximity to current price. Returns top candidates sorted
    by score and profitability.

    Examples:
      cli.py scanner puts --symbols TSLA,AAPL
      cli.py scanner puts --username bob --delta-min 0.05 --delta-max 0.35
      cli.py scanner puts --symbols SPY --max-days 14 --iv-min 20
    """
    db: Db = ctx.obj["db"]

    try:
        # Parse symbols
        if symbols:
            symbols_list = [s.strip().upper() for s in symbols.split(",")]
            click.echo(f"\n🔍 Scanning {len(symbols_list)} symbols: {', '.join(symbols_list)}")
        elif username:
            # Get from user's watchlist
            watchlists = Watchlists(db)
            symbols_list = watchlists.list_symbols(username, guild_id=guild_id)

            if not symbols_list:
                click.secho(f"\n✗ No symbols in watchlist for {username}", fg="red", err=True)
                click.echo("\nAdd symbols to your watchlist first:")
                click.echo("  cli.py watchlist add --username user --symbols TSLA")
                return

            click.echo(f"\n🔍 Scanning {len(symbols_list)} symbols from {username}'s watchlist")
        else:
            click.secho("\n✗ Must provide either --symbols or --username", fg="red", err=True)
            click.echo("\nExamples:")
            click.echo("  cli.py scanner puts --symbols TSLA,AAPL")
            click.echo("  cli.py scanner puts --username bob")
            ctx.exit(1)

        # Display scan parameters
        click.echo("\n📊 Scan Parameters:")
        click.echo(f"   Delta range: {delta_min:.3f} - {delta_max:.3f}")
        click.echo(f"   Max expiration: {max_days} days")
        click.echo(f"   Min IV: {iv_min}%")
        click.echo(f"   Min open interest: {oi_min}")
        click.echo(f"   Min volume: {volume_min}")
        click.echo(f"   Strike proximity: {strike_proximity*100:.0f}%")
        click.echo(f"   Top candidates: {top_candidates}\n")

        # Initialize scanner
        scanner_obj = Scanner(
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_days,
            iv_min=iv_min,
            open_interest_min=oi_min,
            volume_min=volume_min,
            strike_proximity=strike_proximity,
            top_candidates=top_candidates
        )

        # Run scan with diagnostics
        df_result, table_str, params = scanner_obj.scan("PUT", symbols_list, include_params=True)

        if df_result is None:
            # No results - show diagnostic message
            click.secho("\n⚠️  No results found", fg="yellow")
            click.echo(table_str)  # Contains diagnostic info
            click.echo()
        else:
            # Display results
            click.echo("=" * 100)
            click.secho(f"PUT Options Scan Results - {len(df_result)} candidates found", fg="green", bold=True)
            click.echo("=" * 100)
            click.echo()
            click.echo(table_str)
            click.echo()
            click.echo("=" * 100)
            click.echo()

            # Save as image if requested
            if save_image:
                renderer = ScannerRenderer(output_dir=const.DOWNLOADS_DIR)
                image_path = renderer.render(
                    df_result,
                    title="PUT Options Scan",
                    chain_type="PUT",
                    username=username or "cli",
                    delta_min=delta_min,
                    delta_max=delta_max,
                    max_days=max_days
                )

                if image_path and os.path.exists(image_path):
                    click.secho(f"✓ Image saved: {image_path}", fg="green")
                else:
                    click.secho("⚠️  Failed to generate image", fg="yellow")

    except Exception as e:
        logger.error(f"Error scanning PUT options: {e}", exc_info=True)
        click.secho(f"\n✗ Error scanning PUT options: {e}\n", fg="red", err=True)
        ctx.exit(1)


@scanner.command("calls")
@click.option("--symbols", help='Comma-separated symbols (e.g., "TSLA,AAPL"). Default: user watchlist')
@click.option("--username", help="Username for watchlist lookup (required if no symbols provided)")
@click.option("--guild-id", type=int, help="Guild ID for watchlist lookup")
@click.option("--delta-min", type=float, default=0.01, help="Minimum delta (default: 0.01)")
@click.option("--delta-max", type=float, default=0.30, help="Maximum delta (default: 0.30)")
@click.option("--max-days", type=int, default=7, help="Maximum days to expiration (default: 7)")
@click.option("--iv-min", type=float, default=15.0, help="Minimum implied volatility % (default: 15.0)")
@click.option("--oi-min", type=int, default=10, help="Minimum open interest (default: 10)")
@click.option("--volume-min", type=int, default=0, help="Minimum volume (default: 0)")
@click.option("--strike-proximity", type=float, default=0.40, help="Max distance from price % (default: 0.40)")
@click.option("--top-candidates", type=int, default=50, help="Number of results (default: 50)")
@click.option("--save-image/--no-save-image", default=True, help="Save results as PNG image")
@click.pass_context
def scan_calls(ctx, symbols, username, guild_id, delta_min, delta_max, max_days,
               iv_min, oi_min, volume_min, strike_proximity, top_candidates, save_image):
    """
    Scan CALL options for trading opportunities.

    Filters CALL options based on delta range, implied volatility, open interest,
    volume, and strike proximity to current price. Returns top candidates sorted
    by score and profitability.

    Examples:
      cli.py scanner calls --symbols TSLA,AAPL
      cli.py scanner calls --username bob --delta-min 0.05 --delta-max 0.35
      cli.py scanner calls --symbols SPY --max-days 14 --iv-min 20
    """
    db: Db = ctx.obj["db"]

    try:
        # Parse symbols
        if symbols:
            symbols_list = [s.strip().upper() for s in symbols.split(",")]
            click.echo(f"\n🔍 Scanning {len(symbols_list)} symbols: {', '.join(symbols_list)}")
        elif username:
            # Get from user's watchlist
            watchlists = Watchlists(db)
            symbols_list = watchlists.list_symbols(username, guild_id=guild_id)

            if not symbols_list:
                click.secho(f"\n✗ No symbols in watchlist for {username}", fg="red", err=True)
                click.echo("\nAdd symbols to your watchlist first:")
                click.echo("  cli.py watchlist add --username user --symbols TSLA")
                return

            click.echo(f"\n🔍 Scanning {len(symbols_list)} symbols from {username}'s watchlist")
        else:
            click.secho("\n✗ Must provide either --symbols or --username", fg="red", err=True)
            click.echo("\nExamples:")
            click.echo("  cli.py scanner calls --symbols TSLA,AAPL")
            click.echo("  cli.py scanner calls --username bob")
            ctx.exit(1)

        # Display scan parameters
        click.echo("\n📊 Scan Parameters:")
        click.echo(f"   Delta range: {delta_min:.3f} - {delta_max:.3f}")
        click.echo(f"   Max expiration: {max_days} days")
        click.echo(f"   Min IV: {iv_min}%")
        click.echo(f"   Min open interest: {oi_min}")
        click.echo(f"   Min volume: {volume_min}")
        click.echo(f"   Strike proximity: {strike_proximity*100:.0f}%")
        click.echo(f"   Top candidates: {top_candidates}\n")

        # Initialize scanner
        scanner_obj = Scanner(
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_days,
            iv_min=iv_min,
            open_interest_min=oi_min,
            volume_min=volume_min,
            strike_proximity=strike_proximity,
            top_candidates=top_candidates
        )

        # Run scan with diagnostics
        df_result, table_str, params = scanner_obj.scan("CALL", symbols_list, include_params=True)

        if df_result is None:
            # No results - show diagnostic message
            click.secho("\n⚠️  No results found", fg="yellow")
            click.echo(table_str)  # Contains diagnostic info
            click.echo()
        else:
            # Display results
            click.echo("=" * 100)
            click.secho(f"CALL Options Scan Results - {len(df_result)} candidates found", fg="green", bold=True)
            click.echo("=" * 100)
            click.echo()
            click.echo(table_str)
            click.echo()
            click.echo("=" * 100)
            click.echo()

            # Save as image if requested
            if save_image:
                renderer = ScannerRenderer(output_dir=const.DOWNLOADS_DIR)
                image_path = renderer.render(
                    df_result,
                    title="CALL Options Scan",
                    chain_type="CALL",
                    username=username or "cli",
                    delta_min=delta_min,
                    delta_max=delta_max,
                    max_days=max_days
                )

                if image_path and os.path.exists(image_path):
                    click.secho(f"✓ Image saved: {image_path}", fg="green")
                else:
                    click.secho("⚠️  Failed to generate image", fg="yellow")

    except Exception as e:
        logger.error(f"Error scanning CALL options: {e}", exc_info=True)
        click.secho(f"\n✗ Error scanning CALL options: {e}\n", fg="red", err=True)
        ctx.exit(1)
