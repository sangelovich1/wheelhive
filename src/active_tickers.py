"""
Active Tickers Extraction

Reusable module for extracting and analyzing actively traded tickers
from harvested messages. Used by digest generation, earnings calendar,
and other analytics components.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""
import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from db import Db


logger = logging.getLogger(__name__)


# Leveraged ETF mapping (ticker -> underlying ticker)
# Used to resolve earnings/dividends for leveraged funds
LEVERAGED_ETF_MAP = {
    # MicroStrategy leveraged
    "MSTX": "MSTR",  # 2x Long MicroStrategy
    "MSTY": "MSTR",  # Covered Call on MSTR

    # Coinbase leveraged
    "CONL": "COIN",  # 2x Long Coinbase
    "CONY": "COIN",  # Covered Call on COIN

    # Tesla leveraged
    "TSLL": "TSLA",  # 2x Long Tesla
    "TSLY": "TSLA",  # Covered Call on Tesla
    "TSLZ": "TSLA",  # -1x Short Tesla

    # NVIDIA leveraged
    "NVDL": "NVDA",  # 2x Long NVIDIA
    "NVDY": "NVDA",  # Covered Call on NVIDIA
    "NVDZ": "NVDA",  # -1x Short NVIDIA

    # Apple leveraged
    "AAPU": "AAPL",  # 2x Long Apple
    "APLY": "AAPL",  # Covered Call on Apple

    # Amazon leveraged
    "AMZU": "AMZN",  # 2x Long Amazon
    "AMZY": "AMZN",  # Covered Call on Amazon

    # Meta leveraged
    "METU": "META",  # 2x Long Meta
    "METY": "META",  # Covered Call on Meta

    # Google leveraged
    "GGLU": "GOOGL", # 2x Long Google
    "GGLY": "GOOGL", # Covered Call on Google

    # Microsoft leveraged
    "MSFU": "MSFT",  # 2x Long Microsoft
    "MSFY": "MSFT",  # Covered Call on Microsoft

    # Add more as needed
}


class TickerActivity:
    """
    Container for ticker activity data

    Attributes:
        ticker: Stock/ETF ticker symbol
        trade_count: Total number of trades
        usernames: Set of users who traded this ticker
        operations: Counter of operations (STO, BTC, etc.)
        expirations: List of expiration dates
        strikes: List of strike prices
        premiums: List of premium amounts
        examples: List of example trades
    """
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.trade_count = 0
        self.usernames: set[str] = set()
        self.operations: Counter[str] = Counter()
        self.expirations: list[str] = []
        self.strikes: list[float] = []
        self.premiums: list[float] = []
        self.examples: list[dict[str, Any]] = []

    def add_trade(self, trade: dict, username: str):
        """Add a trade to this ticker's activity"""
        self.trade_count += 1
        self.usernames.add(username)

        # Track operations (prefer direct operation field, fallback to deriving from action+position_effect for legacy data)
        operation = trade.get("operation")
        if not operation:
            # Legacy format: derive from action+position_effect
            action = trade.get("action", "")
            effect = trade.get("position_effect", "")
            if action and effect:
                operation = f"{action[0]}{effect[0]}O"  # STO, BTC, etc.
            else:
                operation = "UNKNOWN"

        self.operations[operation] += 1

        # Track trade details
        if trade.get("expiration"):
            self.expirations.append(trade["expiration"])
        if trade.get("strike"):
            self.strikes.append(trade["strike"])
        if trade.get("premium"):
            self.premiums.append(trade["premium"])

        # Store example trades (limit to 3)
        if len(self.examples) < 3:
            self.examples.append({
                "username": username,
                "operation": operation,
                "quantity": trade.get("quantity") or trade.get("contracts"),
                "strike": trade.get("strike"),
                "option_type": trade.get("option_type"),
                "premium": trade.get("premium"),
                "expiration": trade.get("expiration"),
                "source": trade.get("source", "unknown")
            })

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "ticker": self.ticker,
            "trade_count": self.trade_count,
            "trader_count": len(self.usernames),
            "usernames": list(self.usernames),
            "operations": dict(self.operations),
            "expirations": self.expirations,
            "strikes": self.strikes,
            "premiums": self.premiums,
            "examples": self.examples,
            "nearest_expiration": min(self.expirations) if self.expirations else None,
            "avg_premium": sum(self.premiums) / len(self.premiums) if self.premiums else None,
            "min_strike": min(self.strikes) if self.strikes else None,
            "max_strike": max(self.strikes) if self.strikes else None,
        }


