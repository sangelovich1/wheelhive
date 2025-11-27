#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import unittest
import sys
import os
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from db import Db
from trades import Trades
from shares import Shares
from dividends import Dividends


def create_trade(username, date_str, trade_str):
    """Helper to create and parse a Trade object, returning the namedtuple."""
    from trade import Trade
    trade = Trade(username, date_str, trade_str)
    trade.parse()
    return trade.as_named_tuple()


class TestBaseTableProcessor(unittest.TestCase):
    """Test suite for BaseTableProcessor functionality through concrete implementations."""

    def setUp(self):
        """Set up test fixtures with in-memory database."""
        self.db = Db(in_memory=True)
        self.username = 'test_basetable_user'
        self.trades = Trades(self.db)
        self.shares = Shares(self.db)
        self.dividends = Dividends(self.db)

    def tearDown(self):
        """Clean up test data."""
        # No need to clean up - in-memory database is destroyed automatically
        pass

    def test_set_debug(self):
        """Test that set_debug() changes the debug flag."""
        self.assertFalse(self.trades.debug)
        self.trades.set_debug(True)
        self.assertTrue(self.trades.debug)
        self.trades.set_debug(False)
        self.assertFalse(self.trades.debug)

    def test_get_name(self):
        """Test that get_name() returns the correct table name."""
        self.assertEqual(self.trades.get_name(), 'trades')
        self.assertEqual(self.shares.get_name(), 'shares')
        self.assertEqual(self.dividends.get_name(), 'dividends')

    def test_query_with_specific_fields(self):
        """Test querying with specific field selection."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        # Query with specific fields
        results = self.trades.query(self.username, fields=['Symbol', 'Operation', 'Date'])
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 3)  # Should only have 3 fields

    def test_query_with_no_username(self):
        """Test querying with condition but no username."""
        trade1 = create_trade("user1", '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade("user2", '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        # Query without username but with condition
        results = self.trades.query(username=None, condition='Symbol="AAPL"')
        self.assertEqual(len(results), 2)  # Should get both users' trades

    def test_query_with_username_only(self):
        """Test querying with username but no additional condition."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade(self.username, '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        # Query with only username (no condition)
        results = self.trades.query(username=self.username, condition=None)
        self.assertEqual(len(results), 2)

    def test_query_with_no_username_no_condition(self):
        """Test querying with no username and no condition returns all records."""
        trade1 = create_trade("user1", '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade("user2", '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        # Query with no username and no condition
        results = self.trades.query(username=None, condition=None)
        self.assertGreaterEqual(len(results), 2)

    def test_query_all(self):
        """Test query_all() returns all records from table."""
        trade1 = create_trade("user1", '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade("user2", '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        results = self.trades.query_all()
        self.assertGreaterEqual(len(results), 2)

    def test_delete_by_id(self):
        """Test delete() removes a specific record by ID."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        # Get the ID of the inserted trade
        results = self.trades.query(self.username)
        self.assertEqual(len(results), 1)
        record_id = results[0][0]  # ID is first column

        # Delete by ID
        count = self.trades.delete(self.username, record_id)
        self.assertEqual(count, 1)

        # Verify deletion
        results = self.trades.query(self.username)
        self.assertEqual(len(results), 0)

    def test_delete_nonexistent_id(self):
        """Test delete() returns 0 when ID doesn't exist."""
        count = self.trades.delete(self.username, 99999)
        self.assertEqual(count, 0)

    def test_delete_range_with_datetime_objects(self):
        """Test delete_range() with datetime objects instead of strings."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade(self.username, '2025-01-20', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        # Delete using datetime objects
        start = datetime(2025, 1, 14)
        end = datetime(2025, 1, 16)
        count = self.trades.delete_range(self.username, start, end)
        self.assertEqual(count, 1)

        # Verify only one trade remains
        results = self.trades.query(self.username)
        self.assertEqual(len(results), 1)

    def test_delete_range_with_strings(self):
        """Test delete_range() with string dates."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade(self.username, '2025-01-20', "STO 1x TSLA 12/31 250C @ 3.00")
        trade3 = create_trade(self.username, '2025-01-25', "STO 1x NVDA 12/31 450C @ 5.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)
        self.trades.insert(trade3)

        # Delete middle trade
        count = self.trades.delete_range(self.username, '2025-01-18', '2025-01-22')
        self.assertEqual(count, 1)

        # Verify two trades remain
        results = self.trades.query(self.username)
        self.assertEqual(len(results), 2)

    def test_as_csv(self):
        """Test as_csv() creates a CSV file."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        csv_file = '/tmp/test_basetable.csv'
        result = self.trades.as_csv(self.username, csv_file)

        self.assertEqual(result, csv_file)
        self.assertTrue(os.path.exists(csv_file))

        # Verify CSV contents
        df = pd.read_csv(csv_file)
        self.assertEqual(len(df), 1)
        self.assertIn('Symbol', df.columns)

        # Clean up
        os.remove(csv_file)

    def test_as_str_with_data(self):
        """Test as_str() returns formatted table string."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        result = self.trades.as_str(self.username)
        self.assertIsInstance(result, str)
        self.assertIn('AAPL', result)
        self.assertGreater(len(result), 0)

    def test_as_str_with_no_data(self):
        """Test as_str() returns message when no data found."""
        result = self.trades.as_str(self.username)
        self.assertEqual(result, "No records found.")

    def test_styled_df_delegates_to_as_df(self):
        """Test that styled_df() calls as_df()."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        df = self.trades.styled_df(self.username)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 1)

    def test_as_df_with_empty_results(self):
        """Test as_df() returns empty DataFrame with correct headers when no data."""
        df = self.trades.as_df(self.username)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 0)
        self.assertIn('Symbol', df.columns)
        self.assertIn('Date', df.columns)

    def test_as_df_date_formatting(self):
        """Test that as_df() formats dates correctly (MM/DD/YYYY)."""
        trade = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        self.trades.insert(trade)

        df = self.trades.as_df(self.username)
        date_value = df['Date'].iloc[0]
        self.assertRegex(date_value, r'^\d{2}/\d{2}/\d{4}$')  # MM/DD/YYYY format

    def test_as_csv_with_filter(self):
        """Test as_csv() with symbol filter."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade(self.username, '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        csv_file = '/tmp/test_basetable_filter.csv'
        result = self.trades.as_csv(self.username, csv_file, filter='Symbol="AAPL"')

        # Verify only AAPL trade is in CSV
        df = pd.read_csv(csv_file)
        self.assertEqual(len(df), 1)
        self.assertEqual(df['Symbol'].iloc[0], 'AAPL')

        # Clean up
        os.remove(csv_file)

    def test_as_str_with_filter(self):
        """Test as_str() with symbol filter."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade(self.username, '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        result = self.trades.as_str(self.username, filter='Symbol="TSLA"')
        self.assertIn('TSLA', result)
        self.assertNotIn('AAPL', result)

    def test_delete_all_with_multiple_records(self):
        """Test delete_all() removes all user records."""
        for i in range(5):
            trade = create_trade(self.username, f'2025-01-{i+10}', f"STO 1x AAPL 12/{i+1} 150P @ 2.50")
            self.trades.insert(trade)

        count = self.trades.delete_all(self.username)
        self.assertEqual(count, 5)

        results = self.trades.query(self.username)
        self.assertEqual(len(results), 0)

    def test_delete_all_does_not_affect_other_users(self):
        """Test delete_all() only deletes records for specified user."""
        trade1 = create_trade(self.username, '2025-01-15', "STO 1x AAPL 12/31 150P @ 2.50")
        trade2 = create_trade("other_user", '2025-01-16', "STO 1x TSLA 12/31 250C @ 3.00")
        self.trades.insert(trade1)
        self.trades.insert(trade2)

        count = self.trades.delete_all(self.username)
        self.assertEqual(count, 1)

        # Verify other user's trade still exists
        results = self.trades.query("other_user")
        self.assertEqual(len(results), 1)


if __name__ == '__main__':
    unittest.main()
