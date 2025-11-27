#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from collections import namedtuple
from typing import Any

import util
from baseparser import BaseParser


class Share(BaseParser):

    def __init__(self, username: str, d: str, raw_string: str) -> None:
        self.username = username
        self.raw_string = raw_string
        self.classifier: str = ""
        self.date = util.to_db_date(d)
        self.action: str = ""
        self.symbol: str = ""
        self.price = 0.0
        self.quantity = 0.0

    def parse(self) -> None:
        # Buy 300 shares MSTU @ 10

        # Remove qualifier
        raw_string = self.raw_string.replace("shares", "")
        raw_string = raw_string.replace("at", "")
        raw_string = raw_string.replace("@", "")

        parts = raw_string.split()
        self.classifier = parts[0].lower()
        if self.classifier == "buy" or self.classifier == "sell":
            self.action = self.classifier.capitalize()

        # Extract shares
        self.quantity = util.currency_to_float(parts[1])
        self.quantity = abs(self.quantity)

        # Extract symbol
        self.symbol = parts[2]

        # Extract share price
        self.price = util.currency_to_float(parts[3])
        self.price = abs(self.price)

        self.amount = self.quantity * self.price
        if self.classifier == "sell":
            # If sell quantity is negative, amount should be positive
            self.quantity = -self.quantity
            self.amount = abs(self.amount)
        else:
            self.amount = -abs(self.amount)





    def is_valid(self) -> bool:
        if self.action != "Buy" and self.action != "Sell":
            return False
        if self.symbol is None:
            return False
        if len(self.symbol) == 0:
            return False
        if self.price <= 0:
            return False
        if self.quantity == 0:
            return False
        if self.classifier == "buy" and self.quantity <= 0:
            return False
        if self.classifier == "buy" and self.amount >= 0:
            return False
        if self.classifier == "sell" and self.quantity >= 0:
            return False
        if self.classifier == "sell" and self.amount <= 0:
            return False

        return True

    def as_named_tuple(self) -> Any:

        ShareTuple = namedtuple("ShareTuple",
            [ "username",
             "guild_id",
             "account",
             "action",
             "date",
             "symbol",
             "price",
             "quantity",
             "amount"
             ])

        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(self, "guild_id", None)
        account = getattr(self, "account", "default")

        tt = ShareTuple(self.username, guild_id, account, self.action, self.date, self.symbol, self.price, self.quantity, self.amount)


        return tt
