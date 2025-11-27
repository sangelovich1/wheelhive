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

class FidelityShares(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 2, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.SHARES, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Run Date", "Action", "Symbol", "Settlement Date", "Quantity", "Price ($)", "Amount ($)"]
        self.cvs_req_cols(df, required_cols)

        df = df[~df["Symbol"].str.startswith("-", na=False)]
        df = df[~df["Action"].str.startswith("DIVIDEND", na=False)]
        # df = df.dropna(subset=['Action', 'Symbol', 'Amount ($)', 'Price ($)', 'Settlement Date'])
        df = df.dropna(subset=["Action", "Symbol", "Amount ($)", "Settlement Date"])

        # If no share transactions found, return empty DataFrame
        if df.empty:
            logger.info("No share transactions found in file")
            return df

        # Price can be blank in cases like RSA
        df["Price ($)"] = df["Price ($)"].fillna(0)

        df = df.rename(columns={"Amount ($)": "Amount"})
        df = df.rename(columns={"Run Date": "Date"})
        df = df.rename(columns={"Price ($)": "Price"})
        df = df.rename(columns={"Action": "Action_orig"})
        df.insert(2, "Action", df["Action_orig"].str.split(" ").str[1])

        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        df["Action"] = df["Action"].str.replace("BOUGHT", "Buy")
        df["Action"] = df["Action"].str.replace("SOLD", "Sell")

        return df


def main():
    # Example usage
    procesor = FidelityShares("uploads/sangelovich.History_combined.csv")
    procesor.set_debug(True)
    df, start_date, end_date = procesor.process()
    username = "testuser"
    df["username"] = username

    db = Db()
    shares = Shares(db)
    shares.delete_range(username, start_date, end_date)


    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    FidelityShare = namedtuple("FidelityShare", [
        "username", "date", "action", "symbol", "price", "quantity", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        share = FidelityShare(
            username=row["username"],
            date=row["Date"],
            action=row["Action"],
            symbol=row["Symbol"],
            price=row["Price"],
            quantity=row["Quantity"],
            amount=row["Amount"]
        )
        print(f"{share}")
        shares.insert(share)


if __name__ == "__main__":
    main()
