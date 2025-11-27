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

class FidelityOptions(BaseCSVProcessor):
    def __init__(self, fname: str, skiprows: int = 2, skipfooter: int = 0):
        super().__init__(BaseCSVProcessor.Table.OPTIONS, fname, skiprows, skipfooter)

    @classmethod
    def custom_row_processor(cls, row):
        # Example: Calculate a new value based on existing columns
        value = row["Symbol"]
        value = value.upper()
        cp_index = -1
        for i in range(len(value) - 1, -1, -1):
            if value[i] == "C" or value[i] == "P":
                cp_index = i
                break

        # Ensure we have a valid cp_index to avoid index errors
        if cp_index == -1:
            return pd.Series([None, None, None, None])

        op = value[cp_index:cp_index+1]
        strike = value[cp_index+1: len(value)]
        expiration = value[cp_index-6: cp_index]
        symbol = value[1:cp_index-6]
        return pd.Series([symbol, expiration, op, strike])


    def clean(self, df) -> pd.DataFrame:
        df = df.copy()

        required_cols = ["Run Date", "Action", "Symbol", "Description", "Quantity", "Price ($)", "Amount ($)"]
        self.cvs_req_cols(df, required_cols)

        # If Symbol, Price or Amount ($) is blank drop the row
        df = df.dropna(subset=["Symbol", "Amount ($)", "Price ($)"])
        df = df.rename(columns={"Run Date": "Date"})

        # clean_df = clean_df.drop("Account", axis=1)
        columns = ["Type", "Commission ($)", "Fees ($)", "Accrued Interest ($)", "Cash Balance ($)"]
        df = df.drop(columns=columns, axis=1, errors="ignore")
        df = df.rename(columns={"Price ($)": "Price"})

        # Process the cleaned data to extract options information.
        # Creates a new dataframe with only the rows containing Puts and Calls
        # df.to_csv('fidelity_cleaned.csv', index=False)
        df = df[df["Symbol"].str.startswith("-", na=False)]

        # If no options found, return empty DataFrame
        if df.empty:
            logger.info("No option transactions found in file")
            return df

        df = df.copy()

        # Apply the custom function to each row and create new columns
        df[["Symbol", "Expiration", "Operation", "Strike"]] = df.apply(FidelityOptions.custom_row_processor, axis=1)

        # Rename useful columns
        df.rename(columns={"Quantity": "Contracts"}, inplace=True)

        # Extract Bought/Sold Action
        df["results"] = df["Action"].str.findall(r"(BOUGHT|SOLD|OPENING|CLOSING|ASSIGNED|EXPIRED)")
        df["results2"] = df["results"].apply(lambda x: " ".join(x))
        df["aaa"] = ["T".join(y[0] for y in x.split()) for x in df["results2"]]
        df.drop(columns=["results", "results2", "Action"], inplace=True)
        df.rename(columns={"aaa": "Action"}, inplace=True)

        # Drop unnecessary columns
        df = df.drop(columns=["Description", "Settlement Date", "Amount ($)"])
        # Flip sign of Contracts
        df["Contracts"] = df["Contracts"] * -1.0
        # Transaction amount
        df["Amount"] = df["Contracts"] * 100 * df["Price"]
        df["Contracts"] = df["Contracts"].abs()

        # Convert Expiration to datetime format and then to string in MM/DD/YYYY format
        df["Expiration"] = self.to_db_date(df["Expiration"], "%y%m%d")
        df["Date"] = self.to_db_date(df["Date"], "%m/%d/%Y")

        return df



def main():
    # Example usage
    fidelity = FidelityOptions("uploads/sangelovich.History_combined.csv")
    fidelity.set_debug(True)

    df, start_date, end_date = fidelity.process()
    username = "testuser"
    df["username"] = username
    print(f"Range: {start_date} to {end_date}")
    print(f"DataFrame:\n{df.head()}")

    db = Db()
    trades = Trades(db)
    trades.delete_range(username, start_date, end_date)


    df = df.sort_index(ascending=False)

    # Create namedtuple type matching insert() expectations (lowercase fields)
    # DataFrame has friendly column names (Capitalized) for display
    from collections import namedtuple
    FidelityTrade = namedtuple("FidelityTrade", [
        "username", "date", "operation", "contracts", "symbol",
        "expiration_date", "strike_price", "option_type", "premium", "total"
    ])

    for _, row in df.iterrows():
        # Map DataFrame columns (Capitalized) to namedtuple fields (lowercase)
        # Action (BOUGHT/SOLD) -> operation, Operation (C/P) -> option_type
        trade = FidelityTrade(
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
