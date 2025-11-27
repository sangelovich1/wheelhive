"""
Market Data Provider Abstract Base Class

Defines the interface for market data providers (YFinance, Finnhub, etc.)
This abstraction allows easy switching between data providers to handle rate limiting
or service outages.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class MarketDataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def get_stock_info(self, ticker: str) -> dict[str, Any]:
        """
        Get current stock information.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL', 'MSFT')

        Returns:
            Dictionary with stock information:
            {
                'symbol': str,
                'current_price': float,
                'previous_close': float,
                'open': float,
                'day_high': float,
                'day_low': float,
                'volume': int,
                'market_cap': float,
                'pe_ratio': float,
                'dividend_yield': float,
                '52_week_high': float,
                '52_week_low': float,
                'avg_volume': int,
                'beta': float,
                'company_name': str
            }

        Raises:
            Exception: If data retrieval fails
        """

    @abstractmethod
    def get_historical_data(
        self,
        ticker: str,
        period: str = "3mo",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical OHLCV price data.

        Args:
            ticker: Stock ticker symbol
            period: Time period (e.g., '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            interval: Data interval (e.g., '1m', '5m', '1h', '1d', '1wk', '1mo')

        Returns:
            DataFrame with columns: Date, Open, High, Low, Close, Volume
            Index: DatetimeIndex

        Raises:
            Exception: If data retrieval fails
        """

    @abstractmethod
    def get_news(self, ticker: str, count: int = 10) -> list[dict[str, Any]]:
        """
        Get latest news for a ticker.

        Args:
            ticker: Stock ticker symbol
            count: Number of news articles to retrieve

        Returns:
            List of news articles, each with:
            {
                'headline': str,
                'summary': str,
                'source': str,
                'url': str,
                'published': str (ISO 8601 datetime),
                'sentiment': Optional[str]  # 'positive', 'negative', 'neutral' if available
            }

        Raises:
            Exception: If data retrieval fails
        """

    @abstractmethod
    def get_quote(self, ticker: str) -> float:
        """
        Get current price for a ticker (lightweight alternative to get_stock_info).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price as float

        Raises:
            Exception: If data retrieval fails
        """

    @abstractmethod
    def get_options_chain(self, ticker: str) -> dict[str, Any] | None:
        """
        Get options chain data for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with options chain data in standardized format:
            {
                'data': [
                    {
                        'expirationDate': 'YYYY-MM-DD',
                        'options': {
                            'CALL': [
                                {
                                    'strike': float,
                                    'bid': float,
                                    'ask': float,
                                    'delta': float,
                                    'theta': float,
                                    'gamma': float,
                                    'impliedVolatility': float,  # percentage (e.g., 50.0 for 50%)
                                    'openInterest': int,
                                    'volume': int,
                                    'contractName': str
                                },
                                ...
                            ],
                            'PUT': [...]
                        }
                    },
                    ...
                ]
            }
            Returns None if options data is unavailable

        Raises:
            Exception: If data retrieval fails
        """
