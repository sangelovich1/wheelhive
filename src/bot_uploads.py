#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""


import glob
import logging
import os
from typing import Any

import constants as const
from bot_upload_identifier import BotUploadIdentifier, BrokerageType
from brokers.fidelity_deposits import FidelityDeposits
from brokers.fidelity_dividends import FidelityDividends
from brokers.fidelity_options import FidelityOptions
from brokers.fidelity_shares import FidelityShares
from brokers.ibkr_dividends import IBKRDividends
from brokers.ibkr_options import IBKROptions
from brokers.ibkr_shares import IBKRShares
from brokers.robinhood_dividends import RobinhoodDividends
from brokers.robinhood_options import RobinhoodOptions
from brokers.robinhood_shares import RobinhoodShares
from brokers.schwab_dividends import SchwabDividends
from brokers.schwab_options import SchwabOptions
from brokers.schwab_shares import SchwabShares
from db import Db
from deposits import Deposits
from dividends import Dividends
from reports.profittreport import ProfitReport
from shares import Shares
from trades import Trades


logger = logging.getLogger(__name__)

class BotUploads:

    def __init__(self, fname: str, format: str, trades: Trades, dividends: Dividends, shares: Shares, deposits: Deposits):
        self.fname = fname
        self.format = format
        self.trades = trades
        self.dividends = dividends
        self.shares = shares
        self.deposits = deposits


    @classmethod
    def formats_supported(cls):

        return [ "fidelity", "robinhood", "schwab", "ibkr" ]

    def process(self, username: str, append=False, guild_id=None, account="default") -> tuple[bool, str]:
        processors: list[Any] = list()
        if self.format == "fidelity":
            processors.append((FidelityOptions(self.fname), self.trades))
            processors.append((FidelityDividends(self.fname), self.dividends))
            processors.append((FidelityShares(self.fname), self.shares))
            processors.append((FidelityDeposits(self.fname), self.deposits))
        elif self.format == "robinhood":
            processors.append((RobinhoodOptions(self.fname), self.trades))
            processors.append((RobinhoodDividends(self.fname), self.dividends))
            processors.append((RobinhoodShares(self.fname), self.shares))
        elif self.format == "schwab":
            processors.append((SchwabOptions(self.fname), self.trades))
            processors.append((SchwabDividends(self.fname), self.dividends))
            processors.append((SchwabShares(self.fname), self.shares))
        elif self.format == "ibkr":
            processors.append((IBKROptions(self.fname), self.trades))
            processors.append((IBKRDividends(self.fname), self.dividends))
            processors.append((IBKRShares(self.fname), self.shares))
        else:
            logger.info(f"Format {self.format} not supported yet")
            return False, f"Format {self.format} not supported yet"


        try:
            logger.info(f"Processing file: {self.fname}")
            logger.info(f"Format: {self.format}, append: {append}, guild_id: {guild_id}, account: {account}")

            response = list()
            response.append(f"Format: {self.format}, account: {account}, append: {append}")

            for processor, handler in processors:
                df, start_date, end_date = processor.process()
                if not df.empty:

                    name = handler.get_name()
                    cname = name.capitalize()
                    response.append(f"Processing {name}")
                    if append == False:
                        cnt_del = handler.delete_range(username, start_date, end_date, account=account)
                        logger.info(f"Deleted {cnt_del} {name} in range: {start_date} to {end_date}, account: {account}")
                        response.append(f" Deleted {cnt_del} {name} in range: {start_date} to {end_date}, account: {account}")

                    # Add username, guild_id, and account to dataframe
                    df.insert(loc=0, column="username", value=username)
                    df.insert(loc=1, column="guild_id", value=guild_id)
                    df.insert(loc=2, column="account", value=account)

                    df = df.sort_index(ascending=False)
                    cnt = len(df)

                    logger.info(f"{cname} processed {cnt}")
                    response.append(f"   {cname} processed {cnt}")

                    # Map DataFrame column names to namedtuple field names expected by insert()
                    # This mapping ensures compatibility between display-friendly column names
                    # and lowercase namedtuple field names used internally

                    # Determine which table we're processing based on handler type
                    table_name = name  # 'trades', 'dividends', 'shares', or 'deposits'

                    if table_name == "trades":
                        # Options/trades: Action→operation, Expiration→expiration_date, etc.
                        column_mapping = {
                            "Action": "operation",
                            "Expiration": "expiration_date",
                            "Strike": "strike_price",
                            "Operation": "option_type",
                            "Price": "premium",
                            "Amount": "total",
                            "Date": "date",
                            "Symbol": "symbol",
                            "Contracts": "contracts",
                        }
                    elif table_name == "shares":
                        # Shares: Action→action, Price→price, etc.
                        column_mapping = {
                            "Action": "action",
                            "Date": "date",
                            "Symbol": "symbol",
                            "Price": "price",
                            "Quantity": "quantity",
                            "Amount": "amount",
                        }
                    elif table_name == "dividends":
                        # Dividends: Date→date, Symbol→symbol, Amount→amount
                        column_mapping = {
                            "Date": "date",
                            "Symbol": "symbol",
                            "Amount": "amount",
                        }
                    elif table_name == "deposits":
                        # Deposits: Action→action, Date→date, Amount→amount
                        column_mapping = {
                            "Action": "action",
                            "Date": "date",
                            "Amount": "amount",
                        }
                    else:
                        column_mapping = {}

                    df.rename(columns=column_mapping, inplace=True)

                    for row in df.itertuples():
                        logger.debug(f"Inserting row: {row.Index}")
                        handler.insert(row)

            response_msg = "\n".join(response)
            return True, response_msg

        except Exception as e:
            logger.info(f"Error processing the file: {e!s}")
            return False, f"Error processing the file: {e!s}"





def main():
    db = Db()
    trades = Trades(db)
    dividends = Dividends(db)
    shares = Shares(db)
    deposits = Deposits(db)
    identifier = BotUploadIdentifier()

    username = "testuser"

    # Find all CSV files in the uploads directory
    csv_files = sorted(glob.glob(os.path.join(const.UPLOADS_DIR, "*.csv")))

    if not csv_files:
        print(f"No CSV files found in {const.UPLOADS_DIR}")
        return

    print(f"Found {len(csv_files)} CSV files in {const.UPLOADS_DIR}")
    print("=" * 80)

    for fname in csv_files:
        print("\n" + "-" * 80)
        print(f"Importing: {fname}")

        # Automatically detect brokerage format
        try:
            brokerage_type, confidence = identifier.identify(fname)
            format = brokerage_type.value

            print(f"Detected format: {format} (confidence: {confidence:.1%})")

            if brokerage_type == BrokerageType.UNKNOWN:
                print(f"WARNING: Unable to identify format for {fname}")
                continue

            print("Cleanup existing data")
            trades.delete_all(username)
            dividends.delete_all(username)
            shares.delete_all(username)
            deposits.delete_all(username)

            botUploads = BotUploads(fname, format, trades, dividends, shares, deposits)
            status, msg = botUploads.process(username)
            print(f"Status: {status}")
            print(f"Msg: {msg}")
            print("Generating report")

            report = ProfitReport(db, username)
            report.report()

        except Exception as e:
            print(f"ERROR processing {fname}: {e!s}")




if __name__ == "__main__":
    main()





