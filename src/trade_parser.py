"""
Trade Parser: Synchronous trade extraction from text/OCR

Extracts structured trade data from Discord messages and trading screenshots.
Uses LLM with Pydantic validation for type-safe parsing.

Architecture:
- Synchronous core functions (no async)
- Batch-processing friendly
- CLI/script compatible
- Bot can wrap with async as needed

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any

from litellm import completion
from pydantic import BaseModel, Field, field_validator

import constants as const
from providers.market_data_factory import MarketDataFactory


logger = logging.getLogger(__name__)


# ============================================================
# Pydantic Models for Structured Trade Extraction
# ============================================================

class ParsedTrade(BaseModel):
    """Single parsed trade from vision OCR or text"""
    operation: str = Field(..., description="Trade operation: STO, BTC, BTO, STC")
    ticker: str = Field(..., description="Stock ticker symbol")
    option_type: str = Field(..., description="CALL or PUT")
    strike: float = Field(..., description="Strike price")
    expiration: str = Field(..., description="Expiration date (YYYY-MM-DD)")
    quantity: int = Field(..., description="Number of contracts")
    premium: float = Field(..., description="Premium per contract")
    filled_datetime: str | None = Field(None, description="Fill timestamp (if available)")
    source: str | None = Field("unknown", description="Trade source: 'text' | 'image' | 'unknown'")

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate operation is STO, BTC, BTO, or STC"""
        v = v.upper().strip()
        if v not in ["STO", "BTC", "BTO", "STC"]:
            raise ValueError(f"operation must be STO, BTC, BTO, or STC, got: {v}")
        return v

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str) -> str:
        """Validate option_type is CALL or PUT"""
        v = v.upper().strip()
        if v not in ["CALL", "PUT"]:
            raise ValueError(f"option_type must be CALL or PUT, got: {v}")
        return v

    @field_validator("strike")
    @classmethod
    def validate_strike(cls, v: float) -> float:
        """Validate strike price is reasonable"""
        if v <= 0:
            raise ValueError(f"strike must be positive, got: {v}")
        if v > 10000:
            logger.warning(f"High strike price detected: ${v:.2f}")
        return v

    @field_validator("premium")
    @classmethod
    def validate_premium(cls, v: float) -> float:
        """Validate premium is non-negative"""
        if v < 0:
            raise ValueError(f"premium cannot be negative, got: {v}")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """Validate quantity is positive"""
        if v <= 0:
            raise ValueError(f"quantity must be positive, got: {v}")
        return v

    @field_validator("expiration")
    @classmethod
    def validate_expiration(cls, v: str) -> str:
        """Validate expiration date format"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"expiration must be YYYY-MM-DD format, got: {v}")
        return v

    @classmethod
    def validate_strike_premium(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Cross-field validation: strike and premium shouldn't be equal"""
        strike = values.get("strike")
        premium = values.get("premium")

        if strike and premium and abs(strike - premium) < 0.01:
            raise ValueError(
                f"Strike and premium are equal (${premium}), likely parsing error. "
                f"Premium should not equal strike price."
            )
        return values


class TradeExtractionResult(BaseModel):
    """Result from trade parsing LLM"""
    is_trade: bool = Field(..., description="Whether this is a trade execution")
    trades: list[ParsedTrade] = Field(default_factory=list, description="Extracted trades")


# ============================================================
# Core Parsing Functions (Synchronous)
# ============================================================

