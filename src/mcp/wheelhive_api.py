#!/usr/bin/env python3
"""
MCP Server for Options Trading Bot

Provides Model Context Protocol access to:
- Options trading data from trades.db database
- Real-time market data (quotes, news, options chains)
- Historical market data (OHLCV prices)
- Fundamental data (financials, dividends, holders, analyst recommendations)
- Community knowledge and sentiment analysis
- Technical analysis and trading tools

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.

TODO: Review JSON data fields in all ESSENTIAL_TOOLS for LLM consumption
----------------------------------------------------------------------
Audit which fields are actually needed by LLMs vs debugging metadata.
Consider removing fields that clutter context without adding value:
  - Internal IDs (message_id, user_id, etc.) - unless needed for correlation
  - Confidence scores - may not be useful for LLM decision making
  - Extraction metadata (extraction_source) - debugging info
  - Timestamps with microsecond precision - date only may suffice

Tools to review (from constants.ESSENTIAL_TOOLS):
  [✓] get_market_news - has JSON data field
  [✓] get_community_messages - has JSON data field
  [✓] get_community_trades - has JSON data field (REVIEW FIELDS)
  [✓] get_user_statistics - has JSON data field (added as_dict)
  [✓] get_portfolio_overview - has JSON data field (added as_dict)
  [ ] get_current_positions - review JSON structure
  [ ] scan_options_chain - review JSON structure
  [ ] get_detailed_option_chain - review JSON structure
  [ ] get_historical_stock_prices - review JSON structure
  [ ] get_market_sentiment - review JSON structure
  [ ] get_technical_summary - review JSON structure
  [ ] get_trending_tickers - review JSON structure
  [ ] get_analyst_recommendations - review JSON structure
  [ ] list_user_accounts - review JSON structure
  [ ] get_option_expiration_dates - review JSON structure

TODO: Fix mypy type errors in mcp_server.py (43 warnings currently)
-------------------------------------------------------------------
Current mypy warnings breakdown:
  - _validate_username argument type mismatches (multiple locations)
  - Watchlists method argument type issues
  - Item "None" attribute access (needs proper null checks)
  - ExtrinsicValue attribute access issues
  - Market data provider method type mismatches
  - Incompatible assignment on line 240

Target: Reduce from 43 warnings to 0 incrementally.
Strategy:
  1. Fix _validate_username signature/usage consistency
  2. Add proper null checks for Optional types
  3. Fix Watchlists interface mismatches
  4. Review ExtrinsicValue attribute access
  5. Add type annotations where missing

TODO: Create MCP API Documentation
----------------------------------
Generate comprehensive reference document showing all MCP server APIs:
  - Tool name and description
  - Request parameters (with types, defaults, descriptions)
  - Response schema (text + JSON data structure)
  - Example requests and responses
  - Use cases and when to call each API

Location: doc/mcp_api_reference.md
Purpose: Easy review of all APIs, signatures, and return schemas
Format: Markdown with code examples and JSON schemas
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


# Add parent directory (src/) to path so imports work from src/mcp/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Local application imports
import hashlib
import secrets

import constants as const
import util
from db import Db
from deposits import Deposits
from df_stats import DFStats
from dividends import Dividends
from extrinsicvalue import ExtrinsicValue
from market_sentiment import MarketSentiment
from messages import Messages
from pop_calculator import POPCalculator
from positions import Positions
from providers.market_data_factory import MarketDataFactory
from providers.yfinance_provider import YFinanceProvider
from scanner import Scanner
from shares import Shares
from ta_service import get_ta_service
from trades import Trades
from watchlists import Watchlists


# Configure logging using util.setup_logger with custom log file
util.setup_logger(name=None, level="INFO", console=True, log_file=const.API_LOG_FILE)
logger = logging.getLogger(__name__)


# Pseudonymization utilities for PII protection
# ---------------------------------------------
def create_pseudonym_context() -> tuple[str, dict[str, str]]:
    """
    Create ephemeral pseudonymization context for a single request.

    Returns:
        tuple: (salt, empty mapping dict)
        - salt: Random hex string for this request only
        - mapping: username → pseudonym mapping (populated during use)

    Privacy: Each request gets fresh salt/mapping, destroyed after response
    """
    request_salt = secrets.token_hex(16)
    request_map: dict[str, str] = {}
    return request_salt, request_map


def get_pseudonym(username: str, salt: str, mapping: dict[str, str]) -> str:
    """
    Get or create consistent pseudonym for username within this request.

    Args:
        username: Real Discord username
        salt: Request-specific salt
        mapping: Request-specific username → pseudonym map

    Returns:
        Pseudonym like "user_a3f9b2c1" (deterministic within request)

    Privacy: Same username → same pseudonym within request (pattern tracking),
             but different pseudonyms across requests (unlinkable)
    """
    if username not in mapping:
        hash_obj = hashlib.sha256(f"{salt}{username}".encode())
        short_hash = hash_obj.hexdigest()[:8]
        mapping[username] = f"user_{short_hash}"
    return mapping[username]


def get_reverse_map(mapping: dict[str, str]) -> dict[str, str]:
    """
    Get reverse mapping (pseudonym → real username) for digest generation.

    Args:
        mapping: username → pseudonym map

    Returns:
        pseudonym → username map for reversing after LLM processing
    """
    return {v: k for k, v in mapping.items()}


# Initialize FastAPI app
app = FastAPI(
    title="Options Trading Bot MCP Server",
    description="Model Context Protocol server providing comprehensive access to options trading data, real-time market data, fundamental analysis, and community knowledge",
    version="1.0.0",
)

# Track server startup time for debugging
SERVER_START_TIME = None

# Add CORS middleware to allow Open WebUI browser connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local network access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Logging middleware to track all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing information"""
    start_time = time.time()

    # Get client IP
    client_host = request.client.host if request.client else "unknown"

    # Log request
    logger.info("========== Incoming Request ==========")
    logger.info(f"Method: {request.method} | Path: {request.url.path} | Client: {client_host}")

    # Log query params if present
    if request.query_params:
        logger.info(f"Query Params: {dict(request.query_params)}")

    # Process request
    try:
        response = await call_next(request)

        # Calculate request duration
        duration = time.time() - start_time

        # Log response
        logger.info(f"Status: {response.status_code} | Duration: {duration:.3f}s")
        logger.info("======================================")

        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed after {duration:.3f}s: {e!s}", exc_info=True)
        logger.info("======================================")
        raise


# ============================================================================
# MCP Protocol Models
# ============================================================================


class ToolInputSchema(BaseModel):
    """Schema for tool input parameters"""

    type: str = "object"
    properties: dict[str, Any]
    required: list[str] | None = []


class Tool(BaseModel):
    """MCP Tool definition"""

    name: str
    description: str
    inputSchema: ToolInputSchema


class ResourceType(str, Enum):
    """Types of resources available"""

    TEXT = "text"
    IMAGE = "image"
    BINARY = "binary"


class Resource(BaseModel):
    """MCP Resource definition"""

    uri: str
    name: str
    description: str
    mimeType: str


class Prompt(BaseModel):
    """MCP Prompt definition"""

    name: str
    description: str
    arguments: list[dict[str, Any]] | None = []


# ============================================================================
# Request/Response Models
# ============================================================================


class ToolCallRequest(BaseModel):
    """Request model for tool execution"""

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    """Response model for tool execution"""

    content: list[dict[str, Any]]
    isError: bool = False
    pseudonym_map: dict[str, str] | None = None  # For username pseudonymization reversal


class ResourceRequest(BaseModel):
    """Request model for resource access"""

    uri: str


class ResourceResponse(BaseModel):
    """Response model for resource access"""

    contents: list[dict[str, Any]]


class PromptRequest(BaseModel):
    """Request model for prompt execution"""

    name: str
    arguments: dict[str, Any] | None = None


class PromptResponse(BaseModel):
    """Response model for prompt execution"""

    messages: list[dict[str, Any]]


# ============================================================================
# MCP Server Implementation
# ============================================================================


