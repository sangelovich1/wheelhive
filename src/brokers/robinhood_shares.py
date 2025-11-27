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

class RobinhoodShares(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 2):
        super().__init__(BaseCSVProcessor.Table.SHARES, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Settle Date", "Trans Code", "Instrument", "Quantity", "Price", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Trans Code"].isin(["Buy", "Sell"])]

        # If no share transactions found, return empty DataFrame
        if df.empty:
            logger.info("No share transactions found in file")
            return df

        df = df.rename(columns={"Instrument": "Symbol"})
        df = df.rename(columns={"Settle Date": "Date"})
        df = df.rename(columns={"Trans Code": "Action"})

        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")
        df["Price"] =self.currency_to_float(df["Price"])
        df["Amount"] =self.currency_to_float(df["Amount"])

        # Make sure quantity is an float and sign is correct for rollup operations
        df["Quantity"] = df["Quantity"].astype(float)
        df["Quantity"] = df.apply(lambda row: row["Quantity"] * -1 if row["Action"] in ["Sell"] else row["Quantity"], axis=1)

        return df


def main():
    # Example usage
    #rh_shares = RobinhoodShares('uploads/darkpegasus01.Jan_1_2025_Jul_23_2025.csv')
    rh_shares = RobinhoodShares("uploads/crazymonkey7543.b280fccc-fcfe-5431-94c9-8797ade3414e.csv")
    rh_shares = RobinhoodShares("uploads/darkminer.5a62ee96-fd98-5527-8e60-4665e623ad55.csv")
    rh_shares.set_debug(True)
    df, start_date, end_date = rh_shares.process()
    username = "testuser"
    df["username"] = username

    db = Db()
    shares = Shares(db)
    shares.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    RobinhoodShare = namedtuple("RobinhoodShare", [
        "username", "date", "action", "symbol", "price", "quantity", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        share = RobinhoodShare(
            username=row["username"],
            date=row["Date"],
            action=row["Action"],
            symbol=row["Symbol"],
            price=row["Price"],
            quantity=row["Quantity"],
            amount=row["Amount"]
        )
        print(share)
        shares.insert(share)


if __name__ == "__main__":
    main()
