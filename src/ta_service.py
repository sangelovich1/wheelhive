"""
Technical Analysis Service

Provides a high-level API for technical analysis, combining:
- MarketDataFactory for reliable historical data
- TechnicalAnalysis for indicator calculations
- LLM-friendly interpretation and formatting

Designed for use by:
- MCP server (LLM access)
- Discord bot commands
- Automated analysis workflows

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime
from typing import Any

from providers.market_data_factory import MarketDataFactory
from technical_analysis import TechnicalAnalysis


logger = logging.getLogger(__name__)


class TAService:
    """
    High-level Technical Analysis service.

    Provides comprehensive TA with intelligent defaults and LLM-friendly output.
    """

    def __init__(self):
        """Initialize TA service with market data factory."""
        self.market_data_factory = MarketDataFactory()

    def get_technical_analysis(
        self,
        ticker: str,
        period: str = "3mo",
        interval: str = "1d",
        include_patterns: bool = True
    ) -> dict[str, Any]:
        """
        Get comprehensive technical analysis for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1d, 5d, 1wk, 1mo, 3mo)
            include_patterns: Whether to detect chart patterns (slower)

        Returns:
            Dictionary with comprehensive TA including:
            - current_price: Current price and change
            - indicators: RSI, MACD, Bollinger Bands, Moving Averages, ATR, Volume
            - trend_analysis: Trend direction, strength, and signals
            - support_resistance: Key price levels
            - patterns: Chart patterns (if include_patterns=True)
            - interpretation: Human-readable summary for LLM
        """
        try:
            # Normalize ticker to uppercase
            ticker = ticker.upper()

            logger.info(f"Getting technical analysis for {ticker} (period={period}, interval={interval})")

            # Get historical data
            df = MarketDataFactory.get_historical_data_with_fallback(
                ticker=ticker,
                period=period,
                interval=interval
            )

            if df is None or df.empty:
                return {
                    "error": f"No historical data available for {ticker}",
                    "ticker": ticker,
                    "timestamp": datetime.now().isoformat()
                }

            # Get current price info
            current_price = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2]) if len(df) > 1 else current_price
            price_change = current_price - prev_close
            price_change_pct = (price_change / prev_close * 100) if prev_close else 0

            # Calculate indicators
            indicators = TechnicalAnalysis.calculate_indicators(df)

            # Analyze trend
            trend = TechnicalAnalysis.analyze_trend(df, indicators)

            # Detect support/resistance
            levels = TechnicalAnalysis.detect_support_resistance(df)

            # Detect patterns (optional, slower)
            patterns = {}
            if include_patterns:
                double_top = TechnicalAnalysis.detect_double_top(df)
                double_bottom = TechnicalAnalysis.detect_double_bottom(df)
                patterns = {
                    "double_top": double_top,
                    "double_bottom": double_bottom
                }

            # Generate human-readable interpretation
            interpretation = self._generate_interpretation(
                ticker=ticker,
                current_price=current_price,
                price_change_pct=price_change_pct,
                indicators=indicators,
                trend=trend,
                levels=levels,
                patterns=patterns
            )

            return {
                "ticker": ticker,
                "timestamp": datetime.now().isoformat(),
                "current_price": {
                    "price": round(current_price, 2),
                    "change": round(price_change, 2),
                    "change_percent": round(price_change_pct, 2)
                },
                "indicators": indicators,
                "trend_analysis": trend,
                "support_resistance": levels,
                "patterns": patterns if include_patterns else None,
                "interpretation": interpretation,
                "data_points": len(df),
                "date_range": {
                    "start": df.index[0].strftime("%Y-%m-%d"),
                    "end": df.index[-1].strftime("%Y-%m-%d")
                }
            }

        except Exception as e:
            logger.error(f"Error getting technical analysis for {ticker}: {e}", exc_info=True)
            return {
                "error": str(e),
                "ticker": ticker,
                "timestamp": datetime.now().isoformat()
            }

    def get_technical_summary(self, ticker: str) -> dict[str, Any]:
        """
        Get technical indicator summary for a ticker (fast, no patterns).

        Optimized for speed - uses 1 month of data and skips pattern detection.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with technical summary: overall_signal, key_signals, price_info
        """
        try:
            # Normalize ticker to uppercase
            ticker = ticker.upper()
            # Get 1 month of daily data (fast)
            ta_result = self.get_technical_analysis(
                ticker=ticker,
                period="1mo",
                interval="1d",
                include_patterns=False
            )

            if "error" in ta_result:
                return ta_result

            # Extract key signals
            trend = ta_result.get("trend_analysis", {})
            indicators = ta_result.get("indicators", {})

            signals = []
            bullish_count = 0
            bearish_count = 0

            # RSI signal
            if "rsi_14" in indicators:
                rsi = indicators["rsi_14"]
                if rsi > 70:
                    signals.append(f"RSI overbought ({rsi})")
                    bearish_count += 1
                elif rsi < 30:
                    signals.append(f"RSI oversold ({rsi})")
                    bullish_count += 1
                else:
                    signals.append(f"RSI neutral ({rsi})")

            # MACD signal
            if trend.get("macd_signal") == "bullish":
                signals.append("MACD bullish crossover")
                bullish_count += 1
            elif trend.get("macd_signal") == "bearish":
                signals.append("MACD bearish crossover")
                bearish_count += 1

            # Trend signal
            sma_alignment = trend.get("sma_alignment", "unknown")
            if sma_alignment == "bullish":
                signals.append("Moving averages aligned bullish")
                bullish_count += 1
            elif sma_alignment == "bearish":
                signals.append("Moving averages aligned bearish")
                bearish_count += 1

            # Bollinger Band signal
            bb_position = trend.get("bb_position", "unknown")
            if bb_position == "above_upper_band":
                signals.append("Price above upper Bollinger Band")
                bearish_count += 1
            elif bb_position == "below_lower_band":
                signals.append("Price below lower Bollinger Band")
                bullish_count += 1

            # Overall signal
            if bullish_count > bearish_count:
                overall = "BULLISH"
            elif bearish_count > bullish_count:
                overall = "BEARISH"
            else:
                overall = "NEUTRAL"

            return {
                "ticker": ticker,
                "overall_signal": overall,
                "bullish_signals": bullish_count,
                "bearish_signals": bearish_count,
                "key_signals": signals,
                "price_info": ta_result["current_price"],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting technical summary for {ticker}: {e}", exc_info=True)
            return {
                "error": str(e),
                "ticker": ticker,
                "timestamp": datetime.now().isoformat()
            }

    def _generate_interpretation(
        self,
        ticker: str,
        current_price: float,
        price_change_pct: float,
        indicators: dict[str, Any],
        trend: dict[str, Any],
        levels: dict[str, Any],
        patterns: dict[str, Any]
    ) -> str:
        """
        Generate human-readable interpretation for LLM consumption.

        Returns:
            Formatted string with TA interpretation
        """
        lines = []

        # Header
        lines.append(f"**Technical Analysis: ${ticker}**")
        lines.append(f"Price: ${current_price:.2f} ({price_change_pct:+.2f}%)")
        lines.append("")

        # Momentum indicators
        lines.append("**Momentum:**")
        if "rsi_14" in indicators:
            rsi = indicators["rsi_14"]
            rsi_zone = trend.get("rsi_zone", "unknown")
            lines.append(f"- RSI(14): {rsi:.1f} - {rsi_zone.upper()}")
            if rsi > 70:
                lines.append("  ⚠️ Overbought - potential pullback risk")
            elif rsi < 30:
                lines.append("  💡 Oversold - potential bounce opportunity")

        if "macd" in indicators:
            macd_signal = trend.get("macd_signal", "unknown")
            lines.append(f"- MACD: {macd_signal.upper()} signal")

        lines.append("")

        # Trend indicators
        lines.append("**Trend:**")
        sma_alignment = trend.get("sma_alignment", "unknown")
        lines.append(f"- SMA Alignment: {sma_alignment.upper()}")

        if "sma_20" in indicators and "sma_50" in indicators:
            if trend.get("above_sma_20") and trend.get("above_sma_50"):
                lines.append("  ✅ Price above key moving averages (bullish)")
            elif not trend.get("above_sma_20") and not trend.get("above_sma_50"):
                lines.append("  ⚠️ Price below key moving averages (bearish)")
            else:
                lines.append("  ⚡ Price between moving averages (transitioning)")

        lines.append("")

        # Volatility and support/resistance
        lines.append("**Key Levels:**")
        if "bb_upper" in indicators and "bb_lower" in indicators:
            bb_pos = trend.get("bb_position", "unknown")
            lines.append(f"- Bollinger Bands: Price in {bb_pos.replace('_', ' ')}")
            lines.append(f"  Upper: ${indicators['bb_upper']:.2f} | Lower: ${indicators['bb_lower']:.2f}")

        if levels.get("resistance"):
            resistance_str = ", ".join([f"${r:.2f}" for r in levels["resistance"][:3]])
            lines.append(f"- Resistance: {resistance_str}")

        if levels.get("support"):
            support_str = ", ".join([f"${s:.2f}" for s in levels["support"][:3]])
            lines.append(f"- Support: {support_str}")

        lines.append("")

        # Volume
        if "volume_ratio" in indicators:
            vol_ratio = indicators["volume_ratio"]
            vol_status = trend.get("volume", "normal")
            lines.append(f"**Volume:** {vol_status.replace('_', ' ').title()} (ratio: {vol_ratio:.2f}x)")
            lines.append("")

        # Chart patterns
        if patterns:
            detected_patterns = []
            if patterns.get("double_top", {}).get("detected"):
                dt = patterns["double_top"]
                detected_patterns.append(f"Double Top (bearish) - Target: ${dt['target']:.2f}")
            if patterns.get("double_bottom", {}).get("detected"):
                db = patterns["double_bottom"]
                detected_patterns.append(f"Double Bottom (bullish) - Target: ${db['target']:.2f}")

            if detected_patterns:
                lines.append("**Chart Patterns:**")
                for pattern in detected_patterns:
                    lines.append(f"- {pattern}")
                lines.append("")

        return "\n".join(lines)


# Singleton instance
_ta_service_instance = None


def get_ta_service() -> TAService:
    """Get singleton TA service instance."""
    global _ta_service_instance
    if _ta_service_instance is None:
        _ta_service_instance = TAService()
    return _ta_service_instance
