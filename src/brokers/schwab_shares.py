#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""


import logging

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor
from db import Db
from shares import Shares


# Module-level logger
logger = logging.getLogger(__name__)

class SchwabShares(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.SHARES, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Date", "Action", "Symbol", "Quantity", "Price", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Action"].isin(["Buy", "Sell", "Reinvest Shares"])]

        # If no share transactions found, return empty DataFrame
        if df.empty:
            logger.info("No share transactions found in file")
            return df

        df["Action"] = df["Action"].str.replace("Reinvest Shares", "Buy", regex=False)

        # Handle dates with settlement qualifiers (e.g., "08/25/2025 as of 08/22/2025")
        # Some dates may not have the qualifier, so we need to handle both cases
        df = df.rename(columns={"Date": "Date_original"})
        df["Date"] = df["Date_original"].str.split(" ", n=1, expand=True)[0]

        df["Price"] = self.currency_to_float(df["Price"])
        df["Amount"] = self.currency_to_float(df["Amount"])

        # Make sure quantity is an float and sign is correct for rollup operations
        df["Quantity"] = df["Quantity"].astype(float)
        df["Quantity"] = df.apply(lambda row: row["Quantity"] * -1 if row["Action"] in ["Sell"] else row["Quantity"], axis=1)

        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df


def main():
    sc = SchwabShares("uploads/schwab_example.csv")
    sc.set_debug(True)
    df, start_date, end_date = sc.process()
    username="testuser"
    df["username"] = username
    print(f"Options Range: {start_date} to {end_date}")


    db = Db()
    trades = Shares(db)
    trades.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    SchwabShare = namedtuple("SchwabShare", [
        "username", "date", "action", "symbol", "price", "quantity", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        share = SchwabShare(
            username=row["username"],
            date=row["Date"],
            action=row["Action"],
            symbol=row["Symbol"],
            price=row["Price"],
            quantity=row["Quantity"],
            amount=row["Amount"]
        )
        print(share)
        trades.insert(share)


if __name__ == "__main__":
    main()