class MCPServer:
    """Core MCP Server implementation"""

    def __init__(self):
        logger.info("Initializing MCP Server...")

        self.tools: dict[str, Tool] = {}
        self.resources: dict[str, Resource] = {}
        self.prompts: dict[str, Prompt] = {}

        # Initialize database connection
        try:
            self.db = Db(in_memory=False)
            self.trades = Trades(self.db)
            self.shares = Shares(self.db)
            self.dividends = Dividends(self.db)
            self.deposits = Deposits(self.db)
            self.watchlists = Watchlists(self.db)
            self.positions = Positions(self.db, self.shares, self.trades)
            self.messages = Messages(self.db)
            logger.info("Database connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise

        # Market data providers are managed by MarketDataFactory with automatic fallback
        # Scanner, ExtrinsicValue, POPCalculator, etc. all use the factory internally
        MarketDataFactory.set_db(self.db)

        # Initialize market sentiment provider
        try:
            self.sentiment = MarketSentiment()
            logger.info("Market sentiment provider initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize market sentiment: {e}", exc_info=True)
            self.sentiment = None  # type: ignore[assignment]

        self._initialize_defaults()
        logger.info(
            f"MCP Server initialized with {len(self.tools)} tools, {len(self.resources)} resources, {len(self.prompts)} prompts"
        )

    def _get_registered_users(self) -> set:
        """Get set of all registered usernames from the database"""
        return set(self.db.get_users())

    def _validate_username(self, username: str | None) -> tuple[bool, str]:
        """
        Validate username against registered users in database

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not username:
            return False, "ERROR: Username is required and cannot be empty."

        # Get registered users
        registered_users = self._get_registered_users()

        if not registered_users:
            # Database might be empty, allow any username
            logger.warning("No registered users found in database")
            return True, ""

        if username not in registered_users:
            # Common mistakes that violate the prompt
            common_mistakes = {
                "USER": "Never use 'USER' as username - this is a placeholder, not a real username",
                "user": "Never use 'user' as username - this is a placeholder, not a real username",
                "History": "'History' is not a valid username",
                "Alaska": "'Alaska' is an account name, not a username",
                "Joint": "'Joint' is an account name, not a username",
                "HODL": "'HODL' is an account name, not a username",
            }

            error_msg = f"ERROR: Username '{username}' is not registered in the system.\n"

            if username in common_mistakes:
                error_msg += f"\n{common_mistakes[username]}\n"

            error_msg += f"\nRegistered users: {', '.join(sorted(registered_users))}"
            error_msg += "\n\nIf you're looking for user 'sangelovich', use that exact username in your query."

            return False, error_msg

        return True, ""

    def _initialize_defaults(self):
        """Initialize default tools, resources, and prompts"""

        # ========== Tools ==========

        # Query Trades
        self.register_tool(
            Tool(
                name="query_trades",
                description="Query options trades for a user, optionally filtered by symbol, date range, and account",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query trades for",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional ticker symbol to filter by (e.g., 'AAPL')",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date in YYYY-MM-DD format",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Query Shares
        self.register_tool(
            Tool(
                name="query_shares",
                description="Query share transactions for a user, optionally filtered by symbol, date range, and account",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query shares for",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional ticker symbol to filter by",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date in YYYY-MM-DD format",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Query Dividends
        self.register_tool(
            Tool(
                name="query_dividends",
                description="Query dividend payments for a user, optionally filtered by symbol, date range, and account",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query dividends for",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional ticker symbol to filter by",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date in YYYY-MM-DD format",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Query Deposits
        self.register_tool(
            Tool(
                name="query_deposits",
                description="Query deposits and withdrawals for a user, optionally filtered by date range and account",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query deposits for",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date in YYYY-MM-DD format",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date in YYYY-MM-DD format",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Query Watchlist
        self.register_tool(
            Tool(
                name="query_watchlist",
                description="Get the list of symbols on a user's watchlist",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query watchlist for",
                        },
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID to filter watchlist by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Add to Watchlist
        self.register_tool(
            Tool(
                name="add_to_watchlist",
                description="Add a symbol to a user's watchlist",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {"type": "string", "description": "Username to add symbol for"},
                        "symbol": {
                            "type": "string",
                            "description": "Ticker symbol to add (e.g., 'AAPL')",
                        },
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID for multi-guild support",
                        },
                    },
                    required=["username", "symbol"],
                ),
            )
        )

        # Remove from Watchlist
        self.register_tool(
            Tool(
                name="remove_from_watchlist",
                description="Remove a symbol from a user's watchlist",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to remove symbol for",
                        },
                        "symbol": {"type": "string", "description": "Ticker symbol to remove"},
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID for multi-guild support",
                        },
                    },
                    required=["username", "symbol"],
                ),
            )
        )

        # Get User Statistics
        self.register_tool(
            Tool(
                name="get_user_statistics",
                description="Get comprehensive trading statistics for a user, including monthly breakdown of premiums and dividends",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to get statistics for",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year to filter by (defaults to current year)",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Get Symbol Statistics
        self.register_tool(
            Tool(
                name="get_symbol_statistics",
                description="Get aggregated trading data for a specific symbol",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to get statistics for",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year to filter by (defaults to current year)",
                        },
                        "month": {
                            "type": "integer",
                            "description": "Optional month to filter by (1-12, defaults to current month)",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # List Popular Symbols
        self.register_tool(
            Tool(
                name="list_popular_symbols",
                description="Get list of most popular traded symbols, optionally filtered by user and time period",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Optional username to filter by (if not provided, returns team-wide popular symbols)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 7)",
                        },
                    },
                    required=[],
                ),
            )
        )

        # Get Complete Portfolio Overview
        self.register_tool(
            Tool(
                name="get_portfolio_overview",
                description="Get COMPLETE portfolio overview including options trades, share transactions, dividends, and deposits. Use this when asked for 'comprehensive', 'complete', 'full', or 'all' data.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to get portfolio for",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by (e.g., 'Joint', 'Roth IRA')",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year to filter by (defaults to current year)",
                        },
                        "guild_id": {
                            "type": "integer",
                            "description": "Optional guild ID to filter by",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # Compare Periods
        self.register_tool(
            Tool(
                name="compare_periods",
                description="Compare trading performance between two time periods (e.g., this month vs last month, Q1 vs Q2). Returns side-by-side comparison of premiums, dividends, and total income.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to compare data for",
                        },
                        "period1_start": {
                            "type": "string",
                            "description": "Start date of first period (YYYY-MM-DD)",
                        },
                        "period1_end": {
                            "type": "string",
                            "description": "End date of first period (YYYY-MM-DD)",
                        },
                        "period2_start": {
                            "type": "string",
                            "description": "Start date of second period (YYYY-MM-DD)",
                        },
                        "period2_end": {
                            "type": "string",
                            "description": "End date of second period (YYYY-MM-DD)",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                    },
                    required=[
                        "username",
                        "period1_start",
                        "period1_end",
                        "period2_start",
                        "period2_end",
                    ],
                ),
            )
        )

        # Compare Accounts
        self.register_tool(
            Tool(
                name="compare_accounts",
                description="Compare trading performance across different accounts (e.g., Joint vs Roth IRA). Shows which account is performing better.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to compare accounts for",
                        },
                        "account1": {
                            "type": "string",
                            "description": "First account name (e.g., 'Joint')",
                        },
                        "account2": {
                            "type": "string",
                            "description": "Second account name (e.g., 'Roth IRA')",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year to filter by (defaults to current year)",
                        },
                    },
                    required=["username", "account1", "account2"],
                ),
            )
        )

        # Compare Symbols
        self.register_tool(
            Tool(
                name="compare_symbols",
                description="Compare trading performance across different ticker symbols. Shows which symbols are most profitable.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to compare symbols for",
                        },
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of ticker symbols to compare (e.g., ['HOOD', 'AAPL', 'TSLA'])",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Optional year to filter by (defaults to current year)",
                        },
                    },
                    required=["username", "symbols"],
                ),
            )
        )

        # Calculate ROI
        self.register_tool(
            Tool(
                name="calculate_roi",
                description="Calculate Return on Investment (ROI) for a specific symbol or overall portfolio. Factors in all premiums, share purchases/sales, and current positions.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to calculate ROI for",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional ticker symbol (if omitted, calculates overall portfolio ROI)",
                        },
                        "account": {
                            "type": "string",
                            "description": "Optional account name to filter by",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Optional start date for ROI calculation (YYYY-MM-DD)",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "Optional end date for ROI calculation (YYYY-MM-DD)",
                        },
                    },
                    required=["username"],
                ),
            )
        )

        # List User Accounts
        self.register_tool(
            Tool(
                name="list_user_accounts",
                description="Get all distinct account names for a user. Useful for discovering what accounts exist before running comparisons.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to list accounts for",
                        }
                    },
                    required=["username"],
                ),
            )
        )

        # Get Current Positions (Stock Holdings and Open Options)
        self.register_tool(
            Tool(
                name="get_current_positions",
                description="Get current stock holdings and open option positions with live market values, unrealized P/L, cost basis, and DTE (days to expiration). Shows net positions aggregated across ALL accounts by default, or filtered to specific account. Shows totals after accounting for all buys/sells and option trades.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "username": {
                            "type": "string",
                            "description": "Username to query positions for",
                        },
                        "account": {
                            "type": "string",
                            "description": "Account to filter by (e.g., 'IRA', 'Joint'). Use 'ALL' or omit for all accounts aggregated.",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Optional symbol filter to show positions for specific ticker only",
                        },
                        "guild_id": {"type": "string", "description": "Discord guild ID"},
                    },
                    required=["username"],
                ),
            )
        )

        # Get Help
        self.register_tool(
            Tool(
                name="get_help",
                description="Get detailed help about available tools and their usage. Returns comprehensive documentation with examples.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "tool_name": {
                            "type": "string",
                            "description": "Optional specific tool name to get help for (if omitted, lists all tools)",
                        }
                    },
                    required=[],
                ),
            )
        )

        # Scan Options Chain
        self.register_tool(
            Tool(
                name="scan_options_chain",
                description="Scan options chains to identify trading opportunities based on Greeks (delta), expiration, IV, and liquidity filters. Returns top-scored candidates ranked by composite score. Uses Black-Scholes estimation for missing deltas. IMPORTANT: Pass MULTIPLE symbols in a single call to scan efficiently (e.g., symbols=['HOOD','MSTU','TSLA','SOFI']). DO NOT call this tool multiple times with single symbols - that wastes iterations. Use user's watchlist, community trending tickers, or specific tickers based on analysis context. Defaults are permissive - adjust filters based on user's strategy (e.g., conservative=higher delta_min, aggressive=lower delta_min, longer-term=higher max_expiration_days).",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of ticker symbols to scan in a SINGLE call (e.g., ['HOOD', 'MSTU', 'TSLA', 'SOFI']). Pass ALL tickers from watchlist at once, not one at a time.",
                        },
                        "chain": {
                            "type": "string",
                            "description": "Option type to scan: 'PUT' or 'CALL'",
                            "enum": ["PUT", "CALL"],
                        },
                        "delta_min": {
                            "type": "number",
                            "description": "Minimum delta threshold (0.01-1.0, default 0.01). Higher values = more conservative trades closer to ATM.",
                        },
                        "delta_max": {
                            "type": "number",
                            "description": "Maximum delta threshold (0.01-1.0, default 0.30). Lower values = more aggressive OTM trades.",
                        },
                        "max_expiration_days": {
                            "type": "integer",
                            "description": "Maximum days to expiration (default 31). Adjust based on strategy: weeklies=7, monthlies=31, longer-term=60+.",
                        },
                        "iv_min": {
                            "type": "number",
                            "description": "Minimum implied volatility in % (default 15). Higher IV = higher premiums but more risk.",
                        },
                        "open_interest_min": {
                            "type": "integer",
                            "description": "Minimum open interest for liquidity (default 10). Higher = more liquid, easier to exit.",
                        },
                        "volume_min": {
                            "type": "integer",
                            "description": "Minimum daily volume (default 0). Set higher for very liquid tickers.",
                        },
                        "strike_proximity": {
                            "type": "number",
                            "description": "Maximum % distance from current price (default 0.40 = 40%). Prevents finding strikes too far OTM.",
                        },
                        "top_candidates": {
                            "type": "integer",
                            "description": "Number of top results to return (default 30). Results are ranked by composite score.",
                        },
                    },
                    required=["symbols", "chain"],
                ),
            )
        )

        # Calculate Extrinsic Value
        self.register_tool(
            Tool(
                name="calculate_extrinsic_value",
                description="Calculate intrinsic and extrinsic value for option strikes. Shows bid/ask/current price and breaks down value components for each strike. Useful for validating option pricing before entering trades.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Underlying stock ticker symbol (e.g., 'MSTU', 'HOOD')",
                        },
                        "strikes": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "List of strike prices to analyze (e.g., [50, 55, 60])",
                        },
                    },
                    required=["ticker", "strikes"],
                ),
            )
        )

        # Calculate Probability of Profit (POP)
        self.register_tool(
            Tool(
                name="calculate_probability_of_profit",
                description="Calculate probability of profit (POP) for an option position using Black-Scholes model. Shows probability of expiring OTM (good for sellers), expected value, and breakeven price. Helps evaluate risk/reward before entering trades.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Underlying stock ticker symbol (e.g., 'MSTU', 'HOOD')",
                        },
                        "strike": {"type": "number", "description": "Option strike price"},
                        "expiration_date": {
                            "type": "string",
                            "description": "Expiration date in YYYY-MM-DD format",
                        },
                        "option_type": {
                            "type": "string",
                            "description": "Option type: 'PUT' or 'CALL'",
                            "enum": ["PUT", "CALL"],
                        },
                        "premium": {
                            "type": "number",
                            "description": "Premium received/paid per contract (optional, for expected value calculation)",
                        },
                        "iv": {
                            "type": "number",
                            "description": "Implied volatility as percentage (e.g., 50.0 for 50%). If not provided, estimated from historical volatility.",
                        },
                    },
                    required=["ticker", "strike", "expiration_date", "option_type"],
                ),
            )
        )

        # Get Community Messages
        self.register_tool(
            Tool(
                name="get_community_messages",
                description="Query community Discord messages from the knowledge base. Returns recent messages with metadata (user, content, tickers mentioned). Use to discover what the community is discussing about specific topics, tickers, or options strategies. Guild-scoped for data isolation. Filter by category: 'sentiment' for trading discussions/strategies, 'news' for market news/announcements.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "guild_id": {
                            "type": "string",
                            "description": "Discord guild/server ID (required for data isolation)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 7)",
                        },
                        "ticker": {
                            "type": "string",
                            "description": "Optional ticker symbol to filter messages by (e.g., 'MSTX', 'HOOD')",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional message category to filter by: 'sentiment' (trading discussions, strategies, positions) or 'news' (market updates, announcements)",
                        },
                        "username": {
                            "type": "string",
                            "description": "Optional username to filter messages by",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of messages to return (default: 50)",
                        },
                    },
                    required=["guild_id"],
                ),
            )
        )

        # Get Community Trades
        self.register_tool(
            Tool(
                name="get_community_trades",
                description="Get structured trades extracted from Discord messages (text + OCR). Returns only messages with parsed trade details (BTO/STO/BTC/STC operations). Use to analyze what the community is actively trading. Guild-scoped for data isolation.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "guild_id": {
                            "type": "string",
                            "description": "Discord guild/server ID (required for data isolation)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to look back (default: 7)",
                        },
                        "ticker": {
                            "type": "string",
                            "description": "Optional ticker symbol to filter by (e.g., 'MSTX', 'HOOD')",
                        },
                        "username": {
                            "type": "string",
                            "description": "Optional username to filter by",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of trades to return (default: 20)",
                        },
                    },
                    required=["guild_id"],
                ),
            )
        )

        # Get Market News
        self.register_tool(
            Tool(
                name="get_market_news",
                description="Get recent market news articles for a ticker from Yahoo Finance/Finnhub (last 7 days). Returns article headlines, summaries, URLs, and publication timestamps. Use to discover news affecting user positions, watchlist, or trending tickers.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'MSTX', 'HOOD', 'TSLA')",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of articles to return (default: 5, max: 20)",
                        },
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Trending Tickers
        self.register_tool(
            Tool(
                name="get_trending_tickers",
                description="Get trending tickers based on community discussion frequency. Returns tickers sorted by mention count, with statistics on unique users discussing each ticker and recent activity summary. Use this to discover what's hot in the community. Guild-scoped for data isolation.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "guild_id": {
                            "type": "integer",
                            "description": "Discord guild/server ID (required for data isolation)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 7)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of top tickers to return (default: 20)",
                        },
                    },
                    required=["guild_id"],
                ),
            )
        )

        # Get Community Channels
        self.register_tool(
            Tool(
                name="get_community_channels",
                description="List available Discord channels in the harvested message database. Shows channel names and message counts. Useful for discovering where different discussions happen.",
                inputSchema=ToolInputSchema(type="object", properties={}, required=[]),
            )
        )

        # ========== Market Data Tools (from Yahoo Finance) ==========

        # Get Historical Stock Prices
        self.register_tool(
            Tool(
                name="get_historical_stock_prices",
                description="Get historical OHLCV (Open, High, Low, Close, Volume) data for a stock. Supports customizable time periods and intervals. Useful for price charts, trend analysis, and technical indicators.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'",
                            "default": "1mo",
                        },
                        "interval": {
                            "type": "string",
                            "description": "Data interval: '1m', '5m', '15m', '30m', '60m', '1d', '5d', '1wk', '1mo'",
                            "default": "1d",
                        },
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Stock Actions (Dividends & Splits)
        self.register_tool(
            Tool(
                name="get_stock_actions",
                description="Get dividend and stock split history for a ticker. Shows all corporate actions that affect shareholder value. Returns dates, dividend amounts, and split ratios.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                        }
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Financial Statement
        self.register_tool(
            Tool(
                name="get_financial_statement",
                description="Get financial statements: income statement, balance sheet, or cash flow statement. Available in annual or quarterly format. Essential for fundamental analysis.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                        },
                        "statement_type": {
                            "type": "string",
                            "description": "Type of statement: 'income', 'balance', 'cash'",
                            "default": "income",
                        },
                        "period": {
                            "type": "string",
                            "description": "Period: 'annual' or 'quarterly'",
                            "default": "annual",
                        },
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Holder Info
        self.register_tool(
            Tool(
                name="get_holder_info",
                description="Get institutional holders, mutual funds, major holders, or insider transactions. Shows who owns the stock and recent insider activity. Useful for sentiment analysis.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                        },
                        "holder_type": {
                            "type": "string",
                            "description": "Type of holders: 'institutional', 'mutualfund', 'major', 'insider'",
                            "default": "institutional",
                        },
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Analyst Recommendations
        self.register_tool(
            Tool(
                name="get_analyst_recommendations",
                description="Get analyst recommendations and rating history. Shows upgrades, downgrades, and consensus ratings over time. Useful for gauging market sentiment.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                        }
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Option Expiration Dates
        self.register_tool(
            Tool(
                name="get_option_expiration_dates",
                description="Get all available options expiration dates for a ticker. Returns list of dates in YYYY-MM-DD format. Use this first before fetching option chains.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'SPY')",
                        }
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Detailed Option Chain (for specific expiration)
        self.register_tool(
            Tool(
                name="get_detailed_option_chain",
                description="Get detailed options chain for a specific expiration date. Returns full data including Greeks, IV, bid/ask for calls or puts. More comprehensive than scan_options_chain.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'SPY')",
                        },
                        "expiration_date": {
                            "type": "string",
                            "description": "Expiration date in YYYY-MM-DD format (get from get_option_expiration_dates)",
                        },
                        "option_type": {
                            "type": "string",
                            "description": "Option type: 'calls', 'puts', or 'both'",
                            "default": "both",
                        },
                    },
                    required=["ticker", "expiration_date"],
                ),
            )
        )

        # Get Market Sentiment
        self.register_tool(
            Tool(
                name="get_market_sentiment",
                description="Get current market sentiment indicators: VIX (volatility index), CNN Fear & Greed Index (0-100), and Crypto Fear & Greed Index (0-100). Use to gauge overall market conditions and investor sentiment before making trading decisions.",
                inputSchema=ToolInputSchema(type="object", properties={}, required=[]),
            )
        )

        # ========== Technical Analysis Tools ==========

        # Get Technical Analysis
        self.register_tool(
            Tool(
                name="get_technical_analysis",
                description="Get comprehensive technical analysis for a ticker including: RSI, MACD, Bollinger Bands, Moving Averages (SMA/EMA), ATR, volume analysis, support/resistance levels, trend analysis, and chart patterns. Returns both raw indicators and human-readable interpretation. Essential for analyzing entry/exit points and trend strength.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'SPY', 'MSTU')",
                        },
                        "period": {
                            "type": "string",
                            "description": "Time period for analysis: '1d', '5d', '1mo', '3mo' (default), '6mo', '1y', '2y'",
                            "default": "3mo",
                        },
                        "interval": {
                            "type": "string",
                            "description": "Data interval: '1m', '5m', '15m', '30m', '60m', '1d' (default), '1wk'",
                            "default": "1d",
                        },
                        "include_patterns": {
                            "type": "boolean",
                            "description": "Whether to detect chart patterns (double top/bottom). Slower but more comprehensive.",
                            "default": True,
                        },
                    },
                    required=["ticker"],
                ),
            )
        )

        # Get Technical Summary
        self.register_tool(
            Tool(
                name="get_technical_summary",
                description="Get fast trading signals for a ticker (optimized for speed). Returns overall signal (BULLISH/BEARISH/NEUTRAL) and key indicators: RSI, MACD, moving average alignment, Bollinger Band position. Use when you need quick sentiment without full TA. Faster than get_technical_analysis.",
                inputSchema=ToolInputSchema(
                    type="object",
                    properties={
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., 'AAPL', 'SPY', 'MSTU')",
                        }
                    },
                    required=["ticker"],
                ),
            )
        )

        # ========== Resources ==========

        self.register_resource(
            Resource(
                uri="trades://schema",
                name="database_schema",
                description="Database schema information for all tables",
                mimeType="application/json",
            )
        )

        self.register_resource(
            Resource(
                uri="trades://users",
                name="all_users",
                description="List of all users in the system",
                mimeType="application/json",
            )
        )

        # ========== Prompts ==========

        self.register_prompt(
            Prompt(
                name="analyze_trading_performance",
                description="Generate a prompt for analyzing a user's trading performance",
                arguments=[
                    {"name": "username", "description": "Username to analyze", "required": True},
                    {
                        "name": "time_period",
                        "description": "Time period to analyze (e.g., 'last month', 'this year')",
                        "required": False,
                    },
                ],
            )
        )

        self.register_prompt(
            Prompt(
                name="watchlist_analysis",
                description="Generate a prompt for analyzing watchlist symbols and recent trading activity",
                arguments=[
                    {
                        "name": "username",
                        "description": "Username to analyze watchlist for",
                        "required": True,
                    }
                ],
            )
        )

        self.register_prompt(
            Prompt(
                name="portfolio_overview",
                description="Generate a comprehensive portfolio overview prompt including all trades, shares, dividends, and watchlist",
                arguments=[
                    {
                        "name": "username",
                        "description": "Username to generate portfolio overview for",
                        "required": True,
                    }
                ],
            )
        )

    def register_tool(self, tool: Tool):
        """Register a new tool"""
        self.tools[tool.name] = tool

    def register_resource(self, resource: Resource):
        """Register a new resource"""
        self.resources[resource.uri] = resource

    def register_prompt(self, prompt: Prompt):
        """Register a new prompt"""
        self.prompts[prompt.name] = prompt

    def _build_condition(
        self,
        symbol: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        account: str | None = None,
        guild_id: int | None = None,
    ) -> str | None:
        """Build SQL condition string from optional parameters"""
        conditions = []

        if symbol:
            conditions.append(f'symbol = "{symbol.upper()}"')
        if start_date and end_date:
            conditions.append(f'date BETWEEN "{start_date}" AND "{end_date}"')
        elif start_date:
            conditions.append(f'date >= "{start_date}"')
        elif end_date:
            conditions.append(f'date <= "{end_date}"')
        if account:
            conditions.append(f'account = "{account}"')
        if guild_id is not None:
            conditions.append(f"guild_id = {guild_id}")

        return " AND ".join(conditions) if conditions else None

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallResponse:
        """Execute a tool by name"""
        logger.info(f"Executing tool: {name}")
        logger.debug(f"Tool arguments: {arguments}")

        if name not in self.tools:
            logger.warning(f"Tool not found: {name}")
            return ToolCallResponse(
                content=[{"type": "text", "text": f"Tool '{name}' not found"}], isError=True
            )

        try:
            # Query Trades
            if name == "query_trades":
                username = arguments.get("username")
                symbol = arguments.get("symbol")
                account = arguments.get("account")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"query_trades: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                logger.info(
                    f"query_trades: username={username}, symbol={symbol}, account={account}"
                )

                condition = self._build_condition(
                    symbol=symbol,
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                    account=account,
                )
                df = self.trades.as_df(username, filter=condition)
                result = df.to_dict(orient="records")

                logger.info(f"query_trades: Found {len(result)} trades for {username}")
                return ToolCallResponse(
                    content=[
                        {"type": "text", "text": f"Found {len(result)} trades", "data": result}
                    ],
                    isError=False,
                )

            # Query Shares
            if name == "query_shares":
                username = arguments.get("username")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"query_shares: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                condition = self._build_condition(
                    symbol=arguments.get("symbol"),
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                    account=arguments.get("account"),
                )
                df = self.shares.as_df(username, filter=condition)
                result = df.to_dict(orient="records")
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Found {len(result)} share transactions",
                            "data": result,
                        }
                    ],
                    isError=False,
                )

            # Query Dividends
            if name == "query_dividends":
                username = arguments.get("username")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"query_dividends: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                condition = self._build_condition(
                    symbol=arguments.get("symbol"),
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                    account=arguments.get("account"),
                )
                df = self.dividends.as_df(username, filter=condition)
                result = df.to_dict(orient="records")
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Found {len(result)} dividend payments",
                            "data": result,
                        }
                    ],
                    isError=False,
                )

            # Query Deposits
            if name == "query_deposits":
                username = arguments.get("username")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"query_deposits: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                condition = self._build_condition(
                    start_date=arguments.get("start_date"),
                    end_date=arguments.get("end_date"),
                    account=arguments.get("account"),
                )
                df = self.deposits.as_df(username, filter=condition)
                result = df.to_dict(orient="records")
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Found {len(result)} deposit/withdrawal transactions",
                            "data": result,
                        }
                    ],
                    isError=False,
                )

            # Query Watchlist
            if name == "query_watchlist":
                username = arguments.get("username")
                guild_id = arguments.get("guild_id")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"query_watchlist: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                logger.info(f"query_watchlist: username={username}, guild_id={guild_id}")

                symbols = self.watchlists.list_symbols(username, guild_id)  # type: ignore[arg-type]

                logger.info(f"query_watchlist: Found {len(symbols)} symbols for {username}")
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Found {len(symbols)} symbols in watchlist",
                            "data": {"symbols": symbols},
                        }
                    ],
                    isError=False,
                )

            # Add to Watchlist
            if name == "add_to_watchlist":
                username = arguments.get("username")
                symbol = arguments.get("symbol")
                guild_id = arguments.get("guild_id")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"add_to_watchlist: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                success = self.watchlists.add(username, symbol, guild_id)  # type: ignore[arg-type]
                if success:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"Successfully added {symbol} to watchlist for {username}",
                                "data": {
                                    "success": True,
                                    "symbol": symbol,
                                    "username": username,
                                    "action": "added",
                                },
                            }
                        ],
                        isError=False,
                    )
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Symbol {symbol} already exists in watchlist for {username}",
                            "data": {
                                "success": False,
                                "symbol": symbol,
                                "username": username,
                                "action": "already_exists",
                            },
                        }
                    ],
                    isError=False,
                )

            # Remove from Watchlist
            if name == "remove_from_watchlist":
                username = arguments.get("username")
                symbol = arguments.get("symbol")
                guild_id = arguments.get("guild_id")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"remove_from_watchlist: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                deleted = self.watchlists.remove(username, symbol, guild_id)  # type: ignore[arg-type]
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Removed {deleted} entries for {symbol} from watchlist for {username}",
                            "data": {
                                "deleted_count": deleted,
                                "symbol": symbol,
                                "username": username,
                                "action": "removed",
                            },
                        }
                    ],
                    isError=False,
                )

            # Get User Statistics
            if name == "get_user_statistics":
                username = arguments.get("username")
                account = arguments.get("account")
                guild_id = arguments.get("guild_id")
                year = arguments.get("year")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"get_user_statistics: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                # Convert "ALL" to None (LLM may pass "ALL" instead of omitting the parameter)
                if account and account.upper() == "ALL":
                    account = None

                logger.info(
                    f"get_user_statistics: username={username}, account={account}, year={year}, guild_id={guild_id}"
                )

                df_stats = DFStats(self.db)
                df_stats.load(username, account=account, guild_id=guild_id)

                # Apply year filter if provided
                if year:
                    df_stats.filter_by_year(year)
                else:
                    year = datetime.now().year
                    df_stats.filter_by_year(year)

                stats_text = df_stats.my_stats()
                stats_data = df_stats.as_dict()

                logger.info(
                    f"get_user_statistics: Generated statistics for {username} (year={year}, account={account})"
                )
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Trading statistics for {username}:\n\n{stats_text}",
                            "data": {
                                "username": username,
                                "year": year,
                                "account": account if account else "ALL",
                                **stats_data,
                            },
                        }
                    ],
                    isError=False,
                )

            # Get Symbol Statistics
            if name == "get_symbol_statistics":
                username = arguments.get("username")
                account = arguments.get("account")
                guild_id = arguments.get("guild_id")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"get_symbol_statistics: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                df_stats = DFStats(self.db)
                df_stats.load(username, account=account, guild_id=guild_id)

                # Apply filters
                year = arguments.get("year", datetime.now().year)
                month = arguments.get("month", datetime.now().month)
                df_stats.filter_by_year(year)
                df_stats.filter_by_month(month)

                stats_text = df_stats.my_symbol_stats()
                symbol_data = df_stats.symbol_stats_as_dict()

                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Symbol statistics for {username}:\n\n{stats_text}",
                            "data": {
                                "username": username,
                                "year": year,
                                "month": month,
                                "account": account if account else "ALL",
                                "symbols": symbol_data,
                            },
                        }
                    ],
                    isError=False,
                )

            # List Popular Symbols
            if name == "list_popular_symbols":
                username = arguments.get("username")
                days = arguments.get("days", 7)

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"list_popular_symbols: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                df = self.trades.get_popular_symbols(username, days)
                result = df.to_dict(orient="records")
                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": f"Popular symbols (last {days} days)",
                            "data": result,
                        }
                    ],
                    isError=False,
                )

            # Get Complete Portfolio Overview
            if name == "get_portfolio_overview":
                username = arguments.get("username")
                account = arguments.get("account")
                guild_id = arguments.get("guild_id")
                year = arguments.get("year")
                include = arguments.get("include")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"get_portfolio_overview: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                # Convert "ALL" to None (LLM may pass "ALL" instead of omitting the parameter)
                if account and account.upper() == "ALL":
                    account = None

                # Default to include all sections if not specified
                if not include or len(include) == 0:
                    include = ["options", "shares", "deposits"]

                logger.info(
                    f"get_portfolio_overview: username={username}, account={account}, year={year}, guild_id={guild_id}, include={include}"
                )

                # Load stats
                df_stats = DFStats(self.db)
                df_stats.load(username, account=account, guild_id=guild_id)

                if year:
                    df_stats.filter_by_year(year)
                else:
                    year = datetime.now().year
                    df_stats.filter_by_year(year)

                # Get options stats (if requested)
                stats_text = ""
                if "options" in include:
                    stats_text = df_stats.my_stats()

                # Get shares summary (if requested)
                shares_summary = ""
                shares_df = df_stats.shares_df
                if "shares" in include:
                    if not shares_df.empty:
                        shares_summary = f"\nSHARE TRANSACTIONS ({year}):\n"
                        shares_summary += f"Total Transactions: {len(shares_df)}\n"

                        # Group by action
                        buy_df = shares_df[shares_df["Action"] == "Buy"]
                        sell_df = shares_df[shares_df["Action"] == "Sell"]

                        if not buy_df.empty:
                            total_bought = buy_df["Amount"].sum()
                            shares_summary += f"Buys: {len(buy_df)} transactions, Total: ${abs(total_bought):,.2f}\n"

                        if not sell_df.empty:
                            total_sold = sell_df["Amount"].sum()
                            shares_summary += (
                                f"Sells: {len(sell_df)} transactions, Total: ${total_sold:,.2f}\n"
                            )

                        # Top symbols
                        top_symbols = (
                            shares_df.groupby("Symbol")["Quantity"]
                            .sum()
                            .sort_values(ascending=False)
                            .head(5)
                        )
                        if not top_symbols.empty:
                            shares_summary += "\nTop Symbols by Shares Traded:\n"
                            for symbol, qty in top_symbols.items():
                                shares_summary += f"  {symbol}: {qty:.0f} shares\n"
                    else:
                        shares_summary = "\nSHARE TRANSACTIONS: None for this period\n"

                # Get deposits summary (if requested)
                deposits_summary = ""
                deposits_df = (
                    df_stats.deposits_df
                    if hasattr(df_stats, "deposits_df")
                    else self.deposits.as_df(
                        username, filter=f'account="{account}"' if account else None
                    )
                )
                if "deposits" in include:
                    if not deposits_df.empty:
                        deposits_summary = f"\nDEPOSITS/WITHDRAWALS ({year}):\n"
                        deposit_total = (
                            deposits_df[deposits_df["Action"] == "Deposit"]["Amount"].sum()
                            if "Deposit" in deposits_df["Action"].values
                            else 0
                        )
                        withdrawal_total = (
                            deposits_df[deposits_df["Action"] == "Withdrawal"]["Amount"].sum()
                            if "Withdrawal" in deposits_df["Action"].values
                            else 0
                        )
                        deposits_summary += f"Deposits: ${deposit_total:,.2f}\n"
                        deposits_summary += f"Withdrawals: ${withdrawal_total:,.2f}\n"
                        deposits_summary += f"Net: ${deposit_total - withdrawal_total:,.2f}\n"
                    else:
                        deposits_summary = "\nDEPOSITS/WITHDRAWALS: None for this period\n"

                # Add glossary
                glossary = """
GLOSSARY:
- STO (Sell to Open): Premium collected by selling options to open a position
- BTC (Buy to Close): Cost to buy back and close a short option position
- BTO (Buy to Open): Cost to buy options to open a long position
- STC (Sell to Close): Premium collected by selling to close a long position
- Premium: Net income/loss from all options trades
- Dividends: Cash distributions from stock holdings
"""

                full_report = f"PORTFOLIO OVERVIEW for {username} ({year})\n"
                full_report += f"Account: {account if account else 'All Accounts'}\n"
                full_report += f"Sections: {', '.join(include)}\n"
                full_report += "=" * 60 + "\n\n"

                if "options" in include and stats_text:
                    full_report += "OPTIONS TRADING SUMMARY:\n"
                    full_report += stats_text + "\n\n"

                if "shares" in include and shares_summary:
                    full_report += shares_summary + "\n"

                if "deposits" in include and deposits_summary:
                    full_report += deposits_summary

                # Build JSON data - only include requested sections
                portfolio_data = {
                    "username": username,
                    "year": year,
                    "account": account if account else "ALL",
                    "sections_included": include,
                }

                if "options" in include:
                    portfolio_data["options"] = df_stats.as_dict()

                if "shares" in include:
                    portfolio_data["shares"] = (
                        shares_df.to_dict("records") if not shares_df.empty else []
                    )

                if "deposits" in include:
                    portfolio_data["deposits"] = (
                        deposits_df.to_dict("records") if not deposits_df.empty else []
                    )

                logger.info(f"get_portfolio_overview: Generated complete overview for {username}")
                return ToolCallResponse(
                    content=[{"type": "text", "text": full_report, "data": portfolio_data}],
                    isError=False,
                )

            # List User Accounts
            if name == "list_user_accounts":
                username = arguments.get("username")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"list_user_accounts: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                logger.info(f"list_user_accounts: username={username}")

                accounts = util.get_user_accounts(self.db, username)  # type: ignore[arg-type]

                result = f"Accounts for {username}:\n"
                if accounts:
                    for account in accounts:
                        result += f"  - {account}\n"
                else:
                    result = f"No accounts found for {username}"

                logger.info(f"list_user_accounts: Found {len(accounts)} accounts for {username}")
                return ToolCallResponse(
                    content=[{"type": "text", "text": result, "data": {"accounts": accounts}}],
                    isError=False,
                )

            # Get Current Positions
            if name == "get_current_positions":
                username = arguments.get("username")
                account = arguments.get("account")
                symbol = arguments.get("symbol")

                # Validate username
                is_valid, error_msg = self._validate_username(username)
                if not is_valid:
                    logger.warning(f"get_current_positions: Invalid username '{username}'")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": error_msg}], isError=True
                    )

                # After validation, username is guaranteed to be a non-empty string
                assert isinstance(username, str) and username

                # Handle 'ALL' as None for aggregated view
                account_filter = None if (not account or account.upper() == "ALL") else account

                logger.info(
                    f"get_current_positions: username={username}, account={account_filter}, symbol={symbol}"
                )

                # Get stock positions (filtered by account)
                stock_positions = self.positions.get_stock_positions(
                    username, account=account_filter, symbol=symbol
                )

                # Get open options (filtered by account)
                option_positions = self.positions.get_open_options(
                    username, account=account_filter, symbol=symbol
                )

                # Format result
                account_display = account if account_filter else "ALL ACCOUNTS"
                result = f"=== CURRENT POSITIONS ({account_display}) ===\n\n"

                if stock_positions:
                    result += "STOCK HOLDINGS:\n"
                    for pos in stock_positions:
                        cost_basis = pos["shares"] * pos["avg_cost"]
                        pl_str = (
                            f"+${pos['unrealized_pl']:,.2f}"
                            if pos["unrealized_pl"] >= 0
                            else f"-${abs(pos['unrealized_pl']):,.2f}"
                        )
                        company_name = pos.get("company_name", pos["symbol"])
                        result += f"  {pos['symbol']} ({company_name}): {pos['shares']} shares @ ${pos['avg_cost']:.2f} avg"
                        result += f" | Cost: ${cost_basis:,.2f} | Current: ${pos['current_price']:.2f} | Market Value: ${pos['market_value']:,.2f} | P/L: {pl_str}\n"

                    total_stock_value = sum(pos["market_value"] for pos in stock_positions)
                    total_stock_pl = sum(pos["unrealized_pl"] for pos in stock_positions)
                    total_cost_basis = sum(
                        pos["shares"] * pos["avg_cost"] for pos in stock_positions
                    )
                    result += f"\nTotal Cost Basis: ${total_cost_basis:,.2f}\n"
                    result += f"Total Stock Value: ${total_stock_value:,.2f}\n"
                    result += f"Total Stock P/L: ${total_stock_pl:,.2f}\n"
                else:
                    result += "No stock positions\n"

                result += "\n"

                if option_positions:
                    result += "OPEN OPTIONS:\n"
                    for pos in option_positions:
                        company_name = pos.get("company_name", pos["symbol"])
                        result += f"  {pos['symbol']} ({company_name}): {pos['net_contracts']} contracts of {pos['strike']}"
                        result += f" | Exp: {pos['expiration_date']} ({pos['dte']} DTE) | Premium: ${pos['entry_premium']:,.2f}\n"

                    total_option_premium = sum(pos["entry_premium"] for pos in option_positions)
                    result += f"\nTotal Option Premium: ${total_option_premium:,.2f}\n"
                else:
                    result += "No open option positions\n"

                logger.info(
                    f"get_current_positions: Found {len(stock_positions)} stock positions and {len(option_positions)} option positions for {username} (account={account_filter})"
                )

                return ToolCallResponse(
                    content=[
                        {
                            "type": "text",
                            "text": result,
                            "data": {
                                "stock_positions": stock_positions,
                                "option_positions": option_positions,
                            },
                        }
                    ],
                    isError=False,
                )

            # Get Help
            if name == "get_help":
                tool_name = arguments.get("tool_name")

                if tool_name:
                    # Get help for specific tool
                    if tool_name in self.tools:
                        tool = self.tools[tool_name]
                        help_text = f"TOOL: {tool.name}\n\n"
                        help_text += f"DESCRIPTION:\n{tool.description}\n\n"
                        help_text += "REQUIRED PARAMETERS:\n"
                        for param in tool.inputSchema.required:  # type: ignore[union-attr]
                            prop = tool.inputSchema.properties.get(param, {})
                            help_text += (
                                f"  - {param}: {prop.get('description', 'No description')}\n"
                            )
                        help_text += "\nOPTIONAL PARAMETERS:\n"
                        for param, prop in tool.inputSchema.properties.items():
                            if param not in tool.inputSchema.required:  # type: ignore[operator]
                                help_text += (
                                    f"  - {param}: {prop.get('description', 'No description')}\n"
                                )

                        return ToolCallResponse(
                            content=[{"type": "text", "text": help_text}], isError=False
                        )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"Tool '{tool_name}' not found"}],
                        isError=True,
                    )
                # List all tools
                help_text = "AVAILABLE TOOLS:\n\n"
                for tool in self.tools.values():
                    help_text += f"• {tool.name}\n  {tool.description}\n\n"
                help_text += (
                    "\nUse get_help with tool_name parameter for detailed help on a specific tool."
                )

                return ToolCallResponse(
                    content=[{"type": "text", "text": help_text}], isError=False
                )

            # Scan Options Chain
            if name == "scan_options_chain":
                symbols = arguments.get("symbols", [])
                chain = arguments.get("chain", "PUT").upper()
                # Permissive defaults to avoid over-filtering
                delta_min = arguments.get("delta_min", 0.01)
                delta_max = arguments.get("delta_max", 0.30)
                max_expiration_days = arguments.get("max_expiration_days", 31)
                iv_min = arguments.get("iv_min", 15.0)
                open_interest_min = arguments.get("open_interest_min", 10)
                volume_min = arguments.get("volume_min", 0)
                strike_proximity = arguments.get("strike_proximity", 0.40)
                top_candidates = arguments.get("top_candidates", 30)

                logger.info(
                    f"scan_options_chain: symbols={symbols}, chain={chain}, delta={delta_min}-{delta_max}, max_days={max_expiration_days}, iv_min={iv_min}, strike_proximity={strike_proximity}"
                )

                if not symbols:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": "ERROR: At least one symbol required for scanning",
                            }
                        ],
                        isError=True,
                    )

                # Initialize scanner with parameters (max_cache_age uses internal default)
                scanner = Scanner(
                    delta_min=delta_min,
                    delta_max=delta_max,
                    max_expiration_days=max_expiration_days,
                    iv_min=iv_min,
                    open_interest_min=open_interest_min,
                    volume_min=volume_min,
                    strike_proximity=strike_proximity,
                    top_candidates=top_candidates,
                )

                # Scan each symbol
                all_results = []
                diagnostic_messages = []

                for symbol in symbols:
                    try:
                        df, summary, params = scanner.scan(chain, [symbol], include_params=True)

                        if df is not None and not df.empty:
                            # Convert DataFrame to records for JSON serialization
                            results = df.to_dict(orient="records")
                            all_results.extend(results)
                            logger.info(
                                f"scan_options_chain: Found {len(results)} opportunities for {symbol}"
                            )
                        else:
                            logger.warning(f"scan_options_chain: No results for {symbol}")
                            # summary now contains detailed diagnostic message
                            diagnostic_messages.append(summary)
                    except Exception as e:
                        logger.error(f"scan_options_chain: Error scanning {symbol}: {e}")
                        diagnostic_messages.append(f"{symbol}: ERROR - {e!s}")

                # Sort all results by score
                if all_results:
                    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                    # Limit to top N
                    all_results = all_results[:top_candidates]

                # Build response
                if all_results:
                    result_text = f"SCAN RESULTS ({chain})\n"
                    result_text += f"Scanned {len(symbols)} symbols: {', '.join(symbols)}\n"
                    result_text += f"Filters: Delta {delta_min}-{delta_max}, Max {max_expiration_days} DTE, IV≥{iv_min}%\n"
                    result_text += f"\nTop {len(all_results)} Opportunities:\n\n"

                    for i, opp in enumerate(all_results, 1):
                        result_text += f"{i}. {opp.get('symbol')} {opp.get('strike')} (Exp: {opp.get('expiration')})\n"
                        result_text += f"   Delta: {opp.get('delta', 0):.3f} | IV: {opp.get('iv', 0):.1f}% | Score: {opp.get('score', 0):.1f}\n"
                        result_text += f"   Bid: ${opp.get('bid', 0):.2f} | Last: ${opp.get('lastPrice', 0):.2f} | OI: {opp.get('openInterest', 0):,}\n\n"

                    if diagnostic_messages:
                        result_text += "\nDiagnostic Info:\n" + "\n".join(
                            f"  {msg}" for msg in diagnostic_messages
                        )

                    logger.info(
                        f"scan_options_chain: Returning {len(all_results)} total opportunities"
                    )
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": result_text,
                                "data": {
                                    "opportunities": all_results,
                                    "scan_params": params if params else {},
                                },
                            }
                        ],
                        isError=False,
                    )
                # Return detailed diagnostic info when no results found
                diagnostic_text = (
                    "\n\n".join(diagnostic_messages)
                    if diagnostic_messages
                    else "No options data found"
                )
                result_text = f"NO SCAN RESULTS ({chain})\n"
                result_text += f"Scanned {len(symbols)} symbols: {', '.join(symbols)}\n"
                result_text += f"Filters: Delta {delta_min}-{delta_max}, Max {max_expiration_days} DTE, IV≥{iv_min}%\n\n"
                result_text += "DIAGNOSTICS:\n" + diagnostic_text

                logger.info("scan_options_chain: No results, returning diagnostics")
                return ToolCallResponse(
                    content=[{"type": "text", "text": result_text}],
                    isError=False,  # Not an error, just no matches - diagnostics explain why
                )

            # Calculate Extrinsic Value
            if name == "calculate_extrinsic_value":
                ticker = arguments.get("ticker")
                strikes = arguments.get("strikes", [])

                if not ticker:
                    return ToolCallResponse(
                        content=[{"type": "text", "text": "ERROR: Ticker symbol required"}],
                        isError=True,
                    )

                if not strikes:
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": "ERROR: At least one strike price required"}
                        ],
                        isError=True,
                    )

                logger.info(f"calculate_extrinsic_value: ticker={ticker}, strikes={strikes}")

                # Convert strikes list to comma-separated string as expected by ExtrinsicValue
                strikes_str = ",".join(str(s) for s in strikes)

                calc = ExtrinsicValue()
                success, result_text = calc.calculate(ticker, strikes_str)

                if success:
                    # Get structured data for JSON response
                    try:
                        calc_data = calc.as_dict(ticker, strikes_str)
                    except Exception as e:
                        logger.warning(f"Failed to get structured data for {ticker}: {e}")
                        calc_data = None

                    logger.info(f"calculate_extrinsic_value: Successfully calculated for {ticker}")
                    response_content = {
                        "type": "text",
                        "text": f"EXTRINSIC VALUE CALCULATION\n\n{result_text}",
                    }
                    if calc_data:
                        response_content["data"] = calc_data  # type: ignore[assignment]

                    return ToolCallResponse(content=[response_content], isError=False)
                logger.error(f"calculate_extrinsic_value: Failed for {ticker}: {result_text}")
                return ToolCallResponse(
                    content=[{"type": "text", "text": f"ERROR: {result_text}"}], isError=True
                )

            # Calculate Probability of Profit (POP)
            if name == "calculate_probability_of_profit":
                ticker = arguments.get("ticker")
                strike = arguments.get("strike")
                expiration_date = arguments.get("expiration_date")
                option_type = arguments.get("option_type", "PUT").upper()
                premium = arguments.get("premium")
                iv = arguments.get("iv")

                if not ticker or strike is None or not expiration_date:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": "ERROR: ticker, strike, and expiration_date are required",
                            }
                        ],
                        isError=True,
                    )

                logger.info(
                    f"calculate_probability_of_profit: ticker={ticker}, strike={strike}, exp={expiration_date}, type={option_type}, premium={premium}, iv={iv}"
                )

                try:
                    calc = POPCalculator()  # type: ignore[assignment]
                    result = calc.format_pop_result(  # type: ignore[attr-defined]
                        ticker=ticker,
                        strike=strike,
                        expiration_date=expiration_date,
                        option_type=option_type,
                        premium=premium,
                        iv=iv,
                    )

                    formatted_text = calc.format_pop_result(result)  # type: ignore[attr-defined]

                    logger.info(
                        f"calculate_probability_of_profit: Successfully calculated for {ticker} {strike}{option_type}"
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": formatted_text, "data": result}],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(
                        f"calculate_probability_of_profit: Error for {ticker}: {e}", exc_info=True
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"ERROR: {e!s}"}], isError=True
                    )

            # Get Community Messages
            elif name == "get_community_messages":
                guild_id = arguments.get("guild_id")
                days = arguments.get("days", 7)
                ticker = arguments.get("ticker")
                category = arguments.get("category")
                username = arguments.get("username")
                limit = arguments.get("limit", 50)

                if not guild_id:
                    return ToolCallResponse(
                        content=[{"type": "text", "text": "ERROR: guild_id parameter is required"}],
                        isError=True,
                    )

                # Convert guild_id to int
                try:
                    guild_id_int = int(guild_id)
                except ValueError:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"ERROR: Invalid guild_id '{guild_id}' (must be numeric)",
                            }
                        ],
                        isError=True,
                    )

                # Validate category if provided
                if category and category not in ["sentiment", "news"]:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"ERROR: Invalid category '{category}'. Must be 'sentiment' or 'news'",
                            }
                        ],
                        isError=True,
                    )

                # Create pseudonymization context for this request
                salt, username_map = create_pseudonym_context()

                logger.info(
                    f"get_community_messages: guild_id={guild_id}, days={days}, ticker={ticker}, category={category}, username={username}, limit={limit}"
                )

                try:
                    # Calculate date filter (datetime imported at module level)
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    # Build query based on filters
                    if ticker:
                        # Filter by ticker
                        community_messages = self.messages.get_by_ticker(
                            ticker.upper(), limit=limit, guild_id=guild_id_int
                        )
                        # Further filter by date
                        community_messages = [
                            msg for msg in community_messages if msg.timestamp >= cutoff_date
                        ]
                    elif category:
                        # Filter by category (sentiment or news)
                        community_messages = self.messages.get_recent(
                            category=category, limit=limit, guild_id=guild_id_int
                        )
                        community_messages = [
                            msg for msg in community_messages if msg.timestamp >= cutoff_date
                        ]
                    else:
                        # All messages in time window
                        community_messages = self.messages.get_recent(
                            limit=limit, guild_id=guild_id_int
                        )
                        community_messages = [
                            msg for msg in community_messages if msg.timestamp >= cutoff_date
                        ]

                    # Filter by username if specified
                    if username:
                        community_messages = [
                            msg
                            for msg in community_messages
                            if msg.username.lower() == username.lower()
                        ]

                    if not community_messages:
                        filter_desc = (
                            f" for {ticker}"
                            if ticker
                            else f" in category '{category}'"
                            if category
                            else ""
                        )
                        if username:
                            filter_desc += f" from @{username}"
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No community messages found{filter_desc} in the last {days} days",
                                }
                            ],
                            isError=False,
                        )

                    # Format messages (text + JSON)
                    result_text = f"COMMUNITY MESSAGES (Last {days} days)\n"
                    result_text += f"Found {len(community_messages)} messages"
                    if ticker:
                        result_text += f" mentioning ${ticker}"
                    if category:
                        result_text += f" in category '{category}'"
                    if username:
                        result_text += f" from @{username}"
                    result_text += "\n"

                    # Build JSON data array using model's to_dict()
                    messages_data = []

                    # Track which username we're filtering for (if any) to provide mapping
                    requested_username_pseudonym = None

                    # First pass: determine pseudonym for requested username
                    if username and community_messages:
                        first_msg_username = community_messages[0].username
                        requested_username_pseudonym = get_pseudonym(
                            first_msg_username, salt, username_map
                        )

                    # Add pseudonym mapping notice if filtering by username
                    if username and requested_username_pseudonym:
                        result_text += f"\nNOTE: User @{username} appears as @{requested_username_pseudonym} below (privacy pseudonymization).\n"

                    result_text += "\n"

                    for msg in community_messages[:limit]:
                        date = msg.timestamp[:10]  # Just the date
                        # Pseudonymize username in text output
                        pseudonym = get_pseudonym(msg.username, salt, username_map)
                        result_text += f"[{date}] @{pseudonym}:\n"
                        result_text += f"  {msg.content}\n"

                        # Include extracted image data if available
                        if hasattr(msg, "extracted_data") and msg.extracted_data:
                            try:
                                extracted = json.loads(msg.extracted_data)

                                # Only include if we got meaningful data
                                if extracted.get("image_type") != "error" and extracted.get(
                                    "raw_text"
                                ):
                                    result_text += f"\n  [Image Analysis - {extracted.get('image_type', 'unknown')}]\n"

                                    # Include extracted trade details
                                    if extracted.get("raw_text"):
                                        # Limit to first 200 chars to keep context manageable
                                        raw_text = extracted["raw_text"][:200]
                                        if len(extracted["raw_text"]) > 200:
                                            raw_text += "..."
                                        result_text += f"  Extracted: {raw_text}\n"

                                    # Include tickers if found
                                    if extracted.get("tickers") and len(extracted["tickers"]) > 0:
                                        # Filter out noise words
                                        real_tickers = [
                                            t
                                            for t in extracted["tickers"]
                                            if t
                                            not in ["TEXT", "ID", "SOLD", "OCT", "PUTS", "CALL"]
                                        ]
                                        if real_tickers:
                                            result_text += f"  Tickers: {', '.join(real_tickers)}\n"

                            except (json.JSONDecodeError, KeyError) as e:
                                logger.debug(
                                    f"Error parsing extracted_data for message {msg.message_id}: {e}"
                                )

                        result_text += "\n"

                        # Sanitize message for MCP - remove Discord implementation details
                        msg_dict = msg.to_dict()
                        sanitized_msg = {
                            k: v
                            for k, v in msg_dict.items()
                            if k not in ["message_id", "guild_id", "channel_name"]
                        }
                        # Pseudonymize username in JSON data
                        sanitized_msg["username"] = pseudonym
                        messages_data.append(sanitized_msg)

                    # Build response with JSON data field
                    data = {
                        "messages": messages_data,
                        "count": len(messages_data),
                        "time_range": f"Last {days} days",
                        "filters": {"ticker": ticker, "username": username},
                    }

                    # Include reverse mapping for digest generation
                    reverse_map = get_reverse_map(username_map)

                    logger.info(
                        f"get_community_messages: Returning {len(community_messages)} messages ({len(username_map)} unique usernames pseudonymized)"
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": data}],
                        isError=False,
                        pseudonym_map=reverse_map,
                    )

                except Exception as e:
                    logger.error(f"get_community_messages: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR querying community messages: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Community Trades
            elif name == "get_community_trades":
                guild_id = arguments.get("guild_id")
                days = arguments.get("days", 7)
                ticker = arguments.get("ticker")
                username = arguments.get("username")
                limit = arguments.get("limit", 20)

                if not guild_id:
                    return ToolCallResponse(
                        content=[{"type": "text", "text": "ERROR: guild_id parameter is required"}],
                        isError=True,
                    )

                # Convert guild_id to int
                try:
                    guild_id_int = int(guild_id)
                except ValueError:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"ERROR: Invalid guild_id '{guild_id}' (must be numeric)",
                            }
                        ],
                        isError=True,
                    )

                # Create pseudonymization context for this request
                salt, username_map = create_pseudonym_context()

                logger.info(
                    f"get_community_trades: guild_id={guild_id}, days={days}, ticker={ticker}, username={username}, limit={limit}"
                )

                try:
                    # Get messages with extracted trade data
                    messages = Messages(self.db)

                    # Calculate date filter (datetime imported at module level)
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

                    # Query based on filters
                    if ticker:
                        community_messages = messages.get_by_ticker(
                            ticker, limit=1000, guild_id=guild_id_int
                        )
                        # Filter by date
                        community_messages = [
                            msg for msg in community_messages if msg.timestamp >= cutoff_date
                        ]
                    else:
                        community_messages = messages.get_recent(limit=1000, guild_id=guild_id_int)
                        # Filter by date
                        community_messages = [
                            msg for msg in community_messages if msg.timestamp >= cutoff_date
                        ]

                    # Filter by username if specified (case-insensitive)
                    if username:
                        community_messages = [
                            msg
                            for msg in community_messages
                            if msg.username.lower() == username.lower()
                        ]

                    # Extract trades from messages using Message.get_trades()
                    trades_list = []
                    for msg in community_messages:
                        trades_list.extend(msg.get_trades())

                    # Apply limit
                    trades_list = trades_list[:limit]

                    # Build text response
                    result_text = f"COMMUNITY TRADES (Last {days} days)\n"
                    result_text += f"Found {len(trades_list)} trades\n"

                    if ticker:
                        result_text += f"Filtered by ticker: {ticker}\n"
                    if username:
                        result_text += f"Filtered by user: {username}\n"

                    result_text += "\n"

                    for i, trade in enumerate(trades_list, 1):
                        # Format: STO 2x MSTU 11/14 8P @ 0.16
                        op = trade.get("operation", "???")
                        qty = trade.get("quantity", "?")
                        ticker_sym = trade.get("ticker", "???")
                        expiration = trade.get("expiration", "??/??")
                        strike = trade.get("strike", "?")
                        opt_type = trade.get("option_type", "?")
                        premium = trade.get("premium", "?")

                        trade_str = f"{op} {qty}x {ticker_sym} {expiration} {strike}{opt_type}"
                        if premium and premium != "?":
                            trade_str += f" @ {premium}"

                        # Pseudonymize username in text output
                        real_username = trade.get("username", "unknown")
                        pseudonym = get_pseudonym(real_username, salt, username_map)
                        result_text += f"[{trade.get('posted_at', 'N/A')[:10]}] @{pseudonym}:\n"
                        result_text += f"  {trade_str}\n"
                        result_text += f"  Confidence: {trade.get('confidence', 0.0):.0%} | Source: {trade.get('extraction_source')}\n\n"

                    # Sanitize trades for MCP response - remove Discord implementation details
                    sanitized_trades = []
                    for trade in trades_list:
                        sanitized_trade = {
                            k: v for k, v in trade.items() if k not in ["channel", "message_id"]
                        }
                        # Pseudonymize username in JSON data
                        if "username" in sanitized_trade:
                            real_username = sanitized_trade["username"]
                            sanitized_trade["username"] = get_pseudonym(
                                real_username, salt, username_map
                            )
                        sanitized_trades.append(sanitized_trade)

                    # Build JSON data response
                    data = {
                        "trades": sanitized_trades,
                        "count": len(sanitized_trades),
                        "time_range": f"Last {days} days",
                        "filters": {"ticker": ticker, "username": username},
                    }

                    # Include reverse mapping for digest generation
                    reverse_map = get_reverse_map(username_map)

                    logger.info(
                        f"get_community_trades: Returning {len(trades_list)} trades ({len(username_map)} unique usernames pseudonymized)"
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": data}],
                        isError=False,
                        pseudonym_map=reverse_map,
                    )

                except Exception as e:
                    logger.error(f"get_community_trades: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR querying community trades: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Market News
            elif name == "get_market_news":
                ticker = arguments.get("ticker")
                count = arguments.get("count", 5)

                # Cap at 20 articles max
                count = min(count, 20)

                logger.info(f"get_market_news: ticker={ticker}, count={count}")

                if not ticker:
                    return ToolCallResponse(
                        content=[{"type": "text", "text": "ERROR: ticker parameter is required"}],
                        isError=True,
                    )

                try:
                    # Use MarketDataFactory to get news with automatic fallback
                    articles = MarketDataFactory.get_news_with_fallback(ticker.upper(), count=count)

                    if not articles:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No recent news found for {ticker} (last 7 days)",
                                }
                            ],
                            isError=False,
                        )

                    # Build text response (backward compatible)
                    result_text = f"MARKET NEWS - {ticker.upper()} (Last 7 days)\n"
                    result_text += f"Found {len(articles)} articles\n\n"

                    for i, article in enumerate(articles, 1):
                        result_text += f"{i}. {article.get('headline', 'No title')}\n"
                        result_text += f"   Source: {article.get('source', 'Unknown')} | Published: {article.get('published', 'N/A')}\n"
                        if article.get("summary"):
                            summary = (
                                article["summary"][:150] + "..."
                                if len(article.get("summary", "")) > 150
                                else article["summary"]
                            )
                            result_text += f"   {summary}\n"
                        result_text += f"   URL: {article.get('url', 'N/A')}\n\n"

                    # Build JSON data response (for LLM consumption - NO sentiment field)
                    data = {
                        "ticker": ticker.upper(),
                        "articles": [
                            {
                                "headline": article.get("headline", "No title"),
                                "summary": article.get("summary", ""),
                                "source": article.get("source", "Unknown"),
                                "url": article.get("url", ""),
                                "published": article.get("published", ""),
                            }
                            for article in articles
                        ],
                        "count": len(articles),
                        "time_range": "Last 7 days",
                    }

                    logger.info(f"get_market_news: Returning {len(articles)} articles for {ticker}")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": data}], isError=False
                    )

                except Exception as e:
                    logger.error(
                        f"get_market_news: Error fetching news for {ticker}: {e}", exc_info=True
                    )
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"ERROR fetching market news for {ticker}: {e!s}",
                            }
                        ],
                        isError=True,
                    )

            # Get Trending Tickers
            elif name == "get_trending_tickers":
                guild_id = arguments.get("guild_id")
                days = arguments.get("days", 7)
                limit = arguments.get("limit", 20)

                if guild_id is None:
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": "ERROR: guild_id is required for data isolation",
                            }
                        ],
                        isError=True,
                    )

                logger.info(
                    f"get_trending_tickers: guild_id={guild_id}, days={days}, limit={limit}"
                )

                try:
                    # Get ticker stats as dict (following data export pattern)
                    ticker_stats_dict = self.messages.get_ticker_stats_as_dict(
                        guild_id=guild_id, limit=limit
                    )

                    if not ticker_stats_dict:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No trending tickers found in the community knowledge base for guild {guild_id}",
                                }
                            ],
                            isError=False,
                        )

                    # Format result
                    result_text = f"TRENDING TICKERS (Top {len(ticker_stats_dict)})\n"
                    result_text += "Based on community discussion frequency\n\n"

                    for i, ticker_data in enumerate(ticker_stats_dict, 1):
                        result_text += f"{i:2d}. ${ticker_data['ticker']}: {ticker_data['mentions']} mentions\n"

                    # Log the actual data for debugging hallucinations
                    top_5 = ticker_stats_dict[:5]
                    logger.info(
                        f"get_trending_tickers: Returning {len(ticker_stats_dict)} trending tickers for guild {guild_id}"
                    )
                    logger.info(f"get_trending_tickers: Top 5 tickers = {top_5}")

                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": result_text,
                                "data": {"tickers": ticker_stats_dict},
                            }
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_trending_tickers: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting trending tickers: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Community Channels
            elif name == "get_community_channels":
                logger.info("get_community_channels: Fetching channel stats")

                try:
                    channel_stats = self.messages.get_channel_stats()

                    if not channel_stats:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": "No channels found in community knowledge base",
                                }
                            ],
                            isError=False,
                        )

                    # Format result
                    result_text = "COMMUNITY CHANNELS\n\n"
                    for channel, stats in channel_stats.items():
                        result_text += (
                            f"• {channel}: {stats['total']} messages ({stats['active']} active)\n"
                        )

                    logger.info(f"get_community_channels: Returning {len(channel_stats)} channels")
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": result_text,
                                "data": {"channels": channel_stats},
                            }
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_community_channels: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"ERROR getting channels: {e!s}"}],
                        isError=True,
                    )

            # Get Historical Stock Prices
            elif name == "get_historical_stock_prices":
                ticker = arguments.get("ticker")
                period = arguments.get("period", "1mo")
                interval = arguments.get("interval", "1d")

                logger.info(
                    f"get_historical_stock_prices: {ticker}, period={period}, interval={interval}"
                )

                try:
                    provider = YFinanceProvider()
                    df = provider.get_historical_data(ticker, period, interval)  # type: ignore[arg-type]

                    if df.empty:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No historical data available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    # Convert DataFrame to readable text format
                    result_text = f"HISTORICAL PRICES FOR {ticker.upper()}\n"  # type: ignore[union-attr]
                    result_text += f"Period: {period}, Interval: {interval}\n\n"
                    result_text += df.to_string()

                    logger.info(f"get_historical_stock_prices: Returning {len(df)} data points")
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": result_text, "data": df.to_dict("records")}
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_historical_stock_prices: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting historical prices: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Stock Actions (Dividends and Splits)
            elif name == "get_stock_actions":
                ticker = arguments.get("ticker")
                action_type = arguments.get("action_type", "all")

                logger.info(f"get_stock_actions: {ticker}, type={action_type}")

                try:
                    provider = YFinanceProvider()

                    if action_type == "dividends":
                        df = provider.get_dividends(ticker)  # type: ignore[arg-type]
                        title = "DIVIDEND HISTORY"
                    elif action_type == "splits":
                        df = provider.get_splits(ticker)  # type: ignore[arg-type]
                        title = "STOCK SPLIT HISTORY"
                    else:  # all
                        df = provider.get_actions(ticker)  # type: ignore[arg-type]
                        title = "STOCK ACTIONS (DIVIDENDS & SPLITS)"

                    if df.empty:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No {action_type} data available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    result_text = f"{title} FOR {ticker.upper()}\n\n"  # type: ignore[union-attr]
                    result_text += df.to_string()

                    logger.info(f"get_stock_actions: Returning {len(df)} records")
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": result_text, "data": df.to_dict("records")}
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_stock_actions: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"ERROR getting stock actions: {e!s}"}],
                        isError=True,
                    )

            # Get Financial Statement
            elif name == "get_financial_statement":
                ticker = arguments.get("ticker")
                statement_type = arguments.get("statement_type", "income")
                period = arguments.get("period", "annual")

                logger.info(
                    f"get_financial_statement: {ticker}, type={statement_type}, period={period}"
                )

                try:
                    provider = YFinanceProvider()
                    df = provider.get_financials(ticker, statement_type, period)  # type: ignore[arg-type]

                    if df.empty:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No {period} {statement_type} statement available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    statement_names = {
                        "income": "INCOME STATEMENT",
                        "balance": "BALANCE SHEET",
                        "cash": "CASH FLOW STATEMENT",
                    }
                    title = statement_names.get(statement_type, "FINANCIAL STATEMENT")

                    result_text = f"{title} FOR {ticker.upper()}\n"  # type: ignore[union-attr]
                    result_text += f"Period: {period.capitalize()}\n\n"
                    result_text += df.to_string()

                    logger.info(
                        f"get_financial_statement: Returning statement with {df.shape[0]} rows, {df.shape[1]} periods"
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": df.to_dict()}],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_financial_statement: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting financial statement: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Holder Information
            elif name == "get_holder_info":
                ticker = arguments.get("ticker")
                holder_type = arguments.get("holder_type", "institutional")

                logger.info(f"get_holder_info: {ticker}, type={holder_type}")

                try:
                    provider = YFinanceProvider()
                    df = provider.get_holders(ticker, holder_type)  # type: ignore[arg-type]

                    if df.empty:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No {holder_type} holder data available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    holder_names = {
                        "institutional": "INSTITUTIONAL HOLDERS",
                        "mutualfund": "MUTUAL FUND HOLDERS",
                        "major": "MAJOR HOLDERS",
                        "insider": "INSIDER TRANSACTIONS",
                    }
                    title = holder_names.get(holder_type, "HOLDERS")

                    result_text = f"{title} FOR {ticker.upper()}\n\n"  # type: ignore[union-attr]
                    result_text += df.to_string()

                    logger.info(f"get_holder_info: Returning {len(df)} records")
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": result_text, "data": df.to_dict("records")}
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_holder_info: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"ERROR getting holder info: {e!s}"}],
                        isError=True,
                    )

            # Get Analyst Recommendations
            elif name == "get_analyst_recommendations":
                ticker = arguments.get("ticker")

                logger.info(f"get_analyst_recommendations: {ticker}")

                try:
                    provider = YFinanceProvider()
                    df = provider.get_recommendations(ticker)  # type: ignore[arg-type]

                    if df.empty:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No analyst recommendations available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    result_text = f"ANALYST RECOMMENDATIONS FOR {ticker.upper()}\n\n"  # type: ignore[union-attr]
                    result_text += df.to_string()

                    logger.info(f"get_analyst_recommendations: Returning {len(df)} recommendations")
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": result_text, "data": df.to_dict("records")}
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_analyst_recommendations: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": f"ERROR getting analyst recommendations: {e!s}",
                            }
                        ],
                        isError=True,
                    )

            # Get Option Expiration Dates
            elif name == "get_option_expiration_dates":
                ticker = arguments.get("ticker")

                logger.info(f"get_option_expiration_dates: {ticker}")

                try:
                    provider = YFinanceProvider()
                    expirations = provider.get_option_expiration_dates(ticker)  # type: ignore[arg-type]

                    if not expirations:
                        return ToolCallResponse(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"No options expiration dates available for {ticker}",
                                }
                            ],
                            isError=False,
                        )

                    result_text = f"OPTIONS EXPIRATION DATES FOR {ticker.upper()}\n\n"  # type: ignore[union-attr]
                    for exp in expirations:
                        result_text += f"• {exp}\n"

                    logger.info(f"get_option_expiration_dates: Returning {len(expirations)} dates")
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": result_text,
                                "data": {"expirations": expirations},
                            }
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_option_expiration_dates: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting expiration dates: {e!s}"}
                        ],
                        isError=True,
                    )

            # Get Detailed Option Chain
            elif name == "get_detailed_option_chain":
                ticker = arguments.get("ticker")
                expiration_date = arguments.get("expiration_date")

                logger.info(f"get_detailed_option_chain: {ticker}, expiration={expiration_date}")

                try:
                    provider = YFinanceProvider()
                    chain_data = provider.get_options_chain(ticker)  # type: ignore[arg-type]

                    if not chain_data or "data" not in chain_data:
                        return ToolCallResponse(
                            content=[
                                {"type": "text", "text": f"No options chain available for {ticker}"}
                            ],
                            isError=False,
                        )

                    # Filter by expiration if specified
                    if expiration_date:
                        filtered_data = [
                            exp
                            for exp in chain_data["data"]
                            if exp["expirationDate"] == expiration_date
                        ]
                        if not filtered_data:
                            return ToolCallResponse(
                                content=[
                                    {
                                        "type": "text",
                                        "text": f"No options found for {ticker} expiring on {expiration_date}",
                                    }
                                ],
                                isError=False,
                            )
                        chain_data["data"] = filtered_data

                    # Format results
                    result_text = f"OPTIONS CHAIN FOR {ticker.upper()}\n\n"  # type: ignore[union-attr]
                    for exp_data in chain_data["data"]:
                        exp_date = exp_data["expirationDate"]
                        calls = exp_data["options"]["CALL"]
                        puts = exp_data["options"]["PUT"]

                        result_text += f"Expiration: {exp_date}\n"
                        result_text += (
                            f"Calls: {len(calls)} contracts, Puts: {len(puts)} contracts\n\n"
                        )

                    logger.info(
                        f"get_detailed_option_chain: Returning chain with {len(chain_data['data'])} expirations"
                    )
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": chain_data}],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_detailed_option_chain: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[{"type": "text", "text": f"ERROR getting options chain: {e!s}"}],
                        isError=True,
                    )

            elif name == "get_market_sentiment":
                logger.info("get_market_sentiment: Fetching sentiment indicators")

                try:
                    if not self.sentiment:
                        return ToolCallResponse(
                            content=[
                                {"type": "text", "text": "Market sentiment provider not available"}
                            ],
                            isError=True,
                        )

                    # Get formatted table and structured data
                    table_str = self.sentiment.as_table()
                    sentiment_data = self.sentiment.as_dict()

                    result_text = "MARKET SENTIMENT INDICATORS\n\n"
                    result_text += table_str
                    result_text += f"\n\nSummary: {sentiment_data['summary']}"

                    logger.info("get_market_sentiment: Successfully retrieved sentiment data")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": sentiment_data}],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_market_sentiment: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting market sentiment: {e!s}"}
                        ],
                        isError=True,
                    )

            elif name == "get_technical_analysis":
                ticker = arguments.get("ticker", "").upper()
                period = arguments.get("period", "3mo")
                interval = arguments.get("interval", "1d")
                include_patterns = arguments.get("include_patterns", True)

                logger.info(
                    f"get_technical_analysis: ticker={ticker}, period={period}, interval={interval}, patterns={include_patterns}"
                )

                try:
                    ta_service = get_ta_service()
                    ta_result = ta_service.get_technical_analysis(
                        ticker=ticker,
                        period=period,
                        interval=interval,
                        include_patterns=include_patterns,
                    )

                    if "error" in ta_result:
                        return ToolCallResponse(
                            content=[{"type": "text", "text": f"ERROR: {ta_result['error']}"}],
                            isError=True,
                        )

                    # Format response with interpretation (for LLM readability)
                    result_text = ta_result.get("interpretation", "")

                    logger.info(f"get_technical_analysis: Successfully analyzed {ticker}")
                    return ToolCallResponse(
                        content=[
                            {
                                "type": "text",
                                "text": result_text,
                                "data": ta_result,  # Full structured data
                            }
                        ],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_technical_analysis: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting technical analysis: {e!s}"}
                        ],
                        isError=True,
                    )

            elif name == "get_technical_summary":
                ticker = arguments.get("ticker", "").upper()

                logger.info(f"get_technical_summary: ticker={ticker}")

                try:
                    ta_service = get_ta_service()
                    signals_result = ta_service.get_technical_summary(ticker=ticker)

                    if "error" in signals_result:
                        return ToolCallResponse(
                            content=[{"type": "text", "text": f"ERROR: {signals_result['error']}"}],
                            isError=True,
                        )

                    # Format technical summary for LLM
                    overall = signals_result["overall_signal"]
                    signals = signals_result["key_signals"]
                    price_info = signals_result["price_info"]

                    result_text = f"**Technical Summary: ${ticker}**\n\n"
                    result_text += f"Overall: **{overall}** ({signals_result['bullish_signals']} bullish, {signals_result['bearish_signals']} bearish)\n"
                    result_text += f"Price: ${price_info['price']:.2f} ({price_info['change_percent']:+.2f}%)\n\n"
                    result_text += "Key Signals:\n"
                    for signal in signals:
                        result_text += f"- {signal}\n"

                    logger.info(f"get_technical_summary: {ticker} is {overall}")
                    return ToolCallResponse(
                        content=[{"type": "text", "text": result_text, "data": signals_result}],
                        isError=False,
                    )

                except Exception as e:
                    logger.error(f"get_technical_summary: Error: {e}", exc_info=True)
                    return ToolCallResponse(
                        content=[
                            {"type": "text", "text": f"ERROR getting technical summary: {e!s}"}
                        ],
                        isError=True,
                    )

            return ToolCallResponse(
                content=[{"type": "text", "text": f"Tool '{name}' not implemented"}], isError=True
            )

        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            return ToolCallResponse(
                content=[{"type": "text", "text": f"Error executing tool: {e!s}"}], isError=True
            )

    def get_resource(self, uri: str) -> ResourceResponse:
        """Retrieve a resource by URI"""
        if uri not in self.resources:
            raise HTTPException(status_code=404, detail=f"Resource '{uri}' not found")

        try:
            # Database Schema
            if uri == "trades://schema":
                schema_info = {
                    "trades": {
                        "columns": [
                            "id",
                            "username",
                            "guild_id",
                            "account",
                            "date",
                            "raw_trade",
                            "operation",
                            "contracts",
                            "symbol",
                            "expiration_date",
                            "strike_price",
                            "option_type",
                            "premium",
                            "total",
                        ],
                        "description": "Options trades including STO, BTC, BTO, STC operations",
                    },
                    "shares": {
                        "columns": [
                            "id",
                            "username",
                            "guild_id",
                            "account",
                            "date",
                            "action",
                            "symbol",
                            "price",
                            "quantity",
                            "amount",
                        ],
                        "description": "Stock buy/sell transactions",
                    },
                    "dividends": {
                        "columns": [
                            "id",
                            "username",
                            "guild_id",
                            "account",
                            "date",
                            "symbol",
                            "amount",
                        ],
                        "description": "Dividend payments",
                    },
                    "deposits": {
                        "columns": [
                            "id",
                            "username",
                            "guild_id",
                            "account",
                            "action",
                            "date",
                            "amount",
                        ],
                        "description": "Deposits and withdrawals",
                    },
                    "watchlist": {
                        "columns": ["id", "username", "guild_id", "symbol"],
                        "description": "User watchlist symbols",
                    },
                }
                return ResourceResponse(
                    contents=[
                        {"uri": uri, "mimeType": "application/json", "text": str(schema_info)}
                    ]
                )

            # All Users
            if uri == "trades://users":
                query = "SELECT DISTINCT username FROM trades UNION SELECT DISTINCT username FROM shares"
                users = self.db.query_parameterized(query)
                user_list = [u[0] for u in users]
                return ResourceResponse(
                    contents=[
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": str({"users": user_list}),
                        }
                    ]
                )

            return ResourceResponse(contents=[])

        except Exception as e:
            logger.error(f"Error retrieving resource '{uri}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error retrieving resource: {e!s}")

    def execute_prompt(self, name: str, arguments: dict[str, Any] | None = None) -> PromptResponse:
        """Execute a prompt by name"""
        if name not in self.prompts:
            raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

        args = arguments or {}

        try:
            # Analyze Trading Performance
            if name == "analyze_trading_performance":
                username = args.get("username", "")
                time_period = args.get("time_period", "this year")
                prompt_text = f"""Analyze the trading performance for user '{username}' for {time_period}.

Please provide:
1. Overall profitability analysis (premiums collected vs paid)
2. Most profitable symbols and strategies
3. Win rate and average return per trade
4. Risk assessment based on position sizing
5. Recommendations for improvement

Use the query_trades, query_dividends, and get_user_statistics tools to gather the necessary data."""

                return PromptResponse(
                    messages=[{"role": "user", "content": {"type": "text", "text": prompt_text}}]
                )

            # Watchlist Analysis
            if name == "watchlist_analysis":
                username = args.get("username", "")
                prompt_text = f"""Analyze the watchlist and recent trading activity for user '{username}'.

Please provide:
1. List of symbols on the watchlist
2. Recent trades for watchlist symbols
3. Performance metrics for each watchlist symbol
4. Recommendations for which symbols to actively trade
5. Suggestions for adding or removing symbols from the watchlist

Use the query_watchlist and query_trades tools to gather the necessary data."""

                return PromptResponse(
                    messages=[{"role": "user", "content": {"type": "text", "text": prompt_text}}]
                )

            # Portfolio Overview
            if name == "portfolio_overview":
                username = args.get("username", "")
                prompt_text = f"""Generate a comprehensive portfolio overview for user '{username}'.

Please include:
1. Summary of all options trades (STO, BTC, BTO, STC)
2. Stock positions and share transactions
3. Dividend income summary
4. Deposits and withdrawals
5. Current watchlist
6. Overall portfolio performance metrics
7. Risk exposure analysis
8. Strategic recommendations

Use the query_trades, query_shares, query_dividends, query_deposits, query_watchlist, and get_user_statistics tools to compile a complete portfolio view."""

                return PromptResponse(
                    messages=[{"role": "user", "content": {"type": "text", "text": prompt_text}}]
                )

            return PromptResponse(messages=[])

        except Exception as e:
            logger.error(f"Error executing prompt '{name}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error executing prompt: {e!s}")


# Initialize MCP Server
mcp_server = MCPServer()

# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "name": "Options Trading Bot MCP Server",
        "version": "1.0.0",
        "protocolVersion": "2024-11-05",
        "description": "MCP server providing access to options trading data, market data (quotes, historical prices, options chains), fundamental data (financials, dividends, holders, analyst recommendations), and community knowledge",
        "capabilities": {
            "tools": {"available": len(mcp_server.tools), "list": list(mcp_server.tools.keys())},
            "resources": {
                "available": len(mcp_server.resources),
                "list": list(mcp_server.resources.keys()),
            },
            "prompts": {
                "available": len(mcp_server.prompts),
                "list": list(mcp_server.prompts.keys()),
            },
        },
    }


@app.get("/tools/list", response_model=dict[str, list[Tool]])
async def list_tools():
    """List all available tools"""
    return {"tools": list(mcp_server.tools.values())}


@app.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    """Execute a tool"""
    return mcp_server.execute_tool(request.name, request.arguments)


@app.get("/resources/list", response_model=dict[str, list[Resource]])
async def list_resources():
    """List all available resources"""
    return {"resources": list(mcp_server.resources.values())}


@app.post("/resources/read", response_model=ResourceResponse)
async def read_resource(request: ResourceRequest):
    """Read a resource"""
    return mcp_server.get_resource(request.uri)


@app.get("/prompts/list", response_model=dict[str, list[Prompt]])
async def list_prompts():
    """List all available prompts"""
    return {"prompts": list(mcp_server.prompts.values())}


@app.post("/prompts/get", response_model=PromptResponse)
async def get_prompt(request: PromptRequest):
    """Get a prompt"""
    return mcp_server.execute_prompt(request.name, request.arguments)


@app.get("/health")
async def health_check():
    """Health check endpoint with startup time"""
    uptime = None
    if SERVER_START_TIME:
        uptime_delta = datetime.now() - datetime.strptime(SERVER_START_TIME, "%Y-%m-%d %H:%M:%S")
        uptime = str(uptime_delta).split(".")[0]  # Remove microseconds

    return {
        "status": "healthy",
        "startup_time": SERVER_START_TIME,
        "uptime": uptime,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================================
# Individual Tool Endpoints (OpenAPI-compatible wrappers)
# ============================================================================


class QueryWatchlistRequest(BaseModel):
    """Request model for querying watchlist"""

    username: str = Field(..., description="Username to query watchlist for")
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")


class QueryTradesRequest(BaseModel):
    """Request model for querying trades"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich"},
                {"username": "sangelovich", "account": "Joint"},
                {
                    "username": "sangelovich",
                    "symbol": "HOOD",
                    "start_date": "2025-10-01",
                    "end_date": "2025-10-31",
                },
            ]
        }
    )

    username: str = Field(..., description="Username to query trades for", examples=["sangelovich"])
    symbol: str | None = Field(
        None,
        description="Optional ticker symbol to filter by (e.g., 'HOOD'). Omit this field entirely if not filtering by symbol.",
    )
    start_date: str | None = Field(
        None,
        description="Optional start date in YYYY-MM-DD format (e.g., '2025-01-01'). Omit this field entirely if not filtering by date.",
    )
    end_date: str | None = Field(
        None,
        description="Optional end date in YYYY-MM-DD format (e.g., '2025-12-31'). Omit this field entirely if not filtering by date.",
    )
    account: str | None = Field(
        None,
        description="Optional account name to filter by (e.g., 'Joint', 'Roth IRA'). Omit this field entirely if not filtering by account.",
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.symbol == "":
            self.symbol = None
        if self.start_date == "":
            self.start_date = None
        if self.end_date == "":
            self.end_date = None
        if self.account == "":
            self.account = None


class QuerySharesRequest(BaseModel):
    """Request model for querying shares"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich"},
                {"username": "sangelovich", "account": "Joint"},
            ]
        }
    )

    username: str = Field(..., description="Username to query shares for", examples=["sangelovich"])
    symbol: str | None = Field(
        None, description="Optional ticker symbol to filter by. Omit if not filtering."
    )
    start_date: str | None = Field(
        None, description="Optional start date in YYYY-MM-DD format. Omit if not filtering."
    )
    end_date: str | None = Field(
        None, description="Optional end date in YYYY-MM-DD format. Omit if not filtering."
    )
    account: str | None = Field(
        None, description="Optional account name to filter by. Omit if not filtering."
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.symbol == "":
            self.symbol = None
        if self.start_date == "":
            self.start_date = None
        if self.end_date == "":
            self.end_date = None
        if self.account == "":
            self.account = None


class QueryDividendsRequest(BaseModel):
    """Request model for querying dividends"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich"},
                {"username": "sangelovich", "account": "Joint"},
            ]
        }
    )

    username: str = Field(
        ..., description="Username to query dividends for", examples=["sangelovich"]
    )
    symbol: str | None = Field(
        None, description="Optional ticker symbol to filter by. Omit if not filtering."
    )
    start_date: str | None = Field(
        None, description="Optional start date in YYYY-MM-DD format. Omit if not filtering."
    )
    end_date: str | None = Field(
        None, description="Optional end date in YYYY-MM-DD format. Omit if not filtering."
    )
    account: str | None = Field(
        None, description="Optional account name to filter by. Omit if not filtering."
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.symbol == "":
            self.symbol = None
        if self.start_date == "":
            self.start_date = None
        if self.end_date == "":
            self.end_date = None
        if self.account == "":
            self.account = None


class QueryDepositsRequest(BaseModel):
    """Request model for querying deposits"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich"},
                {"username": "sangelovich", "account": "Joint"},
            ]
        }
    )

    username: str = Field(
        ..., description="Username to query deposits for", examples=["sangelovich"]
    )
    start_date: str | None = Field(
        None, description="Optional start date in YYYY-MM-DD format. Omit if not filtering."
    )
    end_date: str | None = Field(
        None, description="Optional end date in YYYY-MM-DD format. Omit if not filtering."
    )
    account: str | None = Field(
        None, description="Optional account name to filter by. Omit if not filtering."
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.start_date == "":
            self.start_date = None
        if self.end_date == "":
            self.end_date = None
        if self.account == "":
            self.account = None


class AddToWatchlistRequest(BaseModel):
    """Request model for adding to watchlist"""

    username: str = Field(..., description="Username to add symbol for")
    symbol: str = Field(..., description="Ticker symbol to add (e.g., 'AAPL')")
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")


class RemoveFromWatchlistRequest(BaseModel):
    """Request model for removing from watchlist"""

    username: str = Field(..., description="Username to remove symbol for")
    symbol: str = Field(..., description="Ticker symbol to remove")
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")


class GetUserStatisticsRequest(BaseModel):
    """Request model for getting user statistics - provides comprehensive monthly trading summary with premiums and dividends"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich", "guild_id": 1405962109262757980},
                {"username": "sangelovich", "guild_id": 1405962109262757980, "year": 2025},
                {
                    "username": "sangelovich",
                    "guild_id": 1405962109262757980,
                    "account": "Joint",
                    "year": 2025,
                },
            ]
        }
    )

    username: str = Field(
        ..., description="Username to get statistics for", examples=["sangelovich"]
    )
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")
    year: int | None = Field(
        None,
        description="Optional year to filter by (defaults to current year). Use 2025 for current year data.",
    )
    account: str | None = Field(
        None,
        description="Optional account name to filter by (e.g., 'Joint', 'Roth IRA'). Omit to get all accounts.",
    )


