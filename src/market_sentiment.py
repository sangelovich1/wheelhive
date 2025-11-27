"""
Market Sentiment Indicators

Provides access to key market sentiment data:
- VIX (CBOE Volatility Index) - Market fear gauge
- CNN Fear & Greed Index - Overall market sentiment (0-100)
- Crypto Fear & Greed Index - Crypto market sentiment (0-100)

Uses MarketDataFactory for resilient data fetching with automatic fallback.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime
from typing import Any

import requests
from tabulate import tabulate

from providers.market_data_factory import MarketDataFactory


logger = logging.getLogger(__name__)


class MarketSentiment:
    """Fetch and process market sentiment indicators"""

    # Fear & Greed API endpoints
    CRYPTO_FEAR_GREED_API = "https://api.alternative.me/fng/"

    def __init__(self):
        """Initialize market sentiment provider"""
        logger.info("Initialized Market Sentiment provider")

    def get_treasury_yields(self) -> dict[str, Any] | None:
        """
        Get US Treasury yields and calculate yield curve slope.

        Monitors:
        - 10-Year Treasury Yield (^TNX): Long-term benchmark rate
        - 2-Year Treasury Yield (^IRX): Short-term rate
        - Yield Spread (10Y - 2Y): Inverted curve (negative) signals recession fears

        Generally:
        - Normal curve: 10Y > 2Y (positive spread, healthy economy)
        - Flat curve: 10Y ≈ 2Y (uncertainty)
        - Inverted curve: 10Y < 2Y (recession warning)

        Returns:
            Dictionary with treasury data or None if error
            {
                'ten_year': float,
                'two_year': float,
                'spread': float,
                'spread_interpretation': str,
                'timestamp': str
            }
        """
        try:
            # Get 10-Year yield
            ten_year_hist = MarketDataFactory.get_historical_data_with_fallback(
                "^TNX",
                period="1d",
                interval="1d"
            )

            # Get 2-Year yield
            two_year_hist = MarketDataFactory.get_historical_data_with_fallback(
                "^IRX",
                period="1d",
                interval="1d"
            )

            if ten_year_hist.empty or two_year_hist.empty:
                logger.error("No treasury yield data available")
                return None

            ten_year = ten_year_hist["Close"].iloc[-1]
            two_year = two_year_hist["Close"].iloc[-1]
            spread = ten_year - two_year

            # Interpret yield curve
            if spread > 1.0:
                interpretation = "Steep"
            elif spread > 0.2:
                interpretation = "Normal"
            elif spread > -0.2:
                interpretation = "Flat"
            else:
                interpretation = "Inverted"

            return {
                "ten_year": round(ten_year, 2),
                "two_year": round(two_year, 2),
                "spread": round(spread, 2),
                "spread_interpretation": interpretation,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error fetching treasury yields: {e}", exc_info=True)
            return None

    def get_vix(self) -> dict[str, Any] | None:
        """
        Get current VIX (CBOE Volatility Index) data.

        The VIX measures expected volatility over the next 30 days.
        Generally:
        - VIX < 12: Very low volatility (complacent market)
        - VIX 12-20: Normal volatility
        - VIX 20-30: Elevated volatility (fear)
        - VIX > 30: High volatility (significant fear)

        Returns:
            Dictionary with VIX data or None if error
            {
                'symbol': 'VIX',
                'price': float,
                'change': float,
                'change_percent': float,
                'interpretation': str,
                'timestamp': str
            }
        """
        try:
            # Get 2 days of VIX data to calculate change
            hist = MarketDataFactory.get_historical_data_with_fallback(
                "^VIX",
                period="2d",
                interval="1d"
            )

            if hist.empty:
                logger.error("No VIX data available")
                return None

            current_price = hist["Close"].iloc[-1]
            prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
            change = current_price - prev_price
            change_percent = (change / prev_price * 100) if prev_price else 0

            # Interpret VIX level
            if current_price < 12:
                interpretation = "Complacent"
            elif current_price < 20:
                interpretation = "Calm"
            elif current_price < 30:
                interpretation = "Fearful"
            else:
                interpretation = "High Fear"

            return {
                "symbol": "VIX",
                "price": round(current_price, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "interpretation": interpretation,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error fetching VIX data: {e}", exc_info=True)
            return None

    def get_fear_and_greed_index(self) -> dict[str, Any] | None:
        """
        Calculate Fear & Greed Index based on VIX and SPY momentum.

        Custom implementation after CNN started blocking API access.
        Based on:
        - VIX levels (primary weight 70%): Low VIX = Greed, High VIX = Fear
        - SPY 20-day momentum (30%): Rising = Greed, Falling = Fear

        VIX Interpretation:
        - < 12: Extreme Greed (complacency)
        - 12-16: Greed (low fear)
        - 16-20: Neutral
        - 20-30: Fear (elevated volatility)
        - > 30: Extreme Fear (panic)

        Returns:
            Dictionary with Fear & Greed data or None if error
            {
                'value': int,  # 0-100
                'classification': str,  # Extreme Fear, Fear, Neutral, Greed, Extreme Greed
                'previous_value': int,
                'timestamp': str,
                'components': dict  # Breakdown of VIX and momentum scores
            }
        """
        try:
            # Get VIX data
            vix_info = self.get_vix()
            if not vix_info or "price" not in vix_info:
                logger.warning("Cannot calculate Fear & Greed: VIX data unavailable")
                return None

            vix_current = vix_info["price"]
            # Calculate previous from current - change
            vix_previous = vix_current - vix_info.get("change", 0)

            # Get SPY data for momentum calculation
            spy_data = MarketDataFactory.get_historical_data_with_fallback(
                ticker="SPY",
                period="1mo",
                interval="1d"
            )

            # Calculate VIX-based fear score (0=greed, 100=fear)
            # Invert VIX to greed scale: lower VIX = higher greed
            if vix_current < 12:
                vix_score = 85  # Extreme Greed
            elif vix_current < 16:
                vix_score = 65  # Greed
            elif vix_current < 20:
                vix_score = 50  # Neutral
            elif vix_current < 30:
                vix_score = 30  # Fear
            else:
                vix_score = 15  # Extreme Fear

            # Calculate SPY momentum score (0=fear, 100=greed)
            momentum_score = 50  # Default neutral
            momentum_pct = 0.0
            if spy_data is not None and len(spy_data) >= 20:
                current_price = spy_data["Close"].iloc[-1]
                price_20d_ago = spy_data["Close"].iloc[-20]
                momentum_pct = ((current_price - price_20d_ago) / price_20d_ago) * 100

                # Map momentum to 0-100 scale
                # -10% or worse = 0 (extreme fear)
                # +10% or better = 100 (extreme greed)
                momentum_score = max(0, min(100, 50 + (momentum_pct * 5)))

            # Weighted average: 70% VIX, 30% momentum
            final_score = int(vix_score * 0.7 + momentum_score * 0.3)

            # Classify based on final score
            if final_score >= 75:
                classification = "Extreme Greed"
            elif final_score >= 55:
                classification = "Greed"
            elif final_score >= 45:
                classification = "Neutral"
            elif final_score >= 25:
                classification = "Fear"
            else:
                classification = "Extreme Fear"

            # Calculate previous value using previous VIX
            vix_prev_score = 50
            if vix_previous < 12:
                vix_prev_score = 85
            elif vix_previous < 16:
                vix_prev_score = 65
            elif vix_previous < 20:
                vix_prev_score = 50
            elif vix_previous < 30:
                vix_prev_score = 30
            else:
                vix_prev_score = 15

            previous_value = int(vix_prev_score * 0.7 + momentum_score * 0.3)

            return {
                "value": final_score,
                "classification": classification,
                "previous_value": previous_value,
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "vix_score": int(vix_score),
                    "vix_value": vix_current,
                    "momentum_score": int(momentum_score),
                    "momentum_pct": round(momentum_pct, 2)
                }
            }

        except Exception as e:
            logger.warning(f"Error calculating Fear & Greed Index: {e}", exc_info=True)
            return None

    def get_crypto_fear_and_greed_index(self) -> dict[str, Any] | None:
        """
        Get Crypto Fear & Greed Index from alternative.me.

        The index ranges from 0 (Extreme Fear) to 100 (Extreme Greed).
        It's based on:
        - Volatility (25%)
        - Market Momentum/Volume (25%)
        - Social Media (15%)
        - Surveys (15%)
        - Dominance (10%)
        - Trends (10%)

        Returns:
            Dictionary with Crypto Fear & Greed data or None if error
            {
                'value': int,  # 0-100
                'classification': str,  # Extreme Fear, Fear, Neutral, Greed, Extreme Greed
                'timestamp': str,
                'time_until_update': str (optional)
            }
        """
        try:
            response = requests.get(self.CRYPTO_FEAR_GREED_API, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" not in data or not data["data"]:
                logger.error("No crypto fear & greed data available")
                return None

            current = data["data"][0]
            value = int(current["value"])
            classification = current["value_classification"]

            return {
                "value": value,
                "classification": classification,
                "timestamp": datetime.fromtimestamp(int(current["timestamp"])).isoformat(),
                "time_until_update": current.get("time_until_update")
            }

        except Exception as e:
            logger.error(f"Error fetching Crypto Fear & Greed Index: {e}", exc_info=True)
            return None

    def get_all_sentiment_indicators(self) -> dict[str, Any]:
        """
        Get all market sentiment indicators in one call.

        Returns:
            Dictionary containing all sentiment data
            {
                'vix': {...},
                'fear_and_greed': {...},
                'crypto_fear_and_greed': {...},
                'treasury_yields': {...},
                'summary': str
            }
        """
        vix = self.get_vix()
        fear_greed = self.get_fear_and_greed_index()
        crypto_fear_greed = self.get_crypto_fear_and_greed_index()
        treasury = self.get_treasury_yields()

        # Generate summary
        summary_parts = []

        if vix:
            summary_parts.append(f"VIX: {vix['price']} ({vix['interpretation']})")

        if fear_greed:
            summary_parts.append(f"Fear & Greed: {fear_greed['value']}/100 ({fear_greed['classification']})")

        if crypto_fear_greed:
            summary_parts.append(f"Crypto F&G: {crypto_fear_greed['value']}/100 ({crypto_fear_greed['classification']})")

        if treasury:
            summary_parts.append(f"10Y-2Y Spread: {treasury['spread']}%")

        summary = " | ".join(summary_parts) if summary_parts else "No sentiment data available"

        return {
            "vix": vix,
            "fear_and_greed": fear_greed,
            "crypto_fear_and_greed": crypto_fear_greed,
            "treasury_yields": treasury,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }

    def as_dict(self) -> dict[str, Any]:
        """
        Get market sentiment data as a dictionary for JSON serialization.

        Alias for get_all_sentiment_indicators() following the standardized
        data export pattern (as_df, as_dict, as_table).

        Returns:
            Dictionary containing all sentiment data (same as get_all_sentiment_indicators)
        """
        return self.get_all_sentiment_indicators()

    def as_table(self) -> str:
        """
        Get market sentiment indicators formatted as a table string.

        Returns:
            Formatted table string with all sentiment indicators
        """
        sentiment_data = self.get_all_sentiment_indicators()

        # Build table data
        table_data = []

        if sentiment_data["vix"]:
            vix = sentiment_data["vix"]
            table_data.append([
                "VIX",
                vix["price"],
                f"{vix['change']:+.2f} ({vix['change_percent']:+.1f}%)",
                vix["interpretation"]
            ])

        if sentiment_data["fear_and_greed"]:
            fg = sentiment_data["fear_and_greed"]
            table_data.append([
                "Fear & Greed",
                f"{fg['value']}/100",
                fg["classification"],
                ""
            ])

        if sentiment_data["crypto_fear_and_greed"]:
            cfg = sentiment_data["crypto_fear_and_greed"]
            table_data.append([
                "Crypto F&G",
                f"{cfg['value']}/100",
                cfg["classification"],
                ""
            ])

        if sentiment_data["treasury_yields"]:
            treasury = sentiment_data["treasury_yields"]
            table_data.append([
                "10-Year Yield",
                f"{treasury['ten_year']}%",
                "",
                ""
            ])
            table_data.append([
                "2-Year Yield",
                f"{treasury['two_year']}%",
                "",
                ""
            ])
            table_data.append([
                "Yield Spread",
                f"{treasury['spread']:+.2f}%",
                treasury["spread_interpretation"],
                ""
            ])

        headers = ["Indicator", "Value", "Change", "Status"]
        return tabulate(table_data, headers=headers, tablefmt="simple")


def main():
    """Test the market sentiment indicators"""
    import sys
    sys.path.insert(0, ".")

    sentiment = MarketSentiment()

    print("=== MARKET SENTIMENT INDICATORS ===\n")

    # VIX
    print("VIX (Volatility Index):")
    vix = sentiment.get_vix()
    if vix:
        print(f"  Price: {vix['price']}")
        print(f"  Change: {vix['change']} ({vix['change_percent']}%)")
        print(f"  Interpretation: {vix['interpretation']}")
    else:
        print("  Error fetching VIX data")
    print()

    # Fear & Greed
    print("Fear & Greed Index:")
    fg = sentiment.get_fear_and_greed_index()
    if fg:
        print(f"  Value: {fg['value']}/100")
        print(f"  Classification: {fg['classification']}")
        if fg.get("previous_value"):
            print(f"  Previous: {fg['previous_value']}")
        if fg.get("note"):
            print(f"  Note: {fg['note']}")
    else:
        print("  Error fetching Fear & Greed data")
    print()

    # Crypto Fear & Greed
    print("Crypto Fear & Greed Index:")
    cfg = sentiment.get_crypto_fear_and_greed_index()
    if cfg:
        print(f"  Value: {cfg['value']}/100")
        print(f"  Classification: {cfg['classification']}")
    else:
        print("  Error fetching Crypto Fear & Greed data")
    print()

    # Treasury Yields
    print("Treasury Yields:")
    treasury = sentiment.get_treasury_yields()
    if treasury:
        print(f"  10-Year: {treasury['ten_year']}%")
        print(f"  2-Year: {treasury['two_year']}%")
        print(f"  Spread (10Y-2Y): {treasury['spread']}%")
        print(f"  Interpretation: {treasury['spread_interpretation']}")
    else:
        print("  Error fetching treasury yield data")
    print()

    # All together (using as_dict() for consistency with data export pattern)
    print("=== ALL SENTIMENT INDICATORS ===")
    all_data = sentiment.as_dict()
    print(all_data["summary"])
    print()

    # Table format
    print("=== TABLE FORMAT ===")
    print(sentiment.as_table())


if __name__ == "__main__":
    main()
