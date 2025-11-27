"""
Ticker Management Commands

Commands for managing valid ticker symbols (reference data).
Uses Click framework for clean, modern CLI interface.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any

import click
from tabulate import tabulate

from active_tickers import (
    format_ticker_summary,
    get_active_tickers,
    resolve_underlying_ticker,
    sort_tickers_by_activity,
)
from ticker import Ticker
from tickers import Tickers


logger = logging.getLogger(__name__)


@click.group()
def tickers():
    """Manage ticker symbols (reference data)"""


@tickers.command("add")
@click.option("--symbol", required=True, help="Ticker symbol (e.g., AAPL)")
@click.option("--company", help="Company name")
@click.option("--exchange", help="Exchange (e.g., NASDAQ, NYSE)")
@click.option("--sector", help="Business sector")
@click.pass_context
def add_ticker(ctx, symbol, company, exchange, sector):
    """Add a ticker symbol"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        ticker = Ticker(
            ticker=symbol.upper(),
            company_name=company,
            exchange=exchange,
            sector=sector,
            is_active=True
        )

        tickers_obj.insert(ticker)
        click.secho(f"\n✓ Added ticker: {symbol.upper()}", fg="green")
        if company:
            click.echo(f"  Company: {company}")
        if exchange:
            click.echo(f"  Exchange: {exchange}")
        if sector:
            click.echo(f"  Sector: {sector}")
        click.echo()

    except Exception as e:
        logger.error(f"Error adding ticker: {e}", exc_info=True)
        click.secho(f"\n✗ Error adding ticker: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("get")
@click.option("--symbol", required=True, help="Ticker symbol")
@click.pass_context
def get_ticker(ctx, symbol):
    """Get ticker details"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        ticker = tickers_obj.get_ticker(symbol)

        if not ticker:
            click.secho(f"\nTicker '{symbol.upper()}' not found\n", fg="yellow")
            return

        click.echo()
        click.echo("=" * 60)
        click.secho(f"TICKER: {ticker.ticker}", bold=True)
        click.echo("=" * 60)
        click.echo(f"Company:  {ticker.company_name or 'N/A'}")
        click.echo(f"Exchange: {ticker.exchange or 'N/A'}")
        click.echo(f"Sector:   {ticker.sector or 'N/A'}")
        click.echo(f"Active:   {'Yes' if ticker.is_active else 'No'}")
        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error getting ticker: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting ticker: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("rm")
@click.option("--symbol", required=True, help="Ticker symbol to remove")
@click.pass_context
def rm_ticker(ctx, symbol):
    """Remove a ticker symbol (soft delete)"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        count = tickers_obj.delete(symbol)

        if count > 0:
            click.secho(f"✓ Removed ticker: {symbol.upper()}", fg="green")
        else:
            click.secho(f"Ticker '{symbol.upper()}' not found", fg="yellow")

    except Exception as e:
        logger.error(f"Error removing ticker: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing ticker: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("list")
@click.option("--limit", type=int, default=20, help="Number of tickers to display")
@click.option("--active-only/--all", default=True, help="Show only active tickers (default: active only)")
@click.pass_context
def list_tickers(ctx, limit, active_only):
    """List ticker symbols"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        df = tickers_obj.as_df(active_only=active_only, limit=limit)

        if df.empty:
            click.secho("No tickers found in database", fg="yellow")
            click.secho("\n💡 Tip: Use 'tickers populate' command to fetch tickers from Wikipedia", fg="cyan")
            return

        # Display the dataframe
        click.echo()
        click.echo(f"Showing {len(df)} tickers (active_only={active_only})")
        click.echo("=" * 100)
        click.echo(tabulate(df, headers="keys", tablefmt="psql", showindex=False))
        click.echo("=" * 100)

        # Show total count
        total = tickers_obj.count(active_only=active_only)
        if total > limit:
            click.echo(f"\nShowing {limit} of {total} tickers")
            click.secho(f"💡 Tip: Use --limit to show more (e.g., --limit {total})", fg="cyan")

    except Exception as e:
        logger.error(f"Error listing tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("search")
@click.option("--query", required=True, help="Search term (ticker symbol or company name)")
@click.option("--limit", type=int, default=10, help="Maximum results to return")
@click.pass_context
def search_tickers(ctx, query, limit):
    """Search for tickers by symbol or company name"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        results = tickers_obj.search(query, limit=limit)

        if not results:
            click.secho(f"\nNo tickers found matching '{query}'", fg="yellow")
            click.secho("💡 Tip: Search by ticker symbol or company name", fg="cyan")
            return

        # Format results as table
        table_data = []
        for ticker in results:
            active_str = "✓" if ticker.is_active else "✗"
            table_data.append([
                ticker.ticker,
                ticker.company_name,
                ticker.exchange or "N/A",
                ticker.sector or "N/A",
                active_str
            ])

        click.echo()
        click.echo(f"Search results for '{query}' ({len(results)} found)")
        click.echo("=" * 120)
        click.echo(tabulate(table_data,
                          headers=["Ticker", "Company", "Exchange", "Sector", "Active"],
                          tablefmt="psql"))
        click.echo("=" * 120)

    except Exception as e:
        logger.error(f"Error searching tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error searching tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("stats")
@click.pass_context
def show_stats(ctx):
    """Show ticker database statistics"""
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        total_active = tickers_obj.count(active_only=True)
        total_all = tickers_obj.count(active_only=False)
        total_inactive = total_all - total_active

        click.echo()
        click.echo("=" * 60)
        click.secho("TICKER DATABASE STATISTICS", bold=True)
        click.echo("=" * 60)
        click.echo(f"Active tickers:   {total_active:,}")
        click.echo(f"Inactive tickers: {total_inactive:,}")
        click.echo(f"Total tickers:    {total_all:,}")
        click.echo("=" * 60)

        if total_all == 0:
            click.secho("\n💡 Tip: Use 'tickers populate' to fetch ticker data from Wikipedia", fg="cyan")

    except Exception as e:
        logger.error(f"Error getting ticker stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting ticker stats: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("active")
@click.option("--days", default=7, help="Look back N days (default: 7)")
@click.option("--sort-by",
              type=click.Choice(["trade_count", "trader_count", "avg_premium"]),
              default="trade_count",
              help="Sort by metric (default: trade_count)")
@click.option("--limit", default=20, help="Number of tickers to show (default: 20)")
@click.option("--min-trades", default=1, help="Minimum trades to include (default: 1)")
@click.option("--guild-id", type=int, help="Filter by guild ID (optional)")
@click.option("--show-examples/--no-examples", default=True, help="Show example trades")
@click.option("--show-leveraged/--no-leveraged", default=True, help="Show leveraged ETF mapping")
@click.pass_context
def active_tickers(ctx, days: int, sort_by: str, limit: int, min_trades: int,
                   guild_id: int | None, show_examples: bool, show_leveraged: bool):
    """
    Show most actively traded tickers from harvested messages

    Analyzes actual trades extracted from Discord messages to show:
    - Most traded tickers by volume
    - Most traded tickers by number of unique traders
    - Highest average premium tickers
    - Leveraged ETF identification

    Examples:

        # Top 20 tickers by trade count in last 7 days
        python src/cli.py tickers active

        # Top 10 by unique traders in last 14 days
        python src/cli.py tickers active --days 14 --sort-by trader_count --limit 10

        # Top 5 highest premium tickers (minimum 3 trades)
        python src/cli.py tickers active --sort-by avg_premium --limit 5 --min-trades 3
    """
    db = ctx.obj["db"]

    try:
        click.echo("=" * 80)
        click.echo(f"ACTIVE TICKERS (last {days} days)")
        if guild_id:
            click.echo(f"Guild filter: {guild_id}")
        click.echo("=" * 80)
        click.echo()

        # Extract active tickers
        ticker_data = get_active_tickers(db, days=days, min_trades=min_trades, guild_id=guild_id)

        if not ticker_data:
            click.secho("No trades found in date range", fg="yellow")
            return

        click.echo(f"Found {len(ticker_data)} unique tickers with {min_trades}+ trades\n")

        # Sort by requested metric
        sort_label = {
            "trade_count": "TRADE COUNT",
            "trader_count": "TRADER COUNT",
            "avg_premium": "AVERAGE PREMIUM"
        }

        click.echo("-" * 80)
        click.echo(f"TOP {limit} BY {sort_label[sort_by]}")
        click.echo("-" * 80)

        sorted_tickers = sort_tickers_by_activity(ticker_data, sort_by=sort_by, limit=limit)

        for i, (ticker, activity) in enumerate(sorted_tickers, 1):
            # Resolve leveraged ETF
            underlying, is_leveraged = resolve_underlying_ticker(ticker)
            leverage_str = f" (tracks {underlying})" if is_leveraged and show_leveraged else ""

            # Header
            click.echo(f"\n{i}. {ticker}{leverage_str}")

            # Summary
            click.echo(format_ticker_summary(activity, show_examples=show_examples))

        # Leveraged ETF summary
        if show_leveraged:
            click.echo("\n")
            click.echo("-" * 80)
            click.echo("LEVERAGED ETF SUMMARY")
            click.echo("-" * 80)

            leveraged_count = 0
            for ticker in ticker_data.keys():
                underlying, is_leveraged = resolve_underlying_ticker(ticker)
                if is_leveraged:
                    leveraged_count += 1
                    activity = ticker_data[ticker]
                    click.echo(f"{ticker} → {underlying}: {activity.trade_count} trades")

            if leveraged_count > 0:
                click.echo(f"\nTotal leveraged ETFs: {leveraged_count}/{len(ticker_data)}")
            else:
                click.echo("No leveraged ETFs detected")

    except Exception as e:
        logger.error(f"Error getting active tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting active tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("cleanup-auto")
@click.option("--dry-run/--no-dry-run", default=True, help="Preview changes without deleting (default: True)")
@click.pass_context
def cleanup_auto_added(ctx, dry_run):
    """
    Remove auto-added tickers from COMMUNITY-AUTO that polluted the database.

    These are terms like HAMAS, GAZA, TRUMP, DEMS, etc. that were incorrectly
    validated and auto-added by the old validation logic.

    By default, runs in dry-run mode to preview changes.
    Use --no-dry-run to actually delete.

    Examples:
        # Preview what would be deleted
        python src/cli.py tickers cleanup-auto

        # Actually delete the garbage tickers
        python src/cli.py tickers cleanup-auto --no-dry-run
    """
    db = ctx.obj["db"]
    tickers_obj = Tickers(db)

    try:
        # Get COMMUNITY-AUTO tickers using Tickers class
        auto_tickers = tickers_obj.get_by_exchange("COMMUNITY-AUTO", limit=50)

        if not auto_tickers:
            click.secho("\n✓ No COMMUNITY-AUTO tickers found - database is clean!\n", fg="green")
            return

        # Get total count (without limit)
        all_auto_tickers = tickers_obj.get_by_exchange("COMMUNITY-AUTO")
        total = len(all_auto_tickers)

        click.echo()
        click.echo("=" * 80)
        click.secho(f"COMMUNITY-AUTO TICKERS ({total} found)", bold=True)
        click.echo("=" * 80)

        # Show first 50 examples
        display_limit = min(50, total)
        table_data = []
        for ticker in auto_tickers[:display_limit]:
            table_data.append([ticker.ticker, ticker.company_name or "N/A", ticker.exchange])

        headers = ["Ticker", "Company Name", "Exchange"]
        click.echo(tabulate(table_data, headers=headers, tablefmt="simple"))

        if total > display_limit:
            click.echo(f"\n... and {total - display_limit} more")

        click.echo()

        if dry_run:
            click.secho("DRY RUN MODE - No changes made", fg="yellow", bold=True)
            click.echo(f"\nWould delete {total} COMMUNITY-AUTO tickers")
            click.echo("\nTo actually delete, run with --no-dry-run flag")
        else:
            # Confirm deletion
            click.secho(f"\n⚠️  WARNING: About to delete {total} tickers!", fg="red", bold=True)
            if not click.confirm("Are you sure you want to proceed?"):
                click.echo("\nCancelled - no changes made")
                return

            # Delete COMMUNITY-AUTO tickers using Tickers class
            deleted = tickers_obj.delete_by_exchange("COMMUNITY-AUTO")

            click.secho(f"\n✓ Deleted {deleted} COMMUNITY-AUTO tickers", fg="green")

            # Suggest next steps
            click.echo("\n💡 Next steps:")
            click.echo("   1. Run: python src/cli.py messages recompute-tickers --days 10000")
            click.echo("   2. This will clean up message_tickers table with proper validation")

        click.echo()

    except Exception as e:
        logger.error(f"Error cleaning up auto-added tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("blacklist-list")
@click.option("--category", help="Filter by category (e.g., common_word, options_term, geographic)")
@click.option("--limit", type=int, default=50, help="Number of entries to display (default: 50)")
@click.pass_context
def blacklist_list(ctx, category, limit):
    """
    List blacklisted ticker terms

    Blacklist contains terms that should never be treated as ticker symbols,
    such as common words (IN, OF, TO), options terminology (STO, BTC),
    geographic terms (USA, UK, CA), etc.

    Examples:
        # List all blacklisted terms (first 50)
        python src/cli.py tickers blacklist-list

        # Show all common words in blacklist
        python src/cli.py tickers blacklist-list --category common_word

        # Show first 100 entries
        python src/cli.py tickers blacklist-list --limit 100
    """
    db = ctx.obj["db"]

    try:
        # Build query
        params: tuple[Any, ...]
        if category:
            query = """
                SELECT term, category, reason, added_at
                FROM ticker_blacklist
                WHERE category = ?
                ORDER BY term
                LIMIT ?
            """
            params = (category, limit)
        else:
            query = """
                SELECT term, category, reason, added_at
                FROM ticker_blacklist
                ORDER BY category, term
                LIMIT ?
            """
            params = (limit,)

        results = db.query_parameterized(query, params)

        if not results:
            if category:
                click.secho(f"\nNo blacklist entries found for category '{category}'\n", fg="yellow")
            else:
                click.secho("\nNo blacklist entries found\n", fg="yellow")
            return

        # Get total count
        if category:
            count_query = "SELECT COUNT(*) FROM ticker_blacklist WHERE category = ?"
            total = db.query_parameterized(count_query, (category,))[0][0]
        else:
            count_query = "SELECT COUNT(*) FROM ticker_blacklist"
            total = db.query_parameterized(count_query, None)[0][0]

        # Format results
        table_data = []
        for row in results:
            term, cat, reason, added_at = row
            table_data.append([term, cat, reason or "N/A", added_at or "N/A"])

        # Display
        click.echo()
        if category:
            click.echo(f"Blacklist entries for category '{category}' ({len(results)} of {total})")
        else:
            click.echo(f"Blacklist entries ({len(results)} of {total})")
        click.echo("=" * 100)
        click.echo(tabulate(table_data,
                          headers=["Term", "Category", "Reason", "Added At"],
                          tablefmt="psql"))
        click.echo("=" * 100)

        if total > limit:
            click.secho(f"\n💡 Showing {limit} of {total} entries. Use --limit to show more", fg="cyan")

        # Show category breakdown
        category_query = """
            SELECT category, COUNT(*) as count
            FROM ticker_blacklist
            GROUP BY category
            ORDER BY count DESC
        """
        category_results = db.query_parameterized(category_query, None)

        if category_results and not category:
            click.echo("\nCategories:")
            for cat, count in category_results:
                click.echo(f"  {cat}: {count}")

        click.echo()

    except Exception as e:
        logger.error(f"Error listing blacklist: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing blacklist: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("blacklist-add")
@click.option("--term", required=True, help="Term to blacklist (e.g., SPAM, FAKE)")
@click.option("--category", required=True, help="Category (e.g., common_word, news, geographic)")
@click.option("--reason", help="Optional reason for blacklisting")
@click.pass_context
def blacklist_add(ctx, term, category, reason):
    """
    Add term to ticker blacklist

    Blacklisted terms will be filtered out during ticker extraction from messages.

    Examples:
        # Add a common word
        python src/cli.py tickers blacklist-add --term SPAM --category common_word --reason "Common word"

        # Add a news term
        python src/cli.py tickers blacklist-add --term BIDEN --category news --reason "Political figure"

        # Add without reason
        python src/cli.py tickers blacklist-add --term FAKE --category common_word
    """
    db = ctx.obj["db"]

    try:
        term_upper = term.upper().strip()

        # Check if already exists
        check_query = "SELECT term FROM ticker_blacklist WHERE term = ?"
        existing = db.query_parameterized(check_query, (term_upper,))

        if existing:
            click.secho(f"\n✗ Term '{term_upper}' is already blacklisted\n", fg="yellow")
            return

        # Insert new term
        insert_query = """
            INSERT INTO ticker_blacklist (term, category, reason)
            VALUES (?, ?, ?)
        """
        db.execute(insert_query, (term_upper, category, reason))

        click.secho(f"\n✓ Added '{term_upper}' to blacklist", fg="green")
        click.echo(f"  Category: {category}")
        if reason:
            click.echo(f"  Reason: {reason}")

        # Suggest next steps
        click.echo("\n💡 Next steps:")
        click.echo("   1. Run: python src/cli.py messages recompute-tickers --days 30")
        click.echo("   2. This will clean up message_tickers table with updated blacklist")
        click.echo()

    except Exception as e:
        logger.error(f"Error adding to blacklist: {e}", exc_info=True)
        click.secho(f"\n✗ Error adding to blacklist: {e}\n", fg="red", err=True)
        ctx.exit(1)


@tickers.command("blacklist-rm")
@click.option("--term", required=True, help="Term to remove from blacklist")
@click.option("--confirm/--no-confirm", default=True, help="Require confirmation (default: True)")
@click.pass_context
def blacklist_remove(ctx, term, confirm):
    """
    Remove term from ticker blacklist

    This will allow the term to be validated as a ticker symbol again.
    Use with caution - only remove terms that are legitimate ticker symbols.

    Examples:
        # Remove a term (with confirmation)
        python src/cli.py tickers blacklist-rm --term AI

        # Remove without confirmation
        python src/cli.py tickers blacklist-rm --term AI --no-confirm
    """
    db = ctx.obj["db"]

    try:
        term_upper = term.upper().strip()

        # Check if exists
        check_query = "SELECT term, category, reason FROM ticker_blacklist WHERE term = ?"
        existing = db.query_parameterized(check_query, (term_upper,))

        if not existing:
            click.secho(f"\n✗ Term '{term_upper}' not found in blacklist\n", fg="yellow")
            return

        # Show details
        _, category, reason = existing[0]
        click.echo()
        click.echo("=" * 60)
        click.echo(f"Term:     {term_upper}")
        click.echo(f"Category: {category}")
        click.echo(f"Reason:   {reason or 'N/A'}")
        click.echo("=" * 60)

        # Confirm deletion
        if confirm:
            click.secho("\n⚠️  Removing this term will allow it to validate as a ticker symbol", fg="yellow")
            if not click.confirm(f"Are you sure you want to remove '{term_upper}' from blacklist?"):
                click.echo("\nCancelled - no changes made\n")
                return

        # Delete
        delete_query = "DELETE FROM ticker_blacklist WHERE term = ?"
        db.execute(delete_query, (term_upper,))

        click.secho(f"\n✓ Removed '{term_upper}' from blacklist", fg="green")

        # Suggest next steps
        click.echo("\n💡 Next steps:")
        click.echo("   1. Run: python src/cli.py messages recompute-tickers --days 30")
        click.echo("   2. This will allow the term to be extracted and validated as a ticker")
        click.echo()

    except Exception as e:
        logger.error(f"Error removing from blacklist: {e}", exc_info=True)
        click.secho(f"\n✗ Error removing from blacklist: {e}\n", fg="red", err=True)
        ctx.exit(1)
