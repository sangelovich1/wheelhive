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

class Shares(BaseTableProcessor):

    def __init__(self, db: Db) -> None:
        super().__init__(db, "shares")
        self.create_table()

    def create_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS shares (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            guild_id INTEGER DEFAULT NULL,
            account TEXT DEFAULT 'default',
            date TEXT NOT NULL,
            action TEXT,
            symbol TEXT,
            price REAL,
            quantity REAL,
            amount REAL
        )
        """
        self.db.create_table(query)

        # Migration: Add columns to existing table if they don't exist
        util.add_column_if_not_exists(self.db.connection, "shares", "guild_id", "INTEGER DEFAULT NULL")
        util.add_column_if_not_exists(self.db.connection, "shares", "account", 'TEXT DEFAULT "default"')

    @classmethod
    def headers(cls) -> list:
        return ["ID", "Username", "guild_id", "account", "Date", "Action", "Symbol", "Price", "Quantity", "Amount"]

    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        """Override base query to ensure columns are selected in header order"""
        if fields is None:
            # Explicitly select columns in the order matching headers()
            fields_str = "id, username, guild_id, account, date, action, symbol, price, quantity, amount"
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

    @classmethod
    def parse(cls, s: str) -> Any:
        items = s.split(None)
        count = len(items)
        if count < 5:
            return None

        action = None
        if items[0].lower().startswith("buy"):
            action = "Buy"
            logger.info("Buy")
        elif items[0].lower().startswith("sel"):
            action = "Sell"
            logger.info("Sell")
        else:
            return None


        date_str = util.to_db_date(items[1])
        symbol = items[2]
        price = util.currency_to_float(items[3])
        quantity = util.currency_to_float(items[4])
        amount = util.currency_to_float(items[5])

        ShareTuple =  namedtuple("ShareTuple", ["Date", "Action", "Symbol", "Price", "Quantity", "Amount"])
        dt = ShareTuple(date_str, action, symbol, price, quantity, amount)
        return dt



    def insert(self, nt: Any) -> None:  # type: ignore[override]
        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(nt, "guild_id", None)
        account = getattr(nt, "account", "default")

        query = """
            INSERT INTO shares
                (username, guild_id, account, date, action, symbol, price, quantity, amount)
                values(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

        row = (nt.username, guild_id, account, nt.date, nt.action, nt.symbol, nt.price, nt.quantity, nt.amount)
        self.db.insert(query, row)


    def as_df(self, user: str | None, filter: str | None = None) -> pd.DataFrame:
        """
        Override base as_df to ensure numeric columns are properly typed.

        SQLite stores these as REAL but pandas reads them as object/string.
        Explicitly convert to numeric to ensure downstream operations work correctly.

        Args:
            user: Username to query shares for
            filter: Optional SQL filter condition

        Returns:
            DataFrame with properly typed numeric columns
        """
        # Get base DataFrame
        df = super().as_df(user, filter)

        if df.empty:
            return df

        # Convert numeric columns (pandas reads SQLite REAL as object)
        # errors='coerce' converts invalid values to NaN
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        return df

    def styled_df(self, user: str, filter: str | None = None) -> pd.DataFrame:  # type: ignore[override]
        df = self.as_df(user, filter)
        df = df.drop(["ID", "Username", "guild_id", "account"], axis=1)


        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
        df.sort_values(by=["Date", "Action"], ascending=[True, True], inplace=True)
        df["Date"] = df["Date"].dt.strftime("%m/%d/%y")

        df.rename(columns={"Quantity": "Shares"}, inplace=True)

        return df
