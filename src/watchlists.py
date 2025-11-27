#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging

# Third-party imports
import pandas as pd
from tabulate import tabulate

# Local application imports
from brokers.basetableprocessor import BaseTableProcessor
from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class Watchlists(BaseTableProcessor):

    def __init__(self, db: Db) -> None:
        super().__init__(db, "watchlist")
        self.create_table()

    def create_table(self) -> None:
        # Check if table exists with old schema (has id column)
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Check if table has id column (old schema)
            cursor.execute("PRAGMA table_info(watchlist)")
            columns = [row[1] for row in cursor.fetchall()]

            if "id" in columns:
                logger.info("Migrating watchlist table to remove ID column")
                # Migrate to new schema
                # 1. Rename old table
                cursor.execute("ALTER TABLE watchlist RENAME TO watchlist_old")

                # 2. Create new table with composite primary key
                cursor.execute("""
                    CREATE TABLE watchlist (
                        username TEXT NOT NULL,
                        guild_id INTEGER NOT NULL DEFAULT 0,
                        symbol TEXT NOT NULL,
                        PRIMARY KEY (username, guild_id, symbol)
                    )
                """)

                # 3. Copy data, converting NULL guild_id to 0
                cursor.execute("""
                    INSERT INTO watchlist (username, guild_id, symbol)
                    SELECT DISTINCT username, COALESCE(guild_id, 0), symbol
                    FROM watchlist_old
                """)

                # 4. Drop old table
                cursor.execute("DROP TABLE watchlist_old")

                self.db.connection.commit()
                logger.info("Watchlist migration complete")
        else:
            # Create new table with composite primary key
            query = """
            CREATE TABLE IF NOT EXISTS watchlist (
                username TEXT NOT NULL,
                guild_id INTEGER NOT NULL DEFAULT 0,
                symbol TEXT NOT NULL,
                PRIMARY KEY (username, guild_id, symbol)
            )
            """
            self.db.create_table(query)

    @classmethod
    def headers(cls) -> list:
        return ["Username", "guild_id", "Symbol"]

    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        """Override base query to ensure columns are selected in header order"""
        if fields is None:
            # Explicitly select columns in the order matching headers()
            fields_str = "username, guild_id, symbol"
        else:
            fields_str = ", ".join(fields)

        select = f"SELECT {fields_str} FROM {self.tablename}"
        filter = None

        if condition is None and username is None:
            filter = None
        if condition is not None and username is None:
            filter = condition
        if condition is None and username is not None:
            filter = f'username = "{username}"'
        elif condition is not None and username is not None:
            filter = f'username = "{username}" AND {condition}'

        logger.debug(f"query select: {select}, condition: {filter}")
        return self.db.query(select=select, condition=filter, orderby="symbol ASC")

    def add(self, username: str, symbol: str, guild_id: int | None = None) -> bool:
        """Add a symbol to the watchlist"""
        # Convert None to 0 for guild_id (NOT NULL constraint)
        guild_id = guild_id if guild_id is not None else 0

        # Check if symbol already exists for this user/guild
        condition = f'symbol = "{symbol.upper()}" AND guild_id = {guild_id}'

        existing = self.query(username, condition=condition)
        if existing:
            logger.info(f"Symbol {symbol} already in watchlist for {username}")
            return False

        query = """
            INSERT INTO watchlist
                (username, guild_id, symbol)
                values(?, ?, ?)
            """
        row = (username, guild_id, symbol.upper())
        self.db.insert(query, row)
        logger.info(f"Added {symbol} to watchlist for {username}")
        return True

    def remove(self, username: str, symbol: str, guild_id: int | None = None) -> int:
        """Remove a symbol from the watchlist"""
        # Convert None to 0 for guild_id (NOT NULL constraint)
        guild_id = guild_id if guild_id is not None else 0

        condition = f'symbol = "{symbol.upper()}" AND guild_id = {guild_id}'

        query = f"DELETE FROM {self.tablename} WHERE username = ? AND {condition}"
        cursor = self.db.connection.cursor()
        cursor.execute(query, (username,))
        self.db.connection.commit()
        deleted = cursor.rowcount
        logger.info(f"Removed {deleted} entries for {symbol} from watchlist for {username}")
        return deleted

    def list_symbols(self, username: str, guild_id: int | None = None) -> list[str]:
        """
        Get list of symbols for a user.

        Args:
            username: Username to get symbols for
            guild_id: Optional guild filter (None = all guilds)

        Returns:
            List of symbol strings
        """
        # Only filter by guild_id if explicitly provided
        condition = None
        if guild_id is not None:
            condition = f"guild_id = {guild_id}"

        results = self.query(username, fields=["symbol"], condition=condition)
        return [row[0] for row in results]

    def as_df(self, username: str | None, condition: str | None = None) -> pd.DataFrame:
        """Override base as_df since watchlist doesn't have Date column"""
        results = self.query(username, condition=condition)
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results, columns=self.headers())
        return df

    def styled_df(self, username: str, guild_id: int | None = None) -> pd.DataFrame:  # type: ignore[override]
        """Return a styled DataFrame for display"""
        # Convert None to 0 for guild_id (NOT NULL constraint)
        guild_id = guild_id if guild_id is not None else 0

        condition = f"guild_id = {guild_id}"

        df = self.as_df(username, condition)
        if df.empty:
            return df

        # Drop internal columns
        df = df.drop(["Username", "guild_id"], axis=1)

        return df

    def as_str(self, username: str, guild_id: int | None = None, symbols_per_row: int = 5) -> str:  # type: ignore[override]
        """
        Return watchlist as a formatted multi-column string for display.

        Args:
            username: Username to get watchlist for
            guild_id: Optional guild filter (None = show all guilds)
            symbols_per_row: Number of symbols to display per row (default: 5)

        Returns:
            Formatted table string ready for display
        """
        # Only filter by guild_id if explicitly provided
        condition = None
        if guild_id is not None:
            condition = f"guild_id = {guild_id}"

        results = self.query(username, condition=condition)

        if not results:
            return "Watchlist is empty."

        # Extract symbols (row[0]=username, row[1]=guild_id, row[2]=symbol)
        symbols = [row[2] for row in results]

        # Format in multiple columns for compact display
        table_data = []
        for i in range(0, len(symbols), symbols_per_row):
            row = symbols[i:i+symbols_per_row]
            table_data.append(row)

        # Create table without headers for cleaner display
        table_str = tabulate(table_data, tablefmt="plain", stralign="left")

        return f"Symbols:\n{table_str}"


def main() -> None:
    db = Db()
    watchlists = Watchlists(db)

    # Test adding symbols
    watchlists.add("testuser", "AAPL")
    watchlists.add("testuser", "TSLA")
    watchlists.add("testuser", "SPY")

    # List symbols
    symbols = watchlists.list_symbols("testuser")
    print(f"Watchlist: {symbols}")


if __name__ == "__main__":
    main()
