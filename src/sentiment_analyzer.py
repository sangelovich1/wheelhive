"""
Sentiment Analyzer

Analyzes financial sentiment from Discord messages with trading content.
Uses LLM to classify overall message sentiment and per-ticker sentiment.

Two-level sentiment:
- Overall message sentiment (bullish/bearish/neutral)
- Per-ticker sentiment for each mentioned ticker

Supports:
- Text-only messages
- Messages with image data (from vision OCR)
- Options trading signals (STO, BTC, etc.)
- Share transactions (accumulation/distribution)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import json
import logging
from typing import Any

from litellm import acompletion

import constants as const


logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyze financial sentiment from trading messages"""

    def __init__(self, model: str | None = None):
        """
        Initialize sentiment analyzer.

        Args:
            model: LLM model to use (default: const.SENTIMENT_MODEL)
        """
        self.model = model or const.SENTIMENT_MODEL
        self.fallback_model = const.SENTIMENT_FALLBACK_MODEL
        self.api_base = const.SENTIMENT_API_BASE
        self.timeout = const.SENTIMENT_TIMEOUT_SECONDS

    async def analyze_sentiment(
        self,
        message_text: str,
        image_data: str | None = None,
        use_fallback: bool = False
    ) -> dict[str, Any]:
        """
        Analyze sentiment of a trading message.

        Args:
            message_text: The message content
            image_data: Optional extracted text from images
            use_fallback: If True, use fallback model (Claude)

        Returns:
            Dict with sentiment analysis:
            {
                "sentiment": "bullish" | "bearish" | "neutral",
                "confidence": 0.0-1.0,
                "tickers": [
                    {"symbol": "AAPL", "sentiment": "bullish", "confidence": 0.85},
                    ...
                ],
                "reasoning": "brief explanation"
            }

        Raises:
            Exception: If sentiment analysis fails
        """
        model = self.fallback_model if use_fallback else self.model

        prompt = self._build_prompt(message_text, image_data)

        try:
            logger.debug(f"Analyzing sentiment with model: {model}")
            response = await acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.api_base if not use_fallback else None,
                timeout=self.timeout
            )

            content = response.choices[0].message.content.strip()

            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            parsed_result: dict[str, Any] = json.loads(content)
            result: dict[str, Any] = parsed_result

            # Validate result structure
            if not all(k in result for k in ["sentiment", "confidence", "tickers", "reasoning"]):
                raise ValueError(f"Invalid sentiment result structure: {result}")

            logger.info(f"Sentiment analysis complete: {result['sentiment']} ({result['confidence']:.2f})")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse sentiment JSON: {e}, content: {content}")
            raise
        except Exception as e:
            logger.error(f"Sentiment analysis failed with {model}: {e}")
            # Try fallback model once
            if not use_fallback and self.fallback_model:
                logger.info(f"Retrying with fallback model: {self.fallback_model}")
                return await self.analyze_sentiment(message_text, image_data, use_fallback=True)
            raise

    def _build_prompt(self, message_text: str, image_data: str | None = None) -> str:
        """
        Build the sentiment analysis prompt.

        Args:
            message_text: The message content
            image_data: Optional extracted text from images

        Returns:
            Formatted prompt string
        """
        return f"""You are a financial sentiment analyst specializing in options trading.

Analyze the sentiment of this trading message.

SENTIMENT CLASSIFICATION:
- bullish: Expecting prices to rise, positive outlook, accumulation
- bearish: Expecting prices to fall, negative outlook, distribution
- neutral: No clear directional bias, uncertain, mixed signals, or balanced positions

OPTIONS TRADING SIGNALS:
Opening positions:
- STO (Sell To Open) puts = BULLISH on underlying stock (collecting premium, expect price to stay above strike)
- BTO (Buy To Open) puts = BEARISH hedge or protection (paying for downside insurance)
- STO (Sell To Open) calls = BEARISH/neutral (capping upside, don't expect significant rise)
- BTO (Buy To Open) calls = BULLISH (expecting price to rise above strike)

Closing positions (interpret by what they're exiting):
- BTC (Buy To Close) puts = BEARISH (closing short put early = worried about downside)
- STC (Sell To Close) calls = BEARISH (exiting long call = no longer bullish)
- BTC (Buy To Close) calls = BULLISH (closing short call early = worried about upside)
- STC (Sell To Close) puts = BULLISH (exiting long put = no longer bearish)

Share accumulation/distribution:
- Buying shares, increasing holdings = BULLISH (accumulation)
- Selling shares, reducing holdings = BEARISH (distribution)

CRITICAL: PER-TICKER SENTIMENT
For EACH ticker mentioned, determine its individual sentiment based on:
- What specific actions are being taken with that ticker
- Opening vs closing positions
- Direction of trade (buy/sell, calls/puts)
- Share accumulation vs distribution

Example 1 - Mixed sentiment per ticker:
Message: "Closed AAPL calls, bought TSLA puts - rotating to defensive"
Overall: bearish
Tickers: [
  {{"symbol": "AAPL", "sentiment": "bearish", "confidence": 0.80}},  # Exiting calls = bearish
  {{"symbol": "TSLA", "sentiment": "bearish", "confidence": 0.90}}   # Buying puts = bearish
]

Example 2 - Pure bullish:
Message: "STO 5x NVDA 8/15 120P @ 2.50 - love this setup"
Overall: bullish
Tickers: [
  {{"symbol": "NVDA", "sentiment": "bullish", "confidence": 0.95}}  # Selling puts = bullish
]

Example 3 - Closing position (interpret direction):
Message: "BTC 3x SPY 450C @ 1.20 - taking profits"
Overall: bearish
Tickers: [
  {{"symbol": "SPY", "sentiment": "bearish", "confidence": 0.75}}  # Closing calls early = no longer bullish
]

Example 4 - Neutral/Mixed:
Message: "Rolled my MSFT 340/350 call spread out to next month"
Overall: neutral
Tickers: [
  {{"symbol": "MSFT", "sentiment": "neutral", "confidence": 0.60}}  # Rolling = maintaining position
]

Example 5 - BTC accumulation:
Message: "Added 2 more BTC at 95k, DCAing in"
Overall: bullish
Tickers: [
  {{"symbol": "BTC", "sentiment": "bullish", "confidence": 0.90}}  # Buying/accumulating = bullish
]

RESPOND WITH JSON ONLY (no markdown, no explanations):
{{
  "sentiment": "bullish" | "bearish" | "neutral",
  "confidence": 0.0-1.0,
  "tickers": [
    {{"symbol": "AAPL", "sentiment": "bullish", "confidence": 0.85}},
    {{"symbol": "TSLA", "sentiment": "bearish", "confidence": 0.90}}
  ],
  "reasoning": "brief explanation"
}}

MESSAGE TEXT:
{message_text}

IMAGE DATA (if available):
{image_data or 'None'}
"""


