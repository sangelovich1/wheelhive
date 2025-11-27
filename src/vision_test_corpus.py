"""
Vision Test Corpus Manager

Automatically saves all trading screenshots as they're harvested.
Builds a test dataset for experimenting with OCR and parsing approaches.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

from system_settings import get_settings


logger = logging.getLogger(__name__)


class VisionTestCorpus:
    """
    Manages a test corpus of trading screenshots.

    Saves all images during harvesting to build a dataset for vision model
    testing and improvement. Manual filtering for unique variants done later.
    """

    def __init__(self, corpus_dir: str = "test_corpus/vision"):
        """
        Initialize corpus manager.

        Args:
            corpus_dir: Directory to store corpus files
        """
        self.corpus_dir = corpus_dir
        settings = get_settings()
        self.enabled = settings.get("vision.corpus_enabled", False)

        if self.enabled:
            os.makedirs(corpus_dir, exist_ok=True)
            logger.info(f"Vision test corpus enabled: {corpus_dir}")

    async def save_image(
        self,
        message_id: int,
        image_url: str,
        message_data: dict[str, Any],
        guild_id: int | None = None
    ) -> str | None:
        """
        Download and save image to corpus.

        Args:
            message_id: Discord message ID
            image_url: Image URL
            message_data: Message metadata (content, trades, etc.)
            guild_id: Discord guild ID (for filtering)

        Returns:
            Path to saved image if successful, None if error
        """
        if not self.enabled:
            return None

        # Check guild filter
        settings = get_settings()
        target_guild_id = settings.get("vision.corpus_guild_id")
        if target_guild_id and guild_id != target_guild_id:
            logger.debug(f"Skipping corpus save - guild {guild_id} doesn't match target {target_guild_id}")
            return None

        try:
            # Download image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to download image for corpus: HTTP {response.status}")
                        return None

                    image_data = await response.read()

            # Determine file extension
            ext = Path(image_url.split("?")[0]).suffix or ".png"

            # Save image
            image_path = os.path.join(self.corpus_dir, f"{message_id}{ext}")
            with open(image_path, "wb") as f:
                f.write(image_data)

            # Save metadata
            metadata = {
                "message_id": message_id,
                "timestamp": message_data.get("timestamp"),
                "username": message_data.get("username"),
                "channel": message_data.get("channel"),
                "guild_id": message_data.get("guild_id"),
                "message_content": message_data.get("content"),
                "image_url": image_url,
                "image_type": message_data.get("image_type"),
                "extracted_trades": message_data.get("trades"),
                "model_used": message_data.get("model_used"),
                "processing_time_ms": message_data.get("processing_time_ms"),
                "added_to_corpus": datetime.now().isoformat()
            }

            metadata_path = os.path.join(self.corpus_dir, f"{message_id}.json")
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"✓ Saved image to corpus: {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"Error saving image to corpus: {e}", exc_info=True)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get corpus statistics."""
        if not self.enabled:
            return {"enabled": False}

        # Count files in corpus directory
        image_files = list(Path(self.corpus_dir).glob("*.png")) + list(Path(self.corpus_dir).glob("*.jpg"))
        metadata_files = list(Path(self.corpus_dir).glob("*.json"))

        return {
            "enabled": True,
            "corpus_dir": self.corpus_dir,
            "total_images": len(image_files),
            "total_metadata": len(metadata_files)
        }
