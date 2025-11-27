#!/usr/bin/env python3
"""
Generate daily digests for all production guilds.

Loops through all guilds defined in constants.GUILDS and generates
digests with LLM narratives, saving them to organized folders.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os

# Add src to path (go up one level from scripts/ to project root, then to src/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from db import Db
from daily_digest import DailyDigest
import constants as const
import util
import logging

# Setup logging
util.setup_logger(name=None, level='INFO', console=True)
logger = logging.getLogger(__name__)


def main():
    """Generate digests for all production guilds."""

    if not const.GUILDS:
        logger.error("No guilds defined in constants.GUILDS")
        return 1

    logger.info(f"Generating digests for {len(const.GUILDS)} guilds")
    logger.info(f"Guild IDs: {const.GUILDS}")

    db = Db()
    today = datetime.now()
    digest_type = 'weekly' if today.weekday() == 4 else 'daily'

    results = []

    for guild_id in const.GUILDS:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Guild ID: {guild_id}")
        logger.info(f"{'='*60}")

        try:
            # Initialize digest generator for this guild
            digest_gen = DailyDigest(
                db=db,
                guild_id=guild_id,
                enable_llm=True
            )

            # Generate digest
            logger.info(f"Generating {digest_type} digest...")
            digest_text = digest_gen.generate_digest(today)

            # Print digest
            print(f"\n{digest_text}\n")

            # Save digest as Markdown (save_digest only saves markdown)
            logger.info("Saving digest as Markdown...")
            md_path = digest_gen.save_digest(
                digest_text,
                date=today
            )

            # Note: PDF generation would need separate implementation
            logger.info(f"Markdown digest saved to: {md_path}")

            results.append({
                'guild_id': guild_id,
                'status': 'success',
                'md_path': md_path,
                'pdf_path': None  # PDF generation not yet implemented
            })

            logger.info(f"✓ Guild {guild_id} completed successfully")
            logger.info(f"  MD:  {md_path}")

        except Exception as e:
            logger.error(f"✗ Error processing guild {guild_id}: {e}", exc_info=True)
            results.append({
                'guild_id': guild_id,
                'status': 'error',
                'error': str(e)
            })

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'error']

    print(f"\nTotal guilds: {len(const.GUILDS)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        print(f"\n✓ Successfully generated digests for:")
        for result in successful:
            print(f"  - Guild {result['guild_id']}")

    if failed:
        print(f"\n✗ Failed to generate digests for:")
        for result in failed:
            print(f"  - Guild {result['guild_id']}: {result['error']}")

    print(f"\nDigests saved in: {const.DAILY_DIGEST_DIR}/")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
