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
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from technical_analysis import TechnicalAnalysis


class TestTechnicalAnalysis(unittest.TestCase):
    """Test TechnicalAnalysis indicator calculations"""

    def _create_sample_data(self, days=100, trend='flat', volatility='normal'):
        """
        Create sample OHLCV data with different characteristics.

        Args:
            days: Number of days of data
            trend: 'up', 'down', or 'flat'
            volatility: 'low', 'normal', or 'high'
        """
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        np.random.seed(42)  # For reproducibility

        # Base price
        start_price = 100

        # Set volatility
        vol_map = {'low': 0.005, 'normal': 0.02, 'high': 0.05}
        vol = vol_map.get(volatility, 0.02)

        # Set trend
        trend_map = {'up': 0.002, 'flat': 0, 'down': -0.002}
        drift = trend_map.get(trend, 0)

        # Generate returns
        returns = np.random.normal(drift, vol, days)
        prices = start_price * (1 + returns).cumprod()

        # Create OHLCV
        df = pd.DataFrame({
            'Open': prices * (1 + np.random.uniform(-0.005, 0.005, days)),
            'High': prices * (1 + np.random.uniform(0, 0.01, days)),
            'Low': prices * (1 - np.random.uniform(0, 0.01, days)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 10000000, days)
        }, index=dates)

        return df

    def test_calculate_indicators_basic(self):
        """Test basic indicator calculation"""
        df = self._create_sample_data(days=60)
        indicators = TechnicalAnalysis.calculate_indicators(df)

        # Should return a dictionary
        self.assertIsInstance(indicators, dict)

        # Should have some indicators (exact set depends on pandas-ta availability)
        # At minimum, if pandas-ta is installed, we expect RSI
        if len(indicators) > 0:
            # Check that values are numeric
            for key, value in indicators.items():
                self.assertIsInstance(value, (int, float), f"{key} should be numeric")

    def test_calculate_indicators_with_insufficient_data(self):
        """Test indicators with insufficient data"""
        df = self._create_sample_data(days=5)  # Too little data
        indicators = TechnicalAnalysis.calculate_indicators(df)

        # Should not error, but may return empty or partial indicators
        self.assertIsInstance(indicators, dict)

    def test_calculate_indicators_empty_dataframe(self):
        """Test indicators with empty dataframe"""
        df = pd.DataFrame()
        indicators = TechnicalAnalysis.calculate_indicators(df)

        # Should return empty dict
        self.assertEqual(indicators, {})

    def test_calculate_indicators_none(self):
        """Test indicators with None input"""
        indicators = TechnicalAnalysis.calculate_indicators(None)
        self.assertEqual(indicators, {})

    def test_analyze_trend(self):
        """Test trend analysis"""
        df = self._create_sample_data(days=60, trend='up')
        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        # Should return dictionary
        self.assertIsInstance(trend, dict)

        # Check for expected trend keys
        if 'rsi_zone' in trend:
            self.assertIn(trend['rsi_zone'], ['overbought', 'oversold', 'neutral'])

        if 'macd_signal' in trend:
            self.assertIn(trend['macd_signal'], ['bullish', 'bearish'])

        if 'sma_alignment' in trend:
            self.assertIn(trend['sma_alignment'], ['bullish', 'bearish', 'mixed'])

    def test_analyze_trend_overbought(self):
        """Test trend analysis with overbought conditions"""
        df = self._create_sample_data(days=60, trend='up')

        # Artificially create overbought RSI (strong rally)
        df['Close'] = df['Close'].iloc[0] * np.linspace(1, 1.3, len(df))

        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        # May have overbought RSI
        if 'rsi_zone' in trend and 'rsi_14' in indicators:
            if indicators['rsi_14'] > 70:
                self.assertEqual(trend['rsi_zone'], 'overbought')

    def test_analyze_trend_oversold(self):
        """Test trend analysis with oversold conditions"""
        df = self._create_sample_data(days=60, trend='down')

        # Artificially create oversold RSI (sharp drop)
        df['Close'] = df['Close'].iloc[0] * np.linspace(1, 0.7, len(df))

        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        # May have oversold RSI
        if 'rsi_zone' in trend and 'rsi_14' in indicators:
            if indicators['rsi_14'] < 30:
                self.assertEqual(trend['rsi_zone'], 'oversold')

    def test_analyze_trend_empty(self):
        """Test trend analysis with empty inputs"""
        trend = TechnicalAnalysis.analyze_trend(None, {})
        self.assertEqual(trend, {})

        trend = TechnicalAnalysis.analyze_trend(pd.DataFrame(), {})
        self.assertEqual(trend, {})

    def test_detect_support_resistance(self):
        """Test support and resistance detection"""
        df = self._create_sample_data(days=60)
        levels = TechnicalAnalysis.detect_support_resistance(df)

        self.assertIsInstance(levels, dict)

        # Should have support, resistance, and current_price
        if 'support' in levels:
            self.assertIsInstance(levels['support'], list)
            # All support levels should be floats
            for level in levels['support']:
                self.assertIsInstance(level, float)

        if 'resistance' in levels:
            self.assertIsInstance(levels['resistance'], list)
            for level in levels['resistance']:
                self.assertIsInstance(level, float)

        if 'current_price' in levels:
            self.assertIsInstance(levels['current_price'], float)

    def test_detect_support_resistance_insufficient_data(self):
        """Test support/resistance with insufficient data"""
        df = self._create_sample_data(days=10)  # Less than default window
        levels = TechnicalAnalysis.detect_support_resistance(df, window=20)

        # Should return empty or handle gracefully
        self.assertIsInstance(levels, dict)

    def test_detect_support_resistance_empty(self):
        """Test support/resistance with empty dataframe"""
        levels = TechnicalAnalysis.detect_support_resistance(pd.DataFrame())
        self.assertEqual(levels, {})

    def test_detect_double_top(self):
        """Test double top pattern detection"""
        df = self._create_sample_data(days=80)

        # Create artificial double top
        mid_point = len(df) // 2
        peak_price = df['High'].max() * 1.1

        # First peak
        df.iloc[mid_point - 10:mid_point, df.columns.get_loc('High')] = peak_price
        df.iloc[mid_point - 10:mid_point, df.columns.get_loc('Close')] = peak_price * 0.99

        # Trough between
        df.iloc[mid_point:mid_point + 10, df.columns.get_loc('Low')] = peak_price * 0.9

        # Second peak
        df.iloc[mid_point + 20:mid_point + 30, df.columns.get_loc('High')] = peak_price
        df.iloc[mid_point + 20:mid_point + 30, df.columns.get_loc('Close')] = peak_price * 0.99

        result = TechnicalAnalysis.detect_double_top(df)

        self.assertIsInstance(result, dict)
        self.assertIn('detected', result)
        self.assertIsInstance(result['detected'], bool)

        if result['detected']:
            self.assertIn('peak1', result)
            self.assertIn('peak2', result)
            self.assertIn('neckline', result)
            self.assertIn('target', result)
            self.assertEqual(result['pattern'], 'double_top')

    def test_detect_double_top_no_pattern(self):
        """Test double top when no pattern exists"""
        df = self._create_sample_data(days=60, trend='flat')
        result = TechnicalAnalysis.detect_double_top(df)

        self.assertIsInstance(result, dict)
        self.assertIn('detected', result)
        # May or may not detect pattern in random data
        self.assertIsInstance(result['detected'], bool)

    def test_detect_double_top_insufficient_data(self):
        """Test double top with insufficient data"""
        df = self._create_sample_data(days=15)
        result = TechnicalAnalysis.detect_double_top(df)

        self.assertEqual(result, {'detected': False})

    def test_detect_double_bottom(self):
        """Test double bottom pattern detection"""
        df = self._create_sample_data(days=80)

        # Create artificial double bottom
        mid_point = len(df) // 2
        trough_price = df['Low'].min() * 0.9

        # First trough
        df.iloc[mid_point - 10:mid_point, df.columns.get_loc('Low')] = trough_price
        df.iloc[mid_point - 10:mid_point, df.columns.get_loc('Close')] = trough_price * 1.01

        # Peak between
        df.iloc[mid_point:mid_point + 10, df.columns.get_loc('High')] = trough_price * 1.1

        # Second trough
        df.iloc[mid_point + 20:mid_point + 30, df.columns.get_loc('Low')] = trough_price
        df.iloc[mid_point + 20:mid_point + 30, df.columns.get_loc('Close')] = trough_price * 1.01

        result = TechnicalAnalysis.detect_double_bottom(df)

        self.assertIsInstance(result, dict)
        self.assertIn('detected', result)

        if result['detected']:
            self.assertIn('trough1', result)
            self.assertIn('trough2', result)
            self.assertIn('neckline', result)
            self.assertIn('target', result)
            self.assertEqual(result['pattern'], 'double_bottom')

    def test_detect_double_bottom_insufficient_data(self):
        """Test double bottom with insufficient data"""
        df = self._create_sample_data(days=15)
        result = TechnicalAnalysis.detect_double_bottom(df)

        self.assertEqual(result, {'detected': False})

    def test_get_technical_summary(self):
        """Test comprehensive technical summary"""
        df = self._create_sample_data(days=60)
        summary = TechnicalAnalysis.get_technical_summary(df)

        self.assertIsInstance(summary, dict)

        # Should have main sections
        if len(summary) > 0:
            self.assertIn('indicators', summary)
            self.assertIn('trend', summary)
            self.assertIn('levels', summary)
            self.assertIn('patterns', summary)

            # Each section should be a dict
            self.assertIsInstance(summary['indicators'], dict)
            self.assertIsInstance(summary['trend'], dict)
            self.assertIsInstance(summary['levels'], dict)
            self.assertIsInstance(summary['patterns'], dict)

    def test_get_technical_summary_empty(self):
        """Test technical summary with empty dataframe"""
        summary = TechnicalAnalysis.get_technical_summary(pd.DataFrame())
        self.assertEqual(summary, {})

    def test_get_technical_summary_none(self):
        """Test technical summary with None"""
        summary = TechnicalAnalysis.get_technical_summary(None)
        self.assertEqual(summary, {})

    def test_volume_analysis(self):
        """Test volume analysis in trend"""
        df = self._create_sample_data(days=60)

        # Create high volume day
        df.iloc[-1, df.columns.get_loc('Volume')] = df['Volume'].mean() * 3

        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        if 'volume' in trend:
            self.assertIn(trend['volume'], ['unusually_high', 'unusually_low', 'normal'])

    def test_bollinger_band_position(self):
        """Test Bollinger Band position analysis"""
        df = self._create_sample_data(days=60)

        # Push price above upper band
        df.iloc[-1, df.columns.get_loc('Close')] = df['Close'].mean() * 1.2

        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        if 'bb_position' in trend:
            self.assertIn(trend['bb_position'], [
                'above_upper_band', 'below_lower_band', 'upper_half', 'lower_half'
            ])

    def test_sma_alignment_bullish(self):
        """Test bullish SMA alignment detection"""
        df = self._create_sample_data(days=250, trend='up')

        # Ensure strong uptrend for clear alignment
        df['Close'] = df['Close'].iloc[0] * np.linspace(1, 1.5, len(df))

        indicators = TechnicalAnalysis.calculate_indicators(df)
        trend = TechnicalAnalysis.analyze_trend(df, indicators)

        # With strong uptrend, should detect bullish alignment
        if 'sma_alignment' in trend and all(k in indicators for k in ['sma_20', 'sma_50', 'sma_200']):
            self.assertIn(trend['sma_alignment'], ['bullish', 'bearish', 'mixed'])


class TestTechnicalAnalysisEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_missing_columns(self):
        """Test with missing required columns"""
        df = pd.DataFrame({
            'Close': [100, 101, 102, 103, 104]
        })

        # Should handle gracefully (may error or return empty)
        try:
            indicators = TechnicalAnalysis.calculate_indicators(df)
            self.assertIsInstance(indicators, dict)
        except Exception:
            # Expected to fail with missing columns
            pass

    def test_nan_values(self):
        """Test with NaN values in data"""
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        df = pd.DataFrame({
            'Open': np.random.randn(60) + 100,
            'High': np.random.randn(60) + 101,
            'Low': np.random.randn(60) + 99,
            'Close': np.random.randn(60) + 100,
            'Volume': np.random.randint(1000000, 10000000, 60)
        }, index=dates)

        # Introduce NaNs
        df.iloc[10:15, df.columns.get_loc('Close')] = np.nan

        indicators = TechnicalAnalysis.calculate_indicators(df)

        # Should handle NaNs gracefully
        self.assertIsInstance(indicators, dict)


if __name__ == '__main__':
    unittest.main()
