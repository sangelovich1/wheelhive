#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import os

# Database
# Use absolute path to ensure all components (Discord bot, MCP server, CLI) use the same database
import pathlib

import discord
from dotenv import load_dotenv


PROJECT_ROOT = pathlib.Path(__file__).parent.parent.absolute()
DATABASE_PATH = str(PROJECT_ROOT / "trades.db")

# Logging
LOG_FILE = "bot.log"
API_LOG_FILE = "wheelhive-api.log"
CMDS_LOG_FILE = "cmds.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

# UPLOADS/DOWNLOADS
UPLOADS_DIR = str(PROJECT_ROOT / "uploads")
DOWNLOADS_DIR = str(PROJECT_ROOT / "downloads")

# App Version
VERSION = 0.7
AUTHOR = "sangelovich"
CONTRIBUTORS = (
    "sangelovich, darkminer, brockhamilton.88, spam4elvis, mslick1, crazymonkey7543, _hrv_"
)

# DISCORD
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_MAX_CHAR_COUNT = 2000

# FINNHUB
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
FINNHUB_URL_OPTIONS = "https://finnhub.io/api/v1/stock/option-chain"
FINNHUB_URL_QUOTE = "https://finnhub.io/api/v1/quote"
OPTIONS_DATA_DIR = str(PROJECT_ROOT / "options_data")

# ALPHA VANTAGE
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

# SYSTEM SETTING KEYS (database-backed configuration)
# Use with SystemSettings: settings.get(const.SETTING_OLLAMA_BASE_URL)
SETTING_OLLAMA_BASE_URL = "llm.ollama_base_url"
SETTING_DEFAULT_LLM_MODEL = "llm.default_model"
SETTING_TRADE_PARSING_MODEL = "llm.trade_parsing_model"
SETTING_TRADE_PARSING_API_BASE = "llm.trade_parsing_api_base"
SETTING_TRADE_PARSING_TEMPERATURE = "llm.trade_parsing_temperature"
SETTING_VISION_OCR_MODEL = "llm.vision_ocr_model"
SETTING_VISION_API_BASE = "llm.vision_api_base"
SETTING_SENTIMENT_MODEL = "llm.sentiment_model"
SETTING_SENTIMENT_FALLBACK_MODEL = "llm.sentiment_fallback_model"
SETTING_SENTIMENT_API_BASE = "llm.sentiment_api_base"
SETTING_AI_TUTOR_MODEL = "llm.ai_tutor_model"
SETTING_IMAGE_ANALYSIS_ENABLED = "features.image_analysis_enabled"
SETTING_SENTIMENT_ANALYSIS_ENABLED = "features.sentiment_analysis_enabled"
SETTING_MARKET_DATA_PROVIDER = "market.data_provider"
SETTING_TRADING_MCP_URL = "mcp.trading_url"

# Vision Processing Configuration
SETTING_IMAGE_ANALYSIS_USE_QUEUE = "vision.use_queue"
SETTING_VISION_TIMEOUT_SECONDS = "vision.timeout_seconds"
SETTING_VISION_USE_DIRECT_JSON = "vision.use_direct_json"
SETTING_VISION_MAX_IMAGES_PER_MESSAGE = "vision.max_images_per_message"
SETTING_VISION_QUEUE_SIZE = "vision.queue_size"
SETTING_VISION_WORKER_COUNT = "vision.worker_count"

# Trade Parsing Configuration
SETTING_TRADE_PARSING_TIMEOUT_SECONDS = "trade_parsing.timeout_seconds"

# Sentiment Analysis Configuration
SETTING_SENTIMENT_ANALYSIS_USE_QUEUE = "sentiment.use_queue"
SETTING_SENTIMENT_TIMEOUT_SECONDS = "sentiment.timeout_seconds"
SETTING_SENTIMENT_QUEUE_SIZE = "sentiment.queue_size"
SETTING_SENTIMENT_WORKER_COUNT = "sentiment.worker_count"

