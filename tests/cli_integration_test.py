"""
Integration tests for CLI commands.

These tests exercise the CLI business logic by testing the underlying data operations
that CLI commands perform. Uses TestDataFactory for clean, maintainable test data setup.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import pytest
import sys
import os

# Add src and tests to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from db import Db
from trades import Trades
from dividends import Dividends
from shares import Shares
from deposits import Deposits
from test_data_factory import TestDataFactory


class TestCLITransactionQueries:
    """Test the query operations that CLI list commands use"""

    def setup_method(self):
        """Set up test database with sample data"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create sample transactions
        self.factory.create_trade(symbol="AAPL", operation="STO", date="2025-01-15")
        self.factory.create_dividend(symbol="SPY", amount=25.50, date="2025-01-10")
        self.factory.create_share(symbol="TSLA", action="BUY", date="2025-01-05")
        self.factory.create_deposit(amount=10000.00, date="2025-01-01")

    def test_list_trades_query(self):
        """Test that trades.query() returns data (used by CLI list command)"""
        result = self.factory.trades.query(self.factory.username)
        assert len(result) == 1
        assert result[0][8] == "AAPL"  # symbol column

    def test_list_trades_with_symbol_filter(self):
        """Test trades.query() with symbol filter"""
        result = self.factory.trades.query(self.factory.username, condition='symbol="AAPL"')
        assert len(result) == 1

        result = self.factory.trades.query(self.factory.username, condition='symbol="TSLA"')
        assert len(result) == 0

    def test_trades_as_dataframe(self):
        """Test trades.as_df() (used by CLI for formatted output)"""
        df = self.factory.trades.as_df(self.factory.username)
        assert len(df) == 1
        assert df.iloc[0]['Symbol'] == 'AAPL'

    def test_list_dividends_query(self):
        """Test that dividends.query() returns data"""
        result = self.factory.dividends.query(self.factory.username)
        assert len(result) == 1

    def test_dividends_as_dataframe(self):
        """Test dividends.as_df()"""
        df = self.factory.dividends.as_df(self.factory.username)
        assert len(df) == 1
        assert df.iloc[0]['Symbol'] == 'SPY'

    def test_list_shares_query(self):
        """Test that shares.query() returns data"""
        result = self.factory.shares.query(self.factory.username)
        assert len(result) == 1

    def test_shares_as_dataframe(self):
        """Test shares.as_df()"""
        df = self.factory.shares.as_df(self.factory.username)
        assert len(df) == 1
        assert df.iloc[0]['Symbol'] == 'TSLA'

    def test_list_deposits_query(self):
        """Test that deposits.query() returns data"""
        result = self.factory.deposits.query(self.factory.username)
        assert len(result) == 1

    def test_deposits_as_dataframe(self):
        """Test deposits.as_df()"""
        df = self.factory.deposits.as_df(self.factory.username)
        assert len(df) == 1
        assert float(df.iloc[0]['Amount']) == 10000.00


class TestCLISymbolOperations:
    """Test symbol extraction operations used by CLI"""

    def setup_method(self):
        """Set up test data with multiple symbols"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create trades with different symbols
        for i, symbol in enumerate(["AAPL", "TSLA", "SPY"]):
            self.factory.create_trade(
                symbol=symbol,
                date=f"2025-01-{i+1:02d}"
            )

    def test_extract_unique_symbols(self):
        """Test extracting unique symbols from trades"""
        rows = self.factory.trades.query(self.factory.username)
        symbols = set(row[8] for row in rows)  # symbol column

        assert len(symbols) == 3
        assert "AAPL" in symbols
        assert "TSLA" in symbols
        assert "SPY" in symbols


class TestCLIAccountOperations:
    """Test account listing operations used by CLI"""

    def setup_method(self):
        """Set up test data with multiple accounts"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create trades in different accounts
        for account in ["Fidelity", "Robinhood", "Schwab"]:
            self.factory.create_trade(
                symbol="SPY",
                account=account
            )

    def test_list_unique_accounts(self):
        """Test extracting unique accounts"""
        rows = self.factory.trades.query(self.factory.username)
        accounts = set(row[3] for row in rows)  # account column

        assert len(accounts) == 3
        assert "Fidelity" in accounts
        assert "Robinhood" in accounts
        assert "Schwab" in accounts

    def test_filter_by_account(self):
        """Test filtering by specific account"""
        rows = self.factory.trades.query(self.factory.username, condition='account="Fidelity"')
        assert len(rows) == 1
        assert rows[0][3] == "Fidelity"


