"""
Ticker Validator Singleton

Provides shared ticker validation with caching across the entire application.
Prevents repeated database queries and API calls for the same ticker symbols.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re
from typing import Optional

from db import Db
from providers.market_data_factory import MarketDataFactory
from tickers import Tickers


logger = logging.getLogger(__name__)


class TickerValidator:
    """
    Singleton ticker validator with caching.

    Provides fast ticker validation by checking:
    1. In-memory cache (valid/invalid)
    2. Database (tickers table)
    3. Market data API (yfinance/finnhub)

    Usage:
        validator = TickerValidator.get_instance(db)
        if validator.is_valid('AAPL'):
            ...

        # Extract and validate from text
        tickers = validator.extract_and_validate("Bought AAPL and TSLA today")
    """

    _instance: Optional["TickerValidator"] = None
    _valid_cache: set[str] = set()
    _invalid_cache: set[str] = set()
    _blacklist: set[str] = set()  # Loaded from database at runtime

    def __init__(self, db: Db):
        """
        Initialize validator (use get_instance() instead).

        Args:
            db: Database instance
        """
        self.db = db
        self.tickers_db = Tickers(db)
        self.market_data = MarketDataFactory.get_provider()

        # Performance metrics
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "blacklist_rejections": 0,
            "db_lookups": 0,
            "api_calls": 0
        }

        # Load blacklist from database
        self._load_blacklist()

        # Preload known valid tickers into cache (S&P 500, DOW, etc.)
        self._preload_valid_tickers()

    @classmethod
    def get_instance(cls, db: Db) -> "TickerValidator":
        """
        Get singleton instance.

        Args:
            db: Database instance

        Returns:
            TickerValidator singleton
        """
        if cls._instance is None:
            cls._instance = cls(db)
            logger.info("TickerValidator singleton created")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)"""
        cls._instance = None
        cls._valid_cache.clear()
        cls._invalid_cache.clear()

    def is_valid(self, ticker: str) -> bool:
        """
        Check if ticker is valid (cached → DB → API).

        Args:
            ticker: Ticker symbol to validate

        Returns:
            True if valid ticker symbol
        """
        ticker = ticker.upper().strip()

        # Check blacklist first
        if ticker in self._blacklist:
            self._metrics["blacklist_rejections"] += 1
            return False

        # Check valid cache
        if ticker in self._valid_cache:
            self._metrics["cache_hits"] += 1
            logger.debug(f"Ticker {ticker} found in valid cache")
            return True

        # Check invalid cache
        if ticker in self._invalid_cache:
            self._metrics["cache_hits"] += 1
            logger.debug(f"Ticker {ticker} found in invalid cache")
            return False

        # Cache miss - need to lookup
        self._metrics["cache_misses"] += 1

        # Check database
        self._metrics["db_lookups"] += 1
        if self.tickers_db.is_valid_ticker(ticker):
            self._valid_cache.add(ticker)
            logger.debug(f"Ticker {ticker} found in database")
            return True

        # Check API and auto-add if valid
        self._metrics["api_calls"] += 1
        if self._validate_via_api(ticker):
            self._valid_cache.add(ticker)
            logger.debug(f"Ticker {ticker} validated via API")
            return True

        # Cache as invalid
        self._invalid_cache.add(ticker)
        logger.debug(f"Ticker {ticker} is invalid")
        return False

    def _validate_via_api(self, ticker: str) -> bool:
        """
        Validate ticker via market data API (NO auto-add).

        NOTE: Auto-add disabled to prevent pollution from news article terms.
        Use CLI command 'tickers add' to manually add community-relevant tickers.

        Args:
            ticker: Ticker symbol

        Returns:
            True if valid (but does NOT add to database)
        """
        # API validation disabled - only use curated database
        # This prevents garbage terms (HAMAS, GAZA, TRUMP, etc.) from validating
        logger.debug(f"API validation disabled for {ticker} - use curated database only")
        return False

    def extract_and_validate(self, text: str) -> set[str]:
        """
        Extract and validate ticker symbols from text.

        Uses regex pattern to find potential tickers (2-5 uppercase letters),
        filters against blacklist, then validates each candidate.

        Args:
            text: Text to extract tickers from

        Returns:
            Set of valid ticker symbols
        """
        if not text:
            return set()

        # Regex pattern for potential ticker symbols (2-5 uppercase letters)
        pattern = r"\b[A-Z]{2,5}\b"
        potential_tickers = set(re.findall(pattern, text))

        # Remove blacklisted terms
        potential_tickers = potential_tickers - self._blacklist

        # Validate each ticker
        valid_tickers = set()
        for ticker in potential_tickers:
            if self.is_valid(ticker):
                valid_tickers.add(ticker)

        if valid_tickers:
            logger.debug(f"Extracted valid tickers: {', '.join(sorted(valid_tickers))}")

        return valid_tickers

    def _preload_valid_tickers(self) -> None:
        """
        Preload known valid tickers from database into cache.

        Loads all active tickers (S&P 500, DOW, NASDAQ, etc.) to avoid
        repeated database lookups during ticker extraction.
        """
        try:
            query = "SELECT ticker FROM valid_tickers WHERE is_active = 1"
            results = self.db.query(query, None)

            if results:
                for row in results:
                    self._valid_cache.add(row[0].upper())

                logger.info(f"Preloaded {len(self._valid_cache)} valid tickers into cache")
            else:
                logger.warning("No valid tickers found in database")

        except Exception as e:
            logger.error(f"Failed to preload valid tickers: {e}")

    def _load_blacklist(self) -> None:
        """
        Load blacklist from database.

        Blacklist contains common words that should never be treated as tickers
        (e.g., 'IN', 'OF', 'TO', 'STO', 'NOV', etc.)
        """
        try:
            query = "SELECT term FROM ticker_blacklist"
            results = self.db.query_parameterized(query, None)

            if results:
                for row in results:
                    self._blacklist.add(row[0].upper())

                logger.info(f"Loaded {len(self._blacklist)} blacklist terms from database")
            else:
                logger.warning("No blacklist terms found in database")

        except Exception as e:
            logger.error(f"Failed to load blacklist: {e}")

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics and performance metrics.

        Returns:
            Dict with cache stats and performance metrics
        """
        total_checks = self._metrics["cache_hits"] + self._metrics["cache_misses"] + self._metrics["blacklist_rejections"]
        hit_rate = (self._metrics["cache_hits"] / total_checks * 100) if total_checks > 0 else 0

        return {
            "valid_cache_size": len(self._valid_cache),
            "invalid_cache_size": len(self._invalid_cache),
            "blacklist_size": len(self._blacklist),
            "performance": {
                "total_checks": total_checks,
                "cache_hits": self._metrics["cache_hits"],
                "cache_misses": self._metrics["cache_misses"],
                "blacklist_rejections": self._metrics["blacklist_rejections"],
                "db_lookups": self._metrics["db_lookups"],
                "api_calls": self._metrics["api_calls"],
                "cache_hit_rate": f"{hit_rate:.1f}%"
            },
            "valid_tickers": sorted(self._valid_cache),
            "invalid_tickers": sorted(self._invalid_cache)
        }