# Market Data Provider Configuration
# Options: 'yfinance' or 'finnhub'
# YFinance: Free, comprehensive data, may have rate limits
# Finnhub: API key required, good for rate limit resilience
# NOTE: Options chains always use Finnhub first (yfinance returns delta=0.0)
# MARKET_DATA_PROVIDER moved to system_settings (use SETTING_MARKET_DATA_PROVIDER)

# LLM Configuration
# API Keys (stored in .env)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# MCP Server URLs
# Trading MCP URL moved to system_settings (use SETTING_TRADING_MCP_URL)
# Default: 'http://localhost:8000'

# Ollama Configuration moved to system_settings (use SETTING_OLLAMA_BASE_URL)
# Fallback constant for backward compatibility with test scripts
OLLAMA_BASE_URL = "http://localhost:11434"  # Default fallback for scripts

# MCP Tool Configuration
# Essential tool set (12 tools) - used for ALL models (Claude, GPT, Ollama)
# Testing showed:
# - Qwen models (Ollama) can handle ~10-15 tools but fail with 34+ tools
# - Claude/GPT respond faster and cost less with smaller tool sets
# - 12 tools provide all critical functionality (65% reduction from 34 tools)
ESSENTIAL_TOOLS = [
    # Core Portfolio (4 tools)
    "get_current_positions",  # Live holdings with prices/P&L
    "get_portfolio_overview",  # Complete trading history
    "get_user_statistics",  # Performance metrics
    "list_user_accounts",  # Account discovery
    # Options Trading (3 tools)
    "scan_options_chain",  # Find trading opportunities
    "get_option_expiration_dates",  # List available expirations
    "get_detailed_option_chain",  # Full chain with Greeks/IV
    # Market Data (4 tools)
    "get_historical_stock_prices",  # Price history/charts
    "get_market_sentiment",  # VIX, Fear & Greed Index
    "get_technical_summary",  # Fast technical analysis
    "get_market_news",  # Market news articles (Yahoo/Finnhub)
    # Research (4 tools)
    "get_trending_tickers",  # Community trending symbols
    "get_analyst_recommendations",  # Analyst ratings/price targets
    "get_community_messages",  # Discord community discussions
    "get_community_trades",  # Extracted trades from Discord
]

# Default model moved to system_settings (use SETTING_DEFAULT_LLM_MODEL)

# User tiers feature postponed until closer to production
# DEFAULT_USER_TIER constant removed

# Available LLM Models (for user selection)
# Consolidated to 3 best models: Premium (Claude Sonnet), Budget (Claude Haiku), Free (Qwen 32B)
# All models support tool calling for MCP integration
# LLM Models are now stored in database (llm_models table)
# Use llm_models.py for model management
# Default models populated via populate_default_models() migration function
# DEFAULT_LLM_MODEL moved to system_settings (use SETTING_DEFAULT_LLM_MODEL)

# DEV GUILD IDs
DEV_GUILDS = [1349592236375019520]
DEV_GUILD_IDS = list()
for id in DEV_GUILDS:
    DEV_GUILD_IDS.append(discord.Object(id=id))

# Production Guild IDs
GUILDS = [1349592236375019520, 1405962109262757980]
GUILD_IDS = list()
for id in GUILDS:
    GUILD_IDS.append(discord.Object(id=id))

# Channel configuration moved to database (guild_channels table)
# Fallback for legacy scripts (use CLI: `python src/cli.py channels list`)
KNOWLEDGEBASE_CHANNELS: dict[int, str] = {}  # Empty dict for type checking

# Date format
ISO_DATE_FMT = "%Y-%m-%d"

# Account filter constant - use "ALL" to query across all accounts
ACCOUNT_ALL = "ALL"

# Help documentation
HELP_DIR = str(PROJECT_ROOT / "doc")
HELP_PDF = "WheelHive.pdf"
HELP_SRC = "wheelhive.md"

# Report directory
REPORT_DIR = str(PROJECT_ROOT / "reports")
DAILY_DIGEST_DIR = str(PROJECT_ROOT / "daily_digest")