def parse_trades_from_text(text: str, source: str = "unknown") -> list[dict[str, Any]]:
    """
    Parse trades from raw text using LLM + Pydantic validation

    SYNCHRONOUS function - no async/await needed.

    Args:
        text: Raw text from message or OCR
        source: Trade source ('text' | 'image' | 'unknown')

    Returns:
        List of trade dictionaries (Pydantic-validated)
    """
    try:
        # Get Pydantic JSON schema
        schema = TradeExtractionResult.model_json_schema()

        # Get current date for year inference
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Extract tickers from text and fetch current prices
        price_context = _build_price_context(text)

        # Build improved prompt with price context and statistical guidance
        prompt = _build_parsing_prompt(text, schema, current_year, current_month, price_context)

        # Call LLM synchronously (no await!)
        response = completion(
            model=const.TRADE_PARSING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_base=const.TRADE_PARSING_API_BASE,
            temperature=const.TRADE_PARSING_TEMPERATURE,
            timeout=const.TRADE_PARSING_TIMEOUT_SECONDS,
            response_format={"type": "json_object"}
        )

        if not response or not response.choices:
            logger.warning("No response from trade parsing LLM")
            return []

        # Parse and validate with Pydantic
        json_str = response.choices[0].message.content
        logger.debug(f"LLM response for trade parsing: {json_str}")
        result = TradeExtractionResult.model_validate_json(json_str)

        # Convert Pydantic models to dicts for downstream compatibility
        if not result.is_trade or not result.trades:
            logger.debug("No trades found in text (non-trade or empty)")
            return []

        trades = []
        for trade in result.trades:
            trade_dict = {
                "operation": trade.operation,
                "ticker": trade.ticker,
                "option_type": trade.option_type,
                "strike": trade.strike,
                "expiration": trade.expiration,
                "quantity": trade.quantity,
                "premium": trade.premium,
                "filled_datetime": trade.filled_datetime,
                "source": source,
                "parsed": True
            }

            # Post-parsing validation
            validation_result = _validate_parsed_trade(trade_dict, text, price_context)
            if validation_result["errors"]:
                logger.warning(
                    f"Validation errors for {trade.ticker} trade: {validation_result['errors']}"
                )
                trade_dict["validation_errors"] = validation_result["errors"]

            if validation_result["warnings"]:
                logger.info(
                    f"Validation warnings for {trade.ticker} trade: {validation_result['warnings']}"
                )
                trade_dict["validation_warnings"] = validation_result["warnings"]

            trades.append(trade_dict)

        logger.info(f"Extracted {len(trades)} trade(s) using {const.TRADE_PARSING_MODEL}")
        return trades

    except Exception as e:
        logger.error(f"Trade parsing failed: {e}", exc_info=True)
        return []


def _validate_parsed_trade(
    trade: dict[str, Any],
    original_text: str,
    price_context: dict[str, float | None]
) -> dict[str, list[str]]:
    """
    Validate a parsed trade for obvious errors.

    Returns:
        {
            'errors': List of error messages (parsing likely wrong),
            'warnings': List of warning messages (unusual but possibly correct)
        }
    """
    errors = []
    warnings = []

    ticker = trade["ticker"]
    strike = trade["strike"]
    quantity = trade["quantity"]
    premium = trade["premium"]

    # 1. Validate quantity against statistical distribution
    if quantity > 1000:
        errors.append(f"Quantity {quantity} exceeds 1000 contracts (almost certainly a parsing error)")
    elif quantity > 100:
        warnings.append(f"Quantity {quantity} exceeds 100 contracts (only 3% of trades are this large)")
    elif quantity > 50:
        warnings.append(f"Quantity {quantity} exceeds 50 contracts (only 7% of trades are this large)")

    # 2. Check for "shares" vs "contracts" confusion
    if quantity > 100 and re.search(r"\b(shares?|stock|equity)\b", original_text, re.IGNORECASE):
        errors.append(
            f"Message mentions 'shares' and quantity={quantity} seems unusually high "
            "(possible shares vs contracts confusion)"
        )

    # 3. Validate strike price against current market price
    if ticker in price_context and price_context[ticker] is not None:
        current_price: float = price_context[ticker]  # type: ignore
        min_strike: float = current_price * 0.5  # -50%
        max_strike: float = current_price * 1.5  # +50%

        if strike < min_strike or strike > max_strike:
            errors.append(
                f"Strike ${strike:.2f} is far from current price ${current_price:.2f} "
                f"(expected range: ${min_strike:.2f}-${max_strike:.2f}). "
                f"May be swapped with quantity={quantity}"
            )

    # 4. Check for strike = premium (common parsing error)
    if abs(strike - premium) < 0.01:
        errors.append(
            f"Strike and premium are identical (${premium:.2f}), likely a parsing error"
        )

    # 5. Validate premium is reasonable
    if premium > 100:
        warnings.append(
            f"Premium ${premium:.2f} is unusually high (may be total credit instead of per-contract)"
        )

    # 6. Validate operation against message context
    operation = trade["operation"]
    text_lower = original_text.lower()

    # Check for operation keywords in message content
    closing_keywords = ["closing", "closed", "close", "btc", "stc", "bought back", "sold for"]
    opening_keywords = ["opening", "opened", "open", "sto", "bto", "selling", "buying"]

    has_closing_context = any(kw in text_lower for kw in closing_keywords)
    has_opening_context = any(kw in text_lower for kw in opening_keywords)

    if has_closing_context and operation in ["STO", "BTO"]:
        errors.append(
            f"Message says 'closing' but operation={operation} is an OPEN operation. "
            f"Should be BTC or STC"
        )
    elif has_opening_context and operation in ["BTC", "STC"]:
        # Less strict - "opening" is less common in messages
        warnings.append(
            f"Message says 'opening' but operation={operation} is a CLOSE operation. "
            f"Verify if this should be BTO or STO"
        )

    # 7. Check if numbers appear in original text
    numbers_in_text = re.findall(r"\b\d+(?:\.\d+)?\b", original_text)
    numbers_in_text = [float(n) for n in numbers_in_text]

    # Strike should appear in text
    if strike not in numbers_in_text and not any(abs(n - strike) < 0.01 for n in numbers_in_text):
        warnings.append(f"Strike ${strike:.2f} does not appear in original text")

    # Quantity should appear in text (as integer)
    int_numbers = [int(n) for n in numbers_in_text if n == int(n)]
    if quantity not in int_numbers:
        warnings.append(f"Quantity {quantity} does not appear in original text")

    return {
        "errors": errors,
        "warnings": warnings
    }


