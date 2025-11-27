#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalize Channel Names Migration Script

Removes emoji prefixes/suffixes from channel names in harvested_messages table
to make CLI usage easier and more consistent.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import logging
from db import Db
import util

# Setup logging
util.setup_logger(name=None, level='INFO', console=True)
logger = logging.getLogger(__name__)


def normalize_existing_channel_names(db: Db, dry_run: bool = True) -> None:
    """
    Normalize channel names in harvested_messages table.

    Args:
        db: Database instance
        dry_run: If True, only show what would be changed without modifying data
    """
    # Get all unique channel names
    query = """
    SELECT DISTINCT channel_name, COUNT(*) as message_count
    FROM harvested_messages
    GROUP BY channel_name
    ORDER BY message_count DESC
    """

    results = db.query_parameterized(query)

    if not results:
        logger.info("No channel names found in harvested_messages table")
        return

    logger.info(f"Found {len(results)} unique channel names")
    logger.info("=" * 80)

    changes = []
    unchanged = []

    for row in results:
        original_name = row[0]
        message_count = row[1]
        normalized_name = util.normalize_channel_name(original_name)

        if original_name != normalized_name:
            changes.append((original_name, normalized_name, message_count))
            logger.info(f"CHANGE: '{original_name}' → '{normalized_name}' ({message_count} messages)")
        else:
            unchanged.append((original_name, message_count))
            logger.debug(f"OK: '{original_name}' ({message_count} messages)")

    logger.info("=" * 80)
    logger.info(f"Summary: {len(changes)} channel names need normalization, {len(unchanged)} already normalized")

    if not changes:
        logger.info("✓ All channel names are already normalized. No migration needed.")
        return

    if dry_run:
        logger.info("")
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - No changes made to database")
        logger.info("To apply changes, run with --apply flag")
        logger.info("=" * 80)
        return

    # Apply changes
    logger.info("")
    logger.info("Applying normalization changes...")

    update_query = """
    UPDATE harvested_messages
    SET channel_name = ?
    WHERE channel_name = ?
    """

    total_messages_updated = 0
    for original_name, normalized_name, message_count in changes:
        try:
            db.execute(update_query, (normalized_name, original_name))
            db.connection.commit()
            total_messages_updated += message_count
            logger.info(f"✓ Updated '{original_name}' → '{normalized_name}' ({message_count} messages)")
        except Exception as e:
            logger.error(f"✗ Failed to update '{original_name}': {e}")
            db.connection.rollback()

    logger.info("=" * 80)
    logger.info(f"✓ Migration complete: {len(changes)} channel names normalized, {total_messages_updated} messages updated")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize channel names in harvested_messages (remove emoji prefixes/suffixes)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show what would be changed (dry run)
  python scripts/normalize_channel_names.py

  # Apply the changes
  python scripts/normalize_channel_names.py --apply

This script will normalize channel names like:
  '💰stock-talk-options' → 'stock-talk-options'
  '💲darkminer-moves' → 'darkminer-moves'
  'news💰' → 'news'
        """
    )

    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes to database (default is dry run)'
    )

    args = parser.parse_args()

    logger.info("Channel Name Normalization Migration")
    logger.info("=" * 80)

    if not args.apply:
        logger.info("Running in DRY RUN mode (no changes will be made)")
        logger.info("Use --apply flag to actually modify the database")
    else:
        logger.warning("APPLYING CHANGES to database")

    logger.info("")

    # Initialize database
    db = Db(in_memory=False)

    # Run migration
    normalize_existing_channel_names(db, dry_run=not args.apply)


if __name__ == "__main__":
    main()
