#!/usr/bin/env python3
"""
IBKR Transaction History Shares Parser

Parses stock trades from IBKR Transaction History CSV exports.
This format is different from the IBKR Activity Statement format.

Handles:
- Buy/Sell stock transactions
- Assignments (options exercised/assigned)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor


logger = logging.getLogger(__name__)


class IBKRTxHistoryShares(BaseCSVProcessor):
    """Parser for IBKR Transaction History format - Stock trades"""

    # OCC symbol pattern to identify options (exclude these)
    OCC_SYMBOL_PATTERN = re.compile(r"^([A-Z]+)\s+(\d{6})([PC])(\d{8})$")

    def __init__(self, fname: str, skipfooter: int = 0):
        skiprows = self._find_tx_history_section(fname)
        super().__init__(BaseCSVProcessor.Table.SHARES, fname, skiprows, skipfooter)

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

    def _is_option_symbol(self, symbol: str) -> bool:
        """Check if symbol is an OCC option symbol"""
        if pd.isna(symbol) or symbol == "-":
            return False
        return self.OCC_SYMBOL_PATTERN.match(str(symbol)) is not None

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

        # Filter to stock transactions:
        # - Buy/Sell with non-option symbols
        # - Assignment transactions
        def is_stock_transaction(row: pd.Series) -> bool:
            tx_type = row["Transaction Type"]
            symbol = row["Symbol"]

            # Assignment is always a stock transaction
            if tx_type == "Assignment":
                return True

            # Buy/Sell with non-option symbol
            if tx_type in ["Buy", "Sell"]:
                return not self._is_option_symbol(symbol)

            return False

        df = df[df.apply(is_stock_transaction, axis=1)]

        if df.empty:
            logger.info("No share transactions found in file")
            return df

        # For assignments, extract ticker from Description
        # e.g., "Sell -100 RIVIAN AUTOMOTIVE INC-A (Assignment)" -> RIVN (from Symbol column)
        # Symbol already contains the ticker for assignments

        # Determine action based on transaction type and quantity
        def determine_action(row: pd.Series) -> str:
            tx_type = row["Transaction Type"]
            qty = float(row["Quantity"]) if not pd.isna(row["Quantity"]) else 0

            if tx_type == "Assignment":
                # Assignment selling shares (assigned on put)
                return "Sell" if qty < 0 else "Buy"
            elif tx_type == "Buy":
                return "Buy"
            elif tx_type == "Sell":
                return "Sell"
            return "Unknown"

        df["Action"] = df.apply(determine_action, axis=1)

        # Clean up quantity (absolute value)
        df["Quantity"] = df["Quantity"].astype(float).abs()

        # Price and Amount
        df.rename(columns={"Net Amount": "Amount"}, inplace=True)
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        return df


def main() -> None:
    """Test the parser with sample file"""
    import sys
    sys.path.insert(0, "src")

    parser = IBKRTxHistoryShares("uploads/capt10l.U22809439.TRANSACTIONS.1Y.csv")
    parser.set_debug(True)
    df, start_date, end_date = parser.process()

    print(f"Shares Range: {start_date} to {end_date}")
    print(f"Found {len(df)} share transactions")
    if not df.empty:
        print(df.to_string())


if __name__ == "__main__":
    main()