def _extract_tickers_from_text(text: str) -> list[str]:
    """Extract ticker symbols from text (same logic as vision_strategy.py)"""
    # Look for 2-5 uppercase letters (common ticker format)
    ticker_pattern = r"\b[A-Z]{2,5}\b"
    tickers = set(re.findall(ticker_pattern, text))

    # Filter out common non-ticker words
    excluded = {
        "CALL", "PUT", "BUY", "SELL", "OPEN", "CLOSE", "LIMIT", "MARKET",
        "FILLED", "PENDING", "IRA", "CASH", "MARGIN", "TYPE", "STATUS",
        "ACCOUNT", "TIME", "GOOD", "DAY", "GTC", "EST", "MDT", "EDT",
        "PST", "CST", "AM", "PM", "FOR", "THE", "AND", "NOT", "BUT", "ALL",
        "STO", "BTC", "BTO", "STC", "BOT", "SOLD", "NOV", "DEC", "JAN",
        "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT"
    }

    return sorted([t for t in tickers if t not in excluded])


def _build_price_context(text: str) -> dict[str, float | None]:
    """
    Extract tickers from text and fetch current prices.

    Returns:
        Dict mapping ticker -> current price (or None if lookup failed)
    """
    tickers = _extract_tickers_from_text(text)
    price_context: dict[str, float | None] = {}

    if not tickers:
        return price_context

    # Limit to 5 tickers to avoid excessive API calls
    tickers = tickers[:5]

    market_data = MarketDataFactory()
    for ticker in tickers:
        try:
            quote = market_data.get_quote_with_fallback(ticker)
            if quote and isinstance(quote, dict) and "price" in quote:
                price_context[ticker] = float(quote["price"])
                logger.debug(f"Price context: {ticker} = ${quote['price']:.2f}")
            else:
                price_context[ticker] = None
        except Exception as e:
            logger.debug(f"Could not fetch price for {ticker}: {e}")
            price_context[ticker] = None

    return price_context


