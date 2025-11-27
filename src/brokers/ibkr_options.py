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

class IBKROptions(BaseCSVProcessor):
    def __init__(self, fname: str, skipfooter: int = 0):
        # Auto-detect the options section
        skiprows = self._find_options_section(fname)
        super().__init__(BaseCSVProcessor.Table.OPTIONS, fname, skiprows, skipfooter)

    def _find_options_section(self, fname: str) -> int:
        """Find the line number where the options Trades section starts"""
        with open(fname) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Look for the Trades header line followed by options data
                if line.startswith("Trades,Header,DataDiscriminator,Asset Category"):
                    # Check if next line contains options data
                    if i + 1 < len(lines) and "Equity and Index Options" in lines[i + 1]:
                        logger.info(f"Found options section at line {i}")
                        return i

        # Default to 1 if not found (backward compatibility)
        logger.warning("Could not find options section, using skiprows=1")
        return 1

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Trades", "Header", "DataDiscriminator", "Asset Category", "Currency", "Symbol", "Date/Time", "Quantity",  "T. Price", "Proceeds", "Code"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Trades"].isin(["Trades"])]
        df = df[df["Header"].isin(["Data"])]
        df = df[df["Asset Category"].isin(["Equity and Index Options"])]

        # If no option transactions found, return empty DataFrame
        if df.empty:
            logger.info("No option transactions found in file")
            return df

        df.rename(columns={"Symbol": "details"}, inplace=True)
        df[["Symbol", "Expiration", "Strike", "Operation"]] = df["details"].str.split(" ", n=4, expand=True)

        df.rename(columns={"Date/Time": "Date"}, inplace=True)
        df["Date"] = df["Date"].str.split(",").str[0]

        df.rename(columns={"Quantity": "Contracts"}, inplace=True)
        df["Contracts"] = df["Contracts"].astype(int)

        df.rename(columns={"T. Price": "Price"}, inplace=True)
        df.rename(columns={"Proceeds": "Amount"}, inplace=True)

        # Assign Action based on Contracts and OpenClose
        def determine_action(row):
            quantity = row["Contracts"]
            open_close = row["Code"]
            if open_close is None or pd.isna(open_close):
                return "Unknown"

            if quantity < 0 and "O" in open_close:
                return "STO"
            if quantity > 0 and "C" in open_close:
                return "BTC"
            if quantity > 0 and "O" in open_close:
                return "BTO"
            if quantity < 0 and "C" in open_close:
                return "STC"
            return "Unknown"

        df["Action"] = df.apply(determine_action, axis=1)

        df["Contracts"] = abs(df["Contracts"])
        # # Convert dates to ISO format
        df["Expiration"] = self.to_db_date(df["Expiration"], "%d%b%y")

        return df


def main():
    sc = IBKROptions("uploads/ibkr_hrv_example.csv")
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
    IBKRTrade = namedtuple("IBKRTrade", [
        "username", "date", "operation", "contracts", "symbol",
        "expiration_date", "strike_price", "option_type", "premium", "total"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        trade = IBKRTrade(
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
