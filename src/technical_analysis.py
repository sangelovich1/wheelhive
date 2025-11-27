"""
Technical Analysis Module

Provides technical indicators and chart pattern detection for stock analysis.
Uses pandas-ta for indicator calculations and custom algorithms for pattern detection.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any

import pandas as pd


try:
    import pandas_ta as ta
except ImportError:
    ta = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TechnicalAnalysis:
    """Technical analysis indicators and pattern detection."""

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> dict[str, Any]:
        """
        Calculate technical indicators from OHLCV data.

        Args:
            df: DataFrame with columns: Open, High, Low, Close, Volume

        Returns:
            Dictionary with indicator values
        """
        if df is None or df.empty:
            return {}

        if ta is None:
            logger.warning("pandas-ta not installed, returning empty indicators")
            return {}

        try:
            indicators = {}

            # === MOMENTUM INDICATORS ===
            # RSI (Relative Strength Index) - overbought/oversold
            rsi = ta.rsi(df["Close"], length=14)
            if rsi is not None and not rsi.empty:
                indicators["rsi_14"] = round(float(rsi.iloc[-1]), 2)

            # === TREND INDICATORS ===
            # Simple Moving Averages
            sma_20 = ta.sma(df["Close"], length=20)
            sma_50 = ta.sma(df["Close"], length=50)
            sma_200 = ta.sma(df["Close"], length=200)

            if sma_20 is not None and not sma_20.empty:
                indicators["sma_20"] = round(float(sma_20.iloc[-1]), 2)
            if sma_50 is not None and not sma_50.empty:
                indicators["sma_50"] = round(float(sma_50.iloc[-1]), 2)
            if sma_200 is not None and not sma_200.empty:
                indicators["sma_200"] = round(float(sma_200.iloc[-1]), 2)

            # Exponential Moving Average
            ema_12 = ta.ema(df["Close"], length=12)
            if ema_12 is not None and not ema_12.empty:
                indicators["ema_12"] = round(float(ema_12.iloc[-1]), 2)

            # === VOLATILITY INDICATORS ===
            # Bollinger Bands
            bbands = ta.bbands(df["Close"], length=20, std=2)  # type: ignore[arg-type]
            if bbands is not None and not bbands.empty:
                # Column names can vary by pandas-ta version, find them dynamically
                bb_cols = bbands.columns.tolist()
                upper_col = next((col for col in bb_cols if "BBU" in col or "upper" in col.lower()), None)
                middle_col = next((col for col in bb_cols if "BBM" in col or "middle" in col.lower() or "basis" in col.lower()), None)
                lower_col = next((col for col in bb_cols if "BBL" in col or "lower" in col.lower()), None)

                if upper_col:
                    indicators["bb_upper"] = round(float(bbands[upper_col].iloc[-1]), 2)
                if middle_col:
                    indicators["bb_middle"] = round(float(bbands[middle_col].iloc[-1]), 2)
                if lower_col:
                    indicators["bb_lower"] = round(float(bbands[lower_col].iloc[-1]), 2)

            # ATR (Average True Range) - volatility measure
            atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
            if atr is not None and not atr.empty:
                indicators["atr_14"] = round(float(atr.iloc[-1]), 2)

            # === MACD (Moving Average Convergence Divergence) ===
            macd_result = ta.macd(df["Close"])
            if macd_result is not None and not macd_result.empty:
                # Column names can vary by pandas-ta version, find them dynamically
                macd_cols = macd_result.columns.tolist()
                macd_col = next((col for col in macd_cols if "MACD_" in col and "h" not in col.lower() and "s" not in col.lower()), None)
                signal_col = next((col for col in macd_cols if "MACD" in col and ("s" in col.lower() or "signal" in col.lower())), None)
                hist_col = next((col for col in macd_cols if "MACD" in col and ("h" in col.lower() or "histogram" in col.lower())), None)

                if macd_col:
                    indicators["macd"] = round(float(macd_result[macd_col].iloc[-1]), 2)
                if signal_col:
                    indicators["macd_signal"] = round(float(macd_result[signal_col].iloc[-1]), 2)
                if hist_col:
                    indicators["macd_histogram"] = round(float(macd_result[hist_col].iloc[-1]), 2)

            # === VOLUME INDICATORS ===
            # Volume SMA for unusual volume detection
            vol_sma = ta.sma(df["Volume"], length=20)
            if vol_sma is not None and not vol_sma.empty:
                indicators["volume_sma_20"] = round(float(vol_sma.iloc[-1]), 0)
                current_volume = float(df["Volume"].iloc[-1])
                indicators["volume_ratio"] = round(current_volume / float(vol_sma.iloc[-1]), 2)

            return indicators

        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
            return {}

    @staticmethod
    def analyze_trend(df: pd.DataFrame, indicators: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze trend direction and strength.

        Args:
            df: DataFrame with OHLCV data
            indicators: Dictionary with calculated indicators

        Returns:
            Dictionary with trend analysis
        """
        if df is None or df.empty or not indicators:
            return {}

        try:
            current_price = float(df["Close"].iloc[-1])
            trend = {}

            # Position relative to moving averages
            if "sma_20" in indicators:
                trend["above_sma_20"] = current_price > indicators["sma_20"]
            if "sma_50" in indicators:
                trend["above_sma_50"] = current_price > indicators["sma_50"]
            if "sma_200" in indicators:
                trend["above_sma_200"] = current_price > indicators["sma_200"]

            # SMA alignment (trend confirmation)
            if all(k in indicators for k in ["sma_20", "sma_50", "sma_200"]):
                if indicators["sma_20"] > indicators["sma_50"] > indicators["sma_200"]:
                    trend["sma_alignment"] = "bullish"
                elif indicators["sma_20"] < indicators["sma_50"] < indicators["sma_200"]:
                    trend["sma_alignment"] = "bearish"
                else:
                    trend["sma_alignment"] = "mixed"

            # RSI zones
            if "rsi_14" in indicators:
                rsi = indicators["rsi_14"]
                if rsi > 70:
                    trend["rsi_zone"] = "overbought"
                elif rsi < 30:
                    trend["rsi_zone"] = "oversold"
                else:
                    trend["rsi_zone"] = "neutral"

            # Bollinger Band position
            if all(k in indicators for k in ["bb_upper", "bb_lower", "bb_middle"]):
                if current_price > indicators["bb_upper"]:
                    trend["bb_position"] = "above_upper_band"
                elif current_price < indicators["bb_lower"]:
                    trend["bb_position"] = "below_lower_band"
                elif current_price > indicators["bb_middle"]:
                    trend["bb_position"] = "upper_half"
                else:
                    trend["bb_position"] = "lower_half"

            # MACD signal
            if "macd" in indicators and "macd_signal" in indicators:
                if indicators["macd"] > indicators["macd_signal"]:
                    trend["macd_signal"] = "bullish"
                else:
                    trend["macd_signal"] = "bearish"

            # Volume analysis
            if "volume_ratio" in indicators:
                vol_ratio = indicators["volume_ratio"]
                if vol_ratio > 1.5:
                    trend["volume"] = "unusually_high"
                elif vol_ratio < 0.5:
                    trend["volume"] = "unusually_low"
                else:
                    trend["volume"] = "normal"

            return trend

        except Exception as e:
            logger.error(f"Error analyzing trend: {e}", exc_info=True)
            return {}

    @staticmethod
    def detect_support_resistance(df: pd.DataFrame, window: int = 20, num_levels: int = 3) -> dict[str, list[float]]:
        """
        Detect support and resistance levels.

        Args:
            df: DataFrame with OHLCV data
            window: Window size for peak/trough detection
            num_levels: Number of levels to return

        Returns:
            Dictionary with support and resistance levels
        """
        if df is None or df.empty or len(df) < window:
            return {}

        try:
            # Find local peaks (resistance) and troughs (support)
            highs = df["High"].rolling(window=window, center=True).max()
            lows = df["Low"].rolling(window=window, center=True).min()

            # Identify resistance levels (local peaks)
            resistance_points = df[df["High"] == highs]["High"].dropna().unique()
            resistance_levels = sorted(resistance_points, reverse=True)[:num_levels]

            # Identify support levels (local troughs)
            support_points = df[df["Low"] == lows]["Low"].dropna().unique()
            support_levels = sorted(support_points)[:num_levels]

            current_price = float(df["Close"].iloc[-1])
            return {
                "resistance": [round(float(x), 2) for x in resistance_levels],
                "support": [round(float(x), 2) for x in support_levels],
                "current_price": round(current_price, 2)  # type: ignore[arg-type]
            }

        except Exception as e:
            logger.error(f"Error detecting support/resistance: {e}", exc_info=True)
            return {}

    @staticmethod
    def detect_double_top(df: pd.DataFrame, tolerance: float = 0.02) -> dict[str, Any]:
        """
        Detect double top pattern (bearish reversal).

        Args:
            df: DataFrame with OHLCV data
            tolerance: Price tolerance for peak similarity (default 2%)

        Returns:
            Dictionary with pattern detection results
        """
        if df is None or df.empty or len(df) < 20:
            return {"detected": False}

        try:
            # Look at last 60 bars
            recent_df = df.tail(60) if len(df) > 60 else df

            # Find local peaks
            peaks = []
            for i in range(5, len(recent_df) - 5):
                if (recent_df["High"].iloc[i] > recent_df["High"].iloc[i-5:i].max() and
                    recent_df["High"].iloc[i] > recent_df["High"].iloc[i+1:i+6].max()):
                    peaks.append((i, recent_df["High"].iloc[i]))

            # Need at least 2 peaks
            if len(peaks) < 2:
                return {"detected": False}

            # Check last two peaks for double top
            peak1_idx, peak1_price = peaks[-2]
            peak2_idx, peak2_price = peaks[-1]

            # Peaks should be similar in price
            price_diff = abs(peak1_price - peak2_price) / peak1_price
            if price_diff > tolerance:
                return {"detected": False}

            # Find the trough between peaks (neckline)
            between_df = recent_df.iloc[peak1_idx:peak2_idx]
            if between_df.empty:
                return {"detected": False}

            neckline = float(between_df["Low"].min())

            # Price target = neckline - (peak - neckline)
            height = peak1_price - neckline
            target = neckline - height

            return {
                "detected": True,
                "peak1": round(float(peak1_price), 2),
                "peak2": round(float(peak2_price), 2),
                "neckline": round(neckline, 2),
                "target": round(target, 2),
                "pattern": "double_top"
            }

        except Exception as e:
            logger.error(f"Error detecting double top: {e}", exc_info=True)
            return {"detected": False}

    @staticmethod
    def detect_double_bottom(df: pd.DataFrame, tolerance: float = 0.02) -> dict[str, Any]:
        """
        Detect double bottom pattern (bullish reversal).

        Args:
            df: DataFrame with OHLCV data
            tolerance: Price tolerance for trough similarity (default 2%)

        Returns:
            Dictionary with pattern detection results
        """
        if df is None or df.empty or len(df) < 20:
            return {"detected": False}

        try:
            # Look at last 60 bars
            recent_df = df.tail(60) if len(df) > 60 else df

            # Find local troughs
            troughs = []
            for i in range(5, len(recent_df) - 5):
                if (recent_df["Low"].iloc[i] < recent_df["Low"].iloc[i-5:i].min() and
                    recent_df["Low"].iloc[i] < recent_df["Low"].iloc[i+1:i+6].min()):
                    troughs.append((i, recent_df["Low"].iloc[i]))

            # Need at least 2 troughs
            if len(troughs) < 2:
                return {"detected": False}

            # Check last two troughs for double bottom
            trough1_idx, trough1_price = troughs[-2]
            trough2_idx, trough2_price = troughs[-1]

            # Troughs should be similar in price
            price_diff = abs(trough1_price - trough2_price) / trough1_price
            if price_diff > tolerance:
                return {"detected": False}

            # Find the peak between troughs (neckline)
            between_df = recent_df.iloc[trough1_idx:trough2_idx]
            if between_df.empty:
                return {"detected": False}

            neckline = float(between_df["High"].max())

            # Price target = neckline + (neckline - trough)
            height = neckline - trough1_price
            target = neckline + height

            return {
                "detected": True,
                "trough1": round(float(trough1_price), 2),
                "trough2": round(float(trough2_price), 2),
                "neckline": round(neckline, 2),
                "target": round(target, 2),
                "pattern": "double_bottom"
            }

        except Exception as e:
            logger.error(f"Error detecting double bottom: {e}", exc_info=True)
            return {"detected": False}

    @staticmethod
    def get_technical_summary(df: pd.DataFrame) -> dict[str, Any]:
        """
        Get comprehensive technical analysis summary.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with full technical analysis
        """
        if df is None or df.empty:
            return {}

        try:
            # Calculate indicators
            indicators = TechnicalAnalysis.calculate_indicators(df)

            # Analyze trend
            trend = TechnicalAnalysis.analyze_trend(df, indicators)

            # Detect support/resistance
            levels = TechnicalAnalysis.detect_support_resistance(df)

            # Detect chart patterns
            double_top = TechnicalAnalysis.detect_double_top(df)
            double_bottom = TechnicalAnalysis.detect_double_bottom(df)

            return {
                "indicators": indicators,
                "trend": trend,
                "levels": levels,
                "patterns": {
                    "double_top": double_top,
                    "double_bottom": double_bottom
                }
            }

        except Exception as e:
            logger.error(f"Error generating technical summary: {e}", exc_info=True)
            return {}
