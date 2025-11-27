#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from typing import Any

# Third-party imports
# Local application imports
import util
from brokers.basetableprocessor import BaseTableProcessor
from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class Deposits(BaseTableProcessor):

    def __init__(self, db: Db) -> None:
        super().__init__(db, "deposits")
        self.create_table()

    def create_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            guild_id INTEGER DEFAULT NULL,
            account TEXT DEFAULT 'default',
            action TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL
        )
        """
        self.db.create_table(query)

        # Migration: Add columns to existing table if they don't exist
        util.add_column_if_not_exists(self.db.connection, "deposits", "guild_id", "INTEGER DEFAULT NULL")
        util.add_column_if_not_exists(self.db.connection, "deposits", "account", 'TEXT DEFAULT "default"')

    @classmethod
    def headers(cls) -> list:
        return ["ID", "Username", "guild_id", "account", "Action", "Date", "Amount"]

    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        """Override base query to ensure columns are selected in header order"""
        if fields is None:
            # Explicitly select columns in the order matching headers()
            # Note: deposits table has action, date, amount order per PRAGMA
            fields_str = "id, username, guild_id, account, action, date, amount"
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
        return self.db.query(select=select, condition=filter, orderby="date DESC")

    def insert(self, nt: Any) -> None:  # type: ignore[override]
        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(nt, "guild_id", None)
        account = getattr(nt, "account", "default")

        query = """
            INSERT INTO deposits
                (username, guild_id, account, action, date, amount)
                values(?, ?, ?, ?, ?, ?)
            """

        row = (nt.username, guild_id, account, nt.action, nt.date, nt.amount)
        self.db.insert(query, row)



def main() -> None:

    db = Db()
    deposits = Deposits(db)




if __name__ == "__main__":
    main()
