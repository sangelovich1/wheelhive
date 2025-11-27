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

class SchwabDividends(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.DIVIDENDS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Date", "Action", "Symbol", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Action"].isin(["Cash Dividend", "Reinvest Dividend"])]

        # If no dividend transactions found, return empty DataFrame
        if df.empty:
            logger.info("No dividend transactions found in file")
            return df

        # Handle dates with settlement qualifiers (e.g., "08/25/2025 as of 08/22/2025")
        # Some dates may not have the qualifier, so we need to handle both cases
        df = df.rename(columns={"Date": "Date_original"})
        df["Date"] = df["Date_original"].str.split(" ", n=1, expand=True)[0]

        df["Amount"] = self.currency_to_float(df["Amount"])
        # Convert dates to ISO format
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df


def main():
    sc = SchwabDividends("uploads/schwab_example.csv")
    sc.set_debug(True)
    df, start_date, end_date = sc.process()
    username="testuser"
    df["username"] = username
    print(f"Options Range: {start_date} to {end_date}")


    db = Db()
    trades = Dividends(db)
    trades.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    SchwabDividend = namedtuple("SchwabDividend", [
        "username", "date", "symbol", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        dividend = SchwabDividend(
            username=row["username"],
            date=row["Date"],
            symbol=row["Symbol"],
            amount=row["Amount"]
        )
        print(dividend)
        trades.insert(dividend)


if __name__ == "__main__":
    main()