class GetSymbolStatisticsRequest(BaseModel):
    """Request model for getting symbol statistics"""

    username: str = Field(..., description="Username to get statistics for")
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")
    year: int | None = Field(
        None, description="Optional year to filter by (defaults to current year)"
    )
    month: int | None = Field(
        None, description="Optional month to filter by (1-12, defaults to current month)"
    )
    account: str | None = Field(None, description="Optional account name to filter by")


class ListPopularSymbolsRequest(BaseModel):
    """Request model for listing popular symbols"""

    username: str | None = Field(None, description="Optional username to filter by")
    days: int | None = Field(7, description="Number of days to look back (default: 7)")


class GetPortfolioOverviewRequest(BaseModel):
    """Request model for getting complete portfolio overview"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich", "guild_id": 1405962109262757980},
                {
                    "username": "sangelovich",
                    "guild_id": 1405962109262757980,
                    "account": "Joint",
                    "year": 2025,
                },
                {
                    "username": "sangelovich",
                    "guild_id": 1405962109262757980,
                    "include": ["shares", "deposits"],
                },
            ]
        }
    )

    username: str = Field(
        ..., description="Username to get portfolio for", examples=["sangelovich"]
    )
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")
    account: str | None = Field(
        None,
        description="Optional account name to filter by (e.g., 'Joint', 'Roth IRA'). Omit if not filtering.",
    )
    year: int | None = Field(
        None,
        description="Optional year to filter by (defaults to current year). Use 2025 for current year data.",
    )
    include: list[str] | None = Field(
        None,
        description="Optional list of sections to include: 'options', 'shares', 'deposits'. Omit or use empty list to include all sections. Use this to reduce response size when only specific data is needed.",
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.account == "":
            self.account = None


@app.post("/tools/query_watchlist", response_model=ToolCallResponse)
async def query_watchlist_endpoint(request: QueryWatchlistRequest):
    """Get the list of symbols on a user's watchlist"""
    return mcp_server.execute_tool(
        "query_watchlist", {"username": request.username, "guild_id": request.guild_id}
    )


