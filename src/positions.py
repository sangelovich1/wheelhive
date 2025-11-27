"""
Positions Module - Calculate current stock holdings and open option positions

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from datetime import datetime

# Third-party imports
import pandas as pd
from tabulate import tabulate

# Local application imports
import constants as const
from db import Db
from providers.market_data_factory import MarketDataFactory
from shares import Shares
from trades import Trades


# Get a logger instance
logger = logging.getLogger(__name__)


class Positions:
    """
    Calculate and display current positions (stock holdings and open options)
    Uses DataFrames to aggregate data from shares and trades tables
    """

    def __init__(self, db: Db, shares: Shares, trades: Trades) -> None:
        """
        Initialize Positions with database and table processors

        Args:
            db: Database instance
            shares: Shares table processor
            trades: Trades table processor
        """
        self.db = db
        self.shares = shares
        self.trades = trades
        self._price_cache: dict[str, float] = {}  # Cache for yfinance price lookups

    def _fetch_current_price(self, symbol: str) -> float:
        """
        Fetch current market price using market data factory with automatic fallback.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Current price or 0.0 if unavailable
        """
        # Check cache first
        if symbol in self._price_cache:
            cached_price: float = float(self._price_cache[symbol])
            return cached_price

        try:
            # Get quote with automatic provider fallback
            price = MarketDataFactory.get_quote_with_fallback(symbol)
            self._price_cache[symbol] = price
            logger.debug(f"Fetched price for {symbol}: ${price:.2f}")
            return price
        except Exception as e:
            logger.warning(f"Failed to fetch price for {symbol}: {e}")
            self._price_cache[symbol] = 0.0
            return 0.0

    def _calculate_dte(self, expiration_date: str) -> int:
        """
        Calculate days to expiration

        Args:
            expiration_date: Date string in YYYY-MM-DD format

        Returns:
            Number of days until expiration
        """
        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
            dte = (exp_date - datetime.now()).days
            return max(0, dte)  # Don't return negative DTE
        except Exception as e:
            logger.warning(f"Failed to calculate DTE for {expiration_date}: {e}")
            return 0

    def _get_company_name(self, symbol: str) -> str:
        """
        Get company name from ticker database.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Company name or symbol if not found
        """
        try:
            query = "SELECT company_name FROM valid_tickers WHERE ticker = ?"
            cursor = self.db.connection.execute(query, (symbol,))
            result = cursor.fetchone()
            if result and result[0]:
                company_name: str = str(result[0])
                return company_name
            logger.debug(f"Company name not found for {symbol}, using symbol")
            return symbol
        except Exception as e:
            logger.warning(f"Failed to fetch company name for {symbol}: {e}")
            return symbol

    def as_df(self, username: str, account: str | None = None, symbol: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get current positions as DataFrames (stock and options separately)

        Args:
            username: Username to query positions for
            account: Must be None (account filtering not supported)
            symbol: Optional symbol filter

        Returns:
            Tuple of (stock_df, options_df) - both as pandas DataFrames
        """
        stock_positions = self.get_stock_positions(username, account, symbol)
        option_positions = self.get_open_options(username, account, symbol)

        # Convert to DataFrames
        stock_df = pd.DataFrame(stock_positions) if stock_positions else pd.DataFrame()
        options_df = pd.DataFrame(option_positions) if option_positions else pd.DataFrame()

        return stock_df, options_df

    def get_stock_positions(self, username: str, account: str | None = None, symbol: str | None = None) -> list[dict]:
        """
        Calculate current stock holdings with live market values using DataFrames

        Args:
            username: Username to query positions for
            account: Optional account name to filter by. None = aggregate across all accounts.
            symbol: Optional symbol filter

        Returns:
            List of position dictionaries sorted by market value descending

        Account Filtering Logic:
        -----------------------
        The database uses negative quantities to represent shares leaving an account
        (transfers out) and positive quantities for shares entering (transfers in).

        Example data:
            AAPL|HODL: -5 shares (transferred out)
            AAPL|Joint: +5 shares (transferred in)
            Total: -5 + 5 = 0 shares

        When account=None (aggregate mode):
            - Groups by Symbol only
            - Negative and positive quantities across accounts net to correct totals
            - No negative positions exist in aggregate (verified)

        When account specified:
            - Groups by (Symbol, Account) to calculate per-account positions
            - Filters to requested account
            - Filters out negative positions (transfer-out records)
            - Adds 'account' field to output
            - Shows only actual holdings in that account

        This approach correctly handles inter-account transfers without requiring
        explicit Transfer In/Out transaction types.
        """
        # Get shares data as DataFrame
        df = self.shares.as_df(username, filter=None)

        if df.empty:
            logger.info(f"No share data found for {username}")
            return []

        # Apply symbol filter if specified
        if symbol:
            df = df[df["Symbol"] == symbol.upper()]

        if df.empty:
            logger.info(f"No shares after filtering for {username}")
            return []

        # Database stores correct signs:
        # - Buy: positive quantity, negative amount (cash outflow)
        # - Sell: negative quantity, positive amount (cash inflow)
        # - Transfer out: negative quantity (leaving this account)
        # - Transfer in: positive quantity (entering this account)

        if account is None:
            # Aggregate across all accounts
            grouped = df.groupby(["Symbol"]).agg({
                "Quantity": "sum",   # Net shares (buys positive, sells negative)
                "Amount": "sum"      # Net cash flow (buys negative, sells positive)
            }).reset_index()
            grouped.rename(columns={"Quantity": "net_quantity", "Amount": "net_amount"}, inplace=True)
            # Filter out zero positions (no negative positions exist in aggregate)
            grouped = grouped[grouped["net_quantity"] != 0]
        else:
            # Group by Symbol AND Account to calculate per-account positions
            grouped = df.groupby(["Symbol", "Account"]).agg({
                "Quantity": "sum",
                "Amount": "sum"
            }).reset_index()
            grouped.rename(columns={"Quantity": "net_quantity", "Amount": "net_amount"}, inplace=True)
            # Filter to requested account
            grouped = grouped[grouped["Account"] == account]
            # Filter out zero AND negative positions (negatives represent transfers out)
            grouped = grouped[grouped["net_quantity"] > 0]

        if grouped.empty:
            logger.info(f"No open stock positions for {username} (account={account})")
            return []

        positions = []
        for _, row in grouped.iterrows():
            sym = row["Symbol"]
            net_shares = row["net_quantity"]
            cost_basis = row["net_amount"]

            # Fetch current price
            current_price = self._fetch_current_price(sym)

            # Calculate values
            market_value = net_shares * current_price
            avg_cost = abs(cost_basis) / abs(net_shares) if net_shares != 0 else 0.0
            # P/L = market_value + net_amount (works for both long and short positions)
            # Long: market_value (+) + net_amount (-) = profit if market_value > abs(net_amount)
            # Short: market_value (-) + net_amount (+) = profit if abs(market_value) < net_amount
            unrealized_pl = market_value + cost_basis

            position = {
                "symbol": sym,
                "shares": int(net_shares),
                "avg_cost": avg_cost,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pl": unrealized_pl
            }

            # Add account field when filtering by specific account
            if account is not None:
                position["account"] = row["Account"]

            positions.append(position)

        # Sort by absolute market value descending
        positions.sort(key=lambda x: abs(x["market_value"]), reverse=True)

        logger.info(f"Found {len(positions)} stock positions for {username} (account={account})")
        return positions

    def get_open_options(self, username: str, account: str | None = None, symbol: str | None = None) -> list[dict]:
        """
        Calculate net open option positions with DTE using DataFrames

        Args:
            username: Username to query positions for
            account: Optional account name to filter by. None = aggregate across all accounts.
            symbol: Optional symbol filter

        Returns:
            List of position dictionaries sorted by market value descending

        Account Filtering Logic:
        -----------------------
        Same logic as get_stock_positions - see that method's docstring for details.
        Options can be transferred between accounts just like shares.
        """
        # Get trades data as DataFrame
        df = self.trades.as_df(username, filter=None)

        if df.empty:
            logger.info(f"No trade data found for {username}")
            return []

        # Apply symbol filter if specified
        if symbol:
            df = df[df["Symbol"] == symbol.upper()]

        if df.empty:
            logger.info(f"No trades after filtering for {username}")
            return []

        # Convert expiration date to datetime for filtering
        df["Expiration_Date"] = pd.to_datetime(df["Expiration_Date"], format="%m/%d/%Y")

        # Filter out expired options
        today = pd.Timestamp(datetime.now().date())
        df = df[df["Expiration_Date"] >= today]

        if df.empty:
            logger.info(f"No unexpired option positions for {username}")
            return []

        # Calculate net contracts and premium by unique position
        # STO/BTO = opening (positive contracts), BTC/STC = closing (negative contracts)
        df["net_contracts"] = df.apply(
            lambda row: row["contracts"] if row["Operation"] in ["STO", "BTO"] else -row["contracts"],
            axis=1
        )

        if account is None:
            # Aggregate across all accounts
            grouped = df.groupby(["Symbol", "Strike", "Expiration_Date", "Option_Type"]).agg({
                "net_contracts": "sum",
                "Total": "sum"
            }).reset_index()
            # Filter out closed positions (net contracts = 0)
            grouped = grouped[grouped["net_contracts"] != 0]
        else:
            # Group by account too for per-account positions
            grouped = df.groupby(["Symbol", "Strike", "Expiration_Date", "Option_Type", "Account"]).agg({
                "net_contracts": "sum",
                "Total": "sum"
            }).reset_index()
            # Filter to requested account
            grouped = grouped[grouped["Account"] == account]
            # Filter out closed AND negative positions
            grouped = grouped[grouped["net_contracts"] > 0]

        if grouped.empty:
            logger.info(f"No open option positions for {username} (account={account})")
            return []

        positions = []
        for _, row in grouped.iterrows():
            sym = row["Symbol"]
            strike = row["Strike"]
            exp_date = row["Expiration_Date"]
            opt_type = row["Option_Type"]
            net_contracts = row["net_contracts"]
            net_premium = row["Total"]

            # Calculate DTE
            dte = (exp_date.date() - datetime.now().date()).days

            # Format strike with option type
            strike_str = f"{strike}{opt_type}"

            # Format expiration date back to string
            exp_date_str = exp_date.strftime("%Y-%m-%d")

            # For now, we'll use net_premium as current value
            # TODO: Could fetch live option prices via yfinance for more accuracy
            current_value = net_premium
            unrealized_pl = 0.0  # Since we're using premium as value

            position = {
                "symbol": sym,
                "strike": strike_str,
                "expiration_date": exp_date_str,
                "option_type": opt_type,
                "net_contracts": int(net_contracts),
                "entry_premium": net_premium,
                "current_value": current_value,
                "dte": dte,
                "unrealized_pl": unrealized_pl
            }

            # Add account field when filtering by specific account
            if account is not None:
                position["account"] = row["Account"]

            positions.append(position)

        # Sort by absolute current value descending
        positions.sort(key=lambda x: abs(x["current_value"]), reverse=True)

        logger.info(f"Found {len(positions)} open option positions for {username} (account={account})")
        return positions

    def my_positions(self, username: str, index: int, account: str | None = None, symbol: str | None = None) -> tuple[str, int]:
        """
        Format current positions for Discord display with pagination

        Args:
            username: Username to query
            index: Page index (0-based)
            account: DEPRECATED - ignored (will raise error if not None). Account filtering not supported.
            symbol: Optional symbol filter

        Returns:
            Tuple of (formatted_table_string, page_count)
        """
        # Account filtering not supported - always use None (all accounts aggregated)
        # This will raise ValueError if account is not None
        stock_positions = self.get_stock_positions(username, account=None, symbol=symbol)
        option_positions = self.get_open_options(username, account=None, symbol=symbol)

        if len(stock_positions) == 0 and len(option_positions) == 0:
            return "No open positions found.", 0

        # Build output sections
        sections = []

        # Stock Holdings Section
        if stock_positions:
            stock_data = []
            for pos in stock_positions:
                stock_data.append([
                    pos["symbol"],
                    pos["shares"],
                    f"${pos['avg_cost']:.2f}",
                    f"${pos['current_price']:.2f}",
                    f"${pos['market_value']:,.0f}",
                    f"${pos['unrealized_pl']:,.0f}" if pos["unrealized_pl"] >= 0 else f"(${abs(pos['unrealized_pl']):,.0f})"
                ])

            stock_headers = ["Symbol", "Shares", "Avg Cost", "Current", "Mkt Value", "Unreal. P/L"]
            stock_table = tabulate(stock_data, headers=stock_headers, stralign="right", tablefmt="simple")
            sections.append(f"=== Stock Holdings ===\n{stock_table}")

        # Open Options Section
        if option_positions:
            option_data = []
            for pos in option_positions:
                # Format expiration date
                exp_str = datetime.strptime(pos["expiration_date"], "%Y-%m-%d").strftime("%m/%d")

                option_data.append([
                    pos["symbol"],
                    pos["strike"],
                    exp_str,
                    pos["net_contracts"],
                    f"${pos['entry_premium']:,.0f}",
                    pos["dte"],
                    f"${pos['unrealized_pl']:,.0f}" if pos["unrealized_pl"] >= 0 else f"(${abs(pos['unrealized_pl']):,.0f})"
                ])

            option_headers = ["Symbol", "Strike", "Exp", "Contracts", "Premium", "DTE", "Unreal. P/L"]
            option_table = tabulate(option_data, headers=option_headers, stralign="right", tablefmt="simple")
            sections.append(f"=== Open Options ===\n{option_table}")

        # Combine sections
        output = "\n\n".join(sections)

        # Calculate totals
        total_stock_value = sum(pos["market_value"] for pos in stock_positions)
        total_stock_pl = sum(pos["unrealized_pl"] for pos in stock_positions)
        total_option_premium = sum(pos["entry_premium"] for pos in option_positions)

        # Add summary
        summary = f"\n\nTotal Stock Value: ${total_stock_value:,.0f}"
        summary += f"\nTotal Stock P/L: ${total_stock_pl:,.0f}" if total_stock_pl >= 0 else f"\nTotal Stock P/L: (${abs(total_stock_pl):,.0f})"
        summary += f"\nTotal Option Premium: ${total_option_premium:,.0f}"

        output += summary

        # For now, single page only (pagination can be added later if needed)
        # Calculate if output fits in Discord's character limit
        if len(output) > const.DISCORD_MAX_CHAR_COUNT:
            logger.warning(f"Position output exceeds Discord limit: {len(output)} chars")
            # TODO: Implement pagination if needed

        return output, 1


def main():
    """Test the Positions class"""
    db = Db()
    shares = Shares(db)
    trades = Trades(db)
    positions = Positions(db, shares, trades)

    # Test with testuser
    username = "sangelovich"
    account = "Alaska"

    print("=== Stock Positions ===")
    stock_pos = positions.get_stock_positions(username, account=account)
    for pos in stock_pos:
        print(pos)

    print("\n=== Open Options ===")
    option_pos = positions.get_open_options(username, account=account)
    for pos in option_pos:
        print(pos)

    print("\n=== Formatted Output ===")
    output, pages = positions.my_positions(username, 0, account=account)
    print(output)


if __name__ == "__main__":
    main()
