"""
Sentiment Processing Queue

Async queue-based sentiment analysis for Discord messages.
Processes messages in background without blocking the bot.

Architecture:
- Event-driven: Triggered by vision OCR completion callback for images
- Immediate processing: Text-only messages processed instantly
- Database coordination: Uses extracted_data field to ensure vision OCR complete

Performance:
- Gemma 2 9B: ~2.0s per message (100% per-ticker accuracy)
- Worker count: 1 (serial GPU processing)
- Queue size: 1000 messages

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import logging
import time
from typing import Any

import constants as const
from db import Db
from messages import Messages
from sentiment_analyzer import SentimentAnalyzer


logger = logging.getLogger(__name__)


class SentimentProcessingQueue:
    """
    Async queue for processing message sentiment analysis.

    Similar to ImageProcessingQueue but for sentiment analysis.
    Coordinates with vision OCR to ensure extracted_data is available.
    """

    def __init__(
        self,
        db: Db,
        model: str | None = None,
        worker_count: int = 1,
        queue_size: int = 1000
    ):
        """
        Initialize sentiment processing queue.

        Args:
            db: Database instance (Messages wrapper)
            model: Sentiment model to use (default: const.SENTIMENT_MODEL)
            worker_count: Number of async workers (default: 1)
            queue_size: Max queue size (default: 1000)
        """
        self.messages_db = db if isinstance(db, Messages) else Messages(db)
        self.model = model or const.SENTIMENT_MODEL
        self.worker_count = worker_count
        self.queue_size = queue_size

        # Initialize sentiment analyzer
        self.analyzer = SentimentAnalyzer(model=self.model)

        # Create async queue (FIFO)
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

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
            f"SentimentProcessingQueue initialized: "
            f"model={self.model}, workers={worker_count}, queue_size={queue_size}"
        )

    async def start_workers(self) -> None:
        """
        Start background worker tasks.

        Creates N async tasks that pull from queue and analyze sentiment.
        Workers run until shutdown_event is set.
        """
        if self.workers:
            logger.warning("Workers already started")
            return

        self.stats["started_at"] = time.time()

        for i in range(self.worker_count):
            task = asyncio.create_task(self._worker(i))
            self.workers.append(task)

        logger.info(f"Started {self.worker_count} sentiment workers")

    async def stop_workers(self) -> None:
        """
        Stop all worker tasks gracefully.

        Sets shutdown event and waits for workers to finish.
        """
        if not self.workers:
            logger.warning("No workers to stop")
            return

        logger.info("Stopping sentiment workers...")
        self.shutdown_event.set()

        # Wait for workers to finish (with timeout)
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

    async def enqueue_message(self, message_id: int) -> bool:
        """
        Enqueue a message for sentiment analysis (non-blocking).

        Args:
            message_id: Discord message ID

        Returns:
            True if enqueued, False if queue full
        """
        try:
            # Non-blocking put (raises QueueFull if full)
            self.queue.put_nowait({
                "message_id": message_id,
                "enqueued_at": time.time()
            })

            self.stats["enqueued"] += 1

            # Log queue depth periodically (every 10th message)
            if self.stats["enqueued"] % 10 == 0:
                depth = self.queue.qsize()
                logger.debug(f"Sentiment queue depth: {depth}/{self.queue_size}")

            return True

        except asyncio.QueueFull:
            self.stats["dropped"] += 1
            logger.warning(
                f"Sentiment queue full ({self.queue_size}) - dropped message {message_id} "
                f"(will be processed by batch job)"
            )
            return False

    async def _worker(self, worker_id: int) -> None:
        """
        Background worker that processes sentiment from queue.

        Args:
            worker_id: Worker identifier (0, 1, 2, ...)
        """
        logger.info(f"Sentiment worker {worker_id} started")

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
                enqueued_at = item["enqueued_at"]

                # Calculate queue wait time
                wait_time = time.time() - enqueued_at

                logger.debug(
                    f"Sentiment worker {worker_id} processing message {message_id} "
                    f"(waited {wait_time:.1f}s in queue)"
                )

                # Process sentiment
                start_time = time.time()

                try:
                    # Fetch message from database
                    msg = self.messages_db.get_message(message_id)

                    if not msg:
                        logger.error(f"Message {message_id} not found in database")
                        self.stats["failed"] += 1
                        continue

                    # Analyze sentiment (with extracted OCR text if available)
                    image_text = None
                    if msg.extracted_data:
                        import json
                        data = json.loads(msg.extracted_data) if isinstance(msg.extracted_data, str) else msg.extracted_data
                        image_text = data.get("raw_text")

                    result = await self.analyzer.analyze_sentiment(
                        message_text=msg.content,
                        image_data=image_text  # OCR text from extracted_data
                    )

                    # Update database with sentiment results (NO TICKERS - they're hallucinated)
                    success = self.messages_db.update_sentiment(
                        message_id,
                        sentiment=result["sentiment"],
                        confidence=result["confidence"],
                        reasoning=result["reasoning"]
                    )

                    if success:
                        elapsed = time.time() - start_time
                        self.stats["processed"] += 1
                        self.stats["total_time"] += elapsed

                        # Update tickers now that sentiment analysis is complete
                        # This extracts tickers from ALL message data (not LLM output)
                        try:
                            self.messages_db.update_tickers(message_id)
                            logger.debug(f"Updated tickers for message {message_id} after sentiment analysis")
                        except Exception as e:
                            logger.error(f"Failed to update tickers for message {message_id}: {e}", exc_info=True)

                        # Log result (don't trust LLM ticker count)
                        logger.info(
                            f"Sentiment worker {worker_id} completed message {message_id} "
                            f"in {elapsed:.1f}s (sentiment={result['sentiment']}, "
                            f"confidence={result['confidence']:.2f})"
                        )
                    else:
                        logger.error(f"Failed to update database for message {message_id}")
                        self.stats["failed"] += 1

                except Exception as e:
                    self.stats["failed"] += 1
                    logger.error(
                        f"Sentiment worker {worker_id} error processing message {message_id}: {e}",
                        exc_info=True
                    )

                finally:
                    # Mark task as done
                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Sentiment worker {worker_id} unexpected error: {e}", exc_info=True)

        logger.info(f"Sentiment worker {worker_id} stopped")

    def get_stats(self) -> dict[str, Any]:
        """
        Get queue statistics.

        Returns:
            Dict with processing statistics
        """
        stats = self.stats.copy()
        stats["queue_depth"] = self.queue.qsize()
        stats["workers_active"] = len(self.workers)

        if stats["processed"] > 0:
            stats["avg_time"] = stats["total_time"] / stats["processed"]
        else:
            stats["avg_time"] = 0.0

        if stats["started_at"]:
            stats["uptime"] = time.time() - stats["started_at"]
        else:
            stats["uptime"] = 0.0

        return stats