DISCORD_PERMISSIONS = [
    "create_instant_invite",
    "kick_members",
    "ban_members",
    "administrator",
    "manage_channels",
    "manage_guild",
    "add_reactions",
    "view_audit_log",
    "priority_speaker",
    "stream",
    "read_messages",
    "view_channel",
    "send_messages",
    "send_tts_messages",
    "manage_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
    "mention_everyone",
    "external_emojis",
    "use_external_emojis",
    "view_guild_insights",
    "connect",
    "speak",
    "mute_members",
    "deafen_members",
    "move_members",
    "use_voice_activation",
    "change_nickname",
    "manage_nicknames",
    "manage_roles",
    "manage_permissions",
    "manage_webhooks",
    "manage_expressions",
    "manage_emojis",
    "manage_emojis_and_stickers",
    "use_application_commands",
    "request_to_speak",
    "manage_events",
    "manage_threads",
    "create_public_threads",
    "create_private_threads",
    "external_stickers",
    "use_external_stickers",
    "send_messages_in_threads",
    "use_embedded_activities",
    "moderate_members",
    "view_creator_monetization_analytics",
    "use_soundboard",
    "create_expressions",
    "create_events",
    "use_external_sounds",
    "send_voice_messages",
    "send_polls",
    "create_polls",
    "use_external_apps",
]

TEST_TRADES = [
    "STO 2x MSTU 8/1 8P @ .16",
    "STO 2x MSTU 8/1 $8P @ $.16",
    "Dividend QQQI 63.66",
    "Deposit 20,000",
    "Withdrawal 15,000",
    "BTC 10x TSLL 8/1 10.5P @ .11",
    "BTC 1x CRCL 9/19 180.0P @ 14",
    "STO 3x HOOD 8/1 92P @ .72",
    "STO 2x TSLL 8/8 13C @ .34",
    "STO 3x CONL 8/15 40P @ 1.15",
    "Dividend ULTY 20.58",
    "Dividend YMAX 18.38",
    "Dividend ULTY 20.70",
    "Dividend YMAX 10.41",
    "Dividend YMAX 13.47",
    "Deposit 20,000",
    "Deposit 6",
    "Deposit 5",
    "Buy 300 shares MSTU @ 10",
    "Buy 250 shares MSTU @ 8.35",
    "Sell 400 shares CONL at 28",
    "Buy 200 shares ULTY @ 6.41",
    "Buy 1000 shares TSLL at 11.34",
    "Buy 5 CRCL at 201.81 5",
    "Sell 60 ETHT at 41.19",
]

# ============================================================
# IMAGE ANALYSIS SETTINGS (Vision Model Text Extraction)
# ============================================================
# Uses vision models (LLaVA, GPT-4V, Claude Vision, etc.) to extract text from images
# Async queue-based processing to avoid blocking the bot

# Feature Flags
# IMAGE_ANALYSIS_ENABLED moved to system_settings (use SETTING_IMAGE_ANALYSIS_ENABLED)
# IMAGE_ANALYSIS_USE_QUEUE moved to system_settings (use SETTING_IMAGE_ANALYSIS_USE_QUEUE)

# Vision Model Configuration
# Supported models (ranked by performance for trade screenshots):
#   - claude-3-5-haiku-20241022 (BEST: captures all details, $0.0008/image, 5s avg) ⭐
#   - claude-sonnet-4-5-20250929 (excellent, 7.4s avg, $0.003/image - 4x more expensive)
#   - ollama/granite3.2-vision:2b (FAST but misses quantities/premiums, free, 3.1s avg)
#   - ollama/minicpm-v (100% reliable, 4.2s avg, free self-hosted)
#   - ollama/llava:13b (93% reliable, 4.7s avg, free self-hosted)
# Vision Analysis Configuration
# Direct vision-to-JSON pipeline: Vision model extracts structured trade data directly
# Claude Haiku 3.5: 100% accuracy, $0.0008/image, 3.1s avg (tested on 8 Robinhood screenshots)
# Benefits over OCR+Parser: faster (30% improvement), more accurate, captures ALL strike prices
# Fallback constants for business logic classes (TODO: pass via constructor)
VISION_OCR_MODEL = "claude-3-5-haiku-20241022"  # fallback
VISION_API_BASE = ""  # fallback (empty = default Anthropic)
VISION_TIMEOUT_SECONDS = 60  # fallback
VISION_USE_DIRECT_JSON = True  # fallback
# VISION_MAX_IMAGES_PER_MESSAGE moved to system_settings (use SETTING_VISION_MAX_IMAGES_PER_MESSAGE)
# VISION_QUEUE_SIZE moved to system_settings (use SETTING_VISION_QUEUE_SIZE)
# VISION_WORKER_COUNT moved to system_settings (use SETTING_VISION_WORKER_COUNT)

