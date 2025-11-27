#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from collections import namedtuple
from typing import Any

import util
from baseparser import BaseParser


# Get a logger instance
logger = logging.getLogger(__name__)

class Deposit(BaseParser):

    def __init__(self, username: str, d: str, raw_string: str) -> None:
        self.username = username
        self.date = util.to_db_date(d)
        self.raw_string = raw_string
        self.classifier: str = ""
        self.action: str = ""
        self.amount = 0.0

    def parse(self) -> None:
        parts = self.raw_string.split()
        self.classifier = parts[0].lower()
        if self.classifier.startswith("dep"):
            self.action = "Deposit"
        elif self.classifier.startswith("wit"):
            self.action = "Withdrawal"


        self.amount = util.currency_to_float(parts[1])
        if self.action == "Withdrawal":
            if self.amount > 0: self.amount = self.amount * -1.0

    def is_valid(self) -> bool:
        if self.classifier == "deposit":
            logger.debug("Deposit")
        elif self.classifier == "withdrawal":
            logger.debug("Withdrawal")
        else:
            return False
        if self.amount == 0:
            return False

        return True

    def as_named_tuple(self) -> Any:

        DepositTuple = namedtuple("DepositTuple",
            [ "username",
             "guild_id",
             "account",
             "action",
             "date",
             "amount"])

        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(self, "guild_id", None)
        account = getattr(self, "account", "default")

        tt = DepositTuple(self.username, guild_id, account, self.action, self.date, self.amount)

        return tt

