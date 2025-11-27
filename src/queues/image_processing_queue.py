"""
Image Processing Queue - Async background processing for vision analysis

Provides non-blocking queue-based architecture for extracting structured data
from Discord message images using vision models (Claude, GPT-4V, Ollama/LLaVA).

Key Design:
- Non-blocking enqueue (< 1ms overhead on message handler)
- Background worker pool processes images asynchronously
- Provider abstraction supports multiple vision models
- Graceful error handling and queue overflow protection
- Expandable to other analysis types (sentiment, translation, etc.)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import constants as const
from db import Db
from messages import Messages
from messages_async import MessagesAsync
from vision_strategy import analyze_text_trades, analyze_trading_image, analyze_trading_image_direct
from vision_test_corpus import VisionTestCorpus


logger = logging.getLogger(__name__)


def _deduplicate_trades(trades_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Deduplicate trades from text and image sources

    Two trades are considered duplicates if they match on:
    - ticker (must match)
    - operation (must match)
    - option_type (must match)
    - strike (within $0.01)
    - expiration (must match)
    - quantity (must match)

    When duplicates found:
    - Keep the trade with more complete data (fewer 0.0/null/empty values)
    - If equal completeness, prefer image source (more accurate)

    Args:
        trades_list: List of trade dicts

    Returns:
        Deduplicated list of trades
    """
    if not trades_list or len(trades_list) <= 1:
        return trades_list

    def trade_key(trade: dict) -> tuple:
        """Create comparison key for trade"""
        return (
            str(trade.get("ticker", "")).upper(),
            str(trade.get("operation", "")).upper(),
            str(trade.get("option_type", "")).upper(),
            round(float(trade.get("strike", 0.0)), 2),  # Round to cents
            str(trade.get("expiration", "")),
            int(trade.get("quantity", 0))
        )

    def trade_completeness(trade: dict) -> int:
        """Score trade by completeness (higher = more complete)"""
        score = 0

        # Check each field
        if trade.get("ticker"):
            score += 1
        if trade.get("operation"):
            score += 1
        if trade.get("option_type"):
            score += 1
        if trade.get("strike", 0.0) > 0.0:
            score += 2  # Strike is critical
        if trade.get("expiration"):
            score += 2  # Expiration is critical
        if trade.get("quantity", 0) > 0:
            score += 1
        if trade.get("premium", 0.0) > 0.0:
            score += 1

        # Bonus for image source (more accurate)
        if trade.get("source") == "image":
            score += 1

        return score

    # Group trades by key
    trade_groups: dict[tuple, list[dict]] = {}
    for trade in trades_list:
        key = trade_key(trade)
        if key not in trade_groups:
            trade_groups[key] = []
        trade_groups[key].append(trade)

    # For each group, keep the most complete trade
    deduplicated = []
    for key, group in trade_groups.items():
        if len(group) == 1:
            deduplicated.append(group[0])
        else:
            # Multiple trades with same key - keep most complete
            best_trade = max(group, key=trade_completeness)
            deduplicated.append(best_trade)

            logger.debug(f"Deduplicated {len(group)} trades for {key[0]}: kept {best_trade.get('source', 'unknown')} source")

    return deduplicated


