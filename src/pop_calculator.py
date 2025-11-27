"""
Probability of Profit (POP) Calculator

Calculates the probability of profit for option positions using the Black-Scholes model
and normal distribution. Useful for evaluating risk/reward before entering trades.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import math
from datetime import datetime
from typing import Any

from scipy.stats import norm

from providers.market_data_factory import MarketDataFactory


logger = logging.getLogger(__name__)


class POPCalculator:
    """
    Calculate Probability of Profit (POP) for option positions.

    Uses Black-Scholes model with implied volatility to calculate the probability
    that an option will expire out-of-the-money (profitable for sellers).
    """

    RISK_FREE_RATE = 0.045  # Current ~4.5% risk-free rate

    def __init__(self):
        """Initialize the POP calculator."""
        self._price_cache = {}

    def calculate_pop(
        self,
        ticker: str,
        strike: float,
        expiration_date: str,
        option_type: str,
        premium: float | None = None,
        iv: float | None = None,
        current_price: float | None = None
    ) -> dict[str, Any]:
        """
        Calculate probability of profit for an option position.

        Args:
            ticker: Stock ticker symbol
            strike: Option strike price
            expiration_date: Expiration date (YYYY-MM-DD format)
            option_type: 'PUT' or 'CALL'
            premium: Premium received/paid (optional, for expected value calc)
            iv: Implied volatility as percentage (e.g., 50.0 for 50%)
            current_price: Current stock price (fetched if not provided)

        Returns:
            Dictionary with POP analysis:
            {
                'ticker': str,
                'current_price': float,
                'strike': float,
                'option_type': str,
                'days_to_expiration': int,
                'iv_percent': float,
                'probability_otm': float,  # Probability of expiring OTM (good for seller)
                'probability_itm': float,  # Probability of expiring ITM
                'breakeven_price': float,  # Including premium (if provided)
                'expected_value': float,   # Expected profit (if premium provided)
                'distance_to_strike_pct': float,
                'status': str  # 'OTM', 'ATM', or 'ITM'
            }
        """
        option_type = option_type.upper()
        if option_type not in ["PUT", "CALL"]:
            raise ValueError("option_type must be 'PUT' or 'CALL'")

        # Fetch current price if not provided
        if current_price is None:
            current_price = self._fetch_current_price(ticker)
            if current_price == 0.0:
                raise ValueError(f"Could not fetch current price for {ticker}")

        # Calculate days to expiration
        exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        days_to_exp = (exp_date - datetime.now()).days
        if days_to_exp < 0:
            raise ValueError("Expiration date is in the past")

        years_to_exp = days_to_exp / 365.25

        # Use provided IV or estimate from historical volatility
        if iv is None:
            iv = self._estimate_iv(ticker)
        iv_decimal = iv / 100.0  # Convert percentage to decimal

        # Calculate d2 from Black-Scholes
        # d2 = [ln(S/K) + (r - 0.5*σ²)*T] / (σ*√T)
        if years_to_exp > 0:
            d2 = (
                math.log(current_price / strike) +
                (self.RISK_FREE_RATE - 0.5 * iv_decimal ** 2) * years_to_exp
            ) / (iv_decimal * math.sqrt(years_to_exp))
        else:
            # At expiration, it's binary
            d2 = float("inf") if current_price > strike else float("-inf")

        # Calculate probabilities
        if option_type == "PUT":
            # For PUT sellers: probability of staying above strike (OTM)
            prob_otm = norm.cdf(d2)
            prob_itm = 1 - prob_otm
        else:  # CALL
            # For CALL sellers: probability of staying below strike (OTM)
            prob_otm = norm.cdf(-d2)
            prob_itm = 1 - prob_otm

        # Calculate breakeven and expected value if premium provided
        breakeven_price = None
        expected_value = None

        if premium is not None:
            if option_type == "PUT":
                breakeven_price = strike - premium
            else:  # CALL
                breakeven_price = strike + premium

            # Expected value for seller = probability of keeping full premium
            expected_value = premium * prob_otm

        # Determine current status
        if option_type == "PUT":
            if current_price > strike:
                status = "OTM"
            elif current_price < strike:
                status = "ITM"
            else:
                status = "ATM"
        elif current_price < strike:
            status = "OTM"
        elif current_price > strike:
            status = "ITM"
        else:
            status = "ATM"

        # Distance to strike
        distance_pct = ((current_price - strike) / current_price) * 100

        result = {
            "ticker": ticker.upper(),
            "current_price": round(current_price, 2),
            "strike": strike,
            "option_type": option_type,
            "days_to_expiration": days_to_exp,
            "iv_percent": round(iv, 1),
            "probability_otm": round(prob_otm * 100, 1),
            "probability_itm": round(prob_itm * 100, 1),
            "distance_to_strike_pct": round(distance_pct, 1),
            "status": status
        }

        if breakeven_price is not None:
            result["breakeven_price"] = round(breakeven_price, 2)
        if expected_value is not None:
            result["expected_value"] = round(expected_value, 2)
        if premium is not None:
            result["premium"] = round(premium, 2)

        logger.info(f"Calculated POP for {ticker} {strike}{option_type}: {prob_otm*100:.1f}% OTM")
        return result

    def _fetch_current_price(self, ticker: str) -> float:
        """
        Fetch current market price using yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Current bid price or 0.0 if unavailable
        """
        # Check cache first
        if ticker in self._price_cache:
            cached_price: float = float(self._price_cache[ticker])
            return cached_price

        try:
            # Get quote with automatic provider fallback
            price = MarketDataFactory.get_quote_with_fallback(ticker)
            self._price_cache[ticker] = price
            logger.debug(f"Fetched price for {ticker}: ${price:.2f}")
            return price
        except Exception as e:
            logger.warning(f"Failed to fetch price for {ticker}: {e}")
            return 0.0

    def _estimate_iv(self, ticker: str) -> float:
        """
        Estimate implied volatility from historical volatility.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Estimated IV as percentage (e.g., 50.0 for 50%)
        """
        try:
            # Get historical data with automatic provider fallback
            hist = MarketDataFactory.get_historical_data_with_fallback(ticker, period="1mo", interval="1d")

            if hist.empty:
                logger.warning(f"No historical data for {ticker}, using default IV of 40%")
                return 40.0

            # Calculate daily returns
            returns = hist["Close"].pct_change().dropna()

            # Annualized volatility
            daily_vol = returns.std()
            annual_vol = daily_vol * math.sqrt(252)  # 252 trading days
            iv_percent = annual_vol * 100

            # Clamp to reasonable range
            iv_percent = max(10.0, min(200.0, iv_percent))

            logger.debug(f"Estimated IV for {ticker}: {iv_percent:.1f}%")
            iv_result: float = float(iv_percent)
            return iv_result

        except Exception as e:
            logger.warning(f"Failed to estimate IV for {ticker}: {e}")
            return 40.0  # Default fallback

    def format_pop_result(self, result: dict[str, Any]) -> str:
        """
        Format POP calculation result for display.

        Args:
            result: Dictionary from calculate_pop()

        Returns:
            Formatted string for Discord/CLI display
        """
        lines = []
        lines.append(f"📊 PROBABILITY OF PROFIT: {result['ticker']} ${result['strike']}{result['option_type']}")
        lines.append("")
        lines.append(f"Current Price: ${result['current_price']:.2f}")
        lines.append(f"Strike: ${result['strike']:.2f}")
        lines.append(f"Days to Expiration: {result['days_to_expiration']}")
        lines.append(f"Status: {result['status']} ({result['distance_to_strike_pct']:+.1f}%)")
        lines.append("")
        lines.append("**Probability Analysis:**")
        lines.append(f"• Probability OTM: {result['probability_otm']:.1f}% ✅")
        lines.append(f"• Probability ITM: {result['probability_itm']:.1f}%")

        if "premium" in result:
            lines.append("")
            lines.append(f"Premium: ${result['premium']:.2f} per contract")

            if "breakeven_price" in result:
                lines.append(f"Breakeven: ${result['breakeven_price']:.2f}")

            if "expected_value" in result:
                lines.append(f"Expected Value: ${result['expected_value']:.2f}")
                ev_pct = (result["expected_value"] / result["premium"]) * 100
                lines.append(f"Expected Return: {ev_pct:.1f}%")

        lines.append("")
        lines.append(f"*Assumes IV of {result['iv_percent']:.1f}% and risk-free rate of {self.RISK_FREE_RATE*100:.1f}%*")

        return "\n".join(lines)


def main():
    """Test the POP calculator."""
    calc = POPCalculator()

    # Test case: MSTX $12P
    result = calc.calculate_pop(
        ticker="MSTX",
        strike=12.0,
        expiration_date="2025-11-15",
        option_type="PUT",
        premium=0.45,
        iv=52.0
    )

    print(calc.format_pop_result(result))
    print("\n" + "="*60 + "\n")

    # Test case: CALL
    result2 = calc.calculate_pop(
        ticker="AAPL",
        strike=230.0,
        expiration_date="2025-11-15",
        option_type="CALL",
        premium=2.50
    )

    print(calc.format_pop_result(result2))


if __name__ == "__main__":
    main()
