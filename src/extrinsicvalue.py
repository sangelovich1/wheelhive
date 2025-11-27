#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any

from tabulate import tabulate

from providers.market_data_factory import MarketDataFactory
from util import parse_string


# Get a logger instance
logger = logging.getLogger(__name__)


class ExtrinsicValue:

    def lookup_ticker(self, ticker: str) -> None:
        """
        Lookup ticker information using market data factory.

        Args:
            ticker: Stock ticker symbol

        Raises:
            KeyError: If ticker lookup fails
        """
        self.ticker = ticker.upper()

        try:
            # Get stock info with automatic fallback
            info = MarketDataFactory.get_stock_info_with_fallback(self.ticker)

            # Use current price as approximation for bid/ask if not available
            self.bid = info.get("current_price", 0.0)
            self.ask = info.get("current_price", 0.0)
            self.ave = info["current_price"]
            self.previousClose = info["previous_close"]

        except Exception as e:
            logger.error(f"Failed to lookup ticker {ticker}: {e}")
            raise KeyError(f"Invalid ticker symbol: {ticker}")


    def extrinsic_value(self, strike):
        intrinsic_value = abs(self.previousClose - strike)
        extrinsic_value = self.ave - intrinsic_value
        return intrinsic_value, extrinsic_value

    def calculate(self, ticker :str, strikes :str) -> tuple[bool, str]:

        try:
            self.lookup_ticker(ticker)
        except KeyError:
            # logging.info(f"Error: {e}")
            return False, "Unable to download ticker: {ticker}"

        try:
            self.STRIKES = parse_string(strikes)
        except ValueError as e:
            logger.error(f"Error parsing strikes: {e}")
            return False, "Unable to parse input strikes: {strikes}"

        header = list()
        header.append(["Ticker", self.ticker])
        header.append(["Bid", f"${self.bid:,.2f}"])
        header.append(["Ask", f"${self.ask:,.2f}"])
        header.append(["Average", f"${self.ave:,.2f}"])
        header.append(["Previous Close", f"${self.previousClose:,.2f}"])
        header_str = tabulate(header,  stralign="right")

        table = list()
        table.append(["Strike", "Intrinsic Value", "Extrinsic Value"])
        for strike in self.STRIKES:
            iv, ev = self.extrinsic_value(strike)
            table.append([str(strike), f"${iv:,.2f}", f"${ev:,.2f}"])

        table_str = tabulate(table, headers="firstrow",  stralign="right")
        logger.info(f"{header_str}\n{table_str}")

        return True, f"{header_str}\n{table_str}"

    def as_dict(self, ticker: str, strikes: str) -> dict[str, Any]:
        """
        Calculate extrinsic value and return as structured dictionary for JSON serialization.

        Follows the standardized data export pattern (as_df, as_dict, as_table).

        Args:
            ticker: Stock ticker symbol
            strikes: Comma-separated strike prices (e.g., "10,11,12")

        Returns:
            Dictionary with ticker info and strike calculations:
            {
                "ticker": str,
                "bid": float,
                "ask": float,
                "average": float,
                "previous_close": float,
                "strikes": [
                    {"strike": float, "intrinsic_value": float, "extrinsic_value": float},
                    ...
                ]
            }

        Raises:
            KeyError: If ticker lookup fails
            ValueError: If strikes string is invalid
        """
        self.lookup_ticker(ticker)
        self.STRIKES = parse_string(strikes)

        strikes_data: list[dict[str, float]] = []
        for strike in self.STRIKES:
            iv, ev = self.extrinsic_value(strike)
            strikes_data.append({
                "strike": float(strike),
                "intrinsic_value": round(iv, 2),
                "extrinsic_value": round(ev, 2)
            })

        return {
            "ticker": self.ticker,
            "bid": round(self.bid, 2),
            "ask": round(self.ask, 2),
            "average": round(self.ave, 2),
            "previous_close": round(self.previousClose, 2),
            "strikes": strikes_data
        }


