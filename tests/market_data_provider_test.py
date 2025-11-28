#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Check if running in CI environment
IN_CI = os.getenv('CI', '').lower() in ('true', '1', 'yes')

import unittest
import pandas as pd
from datetime import datetime

from providers.market_data_provider import MarketDataProvider
from providers.yfinance_provider import YFinanceProvider
from providers.finnhub_provider import FinnhubProvider
# from providers.alphavantage_provider import AlphaVantageProvider  # Commented out: rate limit issues
import constants as const


class TestMarketDataProvider(unittest.TestCase):
    """Test abstract base class cannot be instantiated."""

    def test_cannot_instantiate_abstract_class(self):
        """Verify MarketDataProvider cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            provider = MarketDataProvider()


class MarketDataProviderTestMixin:
    """
    Mixin class containing all integration tests for MarketDataProvider interface.

    Subclasses must define:
    - self.provider: instance of MarketDataProvider
    - self.provider_name: string name for logging
    - self.test_ticker: ticker symbol to test with
    """

    def test_get_quote_live(self):
        """Test quote retrieval with real API."""
        print(f"\n[{self.provider_name}] Testing get_quote({self.test_ticker})...")

        result = self.provider.get_quote(self.test_ticker)

        # Verify quote is reasonable
        self.assertGreater(result, 0, "Quote should be positive")
        self.assertIsInstance(result, float)

        print(f"  ✓ Current quote: ${result:.2f}")
        return result

    def test_get_stock_info_live(self):
        """Test stock info retrieval with real API."""
        print(f"\n[{self.provider_name}] Testing get_stock_info({self.test_ticker})...")

        result = self.provider.get_stock_info(self.test_ticker)

        # Verify required fields exist
        self.assertIn('symbol', result)
        self.assertIn('current_price', result)
        self.assertIn('company_name', result)

        # Verify data quality
        self.assertEqual(result['symbol'], self.test_ticker)
        self.assertGreater(result['current_price'], 0, "Current price should be positive")
        self.assertIsNotNone(result['company_name'])

        print(f"  ✓ Symbol: {result['symbol']}")
        print(f"  ✓ Company: {result['company_name']}")
        print(f"  ✓ Current Price: ${result['current_price']:.2f}")
        print(f"  ✓ Previous Close: ${result['previous_close']:.2f}")
        if result.get('pe_ratio', 0) > 0:
            print(f"  ✓ PE Ratio: {result['pe_ratio']:.2f}")
        if result.get('market_cap', 0) > 0:
            print(f"  ✓ Market Cap: ${result['market_cap']:,.0f}")

        return result

    def test_get_historical_data_live(self):
        """Test historical data retrieval with real API."""
        print(f"\n[{self.provider_name}] Testing get_historical_data({self.test_ticker}, period='1mo', interval='1d')...")

        result = self.provider.get_historical_data(self.test_ticker, period='1mo', interval='1d')

        # Verify DataFrame structure
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0, "Should have historical data")

        # Verify required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in required_cols:
            self.assertIn(col, result.columns, f"Missing required column: {col}")

        # Verify data quality
        self.assertTrue(all(result['High'] >= result['Low']), "High should be >= Low")
        self.assertTrue(all(result['High'] >= result['Open']), "High should be >= Open")
        self.assertTrue(all(result['High'] >= result['Close']), "High should be >= Close")
        self.assertTrue(all(result['Low'] <= result['Open']), "Low should be <= Open")
        self.assertTrue(all(result['Low'] <= result['Close']), "Low should be <= Close")
        self.assertTrue(all(result['Volume'] >= 0), "Volume should be non-negative")

        print(f"  ✓ Retrieved {len(result)} days of data")
        print(f"  ✓ Date range: {result.index[0].date()} to {result.index[-1].date()}")
        print(f"  ✓ Latest close: ${result['Close'].iloc[-1]:.2f}")

        return result

    def test_get_news_live(self):
        """Test news retrieval with real API."""
        print(f"\n[{self.provider_name}] Testing get_news({self.test_ticker}, count=5)...")

        result = self.provider.get_news(self.test_ticker, count=5)

        # Verify news structure
        self.assertIsInstance(result, list)

        if result:
            # If we got news, verify structure
            first_article = result[0]
            self.assertIn('headline', first_article)
            self.assertIn('source', first_article)
            self.assertIn('url', first_article)
            self.assertIn('published', first_article)
            # sentiment is optional

            print(f"  ✓ Retrieved {len(result)} news articles")
            print(f"  ✓ Latest: '{first_article['headline'][:60]}...'")
            print(f"  ✓ Source: {first_article['source']}")
            if first_article.get('sentiment'):
                print(f"  ✓ Sentiment: {first_article['sentiment']}")
        else:
            print(f"  ✓ No news available (this is okay)")

        return result


@unittest.skipIf(IN_CI, "Skip live API tests in CI environment")
class TestYFinanceProviderLive(MarketDataProviderTestMixin, unittest.TestCase):
    """Integration tests for YFinance provider."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        cls.provider = YFinanceProvider()
        cls.provider_name = "YFinance"
        cls.test_ticker = 'AAPL'
        print(f"\n{'='*60}")
        print(f"Testing YFinance Provider with live data")
        print(f"{'='*60}")


