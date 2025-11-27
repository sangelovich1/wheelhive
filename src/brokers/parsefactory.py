#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import constants as const
import util
from baseparser import BaseParser
from db import Db
from deposit import Deposit
from deposits import Deposits
from dividend import Dividend
from dividends import Dividends
from share import Share
from shares import Shares
from trade import Trade
from trades import Trades


# Module-level logger
logger = logging.getLogger(__name__)

class ParseFactory:
    def __init__(self, username: str, date: str, trades: Trades, dividends: Dividends, deposits: Deposits, shares: Shares, guild_id: int | None = None, account: str = "default") -> None:
        self.username = username
        self.date = util.to_db_date(date)
        self.trades = trades
        self.dividends = dividends
        self.deposits = deposits
        self.shares = shares
        self.guild_id = guild_id
        self.account = account

    def factory(self, input: str) -> tuple[BaseParser | None, object | None]:
        obj: BaseParser | None = None
        impl: object | None = None

        if input.upper().startswith("STO") or input.upper().startswith("BTC") or input.upper().startswith("BTO") or input.upper().startswith("STC"):
            obj = Trade(self.username, self.date, input)
            impl = self.trades
        elif input.upper().startswith("DIV"):
            obj = Dividend(self.username, self.date, input)
            impl = self.dividends
        elif input.upper().startswith("BUY") or input.upper().startswith("SEL"):
            obj = Share(self.username, self.date, input)
            impl = self.shares
        elif input.upper().startswith("DEP") or input.upper().startswith("WIT"):
            obj = Deposit(self.username, self.date, input)
            impl = self.deposits
        else:
            logger.warning(f"Unable to classify string {input}")

        # Set guild_id and account on the parser object if it was created
        if obj is not None:
            obj.guild_id = self.guild_id  # type: ignore[attr-defined]
            obj.account = self.account  # type: ignore[attr-defined]

        return obj, impl


def main() -> None:

    db = Db()
    trades = Trades(db)
    dividends = Dividends(db)
    deposits = Deposits(db)
    shares = Shares(db)

    sp = ParseFactory("testuser", "7/18/2025", trades, dividends, deposits, shares)

    for trade_str in const.TEST_TRADES:
        parser, impl = sp.factory(trade_str)
        if parser is None or impl is None:
            logger.warning(f"Failed to parse: {trade_str}")
            continue
        parser.parse()
        status = parser.is_valid()
        nt = parser.as_named_tuple()
        print(f"{trade_str} is valid: {status}, nt: {nt}")
        impl.insert(nt)  # type: ignore[attr-defined]




if __name__ == "__main__":
    main()
