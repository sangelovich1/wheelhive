"""
Tickers collection

Manages valid ticker symbols for validation and extraction from messages.
Populated from S&P 500 and DOW Jones Industrial Average.

Performance Note: If ticker validation becomes a bottleneck, we can cache the
ticker set in memory for faster lookups (e.g., self._cache = set() loaded on init).
Currently using database lookups with indexes which should be fast enough.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any

import pandas as pd
import requests

from brokers.basetableprocessor import BaseTableProcessor
from db import Db
from ticker import Ticker


logger = logging.getLogger(__name__)


class Tickers(BaseTableProcessor):
    """Collection of valid ticker symbols"""

    def __init__(self, db: Db) -> None:
        super().__init__(db, "valid_tickers")
        self.create_table()

    def create_table(self) -> None:
        """Create valid_tickers table if it doesn't exist"""
        query = """
        CREATE TABLE IF NOT EXISTS valid_tickers (
            ticker TEXT PRIMARY KEY,
            company_name TEXT,
            exchange TEXT,
            sector TEXT,
            is_active BOOLEAN DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db.create_table(query)

        # Create index for fast lookups
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_ticker_active ON valid_tickers(ticker, is_active)")

    @classmethod
    def headers(cls) -> list:
        return ["Ticker", "Company", "Exchange", "Sector", "Active", "Added"]

    def insert(self, ticker: Ticker) -> None:  # type: ignore[override]
        """
        Insert a ticker into the database

        Args:
            ticker: Ticker object to insert
        """
        query = """
        INSERT OR REPLACE INTO valid_tickers (ticker, company_name, exchange, sector, is_active)
        VALUES (?, ?, ?, ?, ?)
        """
        self.db.execute(query, ticker.to_tuple())
        logger.debug(f"Inserted ticker: {ticker.ticker}")

    def insert_bulk(self, tickers: list[Ticker]) -> int:
        """
        Insert multiple tickers efficiently

        Args:
            tickers: List of Ticker objects

        Returns:
            Number of tickers inserted
        """
        query = """
        INSERT OR REPLACE INTO valid_tickers (ticker, company_name, exchange, sector, is_active)
        VALUES (?, ?, ?, ?, ?)
        """

        data = [t.to_tuple() for t in tickers]
        cursor = self.db.connection.cursor()

        try:
            cursor.executemany(query, data)
            self.db.connection.commit()
            logger.info(f"Bulk inserted {len(tickers)} tickers")
            return len(tickers)
        except Exception as e:
            logger.error(f"Error bulk inserting tickers: {e}", exc_info=True)
            self.db.connection.rollback()
            return 0

    def is_valid_ticker(self, ticker: str) -> bool:
        """
        Check if a ticker is valid and active

        Args:
            ticker: Ticker symbol to validate

        Returns:
            True if ticker exists and is active
        """
        result = self.db.query_parameterized(
            "SELECT 1 FROM valid_tickers WHERE ticker = ? AND is_active = 1",
            (ticker.upper(),)
        )
        return len(result) > 0

    def get_ticker(self, ticker: str) -> Ticker | None:
        """
        Get ticker details

        Args:
            ticker: Ticker symbol

        Returns:
            Ticker object if found, None otherwise
        """
        result = self.db.query_parameterized(
            "SELECT ticker, company_name, exchange, sector, is_active FROM valid_tickers WHERE ticker = ?",
            (ticker.upper(),)
        )

        if not result:
            return None

        row = result[0]
        return Ticker(
            ticker=row[0],
            company_name=row[1],
            exchange=row[2],
            sector=row[3],
            is_active=bool(row[4])
        )

    def search(self, query: str, limit: int = 10) -> list[Ticker]:
        """
        Search tickers by symbol or company name

        Args:
            query: Search string
            limit: Maximum results

        Returns:
            List of matching Ticker objects
        """
        sql = """
        SELECT ticker, company_name, exchange, sector, is_active
        FROM valid_tickers
        WHERE ticker LIKE ? OR company_name LIKE ?
        ORDER BY ticker
        LIMIT ?
        """

        search_term = f"%{query.upper()}%"
        results = self.db.query_parameterized(sql, (search_term, search_term, limit))

        return [
            Ticker(
                ticker=row[0],
                company_name=row[1],
                exchange=row[2],
                sector=row[3],
                is_active=bool(row[4])
            )
            for row in results
        ]

    def count(self, active_only: bool = True) -> int:
        """
        Count tickers in database

        Args:
            active_only: Only count active tickers

        Returns:
            Count of tickers
        """
        condition = "is_active = 1" if active_only else None
        result = self.db.query(
            "SELECT COUNT(*) FROM valid_tickers",
            condition
        )
        return result[0][0] if result else 0

    def populate_from_wikipedia(self) -> dict[str, Any]:
        """
        Populate tickers from Wikipedia (S&P 500 + DOW 30)

        Returns:
            Dictionary with statistics
        """
        stats: dict[str, Any] = {"sp500": 0, "dow": 0, "total": 0, "errors": []}

        # Set User-Agent header to avoid Wikipedia 403 errors
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Fetch S&P 500
            logger.info("Fetching S&P 500 tickers from Wikipedia...")
            sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            response = requests.get(sp500_url, headers=headers)
            response.raise_for_status()
            sp500_df = pd.read_html(response.text)[0]

            sp500_tickers = []
            for _, row in sp500_df.iterrows():
                ticker = Ticker(
                    ticker=row["Symbol"],
                    company_name=row["Security"],
                    exchange="S&P500",
                    sector=row.get("GICS Sector", None),
                    is_active=True
                )
                sp500_tickers.append(ticker)

            stats["sp500"] = self.insert_bulk(sp500_tickers)
            logger.info(f"Inserted {stats['sp500']} S&P 500 tickers")

        except Exception as e:
            error_msg = f"Error fetching S&P 500: {e}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)

        try:
            # Fetch DOW 30
            logger.info("Fetching DOW 30 tickers from Wikipedia...")
            dow_url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
            response = requests.get(dow_url, headers=headers)
            response.raise_for_status()
            dow_tables = pd.read_html(response.text)

            # Find the table with ticker symbols - iterate through tables to find the right one
            dow_df = None
            for table in dow_tables:
                # Look for table with 'Company' and either 'Symbol' or 'Ticker' column
                if "Company" in table.columns:
                    if "Symbol" in table.columns or "Ticker" in table.columns:
                        dow_df = table
                        break

            if dow_df is None:
                raise ValueError("Could not find DOW tickers table in Wikipedia page")

            # Determine which column has the ticker symbol
            ticker_col = "Symbol" if "Symbol" in dow_df.columns else "Ticker"

            dow_tickers = []
            for _, row in dow_df.iterrows():
                ticker = Ticker(
                    ticker=row[ticker_col],
                    company_name=row["Company"],
                    exchange="DOW",
                    sector=row.get("Industry", None),
                    is_active=True
                )
                dow_tickers.append(ticker)

            stats["dow"] = self.insert_bulk(dow_tickers)
            logger.info(f"Inserted {stats['dow']} DOW tickers")

        except Exception as e:
            error_msg = f"Error fetching DOW: {e}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)

        stats["total"] = self.count(active_only=True)
        return stats

    def delete(self, ticker: str) -> int:  # type: ignore[override]
        """
        Soft delete a ticker by setting is_active to 0

        Args:
            ticker: Ticker symbol to delete

        Returns:
            Number of rows affected (0 or 1)
        """
        query = "UPDATE valid_tickers SET is_active = 0 WHERE ticker = ?"
        cursor = self.db.connection.cursor()
        cursor.execute(query, (ticker.upper(),))
        self.db.connection.commit()
        count = cursor.rowcount

        if count > 0:
            logger.info(f"Soft deleted ticker: {ticker}")
        else:
            logger.warning(f"Ticker not found: {ticker}")

        return count

    def get_by_exchange(self, exchange: str, limit: int | None = None) -> list[Ticker]:
        """
        Get tickers by exchange.

        Args:
            exchange: Exchange name (e.g., 'NASDAQ', 'NYSE', 'COMMUNITY-AUTO')
            limit: Maximum number of results (optional)

        Returns:
            List of Ticker objects
        """
        if limit:
            query = """
                SELECT ticker, company_name, exchange, sector, is_active
                FROM valid_tickers
                WHERE exchange = ?
                ORDER BY added_at DESC
                LIMIT ?
            """
            results = self.db.query_parameterized(query, (exchange, limit))
        else:
            query = """
                SELECT ticker, company_name, exchange, sector, is_active
                FROM valid_tickers
                WHERE exchange = ?
                ORDER BY added_at DESC
            """
            results = self.db.query_parameterized(query, (exchange,))

        tickers = []
        for row in results:
            ticker = Ticker(
                ticker=row[0],
                company_name=row[1],
                exchange=row[2],
                sector=row[3],
                is_active=bool(row[4])
            )
            tickers.append(ticker)

        return tickers

    def delete_by_exchange(self, exchange: str) -> int:
        """
        Hard delete tickers by exchange (PERMANENT).

        Use this to clean up auto-added garbage tickers.

        Args:
            exchange: Exchange name to delete (e.g., 'COMMUNITY-AUTO')

        Returns:
            Number of rows deleted
        """
        query = "DELETE FROM valid_tickers WHERE exchange = ?"
        cursor = self.db.connection.cursor()
        cursor.execute(query, (exchange,))
        self.db.connection.commit()
        count = cursor.rowcount

        if count > 0:
            logger.info(f"Hard deleted {count} tickers from exchange: {exchange}")
        else:
            logger.warning(f"No tickers found for exchange: {exchange}")

        return count

    def as_df(self, active_only: bool = True, limit: int | None = None) -> pd.DataFrame:  # type: ignore[override]
        """
        Get tickers as DataFrame

        Args:
            active_only: Only include active tickers
            limit: Optional row limit

        Returns:
            DataFrame of tickers
        """
        condition = "is_active = 1" if active_only else None
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = "SELECT ticker, company_name, exchange, sector, is_active, added_at FROM valid_tickers"
        if condition:
            query += f" WHERE {condition}"
        query += f" ORDER BY ticker {limit_clause}"

        results = self.db.query(query, None)

        if not results:
            return pd.DataFrame(columns=self.headers())

        df = pd.DataFrame(results, columns=self.headers())
        return df
