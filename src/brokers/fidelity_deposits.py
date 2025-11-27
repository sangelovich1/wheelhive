#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor
from db import Db
from deposits import Deposits


# Module-level logger
logger = logging.getLogger(__name__)

class FidelityDeposits(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 2, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.DEPOSITS, fname, skiprows, skipfooter)

    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Run Date", "Action", "Amount ($)"]
        self.cvs_req_cols(df, required_cols)

        df = df[df["Action"].str.contains("Electronic Funds Transfer", regex=False, na=False, case=False)]

        # If no deposit/withdrawal transactions found, return empty DataFrame
        if df.empty:
            logger.info("No deposit/withdrawal transactions found in file")
            return df

        df = df.rename(columns={"Amount ($)": "Amount"})
        df = df.rename(columns={"Run Date": "Date"})

        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        df["Action"] = "Deposit"
        df.loc[df["Amount"] < 0, "Action"] = "Withdrawal"

        return df


def main():
    # Example usage
    fidelity_deposits = FidelityDeposits("uploads/sangelovich.Accounts_History-8.csv")
    fidelity_deposits.set_debug(True)
    df, start_date, end_date = fidelity_deposits.process()
    username = "testuser"
    df["username"] = username

    print(df)
    db = Db()
    deposits = Deposits(db)
    deposits.delete_range(username, start_date, end_date)

    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    FidelityDeposit = namedtuple("FidelityDeposit", [
        "username", "action", "date", "amount"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        deposit = FidelityDeposit(
            username=row["username"],
            action=row["Action"],
            date=row["Date"],
            amount=row["Amount"]
        )
        print(f"{deposit}")
        deposits.insert(deposit)

    print("Deposits inserted successfully.")

    # print("Queried Dividends:")
    # print(dividends.as_str("sangelovich"))


if __name__ == "__main__":
    main()
