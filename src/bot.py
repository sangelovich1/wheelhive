#!/usr/bin/env python3
"""
Options Trading Bot - Discord Bot

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol, Self

# Third-party imports
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Local application imports
import constants as const
import util
from bot_downloads import BotDownloads
from bot_upload_identifier import BotUploadIdentifier, BrokerageType
from bot_uploads import BotUploads
from daily_digest import DailyDigest
from db import Db
from deposits import Deposits
from df_stats import DFStats
from dividends import Dividends
from extrinsicvalue import ExtrinsicValue
from guild_channels import GuildChannels
from llm_analyzer import LLMAnalyzer
from market_sentiment import MarketSentiment
from message import Message
from messages import Messages
from messages_async import MessagesAsync
from metrics import MetricsTracker
from news_feed import NewsFeedAggregator
from pop_calculator import POPCalculator
from positions import Positions
from positions_renderer import PositionsRenderer
from providers.market_data_factory import MarketDataFactory
from rag_analytics import RAGAnalytics
from reports.optionspivotreport import OptionsPivotReport
from reports.profittreport import ProfitReport
from reports.symbol_report import SymbolReport
from scanner import Scanner
from scanner_renderer import ScannerRenderer
from shares import Shares
from system_settings import get_settings
from trade import Trade
from trademodal import TradeModal
from trades import Trades
from ttracker import TTracker
from watchlists import Watchlists


# Initialize root logger for the application
util.setup_logger(name=None, level="INFO", console=True)
logger = logging.getLogger(__name__)


def _harvest_message_in_thread(
    messages_instance: Messages, discord_message: discord.Message, channel_category: str
) -> Message:
    """
    Process Discord message for harvesting in a worker thread.

    This function performs CPU-intensive OCR operations without blocking the event loop.
    Does NOT touch the database - that's done in the main async thread for SQLite safety.

    Args:
        messages_instance: Messages collection instance (for accessing OCR methods)
        discord_message: Discord message object to process
        channel_category: Channel category ('sentiment' or 'news')

    Returns:
        Message object (ready for database insertion)
    """
    # Create Message object from Discord message
    # Image OCR is now handled by ImageProcessingQueue (async queue-based)
    msg = Message.from_discord_message(discord_message, category=channel_category)
    return msg


def log_command(interaction: discord.Interaction, command_name: str, **params) -> int:
    """
    Standardized logging for Discord commands.

    Logs to both file (bot.log) and metrics database.

    Args:
        interaction: Discord interaction object
        command_name: Name of the command being executed
        **params: Optional parameters to log

    Returns:
        Event ID from metrics database (for linking LLM/MCP calls)
    """
    user = interaction.user.name
    guild_name = interaction.guild.name if interaction.guild else "DM"
    guild_id = interaction.guild.id if interaction.guild else None

    param_str = ""
    if params:
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        param_str = f" | params: {param_str}"

    # Log to file (existing behavior)
    logger.info("*****************************************************************")
    logger.info(f"[{guild_name} ({guild_id})] {user} -> /{command_name}{param_str}")

    # Track in metrics database
    try:
        # Get metrics tracker from bot instance (stored in interaction.client)
        if hasattr(interaction.client, "metrics"):
            event_id: int = int(
                interaction.client.metrics.track_command(
                    command_name=command_name,
                    username=user,
                    guild_id=guild_id,
                    guild_name=guild_name,
                    parameters=params,
                )
            )
            return event_id
    except Exception as e:
        logger.warning(f"Failed to track command in metrics: {e}")

    return 0  # Return 0 if tracking failed (won't break commands)


class MessageLike(Protocol):
    """Protocol for message-like objects that can be processed by tutor handler."""

    content: str
    author: Any
    channel: Any
    guild: Any

    async def add_reaction(self, emoji: str) -> None: ...
    async def remove_reaction(self, emoji: str, user: Any) -> None: ...


class Client(commands.Bot):
    # db: Optional[Db] = None
    # trades: Optional[Trades] = None
    # stats: Optional[Stats] = None
    # df_stats: Optional[DFStats] = None
    # dividends: Optional[Dividends] = None
    # shares: Optional[Shares] = None
    # deposits: Optional[Deposits] = None
    # watchlists: Optional[Watchlists] = None
    # start_time: Optional[datetime] = None

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.db = Db()
        self.trades = Trades(self.db)
        self.df_stats = DFStats(self.db)
        self.dividends = Dividends(self.db)
        self.shares = Shares(self.db)
        self.deposits = Deposits(self.db)
        self.watchlists = Watchlists(self.db)
        self.positions = Positions(self.db, self.shares, self.trades)
        self.messages = Messages(self.db)
        self.metrics = MetricsTracker(self.db)
        self.guild_channels = GuildChannels(self.db)
        self.news_feed = NewsFeedAggregator(self.db)
        self.start_time: datetime = datetime.now()

        # Load system settings from database
        settings = get_settings(self.db)
        self.sentiment_model = settings.get(const.SETTING_SENTIMENT_MODEL)
        self.vision_ocr_model = settings.get(const.SETTING_VISION_OCR_MODEL)
        self.image_analysis_enabled = settings.get(const.SETTING_IMAGE_ANALYSIS_ENABLED)
        self.sentiment_analysis_enabled = settings.get(const.SETTING_SENTIMENT_ANALYSIS_ENABLED)

        # Queue configuration settings
        self.sentiment_worker_count = settings.get(const.SETTING_SENTIMENT_WORKER_COUNT)
        self.sentiment_queue_size = settings.get(const.SETTING_SENTIMENT_QUEUE_SIZE)
        self.vision_worker_count = settings.get(const.SETTING_VISION_WORKER_COUNT)
        self.vision_queue_size = settings.get(const.SETTING_VISION_QUEUE_SIZE)

        # Initialize market data factory with database
        MarketDataFactory.set_db(self.db)

        # Thread pool for CPU-intensive operations (OCR, image processing)
        # Keep pool small to avoid overwhelming CPU during high message volume
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr-worker")

        # Async wrapper for messages (prevents blocking event loop during DB operations)
        self.messages_async = MessagesAsync(self.messages, self.executor)

        # Sentiment processing queue (async sentiment analysis)
        # Must initialize FIRST so image_queue callback can reference it
        from queues.sentiment_processing_queue import SentimentProcessingQueue

        self.sentiment_queue = SentimentProcessingQueue(
            db=self.db,
            model=self.sentiment_model,
            worker_count=self.sentiment_worker_count,
            queue_size=self.sentiment_queue_size,
        )

        # Image processing queue (async vision analysis)
        # Supports Claude Sonnet, GPT-4V, Ollama/LLaVA
        # Callback triggers sentiment analysis after vision OCR completes
        from queues.image_processing_queue import ImageProcessingQueue

        self.image_queue = ImageProcessingQueue(
            db=self.db,
            model=self.vision_ocr_model,
            worker_count=self.vision_worker_count,
            queue_size=self.vision_queue_size,
            on_complete_callback=self._enqueue_sentiment_after_vision,
        )

    @tasks.loop(hours=24)
    async def daily_digest_task(self):
        """Generate daily digests for all guilds at 5pm MST every day (2 hours after market close at 2pm MST/4pm ET).

        Always generates 7-day rolling window digests for better signal-to-noise ratio.
        """
        logger.info("Running daily digest task for all guilds...")

        try:
            today = datetime.now()
            logger.info(f"Generating 7-day rolling digests for {len(const.GUILDS)} guilds")

            results = []

            for guild_id in const.GUILDS:
                try:
                    logger.info(f"Processing guild {guild_id}...")

                    # Initialize digest generator for this guild
                    digest_gen = DailyDigest(
                        db=self.db,
                        guild_id=guild_id,
                        enable_llm=True,  # Enable LLM narrative
                    )

                    # Generate digest (run in thread to avoid blocking event loop)
                    digest_text = await asyncio.to_thread(digest_gen.generate_digest, today)

                    # Save digest as MD (run in thread)
                    md_path = await asyncio.to_thread(digest_gen.save_digest, digest_text, today)

                    results.append({"guild_id": guild_id, "status": "success", "md_path": md_path})

                    logger.info(f"✓ Guild {guild_id} digest saved: {md_path}")

                except Exception as e:
                    logger.error(f"✗ Error processing guild {guild_id}: {e}", exc_info=True)
                    results.append({"guild_id": guild_id, "status": "error", "error": str(e)})

            # Summary
            successful = [r for r in results if r["status"] == "success"]
            failed = [r for r in results if r["status"] == "error"]

            logger.info(
                f"Daily digest task complete: {len(successful)} successful, {len(failed)} failed"
            )

            if successful:
                logger.info(f"Digests saved in: {const.DAILY_DIGEST_DIR}/")

        except Exception as e:
            logger.error(f"Error in daily digest task: {e}", exc_info=True)

    @daily_digest_task.before_loop
    async def before_daily_digest(self):
        """Wait until bot is ready and schedule for 5pm MST (2 hours after market close at 2pm MST/4pm ET)."""
        await self.wait_until_ready()

        # Calculate next 5pm MST (2 hours after market close at 2pm MST/4pm ET)
        # Bot runs in MST timezone
        now = datetime.now()
        next_run = now.replace(hour=17, minute=0, second=0, microsecond=0)

        # If it's already past 5pm today, schedule for tomorrow
        if now.hour >= 17:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info(
            f"Daily digest scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')} MST (in {wait_seconds/3600:.1f} hours)"
        )

        # Wait until 5pm MST
        await asyncio.sleep(wait_seconds)

    async def _enqueue_sentiment_after_vision(self, message_id: int) -> None:
        """
        Callback triggered by vision queue after successful OCR completion.
        Enqueues message for sentiment analysis (now with extracted_data available).

        Args:
            message_id: Discord message ID that completed vision OCR
        """
        if self.sentiment_analysis_enabled:
            await self.sentiment_queue.enqueue_message(message_id)
            logger.debug(f"Enqueued message {message_id} for sentiment analysis (post-vision)")

    @tasks.loop(minutes=5)
    async def news_feed_task(self):
        """Fetch and post news articles to configured guild channels."""
        logger.info("Running news feed update task...")

        try:
            # Get update frequency from system settings
            settings = get_settings(self.db)
            update_frequency = settings.get("news.update_frequency_minutes", default=30)

            # Update loop interval if setting changed
            if self.news_feed_task.minutes != update_frequency:
                logger.info(f"News feed frequency changed to {update_frequency} minutes")
                self.news_feed_task.change_interval(minutes=update_frequency)

            # Update all guilds
            results = await self.news_feed.update_all_guilds(self)

            # Log results
            total_articles = sum(results.values())
            active_guilds = len([g for g, count in results.items() if count > 0])

            logger.info(
                f"News feed update complete: {total_articles} articles posted across {active_guilds} guilds"
            )

        except Exception as e:
            logger.error(f"Error in news feed task: {e}", exc_info=True)

    @news_feed_task.before_loop
    async def before_news_feed(self):
        """Wait until bot is ready before starting news feed task."""
        await self.wait_until_ready()
        logger.info("News feed task ready to start")

    async def on_ready(self) -> None:
        logger.info(f"Initializing bot: {self.user}")
        try:
            # Sync to all guilds (includes both DEV and production guilds)
            all_guilds = set(const.GUILD_IDS + const.DEV_GUILD_IDS)
            for guild in all_guilds:
                synced = await self.tree.sync(guild=guild)
                logger.info(f"Synced {len(synced)} commands to guild.id {guild.id}")

            # Start daily digest task
            if not self.daily_digest_task.is_running():
                self.daily_digest_task.start()
                logger.info("Daily digest task started")

            # Start news feed task
            if not self.news_feed_task.is_running():
                self.news_feed_task.start()
                settings = get_settings(self.db)
                update_frequency = settings.get("news.update_frequency_minutes", default=30)
                logger.info(f"News feed task started (update every {update_frequency} minutes)")

            # Start sentiment processing workers
            if self.sentiment_analysis_enabled:
                await self.sentiment_queue.start_workers()
                logger.info(
                    f"Sentiment analysis enabled: {self.sentiment_worker_count} workers started"
                )
            else:
                logger.info(
                    "Sentiment analysis disabled (system_settings.sentiment_analysis_enabled=False)"
                )

            # Start image processing workers
            if self.image_analysis_enabled:
                await self.image_queue.start_workers()
                logger.info(f"Image processing enabled: {self.vision_worker_count} workers started")
            else:
                logger.info(
                    "Image processing disabled (system_settings.image_analysis_enabled=False)"
                )

        except Exception as e:
            logger.error(f"Error syncing commands: {e}", exc_info=True)

    async def close(self) -> None:
        """Clean shutdown of bot resources"""
        logger.info("Shutting down bot...")

        # Stop daily digest task
        if hasattr(self, "daily_digest_task") and self.daily_digest_task.is_running():
            logger.info("Stopping daily digest task...")
            self.daily_digest_task.cancel()
            logger.info("Daily digest task stopped")

        # Stop news feed task
        if hasattr(self, "news_feed_task") and self.news_feed_task.is_running():
            logger.info("Stopping news feed task...")
            self.news_feed_task.cancel()
            logger.info("News feed task stopped")

        # Stop sentiment processing workers
        if hasattr(self, "sentiment_queue") and self.sentiment_analysis_enabled:
            logger.info("Stopping sentiment processing workers...")
            await self.sentiment_queue.stop_workers()
            stats = self.sentiment_queue.get_stats()
            logger.info(
                f"Sentiment processing workers stopped (processed={stats['processed']}, failed={stats['failed']})"
            )

        # Stop image processing workers
        if hasattr(self, "image_queue") and self.image_analysis_enabled:
            logger.info("Stopping image processing workers...")
            await self.image_queue.stop_workers()
            self.image_queue.log_stats()
            logger.info("Image processing workers stopped")

        # Shutdown thread pool executor gracefully
        if hasattr(self, "executor"):
            logger.info("Shutting down OCR thread pool...")
            self.executor.shutdown(wait=True, cancel_futures=False)
            logger.info("OCR thread pool shutdown complete")

        # Call parent close
        await super().close()

    async def _handle_tutor_thread_message(self, message: MessageLike) -> None:
        """
        Handle messages in AI Tutor threads - provides interactive Q&A with RAG.

        Args:
            message: The Discord message in the tutor thread
        """
        try:
            # Acknowledge we're processing
            await message.add_reaction("🤔")

            # Get the question
            question = message.content.strip()
            user = message.author.name
            guild_id = message.guild.id if message.guild else None

            logger.info(f"AI Tutor question from {user} in thread: '{question[:100]}...'")

            # Send immediate status message so user knows we're working
            # (unless /tutor command already sent one - check for _status_message attribute)
            status_msg = getattr(message, "_status_message", None)
            if not status_msg:
                status_msg = await message.channel.send(
                    "🤔 Analyzing your question with RAG-enhanced AI...\n"
                    "_This may take 30-60 seconds for complex queries with tool calls._"
                )

            # Initialize the tutor with username for personalized responses
            from rag import WheelStrategyTutor

            settings = get_settings(self.db)
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

            tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id, username=user)

            # Determine if this is a question or topic to explain
            question_indicators = [
                "how",
                "what",
                "when",
                "where",
                "why",
                "which",
                "should",
                "can",
                "is",
                "are",
                "do",
                "does",
            ]
            is_question_type = "?" in question or any(
                question.lower().startswith(word) for word in question_indicators
            )

            # Run RAG query in thread to avoid blocking
            if is_question_type:
                result = await asyncio.to_thread(
                    tutor_instance.ask, question=question, n_results=3, temperature=0.7
                )
            else:
                result = await asyncio.to_thread(
                    tutor_instance.explain_topic, topic=question, n_results=5, temperature=0.7
                )

            # Remove thinking reaction, add checkmark
            if self.user:
                await message.remove_reaction("🤔", self.user)
            await message.add_reaction("✅")

            # Delete status message now that we have the answer (if one was created)
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete status message: {e}")

            # Format and send response
            answer_text = result["answer"]
            sources = result.get("sources", [])

            # Send answer (handle long responses)
            first_message = None  # Track first message for rating reactions
            if len(answer_text) <= 2000:
                first_message = await message.channel.send(answer_text)
            else:
                # Split into chunks
                chunks = []
                current_chunk = ""
                for line in answer_text.split("\n"):
                    if len(current_chunk) + len(line) + 1 > 2000:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        if current_chunk:
                            current_chunk += "\n"
                        current_chunk += line
                if current_chunk:
                    chunks.append(current_chunk)

                for i, chunk in enumerate(chunks):
                    if i == 0:
                        first_message = await message.channel.send(chunk)
                    else:
                        await message.channel.send(f"**...continued**\n{chunk}")

            # Send sources as a separate embed
            if sources:
                sources_text = "\n".join([f"• {source}" for source in sources[:10]])
                sources_embed = discord.Embed(
                    title="📖 Training Materials Used",
                    description=sources_text,
                    color=discord.Color.blue(),
                )
                await message.channel.send(embed=sources_embed)

            # Add disclaimer
            disclaimer = discord.Embed(
                description="⚠️ **Disclaimer:** This is AI-generated educational content based on training materials. "
                "Not financial advice. Always verify information and consult qualified professionals before making trading decisions.",
                color=discord.Color.orange(),
            )
            await message.channel.send(embed=disclaimer)

            # Add rating reactions to the first answer message
            if first_message:
                try:
                    await first_message.add_reaction("👍")
                    await first_message.add_reaction("👎")
                except Exception as e:
                    logger.warning(f"Failed to add rating reactions: {e}")

            # Log analytics
            try:
                from rag_analytics import RAGAnalytics

                analytics = RAGAnalytics()
                query_type = "ask" if is_question_type else "explain_topic"
                chunks = result.get("chunks", [])
                await asyncio.to_thread(
                    analytics.log_query,
                    username=user,
                    query_type=query_type,
                    query_text=question,
                    sources=chunks,
                    guild_id=guild_id,
                    n_results=len(chunks),
                    model=model,
                )
            except Exception as e:
                logger.warning(f"Failed to log RAG analytics: {e}")

            logger.info(f"AI Tutor responded to {user} using {len(sources)} sources")

        except FileNotFoundError as e:
            logger.error(f"Vector store not found: {e}", exc_info=True)
            if self.user:
                await message.remove_reaction("🤔", self.user)
            await message.add_reaction("❌")
            await message.channel.send(
                "❌ **AI Tutor Not Initialized**\n\n"
                "The training materials haven't been set up yet. "
                "Contact an administrator to run:\n"
                "```bash\n"
                "python scripts/rag/create_vector_store.py\n"
                "```"
            )
        except Exception as e:
            logger.error(f"Error in AI Tutor thread: {e}", exc_info=True)
            if self.user:
                await message.remove_reaction("🤔", self.user)
            await message.add_reaction("❌")
            await message.channel.send(
                f"❌ Sorry, I encountered an error processing your question: {e!s}\n\n"
                f"Please try rephrasing or ask something else."
            )

    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming DM messages with ! commands and harvest guild messages.

        Args:
            message: The Discord message object
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Handle replies in special threads
        if isinstance(message.channel, discord.Thread):
            # AI Tutor threads - interactive Q&A
            if message.channel.name.startswith("🎓 AI Tutor"):
                await self._handle_tutor_thread_message(message)
                return  # Don't harvest tutor thread messages

            # Catch-up threads
            if message.channel.name.startswith("📊") and "Catch-up" in message.channel.name:
                await message.add_reaction("👀")
                logger.debug(f"Acknowledged message in catch-up thread from {message.author.name}")
                return  # Don't harvest catch-up thread messages

        # Harvest messages from configured channels
        # Check if this channel is configured for message harvesting in database
        if message.guild is not None:
            channel_category = self.guild_channels.get_channel_category(message.channel.id)
            if channel_category is not None:
                try:
                    # Determine if this is a news channel
                    is_news_channel = channel_category == "news"

                    # Skip bot messages UNLESS it's a news channel (news often comes from bots)
                    if message.author.bot and not is_news_channel:
                        return
                    if message.content.startswith("/"):
                        return

                    # Process message in worker thread (CPU-intensive OCR work)
                    # This prevents blocking the event loop during image processing
                    loop = asyncio.get_event_loop()
                    msg = await loop.run_in_executor(
                        self.executor,
                        _harvest_message_in_thread,
                        self.messages,
                        message,
                        channel_category,
                    )

                    # Insert message (async to prevent blocking event loop)
                    # Don't extract tickers from news channels (too many false positives from article text)
                    success = await self.messages_async.insert(
                        msg, extract_tickers=not is_news_channel
                    )

                    if success:
                        logger.debug(
                            f"Harvested message from #{msg.channel_name} by {msg.username}"
                        )

                        has_images = bool(msg.attachment_urls)
                        has_text = bool(msg.content and len(msg.content.strip()) >= 10)

                        # Enqueue for trade parsing (text + vision) if enabled (non-blocking)
                        if self.image_analysis_enabled and (has_images or has_text):
                            enqueued = await self.image_queue.enqueue_message(
                                msg.message_id, msg.attachment_urls or [], msg.content, msg.guild_id
                            )
                            if not enqueued:
                                logger.warning(
                                    f"Failed to enqueue message {msg.message_id} for trade parsing (queue full)"
                                )
                            # Note: Sentiment will be triggered by vision callback after parsing completes

                        # Enqueue for sentiment analysis (event-driven coordination)
                        if self.sentiment_analysis_enabled:
                            if not (has_images or has_text):
                                # No images or text - process sentiment immediately
                                enqueued = await self.sentiment_queue.enqueue_message(
                                    msg.message_id
                                )
                                if not enqueued:
                                    logger.warning(
                                        f"Failed to enqueue message {msg.message_id} for sentiment (queue full)"
                                    )
                            # else: Sentiment will be triggered by vision/trade parsing completion callback
                    else:
                        logger.debug(f"Message {msg.message_id} already exists in database")

                except Exception as e:
                    logger.error(f"Error harvesting message {message.id}: {e}", exc_info=True)

        # Only process DMs (no guild)
        if message.guild is None:
            user = message.author.name
            content = message.content.strip()

            logger.info(f"DM received from {user}: {content}")

            # Handle !hello command
            if content.lower() == "!hello":
                await message.channel.send(f"Hello {user}! 👋 How can I help you today?")

            # Handle !help command
            elif content.lower() == "!help":
                help_text = """**Available DM Commands:**

