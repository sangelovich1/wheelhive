#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import pandas as pd
from tabulate import tabulate

from db import Db
from dividends import Dividends
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)

class DFStats:
    def __init__(self, db: Db, username=None):
        logger.info("DFStats initialized ")
        self.db = db
    def load(self, username: str | None = None, account: str | None = None, guild_id: int | None = None):
        self.username = username

        # Build filter condition for account and/or guild_id if specified
        filter_conditions = []
        if account:
            filter_conditions.append(f'account="{account}"')
        if guild_id:
            filter_conditions.append(f"guild_id={guild_id}")

        filter_condition = " AND ".join(filter_conditions) if filter_conditions else None

        # Load data from the database into DataFrames
        self.trades_df = Trades(self.db).as_df(username, filter=filter_condition)
        self.shares_df = Shares(self.db).as_df(username, filter=filter_condition)
        self.dividends_df = Dividends(self.db).as_df(username, filter=filter_condition)

        # Insert YearMonth column into each DataFrame
        self.trades_df = self.__insert_yearmonth(self.trades_df)
        self.shares_df = self.__insert_yearmonth(self.shares_df)
        self.dividends_df = self.__insert_yearmonth(self.dividends_df)

    def __insert_yearmonth(self, df: pd.DataFrame) -> pd.DataFrame:
        """Insert a YearMonth column into the DataFrame based on the Date column."""
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df["YearMonth"] = df["Date"].dt.strftime("%Y-%m")
        else:
            logger.warning("No 'Date' column found in DataFrame.")
        return df

    def filter_by_year(self, year: int):
        self.trades_df= self.trades_df[self.trades_df["Date"].dt.year == year]
        self.shares_df= self.shares_df[self.shares_df["Date"].dt.year == year]
        self.dividends_df= self.dividends_df[self.dividends_df["Date"].dt.year == year]

    def filter_by_month(self, month: int):
        self.trades_df= self.trades_df[self.trades_df["Date"].dt.month == month]
        self.shares_df= self.shares_df[self.shares_df["Date"].dt.month == month]
        self.dividends_df= self.dividends_df[self.dividends_df["Date"].dt.month == month]

    def filter_by_date_range(self, start_date: str, end_date: str):
        """Filter DataFrames by date range (YYYY-MM-DD format)"""
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        self.trades_df = self.trades_df[(self.trades_df["Date"] >= start) & (self.trades_df["Date"] <= end)]
        self.shares_df = self.shares_df[(self.shares_df["Date"] >= start) & (self.shares_df["Date"] <= end)]
        self.dividends_df = self.dividends_df[(self.dividends_df["Date"] >= start) & (self.dividends_df["Date"] <= end)]


    def dump(self):
        self.trades_df.to_csv("df_stats_trades_df.csv", index=False)
        self.shares_df.to_csv("df_stats_shares_df.csv", index=False)
        self.dividends_df.to_csv("df_stats_dividends_df.csv", index=False)


    def dividend_by_yearmonth(self):
        df = self.dividends_df.copy()

        df = pd.pivot_table(df, values="Amount", index=["YearMonth"],
                            aggfunc="sum", fill_value=0, margins=False).reset_index()

        # Make sure all columns are strings not tuples
        df.columns = ["_".join(col) if isinstance(col, tuple) else col for col in df.columns]

        # Rename 'YearMonth' to 'Date'
        df.rename(columns={"YearMonth": "Date", "Amount": "Dividends"}, inplace=True)
        # df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%m/%y')

        return df

    def options_by_yearmonth(self):
        df = self.trades_df.copy()

        df = pd.pivot_table(df, values="Total", columns=["Operation"], index=["YearMonth"],
                            aggfunc="sum", fill_value=0, margins=False).reset_index()

        for c in ["STO", "BTC", "BTO", "STC"]:
            if c not in df.columns:
                df[c] =  0.0


        # Make sure all columns are strings not tuples
        df.columns = ["_".join(col) if isinstance(col, tuple) else col for col in df.columns]

        # Rename 'YearMonth' to 'Date'
        df.rename(columns={"YearMonth": "Date"}, inplace=True)

        # Calculate Premium
        df["Premium"] = df["STO"] + df["BTC"] + df["BTO"] + df["STC"]

        df = df[["Date", "STO", "BTC", "BTO", "STC", "Premium"]]

        return df

    def options_by_symbol(self):
        df = self.trades_df.copy()
        df = pd.pivot_table(df, values="Total", columns=["Operation"], index=["Symbol"],
                            aggfunc="sum", fill_value=0, margins=False).reset_index()

        for c in ["STO", "BTC", "BTO", "STC"]:
            if c not in df.columns:
                df[c] =  0.0

        df.columns = ["_".join(col) if isinstance(col, tuple) else col for col in df.columns]
        # Calculate Premium
        df["Premium"] = df["STO"] + df["BTC"] + df["BTO"] + df["STC"]

        return df[["Symbol", "STO", "BTC", "BTO", "STC", "Premium"]]


    def format_currency(self, df: pd.DataFrame, columns: list) -> pd.DataFrame:
        """Format specified columns in the DataFrame to currency style."""
        def format_val(x):
            if x < 0:
                return f"(${abs(x):,.0f})"
            return f"${x:,.0f}"

        for col in columns:
            if col in df.columns:
                df[col] = df[col].apply(format_val)
        return df


    def compute_totals(self, df: pd.DataFrame) -> pd.DataFrame:
        totals = {}
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                totals[col] = df[col].sum()
            else:
                totals[col] = " "
        totals[df.columns[0]] = "Total"
        # Convert totals to a DataFrame for better formatting
        summary_row = pd.DataFrame([totals], columns=df.columns)
        df = pd.concat([df, summary_row], ignore_index=True)
        return df

    def merge_dataframes(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        """Merge two DataFrames on 'Date' and fill missing values with 0."""
        merged_df = pd.merge(df1, df2, on="Date", how="outer")
        merged_df.fillna(0, inplace=True)
        return merged_df

    def as_table(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to a string table format."""
        if df.empty:
            return "No data available."
        # Convert DataFrame to string for display
        table_str = tabulate(df, headers=df.columns.tolist(), stralign="right", showindex=False)
        return table_str


    # def shares_detail_by_yearmonth(self, margins=False):
    #     df = self.shares_df.copy()

    #     df['Date'] = pd.to_datetime(df['Date'])
    #     df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')

    #     df = pd.pivot_table(df, values='Amount', columns=['Symbol'], index=['YearMonth'],
    #                         aggfunc='sum', fill_value=0, margins=margins)
    #     return df

    def my_stats(self) -> str:
        """Generate a summary of trades and dividends for the current year."""
        year = pd.to_datetime("today").year
        self.filter_by_year(year)

        df1 = self.options_by_yearmonth()
        df2 = self.dividend_by_yearmonth()
        df3 = self.merge_dataframes(df1, df2)
        df3.sort_values(by="Date", inplace=True)
        df3["Date"] = pd.to_datetime(df3["Date"]).dt.strftime("%m/%y")
        df3 = self.compute_totals(df3)
        df3 = self.format_currency(df3, ["STO", "BTC", "BTO", "STC", "Premium", "Dividends"])
        return self.as_table(df3)

    def my_symbol_stats(self) -> str:
        """Generate a summary of trades per symbol."""
        year = pd.to_datetime("today").year
        month = pd.to_datetime("today").month
        self.filter_by_year(year)
        self.filter_by_month(month)
        df = self.options_by_symbol()

        df = self.compute_totals(df)
        df = self.format_currency(df, ["STO", "BTC", "BTO", "STC", "Premium"])
        return self.as_table(df)

    def symbol_stats_as_dict(self) -> list:
        """
        Convert symbol statistics to list of dictionaries for JSON serialization.

        Returns raw numeric values (not formatted).
        Follows the standardized data export pattern (as_df, as_dict, as_table).

        Returns:
            List of dicts with symbol stats: [{"symbol": "AAPL", "sto": 1000, ...}, ...]
        """
        df = self.options_by_symbol()

        if df.empty:
            return []

        # Convert to lowercase column names for JSON
        df_dict = df.copy()
        df_dict.columns = [col.lower() for col in df_dict.columns]

        return df_dict.to_dict("records")  # type: ignore[no-any-return]

    def as_dict(self) -> dict:
        """
        Convert stats to dictionary format for JSON serialization.
        Returns monthly breakdown with totals (numeric values preserved).
        """
        df_options = self.options_by_yearmonth()
        df_dividends = self.dividend_by_yearmonth()
        df_merged = self.merge_dataframes(df_options, df_dividends)
        df_merged.sort_values(by="Date", inplace=True)

        # Calculate totals
        totals = {
            "Date": "Total",
            "STO": float(df_merged["STO"].sum()),
            "BTC": float(df_merged["BTC"].sum()),
            "BTO": float(df_merged["BTO"].sum()),
            "STC": float(df_merged["STC"].sum()),
            "Premium": float(df_merged["Premium"].sum()),
            "Dividends": float(df_merged["Dividends"].sum())
        }

        return {
            "monthly": df_merged.to_dict("records"),
            "totals": totals
        }


def main():
    db = Db()
    df_stats = DFStats(db)
    df_stats.load("sangelovich")
    print(df_stats.my_stats())
    print(df_stats.my_symbol_stats())




if __name__ == "__main__":
    main()




