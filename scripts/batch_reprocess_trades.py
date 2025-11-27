#!/usr/bin/env python3
"""
Batch Reprocess Trades: Re-extract trades from harvested messages

Uses the improved trade parser to reprocess all harvested messages
and update their extracted_data with better trade parsing.

Usage:
    # Reprocess all messages with images or text
    python scripts/batch_reprocess_trades.py

    # Reprocess specific guild
    python scripts/batch_reprocess_trades.py --guild-id 123456

    # Dry run (show what would be updated, don't save)
    python scripts/batch_reprocess_trades.py --dry-run

    # Limit to N messages
    python scripts/batch_reprocess_trades.py --limit 100

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
import json
import logging
import argparse
from datetime import datetime
from typing import Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db import Db
from trade_parser import parse_trades_from_text

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_messages_to_reprocess(guild_id: int | None = None, limit: int | None = None):
    """
    Fetch messages that should be reprocessed

    Args:
        guild_id: Optional guild ID filter
        limit: Optional limit on number of messages

    Returns:
        List of message dicts with id, content, extracted_data
    """
    db = Db()
    cursor = db.connection.cursor()

    # Build query
    query = """
        SELECT message_id, guild_id, username, content,
               extracted_data, category, timestamp
        FROM harvested_messages
        WHERE is_deleted = 0
          AND (
              -- Has text content (>=10 chars)
              (content IS NOT NULL AND LENGTH(content) >= 10)
              -- OR has OCR text
              OR (json_extract(extracted_data, '$.raw_text') IS NOT NULL
                  AND LENGTH(json_extract(extracted_data, '$.raw_text')) > 0)
          )
    """

    params = []
    if guild_id:
        query += " AND guild_id = ?"
        params.append(guild_id)

    query += " ORDER BY timestamp DESC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    messages = []
    for row in rows:
        msg_id, gid, username, content, extracted_json, category, timestamp = row

        # Parse extracted_data JSON
        extracted = {}
        if extracted_json:
            try:
                extracted = json.loads(extracted_json)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in message {msg_id}, skipping")
                continue

        messages.append({
            'message_id': msg_id,
            'guild_id': gid,
            'username': username,
            'content': content or '',
            'extracted_data': extracted,
            'category': category,
            'timestamp': timestamp
        })

    return messages


def reprocess_message(msg: dict) -> dict:
    """
    Reprocess a single message and extract trades

    Pydantic validation automatically rejects incomplete trades (missing strike/expiration),
    so we don't need explicit deduplication - just parse from the combined text.

    Args:
        msg: Message dict from database

    Returns:
        Updated extracted_data dict
    """
    content = msg['content']
    extracted = msg['extracted_data']

    # Get existing OCR text if available
    raw_text_from_ocr = extracted.get('raw_text', '')

    # Determine which text to parse
    if raw_text_from_ocr and len(raw_text_from_ocr.strip()) >= 10:
        # Use combined text (message + OCR) for parsing
        combined_text = raw_text_from_ocr
        source = 'image'
    elif content and len(content.strip()) >= 10:
        # Use message content only
        combined_text = content
        source = 'text'
    else:
        # No meaningful text
        extracted_result: dict[Any, Any] = extracted
        return extracted_result

    # Parse trades using improved parser (Pydantic validates and rejects incomplete trades)
    trades = parse_trades_from_text(combined_text, source=source)

    # Update extracted_data
    updated = extracted.copy()
    updated['trades'] = trades

    updated_result: dict[Any, Any] = updated
    return updated_result


def update_message_in_db(message_id: int, extracted_data: dict, dry_run: bool = False):
    """
    Update message in database with new extracted_data

    Args:
        message_id: Message ID
        extracted_data: Updated extracted_data dict
        dry_run: If True, don't actually update
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would update message {message_id}")
        return

    db = Db()
    cursor = db.connection.cursor()

    cursor.execute(
        "UPDATE harvested_messages SET extracted_data = ? WHERE message_id = ?",
        (json.dumps(extracted_data), message_id)
    )
    db.connection.commit()


def main():
    parser = argparse.ArgumentParser(description="Batch reprocess trades from harvested messages")
    parser.add_argument('--guild-id', type=int, help="Only process messages from this guild")
    parser.add_argument('--limit', type=int, help="Limit number of messages to process")
    parser.add_argument('--dry-run', action='store_true', help="Show what would be updated, don't save")
    parser.add_argument('--verbose', '-v', action='store_true', help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("="*80)
    logger.info("BATCH TRADE REPROCESSING")
    logger.info("="*80)
    logger.info(f"Guild ID filter: {args.guild_id or 'None (all guilds)'}")
    logger.info(f"Limit: {args.limit or 'None (all messages)'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("")

    # Fetch messages
    logger.info("Fetching messages to reprocess...")
    messages = fetch_messages_to_reprocess(args.guild_id, args.limit)
    logger.info(f"Found {len(messages)} messages to reprocess")
    logger.info("")

    if not messages:
        logger.info("No messages to process. Exiting.")
        return

    # Process messages
    stats = {
        'processed': 0,
        'trades_found': 0,
        'trades_updated': 0,
        'errors': 0
    }

    for idx, msg in enumerate(messages, 1):
        msg_id = msg['message_id']
        username = msg['username']
        old_trades = msg['extracted_data'].get('trades', [])

        try:
            # Reprocess
            updated_data = reprocess_message(msg)
            new_trades = updated_data.get('trades', [])

            # Update stats
            stats['processed'] += 1
            if new_trades:
                stats['trades_found'] += len(new_trades)

            # Check if trades changed
            if len(new_trades) != len(old_trades):
                stats['trades_updated'] += 1
                logger.info(
                    f"[{idx}/{len(messages)}] Message {msg_id} ({username}): "
                    f"{len(old_trades)} → {len(new_trades)} trades"
                )

                # Update database
                update_message_in_db(msg_id, updated_data, dry_run=args.dry_run)

            # Log progress every 10 messages
            if idx % 10 == 0:
                logger.info(f"Progress: {idx}/{len(messages)} ({idx/len(messages)*100:.1f}%)")

        except Exception as e:
            stats['errors'] += 1
            logger.error(f"Error processing message {msg_id}: {e}")

    # Final stats
    logger.info("")
    logger.info("="*80)
    logger.info("REPROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"Messages processed: {stats['processed']}")
    logger.info(f"Messages with trades: {stats['trades_found']}")
    logger.info(f"Messages updated: {stats['trades_updated']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - No changes were saved to database")


if __name__ == "__main__":
    main()
