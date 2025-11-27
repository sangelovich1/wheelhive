"""
CLI Module

Modular command-line interface for the Options Bot using Click.
Each command group is organized into its own module for maintainability.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Import command groups here as they're created
from cli.admin import admin
from cli.analytics import analytics
from cli.brokerage import brokerage
from cli.channels import channels
from cli.llm import llm
from cli.messages import messages
from cli.reports import reports
from cli.scanner import scanner
from cli.tickers import tickers
from cli.tx import tx
from cli.watchlist import watchlist


__all__ = ["admin", "analytics", "brokerage", "channels", "llm", "messages", "reports", "scanner", "tickers", "tx", "watchlist"]