**Analysis Commands (powered by AI):**
• `!analyze` - Comprehensive portfolio review with live market data
• `!opportunities` - Find trading opportunities based on your positions
• `!ask <question>` - Ask any question about your portfolio
• `!sentiment <ticker>` - Analyze community perspective on a ticker

**Community Knowledge:**
• `!user_activity <username>` - View statistics for a community member's messages

**Info:**
• `!hello` - Test the bot
• `!help` - Show this help message

**Note:** AI analysis requires ANTHROPIC_API_KEY in .env. Portfolio commands also need MCP server on port 8000."""
                await message.channel.send(help_text)

            # Handle !analyze command
            elif content.lower() == "!analyze":
                await message.channel.send("🤖 Analyzing your portfolio... This may take a minute.")
                try:
                    analyzer = LLMAnalyzer(db=self.db, metrics_tracker=self.metrics)
                    result = await asyncio.to_thread(analyzer.analyze_portfolio, user)
                    await self._send_long_message(message.channel, result)
                except Exception as e:
                    logger.error(f"Error in !analyze: {e}", exc_info=True)
                    await message.channel.send(
                        f"Error: {e!s}\nEnsure MCP servers are running and ANTHROPIC_API_KEY is set."
                    )

            # Handle !opportunities command
            elif content.lower() == "!opportunities":
                await message.channel.send(
                    "🔍 Finding trading opportunities... This may take a minute."
                )
                try:
                    analyzer = LLMAnalyzer(db=self.db, metrics_tracker=self.metrics)
                    result = await asyncio.to_thread(analyzer.find_opportunities, user)
                    await self._send_long_message(message.channel, result)
                except Exception as e:
                    logger.error(f"Error in !opportunities: {e}", exc_info=True)
                    await message.channel.send(
                        f"Error: {e!s}\nEnsure MCP servers are running and ANTHROPIC_API_KEY is set."
                    )

            # Handle !ask command
            elif content.lower().startswith("!ask "):
                question = content[5:].strip()
                if not question:
                    await message.channel.send(
                        "Please provide a question. Example: `!ask What are my best performing symbols?`"
                    )
                else:
                    await message.channel.send(f"🤖 Analyzing: {question}")
                    try:
                        analyzer = LLMAnalyzer(db=self.db, metrics_tracker=self.metrics)
                        result = await asyncio.to_thread(analyzer.analyze, user, question)
                        await self._send_long_message(message.channel, result)
                    except Exception as e:
                        logger.error(f"Error in !ask: {e}", exc_info=True)
                        await message.channel.send(
                            f"Error: {e!s}\nEnsure MCP servers are running and ANTHROPIC_API_KEY is set."
                        )

            # Handle !sentiment command
            elif content.lower().startswith("!sentiment "):
                ticker = content[11:].strip().upper()
                if not ticker:
                    await message.channel.send(
                        "Please provide a ticker symbol. Example: `!sentiment MSTX`"
                    )
                else:
                    await message.channel.send(
                        f"🔍 Analyzing community sentiment for ${ticker}... This may take a minute."
                    )
                    try:
                        analyzer = LLMAnalyzer(db=self.db, metrics_tracker=self.metrics)
                        result = await asyncio.to_thread(
                            analyzer.analyze_community_sentiment, ticker, limit=50
                        )
                        await self._send_long_message(
                            message.channel, f"**Community Sentiment: ${ticker}**\n\n{result}"
                        )
                    except Exception as e:
                        logger.error(f"Error in !sentiment: {e}", exc_info=True)
                        await message.channel.send(
                            f"Error: {e!s}\nEnsure ANTHROPIC_API_KEY is set in .env"
                        )

            # Handle !user_activity command
            elif content.lower().startswith("!user_activity "):
                username = content[15:].strip()
                if not username:
                    await message.channel.send(
                        "Please provide a username. Example: `!user_activity darkminer`"
                    )
                else:
                    await message.channel.send(f"📊 Fetching statistics for @{username}...")
                    try:
                        from messages import Messages

                        messages = Messages(self.db)
                        stats = messages.get_user_stats(username, limit=10)

                        if stats["total_messages"] == 0:
                            await message.channel.send(f"No messages found from user: @{username}")
                        else:
                            # Build response
                            response = f"**Statistics for @{username}**\n\n"
                            response += f"**Messages:** {stats['total_messages']:,} total ({stats['active_messages']:,} active, {stats['deleted_messages']:,} deleted)\n\n"

                            # Channel breakdown
                            if stats["channels"]:
                                response += "**By Channel:**\n"
                                for channel, count in stats["channels"]:
                                    response += f"• #{channel}: {count:,} messages\n"
                                response += "\n"

                            # Top tickers
                            if stats["top_tickers"]:
                                response += "**Top Mentioned Tickers:**\n"
                                for ticker, count in stats["top_tickers"]:
                                    response += f"• ${ticker}: {count:,} messages\n"

                            await self._send_long_message(message.channel, response)

                    except Exception as e:
                        logger.error(f"Error in !user_activity: {e}", exc_info=True)
                        await message.channel.send(f"Error: {e!s}")

            else:
                # Acknowledge other messages
                await message.channel.send(
                    f"I received your message: {content}\n\nType `!help` to see available commands."
                )

    async def _send_long_message(self, channel, text: str) -> None:
        """
        Send a message that may exceed Discord's character limit by splitting into chunks.

        Intelligently splits at section, paragraph, sentence, or word boundaries to avoid
        breaking messages mid-sentence or mid-table.

        Args:
            channel: Discord channel to send to
            text: Text to send
        """
        chunks = util.smart_split_message(text, const.DISCORD_MAX_CHAR_COUNT)
        for chunk in chunks:
            await channel.send(chunk)

    async def _send_long_message_slash(
        self, interaction: discord.Interaction, text: str, ephemeral: bool = True
    ) -> None:
        """
        Send a slash command response that may exceed Discord's character limit.

        Uses followup messages for responses longer than Discord's limit.
        First message uses interaction.followup.send(), subsequent use regular followup.

        Args:
            interaction: Discord interaction (must be deferred)
            text: Text to send
            ephemeral: Whether messages should be private (default: True for financial data)
        """
        chunks = util.smart_split_message(text, const.DISCORD_MAX_CHAR_COUNT)

        # Send all chunks with same ephemeral setting
        for chunk in chunks:
            await interaction.followup.send(chunk, ephemeral=ephemeral)


def main() -> None:
    # Discord permissions
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    # intents.members = True

    client = Client(command_prefix="!", intents=intents)

    # TODO: Re-enable team_stats in the future if needed
    # @client.tree.command(name="team_stats", description="Team Stats", guilds=const.GUILD_IDS)
    # @app_commands.choices(team_report=[
    #     app_commands.Choice(name="Monthly Trade Summary", value="options_by_yearmonth"),
    # ])
    # async def team_stats(interaction: discord.Interaction, team_report: app_commands.Choice[str]):
    #     log_command(interaction, "team_stats", team_report=team_report.value)
    #
    #     # Capture guild_id to filter team stats by current guild
    #     guild_id = interaction.guild.id if interaction.guild else None
    #
    #     if team_report.value == 'options_by_yearmonth':
    #         # Load stats filtered by guild_id to show only current guild's data
    #         client.df_stats.load(username=None, guild_id=guild_id)
    #         results = client.df_stats.options_by_yearmonth()
    #         s1 = f"Team stats\n```{results}```"
    #     else:
    #         s1 = 'Report not available'
    #
    #     await interaction.response.send_message(s1, ephemeral = False)

    @client.tree.command(
        name="about", description="Information about WheelHive", guilds=const.GUILD_IDS
    )
    async def about(interaction: discord.Interaction):
        log_command(interaction, "about")

        # Calculate uptime
        uptime = datetime.now() - client.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = []
        if days > 0:
            uptime_str.append(f"{days}d")
        if hours > 0:
            uptime_str.append(f"{hours}h")
        if minutes > 0:
            uptime_str.append(f"{minutes}m")
        uptime_str.append(f"{seconds}s")

        s1 = "WheelHive - Where Wheel Traders Multiply Their Intelligence\n"
        s1 = s1 + f" Version: {const.VERSION}\n"
        s1 = s1 + " Website: https://wheelhive.ai\n"
        s1 = s1 + f" Author: {const.AUTHOR}\n"
        s1 = s1 + f" Contributors: {const.CONTRIBUTORS}\n"
        s1 = s1 + f" Uptime: {' '.join(uptime_str)}\n"
        await interaction.response.send_message(s1, ephemeral=True)

    @client.tree.command(
        name="extrinsic_value", description="Calculate Extrinsic Value", guilds=const.GUILD_IDS
    )
    async def extrinsic_value(interaction: discord.Interaction, ticker: str, strikes: str):
        log_command(interaction, "extrinsic_value", ticker=ticker, strikes=strikes)

        ev = ExtrinsicValue()
        status, result = ev.calculate(ticker, strikes)
        if status:
            await interaction.response.send_message(f"```{result}```", ephemeral=True)
        else:
            await interaction.response.send_message(f"Calculation failed {result}", ephemeral=True)

    @client.tree.command(
        name="market_sentiment",
        description="Get current market sentiment indicators (VIX, Fear & Greed, Crypto F&G)",
        guilds=const.GUILD_IDS,
    )
    async def market_sentiment_cmd(interaction: discord.Interaction):
        log_command(interaction, "market_sentiment")

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            sentiment = MarketSentiment()
            table_str = sentiment.as_table()
            output = f"**MARKET SENTIMENT INDICATORS**\n```\n{table_str}\n```"
            await interaction.followup.send(output, ephemeral=True)

        except Exception as e:
            logger.error(f"Error fetching market sentiment: {e}", exc_info=True)
            await interaction.followup.send(
                f"Error fetching market sentiment: {e!s}", ephemeral=True
            )

    @client.tree.command(
        name="probability_of_profit",
        description="Calculate Probability of Profit (POP) for an option",
        guilds=const.GUILD_IDS,
    )
    @app_commands.choices(
        option_type=[
            app_commands.Choice(name="Put", value="PUT"),
            app_commands.Choice(name="Call", value="CALL"),
        ]
    )
    async def probability_of_profit(
        interaction: discord.Interaction,
        ticker: str,
        strike: float,
        expiration: str,
        option_type: app_commands.Choice[str],
        premium: float | None = None,
        iv: float | None = None,
    ):
        log_command(
            interaction,
            "probability_of_profit",
            ticker=ticker,
            strike=strike,
            expiration=expiration,
            option_type=option_type.value,
            premium=premium,
            iv=iv,
        )

        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            calc = POPCalculator()

            # Format expiration date
            exp_date = Trade.format_date(expiration)

            result = calc.calculate_pop(
                ticker=ticker,
                strike=strike,
                expiration_date=exp_date,
                option_type=option_type.value,
                premium=premium,
                iv=iv,
            )

            formatted_output = calc.format_pop_result(result)
            await interaction.followup.send(formatted_output, ephemeral=True)

        except Exception as e:
            logger.error(f"Error calculating POP: {e}", exc_info=True)
            await interaction.followup.send(
                f"Error calculating probability of profit: {e!s}", ephemeral=True
            )

    @client.tree.command(
        name="schedule_potus", description="Schedule for POTUS.", guilds=const.GUILD_IDS
    )
    async def schedule_potus(interaction: discord.Interaction, sdate: str | None = None):
        if sdate == None:
            sdate = datetime.now().strftime("%Y-%m-%d")
        else:
            sdate = Trade.format_date(sdate)

        log_command(interaction, "schedule_potus", sdate=sdate)

        tt = TTracker()
        status, fpath = tt.image(sdate, cacheOnly=True)

        if status:
            await interaction.response.send_message(file=discord.File(fpath), ephemeral=False)
        else:
            await interaction.response.send_message(
                f"Schedule not found in cache for {sdate}.", ephemeral=True
            )

    @client.tree.command(name="my_trades", description="Trade Summary.", guilds=const.GUILD_IDS)
    @app_commands.choices(
        table=[
            app_commands.Choice(name="Options", value="trades"),
            app_commands.Choice(name="Dividends", value="dividends"),
            app_commands.Choice(name="Shares", value="shares"),
            app_commands.Choice(name="Deposits", value="deposits"),
        ]
    )
    async def my_trades(
        interaction: discord.Interaction,
        account: str,
        table: app_commands.Choice[str],
        symbol: str | None = None,
        page: int = 1,
    ):
        log_command(
            interaction, "my_trades", account=account, table=table.value, symbol=symbol, page=page
        )

        user = interaction.user.name
        index = page - 1

        # Convert "ALL" (case-insensitive) to None for querying all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        table_value = table.value

        if table_value == "trades":
            h_str = "Options"
            fields = [
                "id",
                'STRFTIME("%m/%d", date)',
                "operation",
                "contracts",
                "symbol",
                'STRFTIME("%m/%d", expiration_date)',
                '("strike_price" || "" || "option_type") AS strike',
                "premium",
                "total",
            ]
            aliases = ["ID", "Date", "Op", "Con", "Sym", "Exp", "Strike", "Premium", "Total"]
            table_str, cnt = client.trades.my_records(
                user, index, fields=fields, aliases=aliases, symbol=symbol, account=account_filter
            )
        elif table_value == "shares":
            h_str = "Shares"
            fields = [
                "ID",
                'STRFTIME("%m/%d/%Y", date)',
                "Action",
                "Symbol",
                "Price",
                "Quantity",
                "Amount",
            ]
            aliases = ["ID", "Date", "Action", "Symbol", "Price", "Quantity", "Amount"]
            table_str, cnt = client.shares.my_records(
                user, index, fields=fields, aliases=aliases, symbol=symbol, account=account_filter
            )
        elif table_value == "dividends":
            h_str = "Dividends"
            fields = ["ID", 'STRFTIME("%m/%d/%Y", date)', "Symbol", "Amount"]
            aliases = ["ID", "Date", "Symbol", "Amount"]
            table_str, cnt = client.dividends.my_records(
                user, index, fields=fields, aliases=aliases, symbol=symbol, account=account_filter
            )
        elif table_value == "deposits":
            h_str = "Deposits"
            fields = ["ID", "Action", 'STRFTIME("%m/%d/%Y", date)', "Amount"]
            aliases = ["ID", "Action", "Date", "Amount"]
            table_str, cnt = client.deposits.my_records(
                user, index, fields=fields, aliases=aliases, symbol=None, account=account_filter
            )
        else:
            await interaction.response.send_message(
                f"Source {table_value} not supported.", ephemeral=True
            )
            return

        # Add filter information to output
        filter_info = []
        if symbol:
            filter_info.append(f"Symbol: {symbol}")
        if account:
            filter_info.append(f"Account: {account}")
        filter_str = f" ({', '.join(filter_info)})" if filter_info else ""

        s1 = f"Page {page} of {cnt}.{filter_str}\n"
        await interaction.response.send_message(f"{h_str}```\n{table_str}```\n{s1}", ephemeral=True)

    @client.tree.command(name="my_trade_stats", description="Trade Stats.", guilds=const.GUILD_IDS)
    async def my_trade_stats(interaction: discord.Interaction, account: str):
        log_command(interaction, "my_trade_stats", account=account)

        user = interaction.user.name

        # Convert "ALL" (case-insensitive) to None for querying all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        client.df_stats.load(user, account=account_filter)
        table_str = client.df_stats.my_stats()

        # Add account filter info to header if specified
        account_str = f" (Account: {account})" if account_filter else " (All Accounts)"
        s1 = f"Trade Summary{account_str}\n"
        s1 = s1 + f"```{table_str}```\n"

        symbol_stats_str = client.df_stats.my_symbol_stats()

        month = util.month_start_end(datetime.now())
        start_date_str = month[0].strftime("%m/%d/%Y")
        end_date_str = month[1].strftime("%m/%d/%Y")
        s1 = s1 + f"Trade Stats for range: {start_date_str} - {end_date_str}{account_str}\n"
        s1 = s1 + f"```{symbol_stats_str}```\n"

        await interaction.response.send_message(f"{s1}", ephemeral=True)

    @client.tree.command(
        name="my_open_positions",
        description="View current stock and option positions.",
        guilds=const.GUILD_IDS,
    )
    async def my_open_positions(interaction: discord.Interaction, account: str):
        log_command(interaction, "my_open_positions", account=account)

        # Defer response immediately to avoid timeout (fetching live prices can be slow)
        await interaction.response.defer(thinking=True, ephemeral=True)

        user = interaction.user.name

        # Handle 'ALL' as None for aggregated view
        account_filter = None if account.upper() == "ALL" else account

        # Get positions data as DataFrames (filtered by account)
        stock_df, options_df = client.positions.as_df(user, account=account_filter, symbol=None)

        # Check if there are any positions
        if stock_df.empty and options_df.empty:
            account_str = f" for account '{account}'" if account_filter else ""
            await interaction.followup.send(
                f"No open positions found{account_str}.", ephemeral=True
            )
            return

        # Generate PNG image
        renderer = PositionsRenderer(output_dir=const.DOWNLOADS_DIR)
        image_path = renderer.render(
            stock_df, options_df, username=user, symbol_filter=None, account=account
        )

        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as file:
                file_attachment = discord.File(file, filename=f"{user}_positions.png")
                await interaction.followup.send(file=file_attachment, ephemeral=True)
        else:
            # Fallback to old text-based approach if image generation fails
            table_str, cnt = client.positions.my_positions(user, 0, account=account, symbol=None)
            await interaction.followup.send(f"```{table_str}```", ephemeral=True)

    @client.tree.command(
        name="my_accounts", description="List all accounts with trade data.", guilds=const.GUILD_IDS
    )
    async def my_accounts(interaction: discord.Interaction):
        log_command(interaction, "my_accounts")

        user = interaction.user.name

        # Get all accounts using shared utility function
        sorted_accounts = util.get_user_accounts(client.db, user)

        if not sorted_accounts:
            await interaction.response.send_message(
                "You have no accounts with trade data yet.", ephemeral=True
            )
            return

        # Format as a simple list
        account_list = "\n".join([f"  • {account}" for account in sorted_accounts])

        s1 = f"**Your Accounts:**\n{account_list}\n\n"
        s1 += f"💡 **Tip:** Use `{const.ACCOUNT_ALL}` in commands to query all accounts at once."

        await interaction.response.send_message(s1, ephemeral=True)

    @client.tree.command(
        name="report_profit", description="Generate profit summary report", guilds=const.GUILD_IDS
    )
    async def report_profit(
        interaction: discord.Interaction, account: str, symbol_exclude: str | None = None
    ):
        log_command(interaction, "report_profit", account=account, symbol_exclude=symbol_exclude)

        user = interaction.user.name

        # Convert "ALL" (case-insensitive) to None for querying all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        if not os.path.exists(const.REPORT_DIR):
            os.makedirs(const.REPORT_DIR)

        rpt = ProfitReport(client.db, user, symbol_exclude=symbol_exclude, account=account_filter)

        await interaction.response.defer(thinking=True, ephemeral=True)
        report_path = rpt.report()
        report_name = f"{rpt.title}.pdf"
        report_name = report_name.replace(" ", "_")
        logger.info(f"report_path: {report_path}")
        logger.info(f"report_name: {report_name}")
        if not os.path.exists(report_path):
            logger.info(f"Report path not found: {report_path}")
            await interaction.followup.send("Report does not exist.", ephemeral=True)
            return

        with open(report_path, "rb") as file:
            file_attachment = discord.File(file, filename=report_name)
            await interaction.followup.send(file=file_attachment, ephemeral=True)

    @client.tree.command(
        name="report_symbol",
        description="Generate ETF/symbol details report",
        guilds=const.GUILD_IDS,
    )
    async def report_symbol(interaction: discord.Interaction, account: str, symbol: str):
        log_command(interaction, "report_symbol", account=account, symbol=symbol)

        user = interaction.user.name

        # Convert "ALL" (case-insensitive) to None for querying all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        if not os.path.exists(const.REPORT_DIR):
            os.makedirs(const.REPORT_DIR)

        rpt = SymbolReport(client.db, user, symbol, account=account_filter)

        await interaction.response.defer(thinking=True, ephemeral=True)
        report_path = rpt.report()
        report_name = f"{rpt.title}.pdf"
        report_name = report_name.replace(" ", "_")
        logger.info(f"report_path: {report_path}")
        logger.info(f"report_name: {report_name}")
        if not os.path.exists(report_path):
            logger.info(f"Report path not found: {report_path}")
            await interaction.followup.send("Report does not exist.", ephemeral=True)
            return

        with open(report_path, "rb") as file:
            file_attachment = discord.File(file, filename=report_name)
            await interaction.followup.send(file=file_attachment, ephemeral=True)

    @client.tree.command(
        name="report_options_pivot",
        description="Generate options pivot report (current year)",
        guilds=const.GUILD_IDS,
    )
    async def report_options_pivot(interaction: discord.Interaction, account: str):
        log_command(interaction, "report_options_pivot", account=account)

        user = interaction.user.name

        # Convert "ALL" (case-insensitive) to None for querying all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        if not os.path.exists(const.REPORT_DIR):
            os.makedirs(const.REPORT_DIR)

        rpt = OptionsPivotReport(client.db, user, account=account_filter)

        await interaction.response.defer(thinking=True, ephemeral=True)
        report_path = rpt.report()
        report_name = f"{rpt.title}.pdf"
        report_name = report_name.replace(" ", "_")
        logger.info(f"report_path: {report_path}")
        logger.info(f"report_name: {report_name}")
        if not os.path.exists(report_path):
            logger.info(f"Report path not found: {report_path}")
            await interaction.followup.send("Report does not exist.", ephemeral=True)
            return

        with open(report_path, "rb") as file:
            file_attachment = discord.File(file, filename=report_name)
            await interaction.followup.send(file=file_attachment, ephemeral=True)

    @client.tree.command(name="trade", description="Record option trade(s)", guilds=const.GUILD_IDS)
    async def trade(interaction: discord.Interaction):
        log_command(interaction, "trade")

        modal = TradeModal(title="Enter Your Trades")
        modal.set_trades(client.trades, client.dividends, client.deposits, client.shares)

        await interaction.response.send_modal(modal)

    @client.tree.command(
        name="delete", description="Delete a transaction by id", guilds=const.GUILD_IDS
    )
    @app_commands.choices(
        table=[
            app_commands.Choice(name="Options", value="trades"),
            app_commands.Choice(name="Dividends", value="dividends"),
            app_commands.Choice(name="Shares", value="shares"),
            app_commands.Choice(name="Deposits", value="deposits"),
        ]
    )
    async def delete(interaction: discord.Interaction, table: app_commands.Choice[str], id: int):
        log_command(interaction, "delete", table=table.value, id=id)

        user = interaction.user.name
        count = 0
        if table.value == "trades":
            count = client.trades.delete(user, id)
        elif table.value == "dividends":
            count = client.dividends.delete(user, id)
        elif table.value == "shares":
            count = client.shares.delete(user, id)
        elif table.value == "deposits":
            count = client.deposits.delete(user, id)

        s1 = f"Count: {count} transactions delete from {table.value}."
        await interaction.response.send_message(s1, ephemeral=True)

    @client.tree.command(
        name="delete_all",
        description="Delete all options, dividends, shares and deposits for an account.  Use with caution",
        guilds=const.GUILD_IDS,
    )
    async def delete_all(interaction: discord.Interaction, account: str):
        log_command(interaction, "delete_all", account=account)

        user = interaction.user.name
        cnt_options = client.trades.delete_all(user, account)
        cnt_dividends = client.dividends.delete_all(user, account)
        cnt_shares = client.shares.delete_all(user, account)
        cnt_deposits = client.deposits.delete_all(user, account)

        s1 = f"Deleting transactions for account: {account}\n"
        s1 = f"{s1}   Options deleted: {cnt_options}\n"
        s1 = f"{s1}   Dividends deleted: {cnt_dividends}\n"
        s1 = f"{s1}   Shares deleted: {cnt_shares}\n"
        s1 = f"{s1}   Deposits deleted: {cnt_deposits}\n"

        await interaction.response.send_message(s1, ephemeral=True)

    @client.tree.command(name="download", description="Download trades", guilds=const.GUILD_IDS)
    async def download(interaction: discord.Interaction, account: str):
        log_command(interaction, "download", account=account)

        user = interaction.user.name

        # Convert "ALL" (case-insensitive) to None for downloading all accounts
        account_filter = None if account.upper() == const.ACCOUNT_ALL else account

        if not os.path.exists(const.DOWNLOADS_DIR):
            os.makedirs(const.DOWNLOADS_DIR)

        try:
            downloader = BotDownloads(
                client.trades, client.dividends, client.shares, client.deposits
            )
            zip_filename = downloader.process(user, account=account_filter)

            if not os.path.exists(zip_filename):
                await interaction.response.send_message(
                    f"File {zip_filename} does not exist.", ephemeral=True
                )
                return

            with open(zip_filename, "rb") as file:
                file_attachment = discord.File(file)
                await interaction.response.send_message(file=file_attachment, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Error sending the file: {e!s}", ephemeral=True
            )

    @client.tree.command(
        name="upload", description="Brokerage upload (auto-detects format)", guilds=const.GUILD_IDS
    )
    async def upload(
        interaction: discord.Interaction,
        account: str,
        attachment: discord.Attachment,
        append_only: str = "False",
    ):
        # attachment and account are now required - Discord won't allow submission without them

        # Check if the file is a csv file BEFORE deferring
        if not attachment.filename.endswith(".csv"):
            await interaction.response.send_message("Only csv files are allowed.", ephemeral=True)
            return

        # Defer IMMEDIATELY before any long-running operations
        await interaction.response.defer(thinking=True, ephemeral=True)

        if append_only.lower() == "false":
            append_flag = False
        else:
            append_flag = True

        # Capture guild_id from Discord interaction
        guild_id = interaction.guild.id if interaction.guild else None

        user = interaction.user.name

        # Download the file (can be slow for large files)
        if not os.path.exists(const.UPLOADS_DIR):
            os.makedirs(const.UPLOADS_DIR)

        from pathlib import Path

        file_path_str = f"{const.UPLOADS_DIR}/{user}.{attachment.filename}"
        file_path = Path(file_path_str)
        await attachment.save(file_path)

        try:
            # Auto-detect brokerage format
            identifier = BotUploadIdentifier()
            brokerage_type, confidence = identifier.identify(file_path_str)

            if brokerage_type == BrokerageType.UNKNOWN:
                await interaction.followup.send(
                    f"Unable to automatically detect brokerage format (confidence: {confidence:.1%}).\n"
                    f"Please check the file format and try again, or contact support.",
                    ephemeral=True,
                )
                return

            detected_format = brokerage_type.value
            logger.info(f"Auto-detected format: {detected_format} with {confidence:.1%} confidence")

            log_command(
                interaction,
                "upload",
                format=detected_format,
                filename=attachment.filename,
                size=attachment.size,
                account=account,
                append=append_flag,
                confidence=f"{confidence:.1%}",
            )

            if detected_format not in BotUploads.formats_supported():
                await interaction.followup.send(
                    f"Format {detected_format} not supported yet", ephemeral=True
                )
                return

            uploader = BotUploads(
                file_path_str,
                detected_format,
                client.trades,
                client.dividends,
                client.shares,
                client.deposits,
            )

            # Process upload directly in main thread to avoid SQLite threading issues
            status, msg = uploader.process(user, append_flag, guild_id, account)

            # Add detection info at the top of success message
            detection_info = f"**Auto-detected:** {detected_format.capitalize()} ({confidence:.1%} confidence)\n\n"
            await interaction.followup.send(detection_info + msg, ephemeral=True)

        except Exception as e:
            logger.error(f"Error processing upload: {e!s}", exc_info=True)
            await interaction.followup.send(f"Error processing the file: {e!s}", ephemeral=True)

    @client.tree.command(
        name="scan_puts",
        description="Scan PUT options chain for trade opportunities",
        guilds=const.GUILD_IDS,
    )
    @app_commands.describe(
        symbols="Comma-separated symbols to scan (e.g., 'ETHU,TSLA'). Default: your watchlist",
        delta_min="Minimum delta threshold (default: 0.01)",
        delta_max="Maximum delta threshold (default: 0.30)",
        max_expiration_days="Maximum days to expiration (default: 7)",
        iv_min="Minimum implied volatility % (default: 15.0)",
        open_interest_min="Minimum open interest (default: 10)",
        volume_min="Minimum volume (default: 0)",
        strike_proximity="Maximum distance from current price % (default: 40%)",
        top_candidates="Number of top results to return (default: 50)",
    )
    async def scan_puts(
        interaction: discord.Interaction,
        symbols: str | None = None,
        delta_min: float = 0.01,
        delta_max: float = 0.3,
        max_expiration_days: int = 7,
        iv_min: float = 15.0,
        open_interest_min: int = 10,
        volume_min: int = 0,
        strike_proximity: float = 0.40,
        top_candidates: int = 50,
    ):
        log_command(
            interaction,
            "scan_puts",
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_expiration_days,
        )

        # Immediately defer the response to avoid Discord timeout
        await interaction.response.defer(thinking=True, ephemeral=True)

        tracker = Scanner(
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_expiration_days,
            iv_min=iv_min,
            open_interest_min=open_interest_min,
            volume_min=volume_min,
            strike_proximity=strike_proximity,
            top_candidates=top_candidates,
        )

        username = interaction.user.name
        guild_id = interaction.guild.id if interaction.guild else None

        # Get symbols from parameter or user's watchlist
        if symbols:
            # Use symbols from parameter
            symbols_list = [s.strip().upper() for s in symbols.split(",")]
            logger.info(
                f"Scanning {len(symbols_list)} symbols from parameter: {', '.join(symbols_list)}"
            )
        else:
            # Get symbols from user's watchlist
            symbols_list = client.watchlists.list_symbols(username, guild_id=guild_id)

        # If no symbols available, return instructions
        if not symbols_list:
            help_msg = (
                "No symbols to scan. You can either:\n\n"
                "**Option 1:** Provide symbols directly using the `symbols` parameter\n"
                "  Example: `/scan_puts symbols:ETHU,TSLA,MSTU`\n\n"
                "**Option 2:** Use your watchlist\n"
                "1. Use `/my_watchlist_add` to add symbols (e.g., `/my_watchlist_add symbols: TSLL AAPL SPY`)\n"
                "2. View your watchlist with `/my_watchlist`\n"
                "3. Remove symbols with `/my_watchlist_remove` (e.g., `/my_watchlist_remove symbols: TSLL`)\n\n"
                "Once you've added symbols, run `/scan_puts` again to find trade candidates."
            )
            await interaction.followup.send(help_msg, ephemeral=True)
            return

        # Run the scan in executor to avoid blocking Discord heartbeat
        # Scanning many symbols can take 30-60+ seconds with sequential API calls
        loop = asyncio.get_event_loop()
        df_result, table_str, _ = await loop.run_in_executor(
            None,  # Use default executor
            tracker.scan,
            "PUT",
            symbols_list,
        )

        if df_result is None:
            await interaction.followup.send("No results found.", ephemeral=True)
        else:
            # Generate PNG image in downloads directory with username prefix
            renderer = ScannerRenderer(output_dir=const.DOWNLOADS_DIR)
            image_path = renderer.render(
                df_result,
                title="PUT Options Scan",
                chain_type="PUT",
                username=username,
                delta_min=delta_min,
                delta_max=delta_max,
                max_days=max_expiration_days,
            )

            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as file:
                    file_attachment = discord.File(file, filename=f"{username}_scanner_put.png")
                    await interaction.followup.send(file=file_attachment, ephemeral=True)
            else:
                # Fallback to text if image generation fails
                await interaction.followup.send(
                    f"PUT option chain\n```{table_str}```", ephemeral=True
                )

    @client.tree.command(
        name="scan_calls",
        description="Scan CALL options chain for trade opportunities",
        guilds=const.GUILD_IDS,
    )
    @app_commands.describe(
        symbols="Comma-separated symbols to scan (e.g., 'ETHU,TSLA'). Default: your watchlist",
        delta_min="Minimum delta threshold (default: 0.01)",
        delta_max="Maximum delta threshold (default: 0.30)",
        max_expiration_days="Maximum days to expiration (default: 7)",
        iv_min="Minimum implied volatility % (default: 15.0)",
        open_interest_min="Minimum open interest (default: 10)",
        volume_min="Minimum volume (default: 0)",
        strike_proximity="Maximum distance from current price % (default: 40%)",
        top_candidates="Number of top results to return (default: 50)",
    )
    async def scan_calls(
        interaction: discord.Interaction,
        symbols: str | None = None,
        delta_min: float = 0.01,
        delta_max: float = 0.3,
        max_expiration_days: int = 7,
        iv_min: float = 15.0,
        open_interest_min: int = 10,
        volume_min: int = 0,
        strike_proximity: float = 0.40,
        top_candidates: int = 50,
    ):
        log_command(
            interaction,
            "scan_calls",
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_expiration_days,
        )

        # Immediately defer the response to avoid Discord timeout
        await interaction.response.defer(thinking=True, ephemeral=True)

        tracker = Scanner(
            delta_min=delta_min,
            delta_max=delta_max,
            max_expiration_days=max_expiration_days,
            iv_min=iv_min,
            open_interest_min=open_interest_min,
            volume_min=volume_min,
            strike_proximity=strike_proximity,
            top_candidates=top_candidates,
        )

        username = interaction.user.name
        guild_id = interaction.guild.id if interaction.guild else None

        # Get symbols from parameter or user's watchlist
        if symbols:
            # Use symbols from parameter
            symbols_list = [s.strip().upper() for s in symbols.split(",")]
            logger.info(
                f"Scanning {len(symbols_list)} symbols from parameter: {', '.join(symbols_list)}"
            )
        else:
            # Get symbols from user's watchlist
            symbols_list = client.watchlists.list_symbols(username, guild_id=guild_id)

        # If no symbols available, return instructions
        if not symbols_list:
            help_msg = (
                "No symbols to scan. You can either:\n\n"
                "**Option 1:** Provide symbols directly using the `symbols` parameter\n"
                "  Example: `/scan_calls symbols:ETHU,TSLA,MSTU`\n\n"
                "**Option 2:** Use your watchlist\n"
                "1. Use `/my_watchlist_add` to add symbols (e.g., `/my_watchlist_add symbols: TSLL AAPL SPY`)\n"
                "2. View your watchlist with `/my_watchlist`\n"
                "3. Remove symbols with `/my_watchlist_remove` (e.g., `/my_watchlist_remove symbols: TSLL`)\n\n"
                "Once you've added symbols, run `/scan_calls` again to find trade candidates."
            )
            await interaction.followup.send(help_msg, ephemeral=True)
            return

        # Run the scan in executor to avoid blocking Discord heartbeat
        # Scanning many symbols can take 30-60+ seconds with sequential API calls
        loop = asyncio.get_event_loop()
        df_result, table_str, _ = await loop.run_in_executor(
            None,  # Use default executor
            tracker.scan,
            "CALL",
            symbols_list,
        )

        if df_result is None:
            await interaction.followup.send("No results found.", ephemeral=True)
        else:
            # Generate PNG image in downloads directory with username prefix
            renderer = ScannerRenderer(output_dir=const.DOWNLOADS_DIR)
            image_path = renderer.render(
                df_result,
                title="CALL Options Scan",
                chain_type="CALL",
                username=username,
                delta_min=delta_min,
                delta_max=delta_max,
                max_days=max_expiration_days,
            )

            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as file:
                    file_attachment = discord.File(file, filename=f"{username}_scanner_call.png")
                    await interaction.followup.send(file=file_attachment, ephemeral=True)
            else:
                # Fallback to text if image generation fails
                await interaction.followup.send(
                    f"CALL option chain\n```{table_str}```", ephemeral=True
                )

    class HelpPaginator(discord.ui.View):
        """Paginated help system with page buttons"""

        def __init__(self):
            super().__init__(timeout=300)  # 5 minute timeout
            self.current_page = 0
            self.pages = self._create_pages()
            self._update_buttons()

        def _create_pages(self) -> list[discord.Embed]:
            """Create all help pages"""
            pages = []

            # Page 1: Overview + Getting Started
            page1 = discord.Embed(
                title="🐝 WheelHive Help",
                description=(
                    "**Where Wheel Traders Multiply Their Intelligence**\n\n"
                    "AI-powered Discord bot for tracking trades, analyzing performance, "
                    "and finding opportunities.\n\n"
                    "**Getting Started**\n"
                    "• Track multiple accounts: `IRA`, `Joint`, `Taxable`\n"
                    "• Use `account:ALL` to view data across all accounts\n"
                    "• Upload broker CSVs with `/upload` to import trades\n"
                    "• Type `/` to see all available commands"
                ),
                color=discord.Color.gold(),
            )
            page1.add_field(
                name="🚀 Essential Commands",
                value=(
                    "`/my_accounts` - List your trading accounts\n"
                    "`/my_trades` - View your transactions\n"
                    "`/my_trade_stats` - View trading statistics\n"
                    "`/about` - Bot info and uptime"
                ),
                inline=False,
            )
            page1.set_footer(text="Page 1 of 4 • wheelhive.ai")
            pages.append(page1)

            # Page 2: Trading & Analytics
            page2 = discord.Embed(
                title="📊 Trading & Analytics",
                description="Track performance and generate comprehensive reports.",
                color=discord.Color.gold(),
            )
            page2.add_field(
                name="Reports",
                value=(
                    "`/report_profit` - Profit summary (all symbols)\n"
                    "`/report_symbol` - Detailed symbol analysis\n"
                    "`/report_options_pivot` - Premium by symbol (YTD)"
                ),
                inline=False,
            )
            page2.add_field(
                name="Statistics",
                value=(
                    "`/my_trade_stats` - Monthly summaries & win/loss\n"
                    "`/my_trades` - Filter by account/symbol/type\n"
                    "`/extrinsic_value` - Calculate option values"
                ),
                inline=False,
            )
            page2.add_field(
                name="💡 Tip",
                value=(
                    "Use `symbol_exclude:SPAXX,FDRXX` in reports to "
                    "exclude cash-like symbols from profit calculations."
                ),
                inline=False,
            )
            page2.set_footer(text="Page 2 of 4 • wheelhive.ai")
            pages.append(page2)

            # Page 3: Scanner & Watchlist
            page3 = discord.Embed(
                title="🔍 Options Scanner",
                description="Find trade opportunities based on Greeks, IV, and liquidity.",
                color=discord.Color.gold(),
            )
            page3.add_field(
                name="Scanner Commands",
                value=(
                    "`/scan_puts` - Scan PUT options chains\n"
                    "`/scan_calls` - Scan CALL options chains\n\n"
                    "**Optional parameters:**\n"
                    "• `symbols` - Tickers to scan (default: watchlist)\n"
                    "• `delta_min/max` - Delta range (default: 0.01-0.30)\n"
                    "• `max_expiration_days` - DTE limit (default: 7)\n"
                    "• `iv_min` - Min implied volatility (default: 15%)"
                ),
                inline=False,
            )
            page3.add_field(
                name="Watchlist Management",
                value=(
                    "`/my_watchlist` - View your watchlist\n"
                    "`/my_watchlist_add` - Add symbols\n"
                    "`/delete` → Watchlist - Remove symbols"
                ),
                inline=False,
            )
            page3.add_field(
                name="💡 Tip",
                value=(
                    "Scanner results are color-coded: Green = sweet spot, "
                    "Yellow = moderate, Red = risky. Results sorted by score (0-100)."
                ),
                inline=False,
            )
            page3.set_footer(text="Page 3 of 4 • wheelhive.ai")
            pages.append(page3)

            # Page 4: Data Management + Resources
            page4 = discord.Embed(
                title="📥 Data Management & Resources",
                description="Import, export, and manage your trading data.",
                color=discord.Color.gold(),
            )
            page4.add_field(
                name="Import & Export",
                value=(
                    "`/upload` - Import broker CSV (auto-detects format)\n"
                    "`/trade` - Manually record transactions\n"
                    "`/download` - Export all data to CSV\n"
                    "`/delete` - Delete specific transaction\n"
                    "`/delete_all` - Delete all for an account"
                ),
                inline=False,
            )
            page4.add_field(
                name="Supported Brokers",
                value=(
                    "✅ Fidelity • Schwab • IBKR • Robinhood\n\n"
                    "Visit **wheelhive.ai/docs** for detailed broker export guides."
                ),
                inline=False,
            )
            page4.add_field(
                name="📚 Resources",
                value=(
                    "• **Website:** wheelhive.ai\n"
                    "• **Full Documentation:** wheelhive.ai/docs\n"
                    "• **Community Support:** Join our Discord\n"
                    "• **Quick Reference:** Use `/help` anytime"
                ),
                inline=False,
            )
            page4.set_footer(text=f"Page 4 of 4 • WheelHive v{const.VERSION}")
            pages.append(page4)

            return pages

        def _update_buttons(self):
            """Update button states based on current page"""
            # Clear existing buttons
            self.clear_items()

            # Add page number buttons (1-4)
            for i in range(len(self.pages)):
                button: discord.ui.Button[Self] = discord.ui.Button(
                    label=f"Pg {i + 1}",
                    style=discord.ButtonStyle.green
                    if i == self.current_page
                    else discord.ButtonStyle.primary,
                    custom_id=f"page_{i}",
                )
                button.callback = self._make_page_callback(i)  # type: ignore[method-assign]
                self.add_item(button)

            # Add external links
            self.add_item(
                discord.ui.Button(
                    label="📚 Docs",
                    style=discord.ButtonStyle.link,
                    url="https://wheelhive.ai/docs",
                )
            )
            self.add_item(
                discord.ui.Button(
                    label="🌐 Website",
                    style=discord.ButtonStyle.link,
                    url="https://wheelhive.ai",
                )
            )

        def _make_page_callback(self, page_num: int):
            """Create callback for page button"""

            async def callback(interaction: discord.Interaction):
                self.current_page = page_num
                self._update_buttons()
                await interaction.response.edit_message(
                    embed=self.pages[self.current_page], view=self
                )

            return callback

    @client.tree.command(name="help", description="Interactive help guide", guilds=const.GUILD_IDS)
    async def help(interaction: discord.Interaction):
        log_command(interaction, "help")

        view = HelpPaginator()
        await interaction.response.send_message(embed=view.pages[0], view=view, ephemeral=True)

    @client.tree.command(
        name="my_watchlist", description="View your watchlist", guilds=const.GUILD_IDS
    )
    async def my_watchlist(interaction: discord.Interaction):
        log_command(interaction, "my_watchlist")

        user = interaction.user.name
        guild_id = interaction.guild.id if interaction.guild else None

        # Use as_str() method for consistent multi-column formatting
        table_str = client.watchlists.as_str(user, guild_id=guild_id, symbols_per_row=5)

        if table_str == "Watchlist is empty.":
            await interaction.response.send_message(
                "Your watchlist is empty. Use `/my_watchlist_add` to add symbols.", ephemeral=True
            )
            return

        # Count symbols for header
        symbols_list = client.watchlists.list_symbols(user, guild_id=guild_id)
        count_str = f"({len(symbols_list)} symbol{'s' if len(symbols_list) != 1 else ''})"

        await interaction.response.send_message(
            f"**Your Watchlist** {count_str}\n```{table_str}```", ephemeral=True
        )

    @client.tree.command(
        name="my_watchlist_add",
        description="Add symbols to your watchlist (space or comma separated)",
        guilds=const.GUILD_IDS,
    )
    async def my_watchlist_add(interaction: discord.Interaction, symbols: str):
        log_command(interaction, "my_watchlist_add", symbols=symbols)

        # Defer response immediately to avoid timeout with large symbol lists
        await interaction.response.defer(thinking=True, ephemeral=True)

        user = interaction.user.name
        guild_id = interaction.guild.id if interaction.guild else None

        # Parse space or comma delimited list
        symbols_list = re.split(r"[,\s]+", symbols.strip())

        added = []
        skipped = []

        for symbol in symbols_list:
            if not symbol:  # Skip empty strings from split
                continue
            success = client.watchlists.add(user, symbol, guild_id=guild_id)
            if success:
                added.append(symbol.upper())
            else:
                skipped.append(symbol.upper())

        # Build response message
        msg_parts = []
        if added:
            msg_parts.append(f"**Added:** {', '.join(added)}")
        if skipped:
            msg_parts.append(f"**Already in watchlist:** {', '.join(skipped)}")

        if msg_parts:
            await interaction.followup.send("\n".join(msg_parts), ephemeral=True)
        else:
            await interaction.followup.send("No symbols provided.", ephemeral=True)

    @client.tree.command(
        name="my_watchlist_remove",
        description="Remove symbols from your watchlist (space or comma separated)",
        guilds=const.GUILD_IDS,
    )
    async def my_watchlist_remove(interaction: discord.Interaction, symbols: str):
        log_command(interaction, "my_watchlist_remove", symbols=symbols)

        user = interaction.user.name
        guild_id = interaction.guild.id if interaction.guild else None

        # Parse space or comma delimited list
        symbols_list = re.split(r"[,\s]+", symbols.strip())

        removed = []
        not_found = []

        for symbol in symbols_list:
            if not symbol:  # Skip empty strings from split
                continue
            count = client.watchlists.remove(user, symbol, guild_id=guild_id)
            if count > 0:
                removed.append(symbol.upper())
            else:
                not_found.append(symbol.upper())

        # Build response message
        msg_parts = []
        if removed:
            msg_parts.append(f"**Removed:** {', '.join(removed)}")
        if not_found:
            msg_parts.append(f"**Not in watchlist:** {', '.join(not_found)}")

        if msg_parts:
            await interaction.response.send_message("\n".join(msg_parts), ephemeral=True)
        else:
            await interaction.response.send_message("No symbols provided.", ephemeral=True)

    # ============================================================
    # LLM Model Selection Commands (DEV ONLY - Testing)
    # ============================================================

    @client.tree.command(
        name="llm_models",
        description="List available AI models for analysis",
        guilds=const.DEV_GUILD_IDS,
    )
    async def llm_models(interaction: discord.Interaction):
        log_command(interaction, "llm_models")

        from user_preferences import get_user_preferences

        user = interaction.user.name
        user_prefs = get_user_preferences()

        try:
            # Get user's current selection and tier
            current_model = user_prefs.get_llm_preference(user)
            user_tier = user_prefs.get_user_tier(user)  # type: ignore[attr-defined]
            allowed_model_keys = const.TIER_MODEL_ACCESS.get(user_tier, [])  # type: ignore[attr-defined]

            # Show ALL models, but indicate which ones user has access to
            all_models = list(const.AVAILABLE_MODELS.items())  # type: ignore[attr-defined]

            # Build response
            msg_parts = []
            msg_parts.append(f"**Your Tier:** {user_tier}")
            msg_parts.append(
                f"**Current Model:** {const.AVAILABLE_MODELS[current_model]['display_name']}\n"  # type: ignore[attr-defined]
            )
            msg_parts.append("**All Available Models:**\n")
            msg_parts.append("(Models marked with 🔒 require a higher tier)\n")

            for model_key, model_info in all_models:
                is_current = " ✓ ACTIVE" if model_key == current_model else ""
                has_access = model_key in allowed_model_keys
                access_icon = "" if has_access else "🔒 "

                msg_parts.append(
                    f"• {access_icon}**{model_info['display_name']}**{is_current}\n"
                    f"  `{model_key}` - {model_info['description']}\n"
                    f"  Provider: {model_info['provider']} | "
                    f"Cost: {model_info['cost_tier']} | "
                    f"Quality: {model_info['quality']}/5 | "
                    f"Speed: {model_info['speed']}\n"
                )

            msg_parts.append("\nUse `/llm_set <model_key>` to change your model.")

            response = "\n".join(msg_parts)

            # Split if too long using smart splitting
            chunks = util.smart_split_message(response, const.DISCORD_MAX_CHAR_COUNT)

            # Send first chunk as response, rest as followups
            await interaction.response.send_message(chunks[0], ephemeral=True)
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in llm_models command: {e}", exc_info=True)
            await interaction.response.send_message(f"Error listing models: {e!s}", ephemeral=True)

    @client.tree.command(
        name="llm_status",
        description="Show your current AI model selection",
        guilds=const.DEV_GUILD_IDS,
    )
    async def llm_status(interaction: discord.Interaction):
        log_command(interaction, "llm_status")

        from user_preferences import get_user_preferences

        user = interaction.user.name
        user_prefs = get_user_preferences()

        try:
            summary = user_prefs.get_user_summary(user)

            msg = (
                f"**AI Model Status for {user}**\n\n"
                f"**Current Model:** {summary['model_display_name']}\n"
                f"**Model Key:** `{summary['llm_model']}`\n"
                f"**Provider:** {summary['model_provider']}\n"
                f"**Your Tier:** {summary['user_tier']}\n"
                f"**Available Models:** {summary['model_count']}\n\n"
                f"Use `/llm_models` to see all available models.\n"
                f"Use `/llm_set <model_key>` to change your model."
            )

            await interaction.response.send_message(msg, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in llm_status command: {e}", exc_info=True)
            await interaction.response.send_message(f"Error getting status: {e!s}", ephemeral=True)

    @client.tree.command(
        name="llm_set", description="Set your preferred AI model", guilds=const.DEV_GUILD_IDS
    )
    async def llm_set(interaction: discord.Interaction, model_key: str):
        log_command(interaction, "llm_set", model_key=model_key)

        from user_preferences import get_user_preferences

        user = interaction.user.name
        user_prefs = get_user_preferences()

        try:
            # Validate model exists
            if model_key not in const.AVAILABLE_MODELS:  # type: ignore[attr-defined]
                available_keys = list(const.AVAILABLE_MODELS.keys())  # type: ignore[attr-defined]

                # Try to suggest a similar model name
                suggestion = None
                model_lower = model_key.lower()
                for key in available_keys:
                    if model_lower in key.lower() or key.lower() in model_lower:
                        suggestion = key
                        break

                error_msg = f"❌ Invalid model key: `{model_key}`\n\n"
                if suggestion:
                    error_msg += f"💡 Did you mean `{suggestion}`?\n\n"
                error_msg += "**Available models:**\n"
                for k in available_keys:
                    model_info = const.AVAILABLE_MODELS[k]  # type: ignore[attr-defined]
                    error_msg += f"  • `{k}` - {model_info['display_name']}\n"
                error_msg += "\nℹ️ Your model preference was **NOT changed**. Use `/llm_models` for detailed information."

                await interaction.response.send_message(error_msg, ephemeral=True)
                return

            # Try to set the model (will check tier access)
            success = user_prefs.set_llm_preference(user, model_key)

            if success:
                model_info = const.AVAILABLE_MODELS[model_key]  # type: ignore[attr-defined]
                await interaction.response.send_message(
                    f"✓ Model updated successfully!\n\n"
                    f"**New Model:** {model_info['display_name']}\n"
                    f"**Provider:** {model_info['provider']}\n"
                    f"**Description:** {model_info['description']}\n\n"
                    f"This model will be used for all `!ask` commands.",
                    ephemeral=True,
                )
            else:
                user_tier = user_prefs.get_user_tier(user)  # type: ignore[attr-defined]
                await interaction.response.send_message(
                    f"❌ Unable to set model `{model_key}`.\n\n"
                    f"This model may require a higher tier. Your current tier: **{user_tier}**\n\n"
                    f"Use `/llm_models` to see models available to you.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in llm_set command: {e}", exc_info=True)
            await interaction.response.send_message(f"Error setting model: {e!s}", ephemeral=True)

    @client.tree.command(
        name="analyze",
        description="AI-powered portfolio review with live market data",
        guilds=const.DEV_GUILD_IDS,
    )
    async def analyze(interaction: discord.Interaction):
        log_command(interaction, "analyze")

        user = interaction.user.name

        # Defer response since LLM analysis takes time (private response for financial data)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            analyzer = LLMAnalyzer(db=client.db, metrics_tracker=client.metrics)
            result = await asyncio.to_thread(analyzer.analyze_portfolio, user)
            await client._send_long_message_slash(interaction, result)

        except Exception as e:
            logger.error(f"Error in /analyze command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error analyzing portfolio: {e!s}\n\n"
                f"Ensure MCP server is running on port 8000 and ANTHROPIC_API_KEY is set.",
                ephemeral=True,
            )

    @client.tree.command(
        name="opportunities",
        description="Find trading opportunities based on your positions",
        guilds=const.DEV_GUILD_IDS,
    )
    async def opportunities(interaction: discord.Interaction):
        log_command(interaction, "opportunities")

        user = interaction.user.name

        # Defer response since LLM analysis takes time (private response for financial data)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            analyzer = LLMAnalyzer(db=client.db, metrics_tracker=client.metrics)
            result = await asyncio.to_thread(analyzer.find_opportunities, user)
            await client._send_long_message_slash(interaction, result)

        except Exception as e:
            logger.error(f"Error in /opportunities command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error finding opportunities: {e!s}\n\n"
                f"Ensure MCP server is running on port 8000 and ANTHROPIC_API_KEY is set.",
                ephemeral=True,
            )

    @client.tree.command(
        name="ask",
        description="Ask AI a custom question about your portfolio",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.describe(question="Your question (e.g., 'What are my riskiest positions?')")
    async def ask(interaction: discord.Interaction, question: str):
        log_command(interaction, "ask", question=question)

        user = interaction.user.name

        # Defer response since LLM analysis takes time (private response for financial data)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            analyzer = LLMAnalyzer(db=client.db, metrics_tracker=client.metrics)
            result = await asyncio.to_thread(analyzer.analyze, user, question)
            await client._send_long_message_slash(interaction, result)

        except Exception as e:
            logger.error(f"Error in /ask command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error analyzing question: {e!s}\n\n"
                f"Ensure MCP server is running on port 8000 and ANTHROPIC_API_KEY is set.",
                ephemeral=True,
            )

    # Check function to restrict command to specific user
    def is_sangelovich(interaction: discord.Interaction) -> bool:
        return interaction.user.name.lower() == "sangelovich"

    @client.tree.command(
        name="catch-up",
        description="Get a digest of community activity for missed days",
        guilds=const.DEV_GUILD_IDS,  # Testing in dev guild only
    )
    @app_commands.check(is_sangelovich)  # Only visible/usable by sangelovich
    @app_commands.describe(
        days="Number of days to catch up on (default: 1)",
        voice="Tone/style of the narrative",
        temperature="Creativity level for narrative (0.0-2.0, default 0.5 for data accuracy)",
    )
    @app_commands.choices(
        voice=[
            app_commands.Choice(name="Casual (friendly, conversational)", value="casual"),
            app_commands.Choice(name="Professional (formal, business-like)", value="professional"),
            app_commands.Choice(name="Technical (data-heavy, analytical)", value="technical"),
            app_commands.Choice(name="Energetic (enthusiastic, trader lingo)", value="energetic"),
        ]
    )
    async def catch_up(
        interaction: discord.Interaction,
        days: int = 1,
        voice: str = "casual",
        temperature: float = 0.5,
    ):
        """Generate an on-demand catch-up digest for missed community activity"""
        log_command(interaction, "catch-up", days=days, voice=voice, temperature=temperature)

        user = interaction.user.name
        logger.info(
            f"Catch-up digest requested by {user} for {days} day(s), voice={voice}, temperature={temperature}"
        )

        # Defer response since digest generation takes time (30-60s)
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            from reports.catchup_report import CatchUpReport
            from system_settings import get_settings

            # Get MCP URL from settings
            settings = get_settings(client.db)
            mcp_url = settings.get(const.SETTING_TRADING_MCP_URL)

            # Hardcode to Claude for now (testing phase)
            model = "claude-sonnet"
            # TODO: Re-enable user preferences once testing is complete
            # user_prefs = UserPreferences(client.db)
            # model = user_prefs.get_llm_preference(user)

            # Get guild ID from interaction
            if not interaction.guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server (not DMs)"
                )
                return

            # Generate digest using LLM with MCP tools
            # Temperature controls narrative creativity only - data accuracy is enforced by prompt
            report = CatchUpReport(
                mcp_url=mcp_url,
                username=user,
                model=model,
                guild_id=interaction.guild_id,
                days=days,
                temperature=temperature,  # User-specified temperature for narrative style
                voice=voice,
                metrics_tracker=client.metrics,
            )

            digest_text = await asyncio.to_thread(report.generate)

            # Save digest to disk for review
            try:
                import os
                from datetime import datetime

                digest_dir = os.path.join(const.DAILY_DIGEST_DIR, "catchup")
                os.makedirs(digest_dir, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"catchup_{user}_{days}d_{voice}_temp{temperature}_{timestamp}.md"
                filepath = os.path.join(digest_dir, filename)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("# Catch-up Digest\n")
                    f.write(f"- User: {user}\n")
                    f.write(f"- Guild ID: {interaction.guild_id}\n")
                    f.write(f"- Days: {days}\n")
                    f.write(f"- Voice: {voice}\n")
                    f.write(f"- Temperature: {temperature}\n")
                    f.write(f"- Model: {model}\n")
                    f.write(f"- Generated: {timestamp}\n")
                    f.write("\n---\n\n")
                    f.write(digest_text)

                logger.info(f"Catch-up digest saved to: {filepath}")
            except Exception as e:
                logger.error(f"Failed to save catch-up digest to disk: {e}")

            # Create private thread for the digest
            try:
                # Verify we're in a text channel
                if not isinstance(interaction.channel, discord.TextChannel):
                    await interaction.followup.send(
                        "❌ This command only works in text channels", ephemeral=True
                    )
                    return

                # Create private thread for catch-up
                thread = await interaction.channel.create_thread(
                    name=f"📊 {user}'s {days}-day Catch-up",
                    auto_archive_duration=1440,  # Archive after 24 hours of inactivity
                    type=discord.ChannelType.private_thread,
                )

                # Send digest in embeds to the thread
                # Embeds support 4096 chars in description (vs 2000 for plain text)
                # and look much more professional with color and structure
                chunks = util.smart_split_message(digest_text, 4096)  # Embed description limit

                for i, chunk in enumerate(chunks):
                    embed = discord.Embed(
                        title=f"📊 {days}-Day Catch-Up Digest"
                        if i == 0
                        else f"📊 Continued ({i + 1}/{len(chunks)})",
                        description=chunk,
                        color=discord.Color.blue(),
                        timestamp=datetime.now(),
                    )

                    # Add metadata to first embed
                    if i == 0:
                        embed.set_footer(
                            text=f"{voice.title()} voice • Temperature {temperature} • {model}"
                        )
                        embed.add_field(name="Period", value=f"Last {days} day(s)", inline=True)
                        embed.add_field(
                            name="Generated",
                            value=datetime.now().strftime("%b %d, %Y"),
                            inline=True,
                        )

                    await thread.send(embed=embed)

                # Confirm in channel (ephemeral - only user sees this)
                await interaction.followup.send(
                    f"✅ Your {days}-day catch-up digest is ready!\n{thread.jump_url}",
                    ephemeral=True,
                )

                logger.info(
                    f"Catch-up digest sent to {user} via private thread ({len(chunks)} embed(s))"
                )

            except discord.Forbidden:
                # Missing thread permissions
                await interaction.followup.send(
                    "❌ Unable to create thread. Bot needs 'Create Private Threads' permission.",
                    ephemeral=True,
                )
                logger.warning(f"Could not create catch-up thread for {user} - missing permissions")

        except Exception as e:
            logger.error(f"Error in /catch-up command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error generating catch-up digest: {e!s}\n\n"
                f"Troubleshooting:\n"
                f"• Ensure MCP server is running on port 8000\n"
                f"• Check ANTHROPIC_API_KEY is set\n"
                f"• Verify database has community messages",
                ephemeral=True,
            )

    # ============================================================
    # AI Tutor Command - Educational wheel strategy assistance
    # ============================================================

    @client.tree.command(
        name="tutor",
        description="Start an interactive AI tutor conversation about wheel strategy",
        guilds=const.DEV_GUILD_IDS,  # Testing in dev guild
    )
    @app_commands.describe(
        question="Your question about wheel strategy (creates thread, answers immediately)"
    )
    async def tutor(interaction: discord.Interaction, question: str):
        """AI tutor for wheel strategy learning - creates interactive conversation thread"""
        log_command(interaction, "tutor", question=question[:50])

        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a server", ephemeral=True
            )
            return

        # Verify we're in a text channel
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ This command only works in text channels", ephemeral=True
            )
            return

        # Send immediate response BEFORE creating thread
        confirmation = discord.Embed(
            title="🎓 Creating AI Tutor Thread",
            description=f"**Your Question:**\n{question}\n\n"
            f"⏳ Creating thread and analyzing with RAG-enhanced AI...\n"
            f"_This may take 30-60 seconds for complex queries._",
            color=discord.Color.blue(),
        )
        confirmation.set_footer(text="Thread will appear below when ready")
        await interaction.response.send_message(embed=confirmation, ephemeral=True)

        try:
            # Create a private thread for the conversation
            # Truncate question for thread name (Discord limit: 100 chars)
            thread_name = f"🎓 {question[:85]}" if len(question) <= 85 else f"🎓 {question[:82]}..."

            thread = await interaction.channel.create_thread(
                name=thread_name,
                auto_archive_duration=1440,  # Archive after 24 hours of inactivity
                type=discord.ChannelType.private_thread,
            )

            # Add the user to the thread
            await thread.add_user(interaction.user)

            # Send welcome message in thread
            welcome_embed = discord.Embed(
                title="🎓 Welcome to Your AI Wheel Strategy Tutor!",
                description=(
                    "I'm here to help you learn about wheel strategy options trading. "
                    "I have access to training materials and can answer your questions with sources.\n\n"
                    "**How this works:**\n"
                    "• I'll answer your question below with sources from training materials\n"
                    "• Ask follow-up questions anytime in this thread\n"
                    "• Rate answers with 👍 or 👎 to help improve responses\n"
                    "• Our conversation continues until you're satisfied\n\n"
                    "Answering your question now... 🤔"
                ),
                color=discord.Color.green(),
            )
            welcome_embed.set_footer(
                text="Powered by RAG-enhanced AI • This thread auto-archives after 24h of inactivity"
            )

            await thread.send(embed=welcome_embed)

            # Send immediate status message so user sees activity
            status_msg = await thread.send(
                "🤔 Analyzing your question with RAG-enhanced AI...\n"
                "_This may take 30-60 seconds for complex queries with tool calls._"
            )

            # Process the question through the tutor handler
            class FakeMessage:
                """Fake message object for processing initial question through message handler"""

                def __init__(self, content, author, channel, guild, status_message):
                    self.content = content
                    self.author = author
                    self.channel = channel
                    self.guild = guild
                    self._status_message = (
                        status_message  # Pass status msg so handler can delete it
                    )

                async def add_reaction(self, emoji):
                    """No-op for initial question - we don't show thinking reaction"""

                async def remove_reaction(self, emoji, user):
                    """No-op for initial question"""

            fake_msg = FakeMessage(
                content=question,
                author=interaction.user,
                channel=thread,
                guild=interaction.guild,
                status_message=status_msg,
            )

            # Process the question - this will delete our status_msg when done
            await client._handle_tutor_thread_message(fake_msg)

            # Update the initial message with final confirmation
            final_confirmation = discord.Embed(
                title="✅ AI Tutor Thread Ready",
                description=f"**Your Question:**\n{question}\n\n"
                f"✓ Analysis complete! Answer posted in thread with sources.\n\n"
                f"Ask follow-up questions anytime in the thread!",
                color=discord.Color.green(),
            )
            final_confirmation.add_field(
                name="Thread", value=f"[Click here to view]({thread.jump_url})", inline=False
            )
            final_confirmation.set_footer(
                text="Rate answers with 👍 👎 • Thread auto-archives after 24h of inactivity"
            )

            await interaction.edit_original_response(embed=final_confirmation)

            logger.info(
                f"AI Tutor thread created for {interaction.user.name} in guild {interaction.guild_id} "
                f"with question: {question[:50]}..."
            )

        except Exception as e:
            logger.error(f"Error creating tutor thread: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error creating tutor thread: {e!s}", ephemeral=True
            )

    # ============================================================
    # DEPRECATED: Old AI Assistant Implementation (to be removed)
    # ============================================================
    # The following code is deprecated and will be removed in a future update.
    # It has been replaced by the simpler modal-based /ask command above.

    async def is_author(interaction: discord.Interaction) -> bool:
        """Check if user is the bot author"""
        return interaction.user.name == const.AUTHOR

    # DEPRECATED: AIAssistantView class no longer used (replaced by simple modal)
    # class AIAssistantView(discord.ui.View):
    #     """Interactive buttons for AI Assistant responses"""
    #
    #     def __init__(self, question: str, tutor_instance, model: str, guild_id: int | None):
    #         super().__init__(timeout=600)  # 10 minute timeout
    #         self.question = question
    #         self.tutor_instance = tutor_instance
    #         self.model = model
    #         self.guild_id = guild_id

    #     @discord.ui.button(label="More Details", style=discord.ButtonStyle.primary, emoji="🔍")
    #     async def more_details_button(
    #         self, interaction: discord.Interaction, button: discord.ui.Button
    #     ):
    #         """Generate more detailed explanation"""
    #         # ... (button code commented out for brevity)
    #
    #     @discord.ui.button(label="Example", style=discord.ButtonStyle.secondary, emoji="💡")
    #     async def example_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #         """Show practical example"""
    #         # ... (button code commented out for brevity)
    #
    #     @discord.ui.button(label="Helpful", style=discord.ButtonStyle.success, emoji="👍")
    #     async def helpful_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #         """Log positive feedback"""
    #         # ... (button code commented out for brevity)
    #
    #     @discord.ui.button(label="Not Helpful", style=discord.ButtonStyle.danger, emoji="👎")
    #     async def not_helpful_button(
    #         self, interaction: discord.Interaction, button: discord.ui.Button
    #     ):
    #         """Log negative feedback"""
    #         # ... (button code commented out for brevity)

    # DEPRECATED: Replaced by /ask command above
    # @client.tree.command(
    #     name="ai_assistant",
    #     description="Ask the AI assistant about wheel strategy (Author only)",
    #     guilds=const.DEV_GUILD_IDS,  # Testing in dev guild only
    # )
    # @app_commands.check(is_author)
    # @app_commands.describe(
    #     question="Your question or topic (e.g., 'Explain covered calls' or 'How to select strikes?')",
    #     context="Additional context (optional - your experience level, specific details, etc.)",
    # )
    async def ai_assistant_deprecated(
        interaction: discord.Interaction, question: str, context: str | None = None
    ):
        """Ask AI assistant with RAG-enhanced learning - creates private thread with response"""
        log_command(interaction, "ai_assistant", question=question[:50])

        user = interaction.user.name
        logger.info(f"AI Assistant query from {user}: '{question[:100]}...'")

        # Defer response since RAG retrieval + LLM generation takes time
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # Verify we're in a text channel
            if not isinstance(interaction.channel, discord.TextChannel):
                await interaction.followup.send(
                    "❌ This command only works in text channels", ephemeral=True
                )
                return

            from rag import WheelStrategyTutor

            # Get AI tutor model from system settings
            settings = get_settings(client.db)
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

            # Initialize tutor with configured model and guild-specific content
            guild_id = interaction.guild.id if interaction.guild else None
            tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id)

            # Combine question with context
            full_query = question
            if context:
                full_query = f"{question}\n\nAdditional context: {context}"

            # Determine if this is a "learn" query (topic) or "ask" query (question)
            question_indicators = [
                "how",
                "what",
                "when",
                "where",
                "why",
                "which",
                "should",
                "can",
                "is",
                "are",
                "do",
                "does",
            ]
            is_question_type = "?" in question or any(
                question.lower().startswith(word) for word in question_indicators
            )

            # Run appropriate method in thread to avoid blocking event loop
            if is_question_type:
                result = await asyncio.to_thread(
                    tutor_instance.ask, question=full_query, n_results=3, temperature=0.7
                )
                header_emoji = "❓"
                header_label = "Question"
            else:
                result = await asyncio.to_thread(
                    tutor_instance.explain_topic, topic=full_query, n_results=5, temperature=0.7
                )
                header_emoji = "📚"
                header_label = "Learning"

            # Create private thread for the response
            thread = await interaction.channel.create_thread(
                name=f"{header_emoji} {question[:80]}",  # Truncate long questions
                auto_archive_duration=1440,  # Archive after 24 hours
                type=discord.ChannelType.private_thread,
            )

            # Format response with embeds
            answer_text = result["answer"]
            sources = result.get("sources", [])

            # Main answer embed
            answer_embed = discord.Embed(
                title=f"{header_emoji} {header_label}: {question[:200]}",
                description=answer_text[:4096],  # Embed description limit
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            answer_embed.set_footer(text=f"Powered by {model} • RAG-enhanced")

            await thread.send(embed=answer_embed)

            # Sources embed (if any sources were used)
            if sources:
                sources_text = "\n".join([f"• {source}" for source in sources[:10]])  # Limit to 10
                sources_embed = discord.Embed(
                    title="📖 Training Materials Used",
                    description=sources_text,
                    color=discord.Color.blue(),
                )
                await thread.send(embed=sources_embed)

            # DEPRECATED: Interactive buttons removed
            # view = AIAssistantView(
            #     question=question,
            #     tutor_instance=tutor_instance,
            #     model=model,
            #     guild_id=guild_id,
            # )
            # await thread.send("💡 Want to explore further?", view=view)

            # Log analytics
            try:
                analytics = RAGAnalytics()
                query_type = "ask" if is_question_type else "explain_topic"
                chunks = result.get("chunks", [])
                await asyncio.to_thread(
                    analytics.log_query,
                    username=user,
                    query_type=query_type,
                    query_text=question,
                    sources=chunks,
                    guild_id=guild_id,
                    n_results=len(chunks),
                    model=model,
                )
            except Exception as e:
                logger.warning(f"Failed to log RAG analytics: {e}")

            # Confirm in channel (ephemeral)
            await interaction.followup.send(
                f"✅ AI Assistant response ready!\n{thread.jump_url}", ephemeral=True
            )

            logger.info(f"AI Assistant responded to {user} using {len(sources)} sources via thread")

        except FileNotFoundError as e:
            logger.error(f"Vector store not found: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ **AI Assistant Not Initialized**\n\n"
                "The training materials vector store hasn't been created yet.\n\n"
                "**Setup Required:**\n"
                "```bash\n"
                "python scripts/rag/create_vector_store.py\n"
                "```",
                ephemeral=True,
            )

        except Exception as e:
            logger.error(f"Error in /ai_assistant command: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error: {e!s}\n\n"
                "Ensure vector store is initialized and model is accessible.",
                ephemeral=True,
            )

    # DEPRECATED: Error handler for old ai_assistant command
    # @ai_assistant_deprecated.error
    # async def ai_assistant_error(
    #     interaction: discord.Interaction, error: app_commands.AppCommandError
    # ):
    #     """Handle errors for ai_assistant command"""
    #     if isinstance(error, app_commands.CheckFailure):
    #         await interaction.response.send_message(
    #             "❌ This command is currently restricted to the bot author.", ephemeral=True
    #         )
    #     else:
    #         raise error

    # ============================================================
    # Admin Commands (Channels + FAQ Management)
    # ============================================================

    guild_channels = GuildChannels(client.db)

    @client.tree.command(
        name="channels_list",
        description="List all configured analysis channels",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_list(interaction: discord.Interaction):
        """List all channels configured for message analysis."""
        log_command(interaction, "channels_list")
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return
            channels = guild_channels.get_channels_for_guild(guild_id)

            if not channels:
                embed = discord.Embed(
                    title="📋 Configured Channels",
                    description="No channels configured for analysis.",
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Use /channels_add to configure channels")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Separate by category
            sentiment_channels = [c for c in channels if c[2] == "sentiment"]
            news_channels = [c for c in channels if c[2] == "news"]

            embed = discord.Embed(
                title="📋 Configured Analysis Channels",
                description=f"Currently analyzing **{len(channels)}** channel(s) in this server",
                color=discord.Color.blue(),
            )

            if sentiment_channels:
                sentiment_list = "\n".join(
                    [f"• <#{ch[0]}> (`{ch[1]}`)" for ch in sentiment_channels]
                )
                embed.add_field(name="💬 Community Channels", value=sentiment_list, inline=False)

            if news_channels:
                news_list = "\n".join([f"• <#{ch[0]}> (`{ch[1]}`)" for ch in news_channels])
                embed.add_field(name="📰 News Channels", value=news_list, inline=False)

            embed.set_footer(text="Use /channels_add or /channels_remove to modify")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing channels: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error listing channels: {e!s}", ephemeral=True)

    @client.tree.command(
        name="channels_add",
        description="Add a channel for message analysis",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.describe(
        channel="The channel to analyze messages from",
        category="Channel type (community for discussions, news for market news)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_add(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        category: Literal["community", "news"],
    ):
        """Add a channel for message analysis with validation."""
        log_command(interaction, "channels_add", channel=channel.name, category=category)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id or not interaction.guild:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Validate bot permissions
            if not client.user:
                await interaction.followup.send("❌ Bot user not available", ephemeral=True)
                return

            bot_member = interaction.guild.get_member(client.user.id)
            if not bot_member:
                await interaction.followup.send(
                    "❌ Could not find bot member in guild", ephemeral=True
                )
                return

            channel_perms = channel.permissions_for(bot_member)

            if not channel_perms.read_messages:
                await interaction.followup.send(
                    f"❌ I don't have permission to read messages in {channel.mention}\\n"
                    f"Please grant me `Read Messages` permission for that channel.",
                    ephemeral=True,
                )
                return

            if not channel_perms.read_message_history:
                await interaction.followup.send(
                    f"⚠️ Warning: I can read {channel.mention} but cannot read message history.\\n"
                    f"Please grant me `Read Message History` permission for full functionality.",
                    ephemeral=True,
                )
                # Allow to continue - they might fix permissions later

            # Map user-friendly "community" to internal "sentiment"
            internal_category = "sentiment" if category == "community" else "news"

            # Add to database
            guild_channels.add_channel(
                guild_id=guild_id,
                channel_id=channel.id,
                channel_name=channel.name,
                category=internal_category,
            )

            # Success embed
            category_emoji = "💬" if category == "community" else "📰"
            category_label = "Community" if category == "community" else "News"

            embed = discord.Embed(
                title="✅ Channel Added",
                description=f"Now analyzing messages from {channel.mention}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(
                name="Category", value=f"{category_emoji} {category_label}", inline=True
            )
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.set_footer(text="Messages will be analyzed for trading insights")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Channel added by {interaction.user.name}: {channel.name} "
                f"({channel.id}) as {category}"
            )

        except Exception as e:
            logger.error(f"Error adding channel: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error adding channel: {e!s}", ephemeral=True)

    @client.tree.command(
        name="channels_remove",
        description="Remove a channel from analysis",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.describe(channel="The channel to stop analyzing")
    @app_commands.checks.has_permissions(administrator=True)
    async def channels_remove(interaction: discord.Interaction, channel: discord.TextChannel):
        """Remove a channel from message analysis."""
        log_command(interaction, "channels_remove", channel=channel.name)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Check if channel is configured
            channels = guild_channels.get_channels_for_guild(guild_id)
            channel_ids = [c[0] for c in channels]

            if channel.id not in channel_ids:
                await interaction.followup.send(
                    f"ℹ️ {channel.mention} is not currently configured for analysis.", ephemeral=True
                )
                return

            # Remove from database
            guild_channels.remove_channel(guild_id=guild_id, channel_id=channel.id)

            # Success embed
            embed = discord.Embed(
                title="✅ Channel Removed",
                description=f"No longer analyzing messages from {channel.mention}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Guild ID", value=f"`{guild_id}`", inline=True)
            embed.set_footer(text="Use /channels_add to re-enable if needed")

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(
                f"Channel removed by {interaction.user.name}: {channel.name} ({channel.id})"
            )

        except Exception as e:
            logger.error(f"Error removing channel: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error removing channel: {e!s}", ephemeral=True)

    # FAQ commands use the modal, so just the list/remove commands
    @client.tree.command(
        name="faq_list",
        description="List all FAQs in knowledge base",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_list(interaction: discord.Interaction):
        """List all FAQs for the current guild."""
        log_command(interaction, "faq_list")
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Get FAQs for this guild
            from faq_manager import FAQManager

            faq_mgr = FAQManager(guild_id=guild_id)
            faqs = await asyncio.to_thread(faq_mgr.list_faqs)

            if not faqs:
                embed = discord.Embed(
                    title="📋 FAQ Knowledge Base",
                    description="No FAQs found for this server.",
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Use /faq_add to create your first FAQ")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build paginated embed response
            embed = discord.Embed(
                title="📋 FAQ Knowledge Base",
                description=f"Currently tracking **{len(faqs)}** FAQ(s) for this server",
                color=discord.Color.blue(),
            )

            # Add FAQs as fields (max 25 fields per embed)
            for idx, faq in enumerate(faqs[:25], 1):  # Discord limit
                question = faq.get("question", "N/A")
                answer = faq.get("answer", "N/A")
                added_by = faq.get("added_by", "unknown")
                faq_id = faq.get("id", "unknown")

                # Truncate long answers for display
                if len(answer) > 150:
                    answer = answer[:147] + "..."

                field_value = f"**A:** {answer}\\n" f"*Added by {added_by}*\\n" f"ID: `{faq_id}`"

                # Truncate field value if too long (1024 char limit)
                if len(field_value) > 1024:
                    field_value = field_value[:1021] + "..."

                embed.add_field(name=f"{idx}. {question[:100]}", value=field_value, inline=False)

            if len(faqs) > 25:
                embed.set_footer(
                    text=f"Showing first 25 of {len(faqs)} FAQs. " f"Contact admin for full list."
                )
            else:
                embed.set_footer(text="Use /faq_add or /faq_remove to modify")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error listing FAQs: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error listing FAQs: {e!s}", ephemeral=True)

    @client.tree.command(
        name="faq_add",
        description="Add FAQ to knowledge base",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_add(interaction: discord.Interaction):
        """Open modal for admins to add validated FAQ entries."""
        log_command(interaction, "faq_add")

        if not interaction.guild_id:
            await interaction.response.send_message(
                "❌ This command can only be used in a server", ephemeral=True
            )
            return

        # Create and configure modal
        from admin_faq_modal import AdminFAQModal

        modal = AdminFAQModal()
        modal.set_guild_id(interaction.guild_id)

        # Send modal to user
        await interaction.response.send_modal(modal)

    @client.tree.command(
        name="faq_remove",
        description="Remove FAQ from knowledge base",
        guilds=const.DEV_GUILD_IDS,
    )
    @app_commands.describe(faq_id="The FAQ ID to remove (use /faq_list to see IDs)")
    @app_commands.checks.has_permissions(administrator=True)
    async def faq_remove(interaction: discord.Interaction, faq_id: str):
        """Remove FAQ from guild's vector store."""
        log_command(interaction, "faq_remove", faq_id=faq_id)
        await interaction.response.defer(ephemeral=True)

        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Remove FAQ
            from faq_manager import FAQManager

            faq_mgr = FAQManager(guild_id=guild_id)
            success = await asyncio.to_thread(faq_mgr.remove_faq, faq_id)

            if success:
                embed = discord.Embed(
                    title="✅ FAQ Removed",
                    description="Successfully removed FAQ from knowledge base",
                    color=discord.Color.green(),
                )
                embed.add_field(name="FAQ ID", value=f"`{faq_id}`", inline=False)
                embed.set_footer(text="Use /faq_list to see remaining FAQs")
                await interaction.followup.send(embed=embed, ephemeral=True)

                logger.info(
                    f"FAQ removed by {interaction.user.name}: {faq_id} " f"from guild {guild_id}"
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove FAQ `{faq_id}`.\\n"
                    f"It may not exist or there was an error.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error removing FAQ {faq_id}: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error removing FAQ: {e!s}", ephemeral=True)

    # Run it
    if not const.TOKEN:
        logger.error("DISCORD_TOKEN environment variable not set")
        raise ValueError("DISCORD_TOKEN environment variable is required")

    logger.info("Starting Discord bot")
    client.run(const.TOKEN)


if __name__ == "__main__":
    main()
