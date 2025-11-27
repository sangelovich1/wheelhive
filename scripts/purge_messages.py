"""
Purge all harvested messages and associated tickers from the database.
This is useful when you want to re-harvest messages with new features (like OCR).

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from db import Db

def purge_messages():
    """Delete all harvested messages and ticker associations"""
    db = Db()

    print("Purging harvested messages database...")
    print("=" * 80)

    # Get counts before deletion
    message_count = db.query("SELECT COUNT(*) FROM harvested_messages", None)[0][0]
    ticker_count = db.query("SELECT COUNT(*) FROM message_tickers", None)[0][0]

    print(f"Current counts:")
    print(f"  Messages: {message_count:,}")
    print(f"  Message-Ticker associations: {ticker_count:,}")
    print()

    if message_count == 0:
        print("No messages to purge.")
        return

    # Confirm deletion
    response = input(f"Are you sure you want to delete {message_count:,} messages? (yes/no): ")
    if response.lower() != 'yes':
        print("Purge cancelled.")
        return

    # Delete message-ticker associations first (foreign key constraint)
    print(f"Deleting {ticker_count:,} message-ticker associations...")
    db.execute("DELETE FROM message_tickers", None)

    # Delete messages
    print(f"Deleting {message_count:,} messages...")
    db.execute("DELETE FROM harvested_messages", None)

    # Verify deletion
    remaining_messages = db.query("SELECT COUNT(*) FROM harvested_messages", None)[0][0]
    remaining_tickers = db.query("SELECT COUNT(*) FROM message_tickers", None)[0][0]

    print()
    print("Purge complete!")
    print(f"  Messages remaining: {remaining_messages}")
    print(f"  Message-Ticker associations remaining: {remaining_tickers}")
    print()
    print("You can now run harvest_history.py to re-harvest messages with OCR enabled.")
    print("=" * 80)

if __name__ == '__main__':
    purge_messages()
