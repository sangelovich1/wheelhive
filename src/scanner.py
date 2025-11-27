#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import argparse
import json
import logging
import os
from datetime import datetime, timedelta
from math import log, sqrt
from typing import Any

# Third-party imports
import pandas as pd
from scipy.stats import norm
from tabulate import tabulate

# Local application imports
import constants as const
from providers.market_data_factory import MarketDataFactory


# Get a logger instance
logger = logging.getLogger(__name__)


class Scanner:
    """
    Options chain scanner for identifying trading opportunities.

    Scans options chains from Finnhub API based on configurable filters including
    delta, implied volatility, open interest, volume, and strike proximity to current price.
    Scores options based on Greeks and returns top candidates sorted by score and profitability.

    Attributes:
        delta_min: Minimum delta threshold (default 0.01)
        delta_max: Maximum delta threshold (default 1.0)
        max_expiration_days: Maximum days to expiration filter (default 31)
        iv_min: Minimum implied volatility threshold in % (default 15)
        open_interest_min: Minimum open interest for liquidity (default 10)
        volume_min: Minimum volume for activity (default 0 = any volume)
        strike_proximity: Maximum percentage difference from current price (default 0.15 = 15%)
        top_candidates: Number of top candidates to return (default 20)
        max_cache_age: Cache age in minutes (default 3)
    """

    # Class constants (immutable configuration)
    DATA_DIR = const.OPTIONS_DATA_DIR
    CONTRACT_MULTIPLIER = 100  # Standard options contract multiplier

    def __init__(
        self,
        delta_min: float,
        delta_max: float,
        max_expiration_days: int,
        iv_min: float,
        open_interest_min: int,
        volume_min: int,
        strike_proximity: float,
        top_candidates: int,
        max_cache_age: int = 3
    ) -> None:
        """
        Initialize the Scanner instance.

        Args:
            delta_min: Minimum delta threshold (0-1)
            delta_max: Maximum delta threshold (0-1)
            max_expiration_days: Maximum days to expiration
            iv_min: Minimum implied volatility in %
            open_interest_min: Minimum open interest
            volume_min: Minimum volume (0 = any volume)
            strike_proximity: Maximum % difference from current price (0.30 = 30%)
            top_candidates: Number of top results to return
            max_cache_age: Internal cache age in minutes (default 3, reduces Finnhub API throttling)
        """
        logger.info("Initializing Scanner")

        # Instance variables for configurable parameters
        self.delta_min = delta_min
        self.delta_max = delta_max
        self.max_expiration_days = max_expiration_days
        self.iv_min = iv_min
        self.open_interest_min = open_interest_min
        self.volume_min = volume_min
        self.strike_proximity = strike_proximity
        self.top_candidates = top_candidates
        self.max_cache_age = max_cache_age


    def save_data(self, symbol: str, data: dict[str, Any]) -> None:
        """
        Save options chain data to a JSON file for caching.

        Args:
            symbol: Stock ticker symbol (e.g., 'SPY', 'AAPL')
            data: Options chain data dictionary to save
        """
        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)

        file_path = os.path.join(self.DATA_DIR, f"{symbol}_options.json")
        with open(file_path, "w") as json_file:
            json.dump(data, json_file)

        logger.info(f"Data saved to {file_path}")

    def is_file_outdated(self, symbol: str) -> bool:
        """
        Check if cached options data file is outdated or missing.

        Args:
            symbol: Stock ticker symbol (e.g., 'SPY', 'AAPL')

        Returns:
            True if file is outdated or doesn't exist, False if file is current
        """
        file_path = os.path.join(self.DATA_DIR, f"{symbol}_options.json")
        if os.path.exists(file_path):
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            if datetime.now() - file_mod_time < timedelta(minutes=self.max_cache_age):
                return False  # File is not outdated
        return True  # File does not exist or is outdated

    @staticmethod
    def estimate_delta_black_scholes(
        stock_price: float,
        strike: float,
        time_to_expiration_days: int,
        implied_volatility: float,
        option_type: str,
        risk_free_rate: float = 0.045
    ) -> float:
        """
        Estimate delta using Black-Scholes model when provider data is missing.

        Args:
            stock_price: Current price of the underlying stock
            strike: Option strike price
            time_to_expiration_days: Days until option expiration
            implied_volatility: Implied volatility in percentage (e.g., 50 for 50%)
            option_type: 'CALL' or 'PUT'
            risk_free_rate: Annual risk-free rate (default 4.5%)

        Returns:
            Estimated delta value
        """
        try:
            # Convert inputs to proper format
            # Use minimum of 1 day for reasonable delta estimates on near-expiration options
            # This prevents very small T values that cause extreme delta estimates
            T = max(time_to_expiration_days / 365.0, 1.0 / 365.0)
            sigma = implied_volatility / 100.0  # IV as decimal

            # Avoid invalid calculations
            if sigma <= 0 or stock_price <= 0 or strike <= 0:
                return 0.0

            # Black-Scholes d1 calculation
            d1 = (log(stock_price / strike) + (risk_free_rate + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))

            # Delta calculation
            if option_type.upper() == "CALL":
                delta = norm.cdf(d1)
            else:  # PUT
                delta = norm.cdf(d1) - 1.0

            delta_result: float = float(delta)
            return delta_result

        except Exception as e:
            logger.warning(f"Failed to estimate delta: {e}")
            return 0.0

    def calculate_score(self, delta: float, theta: float, gamma: float, open_interest: float, implied_volatility: float) -> float:
        """
        Calculate a composite score for an option based on Greeks and market data.

        Args:
            delta: Option delta (0-1)
            theta: Option theta (time decay)
            gamma: Option gamma (delta sensitivity)
            open_interest: Number of open contracts
            implied_volatility: Implied volatility percentage

        Returns:
            Composite score from 0-100, higher is better
        """
        # Score calculations based on delta, theta, gamma, open interest, and implied volatility
        score_delta = max(0, min((delta - 0.4) / 0.3 * 100, 100) if delta <= 0.7 else 100)
        score_theta = max(0, min(theta * 100, 100))  # Assume theta is a positive value
        score_gamma = max(0, min((gamma - 0.1) / 0.2 * 100, 100) if gamma <= 0.3 else 100)
        score_oi = max(0, min((open_interest - 100) / 900 * 100, 100))
        score_iv = max(0, min((implied_volatility - 20) / 80 * 100, 100))

        # Final score calculation as an average of the individual scores
        final_score = (score_delta + score_theta + score_gamma + score_oi + score_iv) / 5
        return final_score


    def analyze(self, chain: str, symbol: str, options_data: dict[str, Any] | None, market_price: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Analyze options chain and filter options based on configured criteria.

        Args:
            chain: Option type - 'CALL' or 'PUT'
            symbol: Stock ticker symbol (e.g., 'SPY', 'AAPL')
            options_data: Options chain data dictionary from API
            market_price: Current market price of the underlying

        Returns:
            Tuple of (filtered options list, diagnostics dict)
            diagnostics contains:
                - total_scanned: Total options examined
                - filter_stats: Count of failures per filter
                - near_misses: Options that failed only 1 filter
        """
        diagnostics: dict[str, Any] = {
            "total_scanned": 0,
            "passed_filters": 0,
            "filter_stats": {
                "delta": 0,
                "iv": 0,
                "open_interest": 0,
                "volume": 0,
                "proximity": 0,
                "expiration": 0
            },
            "near_misses": [],
            "missing_greeks": False,  # Track if this symbol had missing Greeks
            "estimated_deltas": 0  # Count of estimated deltas
        }

        if not options_data or "data" not in options_data:
            return [], diagnostics

        options = []
        for option in options_data["data"]:
            expiration_date = option["expirationDate"]
            expiration = datetime.strptime(expiration_date, "%Y-%m-%d")

            # Filter for options expiring within the specified number of days
            days_until_exp = (expiration - datetime.now()).days
            if days_until_exp > self.max_expiration_days:
                continue

            for cp in option["options"][chain]:
                diagnostics["total_scanned"] += 1

                strike = cp["strike"]
                bid = cp["bid"]
                ask = cp["ask"]
                delta = cp["delta"]
                iv = cp["impliedVolatility"]  # Already in percentage format from API
                open_interest = cp["openInterest"] if cp["openInterest"] is not None else 0
                volume = cp["volume"] if cp["volume"] is not None else 0
                theta = cp["theta"]  # Assume theta is provided in the data
                gamma = cp["gamma"]  # Assume gamma is provided in the data
                contract_name = cp["contractName"]  # Get the contract name

                # Estimate delta if provider returned 0.0 (missing Greeks)
                delta_estimated = False
                if abs(delta) < 0.001:  # Delta is essentially 0
                    diagnostics["missing_greeks"] = True
                    # Estimate delta using Black-Scholes
                    estimated_delta = self.estimate_delta_black_scholes(
                        stock_price=market_price,
                        strike=strike,
                        time_to_expiration_days=days_until_exp,
                        implied_volatility=iv,
                        option_type=chain
                    )
                    if abs(estimated_delta) > 0.001:  # Valid estimation
                        delta = estimated_delta
                        delta_estimated = True
                        diagnostics["estimated_deltas"] += 1
                        logger.debug(f"{symbol} {strike}{chain[0]} estimated delta: {estimated_delta:.4f}")
                    else:
                        logger.debug(f"{symbol} {strike}{chain[0]} could not estimate delta (estimated={estimated_delta:.4f}, days={days_until_exp}, iv={iv})")

                # Calculate the percentage difference between strike price and market price
                price_diff_percentage = abs(strike - market_price) / market_price

                # Check each filter individually for diagnostics
                passes_delta = self.delta_min <= abs(delta) <= self.delta_max
                passes_iv = iv >= self.iv_min
                passes_oi = open_interest >= self.open_interest_min
                passes_vol = volume >= self.volume_min
                passes_proximity = price_diff_percentage <= self.strike_proximity

                # Track filter failures
                failed_filters = []
                if not passes_delta:
                    diagnostics["filter_stats"]["delta"] += 1
                    failed_filters.append("delta")
                if not passes_iv:
                    diagnostics["filter_stats"]["iv"] += 1
                    failed_filters.append("iv")
                if not passes_oi:
                    diagnostics["filter_stats"]["open_interest"] += 1
                    failed_filters.append("open_interest")
                if not passes_vol:
                    diagnostics["filter_stats"]["volume"] += 1
                    failed_filters.append("volume")
                if not passes_proximity:
                    diagnostics["filter_stats"]["proximity"] += 1
                    failed_filters.append("proximity")

                # Apply filters based on delta, implied volatility, volume, open interest, and strike proximity
                if passes_delta and passes_iv and passes_oi and passes_vol and passes_proximity:
                    diagnostics["passed_filters"] += 1

                    # Calculate median price
                    median_price = (bid + ask) / 2
                    # Calculate profit if exercised
                    profit_if_exercised = (median_price * self.CONTRACT_MULTIPLIER) + (strike * self.CONTRACT_MULTIPLIER - market_price * self.CONTRACT_MULTIPLIER)
                    # Calculate profit if not exercised (premium only)
                    profit_if_not_exercised = median_price * self.CONTRACT_MULTIPLIER

                    # Calculate moneyness (percentage difference between strike and current price)
                    moneyness = ((strike - market_price) / market_price) * 100

                    # Calculate days to expiration for annualized return
                    days_to_expiration = (expiration - datetime.now()).days
                    if days_to_expiration <= 0:
                        days_to_expiration = 1  # Prevent division by zero

                    # Calculate annualized return
                    percent_return = 100 * profit_if_not_exercised / (market_price * self.CONTRACT_MULTIPLIER)
                    annualized_return = (percent_return / days_to_expiration) * 365

                    # Calculate score based on Greeks
                    score = self.calculate_score(delta, theta, gamma, open_interest, iv)

                    options.append({
                        "symbol": symbol,
                        "contract_name": contract_name,  # Store the contract name
                        "expiration": expiration,
                        "market_price": market_price,
                        "strike": strike,
                        "bid": bid,
                        "ask": ask,
                        "median_price": median_price,
                        "capital": market_price * self.CONTRACT_MULTIPLIER,
                        "percent_return": percent_return,
                        "annualized_return": annualized_return,
                        "moneyness": moneyness,
                        "days_to_expiration": days_to_expiration,
                        "profit_if_exercised": profit_if_exercised,
                        "profit_if_not_exercised": profit_if_not_exercised,
                        "delta": delta,
                        "delta_estimated": delta_estimated,  # Flag if delta was estimated
                        "iv": iv,
                        "open_interest": open_interest,
                        "volume": volume,
                        "theta": theta,
                        "gamma": gamma,
                        "score": score
                    })

                # Track near misses (failed only 1 filter) and have decent liquidity
                elif len(failed_filters) == 1 and open_interest >= self.open_interest_min // 2 and bid > 0:
                    diagnostics["near_misses"].append({
                        "contract": f"${strike}{chain[0]}",
                        "expiration": expiration_date,
                        "dte": days_until_exp,
                        "delta": abs(delta),
                        "iv": iv,
                        "oi": open_interest,
                        "volume": volume,
                        "proximity_pct": price_diff_percentage * 100,
                        "bid": bid,
                        "failed_filter": failed_filters[0]
                    })

        # Keep only top 5 near misses sorted by best score potential
        diagnostics["near_misses"] = sorted(
            diagnostics["near_misses"],
            key=lambda x: (x["oi"], x["bid"]),
            reverse=True
        )[:5]

        return options, diagnostics

    def sort_calls(self, calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Sort options by score and profitability, limiting to top candidates.

        Args:
            calls: List of option dictionaries to sort

        Returns:
            Sorted list of top option candidates
        """
        # Sort calls by score and then by maximum profit if exercised
        sorted_calls = sorted(calls, key=lambda x: (x["score"], x["profit_if_exercised"]), reverse=True)[:self.top_candidates]
        return sorted_calls

    def as_df(self, analyzed_calls: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Convert analyzed options to a raw pandas DataFrame with lowercase columns.

        This is the raw data format suitable for programmatic access, MCP/JSON serialization,
        and further processing. For display-formatted output, use styled_df() instead.

        Args:
            analyzed_calls: List of analyzed option dictionaries

        Returns:
            DataFrame with lowercase column names and raw numeric values
        """
        # Create DataFrame with lowercase columns only (raw data)
        df = pd.DataFrame([{
            "symbol": call["symbol"],
            "market_price": call["market_price"],
            "strike": call["strike"],
            "moneyness": round(call["moneyness"], 1),
            "expiration": call["expiration"].strftime("%Y-%m-%d"),
            "bid": round(call["bid"], 2),
            "ask": round(call["ask"], 2),
            "volume": call["volume"],
            "open_interest": call["open_interest"],
            "delta": round(call["delta"], 2),
            "iv": round(call["iv"], 0),
            "theta": round(call["theta"], 2),
            "gamma": round(call["gamma"], 2),
            "return_pct": round(call["percent_return"], 1),
            "annual_pct": round(call["annualized_return"], 0),
            "score": round(call["score"], 1),
            "delta_estimated": call.get("delta_estimated", False)
        } for call in analyzed_calls])

        return df

    def styled_df(self, analyzed_calls: list[dict[str, Any]]) -> pd.DataFrame:
        """
        Convert analyzed options to a display-formatted DataFrame with Title Case columns.

        This format is optimized for human-readable output (tables, reports, CLI display).
        For programmatic access or JSON serialization, use as_df() instead.

        Args:
            analyzed_calls: List of analyzed option dictionaries

        Returns:
            DataFrame with Title Case column names and display-formatted values
        """
        # Create DataFrame with Title Case columns (display format)
        df = pd.DataFrame([{
            "Symbol": call["symbol"],
            "Price": call["market_price"],
            "Strike": call["strike"],
            "Moneyness": round(call["moneyness"], 1),
            "Exp Date": call["expiration"].strftime("%m/%d"),
            "Bid": round(call["bid"], 2),
            "Ask": round(call["ask"], 2),
            "Vol": call["volume"],
            "Open Int": call["open_interest"],
            "Delta": round(call["delta"], 2),
            "IV": round(call["iv"], 0),
            "Theta": round(call["theta"], 2),
            "Gamma": round(call["gamma"], 2),
            "Return %": round(call["percent_return"], 1),
            "Comment": "Δ Est." if call.get("delta_estimated", False) else "",
        } for call in analyzed_calls])

        return df

    def as_dict(self, analyzed_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Convert analyzed options to a list of dictionaries for JSON serialization.

        This is the preferred format for MCP tools and LLM consumption, providing
        clean structured data without DataFrame overhead or display formatting.

        Args:
            analyzed_calls: List of analyzed option dictionaries

        Returns:
            List of dictionaries with lowercase keys and clean values
        """
        return [{
            "symbol": call["symbol"],
            "market_price": call["market_price"],
            "strike": call["strike"],
            "moneyness": round(call["moneyness"], 1),
            "expiration": call["expiration"].strftime("%Y-%m-%d"),
            "bid": round(call["bid"], 2),
            "ask": round(call["ask"], 2),
            "volume": call["volume"],
            "open_interest": call["open_interest"],
            "delta": round(call["delta"], 2),
            "iv": round(call["iv"], 0),
            "theta": round(call["theta"], 2),
            "gamma": round(call["gamma"], 2),
            "return_pct": round(call["percent_return"], 1),
            "annual_pct": round(call["annualized_return"], 0),
            "score": round(call["score"], 1),
            "delta_estimated": call.get("delta_estimated", False)
        } for call in analyzed_calls]

    def compute(self, chain: str, symbol: str) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
        """
        Perform complete analysis for a symbol's options chain.

        Fetches or loads cached options data, gets current price, and analyzes
        the options chain to find trading candidates.

        Args:
            chain: Option type - 'CALL' or 'PUT'
            symbol: Stock ticker symbol (e.g., 'SPY', 'AAPL')

        Returns:
            Tuple of (analyzed options list, diagnostics dict)
        """
        empty_diagnostics = {
            "total_scanned": 0,
            "passed_filters": 0,
            "filter_stats": {},
            "near_misses": []
        }

        options_data = None

        if self.is_file_outdated(symbol):
            logger.info(f"Fetching new data for {symbol}...")
            try:
                # Use factory with automatic fallback (Finnhub → YFinance → AlphaVantage)
                options_data = MarketDataFactory.get_options_chain_with_fallback(symbol)
                if options_data:
                    self.save_data(symbol, options_data)
            except Exception as e:
                logger.error(f"Failed to fetch options chain for {symbol}: {e}")
                options_data = None
        else:
            logger.info(f"Using cached data for {symbol}.")
            file_path = os.path.join(self.DATA_DIR, f"{symbol}_options.json")
            with open(file_path) as json_file:
                options_data = json.load(json_file)

        try:
            # Use factory with automatic fallback for current price
            market_price = MarketDataFactory.get_quote_with_fallback(symbol)
        except Exception as e:
            logger.warning(f"Failed to fetch current price for {symbol}: {e}")
            market_price = None

        if market_price is None:
            logger.warning(f"Could not retrieve current market price for {symbol}. Skipping ticker.")
            return None, empty_diagnostics

        logger.info(f"Current market price of {symbol}: ${market_price:.2f}")

        analyzed_calls, diagnostics = self.analyze(chain, symbol, options_data, market_price)

        return analyzed_calls, diagnostics

    def as_table(self, data: pd.DataFrame) -> str:
        """
        Convert DataFrame to formatted table string for display.

        Args:
            data: DataFrame containing options data

        Returns:
            Formatted table string with currency formatting
        """
        # Convert DataFrame to a formatted table string
        # Format currency columns with dollar signs
        df_formatted = data.copy()
        currency_cols = ["Price", "Strike", "Bid", "Ask"]
        for col in currency_cols:
            if col in df_formatted.columns:
                df_formatted[col] = df_formatted[col].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "-")

        table_str = tabulate(df_formatted, showindex=False, headers="keys", stralign="right", floatfmt=".2f")
        return table_str


    def scan(self, chain: str, items: list[str], include_params: bool = False) -> tuple[pd.DataFrame | None, str, dict[str, Any] | None]:
        """
        Scan options for given symbols and return results.

        Args:
            chain: Option chain type ("PUT" or "CALL")
            items: List of stock symbols to scan
            include_params: If True, returns scanner parameters as third tuple element

        Returns:
            tuple: (DataFrame with results, table string, params/diagnostics dict)
                   params dict includes diagnostics with filter statistics and near misses
                   Returns (None, error_message, diagnostics) if no data found
        """
        call_results = list()
        all_diagnostics = []

        for symbol in items:
            # Ensure all symbols are uppercase
            symbol = symbol.upper()
            logger.info(f"symbol: {symbol}")
            # Display results in a table
            analyzed_calls, diagnostics = self.compute(chain, symbol)
            if analyzed_calls:
                call_results.extend(analyzed_calls)
            diagnostics["symbol"] = symbol
            all_diagnostics.append(diagnostics)

        if call_results:
            call_results = self.sort_calls(call_results)
            df_call = self.as_df(call_results)  # Raw data for programmatic access
            df_styled = self.styled_df(call_results)  # Formatted for display
            logger.info(f"{chain} scan results: {len(call_results)} options from {len(items)} symbols")
            table_str = self.as_table(df_styled)

            params = {
                "delta_min": self.delta_min,
                "delta_max": self.delta_max,
                "max_days": self.max_expiration_days,
                "diagnostics": all_diagnostics
            }

            # Always return 3-tuple to match type signature
            if include_params:
                return (df_call, table_str, params)
            return (df_call, table_str, None)
        logger.info(f"No {chain} options found for {len(items)} symbols scanned.")
        # Build helpful diagnostic message
        diagnostic_msg = self._format_diagnostic_message(all_diagnostics)

        # Always return 3-tuple to match type signature
        if include_params:
            return (None, diagnostic_msg, {"diagnostics": all_diagnostics})
        return (None, diagnostic_msg, None)

    def _format_diagnostic_message(self, all_diagnostics: list[dict[str, Any]]) -> str:
        """
        Format diagnostic information into a helpful message when no results found.

        Args:
            all_diagnostics: List of diagnostic dicts from each symbol scan

        Returns:
            Formatted diagnostic message string
        """
        if not all_diagnostics:
            return "No options data found."

        msg_parts = []
        for diag in all_diagnostics:
            symbol = diag.get("symbol", "Unknown")
            scanned = diag.get("total_scanned", 0)
            passed = diag.get("passed_filters", 0)
            filter_stats = diag.get("filter_stats", {})
            near_misses = diag.get("near_misses", [])

            if scanned == 0:
                msg_parts.append(f"{symbol}: No options data available")
                continue

            msg_parts.append(f"\n{symbol}: Scanned {scanned} contracts, {passed} passed all filters")

            # Check if Greeks were missing and estimated
            missing_greeks = diag.get("missing_greeks", False)
            estimated_deltas = diag.get("estimated_deltas", 0)
            if missing_greeks:
                if estimated_deltas > 0:
                    msg_parts.append(f"  ⚠️  Provider had missing Greeks - estimated delta for {estimated_deltas} options using Black-Scholes")
                else:
                    msg_parts.append("  ⚠️  Provider had missing Greeks (delta=0.0) - could not estimate delta")

            # Show which filters eliminated the most
            if filter_stats:
                sorted_filters = sorted(filter_stats.items(), key=lambda x: x[1], reverse=True)
                top_blockers = sorted_filters[:3]
                if top_blockers and top_blockers[0][1] > 0:
                    filter_names = {"delta": "Delta range", "iv": "IV minimum", "open_interest": "Open interest",
                                  "volume": "Volume", "proximity": "Strike proximity"}
                    blocker_strs = [f"{filter_names.get(f, f)}: {count}" for f, count in top_blockers if count > 0]
                    if blocker_strs:
                        msg_parts.append(f"  Top filter rejections: {', '.join(blocker_strs)}")

            # Show near misses
            if near_misses:
                msg_parts.append("  Near misses (failed 1 filter):")
                for nm in near_misses[:3]:  # Show top 3
                    failed_filter = nm["failed_filter"]
                    msg_parts.append(f"    {nm['contract']} {nm['expiration']} ({nm['dte']}DTE): "
                                   f"Δ={nm['delta']:.3f}, IV={nm['iv']:.0f}%, OI={nm['oi']}, "
                                   f"bid=${nm['bid']:.2f} - Failed: {failed_filter}")

        return "\n".join(msg_parts) if msg_parts else "No options data found."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", type=str, required=True)
    parser.add_argument("--symbols", nargs="+", default="SPY")
    parser.add_argument("--delta_min", default=.05, type=float)
    parser.add_argument("--delta_max", default=.35, type=float)
    parser.add_argument("--max_days", default=31, type=int)

    args = parser.parse_args()
    logger.info(f"Chain: {args.chain}")
    tracker = Scanner(
        delta_min=args.delta_min,
        delta_max=args.delta_max,
        max_expiration_days=args.max_days,
        iv_min=0.0,
        open_interest_min=0,
        volume_min=0,
        strike_proximity=1.0,
        top_candidates=10
    )
    logger.info(f"delta_min: {tracker.delta_min}, delta_max: {tracker.delta_max}, max_expiration_days: {tracker.max_expiration_days}")

    df_result, table_str, _ = tracker.scan(args.chain.upper(), args.symbols)
    print(table_str)