def _build_parsing_prompt(
    text: str,
    schema: dict,
    current_year: int,
    current_month: int,
    price_context: dict[str, float | None]
) -> str:
    """Build the LLM prompt for trade parsing with price context and statistical guidance"""

    # Build price context section
    price_section = ""
    if price_context:
        price_lines = []
        for ticker, price in price_context.items():
            if price is not None:
                price_lines.append(f"- {ticker}: ${price:.2f}")

        if price_lines:
            price_section = f"""
=== CURRENT MARKET PRICES (Use for validation) ===
{chr(10).join(price_lines)}

**IMPORTANT**: Strike prices should typically be within ±50% of current price.
If you see a strike far outside this range, it may be a parsing error (e.g., strike/quantity swapped).
"""

    return f"""Analyze this text from a trading screenshot or message and extract structured trade data.

If this is a trade execution, extract all trade details in JSON format.
If this is NOT a trade (e.g., news, chart, account summary, general discussion), return is_trade: false.
{price_section}
=== CONTRACT QUANTITY VALIDATION (Statistical Guidance) ===
Based on analysis of real trading data:
- **80% of option trades are ≤10 contracts**
- **93% of option trades are ≤50 contracts**
- Trades with >100 contracts are very rare (only 3% of all trades)

**Red flags for quantity parsing**:
- Quantity >100: Unusual, verify carefully (may be shares vs contracts confusion)
- Quantity >1000: Almost certainly a parsing error
- If text mentions "shares" or "stock", the numbers are share counts, NOT contract counts
  Example: "stc 14k of 30k MSTU shares" → This is SHARES, not contracts (likely 14,000 shares = 140 contracts)

**When parsing ambiguous numbers**:
If you see two numbers that could be either strike or quantity:
1. Use the price context above to determine which number is the strike
2. Strike should be close to current price (within ±50%)
3. Quantity should typically be ≤10 contracts

Example: "ETHU Nov 07 2025 115 Call - C - 2 - 0.65 - 130.00"
- If ETHU trades at ~$115: strike=115, quantity=2 (NOT strike=2, quantity=130)
- Reasoning: 115 is close to market price, 2 contracts is typical

=== OPERATION CODES (Standard Trading Terminology) ===
- **STO** = Sell to Open (opening a short position, RECEIVE premium)
- **BTC** = Buy to Close (closing a short position, PAY premium)
- **BTO** = Buy to Open (opening a long position, PAY premium)
- **STC** = Sell to Close (closing a long position, RECEIVE premium)

**CRITICAL**: Getting the operation wrong reverses profit/loss calculations!

Common abbreviations you'll see:
- "sto", "STO", "Sold to Open" → operation: "STO"
- "btc", "BTC", "Buy to Close", "Bought to Close" → operation: "BTC"
- "bto", "BTO", "Buy to Open", "Bought to Open" → operation: "BTO"
- "stc", "STC", "Sell to Close", "Sold to Close" → operation: "STC"

**Context clues to determine operation** (use these if operation code is unclear):
1. **Message text** (HIGHEST PRIORITY - check message content FIRST):
   - "STO", "sto", "Sell to Open" → operation: "STO"
   - "BTC", "btc", "Buy to Close" → operation: "BTC"
   - "BTO", "bto", "Buy to Open" → operation: "BTO"
   - "STC", "stc", "Sell to Close" → operation: "STC"
   - "start a position", "opening" → STO or BTO (opening positions)
   - "closing", "closed", "bought back" → BTC or STC (closing positions)
   - "for credit", "collected premium" → STO or STC (selling options)

2. **Robinhood "History" sections** (IMPORTANT):
   - Robinhood screenshots show "History" header above CURRENT trade executions
   - "History" does NOT mean past/closed trades - it's just a UI section name
   - "Sell" under "History" can be STO (opening) OR STC (closing)
   - **ALWAYS check message text to determine if opening or closing**
   - Example: Message says "STO 2x BMNR" + Screenshot shows "History: Sell BMNR" → operation: "STO"

3. **Screenshot layout**:
   - Operation code often appears BEFORE trade details
   - Look for "BTC", "STO", etc. at the start of each line
   - Example: "**BTC** ETHU Nov 07 2025 115 Call C 2 0.65 130.00"

4. **Default assumption**:
   - If truly ambiguous after checking all context: "Sell" = STO, "Buy" = BTO

=== STRIKE PRICE PARSING (Critical - Handle OCR Errors) ===
Strike prices are often misread by OCR. Apply these rules:

1. **Low strike prices** (under $20):
   - "$2C" or "2 CALL" → strike: 2.0 (NOT 2100!)
   - "$3P" or "3 PUT" → strike: 3.0 (NOT 3000!)
   - "21 NOV 25 2 CALL" → date is "21 NOV 25", strike is 2.0

2. **Sanity check for leveraged ETFs**:
   - Tickers like MSTU, MSTX, TSLL, SOXL, TQQQ rarely trade above $100
   - If strike > 1000 for these tickers, it's likely an OCR error
   - Example: "MSTU 2100C" is wrong → should be "MSTU $2 or $21 call"

3. **Strike extraction from option notation**:
   - "ETHU 10/03/25 147 C" → strike: 147, exp: 2025-10-03, type: CALL
   - "TSLA 400 Put" → strike: 400, type: PUT
   - "12/15 250C" → strike: 250, type: CALL, exp: 2025-12-15

=== DATE PARSING (Year Inference) ===
**Current date**: {datetime.now().strftime('%Y-%m-%d')} (month={current_month}, year={current_year})

When expiration dates lack a year (e.g., "11/9", "12/15", "1/15"):
- If expiration_month >= {current_month}: Use {current_year}
- If expiration_month < {current_month}: Use {current_year + 1}

Examples for today:
- "11/9" → {current_year}-11-09 (November >= {current_month} → {current_year})
- "11/21" → {current_year}-11-21 (November >= {current_month} → {current_year})
- "12/15" → {current_year}-12-15 (December > {current_month} → {current_year})
- "1/15" → {current_year + 1}-01-15 (January < {current_month} → {current_year + 1})

Common OCR date formats:
- "21 NOV 25" → 2025-11-21
- "NOV 21 2025" → 2025-11-21
- "11/21/25" → 2025-11-21
- "10/31/2025" → 2025-10-31

Always output as ISO format: YYYY-MM-DD

=== MULTIPLE FILLS (Partial Fills) ===
Large orders are often filled in multiple partial fills. Keep them SEPARATE:

Example:
- "BOT +13 MSTU 10/31/25 3P @.05" → 1 trade, qty: 13
- "BOT +20 MSTU 10/31/25 3P @.05" → 1 trade, qty: 20
- "BOT +15 MSTU 10/31/25 3P @.05" → 1 trade, qty: 15

Output: 3 separate trades (NOT combined into qty: 48)

=== PREMIUM EXTRACTION (CRITICAL - READ CAREFULLY!) ===
**IMPORTANT**: Focus on PER CONTRACT premium, NOT total credit/debit!

Common scenarios:
1. **Total credit mentioned with per-contract detail**:
   - "STO 25x MSTX for $125 credit (25 contracts at $0.05)" → premium: 0.05 (NOT 125!)
   - "BTC 10x TSLA for $350 credit (10 contracts at $3.50)" → premium: 3.50 (NOT 350!)

2. **Per-contract notation**:
   - "$0.63" → premium: 0.63
   - "@1.10" → premium: 1.10
   - "at .05" → premium: 0.05

3. **Credit/debit with quantity**:
   - "Credit $6.00" (with 1 contract) → premium: 6.0
   - "Debit $12.50" (with 5 contracts) → premium: 2.5 (calculate: $12.50 / 5)

4. **Missing premium**:
   - If no premium found → premium: 0 (NOT null)

**Red flags** (likely parsing errors):
- Premium equals strike price (e.g., strike=0.41, premium=0.41) → ERROR!
- Negative premium (e.g., premium=-125) → ERROR!
- Unusually high premium (e.g., premium=350 for SPY) → Check if it's total credit!

=== OPTION TYPE ===
- "C", "CALL", "Call" → option_type: "CALL"
- "P", "PUT", "Put" → option_type: "PUT"

=== EXAMPLES ===

EXAMPLE 1 (User text - STC abbreviation):
Input: "stc 20x MSTU 11/21 2Cs +22%"
Output: {{"is_trade": true, "trades": [{{"operation": "STC", "ticker": "MSTU", "option_type": "CALL", "strike": 2.0, "expiration": "{current_year}-11-21", "quantity": 20, "premium": 0}}]}}

EXAMPLE 2 (User text - BTC abbreviation):
Input: "btc 50x MSTU 10/31 3p +80%"
Output: {{"is_trade": true, "trades": [{{"operation": "BTC", "ticker": "MSTU", "option_type": "PUT", "strike": 3.0, "expiration": "{current_year}-10-31", "quantity": 50, "premium": 0}}]}}

EXAMPLE 3 (Screenshot OCR - STO with per-contract premium):
Input: "STO 5x TSLA 12/15 250C @ 3.50"
Output: {{"is_trade": true, "trades": [{{"operation": "STO", "ticker": "TSLA", "option_type": "CALL", "strike": 250.0, "expiration": "{current_year}-12-15", "quantity": 5, "premium": 3.5}}]}}

EXAMPLE 4 (CRITICAL - Total credit vs per-contract):
Input: "STO 25x MSTX puts for $125 credit\\nMSTX $9.5 Put 11/7\\n25 contracts at $0.05"
Analysis:
  - Total credit: $125
  - Per-contract: $0.05 (from "25 contracts at $0.05")
  - Validation: 25 × $0.05 × 100 = $125 ✓
Output: {{"is_trade": true, "trades": [{{"operation": "STO", "ticker": "MSTX", "option_type": "PUT", "strike": 9.5, "expiration": "{current_year}-11-07", "quantity": 25, "premium": 0.05}}]}}

EXAMPLE 5 (Screenshot OCR - Multiple fills):
Input: "BOT +13 MSTU 100 31 OCT 25 3 PUT @.05\\nBOT +20 MSTU 100 31 OCT 25 3 PUT @.05"
Output: {{"is_trade": true, "trades": [{{"operation": "BTO", "ticker": "MSTU", "option_type": "PUT", "strike": 3.0, "expiration": "{current_year}-10-31", "quantity": 13, "premium": 0.05}}, {{"operation": "BTO", "ticker": "MSTU", "option_type": "PUT", "strike": 3.0, "expiration": "{current_year}-10-31", "quantity": 20, "premium": 0.05}}]}}

EXAMPLE 6 (Screenshot OCR - Strike price parsing):
Input: "D -20 MSTU 100 21 NOV 25 2 CALL @1.10"
Analysis: "D" = STO (Sell to Open), "21 NOV 25" = date (Nov 21, 2025), "2" = strike ($2), "CALL" = type
Output: {{"is_trade": true, "trades": [{{"operation": "STO", "ticker": "MSTU", "option_type": "CALL", "strike": 2.0, "expiration": "{current_year}-11-21", "quantity": 20, "premium": 1.10}}]}}

EXAMPLE 7 (Non-trade - account summary):
Input: "Account Balance: $50,000, Cash Available: $12,345, Buying Power: $25,000"
Output: {{"is_trade": false, "trades": []}}

EXAMPLE 8 (Non-trade - general discussion):
Input: "I'm thinking about buying some TSLA calls tomorrow"
Output: {{"is_trade": false, "trades": []}}

=== JSON SCHEMA ===
{json.dumps(schema, indent=2)}

=== TEXT TO ANALYZE ===
{text}

=== INSTRUCTIONS ===
Return ONLY the JSON object, no additional text or explanation.
Pay special attention to premium extraction - use per-contract price, NOT total credit!"""