def get_active_tickers(
    db: Db,
    days: int = 7,
    min_trades: int = 1,
    guild_id: int | None = None
) -> dict[str, TickerActivity]:
    """
    Extract actively traded tickers from harvested messages

    Args:
        db: Database connection
        days: Look back N days for trades
        min_trades: Minimum number of trades to include ticker
        guild_id: Optional guild filter (None = all guilds)

    Returns:
        Dict mapping ticker -> TickerActivity object
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor = db.connection.cursor()

    # Build query with optional guild filter
    query = """
        SELECT username, extracted_data
        FROM harvested_messages
        WHERE timestamp >= ?
        AND extracted_data IS NOT NULL
        AND extracted_data != '{}'
    """
    params: list[Any] = [cutoff_date]

    if guild_id:
        query += " AND guild_id = ?"
        params.append(guild_id)

    cursor.execute(query, params)

    ticker_data = {}

    for row in cursor.fetchall():
        username = row[0]

        # Parse JSON data
        try:
            data = json.loads(row[1]) if row[1] else {}
        except json.JSONDecodeError:
            continue

        if not data or "trades" not in data:
            continue

        trades = data.get("trades", [])

        for trade in trades:
            # Support both new Pydantic and old format
            ticker = trade.get("ticker") or trade.get("symbol")
            if not ticker:
                continue

            if ticker not in ticker_data:
                ticker_data[ticker] = TickerActivity(ticker)

            ticker_data[ticker].add_trade(trade, username)

    # Filter by minimum trade count
    ticker_data = {
        ticker: activity
        for ticker, activity in ticker_data.items()
        if activity.trade_count >= min_trades
    }

    logger.info(f"Extracted {len(ticker_data)} active tickers from last {days} days")
    return ticker_data


def sort_tickers_by_activity(
    ticker_data: dict[str, TickerActivity],
    sort_by: str = "trade_count",
    reverse: bool = True,
    limit: int | None = None
) -> list[tuple[str, TickerActivity]]:
    """
    Sort tickers by activity metric

    Args:
        ticker_data: Dict of ticker -> TickerActivity
        sort_by: Sort key ('trade_count', 'trader_count', 'avg_premium')
        reverse: Sort descending if True
        limit: Optional limit on results

    Returns:
        List of (ticker, TickerActivity) tuples, sorted
    """
    if sort_by == "trade_count":
        key_func = lambda x: x[1].trade_count
    elif sort_by == "trader_count":
        key_func = lambda x: len(x[1].usernames)
    elif sort_by == "avg_premium":
        key_func = lambda x: (sum(x[1].premiums) / len(x[1].premiums)) if x[1].premiums else 0
    else:
        raise ValueError(f"Unknown sort_by value: {sort_by}")

    sorted_tickers = sorted(ticker_data.items(), key=key_func, reverse=reverse)

    if limit:
        sorted_tickers = sorted_tickers[:limit]

    return sorted_tickers


def resolve_underlying_ticker(ticker: str) -> tuple[str, bool]:
    """
    Resolve leveraged ETF to underlying ticker

    Args:
        ticker: Ticker symbol (e.g., "MSTX", "TSLA")

    Returns:
        Tuple of (resolved_ticker, is_leveraged)

    Examples:
        >>> resolve_underlying_ticker("MSTX")
        ("MSTR", True)
        >>> resolve_underlying_ticker("TSLA")
        ("TSLA", False)
    """
    if ticker in LEVERAGED_ETF_MAP:
        return LEVERAGED_ETF_MAP[ticker], True
    return ticker, False


def format_ticker_summary(activity: TickerActivity, show_examples: bool = True) -> str:
    """
    Format ticker activity as human-readable summary

    Args:
        activity: TickerActivity object
        show_examples: Include example trades

    Returns:
        Formatted string
    """
    lines = []

    # Header
    lines.append(f"{activity.ticker}: {activity.trade_count} trades by {len(activity.usernames)} trader(s)")

    # Operations breakdown
    ops_str = ", ".join([f"{op}({count})" for op, count in activity.operations.most_common(3)])
    lines.append(f"  Operations: {ops_str}")

    # Stats
    if activity.expirations:
        nearest_exp = min(activity.expirations)
        lines.append(f"  Nearest expiration: {nearest_exp}")

    if activity.premiums:
        avg_premium = sum(activity.premiums) / len(activity.premiums)
        lines.append(f"  Avg premium: ${avg_premium:.2f}")

    # Examples
    if show_examples and activity.examples:
        lines.append("  Example trades:")
        for example in activity.examples[:2]:
            if example.get("strike") and example.get("option_type"):
                lines.append(
                    f"    - {example['operation']} {example['quantity']}x "
                    f"${example['strike']}{example['option_type'][0]} @ ${example['premium']}"
                )

    return "\n".join(lines)
