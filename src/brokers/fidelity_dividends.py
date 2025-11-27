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

class FidelityDividends(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 2, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.DIVIDENDS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Run Date", "Action", "Symbol", "Amount ($)"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Action"].str.startswith("DIVIDEND", na=False)]

        # If no dividend transactions found, return empty DataFrame
        if df.empty:
            logger.info("No dividend transactions found in file")
            return df

        df = df.rename(columns={"Amount ($)": "Amount"})
        df = df.rename(columns={"Run Date": "Date"})
        df = df[["Date", "Symbol", "Amount"]]
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df


def main():
    # Example usage
    fidelity_dividends = FidelityDividends("uploads/sangelovich.Accounts_History-8.csv")
    fidelity_dividends.set_debug(True)
    df, start_date, end_date = fidelity_dividends.process()
    username = "testuser"
    df["username"] = username

    db = Db()
    dividends = Dividends(db)
    dividends.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    FidelityDividend = namedtuple("FidelityDividend", [
        "username", "date", "symbol", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        dividend = FidelityDividend(
            username=row["username"],
            date=row["Date"],
            symbol=row["Symbol"],
            amount=row["Amount"]
        )
        print(f"{dividend}")
        dividends.insert(dividend)


if __name__ == "__main__":
    main()