@app.post("/tools/query_trades", response_model=ToolCallResponse)
async def query_trades_endpoint(request: QueryTradesRequest):
    """Query individual options trades with detailed transaction data. Use get_user_statistics for summaries."""
    return mcp_server.execute_tool(
        "query_trades",
        {
            "username": request.username,
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "account": request.account,
        },
    )


@app.post("/tools/query_shares", response_model=ToolCallResponse)
async def query_shares_endpoint(request: QuerySharesRequest):
    """Query share transactions for a user, optionally filtered by symbol, date range, and account"""
    return mcp_server.execute_tool(
        "query_shares",
        {
            "username": request.username,
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "account": request.account,
        },
    )


@app.post("/tools/query_dividends", response_model=ToolCallResponse)
async def query_dividends_endpoint(request: QueryDividendsRequest):
    """Query dividend payments for a user, optionally filtered by symbol, date range, and account"""
    return mcp_server.execute_tool(
        "query_dividends",
        {
            "username": request.username,
            "symbol": request.symbol,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "account": request.account,
        },
    )


@app.post("/tools/query_deposits", response_model=ToolCallResponse)
async def query_deposits_endpoint(request: QueryDepositsRequest):
    """Query deposits and withdrawals for a user, optionally filtered by date range and account"""
    return mcp_server.execute_tool(
        "query_deposits",
        {
            "username": request.username,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "account": request.account,
        },
    )


