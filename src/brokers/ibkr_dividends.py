#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""


import logging

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor
from db import Db
from dividends import Dividends


# Module-level logger
logger = logging.getLogger(__name__)

class IBKRDividends(BaseCSVProcessor):
    def __init__(self, fname: str, skipfooter: int = 0):
        # Auto-detect the dividends section
        skiprows = self._find_dividends_section(fname)
        super().__init__(BaseCSVProcessor.Table.DIVIDENDS, fname, skiprows, skipfooter)

    def _find_dividends_section(self, fname: str) -> int:
        """Find the line number where the dividends section starts"""
        with open(fname) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Look for the Dividends header line
                if line.startswith("Dividends,Header,Currency,Date"):
                    logger.info(f"Found dividends section at line {i}")
                    return i

        # Default to 1 if not found (backward compatibility)
        logger.warning("Could not find dividends section, using skiprows=1")
        return 1

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Dividends", "Header", "Currency", "Date", "Description", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Dividends"].isin(["Dividends"])]
        df = df[df["Header"].isin(["Data"])]
        # Filter out Total rows
        df = df[df["Currency"] != "Total"]

        # If no dividend transactions found, return empty DataFrame
        if df.empty:
            logger.info("No dividend transactions found in file")
            return df

        # Extract symbol from Description field (e.g., "TSLY(US88636J4444) Cash Dividend..." -> "TSLY")
        df["Symbol"] = df["Description"].str.extract(r"^([A-Z]+)\(")

        # Date is already in the correct format (YYYY-MM-DD)
        # Amount is already named correctly

        return df


def main():
    dividends = IBKRDividends("uploads/ibkr_hrv_example.csv")
    dividends.set_debug(True)
    df, start_date, end_date = dividends.process()
    username = "testuser"
    df["username"] = username
    print(f"Dividends Range: {start_date} to {end_date}")
    print(df)

    db = Db()
    db_div = Dividends(db)
    db_div.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    IBKRDividend = namedtuple("IBKRDividend", [
        "username", "date", "symbol", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        dividend = IBKRDividend(
            username=row["username"],
            date=row["Date"],
            symbol=row["Symbol"],
            amount=row["Amount"]
        )
        print(f"{dividend}")
        db_div.insert(dividend)

if __name__ == "__main__":
    main()
