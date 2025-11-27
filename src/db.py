#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
import sqlite3

# Local application imports
import constants as const


# Get a logger instance
logger = logging.getLogger(__name__)

class Db:
    connection: sqlite3.Connection

    def __init__(self, in_memory: bool = False) -> None:
        """
        Initialize database connection.

        Args:
            in_memory: If True, use an in-memory SQLite database (useful for testing).
                      If False (default), use the persistent trades.db file.
        """
        if in_memory:
            logger.info("init in-memory database")
            self.connection = sqlite3.connect(":memory:")
        else:
            logger.info(f"init database at {const.DATABASE_PATH}")
            # Add timeout to retry on locks (10 seconds) and enable WAL mode for concurrency
            # check_same_thread=False allows connection use across threads (safe with WAL + context managers)
            self.connection = sqlite3.connect(const.DATABASE_PATH, timeout=10.0, check_same_thread=False)

            # Enable Write-Ahead Logging for better concurrency
            # WAL allows readers to access database while writers are active
            self.connection.execute("PRAGMA journal_mode=WAL")
            logger.info("Database configured with WAL mode, 10s timeout, and multi-thread support")


    def __del__(self) -> None:
        if self.connection is not None:
            self.connection.close()


    def create_table(self, query: str) -> None:
        try:
            with self.connection:
                self.connection.execute(query)
                logger.debug(f"Table created {query}")
        except Exception:
            logger.warning("Table create error: {e}")
            raise

    def insert(self, query: str, row: tuple) -> None:
        try:
            with self.connection:
                # logger.info(f'query {query}, row: {row}')
                self.connection.execute(query, row)
        except Exception as e:
            logger.warning(f"Error inserting {row} into database: {e}")
            raise

    def query(self, select: str, condition: str | None = None, groupby: str | None = None, orderby: str | None = None) -> list[tuple]:
        query = select
        if condition:
            query = f"{query} WHERE {condition}"
        if groupby:
            query = f"{query} GROUP BY {groupby}"
        if orderby:
            query = f"{query} ORDER BY {orderby}"
        logger.debug(f"Executing query: {query}")
        try:
            with self.connection:
                rows = self.connection.execute(query).fetchall()
                cnt = len(rows)
                logger.debug(f"Query {query} returned {cnt} rows")
                return rows
        except Exception as e:
            logger.warning(f"Query {query} failed with error {e}")
            raise

    def query_parameterized(self, query: str, params: tuple | None = None) -> list[tuple]:
        """
        Execute a SELECT SQL statement with parameters.
        Returns a list of tuples.
        """
        logger.debug(f"Executing parameterized query: {query} with params: {params}")
        try:
            with self.connection:
                if params:
                    rows = self.connection.execute(query, params).fetchall()
                else:
                    rows = self.connection.execute(query).fetchall()
                cnt = len(rows)
                logger.debug(f"Query {query} returned {cnt} rows")
                return rows
        except Exception as e:
            logger.warning(f"Query {query} failed with error {e}")
            raise

    def execute(self, query: str, params: tuple | None = None) -> sqlite3.Cursor:
        """
        Execute a non-SELECT SQL statement (e.g., INSERT, UPDATE, DELETE).
        Returns the cursor object.
        """
        try:
            with self.connection:
                if params:
                    cur = self.connection.execute(query, params)
                else:
                    cur = self.connection.execute(query)
                logger.debug(f"Executed: {query} with params: {params}")
                return cur
        except Exception as e:
            logger.warning(f"Execution failed for {query} with error {e}")
            raise


    def commit(self) -> None:
        try:
            self.connection.commit()
            logger.info("Database commit successful")
        except Exception as e:
            logger.warning(f"Database commit failed with error {e}")
            raise

    def get_users(self) -> list[str]:
        """
        Get list of all registered usernames across all tables.

        Returns:
            Sorted list of unique usernames
        """
        users: set[str] = set()

        # Query distinct usernames from all tables
        for table_name in ["trades", "dividends", "shares", "deposits"]:
            try:
                rows = self.query(f"SELECT DISTINCT username FROM {table_name}")
                users.update(row[0] for row in rows if row[0])
            except Exception as e:
                logger.warning(f"Failed to query users from {table_name}: {e}")

        return sorted(users)
