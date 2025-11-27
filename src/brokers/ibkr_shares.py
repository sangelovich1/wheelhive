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

class IBKRShares(BaseCSVProcessor):
    def __init__(self, fname: str, skipfooter: int = 0):
        # Auto-detect the shares section
        skiprows = self._find_shares_section(fname)
        super().__init__(BaseCSVProcessor.Table.SHARES, fname, skiprows, skipfooter)

    def _find_shares_section(self, fname: str) -> int:
        """Find the line number where the shares Trades section starts"""
        with open(fname) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Look for the Trades header line followed by stocks data
                if line.startswith("Trades,Header,DataDiscriminator,Asset Category"):
                    # Check if next line contains stocks data
                    if i + 1 < len(lines) and "Stocks" in lines[i + 1]:
                        logger.info(f"Found shares section at line {i}")
                        return i

        # Default to 1 if not found (backward compatibility)
        logger.warning("Could not find shares section, using skiprows=1")
        return 1

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Trades", "Header", "DataDiscriminator", "Asset Category", "Currency", "Symbol", "Date/Time", "Quantity", "T. Price", "Proceeds"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Trades"].isin(["Trades"])]
        df = df[df["Header"].isin(["Data"])]
        df = df[df["Asset Category"].isin(["Stocks"])]

        # If no share transactions found, return empty DataFrame
        if df.empty:
            logger.info("No share transactions found in file")
            return df

        df.rename(columns={"Date/Time": "Date"}, inplace=True)
        df["Date"] = df["Date"].str.split(",").str[0]

        df.rename(columns={"T. Price": "Price"}, inplace=True)

        # Make sure quantity is an float and sign is correct for rollup operations
        df["Quantity"] = df["Quantity"].astype(float)
        df["Action"] = df.apply(lambda row: "Buy" if row["Quantity"] > 0 else "Sell", axis=1)
        df.rename(columns={"Proceeds": "Amount"}, inplace=True)

        return df


def main():
    sc = IBKRShares("uploads/ibkr_hrv_example.csv")
    sc.set_debug(True)
    df, start_date, end_date = sc.process()
    username="testuser"
    df["username"] = username
    print(f"Shares Range: {start_date} to {end_date}")


    db = Db()
    trades = Shares(db)
    trades.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    IBKRShare = namedtuple("IBKRShare", [
        "username", "date", "action", "symbol", "price", "quantity", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        share = IBKRShare(
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
