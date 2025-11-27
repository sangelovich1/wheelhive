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

import unittest
from unittest.mock import Mock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ta_service import TAService, get_ta_service


class TestTAService(unittest.TestCase):
    """Test TAService class"""

    def setUp(self):
        """Set up test fixtures"""
        self.ta_service = TAService()

    def _create_sample_data(self, days=60, start_price=100):
        """Create sample OHLCV data for testing"""
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

        # Generate realistic price movement
        np.random.seed(42)  # For reproducibility
        returns = np.random.normal(0.001, 0.02, days)
        prices = start_price * (1 + returns).cumprod()

        # Create OHLCV data
        data = {
            'Open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
            'High': prices * (1 + np.random.uniform(0, 0.02, days)),
            'Low': prices * (1 - np.random.uniform(0, 0.02, days)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 10000000, days)
        }

        df = pd.DataFrame(data, index=dates)
        return df

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_analysis_success(self, mock_get_data):
        """Test successful technical analysis retrieval"""
        # Mock data
        mock_get_data.return_value = self._create_sample_data()

        # Call service
        result = self.ta_service.get_technical_analysis('AAPL', period='1mo', include_patterns=False)

        # Assertions
        self.assertNotIn('error', result)
        self.assertEqual(result['ticker'], 'AAPL')
        self.assertIn('current_price', result)
        self.assertIn('indicators', result)
        self.assertIn('trend_analysis', result)
        self.assertIn('support_resistance', result)
        self.assertIn('interpretation', result)

        # Check current price structure
        self.assertIn('price', result['current_price'])
        self.assertIn('change', result['current_price'])
        self.assertIn('change_percent', result['current_price'])

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_analysis_with_patterns(self, mock_get_data):
        """Test technical analysis with pattern detection"""
        mock_get_data.return_value = self._create_sample_data(days=90)

        result = self.ta_service.get_technical_analysis('SPY', include_patterns=True)

        self.assertNotIn('error', result)
        self.assertIn('patterns', result)
        self.assertIsNotNone(result['patterns'])
        self.assertIn('double_top', result['patterns'])
        self.assertIn('double_bottom', result['patterns'])

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_analysis_no_data(self, mock_get_data):
        """Test handling of no data available"""
        mock_get_data.return_value = None

        result = self.ta_service.get_technical_analysis('INVALID')

        self.assertIn('error', result)
        self.assertIn('No historical data', result['error'])

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_analysis_empty_dataframe(self, mock_get_data):
        """Test handling of empty dataframe"""
        mock_get_data.return_value = pd.DataFrame()

        result = self.ta_service.get_technical_analysis('INVALID')

        self.assertIn('error', result)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_summary_success(self, mock_get_data):
        """Test technical summary retrieval"""
        mock_get_data.return_value = self._create_sample_data(days=30)

        result = self.ta_service.get_technical_summary('AAPL')

        self.assertNotIn('error', result)
        self.assertEqual(result['ticker'], 'AAPL')
        self.assertIn('overall_signal', result)
        self.assertIn(result['overall_signal'], ['BULLISH', 'BEARISH', 'NEUTRAL'])
        self.assertIn('bullish_signals', result)
        self.assertIn('bearish_signals', result)
        self.assertIn('key_signals', result)
        self.assertIn('price_info', result)
        self.assertIsInstance(result['key_signals'], list)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_get_technical_summary_bullish(self, mock_get_data):
        """Test technical summary with bullish setup"""
        df = self._create_sample_data(days=30, start_price=90)
        # Manipulate to create oversold RSI
        df['Close'] = df['Close'].iloc[0] * 0.85  # Drop price 15%
        df.iloc[-5:, df.columns.get_loc('Close')] *= 1.05  # Recent bounce

        mock_get_data.return_value = df

        result = self.ta_service.get_technical_summary('AAPL')

        # Should have some signals
        self.assertIsInstance(result.get('bullish_signals'), int)
        self.assertIsInstance(result.get('bearish_signals'), int)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_interpretation_generation(self, mock_get_data):
        """Test that interpretation text is generated"""
        mock_get_data.return_value = self._create_sample_data()

        result = self.ta_service.get_technical_analysis('AAPL')

        self.assertIn('interpretation', result)
        interpretation = result['interpretation']
        self.assertIsInstance(interpretation, str)
        self.assertGreater(len(interpretation), 0)
        # Should contain markdown headers
        self.assertIn('**', interpretation)
        # Should mention the ticker
        self.assertIn('AAPL', interpretation)

    def test_singleton_pattern(self):
        """Test that get_ta_service returns same instance"""
        service1 = get_ta_service()
        service2 = get_ta_service()
        self.assertIs(service1, service2)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_different_periods(self, mock_get_data):
        """Test different time periods"""
        periods = ['1mo', '3mo', '6mo', '1y']

        for period in periods:
            with self.subTest(period=period):
                mock_get_data.return_value = self._create_sample_data()
                result = self.ta_service.get_technical_analysis('AAPL', period=period)
                self.assertNotIn('error', result)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_indicators_present(self, mock_get_data):
        """Test that key indicators are calculated"""
        mock_get_data.return_value = self._create_sample_data(days=60)

        result = self.ta_service.get_technical_analysis('AAPL')

        indicators = result.get('indicators', {})

        # Check for key indicators (may not all be present due to data requirements)
        expected_indicators = ['rsi_14', 'sma_20', 'ema_12']
        for indicator in expected_indicators:
            if indicator in indicators:
                self.assertIsInstance(indicators[indicator], (int, float))

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_trend_analysis_present(self, mock_get_data):
        """Test that trend analysis is performed"""
        mock_get_data.return_value = self._create_sample_data(days=60)

        result = self.ta_service.get_technical_analysis('AAPL')

        trend = result.get('trend_analysis', {})

        # Check for trend indicators
        if 'rsi_zone' in trend:
            self.assertIn(trend['rsi_zone'], ['overbought', 'oversold', 'neutral'])

        if 'macd_signal' in trend:
            self.assertIn(trend['macd_signal'], ['bullish', 'bearish'])

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_support_resistance_levels(self, mock_get_data):
        """Test support and resistance level detection"""
        mock_get_data.return_value = self._create_sample_data(days=60)

        result = self.ta_service.get_technical_analysis('AAPL')

        levels = result.get('support_resistance', {})

        if 'support' in levels:
            self.assertIsInstance(levels['support'], list)

        if 'resistance' in levels:
            self.assertIsInstance(levels['resistance'], list)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_error_handling(self, mock_get_data):
        """Test error handling when calculation fails"""
        # Mock to raise exception
        mock_get_data.side_effect = Exception("API Error")

        result = self.ta_service.get_technical_analysis('AAPL')

        self.assertIn('error', result)
        self.assertIn('ticker', result)
        self.assertEqual(result['ticker'], 'AAPL')


