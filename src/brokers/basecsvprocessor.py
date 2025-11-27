#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import os
from enum import Enum

import pandas as pd


# Module-level logger
logger = logging.getLogger(__name__)


class BaseCSVProcessor:

    class Table(Enum):
        OPTIONS = (1, ["Action", "Symbol", "Date", "Expiration", "Contracts", "Strike", "Operation", "Price", "Amount"])
        SHARES = (2, ["Date", "Action", "Symbol", "Price", "Quantity", "Amount"])
        DIVIDENDS = (3, ["Date", "Symbol", "Amount"])
        DEPOSITS = (4, ["Date", "Action", "Amount"])

        def __init__(self, value, required_columns):
            self._value_ = value  # Assign the actual enum value
            self.required_columns = required_columns

    def __init__(self, table:  Table, fname: str, skiprows: int = 0, skipfooter: int = 0):
        self.table = table
        self.file_path = fname
        self.skiprows = skiprows
        self.skipfooter = skipfooter
        self.debug = False

    def set_debug(self, debug: bool):
        self.debug = debug

    def read_csv(self) -> pd.DataFrame:
        df = pd.read_csv(self.file_path, skiprows=self.skiprows, skipfooter=self.skipfooter, engine="python")
        return df

    def cvs_req_cols(self, df, required_cols: list[str]):
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            logger.error(f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
            raise ValueError(f"Required columns: {required_cols}")

    def clean(self, df) -> pd.DataFrame:
        return df

    def set_columns(self, df) -> pd.DataFrame:
        df = df[self.table.required_columns]
        return df

    def validate(self, df):
        # Validate date colums are formatted correctly
        logger.debug(f"Validating {len(df)} rows with columns: {list(df.columns)}")
        df = df.copy()
        try:
            df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="raise")
            if "Expiration" in df.columns:
                df["Expiration"] = pd.to_datetime(df["Expiration"], format="%Y-%m-%d", errors="raise")
        except Exception as e:
            logger.error(f"Date validation failed: {e}")
            raise

        # Check float columns
        float_columns = ["Price", "Amount", "Strike", "Quantity"]
        for col in float_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="raise")
                except Exception as e:
                    logger.error(f"Numeric validation failed for column '{col}': {e}")
                    raise

        # Check integer columns
        int_columns = ["Contracts"]
        for col in int_columns:
            if col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors="raise", downcast="integer")
                except Exception as e:
                    logger.error(f"Integer validation failed for column '{col}': {e}")
                    raise

        # Check that Contracts  are non-negative
        abs_columns = ["Contracts"]
        for col in abs_columns:
            if col in df.columns:
                if (df[col] < 0).any():
                    logger.error(f"Column '{col}' contains negative values")
                    raise ValueError(f"Column '{col}' contains negative values, which is not allowed.")




    def currency_to_float(self, col: pd.Series) -> pd.Series:
        col = col.str.replace(")", "", regex=False)
        col = col.str.replace("$", "", regex=False)
        col = col.str.replace(",", "", regex=False)
        col = col.str.replace("(", "-", regex=False)
        col = col.astype(float)
        return col

    def to_db_date(self, col: pd.Series, input_format: str) -> pd.Series:
        col = pd.to_datetime(col, format=input_format)
        col = col.dt.strftime("%Y-%m-%d")
        return col


    def process(self) -> tuple[pd.DataFrame, str | None, str | None]:
        basename = os.path.basename(self.file_path)
        basename, _ = os.path.splitext(basename)

        logger.info(f"Processing CSV file: {self.file_path}")

        # Load the csv
        df = self.read_csv()
        logger.debug(f"Loaded {len(df)} rows with {len(df.columns)} columns")
        if self.debug:
            df.to_csv(f"{basename}_load.csv", index=False)

        # Trim whitespace
        df = df.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

        # Cleanup the dataframe
        df = self.clean(df)
        if self.debug:
            df.to_csv(f"{basename}_clean.csv", index=False)

        # If DataFrame is empty after cleaning, return early
        if df.empty:
            logger.info("No transactions to process after cleaning")
            return df, None, None

        # Set the required columns
        df = self.set_columns(df)
        logger.debug(f"Set columns to required: {list(df.columns)}")

        # Validate data adheres to standards
        self.validate(df)
        logger.debug("Validation passed")

        start_date = df["Date"].min()
        end_date = df["Date"].max()
        logger.info(f"Processed {len(df)} rows from {start_date} to {end_date}")
        return df, start_date, end_date
