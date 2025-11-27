"""
Messages Commands

Commands for searching and analyzing harvested Discord messages.
Provides content search, ticker mentions, and user activity analysis.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import json
import logging
from datetime import datetime

import click
from tabulate import tabulate

import constants as const
from messages import Messages
from sentiment_analyzer import SentimentAnalyzer
from system_settings import get_settings
from vision_strategy import analyze_trading_image


logger = logging.getLogger(__name__)


@click.group()
def messages():
    """Search and analyze harvested messages"""


@messages.command("list")
@click.option("--channel", help="Filter by channel name")
@click.option(
    "--category",
    type=click.Choice(["sentiment", "news"]),
    help="Filter by category (sentiment=trading discussions, news=market updates)",
)
@click.option("--limit", type=int, default=20, help="Number of messages to display")
@click.option("--include-deleted", is_flag=True, help="Include deleted messages")
@click.option("--full", is_flag=True, help="Show full message content (no truncation)")
@click.pass_context
def list_messages(ctx, channel, category, limit, include_deleted, full):
    """List recent harvested messages"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        logger.info(f"Listing messages - channel: {channel}, category: {category}, limit: {limit}")

        message_list = messages_obj.get_recent(
            channel_name=channel, category=category, limit=limit, include_deleted=include_deleted
        )

        if not message_list:
            click.echo()
            click.secho("No messages found", fg="yellow")
            if not channel:
                click.secho(
                    "💡 Tip: Messages will appear here after harvesting Discord channels", fg="cyan"
                )
            click.echo()
            return

        # Display messages
        click.echo()
        filter_parts = []
        if channel:
            filter_parts.append(f"channel=#{channel}")
        if category:
            filter_parts.append(f"category={category}")
        filter_str = f" ({', '.join(filter_parts)})" if filter_parts else ""
        deleted_str = " (including deleted)" if include_deleted else ""
        click.echo(f"Showing {len(message_list)} messages{filter_str}{deleted_str}")
        click.echo("=" * 120)
        click.echo()

        for msg in message_list:
            deleted_tag = " [DELETED]" if msg.is_deleted else ""

            # Show full content if --full flag is set, otherwise truncate
            if full:
                content = msg.content
            else:
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content

            click.echo(f"{msg.timestamp} | #{msg.channel_name} | @{msg.username}{deleted_tag}")
            click.echo(f"  {content}")
            if msg.tickers:
                click.secho(f"  📊 Tickers: {', '.join(msg.tickers)}", fg="cyan")
            click.echo()

        click.echo("=" * 120)
        click.echo()

    except Exception as e:
        logger.error(f"Error listing messages: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing messages: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("get")
@click.option("--message-id", required=True, type=int, help="Discord message ID")
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.pass_context
def get_message(ctx, message_id, json_output):
    """Get detailed message information by ID"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        logger.info(f"Getting message ID: {message_id}")

        # Get message using Messages class
        msg = messages_obj.get_message(message_id)

        if not msg:
            click.echo()
            click.secho(f"Message {message_id} not found", fg="yellow")
            click.echo()
            return

        # Get tickers from message_tickers table (Stage 1 extraction)
        tickers = messages_obj.get_message_tickers(message_id)

        # Convert Message object to dict for display
        msg_data = {
            "message_id": msg.message_id,
            "guild_id": msg.guild_id,
            "channel_name": msg.channel_name,
            "username": msg.username,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "has_attachments": len(msg.attachment_urls) > 0 if msg.attachment_urls else False,
            "attachment_urls": "\n".join(msg.attachment_urls) if msg.attachment_urls else None,
            "extracted_data": msg.extracted_data,
            "category": msg.category,
            "is_deleted": msg.is_deleted,
            "deleted_at": msg.deleted_at,
            "harvested_at": msg.harvested_at,
            "sentiment": msg.sentiment,
            "sentiment_confidence": msg.sentiment_confidence,
            "sentiment_reasoning": msg.sentiment_reasoning,
            "tickers": tickers,  # From message_tickers table
        }

        if json_output:
            # JSON output - parse extracted_data string to nested JSON
            if msg_data.get("extracted_data") and isinstance(msg_data["extracted_data"], str):
                try:
                    msg_data["extracted_data"] = json.loads(msg_data["extracted_data"])
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

            click.echo(json.dumps(msg_data, indent=2))
        else:
            # Human-readable output
            click.echo()
            click.secho("=" * 80, fg="cyan")
            click.secho(f"MESSAGE DETAILS: {message_id}", fg="cyan", bold=True)
            click.secho("=" * 80, fg="cyan")
            click.echo()

            # Basic info
            click.secho("Basic Info:", fg="yellow", bold=True)
            click.echo(f"  Channel: #{msg_data['channel_name']}")
            click.echo(f"  User: {msg_data['username']}")
            click.echo(f"  Timestamp: {msg_data['timestamp']}")
            click.echo(f"  Category: {msg_data['category']}")
            click.echo(f"  Harvested: {msg_data['harvested_at']}")
            if msg_data["is_deleted"]:
                click.secho(f"  ⚠️  Deleted: {msg_data['deleted_at']}", fg="red")
            click.echo()

            # Content
            if msg_data["content"]:
                click.secho("Content:", fg="yellow", bold=True)
                click.echo(f"  {msg_data['content']}")
                click.echo()

            # Tickers (from message_tickers table - Stage 1 text extraction)
            if tickers:
                click.secho("Tickers:", fg="yellow", bold=True)
                click.echo(f"  {', '.join(tickers)}")
                click.echo()

            # Attachments
            if msg_data["has_attachments"]:
                click.secho("Attachments:", fg="yellow", bold=True)
                attachment_urls = msg_data["attachment_urls"]
                urls = (
                    attachment_urls.split("\n")
                    if attachment_urls and isinstance(attachment_urls, str)
                    else []
                )
                for url in urls:
                    if url.strip():
                        click.echo(f"  🔗 {url.strip()}")
                click.echo()

            # Extracted data (always show status)
            click.secho("Extracted Data:", fg="yellow", bold=True)
            if msg_data["extracted_data"]:
                # Parse JSON string if needed
                if isinstance(msg_data["extracted_data"], str):
                    ex_data = json.loads(msg_data["extracted_data"])
                else:
                    ex_data = msg_data["extracted_data"]

                # Image type
                if ex_data.get("image_type"):
                    click.echo(f"  Type: {ex_data['image_type']}")

                # Tickers
                if ex_data.get("tickers"):
                    click.echo(f"  Tickers: {', '.join(ex_data['tickers'])}")

                # Sentiment
                if ex_data.get("sentiment"):
                    sentiment_color = {
                        "bullish": "green",
                        "bearish": "red",
                        "neutral": "yellow",
                    }.get(ex_data["sentiment"], "white")
                    click.secho(f"  Sentiment: {ex_data['sentiment']}", fg=sentiment_color)

                # Trades
                if ex_data.get("trades"):
                    click.echo(f"\n  Trades ({len(ex_data['trades'])}):")
                    for i, trade in enumerate(ex_data["trades"], 1):
                        # Handle both 'action' and 'operation' field names
                        op = trade.get("action") or trade.get("operation", "N/A")
                        qty = trade.get("quantity", 0)
                        ticker = trade.get("ticker", "N/A")
                        strike = trade.get("strike", 0.0)
                        opt_type = trade.get("option_type", "N/A")
                        premium = trade.get("premium", 0.0)
                        exp = trade.get("expiration", "N/A")
                        source = trade.get("source", "unknown")

                        click.echo(
                            f"    {i}. {op} {qty}x {ticker} ${strike} {opt_type} @ ${premium}"
                        )
                        click.echo(f"       Exp: {exp} | Source: {source}")

                # Metadata
                if ex_data.get("extraction_metadata"):
                    meta = ex_data["extraction_metadata"]
                    click.echo("\n  Processing:")
                    click.echo(f"    Model: {meta.get('model_used', 'N/A')}")
                    click.echo(f"    Time: {meta.get('processing_time_ms', 0)}ms")
                    click.echo(f"    Confidence: {meta.get('confidence', 0):.2f}")

                # Raw OCR text (truncated)
                if ex_data.get("raw_text"):
                    raw_text = ex_data["raw_text"]
                    preview = raw_text[:200] + "..." if len(raw_text) > 200 else raw_text
                    click.echo("\n  OCR Preview:")
                    click.echo(f"    {preview}")

                click.echo()
            else:
                # No extracted data
                click.echo("  (None)")
                click.echo()

            # Overall sentiment (separate from extracted_data)
            if msg_data.get("sentiment"):
                click.secho("Overall Sentiment:", fg="yellow", bold=True)
                sentiment_value = str(msg_data["sentiment"]) if msg_data["sentiment"] else "unknown"
                sentiment_color = {"bullish": "green", "bearish": "red", "neutral": "yellow"}.get(
                    sentiment_value, "white"
                )
                click.secho(f"  {sentiment_value}", fg=sentiment_color, bold=True)
                if msg_data.get("sentiment_confidence"):
                    click.echo(f"  Confidence: {msg_data['sentiment_confidence']:.2f}")
                if msg_data.get("sentiment_reasoning"):
                    reasoning: str = str(msg_data["sentiment_reasoning"])
                    preview = reasoning[:300] + "..." if len(reasoning) > 300 else reasoning
                    click.echo(f"  Reasoning: {preview}")
                click.echo()

            click.secho("=" * 80, fg="cyan")
            click.echo()

    except Exception as e:
        logger.error(f"Error getting message: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting message: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("by-ticker")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for data isolation)")
@click.option("--ticker", required=True, help="Ticker symbol")
@click.option("--limit", type=int, default=20, help="Number of messages to display")
@click.option("--full", is_flag=True, help="Show full message content (no truncation)")
@click.pass_context
def by_ticker(ctx, guild_id, ticker, limit, full):
    """Find messages mentioning a ticker"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        logger.info(f"Finding messages for ticker: {ticker} in guild: {guild_id}")

        message_list = messages_obj.get_by_ticker(ticker, limit=limit, guild_id=guild_id)

        if not message_list:
            click.echo()
            click.secho(f"No messages found mentioning ${ticker.upper()}", fg="yellow")
            click.secho(
                "💡 Tip: Make sure messages have been harvested and ticker is valid", fg="cyan"
            )
            click.echo()
            return

        # Display messages
        click.echo()
        click.echo(f"Messages mentioning ${ticker.upper()} ({len(message_list)} found)")
        click.echo("=" * 120)
        click.echo()

        for msg in message_list:
            deleted_tag = " [DELETED]" if msg.is_deleted else ""

            # Show full content if --full flag is set, otherwise truncate
            if full:
                content = msg.content
            else:
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content

            click.echo(f"{msg.timestamp} | #{msg.channel_name} | @{msg.username}{deleted_tag}")
            click.echo(f"  {content}")
            if msg.tickers and len(msg.tickers) > 1:
                click.secho(
                    f"  📊 Also mentions: {', '.join([t for t in msg.tickers if t != ticker.upper()])}",
                    fg="cyan",
                )
            click.echo()

        click.echo("=" * 120)
        click.echo()

    except Exception as e:
        logger.error(f"Error finding messages by ticker: {e}", exc_info=True)
        click.secho(f"\n✗ Error finding messages: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("by-user")
@click.option("--username", required=True, help="Username")
@click.option("--limit", type=int, default=20, help="Number of messages to display")
@click.option("--include-deleted", is_flag=True, help="Include deleted messages")
@click.option("--full", is_flag=True, help="Show full message content (no truncation)")
@click.pass_context
def by_user(ctx, username, limit, include_deleted, full):
    """Find messages from a specific user"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        logger.info(f"Messages by user - username: {username}, limit: {limit}")

        message_list = messages_obj.get_by_user(
            username, limit=limit, include_deleted=include_deleted
        )

        if not message_list:
            click.echo()
            click.secho(f"No messages found from user: {username}", fg="yellow")
            click.secho(
                "💡 Tip: Make sure messages have been harvested and username is correct", fg="cyan"
            )
            click.echo()
            return

        # Display messages
        click.echo()
        click.echo(f"Messages from @{username} ({len(message_list)} found)")
        click.echo("=" * 120)
        click.echo()

        for msg in message_list:
            deleted_tag = " [DELETED]" if msg.is_deleted else ""

            # Show full content if --full flag is set, otherwise truncate
            if full:
                content = msg.content
            else:
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content

            click.echo(f"{msg.timestamp} | #{msg.channel_name}{deleted_tag}")
            click.echo(f"  {content}")
            if msg.tickers:
                click.secho(f"  📊 Tickers: {', '.join(msg.tickers)}", fg="cyan")
            click.echo()

        click.echo("=" * 120)
        click.echo()

    except Exception as e:
        logger.error(f"Error finding messages by user: {e}", exc_info=True)
        click.secho(f"\n✗ Error finding messages: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("user-stats")
@click.option("--username", required=True, help="Username")
@click.option("--limit", type=int, default=20, help="Number of top tickers to display")
@click.pass_context
def user_stats(ctx, username, limit):
    """Show statistics for a specific user's messages"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        logger.info(f"User stats - username: {username}")

        stats = messages_obj.get_user_stats(username, limit=limit)

        if stats["total_messages"] == 0:
            click.echo()
            click.secho(f"No messages found from user: {username}", fg="yellow")
            click.secho(
                "💡 Tip: Make sure messages have been harvested and username is correct", fg="cyan"
            )
            click.echo()
            return

        # Display user statistics
        click.echo()
        click.echo("=" * 80)
        click.secho(f"STATISTICS FOR @{username}", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total messages:   {stats['total_messages']:,}")
        click.echo(f"Active messages:  {stats['active_messages']:,}")
        click.echo(f"Deleted messages: {stats['deleted_messages']:,}")
        click.echo()

        # Display top tickers if available
        if stats["top_tickers"]:
            click.secho("TOP TICKERS MENTIONED:", bold=True)
            click.echo("=" * 80)

            table_data = []
            for ticker, count in stats["top_tickers"]:
                table_data.append([ticker, count])

            click.echo(tabulate(table_data, headers=["Ticker", "Mentions"], tablefmt="psql"))
            click.echo("=" * 80)

        click.echo()

    except Exception as e:
        logger.error(f"Error getting user stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error getting user stats: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("analyze-image")
@click.option("--url", required=True, help="Discord CDN image URL")
@click.option(
    "--model",
    default=None,
    help="Vision model to use (default: from VISION_OCR_MODEL in constants)",
)
@click.option("--json-output", is_flag=True, help="Output raw JSON instead of formatted text")
@click.pass_context
def analyze_image(ctx, url, model, json_output):
    """Analyze a trading image and extract structured data"""
    db = ctx.obj["db"]

    try:
        # Use default model from system settings if not specified
        settings = get_settings(db)
        model = model or settings.get(const.SETTING_VISION_OCR_MODEL)

        logger.info(f"Analyzing image: {url}")

        # Run async analysis with model
        result = asyncio.run(analyze_trading_image(url, ocr_model=model))

        if json_output:
            # Raw JSON output for scripting
            click.echo(json.dumps(result, indent=2))
            return

        # Formatted human-readable output
        click.echo()
        click.echo("=" * 80)
        click.secho("IMAGE ANALYSIS RESULTS", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Image type
        image_type_colors = {
            "trade_execution": "green",
            "technical_analysis": "cyan",
            "account_summary": "yellow",
            "error": "red",
            "other": "white",
        }
        image_type = result.get("image_type", "other")
        color = image_type_colors.get(image_type, "white")
        click.secho(f"Image Type: {image_type.upper().replace('_', ' ')}", fg=color, bold=True)
        click.echo()

        # Sentiment
        if result.get("sentiment"):
            sentiment_colors = {"bullish": "green", "bearish": "red", "neutral": "yellow"}
            sentiment_color = sentiment_colors.get(result["sentiment"], "white")
            click.secho(f"Sentiment: {result['sentiment'].upper()}", fg=sentiment_color)
            click.echo()

        # Tickers
        if result.get("tickers"):
            click.secho("Tickers Found:", bold=True)
            click.echo(f"  {', '.join(result['tickers'])}")
            click.echo()

        # Trades
        if result.get("trades"):
            click.secho(f"Trades Extracted ({len(result['trades'])}):", bold=True)
            click.echo("=" * 80)
            for i, trade in enumerate(result["trades"], 1):
                click.echo(f"\n  Trade #{i}:")
                click.echo(f"    Operation:  {trade.get('operation')}")
                click.echo(f"    Symbol:     {trade.get('symbol')}")
                click.echo(f"    Contracts:  {trade.get('contracts')}")
                click.echo(f"    Strike:     ${trade.get('strike')}")
                click.echo(f"    Type:       {trade.get('option_type')}")
                click.echo(f"    Premium:    ${trade.get('premium')}")
                click.echo(f"    Total:      ${trade.get('total')}")
                click.echo(f"    Expiration: {trade.get('expiration')}")
                click.secho(f"    Raw:        {trade.get('raw_string')}", fg="cyan")
            click.echo()
            click.echo("=" * 80)

        # Account values
        if result.get("account_value"):
            click.secho("Account Information:", bold=True)
            click.echo(f"  Account Value: ${result['account_value']:,.2f}")
            if result.get("daily_pnl"):
                pnl = result["daily_pnl"]
                pnl_color = "green" if pnl > 0 else "red"
                click.secho(f"  Daily P&L:     ${pnl:,.2f}", fg=pnl_color)
            click.echo()

        # TA indicators
        if result.get("ta_indicators"):
            click.secho("Technical Indicators:", bold=True)
            click.echo(f"  {', '.join(result['ta_indicators'])}")
            click.echo()

        # Raw text
        if result.get("raw_text"):
            click.secho("Extracted Text:", bold=True)
            click.echo("=" * 80)
            # Limit to first 500 chars for readability
            raw_text = result["raw_text"]
            if len(raw_text) > 500:
                click.echo(raw_text[:500] + "...")
                click.secho(f"\n(Truncated - {len(raw_text)} total chars)", fg="yellow")
            else:
                click.echo(raw_text)
            click.echo()
            click.echo("=" * 80)

        click.echo()

    except Exception as e:
        logger.error(f"Error analyzing image: {e}", exc_info=True)
        click.secho(f"\n✗ Error analyzing image: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("vision-raw-text")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for data isolation)")
@click.option("--channel", required=True, help="Channel name (e.g., 💸darkminer-moves)")
@click.option("--days", type=int, default=7, help="Look back N days (default: 7)")
@click.option("--limit", type=int, default=20, help="Number of messages to show (default: 20)")
@click.option("--output", type=click.Path(), help="Save to file instead of displaying")
@click.option("--full", is_flag=True, help="Show full raw text (no truncation)")
@click.pass_context
def vision_raw_text(ctx, guild_id, channel, days, limit, output, full):
    """
    Export raw vision OCR text for QC review

    Displays the raw text extracted from images by the vision model.
    Useful for quality control and improving vision model performance.

    Examples:
        # View recent extractions
        cli.py messages vision-raw-text --guild-id 1405962109262757980 --channel 💸darkminer-moves --days 7

        # Export to file for review
        cli.py messages vision-raw-text --guild-id 1405962109262757980 --channel 💸darkminer-moves --days 30 --output vision_qc.txt --full

        # Show all extractions (no limit)
        cli.py messages vision-raw-text --guild-id 1405962109262757980 --channel 💸darkminer-moves --days 7 --limit 999
    """
    db = ctx.obj["db"]

    try:
        logger.info(
            f"Fetching vision raw text - guild: {guild_id}, channel: {channel}, days: {days}"
        )

        query = """
        SELECT
            message_id,
            datetime(timestamp) as timestamp,
            username,
            content,
            json_extract(extracted_data, '$.raw_text') as raw_text,
            json_extract(extracted_data, '$.image_type') as image_type,
            json_extract(extracted_data, '$.extraction_metadata.model_used') as model_used,
            json_extract(extracted_data, '$.extraction_metadata.processing_time_ms') as processing_time_ms,
            json_extract(extracted_data, '$.trades') as trades_json
        FROM harvested_messages
        WHERE guild_id = ?
          AND channel_name = ?
          AND has_attachments = 1
          AND extracted_data IS NOT NULL
          AND json_extract(extracted_data, '$.raw_text') IS NOT NULL
          AND timestamp >= datetime('now', '-' || ? || ' days')
        ORDER BY timestamp DESC
        LIMIT ?
        """

        results = db.query_parameterized(query, (guild_id, channel, days, limit))

        if not results:
            click.echo()
            click.secho(
                f"No vision extractions found for #{channel} in the last {days} days", fg="yellow"
            )
            click.echo()
            return

        # Prepare output
        output_lines = []
        output_lines.append("=" * 100)
        output_lines.append("VISION RAW TEXT EXPORT")
        output_lines.append(f"Guild ID: {guild_id}")
        output_lines.append(f"Channel: {channel}")
        output_lines.append(f"Days: {days}")
        output_lines.append(f"Count: {len(results)}")
        output_lines.append("=" * 100)
        output_lines.append("")

        for row in results:
            (
                message_id,
                timestamp,
                username,
                content,
                raw_text,
                image_type,
                model_used,
                processing_time_ms,
                trades_json,
            ) = row

            output_lines.append("-" * 100)
            output_lines.append(f"Message ID: {message_id}")
            output_lines.append(f"Timestamp:  {timestamp}")
            output_lines.append(f"User:       {username}")
            output_lines.append(f"Image Type: {image_type or 'unknown'}")
            output_lines.append(f"Model:      {model_used or 'unknown'}")
            output_lines.append(f"Time:       {processing_time_ms or 0}ms")
            output_lines.append("")

            # Message content
            output_lines.append("MESSAGE CONTENT:")
            if content:
                msg_preview = content[:200] + "..." if len(content) > 200 and not full else content
                output_lines.append(msg_preview)
            else:
                output_lines.append("(no text)")
            output_lines.append("")

            # Trades extracted
            if trades_json and trades_json != "null":
                try:
                    import json as json_module

                    trades = json_module.loads(trades_json)
                    output_lines.append(f"TRADES EXTRACTED: {len(trades)}")
                    for i, trade in enumerate(trades, 1):
                        output_lines.append(
                            f"  {i}. {trade.get('operation')} {trade.get('contracts')}x {trade.get('symbol')} {trade.get('strike')}{trade.get('option_type')} @ ${trade.get('premium')}"
                        )
                    output_lines.append("")
                except:
                    pass

            # Raw vision text
            output_lines.append("RAW VISION TEXT:")
            output_lines.append("-" * 100)
            if raw_text:
                if full:
                    output_lines.append(raw_text)
                # Truncate to 500 chars for display
                elif len(raw_text) > 500:
                    output_lines.append(raw_text[:500])
                    output_lines.append(f"... (truncated - {len(raw_text)} total chars)")
                else:
                    output_lines.append(raw_text)
            else:
                output_lines.append("(no raw text)")
            output_lines.append("-" * 100)
            output_lines.append("")

        output_lines.append("=" * 100)
        output_lines.append(f"END OF EXPORT ({len(results)} messages)")
        output_lines.append("=" * 100)

        # Write to file or display
        output_text = "\n".join(output_lines)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(output_text)
            click.echo()
            click.secho(f"✓ Exported {len(results)} vision extractions to: {output}", fg="green")
            click.echo()
        else:
            click.echo()
            click.echo(output_text)
            click.echo()

    except Exception as e:
        logger.error(f"Error exporting vision raw text: {e}", exc_info=True)
        click.secho(f"\n✗ Error exporting vision raw text: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("vision-stats")
@click.pass_context
def vision_stats(ctx):
    """Show vision analysis statistics and coverage"""
    db = ctx.obj["db"]

    try:
        logger.info("Showing vision analysis statistics")

        messages_obj = Messages(db)
        stats = messages_obj.get_vision_processing_stats()

        click.echo()
        click.echo("=" * 80)
        click.secho("VISION ANALYSIS COVERAGE", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total images:      {stats['messages_with_images']:,}")
        click.echo(
            f"Analyzed:          {stats['messages_processed']:,} ({stats['success_rate']:.1f}%)"
        )
        click.echo(
            f"Not analyzed:      {stats['messages_with_images'] - stats['messages_processed']:,}"
        )
        if stats["avg_processing_time_ms"] > 0:
            click.echo(f"Avg processing:    {stats['avg_processing_time_ms']:.0f}ms")
        click.echo()

        # Image type distribution
        if stats["image_types"]:
            click.secho("IMAGE TYPE DISTRIBUTION:", bold=True)
            click.echo("=" * 80)
            table_data = []
            total_types = sum(stats["image_types"].values())
            for image_type, count in sorted(
                stats["image_types"].items(), key=lambda x: x[1], reverse=True
            ):
                pct = (count / total_types * 100) if total_types > 0 else 0
                table_data.append([image_type or "unknown", f"{count:,}", f"{pct:.1f}%"])
            click.echo(
                tabulate(table_data, headers=["Type", "Count", "Percentage"], tablefmt="psql")
            )
            click.echo("=" * 80)
            click.echo()

        # Models used
        if stats["models_used"]:
            click.secho("MODELS USED:", bold=True)
            click.echo("=" * 80)
            table_data = []
            for model, count in sorted(
                stats["models_used"].items(), key=lambda x: x[1], reverse=True
            ):
                table_data.append([model, f"{count:,}"])
            click.echo(tabulate(table_data, headers=["Model", "Count"], tablefmt="psql"))
            click.echo("=" * 80)
            click.echo()

    except Exception as e:
        logger.error(f"Error showing vision stats: {e}", exc_info=True)
        click.secho(f"\n✗ Error showing vision stats: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("trending-tickers")
@click.option("--guild-id", type=int, required=True, help="Guild ID to analyze")
@click.option("--days", type=int, default=7, help="Number of days to analyze (default: 7)")
@click.option("--min-mentions", type=int, default=3, help="Minimum mentions to show (default: 3)")
@click.option("--limit", type=int, default=20, help="Number of tickers to show (default: 20)")
@click.pass_context
def trending_tickers(ctx, guild_id, days, min_mentions, limit):
    """Show trending tickers from vision-analyzed trading images"""
    db = ctx.obj["db"]

    try:
        logger.info(
            f"Finding trending tickers for guild {guild_id} - days: {days}, min_mentions: {min_mentions}"
        )

        messages_obj = Messages(db)
        rows = messages_obj.get_trending_tickers(
            days=days, min_mentions=min_mentions, limit=limit, guild_id=guild_id
        )

        click.echo()
        click.echo("=" * 80)
        click.secho(f"TRENDING TICKERS - Guild {guild_id} (Last {days} Days)", bold=True)
        click.echo("=" * 80)

        if not rows:
            click.secho(f"No tickers found with at least {min_mentions} mentions", fg="yellow")
        else:
            table_data = []
            for ticker, mentions, active_days in rows:
                table_data.append([ticker, f"{mentions:,}", f"{active_days}"])
            click.echo(
                tabulate(table_data, headers=["Ticker", "Mentions", "Active Days"], tablefmt="psql")
            )
            click.echo("=" * 80)
            click.echo(f"Showing {len(rows)} tickers")

        click.echo()

    except Exception as e:
        logger.error(f"Error finding trending tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error finding trending tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("ticker-sentiment")
@click.argument("ticker")
@click.pass_context
def ticker_sentiment(ctx, ticker):
    """Show sentiment analysis for a specific ticker from images"""
    db = ctx.obj["db"]

    try:
        logger.info(f"Analyzing sentiment for ticker: {ticker}")

        messages_obj = Messages(db)
        stats = messages_obj.get_ticker_sentiment_stats(ticker)

        click.echo()
        click.echo("=" * 80)
        click.secho(f"SENTIMENT ANALYSIS: ${stats['ticker']}", bold=True)
        click.echo("=" * 80)

        if stats["total_mentions"] == 0:
            click.secho(f"No sentiment data found for ${ticker}", fg="yellow")
            click.secho(
                "💡 Tip: Make sure images have been analyzed and ticker is mentioned", fg="cyan"
            )
        else:
            click.echo(f"Total mentions: {stats['total_mentions']}")
            click.echo()

            # Calculate percentages
            total = stats["total_mentions"]
            table_data = []
            for sentiment, count in stats["sentiment_breakdown"].items():
                pct = (count / total * 100) if total > 0 else 0
                table_data.append([sentiment, f"{count:,}", f"{pct:.1f}%"])

            click.echo(
                tabulate(table_data, headers=["Sentiment", "Count", "Percentage"], tablefmt="psql")
            )
            click.echo("=" * 80)

        click.echo()

    except Exception as e:
        logger.error(f"Error analyzing ticker sentiment: {e}", exc_info=True)
        click.secho(f"\n✗ Error analyzing ticker sentiment: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("stats")
@click.pass_context
def stats(ctx):
    """Show comprehensive message harvest statistics"""
    db = ctx.obj["db"]

    try:
        logger.info("Generating message harvest statistics")

        click.echo()
        click.echo("=" * 80)
        click.secho("MESSAGE HARVEST STATISTICS", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Overall statistics
        query = """
        SELECT
            COUNT(*) as total_messages,
            COUNT(DISTINCT channel_name) as channels,
            COUNT(DISTINCT username) as users,
            SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_images,
            MIN(DATE(timestamp)) as earliest,
            MAX(DATE(timestamp)) as latest
        FROM harvested_messages
        """
        row = db.query(query)[0]
        total, channels, users, with_images, earliest, latest = row

        click.echo(f"Total messages:        {total:,}")
        click.echo(f"Channels:              {channels}")
        click.echo(f"Users:                 {users}")
        click.echo(f"Messages with images:  {with_images:,}")
        click.echo(f"Date range:            {earliest} to {latest}")
        click.echo()

        # Messages by channel
        query = """
        SELECT
            channel_name,
            COUNT(*) as messages,
            SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_images,
            MIN(DATE(timestamp)) as earliest,
            MAX(DATE(timestamp)) as latest
        FROM harvested_messages
        GROUP BY channel_name
        ORDER BY messages DESC
        """
        rows = db.query(query)

        if rows:
            click.secho("MESSAGES BY CHANNEL:", bold=True)
            click.echo("=" * 80)
            table_data = []
            for channel, messages, images, earliest, latest in rows:
                table_data.append([channel, f"{messages:,}", f"{images:,}", earliest, latest])
            click.echo(
                tabulate(
                    table_data,
                    headers=["Channel", "Messages", "Images", "Earliest", "Latest"],
                    tablefmt="psql",
                )
            )
            click.echo("=" * 80)
            click.echo()

        # Image statistics
        query = """
        SELECT
            COUNT(*) as total_images,
            SUM(CASE WHEN extracted_data IS NOT NULL THEN 1 ELSE 0 END) as analyzed,
            SUM(CASE WHEN extracted_data IS NULL THEN 1 ELSE 0 END) as pending
        FROM harvested_messages
        WHERE has_attachments = 1
        """
        row = db.query(query)[0]
        total_images, analyzed, pending = row

        click.secho("IMAGE ANALYSIS STATUS:", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total images:          {total_images:,}")
        click.echo(f"Analyzed (vision):     {analyzed:,}")
        click.echo(f"Pending analysis:      {pending:,}")
        if total_images > 0:
            pct = (analyzed / total_images) * 100
            click.echo(f"Analysis coverage:     {pct:.1f}%")
        click.echo("=" * 80)
        click.echo()

        # Top users
        query = """
        SELECT
            username,
            COUNT(*) as messages,
            SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_images
        FROM harvested_messages
        GROUP BY username
        ORDER BY messages DESC
        LIMIT 10
        """
        rows = db.query(query)

        if rows:
            click.secho("TOP USERS BY MESSAGE COUNT:", bold=True)
            click.echo("=" * 80)
            table_data = []
            for username, messages, images in rows:
                table_data.append([username, f"{messages:,}", f"{images:,}"])
            click.echo(
                tabulate(
                    table_data, headers=["Username", "Messages", "With Images"], tablefmt="psql"
                )
            )
            click.echo("=" * 80)
            click.echo()

        # Category breakdown
        query = """
        SELECT
            category,
            COUNT(*) as messages,
            SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_images
        FROM harvested_messages
        GROUP BY category
        """
        rows = db.query(query)

        if rows:
            click.secho("CATEGORY BREAKDOWN:", bold=True)
            click.echo("=" * 80)
            table_data = []
            for category, messages, images in rows:
                table_data.append([category, f"{messages:,}", f"{images:,}"])
            click.echo(
                tabulate(
                    table_data, headers=["Category", "Messages", "With Images"], tablefmt="psql"
                )
            )
            click.echo("=" * 80)
            click.echo()

        # Sentiment analysis statistics
        query = """
        SELECT
            COUNT(*) as total_messages,
            SUM(CASE WHEN sentiment IS NOT NULL THEN 1 ELSE 0 END) as analyzed,
            SUM(CASE WHEN sentiment IS NULL THEN 1 ELSE 0 END) as pending
        FROM harvested_messages
        """
        row = db.query(query)[0]
        total_msgs, sentiment_analyzed, sentiment_pending = row

        click.secho("SENTIMENT ANALYSIS STATUS:", bold=True)
        click.echo("=" * 80)
        click.echo(f"Total messages:        {total_msgs:,}")
        click.echo(f"Analyzed (sentiment):  {sentiment_analyzed:,}")
        click.echo(f"Pending analysis:      {sentiment_pending:,}")
        if total_msgs > 0:
            pct = (sentiment_analyzed / total_msgs) * 100
            click.echo(f"Analysis coverage:     {pct:.1f}%")
        click.echo("=" * 80)
        click.echo()

        # Sentiment distribution (if we have data)
        if sentiment_analyzed > 0:
            query = """
            SELECT
                sentiment,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage,
                ROUND(AVG(sentiment_confidence), 2) as avg_confidence
            FROM harvested_messages
            WHERE sentiment IS NOT NULL
            GROUP BY sentiment
            ORDER BY count DESC
            """
            rows = db.query(query)

            if rows:
                click.secho("OVERALL SENTIMENT DISTRIBUTION:", bold=True)
                click.echo("=" * 80)
                table_data = []
                for sentiment, count, pct, avg_conf in rows:
                    sentiment_colors = {"bullish": "green", "bearish": "red", "neutral": "yellow"}
                    table_data.append(
                        [
                            sentiment.upper() if sentiment else "UNKNOWN",
                            f"{count:,}",
                            f"{pct}%",
                            f"{avg_conf:.0%}" if avg_conf else "N/A",
                        ]
                    )
                click.echo(
                    tabulate(
                        table_data,
                        headers=["Sentiment", "Count", "Percentage", "Avg Confidence"],
                        tablefmt="psql",
                    )
                )
                click.echo("=" * 80)
                click.echo()

            # Top tickers by sentiment volume
            query = """
            SELECT
                ticker,
                COUNT(*) as mentions,
                SUM(CASE WHEN sentiment = 'bullish' THEN 1 ELSE 0 END) as bullish,
                SUM(CASE WHEN sentiment = 'bearish' THEN 1 ELSE 0 END) as bearish,
                SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral,
                ROUND(AVG(confidence), 2) as avg_confidence
            FROM message_ticker_sentiment
            GROUP BY ticker
            ORDER BY mentions DESC
            LIMIT 15
            """
            rows = db.query(query)

            if rows:
                click.secho("TOP TICKERS BY SENTIMENT VOLUME:", bold=True)
                click.echo("=" * 80)
                table_data = []
                for ticker, mentions, bullish, bearish, neutral, avg_conf in rows:
                    # Calculate net sentiment (bullish - bearish)
                    net = bullish - bearish
                    net_str = f"+{net}" if net > 0 else str(net)
                    table_data.append(
                        [
                            ticker,
                            f"{mentions:,}",
                            f"{bullish:,}",
                            f"{bearish:,}",
                            f"{neutral:,}",
                            net_str,
                            f"{avg_conf:.0%}" if avg_conf else "N/A",
                        ]
                    )
                click.echo(
                    tabulate(
                        table_data,
                        headers=["Ticker", "Total", "Bull", "Bear", "Neut", "Net", "Conf"],
                        tablefmt="psql",
                    )
                )
                click.echo("=" * 80)

        click.echo()

    except Exception as e:
        logger.error(f"Error generating statistics: {e}", exc_info=True)
        click.secho(f"\n✗ Error generating statistics: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("analyze-sentiment")
@click.option("--days", type=int, default=7, help="Analyze messages from last N days (default: 7)")
@click.option(
    "--limit", type=int, help="Limit number of messages to analyze (default: all in date range)"
)
@click.option("--model", help="Sentiment model to use (default: from SENTIMENT_MODEL in constants)")
@click.option("--update-db", is_flag=True, help="Store sentiment results in database")
@click.option("--force", is_flag=True, help="Re-analyze already analyzed messages")
@click.option("--channel", help="Filter by specific channel name")
@click.pass_context
def analyze_sentiment(ctx, days, limit, model, update_db, force, channel):
    """Analyze sentiment for harvested messages using LLM"""
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)
        analyzer = SentimentAnalyzer(model=model)

        # Get messages for sentiment analysis
        query_parts = [
            "SELECT message_id, content, extracted_data FROM harvested_messages",
            "WHERE 1=1",  # Base condition for easier query building
        ]

        # Add sentiment filter unless force mode is enabled
        if not force:
            query_parts.append("AND sentiment IS NULL")

        query_parts.append(f"AND timestamp >= date('now', '-{days} days')")

        if channel:
            query_parts.append(f"AND channel_name = '{channel}'")

        query_parts.append("ORDER BY timestamp DESC")

        if limit:
            query_parts.append(f"LIMIT {limit}")

        query = " ".join(query_parts)
        rows = db.query(query)

        if not rows:
            click.echo()
            click.secho(f"No unanalyzed messages found in last {days} days", fg="yellow")
            if channel:
                click.secho(f"Channel filter: #{channel}", fg="cyan")
            click.echo()
            return

        total = len(rows)
        click.echo()
        settings = get_settings(db)
        default_model = settings.get(const.SETTING_SENTIMENT_MODEL)
        click.echo("=" * 80)
        click.secho(f"SENTIMENT ANALYSIS (Last {days} Days)", bold=True)
        click.echo("=" * 80)
        click.echo(f"Messages to analyze: {total:,}")
        click.echo(f"Model: {model or default_model}")
        if channel:
            click.echo(f"Channel: #{channel}")
        if update_db:
            click.secho("Database updates: ENABLED", fg="green")
        else:
            click.secho("Database updates: DISABLED (dry run)", fg="yellow")
        click.echo(f"Force reanalyze:   {'Yes' if force else 'No (unanalyzed only)'}")
        click.echo()

        # Process messages
        processed = 0
        errors = 0
        sentiment_counts = {"bullish": 0, "bearish": 0, "neutral": 0}

        async def process_messages():
            nonlocal processed, errors
            for i, (message_id, content, extracted_data) in enumerate(rows, 1):
                try:
                    # Show progress
                    if i % 10 == 0 or i == total:
                        click.echo(f"Progress: {i}/{total} ({100*i//total}%)", nl=False)
                        click.echo("\r", nl=False)

                    # Extract OCR text from extracted_data JSON
                    image_text = None
                    if extracted_data:
                        import json

                        data = (
                            json.loads(extracted_data)
                            if isinstance(extracted_data, str)
                            else extracted_data
                        )
                        image_text = data.get("raw_text")

                    # Analyze sentiment
                    result = await analyzer.analyze_sentiment(
                        message_text=content, image_data=image_text
                    )

                    sentiment = result["sentiment"]
                    confidence = result["confidence"]
                    reasoning = result["reasoning"]
                    tickers = result.get("tickers", [])

                    sentiment_counts[sentiment] += 1
                    processed += 1

                    # Update database if requested
                    if update_db:
                        # Update overall sentiment in messages table
                        db.execute(
                            """UPDATE harvested_messages
                               SET sentiment = ?,
                                   sentiment_confidence = ?,
                                   sentiment_reasoning = ?,
                                   sentiment_analyzed_at = ?
                               WHERE message_id = ?""",
                            (
                                sentiment,
                                confidence,
                                reasoning,
                                datetime.now().isoformat(),
                                message_id,
                            ),
                        )

                        # Insert per-ticker sentiment
                        for ticker_data in tickers:
                            try:
                                db.execute(
                                    """INSERT OR REPLACE INTO message_ticker_sentiment
                                       (message_id, ticker, sentiment, confidence)
                                       VALUES (?, ?, ?, ?)""",
                                    (
                                        message_id,
                                        ticker_data["symbol"],
                                        ticker_data["sentiment"],
                                        ticker_data["confidence"],
                                    ),
                                )
                            except Exception as e:
                                logger.warning(f"Failed to store per-ticker sentiment: {e}")

                except Exception as e:
                    errors += 1
                    logger.error(f"Error analyzing message {message_id}: {e}")
                    continue

        # Run async processing
        asyncio.run(process_messages())

        # Show results
        click.echo()
        click.echo("=" * 80)
        click.secho("RESULTS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Processed:       {processed:,}/{total:,}")
        click.echo(f"Errors:          {errors:,}")
        click.echo()

        if processed > 0:
            click.secho("SENTIMENT BREAKDOWN:", bold=True)
            table_data = []
            for sentiment, count in sorted(
                sentiment_counts.items(), key=lambda x: x[1], reverse=True
            ):
                pct = (count / processed) * 100 if processed > 0 else 0
                color = {"bullish": "green", "bearish": "red", "neutral": "yellow"}.get(
                    sentiment, "white"
                )
                table_data.append([sentiment.upper(), f"{count:,}", f"{pct:.1f}%"])
            click.echo(
                tabulate(table_data, headers=["Sentiment", "Count", "Percentage"], tablefmt="psql")
            )
            click.echo("=" * 80)

        if not update_db:
            click.echo()
            click.secho("💡 Tip: Add --update-db to store sentiment in database", fg="cyan")

        click.echo()

    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
        click.secho(f"\n✗ Error analyzing sentiment: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("recompute-tickers")
@click.option(
    "--days", type=int, default=30, help="Recompute tickers for messages from last N days"
)
@click.option("--channel", help="Filter by channel name")
@click.option("--limit", type=int, help="Limit number of messages to process")
@click.pass_context
def recompute_tickers(ctx, days, channel, limit):
    """
    Recompute tickers for messages by extracting from ALL message data.

    This is useful for cleaning up hallucinated tickers from old sentiment analysis.
    Tickers are extracted from:
    - Message content (text)
    - extracted_data.trades array
    - extracted_data.tickers array
    - extracted_data.raw_text (OCR)

    Does NOT extract from sentiment_reasoning (LLM hallucinations).
    """
    db = ctx.obj["db"]

    try:
        messages_obj = Messages(db)

        click.echo()
        click.echo("=" * 80)
        click.secho("RECOMPUTE TICKERS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Time range:   Last {days} days")
        if channel:
            click.echo(f"Channel:      {channel}")
        if limit:
            click.echo(f"Limit:        {limit} messages")
        click.echo()

        # Use Messages class method instead of raw SQL
        # Get recent messages using the proper API
        all_messages = messages_obj.get_recent(
            channel_name=channel,
            limit=limit or 10000,  # Default to large number if not specified
            include_deleted=False,
        )

        # Filter by date range
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        messages_to_process = [
            msg
            for msg in all_messages
            if datetime.fromisoformat(msg.timestamp.replace("+00:00", "")) >= cutoff_date
        ]

        total = len(messages_to_process)

        if total == 0:
            click.secho("✓ No messages to process", fg="green")
            click.echo()
            return

        click.echo(f"Found {total:,} messages to process")
        click.echo()

        # Process messages
        processed = 0
        updated = 0
        errors = 0

        click.echo("Processing...")
        click.echo()

        for i, msg in enumerate(messages_to_process, 1):
            try:
                # Use Messages.update_tickers() method (follows architecture)
                result = messages_obj.update_tickers(msg.message_id)

                if result:
                    updated += 1

                processed += 1

                # Show progress every 100 messages
                if processed % 100 == 0 or processed == total:
                    pct = (processed / total) * 100
                    click.echo(
                        f"Progress: {processed:,}/{total:,} ({pct:.1f}%) - Updated: {updated:,}, Errors: {errors:,}"
                    )

            except Exception as e:
                errors += 1
                logger.error(f"Error recomputing tickers for message {msg.message_id}: {e}")

        # Show results
        click.echo()
        click.echo("=" * 80)
        click.secho("RESULTS", bold=True)
        click.echo("=" * 80)
        click.echo(f"Processed:    {processed:,}/{total:,}")
        click.echo(f"Updated:      {updated:,}")
        click.echo(f"Errors:       {errors:,}")
        click.echo("=" * 80)
        click.echo()

        if updated > 0:
            click.secho(f"✓ Successfully recomputed tickers for {updated:,} messages", fg="green")
        else:
            click.secho("⚠ No messages were updated", fg="yellow")

        click.echo()

    except Exception as e:
        logger.error(f"Error recomputing tickers: {e}", exc_info=True)
        click.secho(f"\n✗ Error recomputing tickers: {e}\n", fg="red", err=True)
        ctx.exit(1)


@messages.command("extracted-trades")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for data isolation)")
@click.option("--channel", required=True, help="Channel name (e.g., 💸darkminer-moves)")
@click.option("--username", help="Filter by username")
@click.option("--days", type=int, default=7, help="Look back N days (default: 7)")
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Limit number of trades to display (default: show all within date range)",
)
@click.option("--show-warnings", is_flag=True, help="Show validation warnings")
@click.option("--verbose", is_flag=True, help="Show username and message date")
@click.pass_context
def extracted_trades(ctx, guild_id, channel, username, days, limit, show_warnings, verbose):
    """
    List trades extracted from a specific channel

    Shows trades parsed from messages and images in channels like darkminer-moves.
    Useful for reviewing trade extraction accuracy and completeness.

    Examples:
        # List recent trades from darkminer-moves
        python src/cli.py messages extracted-trades --guild-id 1405962109262757980 --channel 💸darkminer-moves

        # Show last 30 days with validation warnings
        python src/cli.py messages extracted-trades --guild-id 1405962109262757980 --channel 💸darkminer-moves --days 30 --show-warnings

        # Show with username and date
        python src/cli.py messages extracted-trades --guild-id 1405962109262757980 --channel 💸darkminer-moves --verbose

        # Filter by specific user
        python src/cli.py messages extracted-trades --guild-id 1405962109262757980 --channel 💸darkminer-moves --username darkminer
    """
    db = ctx.obj["db"]

    try:
        # Query messages with extracted trades (filtered by guild_id for data isolation)
        # Note: We query ALL messages in the date range (no LIMIT) because we need to
        # iterate through all trades to reach the user's requested limit
        query = """
        SELECT
            message_id,
            datetime(timestamp) as timestamp,
            username,
            json_extract(extracted_data, '$.trades') as trades_json,
            substr(content, 1, 100) as content_preview
        FROM harvested_messages
        WHERE guild_id = ?
          AND channel_name = ?
          AND timestamp >= datetime('now', '-' || ? || ' days')
          AND json_extract(extracted_data, '$.trades') IS NOT NULL
          AND json_type(json_extract(extracted_data, '$.trades')) = 'array'
        """

        params = [guild_id, channel, days]

        # Add username filter if provided
        if username:
            query += " AND username = ?"
            params.append(username)

        query += " ORDER BY timestamp DESC"

        results = db.query_parameterized(query, tuple(params))

        if not results:
            user_filter = f" for user '@{username}'" if username else ""
            click.secho(
                f"\nNo trades found in channel '{channel}'{user_filter} for guild {guild_id} (last {days} days)\n",
                fg="yellow",
            )
            return

        # Parse trades and build display
        trades_list = []
        total_trades = 0

        for row in results:
            message_id, timestamp, username, trades_json, content_preview = row

            # Parse JSON trades array
            try:
                trades = json.loads(trades_json) if trades_json else []
            except json.JSONDecodeError:
                trades = []

            # Skip if no trades
            if not trades:
                continue

            for trade in trades:
                total_trades += 1
                if limit is not None and total_trades > limit:
                    break

                # Extract trade details
                operation = trade.get("operation", "N/A")
                ticker = trade.get("ticker", "N/A")
                strike = trade.get("strike", "N/A")
                option_type = trade.get("option_type", "N/A")
                expiration = trade.get("expiration", "N/A")
                quantity = trade.get("quantity", "N/A")
                premium = trade.get("premium", "N/A")
                source = trade.get("source", "text")
                warnings = trade.get("validation_warnings", [])

                # Format expiration (MM/DD)
                exp_str = "N/A"
                if expiration != "N/A":
                    try:
                        if " " in str(expiration):
                            expiration = expiration.split(" ")[0]
                        # Parse YYYY-MM-DD and convert to MM/DD
                        parts = expiration.split("-")
                        if len(parts) == 3:
                            exp_str = f"{parts[1]}/{parts[2]}"
                    except:
                        exp_str = str(expiration)

                # Format option type (C/P)
                opt_type_short = option_type[0] if (option_type and option_type != "N/A") else "N/A"

                # Build compact trade string: "OP QTYx TICKER $STRIKE C/P @ $PREMIUM (MM/DD)"
                trade_str = f"{operation} {quantity}x {ticker} ${strike}{opt_type_short} @ ${premium} ({exp_str})"

                # Add warnings if requested
                if show_warnings and warnings:
                    trade_str += f" ⚠ {warnings[0][:60]}"

                trades_list.append((timestamp, username, source, trade_str))

            if limit is not None and total_trades >= limit:
                break

        if not trades_list:
            user_filter = f" for user '@{username}'" if username else ""
            click.secho(
                f"\nNo trades extracted in channel '{channel}'{user_filter} (last {days} days)\n",
                fg="yellow",
            )
            return

        # Display results in compact format
        click.echo()
        user_header = f" (@{username})" if username else ""
        click.secho(f"Extracted Trades from {channel}{user_header}:", bold=True)
        click.echo(f"{len(trades_list)} trades extracted (last {days} days):")

        for timestamp, username, source, trade_str in trades_list:
            # Format verbose prefix (date and username)
            verbose_prefix = ""
            if verbose:
                # Parse timestamp and format as MM/DD/YYYY
                from datetime import datetime

                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    date_str = dt.strftime("%m/%d/%Y")
                    verbose_prefix = f"[{date_str} @{username}] "
                except:
                    verbose_prefix = f"[@{username}] "

            source_badge = f"[{source}]" if show_warnings else ""
            click.echo(f"  - {verbose_prefix}{trade_str} {source_badge}")

        if limit is not None and total_trades >= limit:
            click.echo()
            click.secho(f"💡 Showing first {limit} trades. Use --limit to show more", fg="cyan")

        click.echo()

    except Exception as e:
        logger.error(f"Error listing extracted trades: {e}", exc_info=True)
        click.secho(f"\n✗ Error listing extracted trades: {e}\n", fg="red", err=True)
        ctx.exit(1)
