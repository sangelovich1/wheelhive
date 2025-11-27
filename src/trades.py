#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from datetime import datetime, timedelta
from typing import Any

# Third-party imports
import pandas as pd

# Local application imports
import util
from brokers.basetableprocessor import BaseTableProcessor
from db import Db
from trade import Trade


# Get a logger instance
logger = logging.getLogger(__name__)

class Trades(BaseTableProcessor):

    def __init__(self, db: Db) -> None:
        super().__init__(db, "trades")
        self.create_table()

    def create_table(self) -> None:
        query = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL,
            guild_id INTEGER DEFAULT NULL,
            account TEXT DEFAULT 'default',
            date TEXT NOT NULL, raw_trade TEXT NOT NULL,
            operation TEXT, contracts INTEGER,
            symbol TEXT, expiration_date TEXT,
            strike_price REAL, option_type TEXT,
            premium REAL, total REAL
        )
        """
        self.db.create_table(query)

        # Migration: Add columns to existing table if they don't exist
        util.add_column_if_not_exists(self.db.connection, "trades", "guild_id", "INTEGER DEFAULT NULL")
        util.add_column_if_not_exists(self.db.connection, "trades", "account", 'TEXT DEFAULT "default"')

    @classmethod
    def headers(cls) -> tuple:
        return ("ID", "Username", "guild_id", "account", "Date", "raw_trade",
                "Operation", "contracts", "Symbol",
                "Expiration_Date", "Strike",
                 "Option_Type", "Premium", "Total")

    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        """Override base query to ensure columns are selected in header order"""
        if fields is None:
            # Explicitly select columns in the order matching headers()
            # This is critical because guild_id and account were added via ALTER TABLE
            # and appear at the end of the table, but we need them in positions 3 and 4
            fields_str = "id, username, guild_id, account, date, raw_trade, operation, contracts, symbol, expiration_date, strike_price, option_type, premium, total"
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
            INSERT INTO trades
                (username, guild_id, account, date, raw_trade, operation, contracts,
                symbol, expiration_date, strike_price, option_type, premium, total)
                values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

        raw_trade = f"{nt.operation} {nt.contracts}x {nt.symbol} {nt.expiration_date} ${nt.strike_price}{nt.option_type} @ ${nt.premium}"
        row = (nt.username, guild_id, account, nt.date, raw_trade, nt.operation, nt.contracts, nt.symbol, nt.expiration_date, nt.strike_price, nt.option_type, nt.premium, nt.total)
        self.db.insert(query, row)

    def as_df(self, user: str | None, filter: str | None = None) -> pd.DataFrame:
        df =  super().as_df(user, filter)
        # If empty DataFrame, return it as-is without date parsing
        if df.empty:
            return df
        df["Expiration_Date"] = pd.to_datetime(df["Expiration_Date"], format="%Y-%m-%d")
        df["Expiration_Date"] = df["Expiration_Date"].dt.strftime("%m/%d/%Y")
        return df

    def styled_df(self, user: str, filter: str | None = None) -> pd.DataFrame:  # type: ignore[override]
        df = self.as_df(user, filter)
        df["Strike"] = df["Strike"].astype(str).str.cat(df["Option_Type"], sep="", na_rep="")
        df["Strike"] = "$" + df["Strike"]
        df = df.drop(["ID", "raw_trade", "Username", "guild_id", "account", "Option_Type"], axis=1)
        df = df.rename(columns={"Expiration_Date": "Expiration"})
        df = df.rename(columns={"contracts": "Con"})
        df = df.rename(columns={"Operation": "Action"})
        df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
        df.sort_values(by=["Date", "Action"], ascending=[True, True], inplace=True)
        df["Date"] = df["Date"].dt.strftime("%m/%d/%y")
        df["Expiration"] = pd.to_datetime(df["Expiration"], format="%m/%d/%Y")
        df["Expiration"] = df["Expiration"].dt.strftime("%m/%d/%y")

        return df

    def trade(self, user: str, d: str, t: str) -> None:
        trade = Trade(user, d, t)
        trade.parse()
        self.insert(trade.as_named_tuple())

    def get_popular_symbols(self, username: str | None = None, days: int = 7) -> pd.DataFrame:
        """
        Returns a DataFrame of symbols traded in the last `days` days, sorted by count descending.
        If username is provided, filters by user.
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        condition = f'date BETWEEN "{start_date}" AND "{end_date}"'
        if username:
            condition += f' AND username="{username}"'
        query = (
            "SELECT symbol, COUNT(*) as count "
            "FROM trades "
            f"WHERE {condition} "
            "GROUP BY symbol "
            "ORDER BY count DESC"
        )
        rows = self.db.query(select=query)
        df = pd.DataFrame(rows, columns=["Symbol", "Count"])
        return df


def main() -> None:

    db = Db()
    trades = Trades(db)

    d = "2025-07-20"
    trade_str = "STO 1x CONL 7/18 24P at .95"

    trade = Trade("sangelovich", d, trade_str)
    trade.parse()
    nt = trade.as_named_tuple()
    trades.insert(nt)



    # trades.delete_all('sangelovich')

    # start_date = datetime.strptime('2025-01-01', '%Y-%m-%d')
    # end_date = datetime.now()

    # day_count = (end_date - start_date).days + 1

    # for single_date in (start_date + timedelta(n) for n in range(day_count)):
    #    dstr = single_date.strftime("%Y-%m-%d")
    #    trades.trade('sangelovich', dstr, 'STO 3x AAPL 5/23 $150P for $1.50')

    # rows = trades.my_trades('sangelovich', 0)
    # for row in rows:
    #    print(row)




if __name__ == "__main__":
    main()
