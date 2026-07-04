#!/usr/bin/env python3
"""
IBKR Transaction History Deposits Parser

Parses deposit and withdrawal transactions from IBKR Transaction History CSV exports.
This format is different from the IBKR Activity Statement format.

Handles:
- Electronic Fund Transfer (deposits)
- Withdrawals
- Deposit Advance / Cancellation adjustments

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor


logger = logging.getLogger(__name__)


class IBKRTxHistoryDeposits(BaseCSVProcessor):
    """Parser for IBKR Transaction History format - Deposits/Withdrawals"""

    def __init__(self, fname: str, skipfooter: int = 0):
        skiprows = self._find_tx_history_section(fname)
        super().__init__(BaseCSVProcessor.Table.DEPOSITS, fname, skiprows, skipfooter)

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

        # Filter to deposit/withdrawal transactions
        deposit_types = ["Deposit", "Withdrawal"]
        df = df[df["Transaction Type"].isin(deposit_types)]

        if df.empty:
            logger.info("No deposit/withdrawal transactions found in file")
            return df

        # Determine action from transaction type
        df["Action"] = df["Transaction Type"].apply(
            lambda x: "Deposit" if x == "Deposit" else "Withdrawal"
        )

        # Amount from Net Amount
        df.rename(columns={"Net Amount": "Amount"}, inplace=True)
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        # For withdrawals, amount might be negative - we keep it as-is
        # The database/handler should handle negative amounts for withdrawals

        return df


def main() -> None:
    """Test the parser with sample file"""
    import sys
    sys.path.insert(0, "src")

    parser = IBKRTxHistoryDeposits("uploads/capt10l.U22809439.TRANSACTIONS.1Y.csv")
    parser.set_debug(True)
    df, start_date, end_date = parser.process()

    print(f"Deposits Range: {start_date} to {end_date}")
    print(f"Found {len(df)} deposit/withdrawal transactions")
    if not df.empty:
        print(df.to_string())


if __name__ == "__main__":
    main()
