"""
Market Data Factory with Fallback Support

Provides centralized creation and management of market data providers with
automatic fallback when providers fail or hit rate limits.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any

import pandas as pd

import constants as const
from providers.finnhub_provider import FinnhubProvider
from providers.market_data_provider import MarketDataProvider
from providers.yfinance_provider import YFinanceProvider


logger = logging.getLogger(__name__)


class MarketDataFactory:
    """
    Factory for creating and managing market data providers with fallback support.

    Features:
    - Singleton pattern for provider instances
    - Automatic fallback to alternative providers on failure
    - Rate limit detection and provider rotation

    Design: Cache-ready architecture (add caching later when needed)

    Usage:
        Entry points should call set_db(db) once at startup to inject database.
        Factory will automatically load default provider from SystemSettings.
    """

    # Singleton instances (one per provider type)
    _providers: dict[str, MarketDataProvider] = {}

    # Database instance (injected by entry points)
    _db_instance: Any | None = None

    # Default provider cache (loaded from SystemSettings at startup)
    _default_provider_cache: str | None = None

    @classmethod
    def set_db(cls, db: Any) -> None:
        """
        Inject database instance for reading SystemSettings.

        Entry points should call this once at startup.

        Args:
            db: Database instance
        """
        cls._db_instance = db
        cls._load_default_provider()

    @classmethod
    def _load_default_provider(cls) -> None:
        """Load default provider from SystemSettings (called once at startup)."""
        from system_settings import get_settings
        settings = get_settings(cls._db_instance)
        cls._default_provider_cache = settings.get(const.SETTING_MARKET_DATA_PROVIDER)
        logger.info(f"Market data provider loaded from settings: {cls._default_provider_cache}")

    @classmethod
    def reload_settings(cls) -> None:
        """
        Reload settings from database (for runtime configuration changes).

        Call this after updating market data provider in SystemSettings.
        """
        cls._default_provider_cache = None
        cls._load_default_provider()
        logger.info("Market data provider settings reloaded")

    @classmethod
    def get_provider(cls, provider_name: str | None = None) -> MarketDataProvider:
        """
        Get a market data provider instance.

        Args:
            provider_name: Name of provider ('yfinance', 'finnhub')
                          If None, uses default from SystemSettings

        Returns:
            MarketDataProvider instance

        Raises:
            Exception: If provider cannot be created
        """
        if provider_name is None:
            if cls._default_provider_cache is None:
                # Fallback for tests/edge cases where set_db() wasn't called
                logger.warning("MarketDataFactory.set_db() not called, using fallback provider 'yfinance'")
                provider_name = "yfinance"
            else:
                provider_name = cls._default_provider_cache

        provider_name = provider_name.lower()

        # Return cached instance if available
        if provider_name in cls._providers:
            return cls._providers[provider_name]

        # Create new provider instance
        try:
            provider: MarketDataProvider
            if provider_name == "finnhub":
                provider = FinnhubProvider()
            else:  # default to yfinance
                provider = YFinanceProvider()

            cls._providers[provider_name] = provider
            logger.info(f"Initialized {provider_name} market data provider")
            return provider

        except Exception as e:
            logger.error(f"Failed to create {provider_name} provider: {e}")
            raise

    @classmethod
    def get_fallback_providers(cls) -> list[MarketDataProvider]:
        """
        Get list of fallback providers in priority order.

        Returns providers in order: primary, then alternatives.
        Order ensures best-available provider is tried first.
        """
        primary_name = (cls._default_provider_cache or "yfinance").lower()
        all_providers = ["yfinance", "finnhub"]

        # Remove primary from list, then add it at the front
        fallback_order = [p for p in all_providers if p != primary_name]
        provider_order = [primary_name] + fallback_order

        providers = []
        for name in provider_order:
            try:
                provider = cls.get_provider(name)
                providers.append(provider)
            except Exception as e:
                logger.warning(f"Could not initialize {name} provider: {e}")
                continue

        if not providers:
            raise Exception("No market data providers available")

        return providers

    @classmethod
    def _is_rate_limit_error(cls, error: Exception) -> bool:
        """Check if error is due to rate limiting."""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "rate limit",
            "429",
            "too many requests",
            "quota exceeded",
            "limit exceeded",
            "throttle",
            "api calls quota"
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)

    @classmethod
    def get_quote_with_fallback(cls, ticker: str) -> float:
        """
        Get stock quote with automatic fallback on failure.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current price as float

        Raises:
            Exception: If all providers fail
        """
        providers = cls.get_fallback_providers()
        last_error = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                price = provider.get_quote(ticker)
                if price > 0:  # Valid price
                    logger.debug(f"Got quote for {ticker} from {provider_name}: ${price:.2f}")
                    return price
                logger.warning(f"{provider_name} returned invalid price for {ticker}: {price}")
                continue

            except Exception as e:
                last_error = e
                if cls._is_rate_limit_error(e):
                    logger.warning(f"{provider_name} rate limited for {ticker}, trying fallback")
                else:
                    logger.warning(f"{provider_name} failed for {ticker}: {e}")
                continue

        # All providers failed
        raise Exception(f"All providers failed to get quote for {ticker}. Last error: {last_error}")

    @classmethod
    def get_stock_info_with_fallback(cls, ticker: str) -> dict[str, Any]:
        """
        Get stock information with automatic fallback on failure.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with stock information

        Raises:
            Exception: If all providers fail
        """
        providers = cls.get_fallback_providers()
        last_error = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                info = provider.get_stock_info(ticker)
                logger.debug(f"Got stock info for {ticker} from {provider_name}")
                return info

            except Exception as e:
                last_error = e
                if cls._is_rate_limit_error(e):
                    logger.warning(f"{provider_name} rate limited for {ticker}, trying fallback")
                else:
                    logger.warning(f"{provider_name} failed for {ticker}: {e}")
                continue

        # All providers failed
        raise Exception(f"All providers failed to get stock info for {ticker}. Last error: {last_error}")

    @classmethod
    def get_historical_data_with_fallback(
        cls,
        ticker: str,
        period: str = "3mo",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Get historical data with automatic fallback on failure.

        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            interval: Data interval (1m, 5m, 1h, 1d, 1wk, 1mo)

        Returns:
            DataFrame with OHLCV data

        Raises:
            Exception: If all providers fail
        """
        providers = cls.get_fallback_providers()
        last_error = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                df = provider.get_historical_data(ticker, period, interval)
                if not df.empty:
                    logger.debug(f"Got historical data for {ticker} from {provider_name} ({len(df)} bars)")
                    return df
                logger.warning(f"{provider_name} returned empty data for {ticker}")
                continue

            except Exception as e:
                last_error = e
                if cls._is_rate_limit_error(e):
                    logger.warning(f"{provider_name} rate limited for {ticker}, trying fallback")
                else:
                    logger.warning(f"{provider_name} failed for {ticker}: {e}")
                continue

        # All providers failed
        raise Exception(f"All providers failed to get historical data for {ticker}. Last error: {last_error}")

    @classmethod
    def get_news_with_fallback(cls, ticker: str, count: int = 10) -> list[dict[str, Any]]:
        """
        Get news with automatic fallback on failure.

        Args:
            ticker: Stock ticker symbol
            count: Number of articles

        Returns:
            List of news articles (may be empty if no news available)

        Raises:
            Exception: If all providers fail
        """
        providers = cls.get_fallback_providers()
        last_error = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                news = provider.get_news(ticker, count)
                logger.debug(f"Got {len(news)} news articles for {ticker} from {provider_name}")
                return news  # Return even if empty - no news is valid

            except Exception as e:
                last_error = e
                if cls._is_rate_limit_error(e):
                    logger.warning(f"{provider_name} rate limited for {ticker}, trying fallback")
                else:
                    logger.warning(f"{provider_name} failed for {ticker}: {e}")
                continue

        # All providers failed
        raise Exception(f"All providers failed to get news for {ticker}. Last error: {last_error}")

    @classmethod
    def get_options_chain_with_fallback(cls, ticker: str) -> dict[str, Any] | None:
        """
        Get options chain with automatic fallback on failure.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with options chain data, or None if unavailable

        Raises:
            Exception: If all providers fail

        Note:
            Options chains use Finnhub first because yfinance returns delta=0.0
            for all options, making Greeks unusable for scanning.
        """
        # Use Finnhub first for options chains (provides accurate Greeks)
        # Then fallback to YFinance
        options_provider_order = ["finnhub", "yfinance"]

        providers = []
        for name in options_provider_order:
            try:
                provider = cls.get_provider(name)
                providers.append(provider)
            except Exception as e:
                logger.warning(f"Could not initialize {name} provider for options: {e}")
                continue

        if not providers:
            raise Exception("No market data providers available for options chains")

        last_error = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                chain_data = provider.get_options_chain(ticker)
                if chain_data is not None:
                    logger.debug(f"Got options chain for {ticker} from {provider_name}")
                    return chain_data
                logger.warning(f"{provider_name} returned None for {ticker} options chain")
                continue

            except Exception as e:
                last_error = e
                if cls._is_rate_limit_error(e):
                    logger.warning(f"{provider_name} rate limited for {ticker}, trying fallback")
                else:
                    logger.warning(f"{provider_name} failed for {ticker}: {e}")
                continue

        # All providers failed
        raise Exception(f"All providers failed to get options chain for {ticker}. Last error: {last_error}")

    @classmethod
    def reset(cls):
        """Reset factory state (mainly for testing)."""
        cls._providers.clear()
        logger.info("Market data factory reset")
