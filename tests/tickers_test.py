"""
Unit tests for Tickers functionality.

Tests for ticker management including insert, lookup, search, and validation.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ticker import Ticker
from tickers import Tickers
from db import Db


class TestTickerInsert:
    """Test ticker insertion"""

    def setup_method(self):
        """Set up test database"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

    def test_insert_ticker(self):
        """Test inserting a single ticker"""
        ticker = Ticker(
            ticker="AAPL",
            company_name="Apple Inc",
            exchange="NASDAQ",
            sector="Technology",
            is_active=True
        )

        self.tickers.insert(ticker)

        # Verify ticker was inserted
        result = self.tickers.get_ticker("AAPL")
        assert result is not None
        assert result.ticker == "AAPL"
        assert result.company_name == "Apple Inc"
        assert result.exchange == "NASDAQ"

    def test_insert_duplicate_ticker_updates(self):
        """Test that inserting a duplicate ticker updates the existing one"""
        ticker1 = Ticker(
            ticker="AAPL",
            company_name="Apple Inc",
            exchange="NASDAQ",
            sector="Technology",
            is_active=True
        )
        self.tickers.insert(ticker1)

        # Insert same ticker with different company name
        ticker2 = Ticker(
            ticker="AAPL",
            company_name="Apple Incorporated",
            exchange="NASDAQ",
            sector="Tech",
            is_active=True
        )
        self.tickers.insert(ticker2)

        # Should have updated, not duplicated
        result = self.tickers.get_ticker("AAPL")
        assert result.company_name == "Apple Incorporated"
        assert result.sector == "Tech"

    def test_insert_bulk(self):
        """Test bulk insertion of tickers"""
        tickers = [
            Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True),
            Ticker("GOOGL", "Alphabet Inc", "NASDAQ", "Technology", True),
            Ticker("MSFT", "Microsoft Corp", "NASDAQ", "Technology", True),
        ]

        count = self.tickers.insert_bulk(tickers)
        assert count == 3

        # Verify all were inserted
        assert self.tickers.is_valid_ticker("AAPL")
        assert self.tickers.is_valid_ticker("GOOGL")
        assert self.tickers.is_valid_ticker("MSFT")