class TestCLIDateFiltering:
    """Test date filtering operations used by CLI"""

    def setup_method(self):
        """Set up test data across date range"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create trades on different dates
        for date in ["2025-01-01", "2025-01-15", "2025-01-30"]:
            self.factory.create_trade(
                symbol="SPY",
                date=date
            )

    def test_filter_by_date_range(self):
        """Test date range filtering"""
        rows = self.factory.trades.query(
            self.factory.username,
            condition='date >= "2025-01-10" AND date <= "2025-01-20"'
        )

        assert len(rows) == 1
        assert rows[0][4] == "2025-01-15"  # date column

    def test_get_all_dates(self):
        """Test retrieving all trades across date range"""
        df = self.factory.trades.as_df(self.factory.username)
        assert len(df) == 3


class TestCLIStyledOutput:
    """Test styled output formatting used by CLI"""

    def setup_method(self):
        """Set up test data"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)
        self.factory.create_trade(symbol="SPY")

    def test_styled_df_output(self):
        """Test that styled_df() produces output"""
        result = self.factory.trades.styled_df(self.factory.username)
        assert result is not None
        assert len(result) > 0
        # Should contain the symbol
        assert "SPY" in result['Symbol'].values


class TestCLIMultipleTransactionTypes:
    """Test querying across different transaction types"""

    def setup_method(self):
        """Set up all transaction types"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Use the factory to create a complete portfolio
        self.factory.create_sample_portfolio(
            num_trades=3,
            num_dividends=2,
            num_shares=2,
            num_deposits=1
        )

    def test_count_all_transaction_types(self):
        """Test that all transaction types are stored"""
        assert len(self.factory.trades.query(self.factory.username)) == 3
        assert len(self.factory.dividends.query(self.factory.username)) == 2
        assert len(self.factory.shares.query(self.factory.username)) == 2
        assert len(self.factory.deposits.query(self.factory.username)) == 1

    def test_dataframes_for_all_types(self):
        """Test that all transaction types can be converted to DataFrame"""
        trades_df = self.factory.trades.as_df(self.factory.username)
        divs_df = self.factory.dividends.as_df(self.factory.username)
        shares_df = self.factory.shares.as_df(self.factory.username)
        deps_df = self.factory.deposits.as_df(self.factory.username)

        assert len(trades_df) == 3
        assert len(divs_df) == 2
        assert len(shares_df) == 2
        assert len(deps_df) == 1


class TestCLIAccountFilter:
    """Test account-based filtering across transaction types"""

    def setup_method(self):
        """Set up test data across multiple accounts"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create transactions in Fidelity account
        self.factory.create_trade(symbol="AAPL", account="Fidelity", date="2025-01-01")
        self.factory.create_dividend(symbol="SPY", account="Fidelity", date="2025-01-02")

        # Create transactions in Robinhood account
        self.factory.create_trade(symbol="TSLA", account="Robinhood", date="2025-01-03")
        self.factory.create_share(symbol="NVDA", account="Robinhood", date="2025-01-04")

    def test_filter_trades_by_account(self):
        """Test filtering trades by account"""
        fidelity_trades = self.factory.trades.query(
            self.factory.username,
            condition='account="Fidelity"'
        )
        assert len(fidelity_trades) == 1
        assert fidelity_trades[0][8] == "AAPL"

    def test_filter_dividends_by_account(self):
        """Test filtering dividends by account"""
        fidelity_divs = self.factory.dividends.query(
            self.factory.username,
            condition='account="Fidelity"'
        )
        assert len(fidelity_divs) == 1


class TestCLIOperationTypes:
    """Test filtering by operation type (STO, BTC, etc.)"""

    def setup_method(self):
        """Set up test data with different operations"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create different operation types
        self.factory.create_trade(symbol="AAPL", operation="STO", date="2025-01-01")
        self.factory.create_trade(symbol="TSLA", operation="BTC", date="2025-01-02")
        self.factory.create_trade(symbol="SPY", operation="STO", date="2025-01-03")

    def test_filter_by_operation(self):
        """Test filtering trades by operation type"""
        sto_trades = self.factory.trades.query(
            self.factory.username,
            condition='operation="STO"'
        )
        assert len(sto_trades) == 2

        btc_trades = self.factory.trades.query(
            self.factory.username,
            condition='operation="BTC"'
        )
        assert len(btc_trades) == 1


class TestCLIGuildFiltering:
    """Test guild-based filtering"""

    def setup_method(self):
        """Set up test data across multiple guilds"""
        self.db = Db(':memory:')
        self.factory = TestDataFactory(self.db)

        # Create trades in different guilds
        self.factory.create_trade(symbol="AAPL", guild_id=111, date="2025-01-01")
        self.factory.create_trade(symbol="TSLA", guild_id=222, date="2025-01-02")

    def test_filter_by_guild(self):
        """Test filtering by guild ID"""
        guild_trades = self.factory.trades.query(
            self.factory.username,
            condition='guild_id=111'
        )
        assert len(guild_trades) == 1
        assert guild_trades[0][8] == "AAPL"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
