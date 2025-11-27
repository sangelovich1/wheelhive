#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from providers.market_data_factory import MarketDataFactory
from providers.yfinance_provider import YFinanceProvider
from providers.finnhub_provider import FinnhubProvider
from db import Db
import constants as const


class TestMarketDataFactory(unittest.TestCase):
    """Test market data factory with fallback logic."""

    def setUp(self):
        """Reset factory state and setup test database before each test."""
        MarketDataFactory.reset()
        # Setup in-memory database with SystemSettings
        self.db = Db(in_memory=True)
        # Initialize factory with test database
        MarketDataFactory.set_db(self.db)

    def test_get_provider_creates_instance(self):
        """Test that get_provider creates and caches instances."""
        provider1 = MarketDataFactory.get_provider('yfinance')
        provider2 = MarketDataFactory.get_provider('yfinance')

        # Should return same instance (singleton)
        self.assertIs(provider1, provider2)
        self.assertIsInstance(provider1, YFinanceProvider)

    def test_get_provider_creates_different_types(self):
        """Test that different provider types are created correctly."""
        yf = MarketDataFactory.get_provider('yfinance')
        fh = MarketDataFactory.get_provider('finnhub')

        self.assertIsInstance(yf, YFinanceProvider)
        self.assertIsInstance(fh, FinnhubProvider)

    def test_fallback_providers_order(self):
        """Test that fallback providers are in correct priority order."""
        # Factory should use yfinance as default (from SystemSettings)
        providers = MarketDataFactory.get_fallback_providers()

        # Should have yfinance first (primary), then others
        self.assertGreaterEqual(len(providers), 1)
        self.assertIsInstance(providers[0], YFinanceProvider)

    def test_quote_fallback_on_rate_limit(self):
        """Test fallback when primary provider hits rate limit."""
        # Mock yfinance to raise rate limit error
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_quote.side_effect = Exception("rate limit exceeded")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        # Mock finnhub to succeed
        mock_fh = Mock(spec=FinnhubProvider)
        mock_fh.get_quote.return_value = 150.0
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should fallback to finnhub
            price = MarketDataFactory.get_quote_with_fallback('AAPL')
            self.assertEqual(price, 150.0)
            mock_yf.get_quote.assert_called_once_with('AAPL')
            mock_fh.get_quote.assert_called_once_with('AAPL')

    def test_quote_fallback_on_generic_error(self):
        """Test fallback when primary provider fails with generic error."""
        # Mock yfinance to fail
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_quote.side_effect = Exception("Connection timeout")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        # Mock finnhub to succeed
        mock_fh = Mock(spec=FinnhubProvider)
        mock_fh.get_quote.return_value = 155.0
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should fallback to finnhub
            price = MarketDataFactory.get_quote_with_fallback('AAPL')
            self.assertEqual(price, 155.0)

    def test_all_providers_fail(self):
        """Test that exception is raised when all providers fail."""
        # Mock all providers to fail
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_quote.side_effect = Exception("YF Error")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        mock_fh = Mock(spec=FinnhubProvider)
        mock_fh.get_quote.side_effect = Exception("FH Error")
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should raise exception
            with self.assertRaises(Exception) as context:
                MarketDataFactory.get_quote_with_fallback('AAPL')

            self.assertIn("All providers failed", str(context.exception))

    def test_stock_info_fallback(self):
        """Test stock info with fallback."""
        # Mock yfinance to fail
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_stock_info.side_effect = Exception("Error")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        # Mock finnhub to succeed
        mock_fh = Mock(spec=FinnhubProvider)
        mock_fh.get_stock_info.return_value = {
            'symbol': 'AAPL',
            'current_price': 150.0,
            'company_name': 'Apple Inc.'
        }
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should fallback to finnhub
            info = MarketDataFactory.get_stock_info_with_fallback('AAPL')
            self.assertEqual(info['symbol'], 'AAPL')
            self.assertEqual(info['current_price'], 150.0)

    def test_historical_data_fallback(self):
        """Test historical data with fallback."""
        # Mock yfinance to fail
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_historical_data.side_effect = Exception("Error")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        # Mock finnhub to succeed
        mock_fh = Mock(spec=FinnhubProvider)
        test_df = pd.DataFrame({
            'Open': [100, 101],
            'High': [102, 103],
            'Low': [99, 100],
            'Close': [101, 102],
            'Volume': [1000, 1100]
        })
        mock_fh.get_historical_data.return_value = test_df
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should fallback to finnhub
            df = MarketDataFactory.get_historical_data_with_fallback('AAPL', period='1mo')
            self.assertEqual(len(df), 2)
            self.assertIn('Close', df.columns)

    def test_news_fallback(self):
        """Test news with fallback."""
        # Mock yfinance to fail
        mock_yf = Mock(spec=YFinanceProvider)
        mock_yf.get_news.side_effect = Exception("Error")
        mock_yf.__class__.__name__ = 'YFinanceProvider'

        # Mock finnhub to succeed
        mock_fh = Mock(spec=FinnhubProvider)
        mock_fh.get_news.return_value = [
            {'headline': 'Apple news', 'source': 'Test', 'url': 'http://test.com'}
        ]
        mock_fh.__class__.__name__ = 'FinnhubProvider'

        # Mock get_fallback_providers to return our mocks
        with patch.object(MarketDataFactory, 'get_fallback_providers', return_value=[mock_yf, mock_fh]):
            # Should fallback to finnhub
            news = MarketDataFactory.get_news_with_fallback('AAPL', count=5)
            self.assertEqual(len(news), 1)
            self.assertEqual(news[0]['headline'], 'Apple news')

    def test_is_rate_limit_error(self):
        """Test rate limit error detection."""
        self.assertTrue(MarketDataFactory._is_rate_limit_error(Exception("rate limit exceeded")))
        self.assertTrue(MarketDataFactory._is_rate_limit_error(Exception("429 Too Many Requests")))
        self.assertTrue(MarketDataFactory._is_rate_limit_error(Exception("quota exceeded")))
        self.assertFalse(MarketDataFactory._is_rate_limit_error(Exception("connection timeout")))
        self.assertFalse(MarketDataFactory._is_rate_limit_error(Exception("invalid ticker")))

    def test_reset(self):
        """Test factory reset."""
        # Create provider
        MarketDataFactory.get_provider('yfinance')
        self.assertEqual(len(MarketDataFactory._providers), 1)

        # Reset
        MarketDataFactory.reset()
        self.assertEqual(len(MarketDataFactory._providers), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