async def analyze_message_sentiment(
    message_text: str,
    image_data: str | None = None,
    model: str | None = None
) -> dict[str, Any]:
    """
    Convenience function to analyze sentiment of a single message.

    Args:
        message_text: The message content
        image_data: Optional extracted text from images
        model: Optional model override

    Returns:
        Dict with sentiment analysis results

    Example:
        >>> result = await analyze_message_sentiment("STO 5x NVDA 120P @ 2.50")
        >>> print(result['sentiment'])  # "bullish"
        >>> print(result['tickers'][0])  # {"symbol": "NVDA", "sentiment": "bullish", ...}
    """
    analyzer = SentimentAnalyzer(model=model)
    return await analyzer.analyze_sentiment(message_text, image_data)


def analyze_message_sentiment_sync(
    message_text: str,
    image_data: str | None = None,
    model: str | None = None
) -> dict[str, Any]:
    """
    Synchronous wrapper for analyze_message_sentiment.

    Args:
        message_text: The message content
        image_data: Optional extracted text from images
        model: Optional model override

    Returns:
        Dict with sentiment analysis results

    Example:
        >>> result = analyze_message_sentiment_sync("STO 5x NVDA 120P @ 2.50")
        >>> print(result['sentiment'])  # "bullish"
    """
    return asyncio.run(analyze_message_sentiment(message_text, image_data, model))
