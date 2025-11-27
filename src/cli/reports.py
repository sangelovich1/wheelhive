"""
Reports Commands

Commands for generating reports and viewing portfolio positions.
Includes PDF reports and position summaries.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime

import click

import constants as const
from positions import Positions
from reports.activity_report import ActivityReport
from reports.catchup_report import CatchUpReport
from reports.optionspivotreport import OptionsPivotReport
from reports.profittreport import ProfitReport
from reports.symbol_report import SymbolReport
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)


@click.group()
def reports():
    """Generate reports and view positions"""


@reports.command("positions")
@click.option("--username", required=True, help="Username")
@click.option("--symbol", help="Filter by symbol")
@click.pass_context
def positions(ctx, username, symbol):
    """Show current stock holdings and open option positions"""
    db = ctx.obj["db"]

    try:
        # Initialize positions
        trades = Trades(db)
        shares = Shares(db)
        positions_obj = Positions(db, shares, trades)

        logger.info(f"Showing open positions for user: {username}, symbol: {symbol}")

        # Get positions (aggregated across all accounts)
        output, page_count = positions_obj.my_positions(
            username,
            index=0,  # CLI always shows first page
            account=None,  # Account filtering not supported in CLI
            symbol=symbol
        )

        # Print header with filters
        filter_parts = [f"User: {username}", "All Accounts"]
        if symbol:
            filter_parts.append(f"Symbol: {symbol}")

        click.echo()
        click.echo("=" * 80)
        click.secho("CURRENT OPEN POSITIONS (AGGREGATED)", bold=True)
        click.echo(" | ".join(filter_parts))
        click.echo("=" * 80)
        click.echo()
        click.echo(output)
        click.echo()
        click.echo("=" * 80)
        click.echo()

    except Exception as e:
        logger.error(f"Error showing positions: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing positions: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("profit")
@click.option("--username", required=True, help="Username")
@click.option("--account", help="Filter by account")
@click.pass_context
def profit(ctx, username, account):
    """Generate profit summary report (PDF)"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Generating profit summary report for user: {username}, account: {account}")

        click.echo()
        click.echo(f"📊 Generating profit summary report for {username}...")
        if account:
            click.echo(f"   Account: {account}")
        click.echo()

        report = ProfitReport(db, username, account=account)
        report_path = report.report()

        logger.info(f"Profit Summary report generated: {report_path}")

        click.echo("=" * 60)
        click.secho("REPORT GENERATED", bold=True, fg="green")
        click.echo("=" * 60)
        click.echo(f"File: {report_path}")
        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error generating profit report: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating profit report: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("symbol")
@click.option("--username", required=True, help="Username")
@click.option("--symbol", required=True, help="Symbol/ticker")
@click.option("--account", help="Filter by account")
@click.pass_context
def symbol_report(ctx, username, symbol, account):
    """Generate ETF/symbol details report (PDF)"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Generating symbol report for: {symbol}, user: {username}, account: {account}")

        click.echo()
        click.echo(f"📊 Generating symbol details report for {symbol}...")
        click.echo(f"   User: {username}")
        if account:
            click.echo(f"   Account: {account}")
        click.echo()

        report = SymbolReport(db, username, symbol, account=account)
        report_path = report.report()

        logger.info(f"Symbol report for {symbol} generated: {report_path}")

        click.echo("=" * 60)
        click.secho("REPORT GENERATED", bold=True, fg="green")
        click.echo("=" * 60)
        click.echo(f"Symbol: {symbol}")
        click.echo(f"File:   {report_path}")
        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error generating symbol report: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating symbol report: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("pivot")
@click.option("--username", required=True, help="Username")
@click.option("--account", help="Filter by account")
@click.pass_context
def pivot(ctx, username, account):
    """Generate options pivot report for current year (PDF)"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Generating options pivot report for user: {username}, account: {account}")

        click.echo()
        click.echo(f"📊 Generating options pivot report for {username}...")
        if account:
            click.echo(f"   Account: {account}")
        click.echo()

        report = OptionsPivotReport(db, username, account=account)
        report_path = report.report()

        logger.info(f"Options Pivot report generated: {report_path}")

        click.echo("=" * 60)
        click.secho("REPORT GENERATED", bold=True, fg="green")
        click.echo("=" * 60)
        click.echo(f"File: {report_path}")
        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error generating pivot report: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating pivot report: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("activity")
