#!/usr/bin/env python3
"""
IBKR Transaction History Options Parser

Parses options trades from IBKR Transaction History CSV exports.
This format is different from the IBKR Activity Statement format.

Symbol format: HOOD  260102P00112000 (SYMBOL + space + YYMMDD + P/C + strike*1000)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re

import pandas as pd

from brokers.basecsvprocessor import BaseCSVProcessor


logger = logging.getLogger(__name__)


class IBKRTxHistoryOptions(BaseCSVProcessor):
    """Parser for IBKR Transaction History format - Options trades"""

    # OCC symbol pattern: SYMBOL + spaces + YYMMDD + P/C + strike (8 digits)
    OCC_SYMBOL_PATTERN = re.compile(r"^([A-Z]+)\s+(\d{6})([PC])(\d{8})$")

    def __init__(self, fname: str, skipfooter: int = 0):
        skiprows = self._find_tx_history_section(fname)
        super().__init__(BaseCSVProcessor.Table.OPTIONS, fname, skiprows, skipfooter)

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

    def _parse_occ_symbol(self, symbol: str) -> tuple[str, str, str, str] | None:
        """
        Parse OCC option symbol format.

        Args:
            symbol: OCC symbol like "HOOD  260102P00112000"

        Returns:
            Tuple of (underlying, expiration, option_type, strike) or None if invalid
        """
        match = self.OCC_SYMBOL_PATTERN.match(symbol)
        if not match:
            return None

        underlying = match.group(1)
        date_str = match.group(2)  # YYMMDD
        option_type = "Put" if match.group(3) == "P" else "Call"
        strike_raw = match.group(4)  # 8 digits, last 3 are decimal places

        # Parse expiration: YYMMDD -> YYYY-MM-DD
        year = int("20" + date_str[:2])
        month = int(date_str[2:4])
        day = int(date_str[4:6])
        expiration = f"{year:04d}-{month:02d}-{day:02d}"

        # Parse strike: 00112000 -> 112.000 -> "112"
        strike = float(strike_raw) / 1000
        # Format as string, removing trailing zeros
        if strike == int(strike):
            strike_str = str(int(strike))
        else:
            strike_str = f"{strike:.2f}".rstrip("0").rstrip(".")

        return (underlying, expiration, option_type, strike_str)

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Rename columns based on Transaction History format
        # Columns: Transaction History, Header, Date, Account, Description, Transaction Type,
        #          Symbol, Quantity, Price, Gross Amount, Commission, Net Amount
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

        # Filter to options trades only (Buy/Sell with OCC symbols)
        # Options have symbols like "HOOD  260102P00112000"
        def is_option_symbol(symbol: str) -> bool:
            if pd.isna(symbol) or symbol == "-":
                return False
            return self.OCC_SYMBOL_PATTERN.match(str(symbol)) is not None

        df = df[df["Symbol"].apply(is_option_symbol)]

        if df.empty:
            logger.info("No option transactions found in file")
            return df

        # Filter to Buy/Sell transactions only (exclude assignments for options parser)
        df = df[df["Transaction Type"].isin(["Buy", "Sell"])]

        if df.empty:
            logger.info("No Buy/Sell option transactions found")
            return df

        # Parse OCC symbols into components
        parsed = df["Symbol"].apply(lambda s: self._parse_occ_symbol(str(s)))
        df["Symbol"] = parsed.apply(lambda x: x[0] if x else None)
        df["Expiration"] = parsed.apply(lambda x: x[1] if x else None)
        df["Operation"] = parsed.apply(lambda x: x[2] if x else None)  # Put/Call
        df["Strike"] = parsed.apply(lambda x: x[3] if x else None)

        # Determine action (STO/BTC/BTO/STC) based on transaction type and quantity
        def determine_action(row: pd.Series) -> str:
            tx_type = row["Transaction Type"]
            qty = float(row["Quantity"]) if not pd.isna(row["Quantity"]) else 0

            if tx_type == "Sell" and qty < 0:
                return "STO"  # Sell to Open
            elif tx_type == "Buy" and qty > 0:
                return "BTC"  # Buy to Close
            elif tx_type == "Buy" and qty > 0:
                return "BTO"  # Buy to Open (less common for wheel strategy)
            elif tx_type == "Sell" and qty < 0:
                return "STC"  # Sell to Close
            return "Unknown"

        df["Action"] = df.apply(determine_action, axis=1)

        # Convert date format (already YYYY-MM-DD)
        df.rename(columns={"Date": "Date"}, inplace=True)

        # Contracts (absolute value of quantity)
        df["Contracts"] = df["Quantity"].astype(float).abs().astype(int)

        # Price and Amount
        df.rename(columns={"Price": "Price", "Net Amount": "Amount"}, inplace=True)
        df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        return df


def main() -> None:
    """Test the parser with sample file"""
    import sys
    sys.path.insert(0, "src")

    parser = IBKRTxHistoryOptions("uploads/capt10l.U22809439.TRANSACTIONS.1Y.csv")
    parser.set_debug(True)
    df, start_date, end_date = parser.process()

    print(f"Options Range: {start_date} to {end_date}")
    print(f"Found {len(df)} option transactions")
    if not df.empty:
        print(df.to_string())


if __name__ == "__main__":
    main()
