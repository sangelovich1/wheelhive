#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import constants as const
import util
from deposits import Deposits
from dividends import Dividends
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)

class BotDownloads:

    def __init__(self, trades: Trades, dividends: Dividends, shares: Shares, deposits: Deposits):
        self.trades = trades
        self.dividends = dividends
        self.shares = shares
        self.deposits = deposits

    def process(self, username: str, account: str | None = None) -> str:
        # Build filter condition if account specified
        filter_condition = None
        if account:
            filter_condition = f'account="{account}"'

        # Generate CSV files with account filtering
        self.trades.as_csv(username, f"{const.DOWNLOADS_DIR}/{username}_trades.csv", filter=filter_condition)
        self.dividends.as_csv(username, f"{const.DOWNLOADS_DIR}/{username}_dividends.csv", filter=filter_condition)
        self.shares.as_csv(username, f"{const.DOWNLOADS_DIR}/{username}_shares.csv", filter=filter_condition)
        self.deposits.as_csv(username, f"{const.DOWNLOADS_DIR}/{username}_deposits.csv", filter=filter_condition)

        # Include account in zip filename if specified
        zip_suffix = f"_{account}" if account else ""
        zip_filename = f"{const.DOWNLOADS_DIR}/{username}{zip_suffix}.zip"

        # Define the list of files to include in the archive
        files = [f"{const.DOWNLOADS_DIR}/{username}_trades.csv",
                 f"{const.DOWNLOADS_DIR}/{username}_dividends.csv",
                 f"{const.DOWNLOADS_DIR}/{username}_shares.csv",
                 f"{const.DOWNLOADS_DIR}/{username}_deposits.csv"]

        # Create the zip archive
        util.create_zip_archive(zip_filename, files)
        return zip_filename