@app.post("/tools/add_to_watchlist", response_model=ToolCallResponse)
async def add_to_watchlist_endpoint(request: AddToWatchlistRequest):
    """Add a symbol to a user's watchlist"""
    return mcp_server.execute_tool(
        "add_to_watchlist",
        {"username": request.username, "symbol": request.symbol, "guild_id": request.guild_id},
    )


@app.post("/tools/remove_from_watchlist", response_model=ToolCallResponse)
async def remove_from_watchlist_endpoint(request: RemoveFromWatchlistRequest):
    """Remove a symbol from a user's watchlist"""
    return mcp_server.execute_tool(
        "remove_from_watchlist",
        {"username": request.username, "symbol": request.symbol, "guild_id": request.guild_id},
    )


@app.post("/tools/get_user_statistics", response_model=ToolCallResponse)
async def get_user_statistics_endpoint(request: GetUserStatisticsRequest):
    """BEST TOOL FOR SUMMARIES: Get comprehensive trading statistics with monthly breakdown of all options premiums (STO/BTC/BTO/STC) and dividends. Returns formatted table with totals. Use this tool when asked to 'review', 'summarize', or 'analyze' trading activity."""
    return mcp_server.execute_tool(
        "get_user_statistics",
        {
            "username": request.username,
            "year": request.year,
            "account": request.account,
            "guild_id": request.guild_id,
        },
    )


