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

class RobinhoodOptions(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 0, skipfooter: int = 2):
        super().__init__(BaseCSVProcessor.Table.OPTIONS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Process Date", "Trans Code", "Instrument", "Description", "Quantity", "Price"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Trans Code"].isin(["STO", "BTC", "BTO", "STC"])]

        # If no option transactions found, return empty DataFrame
        if df.empty:
            logger.info("No option transactions found in file")
            return df

        columns = ["Activity Date", "Settle Date", "Amount"]
        df = df.drop(columns=columns, axis=1, errors="ignore")
        df = df.rename(columns={"Process Date": "Date"})
        df = df.rename(columns={"Instrument": "Symbol"})
        df = df.rename(columns={"Trans Code": "Action"})

        df = df.rename(columns={"Quantity": "Contracts"})
        df["Contracts"] = df["Contracts"].astype(int)

        df[["Field1", "Expiration", "Operation", "Strike"]] = df["Description"].str.split(" ", n=3, expand=True)
        df = df.drop("Field1", axis=1, errors="ignore")
        df["Strike"] = df["Strike"].str.replace("$", "", regex=False).astype(float)
        df["Price"] = df["Price"].str.replace("$", "", regex=False).astype(float)
        df["Operation"] = df["Operation"].str[0]

        df["Amount"] = df["Contracts"] * 100 * df["Price"]
        df["Amount"] = df.apply(lambda row: row["Amount"] * -1 if row["Action"] in ["BTO", "BTC"] else row["Amount"], axis=1)

        # Convert dates to ISO format
        df["Expiration"] = self.to_db_date(df["Expiration"], "%m/%d/%Y")
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df


def main():
    # Example usage
    rh = RobinhoodOptions("uploads/darkminer.3b67b712-69af-53c7-b872-2f4189ecc640.csv")
    rh.set_debug(True)
    # rh = Robinhood('uploads/darkminer.b986ab8f-b8e5-53ae-9114-287404922edb.csv')
    df, start_date, end_date = rh.process()
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
    RobinhoodTrade = namedtuple("RobinhoodTrade", [
        "username", "date", "operation", "contracts", "symbol",
        "expiration_date", "strike_price", "option_type", "premium", "total"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        trade = RobinhoodTrade(
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