class ImageProcessingQueue:
    """
    Async queue for processing Discord message images with vision models.

    Supports multiple vision providers:
    - claude-sonnet-4-5-20250929 (Anthropic API, excellent OCR, $0.003/image)
    - gpt-4o (OpenAI API, good OCR)
    - ollama/llava:13b (self-hosted, free but slower)

    Architecture:
    1. Messages enqueued with put_nowait() (non-blocking)
    2. Worker pool pulls from queue and processes async
    3. vision_strategy handles OCR + parsing pipeline
    4. Results written back to database
    5. Stats tracked for monitoring
    """

    def __init__(
        self,
        db: Db,
        model: str,
        worker_count: int = 1,
        queue_size: int = 500,
        on_complete_callback: Callable | None = None
    ):
        """
        Initialize image processing queue

        Args:
            db: Database instance
            model: Vision model name (REQUIRED)
                  Examples: "claude-sonnet-4-5-20250929", "ollama/llava:13b"
            worker_count: Number of async workers (default: 1)
            queue_size: Max queue capacity (default: 500)
            on_complete_callback: Optional async callback(message_id: int) triggered
                                 after successful vision OCR completion
        """
        self.db = db
        self.messages_db = Messages(db)
        self.messages_async = MessagesAsync(self.messages_db)
        self.model = model
        self.worker_count = worker_count
        self.queue_size = queue_size
        self.on_complete_callback = on_complete_callback

        # Create async queue (FIFO)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

        # Initialize test corpus manager
        self.corpus = VisionTestCorpus()

        # Worker tasks
        self.workers: list[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()

        # Statistics
        self.stats: dict[str, Any] = {
            "enqueued": 0,
            "processed": 0,
            "failed": 0,
            "dropped": 0,  # Queue full
            "total_time": 0.0,
            "started_at": None
        }

        logger.info(
            f"ImageProcessingQueue initialized: "
            f"model={self.model}, workers={worker_count}, queue_size={queue_size}"
        )

    async def start_workers(self) -> None:
        """
        Start background worker tasks

        Creates N async tasks that pull from queue and process images.
        Workers run until shutdown_event is set.
        """
        if self.workers:
            logger.warning("Workers already started")
            return

        self.stats["started_at"] = datetime.now()

        for worker_id in range(self.worker_count):
            task = asyncio.create_task(self._worker(worker_id))
            self.workers.append(task)

        logger.info(f"Started {self.worker_count} image processing worker(s)")

    async def stop_workers(self) -> None:
        """
        Gracefully stop all workers

        Sets shutdown event, waits for workers to finish current tasks,
        then cancels any remaining work.
        """
        if not self.workers:
            logger.warning("No workers to stop")
            return

        logger.info("Stopping image processing workers...")

        # Signal shutdown
        self.shutdown_event.set()

        # Wait for workers to finish current tasks (max 60s)
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.workers, return_exceptions=True),
                timeout=60.0
            )
            logger.info("All workers stopped gracefully")
        except asyncio.TimeoutError:
            logger.warning("Workers did not stop in time, cancelling...")
            for task in self.workers:
                task.cancel()

        self.workers.clear()

    async def enqueue_message(
        self,
        message_id: int,
        image_urls: list[str],
        message_content: str = "",
        guild_id: int | None = None
    ) -> bool:
        """
        Enqueue a message for trade parsing analysis (text + images, non-blocking)

        Args:
            message_id: Discord message ID
            image_urls: List of Discord CDN image URLs
            message_content: Message text content for text-based trade parsing
            guild_id: Discord guild ID (for corpus filtering)

        Returns:
            True if enqueued, False if queue full (will be batched later)
        """
        try:
            # Non-blocking put (raises QueueFull if full)
            self.queue.put_nowait({
                "message_id": message_id,
                "image_urls": image_urls,
                "message_content": message_content,
                "guild_id": guild_id,
                "enqueued_at": time.time()
            })

            self.stats["enqueued"] += 1

            # Log queue depth periodically (every 10th message)
            if self.stats["enqueued"] % 10 == 0:
                depth = self.queue.qsize()
                logger.debug(f"Queue depth: {depth}/{self.queue_size}")

            return True

        except asyncio.QueueFull:
            self.stats["dropped"] += 1
            logger.warning(
                f"Queue full ({self.queue_size}) - dropped message {message_id} "
                f"(will be processed by batch job)"
            )
            return False

    async def _worker(self, worker_id: int) -> None:
        """
        Background worker that processes images from queue

        Args:
            worker_id: Worker identifier (0, 1, 2, ...)
        """
        logger.info(f"Worker {worker_id} started")

        while not self.shutdown_event.is_set():
            try:
                # Wait for item from queue (with timeout to check shutdown)
                try:
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No items in queue, check if shutting down
                    continue

                message_id = item["message_id"]
                image_urls = item["image_urls"]
                message_content = item.get("message_content", "")
                guild_id = item.get("guild_id")
                enqueued_at = item["enqueued_at"]

                # Calculate queue wait time
                wait_time = time.time() - enqueued_at

                has_images = bool(image_urls)
                has_text = bool(message_content and len(message_content.strip()) >= 10)

                logger.debug(
                    f"Worker {worker_id} processing message {message_id} "
                    f"({len(image_urls)} images, text={'yes' if has_text else 'no'}, waited {wait_time:.1f}s in queue)"
                )

                # Process trades from both text and images
                start_time = time.time()

                try:
                    text_data = None
                    image_data = None

                    # Step 1: Parse text-based trades if present
                    if has_text:
                        text_data = await analyze_text_trades(message_content)
                        logger.debug(f"Text parsing: {len(text_data.get('trades', []))} trades found")

                    # Step 2: Parse image-based trades if present
                    if has_images:
                        # Use direct vision-to-JSON or OCR+Parser based on config
                        if const.VISION_USE_DIRECT_JSON:
                            image_data = await analyze_trading_image_direct(
                                image_urls[0],
                                message_content,
                                ocr_model=self.model
                            )
                            logger.debug(f"Image parsing (direct): {len(image_data.get('trades', []))} trades found")
                        else:
                            image_data = await analyze_trading_image(image_urls[0], ocr_model=self.model)
                            logger.debug(f"Image parsing (OCR+Parser): {len(image_data.get('trades', []))} trades found")

                    # Step 3: Merge and deduplicate results
                    if text_data and image_data:
                        # Both sources - merge and deduplicate trades
                        all_trades = text_data.get("trades", []) + image_data.get("trades", [])
                        deduplicated_trades = _deduplicate_trades(all_trades)

                        extracted_data = image_data.copy()
                        extracted_data["trades"] = deduplicated_trades
                        extracted_data["tickers"] = list(set(text_data.get("tickers", []) + image_data.get("tickers", [])))
                        extracted_data["raw_text"] = f"{message_content}\n\n--- IMAGE DATA ---\n\n{image_data.get('raw_text', '')}"

                        logger.info(
                            f"Merged text ({len(text_data.get('trades', []))}) + "
                            f"image ({len(image_data.get('trades', []))}) = "
                            f"{len(all_trades)} trades, deduplicated to {len(deduplicated_trades)}"
                        )
                    elif text_data:
                        # Text only
                        extracted_data = text_data
                    elif image_data:
                        # Image only (existing behavior)
                        extracted_data = image_data
                    else:
                        extracted_data = None

                    # Update database with extracted data (async to prevent blocking)
                    if extracted_data:
                        success = await self.messages_async.update_extracted_data(
                            message_id,
                            extracted_data
                        )

                        if success:
                            elapsed = time.time() - start_time
                            self.stats["processed"] += 1
                            self.stats["total_time"] += elapsed

                            # Log extracted info
                            image_type = extracted_data.get("image_type", "unknown")
                            ticker_count = len(extracted_data.get("tickers", []))

                            logger.info(
                                f"Worker {worker_id} completed message {message_id} "
                                f"in {elapsed:.1f}s (type={image_type}, tickers={ticker_count})"
                            )

                            # Save to test corpus if enabled and from target guild
                            if has_images and image_type == "trade_execution":
                                try:
                                    # Get message metadata for corpus
                                    corpus_metadata = {
                                        "timestamp": datetime.now().isoformat(),
                                        "username": None,  # Not available in queue context
                                        "channel": None,   # Not available in queue context
                                        "guild_id": guild_id,
                                        "content": message_content,
                                        "image_type": image_type,
                                        "trades": extracted_data.get("trades", []),
                                        "model_used": self.model,
                                        "processing_time_ms": int(elapsed * 1000)
                                    }
                                    await self.corpus.save_image(message_id, image_urls[0], corpus_metadata, guild_id)
                                except Exception as e:
                                    logger.debug(f"Failed to save to corpus (non-critical): {e}")

                            # Update tickers now that vision extraction is complete
                            # This extracts tickers from ALL message data (content + extracted_data)
                            try:
                                await self.messages_async.update_tickers(message_id)
                                logger.debug(f"Updated tickers for message {message_id} after vision extraction")
                            except Exception as e:
                                logger.error(f"Failed to update tickers for message {message_id}: {e}", exc_info=True)

                            # Trigger callback (e.g., enqueue for sentiment analysis)
                            if self.on_complete_callback:
                                try:
                                    await self.on_complete_callback(message_id)
                                    logger.debug(f"Triggered completion callback for message {message_id}")
                                except Exception as e:
                                    logger.error(f"Callback error for message {message_id}: {e}", exc_info=True)
                        else:
                            logger.error(f"Failed to update database for message {message_id}")
                            self.stats["failed"] += 1
                    else:
                        logger.warning(f"No extracted data for message {message_id}")
                        self.stats["failed"] += 1

                except Exception as e:
                    self.stats["failed"] += 1
                    logger.error(
                        f"Worker {worker_id} error processing message {message_id}: {e}",
                        exc_info=True
                    )

                finally:
                    # Mark task as done
                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Worker {worker_id} unexpected error: {e}", exc_info=True)
                # Continue running (don't crash worker)

        logger.info(f"Worker {worker_id} stopped")

    def get_stats(self) -> dict[str, Any]:
        """
        Get queue processing statistics

        Returns:
            Dictionary with stats:
            - enqueued: Total messages enqueued
            - processed: Successfully processed
            - failed: Failed to process
            - dropped: Dropped due to queue full
            - queue_depth: Current queue size
            - avg_time: Average processing time per image
            - uptime: Time since workers started
        """
        stats = self.stats.copy()
        stats["queue_depth"] = self.queue.qsize()

        if stats["processed"] > 0:
            stats["avg_time"] = stats["total_time"] / stats["processed"]
        else:
            stats["avg_time"] = 0.0

        if stats["started_at"]:
            uptime = (datetime.now() - stats["started_at"]).total_seconds()
            stats["uptime"] = uptime
        else:
            stats["uptime"] = 0.0

        return stats

    def log_stats(self) -> None:
        """Log current queue statistics"""
        stats = self.get_stats()

        logger.info(
            f"Image Queue Stats: "
            f"enqueued={stats['enqueued']}, "
            f"processed={stats['processed']}, "
            f"failed={stats['failed']}, "
            f"dropped={stats['dropped']}, "
            f"queue_depth={stats['queue_depth']}/{self.queue_size}, "
            f"avg_time={stats['avg_time']:.1f}s, "
            f"uptime={stats['uptime']:.0f}s"
        )
