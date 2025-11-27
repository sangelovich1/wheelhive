#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from collections import namedtuple
from datetime import datetime

# Local application imports
from baseparser import BaseParser


# Get a logger instance
logger = logging.getLogger(__name__)


class Trade(BaseParser):
    def __init__(self, username: str, d: str, raw_trade_string: str):
        self.username = username
        self.date = d
        self.raw_trade_string = raw_trade_string
        self.operation: str = ""
        self.contracts: int = 0
        self.symbol: str = ""
        self.expiration_date: str = ""
        self.strike_price: float = 0.0
        self.option_type: str = ""
        self.premium: float = 0.0
        self.total: float = 0.0

        self.partial_result = False

    @classmethod
    def headers(cls):
        return ("ID", "Date", "Op", "Con", "Sym", "Exp", "Str", "T", "Pre", "Total")
    def as_tuple(self):
        return (self.username, self.date, self.raw_trade_string,
                self.operation, self.contracts, self.symbol,
                self.expiration_date, self.strike_price, self.option_type,
                self.premium, self.total)

    def as_named_tuple(self):

        TradeTuple = namedtuple("TradeTuple",
            [ "username",
             "guild_id",
             "account",
             "date",
             "operation",
             "contracts",
             "symbol",
             "expiration_date",
             "strike_price",
             "option_type",
             "premium",
             "total"])

        # Extract guild_id and account if present, otherwise use defaults
        guild_id = getattr(self, "guild_id", None)
        account = getattr(self, "account", "default")

        tt = TradeTuple(self.username, guild_id, account, self.date, self.operation,
                        self.contracts, self.symbol, self.expiration_date,
                        self.strike_price, self.option_type, self.premium, self.total)


        return tt


    def parse(self):
        try:
            # Split the trade string into parts based on spaces
            raw_trade_string = self.raw_trade_string.replace("@", "")
            raw_trade_string = raw_trade_string.replace("at", "")
            parts = raw_trade_string.upper().split()

            # #Use an ISO formatted date
            # self.date = datetime.now().strftime("%Y-%m-%d")

            # Parse operation
            self.operation = parts[0]
            logger.debug(f"operation: {self.operation}")
            if self.operation not in ["STO", "BTC", "BTO", "STC"]:
                self.partial_result = True
                return

            # Handle contracts
            contracts_str = parts[1]
            logger.debug(f"contracts_str: {contracts_str}")
            contracts_str = contracts_str.replace("X", "")
            self.contracts = int(contracts_str)
            logger.debug(f"contracts: {self.contracts}")

            # Parse symbol
            index = self.find_symbol(parts)
            self.symbol = parts[index]
            logger.debug(f"symbol: {self.symbol}")
            #Check and see if the symbol is valid

            # Parse expiration date
            index = self.find_date(parts)
            logger.debug(f"parts: {parts}")
            self.expiration_date = Trade.format_date(parts[index])
            logger.debug(f"expiration_date: {self.expiration_date}")

            # Parse strike price
            index = self.find_strike(parts)
            strike_price_and_type = parts[index]
            strike_price_and_type = strike_price_and_type.replace("$", "")
            self.strike_price = float(strike_price_and_type[:-1])
            logger.debug(f"strike_price: {self.strike_price}")

            # Parse option type
            self.option_type = strike_price_and_type[-1]
            logger.debug(f"option_type: {self.option_type}")


            # Handle premium
            index = self.find_premium(parts)
            premium_str = parts[index]
            premium_str = premium_str.replace("$", "")
            self.premium = float(premium_str)
            logger.debug(f"premium: {self.premium}")

            self.total = self.contracts * (self.premium * 100)
            if self.operation == "BTC" or self.operation == "BTO":
                self.total = self.total * -1

        except (ValueError, IndexError):
            self.partial_result = True

    def find_symbol(self, parts) -> int:
        cnt = len(parts)
        for i in range(1, cnt):
            if parts[i].isalpha():
                return i
        return -1


    def find_date(self, parts) -> int:
        cnt = len(parts)
        for i in range(cnt):
            if "/" in parts[i]:
                return i
        return -1

    def find_strike(self, parts) -> int:
        cnt = len(parts)
        for i in range(1, cnt):
            if parts[i].endswith("C"):
                return i
            if parts[i].endswith("P"):
                return i
        return -1

    def find_premium(self, parts) -> int:
        cnt = len(parts)
        for i in range(5, cnt):
            if "$" in parts[i]:
                return i
            if parts[i].isnumeric():
                return i
        return -1


    # def format_date(self, d: str) -> str:
    #     parts = d.split('/')
    #     new_parts = list()
    #     for part in parts:
    #         ip = int(part)
    #         sp = f'{ip:02}'
    #         new_parts.append(sp)
    #     separator = "/"
    #     new_date = separator.join(new_parts)
    #     return new_date


    # Take a date in the format m/d or m/d/yyyy and convert it to an ISO format

    @classmethod
    def format_date(cls, d: str) -> str:
        year = datetime.now().strftime("%Y")
        if d.count("/") == 1:
            d = f"{d}/{year}"
        dt = datetime.strptime(d, "%m/%d/%Y")
        str_dt = dt.strftime("%Y-%m-%d")
        return str_dt


    def __str__(self):
        fields = [
            f"Username: {self.username}",
            f"Raw Trade String: {self.raw_trade_string}",
            f"Operation: {self.operation}",
            f"Contracts: {self.contracts}",
            f"Symbol: {self.symbol}",
            f"Expiration Date: {self.expiration_date}",
            f"Strike Price: {self.strike_price}",
            f"Option Type: {self.option_type}",
            f"Premium: ${self.premium}" if self.premium is not None else "Premium: None",
            f"Partial Result: {self.partial_result}"
        ]
        return ", ".join(fields)

    def is_valid(self) -> bool:
        if self.partial_result:
            return False
        # Check if all required fields are set
        if self.username is None or self.operation is None or self.contracts is None or self.symbol is None or \
           self.expiration_date is None or self.strike_price is None or \
           self.option_type is None or self.premium is None:
            return False
        # Ensure that the operation is valid
        if self.operation not in ["STO", "BTC", "BTO", "STC"]:
            return False
        # Ensure that the strike price and premium are valid numbers
        if not isinstance(self.strike_price, (int, float)) or not isinstance(self.premium, (int, float)):
            return False
        # Ensure that the contracts is a positive integer
        if not isinstance(self.contracts, int) or self.contracts <= 0:
            return False
        # Ensure that the option type is either 'C' or 'P'
        if self.option_type not in ["C", "P"]:
            return False
        # If all checks passed, the trade is valid
        logger.info(f"Trade is valid: {self}")
        return True

def main():
    print("main")

if __name__ == "__main__":
    main()