@app.post("/tools/get_symbol_statistics", response_model=ToolCallResponse)
async def get_symbol_statistics_endpoint(request: GetSymbolStatisticsRequest):
    """Get aggregated trading data for a specific symbol"""
    return mcp_server.execute_tool(
        "get_symbol_statistics",
        {
            "username": request.username,
            "year": request.year,
            "month": request.month,
            "account": request.account,
            "guild_id": request.guild_id,
        },
    )


@app.post("/tools/list_popular_symbols", response_model=ToolCallResponse)
async def list_popular_symbols_endpoint(request: ListPopularSymbolsRequest):
    """Get list of most popular traded symbols, optionally filtered by user and time period"""
    return mcp_server.execute_tool(
        "list_popular_symbols", {"username": request.username, "days": request.days}
    )


@app.post("/tools/get_portfolio_overview", response_model=ToolCallResponse)
async def get_portfolio_overview_endpoint(request: GetPortfolioOverviewRequest):
    """COMPLETE PORTFOLIO: Get comprehensive overview including options, shares, dividends, and deposits. Use when asked for 'complete', 'full', 'comprehensive', or 'all' data. Use 'include' parameter to filter specific sections and reduce response size."""
    return mcp_server.execute_tool(
        "get_portfolio_overview",
        {
            "username": request.username,
            "account": request.account,
            "year": request.year,
            "guild_id": request.guild_id,
            "include": request.include,
        },
    )


