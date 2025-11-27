#!/usr/bin/env python3
"""
Generate historical digests for manual review.

This script generates 7-day rolling window digests for each day starting from
a specified date, allowing manual review of digest quality across different
time periods and data volumes.

Usage:
    python scripts/generate_historical_digests.py --start-date 2025-10-15 --end-date 2025-11-01
    python scripts/generate_historical_digests.py --start-date 2025-10-15  # defaults to today

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
sys.path.insert(0, 'src')

import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional
from db import Db
from daily_digest import DailyDigest
import constants as const

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_historical_digests(
    start_date: datetime,
    end_date: datetime,
    guild_id: Optional[int] = None,
    enable_llm: bool = True,
    save_files: bool = True
):
    """
    Generate digests for each day in the date range.

    Args:
        start_date: First date to generate digest for
        end_date: Last date to generate digest for (inclusive)
        guild_id: Guild ID (defaults to first guild in config)
        enable_llm: Whether to use LLM for narratives
        save_files: Whether to save markdown/PDF files
    """
    db = Db()

    if not guild_id:
        guild_id = const.GUILDS[0] if const.GUILDS else None
        if not guild_id:
            logger.error("No guild_id specified and no guilds in config")
            return

    logger.info("=" * 80)
    logger.info("HISTORICAL DIGEST GENERATION")
    logger.info("=" * 80)
    logger.info(f"Guild ID: {guild_id}")
    logger.info(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"LLM Enabled: {enable_llm}")
    logger.info(f"Save Files: {save_files}")
    logger.info("=" * 80)
    logger.info("")

    # Initialize digest generator
    digest_gen = DailyDigest(
        db=db,
        guild_id=guild_id,
        enable_llm=enable_llm,
        llm_temperature=1.0
    )

    # Generate digest for each day
    current_date = start_date
    total_days = (end_date - start_date).days + 1
    successful = 0
    failed = 0
    errors = []

    while current_date <= end_date:
        day_num = (current_date - start_date).days + 1
        date_str = current_date.strftime('%Y-%m-%d')

        try:
            logger.info(f"[{day_num}/{total_days}] Generating digest for {date_str}...")

            # Generate digest
            digest_content = digest_gen.generate_digest(current_date)

            if save_files:
                # Save as markdown
                md_path = digest_gen.save_digest(
                    digest_text=digest_content,
                    date=current_date
                )
                logger.info(f"  ✓ Saved: {md_path}")
            else:
                # Just display
                logger.info(f"  ✓ Generated ({len(digest_content)} chars)")
                logger.info("")
                logger.info("-" * 80)
                logger.info(digest_content[:500] + "..." if len(digest_content) > 500 else digest_content)
                logger.info("-" * 80)
                logger.info("")

            successful += 1

        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            failed += 1
            errors.append({
                'date': date_str,
                'error': str(e)
            })

        # Move to next day
        current_date += timedelta(days=1)
        logger.info("")

    # Summary
    logger.info("=" * 80)
    logger.info("GENERATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total Days: {total_days}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")

    if errors:
        logger.info("")
        logger.info("Errors:")
        for err in errors:
            logger.info(f"  - {err['date']}: {err['error']}")

    if save_files and successful > 0:
        logger.info("")
        logger.info(f"Digests saved in: {const.DAILY_DIGEST_DIR}/guild_{guild_id}/")

    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Generate historical digests for manual review'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2025-10-15',
        help='Start date (YYYY-MM-DD) - default: 2025-10-15'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        default=None,
        help='End date (YYYY-MM-DD) - default: today'
    )
    parser.add_argument(
        '--guild-id',
        type=int,
        default=None,
        help='Guild ID - default: first guild in config'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM narratives (text-only summaries)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Don\'t save files (just display to console)'
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')

    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    # Validate date range
    if start_date > end_date:
        logger.error(f"Start date ({start_date}) is after end date ({end_date})")
        sys.exit(1)

    # Generate digests
    generate_historical_digests(
        start_date=start_date,
        end_date=end_date,
        guild_id=args.guild_id,
        enable_llm=not args.no_llm,
        save_files=not args.no_save
    )


if __name__ == '__main__':
    main()