@unittest.skipIf(IN_CI, "Skip live API tests in CI environment")
class TestFinnhubProviderLive(MarketDataProviderTestMixin, unittest.TestCase):
    """Integration tests for Finnhub provider."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        if not const.FINNHUB_API_KEY:
            raise unittest.SkipTest("FINNHUB_API_KEY not configured in .env")

        cls.provider = FinnhubProvider()
        cls.provider_name = "Finnhub"
        cls.test_ticker = 'AAPL'
        print(f"\n{'='*60}")
        print(f"Testing Finnhub Provider with live data")
        print(f"Note: Free tier has limitations on historical data")
        print(f"{'='*60}")

    def test_get_historical_data_live(self):
        """Override to handle Finnhub free tier limitation."""
        print(f"\n[{self.provider_name}] Testing get_historical_data({self.test_ticker}, period='1mo', interval='1d')...")

        try:
            result = super().test_get_historical_data_live()
        except Exception as e:
            if '403' in str(e) or 'Forbidden' in str(e):
                print(f"  ⚠ Historical data not available on free tier (expected)")
                self.skipTest("Historical data requires Finnhub premium tier")
            else:
                raise


# Commented out: AlphaVantage provider has rate limit issues (25 requests/day on free tier)
# class TestAlphaVantageProviderLive(MarketDataProviderTestMixin, unittest.TestCase):
#     """Integration tests for Alpha Vantage provider."""
#
#     @classmethod
#     def setUpClass(cls):
#         """Set up test fixtures once for all tests."""
#         if not const.ALPHAVANTAGE_API_KEY:
#             raise unittest.SkipTest("ALPHAVANTAGE_API_KEY not configured")
#
#         cls.provider = AlphaVantageProvider()
#         cls.provider_name = "AlphaVantage"
#         cls.test_ticker = 'AAPL'
#         print(f"\n{'='*60}")
#         print(f"Testing Alpha Vantage Provider with live data")
#         print(f"Note: Free tier limited to 25 requests/day")
#         print(f"{'='*60}")


@unittest.skipIf(IN_CI, "Skip live API tests in CI environment")
class TestProviderComparison(unittest.TestCase):
    """Compare outputs between providers to ensure consistency."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.yf_provider = YFinanceProvider()
        cls.test_ticker = 'AAPL'

        # Optional providers (skip comparison if not configured)
        cls.fh_provider = FinnhubProvider() if const.FINNHUB_API_KEY else None
        cls.av_provider = None  # AlphaVantageProvider() if const.ALPHAVANTAGE_API_KEY else None  # Commented out: rate limits

        print(f"\n{'='*60}")
        print(f"Comparing Provider Outputs for Consistency")
        print(f"{'='*60}")

    def test_quote_comparison(self):
        """Compare quotes from all available providers (should be similar)."""
        print(f"\n[Comparison] Testing quote prices for {self.test_ticker}...")

        # Get YFinance quote (always available)
        yf_quote = self.yf_provider.get_quote(self.test_ticker)
        print(f"  YFinance quote: ${yf_quote:.2f}")

        # Compare with Finnhub if available
        if self.fh_provider:
            fh_quote = self.fh_provider.get_quote(self.test_ticker)
            print(f"  Finnhub quote:  ${fh_quote:.2f}")

            difference_pct = abs(yf_quote - fh_quote) / yf_quote * 100
            print(f"  YF vs FH diff:  {difference_pct:.2f}%")
            self.assertLess(difference_pct, 5.0, f"YF/FH quotes differ by more than 5% ({difference_pct:.2f}%)")

        # Compare with Alpha Vantage if available
        if self.av_provider:
            av_quote = self.av_provider.get_quote(self.test_ticker)
            print(f"  AlphaV quote:   ${av_quote:.2f}")

            difference_pct = abs(yf_quote - av_quote) / yf_quote * 100
            print(f"  YF vs AV diff:  {difference_pct:.2f}%")
            self.assertLess(difference_pct, 5.0, f"YF/AV quotes differ by more than 5% ({difference_pct:.2f}%)")

        print(f"  ✓ All providers are consistent (within 5%)")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
