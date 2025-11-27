#!/usr/bin/env python3
"""
Migration Script: Seed System Settings from Constants

This script migrates configuration values from constants.py (and .env)
into the system_settings database table. This enables runtime configuration
changes without code modifications.

Usage:
    python scripts/migrate_settings_to_db.py [--dry-run]

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import argparse
import logging
from db import Db
from system_settings import get_settings
import constants as const

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# Settings to migrate from .env to database
# Format: (key_constant, default_value, category, description)
# Note: These are initial default values since constants.py no longer has setting values
SETTINGS_TO_MIGRATE = [
    # LLM Configuration
    (const.SETTING_OLLAMA_BASE_URL, 'http://jedi.local:11434', 'llm',
     'Ollama server endpoint for local LLM inference'),

    (const.SETTING_DEFAULT_LLM_MODEL, 'ollama-qwen-32b', 'llm',
     'Default LLM model for general analysis and queries'),

    (const.SETTING_TRADE_PARSING_MODEL, 'ollama/qwen2.5-coder:7b', 'llm',
     'LLM model for trade parsing from text/images'),

    (const.SETTING_TRADE_PARSING_API_BASE, 'http://jedi.local:11434', 'llm',
     'API endpoint for trade parsing model'),

    (const.SETTING_TRADE_PARSING_TEMPERATURE, 0.0, 'llm',
     'Temperature for trade parsing (0.0 = deterministic)'),

    (const.SETTING_VISION_OCR_MODEL, 'claude-3-5-haiku-20241022', 'llm',
     'Vision model for OCR and image analysis'),

    (const.SETTING_VISION_API_BASE, '', 'llm',
     'API endpoint for vision model (empty = default Anthropic)'),

    (const.SETTING_SENTIMENT_MODEL, 'ollama/gemma2:9b', 'llm',
     'Primary model for sentiment analysis'),

    (const.SETTING_SENTIMENT_FALLBACK_MODEL, 'claude-sonnet-4-5-20250929', 'llm',
     'Fallback model for critical sentiment analysis'),

    (const.SETTING_SENTIMENT_API_BASE, 'http://jedi.local:11434', 'llm',
     'API endpoint for sentiment model'),

    (const.SETTING_AI_TUTOR_MODEL, 'claude-sonnet', 'llm',
     'LLM model for AI tutor (RAG-enhanced educational responses)'),

    # Feature Flags
    (const.SETTING_IMAGE_ANALYSIS_ENABLED, True, 'features',
     'Enable automatic trade parsing from images'),

    (const.SETTING_SENTIMENT_ANALYSIS_ENABLED, False, 'features',
     'Enable automatic sentiment analysis of messages'),

    # Market Data
    (const.SETTING_MARKET_DATA_PROVIDER, 'yfinance', 'market',
     'Primary market data provider (yfinance, finnhub, alphavantage)'),

    # MCP Server URLs
    (const.SETTING_TRADING_MCP_URL, 'http://localhost:8000', 'mcp',
     'Trading MCP server URL (all trading, market data, technical analysis tools)'),

    # Vision Processing Configuration
    (const.SETTING_IMAGE_ANALYSIS_USE_QUEUE, True, 'vision',
     'Use async queue for non-blocking image processing (recommended)'),

    (const.SETTING_VISION_TIMEOUT_SECONDS, 60, 'vision',
     'Timeout for vision inference (seconds)'),

    (const.SETTING_VISION_USE_DIRECT_JSON, True, 'vision',
     'Use direct vision-to-JSON pipeline vs OCR+Parser'),

    (const.SETTING_VISION_MAX_IMAGES_PER_MESSAGE, 3, 'vision',
     'Maximum images to process per message (performance limit)'),

    (const.SETTING_VISION_QUEUE_SIZE, 500, 'vision',
     'Maximum messages in async processing queue'),

    (const.SETTING_VISION_WORKER_COUNT, 1, 'vision',
     'Number of async workers (1 recommended for serial GPU processing)'),

    # Trade Parsing Configuration
    (const.SETTING_TRADE_PARSING_TIMEOUT_SECONDS, 30, 'trade_parsing',
     'Timeout for trade parsing inference (seconds)'),

    # Sentiment Analysis Configuration
    (const.SETTING_SENTIMENT_ANALYSIS_USE_QUEUE, False, 'sentiment',
     'Use async queue for non-blocking sentiment processing'),

    (const.SETTING_SENTIMENT_TIMEOUT_SECONDS, 30, 'sentiment',
     'Timeout for sentiment inference (seconds)'),

    (const.SETTING_SENTIMENT_QUEUE_SIZE, 1000, 'sentiment',
     'Maximum messages in async processing queue'),

    (const.SETTING_SENTIMENT_WORKER_COUNT, 1, 'sentiment',
     'Number of async workers (1 recommended for serial GPU processing)'),
]


def migrate_settings(dry_run: bool = False):
    """
    Migrate settings from constants to database.

    Args:
        dry_run: If True, only show what would be migrated without making changes
    """
    db = Db(in_memory=False)
    settings = get_settings(db)

    logger.info("=" * 80)
    logger.info("System Settings Migration")
    logger.info("=" * 80)
    logger.info("")

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        logger.info("")

    migrated = 0
    skipped = 0

    for key, value, category, description in SETTINGS_TO_MIGRATE:
        # Check if setting already exists
        existing = settings.get(key)

        if existing is not None:
            logger.info(f"⏭️  SKIP: {key}")
            logger.info(f"   Reason: Already exists (value: {existing})")
            skipped += 1
        else:
            if dry_run:
                logger.info(f"📝 WOULD ADD: {key}")
            else:
                logger.info(f"✓ ADDING: {key}")

            logger.info(f"   Category: {category}")
            logger.info(f"   Value: {value}")
            logger.info(f"   Type: {type(value).__name__}")
            logger.info(f"   Description: {description}")

            if not dry_run:
                settings.set(
                    key=key,
                    value=value,
                    username='migration',
                    category=category,
                    description=description
                )

            migrated += 1

        logger.info("")

    logger.info("=" * 80)
    logger.info("Migration Summary")
    logger.info("=" * 80)
    logger.info(f"Settings added: {migrated}")
    logger.info(f"Settings skipped: {skipped}")
    logger.info(f"Total settings: {migrated + skipped}")
    logger.info("")

    if dry_run:
        logger.info("This was a DRY RUN - no changes were made")
        logger.info("Run without --dry-run to apply changes")
    else:
        logger.info("✓ Migration complete!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. View settings: python src/cli.py admin settings-list")
        logger.info("  2. Update a setting: python src/cli.py admin settings-set --key <key> --value <value>")
        logger.info("  3. Export backup: python src/cli.py admin settings-export --output settings_backup.json")

    logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description='Migrate configuration settings from constants.py to database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without making changes'
    )

    args = parser.parse_args()

    try:
        migrate_settings(dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