# ============================================================
# TRADE PARSING SETTINGS
# ============================================================
# Extracts structured trade data from vision OCR text output
# Uses LLM with Pydantic schema validation for consistent JSON extraction

# Trade Parsing Model Configuration
# Best models for structured data extraction (ranked by JSON accuracy):
#   - ollama/qwen2.5-coder:7b (BEST: optimized for structured data, 4.7GB, ~2s avg) ⭐
#   - ollama/qwen2.5-coder:14b (9GB, ~3s avg, highest accuracy)
#   - ollama/llama3.1:8b (4.7GB, ~2s avg, good fallback)
# Fallback constants for business logic classes (TODO: pass via constructor)
TRADE_PARSING_MODEL = "ollama/qwen2.5-coder:7b"  # fallback
TRADE_PARSING_API_BASE = "http://jedi.local:11434"  # fallback
TRADE_PARSING_TIMEOUT_SECONDS = 30  # fallback
TRADE_PARSING_TEMPERATURE = 0.0  # fallback

# ============================================================
# SENTIMENT ANALYSIS SETTINGS
# ============================================================
# Analyzes bullish/bearish/neutral sentiment from message text + image data
# Two-level sentiment: overall message + per-ticker granularity

# Feature Flags
# SENTIMENT_ANALYSIS_ENABLED moved to system_settings (use SETTING_SENTIMENT_ANALYSIS_ENABLED)
# SENTIMENT_ANALYSIS_USE_QUEUE moved to system_settings (use SETTING_SENTIMENT_ANALYSIS_USE_QUEUE)

# Sentiment Model Configuration
# Tested models (ranked by per-ticker accuracy):
#   - ollama/gemma2:9b (BEST FREE: 100% per-ticker, 83.3% overall, 2.01s avg) ⭐
#   - claude-sonnet-4-5-20250929 (BEST OVERALL: 100% per-ticker, 91.7% overall, 4.63s avg, $0.003/1k)
#   - ollama/qwen2.5:32b (100% per-ticker, 83.3% overall, 3.78s avg)
#   - ollama/llama3.1:8b (88.9% per-ticker, 91.7% overall, 1.83s avg)
# Sentiment Analysis - Fallback constants for business logic classes (TODO: pass via constructor)
SENTIMENT_MODEL = "ollama/gemma2:9b"  # fallback
SENTIMENT_FALLBACK_MODEL = "claude-sonnet-4-5-20250929"  # fallback
SENTIMENT_API_BASE = "http://jedi.local:11434"  # fallback
SENTIMENT_TIMEOUT_SECONDS = 30  # fallback
# SENTIMENT_QUEUE_SIZE moved to system_settings (use SETTING_SENTIMENT_QUEUE_SIZE)
# SENTIMENT_WORKER_COUNT moved to system_settings (use SETTING_SENTIMENT_WORKER_COUNT)

