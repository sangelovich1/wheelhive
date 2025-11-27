"""
YFinance Market Data Provider

Implementation of MarketDataProvider using the yfinance library.
Provides stock quotes, historical data, and news from Yahoo Finance.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf

from providers.market_data_provider import MarketDataProvider


logger = logging.getLogger(__name__)


def _safe_int(value, default: int = 0) -> int:
    """Safely convert value to int, handling NaN and None."""
    if pd.isna(value):
        return int(default)
    try:
        return int(value)
    except (ValueError, TypeError):
        return int(default)


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float, handling NaN and None."""
    if pd.isna(value):
        return float(default)
    try:
        return float(value)
    except (ValueError, TypeError):
        return float(default)


class YFinanceProvider(MarketDataProvider):
    """Market data provider using Yahoo Finance (yfinance library)."""

    def __init__(self):
        """Initialize YFinance provider."""
        logger.info("Initialized YFinance market data provider")

    def get_stock_info(self, ticker: str) -> dict[str, Any]:
        """
        Get current stock information from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with stock information

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Extract relevant fields with fallback values
            result = {
                "symbol": ticker.upper(),
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
                "previous_close": info.get("previousClose", 0.0),
                "open": info.get("open") or info.get("regularMarketOpen", 0.0),
                "day_high": info.get("dayHigh") or info.get("regularMarketDayHigh", 0.0),
                "day_low": info.get("dayLow") or info.get("regularMarketDayLow", 0.0),
                "volume": info.get("volume") or info.get("regularMarketVolume", 0),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0.0),
                "dividend_yield": info.get("dividendYield", 0.0),
                "52_week_high": info.get("fiftyTwoWeekHigh", 0.0),
                "52_week_low": info.get("fiftyTwoWeekLow", 0.0),
                "avg_volume": info.get("averageVolume", 0),
                "beta": info.get("beta", 0.0),
                "company_name": info.get("longName") or info.get("shortName", ticker)
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
        Get historical OHLCV price data from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1d, 5d, 1wk, 1mo, 3mo)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index: DatetimeIndex

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)

            if df.empty:
                raise Exception(f"No historical data available for {ticker}")

            # Ensure we have the standard OHLCV columns
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            for col in required_cols:
                if col not in df.columns:
                    raise Exception(f"Missing required column '{col}' in historical data")

            logger.debug(f"Retrieved {len(df)} bars of historical data for {ticker} (period={period}, interval={interval})")
            return df[required_cols]

        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve historical data for {ticker}: {e}")

    def get_news(self, ticker: str, count: int = 10) -> list[dict[str, Any]]:
        """
        Get latest news for a ticker from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol
            count: Number of news articles to retrieve

        Returns:
            List of news articles

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            news = stock.news

            if not news:
                logger.warning(f"No news available for {ticker}")
                return []

            # Format news to match interface
            # Yahoo Finance API structure: articles have nested 'content' field (as of v0.2.66)
            result = []
            for article in news[:count]:
                # Check if article has nested content structure (new API format)
                if "content" in article and isinstance(article["content"], dict):
                    content = article["content"]
                    result.append({
                        "headline": content.get("title", "No title"),
                        "summary": content.get("summary", ""),
                        "source": content.get("provider", {}).get("displayName", "Unknown"),
                        "url": content.get("canonicalUrl", {}).get("url", ""),
                        "published": content.get("pubDate", "")
                    })
                else:
                    # Fallback to old structure (direct fields)
                    result.append({
                        "headline": article.get("title", "No title"),
                        "summary": article.get("summary", ""),
                        "source": article.get("publisher", "Unknown"),
                        "url": article.get("link", ""),
                        "published": datetime.fromtimestamp(article.get("providerPublishTime", 0)).isoformat()
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
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)

            if price == 0.0:
                # Fallback: try to get from history
                hist = stock.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])

            logger.debug(f"Retrieved quote for {ticker}: ${price}")
            return float(price)

        except Exception as e:
            logger.error(f"Error fetching quote for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve quote for {ticker}: {e}")

    def get_options_chain(self, ticker: str) -> dict[str, Any] | None:
        """
        Get options chain data from Yahoo Finance.

        Transforms yfinance format to match Finnhub format for compatibility.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with options chain data (normalized to Finnhub format)
            Returns None if no options data available

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options  # List of expiration dates

            if not expirations:
                logger.warning(f"No options expiration dates available for {ticker}")
                return None

            # Build normalized data structure
            normalized_data = []

            for exp_date in expirations:
                try:
                    chain = stock.option_chain(exp_date)

                    # Transform calls DataFrame to list of dicts
                    calls_list = []
                    for _, row in chain.calls.iterrows():
                        calls_list.append({
                            "strike": _safe_float(row.get("strike", 0.0)),
                            "bid": _safe_float(row.get("bid", 0.0)),
                            "ask": _safe_float(row.get("ask", 0.0)),
                            "delta": 0.0,  # yfinance doesn't provide Greeks
                            "theta": 0.0,  # Default to 0.0
                            "gamma": 0.0,  # Default to 0.0
                            "impliedVolatility": _safe_float(row.get("impliedVolatility", 0.0)) * 100,  # Convert to percentage
                            "openInterest": _safe_int(row.get("openInterest", 0)),
                            "volume": _safe_int(row.get("volume", 0)),
                            "contractName": str(row.get("contractSymbol", ""))
                        })

                    # Transform puts DataFrame to list of dicts
                    puts_list = []
                    for _, row in chain.puts.iterrows():
                        puts_list.append({
                            "strike": _safe_float(row.get("strike", 0.0)),
                            "bid": _safe_float(row.get("bid", 0.0)),
                            "ask": _safe_float(row.get("ask", 0.0)),
                            "delta": 0.0,  # yfinance doesn't provide Greeks
                            "theta": 0.0,  # Default to 0.0
                            "gamma": 0.0,  # Default to 0.0
                            "impliedVolatility": _safe_float(row.get("impliedVolatility", 0.0)) * 100,  # Convert to percentage
                            "openInterest": _safe_int(row.get("openInterest", 0)),
                            "volume": _safe_int(row.get("volume", 0)),
                            "contractName": str(row.get("contractSymbol", ""))
                        })

                    normalized_data.append({
                        "expirationDate": exp_date,
                        "options": {
                            "CALL": calls_list,
                            "PUT": puts_list
                        }
                    })

                except Exception as e:
                    logger.warning(f"Failed to fetch options for {ticker} expiration {exp_date}: {e}")
                    continue

            if not normalized_data:
                logger.warning(f"No options chain data could be retrieved for {ticker}")
                return None

            logger.debug(f"Retrieved options chain for {ticker} ({len(normalized_data)} expirations)")
            return {"data": normalized_data}

        except Exception as e:
            logger.error(f"Error fetching options chain for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve options chain for {ticker}: {e}")

    # Fundamental Data Methods (not in MarketDataProvider base class)
    # These are YFinance-specific extensions for company fundamentals

    def get_dividends(self, ticker: str) -> pd.DataFrame:
        """
        Get dividend history for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with dividend history (Date, Dividends)

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            dividends = stock.dividends

            if dividends.empty:
                logger.warning(f"No dividend data available for {ticker}")
                return pd.DataFrame(columns=["Date", "Dividends"])

            # Convert to DataFrame with named columns
            df = dividends.to_frame("Dividends")
            df.index.name = "Date"
            df.reset_index(inplace=True)

            logger.debug(f"Retrieved {len(df)} dividend records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching dividends for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve dividends for {ticker}: {e}")

    def get_splits(self, ticker: str) -> pd.DataFrame:
        """
        Get stock split history for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with split history (Date, Stock Splits)

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            splits = stock.splits

            if splits.empty:
                logger.warning(f"No split data available for {ticker}")
                return pd.DataFrame(columns=["Date", "Stock Splits"])

            # Convert to DataFrame with named columns
            df = splits.to_frame("Stock Splits")
            df.index.name = "Date"
            df.reset_index(inplace=True)

            logger.debug(f"Retrieved {len(df)} split records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching splits for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve splits for {ticker}: {e}")

    def get_actions(self, ticker: str) -> pd.DataFrame:
        """
        Get combined dividend and split history for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with dividend and split history (Date, Dividends, Stock Splits)

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            actions = stock.actions

            if actions.empty:
                logger.warning(f"No actions data available for {ticker}")
                return pd.DataFrame(columns=["Date", "Dividends", "Stock Splits"])

            # Reset index to make Date a column
            df = actions.copy()
            df.index.name = "Date"
            df.reset_index(inplace=True)

            logger.debug(f"Retrieved {len(df)} action records for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Error fetching actions for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve actions for {ticker}: {e}")

    def get_financials(self, ticker: str, statement_type: str = "income", period: str = "annual") -> pd.DataFrame:
        """
        Get financial statements for a ticker.

        Args:
            ticker: Stock ticker symbol
            statement_type: Type of statement ('income', 'balance', 'cash')
            period: 'annual' or 'quarterly'

        Returns:
            DataFrame with financial statement data

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)

            # Select the appropriate statement
            if statement_type == "income":
                df = stock.financials if period == "annual" else stock.quarterly_financials
            elif statement_type == "balance":
                df = stock.balance_sheet if period == "annual" else stock.quarterly_balance_sheet
            elif statement_type == "cash":
                df = stock.cashflow if period == "annual" else stock.quarterly_cashflow
            else:
                raise ValueError(f"Invalid statement_type: {statement_type}. Must be 'income', 'balance', or 'cash'")

            if df.empty:
                logger.warning(f"No {period} {statement_type} statement available for {ticker}")
                return pd.DataFrame()

            logger.debug(f"Retrieved {period} {statement_type} statement for {ticker} ({df.shape[0]} rows, {df.shape[1]} periods)")
            return df

        except Exception as e:
            logger.error(f"Error fetching {period} {statement_type} statement for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve {period} {statement_type} statement for {ticker}: {e}")

    def get_holders(self, ticker: str, holder_type: str = "institutional") -> pd.DataFrame:
        """
        Get holder information for a ticker.

        Args:
            ticker: Stock ticker symbol
            holder_type: Type of holders ('institutional', 'mutualfund', 'major', 'insider')

        Returns:
            DataFrame with holder information

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)

            # Select the appropriate holder data
            if holder_type == "institutional":
                df = stock.institutional_holders
            elif holder_type == "mutualfund":
                df = stock.mutualfund_holders
            elif holder_type == "major":
                df = stock.major_holders
            elif holder_type == "insider":
                df = stock.insider_transactions
            else:
                raise ValueError(f"Invalid holder_type: {holder_type}. Must be 'institutional', 'mutualfund', 'major', or 'insider'")

            if df is None or df.empty:
                logger.warning(f"No {holder_type} holder data available for {ticker}")
                return pd.DataFrame()

            logger.debug(f"Retrieved {holder_type} holder data for {ticker} ({len(df)} records)")
            return df

        except Exception as e:
            logger.error(f"Error fetching {holder_type} holders for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve {holder_type} holders for {ticker}: {e}")

    def get_recommendations(self, ticker: str) -> pd.DataFrame:
        """
        Get analyst recommendations for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with analyst recommendations history

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            recommendations = stock.recommendations

            if recommendations is None or recommendations.empty:
                logger.warning(f"No analyst recommendations available for {ticker}")
                return pd.DataFrame()

            logger.debug(f"Retrieved {len(recommendations)} analyst recommendations for {ticker}")
            return recommendations

        except Exception as e:
            logger.error(f"Error fetching recommendations for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve recommendations for {ticker}: {e}")

    def get_option_expiration_dates(self, ticker: str) -> list[str]:
        """
        Get available options expiration dates for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of expiration dates in YYYY-MM-DD format

        Raises:
            Exception: If data retrieval fails
        """
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options  # Returns tuple of date strings

            if not expirations:
                logger.warning(f"No options expiration dates available for {ticker}")
                return []

            logger.debug(f"Retrieved {len(expirations)} expiration dates for {ticker}")
            return list(expirations)

        except Exception as e:
            logger.error(f"Error fetching option expiration dates for {ticker}: {e}", exc_info=True)
            raise Exception(f"Failed to retrieve option expiration dates for {ticker}: {e}")
