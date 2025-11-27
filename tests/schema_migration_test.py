#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import unittest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from db import Db
from trades import Trades
from shares import Shares
from dividends import Dividends
from deposits import Deposits
from trade import Trade
from share import Share
from dividend import Dividend
from deposit import Deposit


class TestSchemaMigration(unittest.TestCase):
    """Comprehensive tests for guild_id and account schema migration"""

    def setUp(self):
        """Create in-memory database for each test"""
        self.db = Db(in_memory=True)
        self.trades = Trades(self.db)
        self.shares = Shares(self.db)
        self.dividends = Dividends(self.db)
        self.deposits = Deposits(self.db)

    def tearDown(self):
        """Clean up database connection"""
        if self.db:
            del self.db

    def test_backward_compatibility_trades(self):
        """Test that old code (without guild_id/account) still works with trades"""
        # Insert using old method (without guild_id/account in the Trade object)
        trade = Trade('testuser', '2025-01-15', 'STO 1x AAPL 1/31 150P @ 2.50')
        trade.parse()
        self.assertTrue(trade.is_valid())

        nt = trade.as_named_tuple()
        self.trades.insert(nt)

        # Query should work
        df = self.trades.as_df('testuser')
        self.assertEqual(len(df), 1)

        # Verify defaults are set correctly
        rows = self.trades.query('testuser')
        self.assertEqual(len(rows), 1)
        # guild_id should be at index 2, account at index 3
        self.assertIsNone(rows[0][2])  # guild_id = NULL
        self.assertEqual(rows[0][3], 'default')  # account = 'default'

    def test_guild_id_population_trades(self):
        """Test that guild_id can be set and stored correctly for trades"""
        trade = Trade('testuser', '2025-01-15', 'STO 1x AAPL 1/31 150P @ 2.50')
        trade.parse()

        # Manually set guild_id and account
        trade.guild_id = 1234567890
        trade.account = 'IRA'

        nt = trade.as_named_tuple()
        self.assertEqual(nt.guild_id, 1234567890)
        self.assertEqual(nt.account, 'IRA')

        self.trades.insert(nt)

        # Query and verify
        rows = self.trades.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 1234567890)  # guild_id
        self.assertEqual(rows[0][3], 'IRA')  # account

    def test_account_filtering_trades(self):
        """Test that account filtering works correctly for trades"""
        # Insert trades with different accounts
        for i, account in enumerate(['default', 'IRA', 'Roth', 'IRA']):
            trade = Trade('testuser', '2025-01-15', f'STO 1x AAPL 1/31 {150+i}P @ 2.50')
            trade.parse()
            trade.account = account
            nt = trade.as_named_tuple()
            self.trades.insert(nt)

        # Query all trades
        all_trades = self.trades.query('testuser')
        self.assertEqual(len(all_trades), 4)

        # Query with account filter
        ira_condition = 'account="IRA"'
        ira_trades = self.trades.query('testuser', condition=ira_condition)
        self.assertEqual(len(ira_trades), 2)

        # Verify both IRA trades are returned
        for row in ira_trades:
            self.assertEqual(row[3], 'IRA')

    def test_backward_compatibility_shares(self):
        """Test that old code still works with shares"""
        share = Share('testuser', '01/15/2025', 'Buy 100 shares AAPL @ 150')
        share.parse()
        self.assertTrue(share.is_valid())

        nt = share.as_named_tuple()
        self.shares.insert(nt)

        # Query should work
        df = self.shares.as_df('testuser')
        self.assertEqual(len(df), 1)

        # Verify defaults
        rows = self.shares.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0][2])  # guild_id = NULL
        self.assertEqual(rows[0][3], 'default')  # account = 'default'

    def test_guild_id_population_shares(self):
        """Test guild_id population for shares"""
        share = Share('testuser', '01/15/2025', 'Buy 100 shares AAPL @ 150')
        share.parse()
        share.guild_id = 1234567890
        share.account = 'Trading'

        nt = share.as_named_tuple()
        self.shares.insert(nt)

        rows = self.shares.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 1234567890)  # guild_id
        self.assertEqual(rows[0][3], 'Trading')  # account

    def test_backward_compatibility_dividends(self):
        """Test that old code still works with dividends"""
        dividend = Dividend('testuser', '01/15/2025', 'Dividend AAPL 50.00')
        dividend.parse()
        self.assertTrue(dividend.is_valid())

        nt = dividend.as_named_tuple()
        self.dividends.insert(nt)

        df = self.dividends.as_df('testuser')
        self.assertEqual(len(df), 1)

        rows = self.dividends.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0][2])  # guild_id = NULL
        self.assertEqual(rows[0][3], 'default')  # account = 'default'

    def test_guild_id_population_dividends(self):
        """Test guild_id population for dividends"""
        dividend = Dividend('testuser', '01/15/2025', 'Dividend AAPL 50.00')
        dividend.parse()
        dividend.guild_id = 1234567890
        dividend.account = 'Roth'

        nt = dividend.as_named_tuple()
        self.dividends.insert(nt)

        rows = self.dividends.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 1234567890)  # guild_id
        self.assertEqual(rows[0][3], 'Roth')  # account

    def test_backward_compatibility_deposits(self):
        """Test that old code still works with deposits"""
        deposit = Deposit('testuser', '01/15/2025', 'Deposit 10000')
        deposit.parse()
        self.assertTrue(deposit.is_valid())

        nt = deposit.as_named_tuple()
        self.deposits.insert(nt)

        df = self.deposits.as_df('testuser')
        self.assertEqual(len(df), 1)

        rows = self.deposits.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0][2])  # guild_id = NULL
        self.assertEqual(rows[0][3], 'default')  # account = 'default'

    def test_guild_id_population_deposits(self):
        """Test guild_id population for deposits"""
        deposit = Deposit('testuser', '01/15/2025', 'Deposit 10000')
        deposit.parse()
        deposit.guild_id = 1234567890
        deposit.account = 'IRA'

        nt = deposit.as_named_tuple()
        self.deposits.insert(nt)

        rows = self.deposits.query('testuser')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 1234567890)  # guild_id
        self.assertEqual(rows[0][3], 'IRA')  # account

    def test_mixed_guild_and_accounts(self):
        """Test querying with multiple guilds and accounts"""
        # Insert trades from different guilds and accounts
        configs = [
            (1111111111, 'default'),
            (1111111111, 'IRA'),
            (2222222222, 'default'),
            (2222222222, 'Roth'),
            (None, 'default'),  # Old record without guild_id
        ]

        for i, (guild_id, account) in enumerate(configs):
            trade = Trade('testuser', '2025-01-15', f'STO 1x AAPL 1/31 {150+i}P @ 2.50')
            trade.parse()
            if guild_id:
                trade.guild_id = guild_id
            trade.account = account
            nt = trade.as_named_tuple()
            self.trades.insert(nt)

        # Query all trades
        all_trades = self.trades.query('testuser')
        self.assertEqual(len(all_trades), 5)

        # Query by guild and account
        condition = 'guild_id=1111111111 AND account="IRA"'
        filtered = self.trades.query('testuser', condition=condition)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0][2], 1111111111)
        self.assertEqual(filtered[0][3], 'IRA')

    def test_database_schema_contains_new_columns(self):
        """Verify that all tables have guild_id and account columns"""
        tables = ['trades', 'shares', 'dividends', 'deposits']

        for table in tables:
            cursor = self.db.connection.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            self.assertIn('guild_id', columns, f"{table} should have guild_id column")
            self.assertIn('account', columns, f"{table} should have account column")


if __name__ == '__main__':
    unittest.main()
