#!/usr/bin/env python3
"""
IBKR Transaction History Dividends Parser

Parses dividend payments from IBKR Transaction History CSV exports.
This format is different from the IBKR Activity Statement format.

Handles:
- Payment in Lieu (dividends on borrowed/lent shares)
- Regular dividends (if present in this format)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor


logger = logging.getLogger(__name__)


class IBKRTxHistoryDividends(BaseCSVProcessor):
    """Parser for IBKR Transaction History format - Dividends"""

    def __init__(self, fname: str, skipfooter: int = 0):
        skiprows = self._find_tx_history_section(fname)
        super().__init__(BaseCSVProcessor.Table.DIVIDENDS, fname, skiprows, skipfooter)

    def _find_tx_history_section(self, fname: str) -> int:
        """Find the line number where the Transaction History section starts"""
        with open(fname) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith("Transaction History,Header,"):
                    logger.info(f"Found Transaction History section at line {i}")
                    return i
        logger.warning("Could not find Transaction History section, using skiprows=1")
        return 1

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Check expected columns
        expected_cols = ["Transaction History", "Header"]
        if not all(col in df.columns for col in expected_cols):
            logger.error(f"Missing expected columns. Found: {list(df.columns)}")
            return pd.DataFrame()

        # Filter to data rows only
        df = df[df["Transaction History"] == "Transaction History"]
        df = df[df["Header"] == "Data"]

        if df.empty:
            logger.info("No data rows found in Transaction History")
            return df

        # Filter to dividend transactions
        # "Payment in Lieu" is IBKR's dividend type in this format
        dividend_types = ["Payment in Lieu", "Dividend", "Cash Dividend"]
        df = df[df["Transaction Type"].isin(dividend_types)]

        if df.empty:
            logger.info("No dividend transactions found in file")
            return df

        # Extract symbol from Description field
        # Format: "IBKR(US45841N1072) Payment in Lieu of Dividend (Ordinary Dividend)"
        def extract_symbol(description: str) -> str | None:
            if pd.isna(description):
                return None
            # Try pattern: SYMBOL(CUSIP)
            match = re.match(r"^([A-Z]+)\(", str(description))
            if match:
                return match.group(1)
            return None

        df["Symbol"] = df["Description"].apply(extract_symbol)

        # Amount from Net Amount
        df.rename(columns={"Net Amount": "Amount"}, inplace=True)
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        # Filter out rows where we couldn't extract symbol
        df = df[df["Symbol"].notna()]

        return df


def main() -> None:
    """Test the parser with sample file"""
    import sys
    sys.path.insert(0, "src")

    parser = IBKRTxHistoryDividends("uploads/capt10l.U22809439.TRANSACTIONS.1Y.csv")
    parser.set_debug(True)
    df, start_date, end_date = parser.process()

    print(f"Dividends Range: {start_date} to {end_date}")
    print(f"Found {len(df)} dividend transactions")
    if not df.empty:
        print(df.to_string())


if __name__ == "__main__":
    main()
