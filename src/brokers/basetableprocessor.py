#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import math
from itertools import batched
from typing import Any

import pandas as pd
from tabulate import tabulate

import constants as const
from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class BaseTableProcessor:
    def __init__(self, db: Db, tablename: str) -> None:
        self.db = db
        self.tablename = tablename
        self.debug = False
        self.create_table()

    def set_debug(self, debug: bool) -> None:
        self.debug = debug

    def get_name(self) -> str:
        return self.tablename

    def create_table(self) -> None:
        raise NotImplementedError("Subclasses should implement this method")

    def insert(self) -> None:
        raise NotImplementedError("Subclasses should implement this method")


    def query(self, username: str | None, fields: list | None = None, condition: str | None = None) -> list[tuple]:
        if fields is None:
            fields_str = "*"
        else :
            fields_str = ", ".join(fields)

        select = f"SELECT {fields_str} FROM {self.tablename}"
        filter = None

        if condition is None and username is None:
            filter = None
        if condition is not None and username is None:
            filter = condition
        if condition is None and username is not None:
            filter = f'username = "{username}"'
        elif condition is not None and username is not None:
            filter = f'username = "{username}" AND {condition}'


        logger.debug(f"query select: {select}, condition: {filter}")
        return self.db.query(select=select, condition=filter, orderby="date DESC")

    def query_all(self) -> list[tuple]:
        return self.db.query(select=f"SELECT * FROM {self.tablename}", condition=None, orderby="date DESC")


    def delete(self, username: str, id: int) -> int:
        query = f"DELETE FROM {self.tablename} WHERE username=? and ID=?"
        cur = self.db.execute(query, (username, id))
        count = cur.rowcount
        logger.info(f"Deleted {count} from {self.tablename} for user {username} and id {id}")
        self.db.commit()
        return count

    def delete_all(self, username: str, account: str | None = None) -> int:
        """
        Delete all records for a username, optionally filtered by account.

        Args:
            username: The username to delete records for
            account: Optional account filter. If None, deletes all accounts.

        Returns:
            Number of records deleted
        """
        if account is None:
            # Delete all records for username regardless of account
            query = f"DELETE FROM {self.tablename} WHERE username=?"
            cur = self.db.execute(query, (username,))
            logger.info(f"Deleted {cur.rowcount} from {self.tablename} for user {username} (all accounts)")
        else:
            # Delete only records for specific account
            query = f"DELETE FROM {self.tablename} WHERE username=? AND account=?"
            cur = self.db.execute(query, (username, account))
            logger.info(f"Deleted {cur.rowcount} from {self.tablename} for user {username} and account {account}")

        count = cur.rowcount
        logger.debug(f"query: {query}")
        self.db.commit()
        return count

    def delete_range(self, username: str, start_date: str | None, end_date: str | None, account: str | None = None) -> int:
        """
        Delete records in a date range for a username, optionally filtered by account.

        Args:
            username: The username to delete records for
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            account: Optional account filter. If None, deletes from all accounts.

        Returns:
            Number of records deleted
        """
        logger.debug(f"Deleting from {self.tablename} for user {username} between {start_date} and {end_date}, account={account}")

        # Handle None dates - return 0 if dates are not provided
        if start_date is None or end_date is None:
            logger.warning(f"Cannot delete range with None dates: start={start_date}, end={end_date}")
            return 0

        # Convert datetime objects to strings if needed
        if not isinstance(start_date, str):
            start_date = start_date.strftime("%Y-%m-%d")
        if not isinstance(end_date, str):
            end_date = end_date.strftime("%Y-%m-%d")

        if account is None:
            # Delete all records in date range regardless of account
            query = f"DELETE FROM {self.tablename} WHERE username=? AND date BETWEEN ? AND ?"
            cur = self.db.execute(query, (username, start_date, end_date))
            logger.info(f"Deleted {cur.rowcount} from {self.tablename} for user {username} between {start_date} and {end_date} (all accounts)")
        else:
            # Delete only records for specific account in date range
            query = f"DELETE FROM {self.tablename} WHERE username=? AND date BETWEEN ? AND ? AND account=?"
            cur = self.db.execute(query, (username, start_date, end_date, account))
            logger.info(f"Deleted {cur.rowcount} from {self.tablename} for user {username} between {start_date} and {end_date}, account={account}")

        count = cur.rowcount
        self.db.commit()
        return count


    def styled_df(self, user: str | None, filter: str | None = None) -> pd.DataFrame:
        return self.as_df(user, filter)

    def as_df(self, user: str | None, filter: str | None = None) -> pd.DataFrame:
        logger.debug(f"as_df user: {user}, filter: {filter}")
        results = self.query(user, condition=filter)
        # If no results, return an empty DataFrame with headers
        if not results:
            return pd.DataFrame(columns=self.headers())  # type: ignore[attr-defined]

        df = pd.DataFrame(results, columns=self.headers())  # type: ignore[attr-defined]
        df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
        df["Date"] = df["Date"].dt.strftime("%m/%d/%Y")
        return df

    def as_csv(self, user: str | None, fname: str, filter: str | None = None) -> str:
        df = self.as_df(user, filter)
        # Drop username and guild_id columns for export
        columns_to_drop = ["Username", "guild_id"]
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns])
        df.to_csv(fname, index=False)
        return fname

    def as_str(self, user: str | None, filter: str | None = None) -> str:
        logger.info(f"as_str user: {user}, filter: {filter}")
        df = self.styled_df(user, filter)
        if df.empty:
            return "No records found."

        table_str = tabulate(df.values, headers=self.headers(), stralign="right", floatfmt=".2f")  # type: ignore[attr-defined]
        return table_str

    def as_dict(self, user: str | None, filter: str | None = None, orient: str = "records") -> dict | list:
        """
        Convert table data to dictionary format for JSON serialization.

        Args:
            user: Username to filter by (None for all users)
            filter: Additional SQL filter condition
            orient: Pandas to_dict orientation ('records', 'dict', 'list', 'index')
                   Default 'records' returns list of dicts (one per row)

        Returns:
            Dictionary or list depending on orient parameter
        """
        logger.debug(f"as_dict user: {user}, filter: {filter}, orient: {orient}")
        df = self.as_df(user, filter)
        if df.empty:
            return [] if orient == "records" else {}
        result: dict[Any, Any] | list[Any] = df.to_dict(orient=orient)
        return result

    def my_records_v1(self, user: str, index: int, fields: list[str], aliases: list | None = None, symbol: str | None = None) -> tuple[str, int]:
        if symbol:
            symbol = symbol.upper()
            symbol = f'symbol="{symbol}"'

        if fields is not None:
            logger.info(f"Fields specified: {fields}")

        if aliases is None:
            aliases = fields

        logger.info(f"condition: {symbol}")
        rows=self.query(user, fields=fields, condition=symbol)

        if len(rows) == 0:
            return "No records found.", 0

        # TODO - Refactor this to be more accurate
        single_row = tabulate([], headers=aliases, stralign="right", floatfmt=".2f")
        single_row_size = math.ceil(len(single_row)/2.0)
        row_cnt = math.floor(const.DISCORD_MAX_CHAR_COUNT / single_row_size)
        row_cnt = row_cnt - 5  # Reserve some space for the header and footer

        logger.info(f"single_row size: {single_row_size}")

        batch_list = list(batched(rows, row_cnt))
        cnt = len(batch_list)
        if cnt -1 < index:
            return "No recods found.  Attempting to access records beyond page index.", 0


        header = self.headers()  # type: ignore[attr-defined]
        table_str = tabulate(batch_list[index], headers=aliases, stralign="right", floatfmt=".2f")
        table_size = len(table_str)
        logger.info(f"table size: {table_size}")
        return table_str, cnt

    def my_records(self, user: str, index: int, fields: list[str], aliases: list | None = None, symbol: str | None = None, account: str | None = None) -> tuple[str, int]:
        # Build condition string from symbol and account filters
        conditions = []
        if symbol:
            symbol = symbol.upper()
            conditions.append(f'symbol="{symbol}"')
        if account:
            conditions.append(f'account="{account}"')

        condition = " AND ".join(conditions) if conditions else None

        if fields is not None:
            logger.info(f"Fields specified: {fields}")

        if aliases is None:
            aliases = fields

        logger.info(f"condition: {condition}")
        rows=self.query(user, fields=fields, condition=condition)

        if len(rows) == 0:
            return "No records found.", 0

        header_text_reserve = 200
        # Total number of rows in query
        row_cnt = len(rows) + 2 # Two rows are used by the header
        table_size = len(tabulate(rows, headers=aliases, stralign="right", floatfmt=".2f"))
        logger.info(f"table_size {table_size}")

        row_size = math.ceil(table_size / (row_cnt))
        logger.info(f"row size {row_size}")

        page_cnt = math.ceil(table_size / const.DISCORD_MAX_CHAR_COUNT)

        rows_per_page = math.floor((const.DISCORD_MAX_CHAR_COUNT - header_text_reserve) / row_size)
        logger.info(f"rows_per_page: {rows_per_page}")
        size_check = rows_per_page * row_size + header_text_reserve
        logger.info(f"Estimated size: {size_check}")

        # Reserve space for header rows
        batch_size = rows_per_page - 2
        logger.info(f"batch size: {batch_size}")

        batch_list = list(batched(rows, batch_size))
        cnt = len(batch_list)
        if cnt -1 < index:
            return "No recods found.  Attempting to access records beyond page index.", 0

        header = self.headers()  # type: ignore[attr-defined]
        table_str = tabulate(batch_list[index], headers=aliases, stralign="right", floatfmt=".2f")
        table_size = len(table_str)
        logger.info(f"table size: {table_size}")

        return table_str, cnt