class TestTickerValidation:
    """Test ticker validation"""

    def setup_method(self):
        """Set up test database with sample tickers"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

        # Insert some test tickers
        self.tickers.insert(Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("TSLA", "Tesla Inc", "NASDAQ", "Automotive", True))
        self.tickers.insert(Ticker("INACTIVE", "Inactive Co", "NYSE", None, False))

    def test_is_valid_ticker_active(self):
        """Test that active tickers are valid"""
        assert self.tickers.is_valid_ticker("AAPL") == True
        assert self.tickers.is_valid_ticker("TSLA") == True

    def test_is_valid_ticker_inactive(self):
        """Test that inactive tickers are not valid by default"""
        assert self.tickers.is_valid_ticker("INACTIVE") == False

    def test_is_valid_ticker_not_exists(self):
        """Test that non-existent tickers are not valid"""
        assert self.tickers.is_valid_ticker("NOTEXIST") == False

    def test_get_ticker(self):
        """Test retrieving a ticker by symbol"""
        ticker = self.tickers.get_ticker("AAPL")
        assert ticker is not None
        assert ticker.ticker == "AAPL"
        assert ticker.company_name == "Apple Inc"
        assert ticker.is_active == True

    def test_get_ticker_not_exists(self):
        """Test retrieving non-existent ticker returns None"""
        ticker = self.tickers.get_ticker("NOTEXIST")
        assert ticker is None


class TestTickerSearch:
    """Test ticker search functionality"""

    def setup_method(self):
        """Set up test database with sample tickers"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

        # Insert test tickers
        self.tickers.insert(Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("GOOGL", "Alphabet Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("MSFT", "Microsoft Corp", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("AMZN", "Amazon.com Inc", "NASDAQ", "E-commerce", True))
        self.tickers.insert(Ticker("META", "Meta Platforms Inc", "NASDAQ", "Technology", True))

    def test_search_by_ticker_symbol(self):
        """Test searching by ticker symbol"""
        results = self.tickers.search("AAP", limit=10)
        assert len(results) > 0
        assert any(t.ticker == "AAPL" for t in results)

    def test_search_by_company_name(self):
        """Test searching by company name"""
        results = self.tickers.search("Apple", limit=10)
        assert len(results) > 0
        assert any(t.company_name == "Apple Inc" for t in results)

    def test_search_case_insensitive(self):
        """Test that search is case insensitive"""
        results = self.tickers.search("apple", limit=10)
        assert len(results) > 0
        assert any(t.company_name == "Apple Inc" for t in results)

    def test_search_with_limit(self):
        """Test that search respects limit parameter"""
        results = self.tickers.search("", limit=3)
        assert len(results) <= 3


class TestTickerCount:
    """Test ticker counting"""

    def setup_method(self):
        """Set up test database"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

        # Insert tickers with mix of active and inactive
        self.tickers.insert(Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("TSLA", "Tesla Inc", "NASDAQ", "Automotive", True))
        self.tickers.insert(Ticker("INACTIVE1", "Inactive Co", "NYSE", None, False))
        self.tickers.insert(Ticker("INACTIVE2", "Old Company", "NYSE", None, False))

    def test_count_active_only(self):
        """Test counting only active tickers"""
        count = self.tickers.count(active_only=True)
        assert count == 2

    def test_count_all(self):
        """Test counting all tickers"""
        count = self.tickers.count(active_only=False)
        assert count == 4


class TestTickerDelete:
    """Test ticker deletion"""

    def setup_method(self):
        """Set up test database"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

        self.tickers.insert(Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("TSLA", "Tesla Inc", "NASDAQ", "Automotive", True))

    def test_delete_existing_ticker(self):
        """Test deleting an existing ticker (soft delete - sets is_active to 0)"""
        rows_deleted = self.tickers.delete("AAPL")
        assert rows_deleted == 1

        # Verify ticker is still there but marked inactive
        ticker = self.tickers.get_ticker("AAPL")
        assert ticker is not None
        assert ticker.is_active == False

        # Verify it's not considered valid anymore
        assert self.tickers.is_valid_ticker("AAPL") == False

    def test_delete_non_existent_ticker(self):
        """Test deleting a non-existent ticker"""
        rows_deleted = self.tickers.delete("NOTEXIST")
        assert rows_deleted == 0


class TestTickerDataFrame:
    """Test DataFrame conversion"""

    def setup_method(self):
        """Set up test database with sample tickers"""
        self.db = Db(':memory:')
        self.tickers = Tickers(self.db)

        # Insert test tickers
        self.tickers.insert(Ticker("AAPL", "Apple Inc", "NASDAQ", "Technology", True))
        self.tickers.insert(Ticker("TSLA", "Tesla Inc", "NASDAQ", "Automotive", True))
        self.tickers.insert(Ticker("INACTIVE", "Inactive Co", "NYSE", None, False))

    def test_as_df_active_only(self):
        """Test DataFrame conversion with active tickers only"""
        df = self.tickers.as_df(active_only=True)
        assert len(df) == 2
        assert all(df['Active'] == True)

    def test_as_df_all_tickers(self):
        """Test DataFrame conversion with all tickers"""
        df = self.tickers.as_df(active_only=False)
        assert len(df) == 3

    def test_as_df_with_limit(self):
        """Test DataFrame conversion with limit"""
        df = self.tickers.as_df(active_only=False, limit=2)
        assert len(df) <= 2

    def test_as_df_columns(self):
        """Test that DataFrame has expected columns"""
        df = self.tickers.as_df()
        expected_columns = ['Ticker', 'Company', 'Exchange', 'Sector', 'Active', 'Added']
        assert list(df.columns) == expected_columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