# Trading Glossary - for LLM prompts to prevent terminology confusion
TRADE_GLOSSARY = """
---
**TRADING GLOSSARY** (Reference for accurate terminology)

**OPTIONS OPERATIONS** (4-letter codes for options only):
• **BTO (Buy to Open)**: Opening a LONG options position by purchasing contracts (you pay premium)
• **STO (Sell to Open)**: Opening a SHORT options position by selling contracts (you collect premium upfront)
• **BTC (Buy to Close)**: Closing a SHORT position by buying back contracts you previously sold
• **STC (Sell to Close)**: Closing a LONG position by selling contracts you previously bought
• **Contract Size:** 1 option contract = 100 shares of underlying stock (cannot buy/sell partial contracts)

**SHARE OPERATIONS** (plain language, NOT option codes):
• **Buy Shares**: Purchasing stock (e.g., "Buy 100 AAPL @ 150")
• **Sell Shares**: Selling stock (e.g., "Sell 100 AAPL @ 155")
• ⚠️ **Common Mistake**: Shares are NEVER called BTO/STO - those terms are exclusively for options!

**CALL OPTIONS** (by perspective):
• **Buyer (BTO Call)**:
  - Right to BUY 100 shares at strike price
  - Outlook: Bullish (profit if stock rises above strike + premium)
  - Max Profit: Unlimited | Max Loss: Premium paid
• **Seller (STO Call)**:
  - Obligation to SELL 100 shares at strike if assigned
  - Outlook: Neutral/Bearish (collect premium, hope stock stays below strike)
  - Max Profit: Premium collected | Max Loss: Unlimited

**PUT OPTIONS** (by perspective):
• **Buyer (BTO Put)**:
  - Right to SELL 100 shares at strike price
  - Outlook: Bearish (profit if stock falls below strike - premium)
  - Max Profit: Strike × 100 - premium | Max Loss: Premium paid
• **Seller (STO Put)**:
  - Obligation to BUY 100 shares at strike if assigned
  - Outlook: Neutral/Bullish (collect premium, hope stock stays above strike)
  - Max Profit: Premium collected | Max Loss: Strike × 100 - premium

**KEY TERMS:**
• **Strike**: Price at which option can be exercised
• **Premium**: Money paid (buyer) or collected (seller) per contract
• **DTE (Days to Expiration)**: Time until option expires
• **ITM (In The Money)**: Option has intrinsic value (Call: stock > strike, Put: stock < strike)
• **OTM (Out of The Money)**: No intrinsic value (Call: stock < strike, Put: stock > strike)
• **ATM (At The Money)**: Stock price ≈ strike price

**COMMON STRATEGIES:**
• **Wheel**: STO puts → get assigned → STO covered calls → get assigned → repeat
• **CSP (Cash-Secured Put)**: STO puts with cash to buy shares if assigned
• **Covered Call (CC)**: STO calls against shares you own (income, capped upside)
• **Naked Put/Call**: STO options WITHOUT shares/collateral (high risk, undefined loss)
• **Iron Condor**: STO OTM put spread + call spread (profit from low volatility)

**THE GREEKS** (risk measures):
• **Delta**: Price change per $1 stock move (Calls: 0 to 1.0, Puts: 0 to -1.0)
• **Theta**: Daily time decay in dollars (negative for buyers, positive for sellers)
• **Gamma**: Rate of delta change (higher = faster acceleration)
• **Vega**: Sensitivity to IV changes (higher IV = higher premiums)
• **IV (Implied Volatility)**: Market's expected future volatility

**MARKET INDICATORS:**
• **VIX (Volatility Index)**: <15 = calm, 15-20 = normal, 20-30 = elevated, >30 = fear/panic
• **Fear & Greed Index**: 0-25 = extreme fear, 25-45 = fear, 45-55 = neutral, 55-75 = greed, 75-100 = extreme greed
• **DCA (Dollar Cost Averaging)**: Buying fixed amounts at intervals to smooth entry price

**ASSIGNMENT & EXERCISE:**
• **Assignment**: When option seller must fulfill obligation (deliver/buy shares)
• **Exercise**: When option buyer uses their right to buy/sell shares at strike
• Typically occurs at expiration if ITM, or early if deeply ITM (especially calls before dividends)
---
"""

# General disclaimer - for reports, analysis, and information outputs
DISCLAIMER = """
---
⚠️ **DISCLAIMER**: For informational purposes only. Not financial advice. Trading involves risk of loss. Do your own research.
---
"""