@click.option("--date", help="End date in YYYY-MM-DD format (default: today)")
@click.option("--username", help="Filter by username")
@click.option("--account", help="Filter by account")
@click.option("--days", default=1, type=int, help="Number of days to include (1=single day, 7=week)")
@click.option("--save", is_flag=True, help="Save report to file")
@click.pass_context
def activity(ctx, date, username, account, days, save):
    """Generate daily activity report (text format)"""
    db = ctx.obj["db"]

    try:
        # Parse date or use today
        if date:
            try:
                report_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                click.secho("\n✗ Invalid date format. Use YYYY-MM-DD\n", fg="red")
                ctx.exit(1)
        else:
            report_date = datetime.now()

        date_str = report_date.strftime("%Y-%m-%d")

        logger.info(f"Generating activity report - date: {date_str}, username: {username}, account: {account}")

        click.echo()
        click.echo(f"📊 Generating activity report for {date_str}...")
        if username:
            click.echo(f"   User: {username}")
        if account:
            click.echo(f"   Account: {account}")
        click.echo()

        # Generate the report using ActivityReport class
        report = ActivityReport(db, date_str, username=username, account=account, days=days)
        report_text = report.generate()

        # Print to console
        click.echo(report_text)

        # Save to file if requested
        if save:
            filepath = report.save()
            click.echo()
            click.secho(f"✓ Report saved to: {filepath}", fg="green")
            click.echo()

    except Exception as e:
        logger.error(f"Error generating activity report: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating activity report: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("digest")
@click.option("--type", type=click.Choice(["daily", "weekly", "auto"]), default="auto",
              help="Digest type (default: auto-detect from day)")
@click.option("--guild-id", type=int, help="Guild ID (defaults to first guild in config)")
@click.option("--enable-llm/--no-llm", default=False, help="Enable LLM narrative summary")
@click.option("--llm-model", type=str, default=None,
              help="LLM model key (e.g., ollama-qwen-32b, claude-sonnet, claude-haiku)")
@click.option("--llm-temperature", type=float, default=1.0,
              help="LLM temperature 0.0-2.0 (default: 1.0)")
@click.option("--save", type=click.Choice(["markdown", "pdf", "both"]), default="both",
              help="Save format (default: both)")
@click.option("--charts/--no-charts", default=True, help="Include charts (default: True)")
@click.pass_context
def digest(ctx, type, guild_id, enable_llm, llm_model, llm_temperature, save, charts):
    """
    Generate daily/weekly community digest.

    Creates a comprehensive digest of community trading activity including:
    - Top performing symbols
    - Scanner picks
    - Leaderboards (weekly only)
    - Channel statistics
    - Optional LLM narrative summary

    Examples:
      cli.py reports digest --guild-id 123 --enable-llm
      cli.py reports digest --type weekly --save markdown --no-charts
    """
    import constants as const
    from daily_digest import DailyDigest

    db = ctx.obj["db"]

    try:
        # Default to first guild if not specified
        if not guild_id:
            guild_id = const.GUILDS[0] if const.GUILDS else None
            if not guild_id:
                click.secho("\n✗ No guild_id specified and no guilds in config", fg="red", err=True)
                ctx.exit(1)

        click.echo()
        click.echo(f"📰 Generating {type} digest for guild {guild_id}...")
        if enable_llm:
            model_str = f" ({llm_model})" if llm_model else ""
            click.echo(f"   LLM enabled{model_str} (temperature: {llm_temperature})")
        click.echo(f"   Save format: {save}")
        click.echo(f"   Charts: {'Yes' if charts else 'No'}")
        click.echo()

        # Generate digest
        digest_obj = DailyDigest(db, guild_id, enable_llm=enable_llm,
                                llm_temperature=llm_temperature, llm_model=llm_model)

        # Generate digest content
        digest_content = digest_obj.generate_digest()

        # Save if requested
        saved_files = []
        if save != "both":
            # Just display
            result = {"content": digest_content}
        else:
            # Save to files (save_digest only saves markdown, returns filepath)
            filepath = digest_obj.save_digest(
                digest_text=digest_content
            )
            result = {
                "content": digest_content,
                "markdown_path": filepath
            }

        # Display result
        if result.get("content"):
            click.echo("=" * 80)
            click.echo(result["content"])
            click.echo("=" * 80)
            click.echo()

        # Show saved file paths
        if result.get("markdown_path"):
            click.secho(f"✓ Markdown saved: {result['markdown_path']}", fg="green")
        if result.get("pdf_path"):
            click.secho(f"✓ PDF saved: {result['pdf_path']}", fg="green")
        if result.get("charts"):
            click.secho(f"✓ {len(result['charts'])} chart(s) generated", fg="green")

        click.echo()

    except Exception as e:
        logger.error(f"Error generating digest: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating digest: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("market-sentiment")
@click.pass_context
def market_sentiment(ctx):
    """
    Get current market sentiment indicators.

    Displays:
    - VIX (CBOE Volatility Index)
    - CNN Fear & Greed Index
    - Crypto Fear & Greed Index

    These indicators help gauge overall market sentiment and risk levels.
    """
    from market_sentiment import MarketSentiment

    try:
        click.echo()
        click.echo("📊 Fetching market sentiment indicators...")
        click.echo()

        sentiment = MarketSentiment()
        result = sentiment.get_all_sentiment_indicators()

        # Display results
        click.echo("=" * 60)
        click.secho("MARKET SENTIMENT INDICATORS", bold=True, fg="cyan")
        click.echo("=" * 60)
        click.echo()

        # VIX
        if "vix" in result:
            vix = result["vix"]
            click.secho("VIX (CBOE Volatility Index):", bold=True)
            click.echo(f"  Current: {vix.get('current', 'N/A')}")
            click.echo(f"  Status: {vix.get('status', 'N/A')}")
            click.echo(f"  Interpretation: {vix.get('interpretation', 'N/A')}")
            click.echo()

        # Fear & Greed
        if "fear_greed" in result:
            fg = result["fear_greed"]
            click.secho("CNN Fear & Greed Index:", bold=True)
            click.echo(f"  Current: {fg.get('value', 'N/A')} - {fg.get('text', 'N/A')}")
            click.echo()

        # Crypto Fear & Greed
        if "crypto_fear_greed" in result:
            cfg = result["crypto_fear_greed"]
            click.secho("Crypto Fear & Greed Index:", bold=True)
            click.echo(f"  Current: {cfg.get('value', 'N/A')} - {cfg.get('classification', 'N/A')}")
            click.echo()

        click.echo("=" * 60)
        click.echo()

    except Exception as e:
        logger.error(f"Error fetching market sentiment: {e}", exc_info=True)
        click.secho(f"\n✗ Error fetching market sentiment: {e}\n", fg="red", err=True)
        ctx.exit(1)


@reports.command("catch-up")
@click.option("--username", required=True, help="Username requesting the digest")
@click.option("--model", required=True, help="LLM model to use (e.g., claude-sonnet, ollama-qwen-32b)")
@click.option("--guild-id", type=int, required=True, help="Discord guild/server ID (required for data isolation)")
@click.option("--days", type=int, default=1, help="Number of days to catch up on (1-30, default: 1)")
@click.option("--temperature", type=float, default=0.5, help="LLM temperature 0.0-2.0 (default: 0.5, lower=more factual)")
@click.option("--voice", type=click.Choice(["professional", "casual", "technical", "energetic"]),
              default="casual", help="Tone/style of the digest (default: casual)")
@click.pass_context
def catch_up(ctx, username, model, guild_id, days, temperature, voice):
    """
    Generate on-demand catch-up digest for missed community activity.

    Uses LLM with MCP tools to analyze trading activity, discussions, and
    market context over the specified time period.

    Examples:
        # Get 1-day catch-up in casual voice with Claude
        python src/cli.py reports catch-up --username johndoe --model claude-sonnet --guild-id 1405962109262757980

        # Get 7-day catch-up with professional tone using Ollama
        python src/cli.py reports catch-up --username johndoe --model ollama-qwen-32b --guild-id 1405962109262757980 --days 7 --voice professional

        # Get creative 3-day digest with high temperature
        python src/cli.py reports catch-up --username johndoe --model claude-sonnet --guild-id 1405962109262757980 --days 3 --temperature 1.2 --voice energetic
    """
    db = ctx.obj["db"]

    try:
        logger.info(
            f"Generating catch-up digest - username: {username}, guild_id: {guild_id}, days: {days}, "
            f"temperature: {temperature}, voice: {voice}"
        )

        click.echo()
        click.echo(f"📊 Generating {days}-day catch-up digest...")
        click.echo(f"   User: {username}")
        click.echo(f"   Guild ID: {guild_id}")
        click.echo(f"   Model: {model}")
        click.echo(f"   Temperature: {temperature}")
        click.echo(f"   Voice: {voice}")
        click.echo()
        click.secho("⏳ This may take 30-60 seconds as the LLM analyzes community data...", fg="yellow")
        click.echo()

        # Get MCP URL from settings
        from system_settings import get_settings
        settings = get_settings(db)
        mcp_url = settings.get(const.SETTING_TRADING_MCP_URL)

        # Generate the digest (no metrics tracking for CLI)
        report = CatchUpReport(
            mcp_url=mcp_url,
            username=username,
            model=model,
            guild_id=guild_id,
            days=days,
            temperature=temperature,
            voice=voice,
            metrics_tracker=None
        )

        digest_text = report.generate()

        # Print to console
        click.echo(digest_text)
        click.echo()
        click.secho("✓ Digest generated successfully", fg="green")
        click.echo()

    except Exception as e:
        logger.error(f"Error generating catch-up digest: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating catch-up digest: {e}\n", fg="red", err=True)
        click.echo()
        click.echo("Troubleshooting:")
        click.echo("  • Ensure MCP server is running on port 8000")
        click.echo("  • Check ANTHROPIC_API_KEY is set in .env")
        click.echo("  • Verify database has community messages")
        click.echo()
        ctx.exit(1)
