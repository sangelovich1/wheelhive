#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

from db import Db
from providers.market_data_factory import MarketDataFactory


# Get a logger instance
logger = logging.getLogger(__name__)


class LookUp:
    """Lookup ticker prices using market data factory with automatic fallback."""

    def __init__(self):
        self.delisted = ["MSTX1"]

    def lookup_ticker(self, ticker: str) -> float:
        """
        Lookup current price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price as float, -1 if delisted, 0 if lookup fails
        """
        ticker = ticker.upper()

        if ticker in self.delisted:
            return -1

        try:
            # Factory handles provider selection and fallback automatically
            return MarketDataFactory.get_quote_with_fallback(ticker)
        except Exception as e:
            logger.warning(f"Unable to lookup ticker: {ticker}, error: {e}")
            return 0

if __name__ == "__main__":

    db = Db()
    rows = db.query("SELECT DISTINCT symbol from dividends")
    for row in rows:
        lu = LookUp()
        symbol = row[0]
        price = lu.lookup_ticker(symbol)
        print(f"Symbol {symbol}, price: {price}")
