"""
Finnhub Market Data Provider

Implementation of MarketDataProvider using the Finnhub API.
Provides stock quotes, historical data, and news from Finnhub.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

import constants as const
from providers.market_data_provider import MarketDataProvider


logger = logging.getLogger(__name__)


class FinnhubProvider(MarketDataProvider):
    """Market data provider using Finnhub API."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str | None = None):
        """
        Initialize Finnhub provider.

        Args:
            api_key: Finnhub API key (defaults to const.FINNHUB_API_KEY)
        """
        self.api_key = api_key or const.FINNHUB_API_KEY
        if not self.api_key:
            raise ValueError("Finnhub API key not configured")
        logger.info("Initialized Finnhub market data provider")

    def _make_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Make HTTP request to Finnhub API with error handling.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            Exception: If request fails
        """
        params["token"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        except requests.exceptions.Timeout:
            logger.error(f"Finnhub API timeout for {endpoint}")
            raise Exception("Finnhub API timeout")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                logger.error("Finnhub API rate limit exceeded")
                raise Exception("Finnhub API rate limit exceeded")
            logger.error(f"Finnhub API HTTP error: {e}")
            raise Exception(f"Finnhub API error: {e}")
        except Exception as e:
            logger.error(f"Finnhub API request failed: {e}", exc_info=True)
            raise Exception(f"Finnhub API request failed: {e}")

    def get_stock_info(self, ticker: str) -> dict[str, Any]:
        """
        Get current stock information from Finnhub.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with stock information

        Raises:
            Exception: If data retrieval fails
        """
        try:
            # Get quote data
            quote_data = self._make_request("quote", {"symbol": ticker})

            # Get company profile for additional info
            profile_data = self._make_request("stock/profile2", {"symbol": ticker})

            # Combine data
            result = {
                "symbol": ticker.upper(),
                "current_price": quote_data.get("c", 0.0),  # Current price
                "previous_close": quote_data.get("pc", 0.0),  # Previous close
                "open": quote_data.get("o", 0.0),  # Open price
                "day_high": quote_data.get("h", 0.0),  # High price
                "day_low": quote_data.get("l", 0.0),  # Low price
                "volume": 0,  # Not available in quote endpoint
                "market_cap": profile_data.get("marketCapitalization", 0) * 1_000_000 if profile_data.get("marketCapitalization") else 0,  # Convert from millions
                "pe_ratio": 0.0,  # Not available in free tier
                "dividend_yield": 0.0,  # Not available in free tier
                "52_week_high": quote_data.get("h", 0.0),  # Using day high as approximation
                "52_week_low": quote_data.get("l", 0.0),  # Using day low as approximation
                "avg_volume": 0,  # Not available in free tier
                "beta": 0.0,  # Not available in free tier
                "company_name": profile_data.get("name", ticker)
            }

            logger.debug(f"Retrieved stock info for {ticker}: price=${result['current_price']}")
            return result

        except Exception as e:
            logger.error(f"Error fetching stock info for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve stock info for {ticker}: {e}")

    def get_historical_data(
        self,
        ticker: str,
        period: str = "3mo",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical OHLCV price data from Finnhub.

        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            interval: Data interval (1d, 1wk, 1mo) - Finnhub uses resolution parameter

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index: DatetimeIndex

        Raises:
            Exception: If data retrieval fails
        """
        try:
            # Convert period to date range
            end_date = datetime.now()
            period_map = {
                "1d": 1,
                "5d": 5,
                "1mo": 30,
                "3mo": 90,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
                "10y": 3650,
                "ytd": (end_date - datetime(end_date.year, 1, 1)).days,
                "max": 3650  # Default to 10 years for max
            }
            days_back = period_map.get(period, 90)
            start_date = end_date - timedelta(days=days_back)

            # Convert interval to Finnhub resolution
            resolution_map = {
                "1m": "1",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "60m": "60",
                "1h": "60",
                "1d": "D",
                "1wk": "W",
                "1mo": "M"
            }
            resolution = resolution_map.get(interval, "D")

            # Make API request
            params = {
                "symbol": ticker,
                "resolution": resolution,
                "from": int(start_date.timestamp()),
                "to": int(end_date.timestamp())
            }
            data = self._make_request("stock/candle", params)

            # Check if data is valid
            if data.get("s") != "ok":
                raise Exception(f"No historical data available for {ticker}")

            # Convert to DataFrame
            df = pd.DataFrame({
                "Open": data["o"],
                "High": data["h"],
                "Low": data["l"],
                "Close": data["c"],
                "Volume": data["v"]
            })

            # Add datetime index
            df.index = pd.to_datetime(data["t"], unit="s")
            df.index.name = "Date"

            if df.empty:
                raise Exception(f"No historical data available for {ticker}")

            logger.debug(f"Retrieved {len(df)} bars of historical data for {ticker} (period={period}, interval={interval})")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve historical data for {ticker}: {e}")

    def get_news(self, ticker: str, count: int = 10) -> list[dict[str, Any]]:
        """
        Get latest news for a ticker from Finnhub.

        Args:
            ticker: Stock ticker symbol
            count: Number of news articles to retrieve (max 50)

        Returns:
            List of news articles

        Raises:
            Exception: If data retrieval fails
        """
        try:
            # Finnhub company news requires date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Last 7 days

            params = {
                "symbol": ticker,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d")
            }
            news_response = self._make_request("company-news", params)

            if not news_response:
                logger.warning(f"No news available for {ticker}")
                return []

            # API returns a list of articles
            news_data: list[Any] = news_response if isinstance(news_response, list) else []

            # Format news to match interface
            result = []
            for article in news_data[:count]:
                result.append({
                    "headline": article.get("headline", "No title"),
                    "summary": article.get("summary", ""),
                    "source": article.get("source", "Unknown"),
                    "url": article.get("url", ""),
                    "published": datetime.fromtimestamp(article.get("datetime", 0)).isoformat(),
                    "sentiment": article.get("sentiment")  # Finnhub may provide sentiment
                })

            logger.debug(f"Retrieved {len(result)} news articles for {ticker}")
            return result

        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve news for {ticker}: {e}")

    def get_quote(self, ticker: str) -> float:
        """
        Get current price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price as float

        Raises:
            Exception: If data retrieval fails
        """
        try:
            quote_data = self._make_request("quote", {"symbol": ticker})
            price = quote_data.get("c", 0.0)  # Current price

            logger.debug(f"Retrieved quote for {ticker}: ${price}")
            price_result: float = float(price)
            return price_result

        except Exception as e:
            logger.error(f"Error fetching quote for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve quote for {ticker}: {e}")

    def get_options_chain(self, ticker: str) -> dict[str, Any] | None:
        """
        Get options chain data from Finnhub.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with options chain data (Finnhub native format)
            Returns None if no options data available

        Raises:
            Exception: If data retrieval fails
        """
        try:
            # Finnhub uses stock/option-chain endpoint
            params = {"symbol": ticker}
            data = self._make_request("stock/option-chain", params)

            # Finnhub returns data in the exact format we need
            # No transformation required
            if data and "data" in data:
                logger.debug(f"Retrieved options chain for {ticker} ({len(data.get('data', []))} expirations)")
                return data
            logger.warning(f"No options chain data available for {ticker}")
            return None

        except Exception as e:
            logger.error(f"Error fetching options chain for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve options chain for {ticker}: {e}")
