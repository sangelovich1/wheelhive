#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from collections import namedtuple
from typing import Any

import util
from baseparser import BaseParser


class Dividend(BaseParser):

    def __init__(self, username: str, d: str, raw_string: str) -> None:
        self.username = username
        self.date = util.to_db_date(d)
        self.raw_string = raw_string
        self.classifier: str = ""
        self.symbol: str = ""
        self.amount: float = 0.0

    def parse(self) -> None:
        parts = self.raw_string.split()
        self.classifier = parts[0].lower().capitalize()
        self.symbol = parts[1]
        self.amount = util.currency_to_float(parts[2])
        self.amount = abs(self.amount)

    def is_valid(self) -> bool:
        if self.classifier != "Dividend":
            return False
        if self.symbol is None:
            return False
        if len(self.symbol) == 0:
            return False
        if self.amount <= 0:
            return False

        return True

    def as_named_tuple(self) -> Any:

        DividendTuple = namedtuple("DividendTuple",
            [ "username",
             "guild_id",
             "account",
             "date",
             "symbol",
             "amount"])

        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(self, "guild_id", None)
        account = getattr(self, "account", "default")

        tt = DividendTuple(self.username, guild_id, account, self.date, self.symbol, self.amount)


        return tt


