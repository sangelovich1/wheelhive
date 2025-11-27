"""
Test Data Factory

Utility class for creating test data for CLI and integration tests.
Uses the proper insert methods from Trades, Dividends, Shares, and Deposits classes.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from collections import namedtuple
from datetime import datetime, timedelta
from typing import Optional
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db import Db
from trades import Trades
from dividends import Dividends
from shares import Shares
from deposits import Deposits


# Define namedtuples matching the expected insert formats
NewTrade = namedtuple('NewTrade', [
    'username', 'date', 'raw_trade_string', 'operation', 'contracts',
    'symbol', 'expiration_date', 'strike_price', 'option_type', 'premium', 'total',
    'guild_id', 'account'
])

NewDividend = namedtuple('NewDividend', [
    'username', 'date', 'symbol', 'amount', 'guild_id', 'account'
])

NewShare = namedtuple('NewShare', [
    'username', 'date', 'action', 'symbol', 'price', 'quantity', 'amount',
    'guild_id', 'account'
])

NewDeposit = namedtuple('NewDeposit', [
    'username', 'date', 'amount', 'action', 'guild_id', 'account'
])


class TestDataFactory:
    """Factory for creating test data in the database"""

    def __init__(self, db: Db, username: str = "testuser", guild_id: int = 999888777, account: str = "test_account"):
        """
        Initialize test data factory

        Args:
            db: Database instance
            username: Default username for test data
            guild_id: Default guild ID for test data
            account: Default account for test data
        """
        self.db = db
        self.username = username
        self.guild_id = guild_id
        self.account = account

        self.trades = Trades(db)
        self.dividends = Dividends(db)
        self.shares = Shares(db)
        self.deposits = Deposits(db)

    def create_trade(
        self,
        symbol: str = "AAPL",
        operation: str = "STO",
        contracts: int = 1,
        strike: float = 150.0,
        option_type: str = "P",
        premium: float = 1.50,
        date: Optional[str] = None,
        expiration_days: int = 30,
        username: Optional[str] = None,
        guild_id: Optional[int] = None,
        account: Optional[str] = None
    ) -> NewTrade:
        """
        Create and insert a test trade

        Args:
            symbol: Stock symbol
            operation: Trade operation (STO, BTC, BTO, STC)
            contracts: Number of contracts
            strike: Strike price
            option_type: Option type (P or C)
            premium: Premium per contract
            date: Trade date (defaults to today)
            expiration_days: Days until expiration
            username: Override default username
            guild_id: Override default guild_id
            account: Override default account

        Returns:
            NewTrade namedtuple
        """
        username = username or self.username
        guild_id = guild_id or self.guild_id
        account = account or self.account
        date = date or datetime.now().strftime('%Y-%m-%d')

        exp_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=expiration_days)).strftime('%Y-%m-%d')
        total = premium * contracts * 100  # Options are in 100-share lots

        raw_trade = f"{operation} {contracts}x {symbol} {exp_date} {strike}{option_type} @ {premium}"

        trade = NewTrade(
            username=username,
            date=date,
            raw_trade_string=raw_trade,
            operation=operation,
            contracts=contracts,
            symbol=symbol,
            expiration_date=exp_date,
            strike_price=strike,
            option_type=option_type,
            premium=premium,
            total=total,
            guild_id=guild_id,
            account=account
        )

        self.trades.insert(trade)
        return trade

    def create_dividend(
        self,
        symbol: str = "SPY",
        amount: float = 25.50,
        date: Optional[str] = None,
        username: Optional[str] = None,
        guild_id: Optional[int] = None,
        account: Optional[str] = None
    ) -> NewDividend:
        """
        Create and insert a test dividend

        Args:
            symbol: Stock symbol
            amount: Dividend amount
            date: Dividend date (defaults to today)
            username: Override default username
            guild_id: Override default guild_id
            account: Override default account

        Returns:
            NewDividend namedtuple
        """
        username = username or self.username
        guild_id = guild_id or self.guild_id
        account = account or self.account
        date = date or datetime.now().strftime('%Y-%m-%d')

        dividend = NewDividend(
            username=username,
            date=date,
            symbol=symbol,
            amount=amount,
            guild_id=guild_id,
            account=account
        )

        self.dividends.insert(dividend)
        return dividend

    def create_share(
        self,
        symbol: str = "TSLA",
        action: str = "BUY",
        price: float = 250.00,
        quantity: int = 10,
        date: Optional[str] = None,
        username: Optional[str] = None,
        guild_id: Optional[int] = None,
        account: Optional[str] = None
    ) -> NewShare:
        """
        Create and insert a test share transaction

        Args:
            symbol: Stock symbol
            action: Action (BUY or SELL)
            price: Price per share
            quantity: Number of shares
            date: Transaction date (defaults to today)
            username: Override default username
            guild_id: Override default guild_id
            account: Override default account

        Returns:
            NewShare namedtuple
        """
        username = username or self.username
        guild_id = guild_id or self.guild_id
        account = account or self.account
        date = date or datetime.now().strftime('%Y-%m-%d')

        amount = price * quantity

        share = NewShare(
            username=username,
            date=date,
            action=action,
            symbol=symbol,
            price=price,
            quantity=quantity,
            amount=amount,
            guild_id=guild_id,
            account=account
        )

        self.shares.insert(share)
        return share

    def create_deposit(
        self,
        amount: float = 10000.00,
        deposit_type: str = "DEPOSIT",
        date: Optional[str] = None,
        username: Optional[str] = None,
        guild_id: Optional[int] = None,
        account: Optional[str] = None
    ) -> NewDeposit:
        """
        Create and insert a test deposit

        Args:
            amount: Deposit amount
            deposit_type: Type (DEPOSIT or WITHDRAWAL)
            date: Deposit date (defaults to today)
            username: Override default username
            guild_id: Override default guild_id
            account: Override default account

        Returns:
            NewDeposit namedtuple
        """
        username = username or self.username
        guild_id = guild_id or self.guild_id
        account = account or self.account
        date = date or datetime.now().strftime('%Y-%m-%d')

        deposit = NewDeposit(
            username=username,
            date=date,
            amount=amount,
            action=deposit_type,
            guild_id=guild_id,
            account=account
        )

        self.deposits.insert(deposit)
        return deposit

    def create_sample_portfolio(self, num_trades: int = 5, num_dividends: int = 2,
                                num_shares: int = 3, num_deposits: int = 1):
        """
        Create a sample portfolio with multiple transaction types

        Args:
            num_trades: Number of option trades to create
            num_dividends: Number of dividends to create
            num_shares: Number of share transactions to create
            num_deposits: Number of deposits to create
        """
        symbols = ["AAPL", "TSLA", "SPY", "QQQ", "MSTU", "NVDA", "MSFT"]

        # Create trades
        for i in range(num_trades):
            symbol = symbols[i % len(symbols)]
            operation = "STO" if i % 2 == 0 else "BTC"
            date = (datetime.now() - timedelta(days=num_trades - i)).strftime('%Y-%m-%d')
            self.create_trade(
                symbol=symbol,
                operation=operation,
                contracts=1 + (i % 3),
                strike=100.0 + (i * 10),
                date=date
            )

        # Create dividends
        for i in range(num_dividends):
            symbol = symbols[i % len(symbols)]
            date = (datetime.now() - timedelta(days=num_dividends - i)).strftime('%Y-%m-%d')
            self.create_dividend(
                symbol=symbol,
                amount=20.0 + (i * 5),
                date=date
            )

        # Create share transactions
        for i in range(num_shares):
            symbol = symbols[i % len(symbols)]
            action = "BUY" if i % 2 == 0 else "SELL"
            date = (datetime.now() - timedelta(days=num_shares - i)).strftime('%Y-%m-%d')
            self.create_share(
                symbol=symbol,
                action=action,
                price=100.0 + (i * 20),
                quantity=10 + (i * 5),
                date=date
            )

        # Create deposits
        for i in range(num_deposits):
            deposit_type = "DEPOSIT" if i % 2 == 0 else "WITHDRAWAL"
            date = (datetime.now() - timedelta(days=num_deposits - i)).strftime('%Y-%m-%d')
            self.create_deposit(
                amount=5000.0 + (i * 1000),
                deposit_type=deposit_type,
                date=date
            )
