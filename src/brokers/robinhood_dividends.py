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

class RobinhoodDividends(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 2):
        super().__init__(BaseCSVProcessor.Table.DIVIDENDS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Settle Date", "Trans Code", "Instrument", "Amount"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Trans Code"].str.startswith("CDIV", na=False)]

        # If no dividend transactions found, return empty DataFrame
        if df.empty:
            logger.info("No dividend transactions found in file")
            return df

        df = df.rename(columns={"Instrument": "Symbol"})
        df = df.rename(columns={"Settle Date": "Date"})
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        df["Amount"] = self.currency_to_float(df["Amount"])

        return df


def main():
    # Example usage
    dividends = RobinhoodDividends("uploads/darkpegasus01.Jan_1_2025_Jul_23_2025.csv")
    dividends.set_debug(True)
    df, start_date, end_date = dividends.process()
    username = "sangelovich"
    df["username"] = username
    print(df)

    db = Db()
    db_div = Dividends(db)
    db_div.delete_range("sangelovich", start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    RobinhoodDividend = namedtuple("RobinhoodDividend", [
        "username", "date", "symbol", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        dividend = RobinhoodDividend(
            username=row["username"],
            date=row["Date"],
            symbol=row["Symbol"],
            amount=row["Amount"]
        )
        print(f"{dividend}")
        db_div.insert(dividend)


if __name__ == "__main__":
    main()
