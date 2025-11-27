"""
Unit tests for Db class

Tests database operations including connection management, queries,
inserts, error handling, and transaction management.
Uses Trades, Shares, Dividends, and Deposits classes for realistic testing.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
import sqlite3
from db import Db
from trade import Trade
from trades import Trades
from share import Share
from shares import Shares
from dividend import Dividend
from dividends import Dividends
from deposit import Deposit
from deposits import Deposits


class TestDbConnection(unittest.TestCase):
    """Test database connection initialization"""

    def test_in_memory_connection(self):
        """Test that in-memory database is created correctly"""
        db = Db(in_memory=True)
        self.assertIsNotNone(db.connection)
        # Verify it's an in-memory database by checking we can create tables
        db.connection.execute("CREATE TABLE test (id INTEGER)")
        self.assertTrue(True)  # If we get here, connection works

    def test_connection_close_on_delete(self):
        """Test that connection is closed when Db object is deleted"""
        db = Db(in_memory=True)
        conn = db.connection
        self.assertIsNotNone(conn)

        # Delete the Db object
        del db

        # Connection should be closed (trying to use it will raise an error)
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


class TestDbCreateTable(unittest.TestCase):
    """Test create_table() method using Trades class"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)

    def test_create_table_success(self):
        """Test successful table creation using Trades"""
        trades = Trades(self.db)

        # Verify table was created by querying it
        result = self.db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'trades')

    def test_create_table_error(self):
        """Test create_table() raises on invalid SQL"""
        query = "CREATE TABLE invalid syntax here"

        with self.assertRaises(Exception):
            self.db.create_table(query)


class TestDbInsert(unittest.TestCase):
    """Test insert() method using Trades"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)
        self.trades = Trades(self.db)

    def test_insert_success(self):
        """Test successful insert using trades.insert()"""
        trade = Trade('testuser', '2025-01-01', 'STO 1x AAPL 1/15 150P @ 2.50')
        trade.parse()

        self.trades.insert(trade.as_named_tuple())

        # Verify insert
        result = self.db.query("SELECT * FROM trades")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 'testuser')
        self.assertEqual(result[0][8], 'AAPL')  # Symbol is now column 8 (was 6, shifted by 2 for guild_id and account)

    def test_insert_error(self):
        """Test insert() raises on constraint violation"""
        # Insert with explicit ID
        query = """
            INSERT INTO trades (id, username, date, raw_trade, operation, contracts, symbol, expiration_date, strike_price, option_type, premium, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        row = (1, 'testuser', '2025-01-01', 'STO 1x AAPL 1/1 150P @ 2.50', 'STO', 1, 'AAPL', '2025-01-01', 150.0, 'P', 2.50, 250.0)
        self.db.insert(query, row)

        # Try to insert duplicate ID (should fail)
        with self.assertRaises(Exception):
            self.db.insert(query, row)


class TestDbQuery(unittest.TestCase):
    """Test query() method using Trades and Shares"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)
        self.trades = Trades(self.db)

        # Insert test data using trades.insert()
        trade1 = Trade('user1', '2025-01-01', 'STO 1x AAPL 1/15 150P @ 2.50')
        trade1.parse()
        self.trades.insert(trade1.as_named_tuple())

        trade2 = Trade('user1', '2025-01-02', 'STO 2x AAPL 1/15 155P @ 3.00')
        trade2.parse()
        self.trades.insert(trade2.as_named_tuple())

        trade3 = Trade('user2', '2025-01-03', 'STO 1x TSLA 1/15 250C @ 5.00')
        trade3.parse()
        self.trades.insert(trade3.as_named_tuple())

    def test_query_all(self):
        """Test query without conditions"""
        results = self.db.query("SELECT * FROM trades")
        self.assertEqual(len(results), 3)

    def test_query_with_condition(self):
        """Test query with WHERE clause"""
        results = self.db.query("SELECT * FROM trades", condition='symbol="AAPL"')
        self.assertEqual(len(results), 2)

    def test_query_with_orderby(self):
        """Test query with ORDER BY clause"""
        results = self.db.query("SELECT * FROM trades", orderby='premium DESC')
        self.assertEqual(results[0][12], 5.00)  # TSLA should be first (premium is column 12, was 10, shifted by 2)

    def test_query_with_groupby(self):
        """Test query with GROUP BY clause"""
        results = self.db.query(
            "SELECT symbol, SUM(contracts) FROM trades",
            groupby='symbol',
            orderby='symbol'
        )
        self.assertEqual(len(results), 2)  # AAPL and TSLA
        self.assertEqual(results[0][0], 'AAPL')
        self.assertEqual(results[0][1], 3)  # Total AAPL contracts

    def test_query_with_all_clauses(self):
        """Test query with WHERE, GROUP BY, and ORDER BY"""
        results = self.db.query(
            "SELECT username, COUNT(*) FROM trades",
            condition='contracts > 0',
            groupby='username',
            orderby='username'
        )
        self.assertEqual(len(results), 2)  # user1 and user2

    def test_query_error(self):
        """Test query() raises on invalid SQL"""
        with self.assertRaises(Exception):
            self.db.query("SELECT * FROM nonexistent_table")


class TestDbQueryParameterized(unittest.TestCase):
    """Test query_parameterized() method using Dividends"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)
        self.dividends = Dividends(self.db)

        # Insert test data using dividends.insert()
        div1 = Dividend('user1', '2025-01-01', 'Dividend AAPL 150.50')
        div1.parse()
        self.dividends.insert(div1.as_named_tuple())

        div2 = Dividend('user1', '2025-01-02', 'Dividend TSLA 250.00')
        div2.parse()
        self.dividends.insert(div2.as_named_tuple())

    def test_parameterized_query_with_params(self):
        """Test parameterized query with parameters"""
        query = "SELECT * FROM dividends WHERE symbol = ?"
        params = ('AAPL',)

        results = self.db.query_parameterized(query, params)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][5], 'AAPL')  # Symbol is column 5 in dividends table (was 3, shifted by 2)

    def test_parameterized_query_without_params(self):
        """Test parameterized query without parameters"""
        query = "SELECT * FROM dividends"

        results = self.db.query_parameterized(query, None)
        self.assertEqual(len(results), 2)

    def test_parameterized_query_multiple_params(self):
        """Test parameterized query with multiple parameters"""
        query = "SELECT * FROM dividends WHERE symbol = ? AND amount > ?"
        params = ('TSLA', 100.00)

        results = self.db.query_parameterized(query, params)
        self.assertEqual(len(results), 1)

    def test_parameterized_query_error(self):
        """Test query_parameterized() raises on invalid SQL"""
        with self.assertRaises(Exception):
            self.db.query_parameterized("SELECT * FROM nonexistent_table")