class GetMarketNewsRequest(BaseModel):
    """Request model for getting market news"""

    ticker: str = Field(..., description="Stock ticker symbol (e.g., 'MSTX', 'HOOD')")
    count: int = Field(5, description="Number of articles to return (default: 5, max: 20)")


class GetCommunityMessagesRequest(BaseModel):
    """Request model for getting community messages"""

    guild_id: str = Field(..., description="Discord guild/server ID (required for data isolation)")
    days: int = Field(7, description="Number of days to look back (default: 7)")
    ticker: str | None = Field(
        None, description="Optional ticker symbol to filter by (e.g., 'MSTX', 'HOOD')"
    )
    category: str | None = Field(
        None,
        description="Optional category to filter by: 'sentiment' (trading discussions) or 'news' (market updates)",
    )
    username: str | None = Field(None, description="Optional username to filter by")
    limit: int = Field(50, description="Maximum number of messages to return (default: 50)")


class GetCommunityTradesRequest(BaseModel):
    """Request model for getting community trades extracted from messages"""

    guild_id: str = Field(..., description="Discord guild/server ID (required for data isolation)")
    days: int = Field(7, description="Number of days to look back (default: 7)")
    ticker: str | None = Field(
        None, description="Optional ticker symbol to filter by (e.g., 'MSTX', 'HOOD')"
    )
    username: str | None = Field(None, description="Optional username to filter by")
    limit: int = Field(20, description="Maximum number of trades to return (default: 20)")