class TestTAServiceEdgeCases(unittest.TestCase):
    """Test edge cases for TAService"""

    def setUp(self):
        self.ta_service = TAService()

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_insufficient_data_for_indicators(self, mock_get_data):
        """Test with insufficient data points"""
        # Only 5 days of data - not enough for most indicators
        dates = pd.date_range(end=datetime.now(), periods=5, freq='D')
        df = pd.DataFrame({
            'Open': [100, 101, 102, 101, 103],
            'High': [101, 102, 103, 102, 104],
            'Low': [99, 100, 101, 100, 102],
            'Close': [100, 101, 102, 101, 103],
            'Volume': [1000000] * 5
        }, index=dates)

        mock_get_data.return_value = df

        result = self.ta_service.get_technical_analysis('AAPL')

        # Should not error, but may have limited indicators
        self.assertNotIn('error', result)
        self.assertIn('indicators', result)
        self.assertIn('interpretation', result)

    @patch('ta_service.MarketDataFactory.get_historical_data_with_fallback')
    def test_ticker_case_insensitive(self, mock_get_data):
        """Test that ticker is converted to uppercase"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        df = pd.DataFrame({
            'Open': np.random.randn(30) + 100,
            'High': np.random.randn(30) + 101,
            'Low': np.random.randn(30) + 99,
            'Close': np.random.randn(30) + 100,
            'Volume': np.random.randint(1000000, 10000000, 30)
        }, index=dates)

        mock_get_data.return_value = df

        result = self.ta_service.get_technical_analysis('aapl')

        # Should be normalized to uppercase
        self.assertEqual(result['ticker'], 'AAPL')


if __name__ == '__main__':
    unittest.main()