class TestDbExecute(unittest.TestCase):
    """Test execute() method using Deposits"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)
        self.deposits = Deposits(self.db)

        # Insert test data using deposits.insert()
        dep = Deposit('user1', '2025-01-01', 'Deposit 1000')
        dep.parse()
        self.deposits.insert(dep.as_named_tuple())

    def test_execute_with_params(self):
        """Test execute() with parameters (UPDATE)"""
        query = "UPDATE deposits SET amount = ? WHERE username = ?"
        params = (2000.00, 'user1')

        cur = self.db.execute(query, params)
        self.assertIsNotNone(cur)
        self.assertEqual(cur.rowcount, 1)

        # Verify update
        result = self.db.query("SELECT amount FROM deposits WHERE username = 'user1'")
        self.assertEqual(result[0][0], 2000.00)

    def test_execute_without_params(self):
        """Test execute() without parameters (DELETE)"""
        query = "DELETE FROM deposits WHERE username = 'user1'"

        cur = self.db.execute(query)
        self.assertIsNotNone(cur)
        self.assertEqual(cur.rowcount, 1)

        # Verify deletion
        result = self.db.query("SELECT * FROM deposits")
        self.assertEqual(len(result), 0)

    def test_execute_error(self):
        """Test execute() raises on invalid SQL"""
        with self.assertRaises(Exception):
            self.db.execute("INVALID SQL STATEMENT")


class TestDbCommit(unittest.TestCase):
    """Test commit() method using Shares"""

    def setUp(self):
        """Set up test fixtures"""
        self.db = Db(in_memory=True)
        self.shares = Shares(self.db)

    def test_commit_success(self):
        """Test successful commit operation"""
        # Use shares.insert() which auto-commits via context manager
        share = Share('user1', '2025-01-01', 'Buy 100 AAPL @ 150.00')
        share.parse()
        self.shares.insert(share.as_named_tuple())

        # Manually commit (redundant but tests the method)
        self.db.commit()

        # Verify data is committed
        result = self.db.query("SELECT * FROM shares")
        self.assertEqual(len(result), 1)

    def test_commit_error(self):
        """Test commit() error handling"""
        # Close the connection to force commit error
        self.db.connection.close()

        # Try to commit (should raise exception)
        with self.assertRaises(Exception):
            self.db.commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