# ============================================================
# Batch Processing Helper
# ============================================================

def batch_parse_trades(messages: list[dict[str, Any]], batch_size: int = 10) -> list[dict[str, Any]]:
    """
    Batch process multiple messages for trade extraction

    Args:
        messages: List of message dicts with 'id', 'content', 'extracted_data' fields
        batch_size: Number of messages to process before logging progress

    Returns:
        List of results with message_id and extracted trades
    """
    import json
    results = []
    total = len(messages)

    for idx, msg in enumerate(messages, 1):
        msg_id = msg.get("id")
        content = msg.get("content", "")

        # Extract OCR text from extracted_data JSON
        image_text = ""
        extracted_data = msg.get("extracted_data")
        if extracted_data:
            data = json.loads(extracted_data) if isinstance(extracted_data, str) else extracted_data
            image_text = data.get("raw_text", "")

        # Combine text and OCR
        combined_text = f"{content}\n\n--- IMAGE OCR ---\n\n{image_text}" if image_text else content

        # Parse trades
        trades = parse_trades_from_text(combined_text, source="text" if not image_text else "image")

        results.append({
            "message_id": msg_id,
            "trades": trades,
            "trade_count": len(trades)
        })

        # Log progress
        if idx % batch_size == 0:
            logger.info(f"Processed {idx}/{total} messages ({idx/total*100:.1f}%)")

    logger.info(f"Batch processing complete: {len(results)} messages processed")
    return results
