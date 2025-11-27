#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""


import logging

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor
from db import Db
from trades import Trades


# Module-level logger
logger = logging.getLogger(__name__)

class SchwabOptions(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.OPTIONS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Date", "Action", "Symbol", "Quantity", "Price", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Action"].isin(["Sell to Open", "Buy to Close", "Buy to Open", "Sell to Close"])]

        # If no option transactions found, return empty DataFrame
        if df.empty:
            logger.info("No option transactions found in file")
            return df

        df["Action"] = df["Action"].str.replace("Sell to Open", "STO", regex=False)
        df["Action"] = df["Action"].str.replace("Buy to Close", "BTC", regex=False)
        df["Action"] = df["Action"].str.replace("Buy to Open", "BTO", regex=False)
        df["Action"] = df["Action"].str.replace("Sell to Close", "STC", regex=False)

        # Handle dates with settlement qualifiers (e.g., "08/25/2025 as of 08/22/2025")
        # Some dates may not have the qualifier, so we need to handle both cases
        df = df.rename(columns={"Date": "Date_original"})
        df["Date"] = df["Date_original"].str.split(" ", n=1, expand=True)[0]

        df = df.rename(columns={"Symbol": "Symbol_original"})
        df[["Symbol", "Expiration", "Strike", "Operation"]] = df["Symbol_original"].str.split(" ", n=4, expand=True)

        df = df.rename(columns={"Quantity": "Contracts"})
        df["Contracts"] = df["Contracts"].astype(int)

        df["Price"] = self.currency_to_float(df["Price"])
        df["Amount"] = self.currency_to_float(df["Amount"])

        # Convert dates to ISO format
        df["Expiration"] = self.to_db_date(df["Expiration"], "%m/%d/%Y")
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df


def main():
    sc = SchwabOptions("uploads/schwab_example.csv")
    sc.set_debug(True)
    df, start_date, end_date = sc.process()
    username="testuser"
    df["username"] = username
    print(f"Options Range: {start_date} to {end_date}")


    db = Db()
    trades = Trades(db)
    trades.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    SchwabTrade = namedtuple("SchwabTrade", [
        "username", "date", "operation", "contracts", "symbol",
        "expiration_date", "strike_price", "option_type", "premium", "total"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        trade = SchwabTrade(
            username=row["username"],
            date=row["Date"],
            operation=row["Action"],
            contracts=row["Contracts"],
            symbol=row["Symbol"],
            expiration_date=row["Expiration"],
            strike_price=row["Strike"],
            option_type=row["Operation"],
            premium=row["Price"],
            total=row["Amount"]
        )
        print(trade)
        trades.insert(trade)


if __name__ == "__main__":
    main()
