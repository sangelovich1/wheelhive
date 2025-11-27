#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from collections import namedtuple
from typing import Any

# Third-party imports
import pandas as pd

# Local application imports
import util
from brokers.basetableprocessor import BaseTableProcessor
from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class Dividends(BaseTableProcessor):

    def __init__(self, db: Db) -> None:
        super().__init__(db, "dividends")
        self.create_table()

    def create_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS dividends (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            guild_id INTEGER DEFAULT NULL,
            account TEXT DEFAULT 'default',
            date TEXT NOT NULL,
            symbol TEXT,
            amount REAL
        )
        """
        self.db.create_table(query)

        # Migration: Add columns to existing table if they don't exist
        util.add_column_if_not_exists(self.db.connection, "dividends", "guild_id", "INTEGER DEFAULT NULL")
        util.add_column_if_not_exists(self.db.connection, "dividends", "account", 'TEXT DEFAULT "default"')

    @classmethod
    def headers(cls) -> list:
        return ["ID", "Username", "guild_id", "account", "Date", "Symbol", "Amount"]

    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        """Override base query to ensure columns are selected in header order"""
        if fields is None:
            # Explicitly select columns in the order matching headers()
            fields_str = "id, username, guild_id, account, date, symbol, amount"
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
            INSERT INTO dividends
                (username, guild_id, account, date, symbol, amount)
                values(?, ?, ?, ?, ?, ?)
            """

        row = (nt.username, guild_id, account, nt.date, nt.symbol, nt.amount)
        self.db.insert(query, row)

    @classmethod
    def parse(cls, s: str) -> Any:
        items = s.split(None)
        count = len(items)
        if count < 4:
            return None

        if not items[0].lower().startswith("div"):
            return None

        date_str = util.to_db_date(items[1])
        symbol = items[2]
        amount = util.currency_to_float(items[3])

        DividendTuple =  namedtuple("DividendTuple", ["Date", "Symbol", "Amount"])
        dt = DividendTuple(date_str, symbol, amount)
        return dt

    def styled_df(self, user: str, filter: str | None = None) -> pd.DataFrame:  # type: ignore[override]
        df = self.as_df(user, filter)
        df = df.drop(["ID", "Username", "guild_id", "account"], axis=1)

        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
        df.sort_values(by=["Date"], ascending=[True], inplace=True)
        df["Date"] = df["Date"].dt.strftime("%m/%d/%y")

        return df









def main() -> None:

    db = Db()
    dividends = Dividends(db)

    # username = 'sangelovich'
    username = "chance1368"
    symbol = None
    h_str = "Dividends"
    fields = ["ID", 'STRFTIME("%m/%d/%Y", date)', "Symbol", "Amount"]
    aliases = ["ID", "Date", "Symbol", "Amount"]
    index = 0
    table_str, cnt = dividends.my_records(username, index, fields=fields, aliases=aliases, symbol=symbol)
    print(len(table_str))



if __name__ == "__main__":
    main()