class GetCurrentPositionsRequest(BaseModel):
    """Request model for getting current positions"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"username": "sangelovich", "guild_id": 1405962109262757980},
                {"username": "sangelovich", "guild_id": 1405962109262757980, "account": "IRA"},
                {"username": "sangelovich", "guild_id": 1405962109262757980, "symbol": "MSTX"},
                {"username": "sangelovich", "guild_id": 1405962109262757980, "account": "ALL"},
            ]
        }
    )

    username: str = Field(
        ..., description="Username to get positions for", examples=["sangelovich"]
    )
    guild_id: int = Field(..., description="Guild ID (required for data isolation)")
    account: str | None = Field(
        None,
        description="Account to filter by (e.g., 'IRA', 'Joint'). Use 'ALL' or omit for all accounts aggregated.",
    )
    symbol: str | None = Field(
        None, description="Optional symbol to filter by (e.g., 'MSTX'). Omit for all symbols."
    )

    def model_post_init(self, __context):
        # Convert empty strings to None
        if self.symbol == "":
            self.symbol = None
        if self.account == "":
            self.account = None


@app.post("/tools/get_market_news", response_model=ToolCallResponse)
async def get_market_news_endpoint(request: GetMarketNewsRequest):
    """MARKET NEWS: Get recent market news articles for a ticker from Yahoo Finance/Finnhub (last 7 days). Returns article headlines, summaries, URLs, and publication timestamps."""
    return mcp_server.execute_tool(
        "get_market_news", {"ticker": request.ticker, "count": request.count}
    )


@app.post("/tools/get_community_messages", response_model=ToolCallResponse)
async def get_community_messages_endpoint(request: GetCommunityMessagesRequest):
    """COMMUNITY MESSAGES: Query community Discord messages from the knowledge base. Returns recent messages with metadata (user, content, tickers mentioned). Filter by category: 'sentiment' for trading discussions, 'news' for market updates. Guild-scoped for data isolation."""
    return mcp_server.execute_tool(
        "get_community_messages",
        {
            "guild_id": request.guild_id,
            "days": request.days,
            "ticker": request.ticker,
            "category": request.category,
            "username": request.username,
            "limit": request.limit,
        },
    )


@app.post("/tools/get_community_trades", response_model=ToolCallResponse)
async def get_community_trades_endpoint(request: GetCommunityTradesRequest):
    """COMMUNITY TRADES: Get structured trades extracted from Discord messages (text + OCR). Returns only messages with parsed trade details (BTO/STO/BTC/STC operations). Guild-scoped for data isolation."""
    return mcp_server.execute_tool(
        "get_community_trades",
        {
            "guild_id": request.guild_id,
            "days": request.days,
            "ticker": request.ticker,
            "username": request.username,
            "limit": request.limit,
        },
    )


@app.post("/tools/get_current_positions", response_model=ToolCallResponse)
async def get_current_positions_endpoint(request: GetCurrentPositionsRequest):
    """CURRENT POSITIONS: Get current stock holdings and open option positions with live market values, cost basis, and unrealized P/L. Shows net positions aggregated across ALL accounts by default, or filtered to specific account."""
    return mcp_server.execute_tool(
        "get_current_positions",
        {
            "username": request.username,
            "account": request.account,
            "symbol": request.symbol,
            "guild_id": request.guild_id,
        },
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # Set startup time (module-level variable declared at top)
    SERVER_START_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info("=" * 60)
    logger.info("Starting Options Trading Bot MCP Server")
    logger.info(f"STARTUP TIME: {SERVER_START_TIME}")
    logger.info(f"Logging to: {const.API_LOG_FILE}")
    logger.info("Server will run on: http://0.0.0.0:8000")
    logger.info("=" * 60)

    # Print to console as well for visibility
    print("\n" + "=" * 60)
    print("🚀 MCP SERVER STARTED")
    print(f"📅 STARTUP TIME: {SERVER_START_TIME}")
    print("🌐 Server: http://0.0.0.0:8000")
    print(f"📝 Logs: {const.API_LOG_FILE}")
    print("💡 Health check: http://localhost:8000/health")
    print("=" * 60 + "\n")

    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        raise
