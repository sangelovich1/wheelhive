#!/usr/bin/env python3
"""
Question classifier for RAG tutor tool usage decisions.

This module uses deterministic pattern matching to categorize user questions
and determine which tools (if any) should be called.

Future Enhancement: ML-based classification for acquisition value.
Current: Simple, reliable, measurable pattern matching.

Categories:
- conceptual: Definitions, explanations (no tools needed)
- recommendation: Trade suggestions (requires current market data)
- analysis: Ticker evaluation (may need community/sentiment data)
- strategic: When/why/how questions (training materials usually sufficient)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class CategoryPattern:
    """Single pattern for question categorization"""
    category: str
    pattern: str
    priority: int  # Lower = higher priority (checked first)
    tools: list[str]  # Tools that should be called for this category
    description: str
    examples: list[str]


class QuestionClassifier:
    """
    Deterministic question classifier using regex patterns.

    This provides strong guidance to the LLM about which tools to call.
    All decisions are logged for future ML model training.
    """

    # Pattern definitions (order matters - higher priority checked first)
    PATTERNS = [
        # RECOMMENDATION - Explicit trade/stock requests (check BEFORE conceptual)
        CategoryPattern(
            category="recommendation",
            pattern=r"(what (stocks|tickers|options)|which (stocks|options)|what are (some |)good (stocks|tickers|options|trades|puts|calls|plays)|good (trades|puts|calls|plays|stocks)|looking for.*(stocks|trades))",
            priority=1,
            tools=["query_watchlist", "scan_options_chain"],
            description="Asking for specific trade recommendations",
            examples=[
                "What stocks should I trade?",
                "What are good stocks for the wheel?",
                "What are some good wheel stocks?",
                "Good puts for next week?",
                "Which options are good right now?",
                "Looking for good income stocks"
            ]
        ),

        # RECOMMENDATION - Account size mentioned (position sizing needed)
        CategoryPattern(
            category="recommendation",
            pattern=r"(i have \$[\d,]+|with \$[\d,]+)",
            priority=1,
            tools=["query_watchlist", "scan_options_chain"],
            description="Mentions account size - needs position sizing guidance",
            examples=[
                "I have $25K, what should I trade?",
                "With $50K where should I start?",
                "With $100K where should I start?"
            ]
        ),

        # CONCEPTUAL - Definitions and explanations (after recommendation check)
        CategoryPattern(
            category="conceptual",
            pattern=r"^(what is|what does|what are (the |)(greeks|assignment|bto|sto|dtc|otc)|explain|define|meaning of|how does.*work)",
            priority=2,
            tools=[],  # No tools - answer from training materials
            description="Asking for definitions or conceptual explanations",
            examples=[
                "What is assignment?",
                "What does BTO mean?",
                "What are the Greeks?",
                "Explain the wheel strategy",
                "How does a covered call work?"
            ]
        ),

        # CONCEPTUAL - Terminology questions (what does X mean/imply)
        CategoryPattern(
            category="conceptual",
            pattern=r"((what|how) (does|would|will) \w+|\w+ would) (mean|imply|stand for)",
            priority=2,
            tools=[],
            description="Terminology questions - what terms mean",
            examples=[
                "What does BTO mean?",
                "STO would imply?",
                "What would that mean?",
                "BTC would mean what?"
            ]
        ),

        # CONCEPTUAL - Terminology confusion (BTO vs buy shares, etc.)
        CategoryPattern(
            category="conceptual",
            pattern=r"(do i bto|bto (them|shares|stock)|bto or (buy|sell))",
            priority=2,
            tools=[],
            description="Terminology confusion questions",
            examples=[
                "When I get assigned shares, do I BTO them or just buy them?",
                "Do I BTO shares when assigned?"
            ]
        ),

        # CONCEPTUAL - Premium/credit mechanics
        CategoryPattern(
            category="conceptual",
            pattern=r"do (you|i) (keep|get|retain).*(premium|credit|money)",
            priority=2,
            tools=[],
            description="Mechanics of premiums and credits",
            examples=[
                "Do you keep the premiums on the CSP?",
                "Do I get to keep the credit if I close early?",
                "Do you keep premium when closing position?"
            ]
        ),

        # CONCEPTUAL - Strategy mechanism questions
        CategoryPattern(
            category="conceptual",
            pattern=r"(would|is|can) (selling|buying).*(be a play|work|be done|still (a |)play)",
            priority=2,
            tools=[],
            description="Asking how a strategy works or if it's valid",
            examples=[
                "Would selling a call without shares be a play?",
                "Is naked calling a thing?",
                "Can selling puts work in a bear market?"
            ]
        ),

        # ANALYSIS - Ticker risk evaluation (too risky, too expensive, etc.)
        CategoryPattern(
            category="analysis",
            pattern=r"is \w+ (too |)(good|bad|safe|risky|worth|expensive|cheap|overpriced|a good)",
            priority=3,
            tools=["get_community_messages", "get_market_sentiment"],
            description="Evaluating specific ticker risk or value",
            examples=[
                "Is AAPL a good wheel stock?",
                "Is TSLA too risky?",
                "Is AAPL at $175 too expensive?",
                "Is this trade worth it?"
            ]
        ),

        # ANALYSIS - Community sentiment (what are PEOPLE doing, not what ARE things)
        CategoryPattern(
            category="analysis",
            pattern=r"(what|how).*(community|people|everyone|others).*(saying|think|trading|discussing|feel)",
            priority=3,
            tools=["get_community_messages"],
            description="Asking about community sentiment or activity",
            examples=[
                "What's the community saying about TSLA?",
                "What are people trading?",
                "How does everyone feel about the market?"
            ]
        ),

        # RECOMMENDATION - Timeframe mentioned (needs current data)
        CategoryPattern(
            category="recommendation",
            pattern=r"(next week|this week|this month|upcoming|soon|tomorrow)",
            priority=4,
            tools=["scan_options_chain"],
            description="Mentions timeframe - needs current market data",
            examples=[
                "What's good for next week?",
                "Any upcoming opportunities?",
                "What should I trade this week?"
            ]
        ),

        # ANALYSIS - Market timing
        CategoryPattern(
            category="analysis",
            pattern=r"(is (now|this) a good time|should i (wait|enter))",
            priority=5,
            tools=["get_market_sentiment"],
            description="Asking about market timing",
            examples=[
                "Is now a good time to trade?",
                "Should I wait for a pullback?",
                "Is this a good entry point?"
            ]
        ),

        # STRATEGIC - Ticker-specific position management (check before general strategic)
        CategoryPattern(
            category="strategic_ticker",
            pattern=r"((own|have|holding|assigned).*(shares|position|stock)|thoughts on.*(shares|position)|wheeling.*shares)",
            priority=9,
            tools=["scan_options_chain", "get_community_messages"],
            description="Position management for specific ticker - needs current data",
            examples=[
                "I own 103 shares of KIM down 5.5%, should I exit?",
                "Thoughts on wheeling out of 300 MSTX shares?",
                "I have 100 shares of AAPL at $180, should I sell CCs?"
            ]
        ),

        # STRATEGIC - When/why/how to apply concepts (lower priority)
        CategoryPattern(
            category="strategic",
            pattern=r"^(when|why|how) (should|do|can|to|i)",
            priority=10,
            tools=[],  # LLM decides based on context
            description="Strategic questions about when/why/how to apply concepts",
            examples=[
                "When should I roll my call?",
                "Why use delta 0.30 instead of 0.40?",
                "How do I manage assignment?"
            ]
        ),

        # DEFAULT - Catch-all for anything else
        CategoryPattern(
            category="strategic",
            pattern=r".*",  # Matches everything
            priority=99,
            tools=[],  # LLM decides
            description="General strategic question",
            examples=[]
        ),
    ]

    @classmethod
    def classify(cls, question: str) -> dict:
        """
        Classify a question and determine which tools to call.

        Args:
            question: User's question text

        Returns:
            {
                'category': str,
                'tools': List[str],
                'confidence': str,
                'matched_pattern': str,
                'description': str,
                'timestamp': str,
                'question': str
            }
        """
        if not question or not question.strip():
            return {
                "category": "strategic",
                "tools": [],
                "confidence": "low",
                "matched_pattern": None,
                "description": "Empty question",
                "timestamp": datetime.now().isoformat(),
                "question": question
            }

        q_lower = question.lower().strip()

        # Find first matching pattern (sorted by priority)
        for pattern in sorted(cls.PATTERNS, key=lambda p: p.priority):
            if re.search(pattern.pattern, q_lower):
                result = {
                    "category": pattern.category,
                    "tools": pattern.tools.copy(),  # Copy to avoid mutation
                    "confidence": "high" if pattern.priority < 10 else "medium",
                    "matched_pattern": pattern.pattern,
                    "description": pattern.description,
                    "timestamp": datetime.now().isoformat(),
                    "question": question
                }

                logger.info(
                    f"Classified as '{pattern.category}' "
                    f"(pattern: {pattern.pattern[:60]}...) "
                    f"→ tools: {pattern.tools}"
                )

                return result

        # Should never reach here due to catch-all pattern
        logger.warning(f"No pattern matched for: {question[:100]}")
        return {
            "category": "strategic",
            "tools": [],
            "confidence": "low",
            "matched_pattern": None,
            "description": "No pattern matched",
            "timestamp": datetime.now().isoformat(),
            "question": question
        }

    @classmethod
    def get_examples(cls) -> dict[str, list[str]]:
        """Get example questions for each category (useful for testing)"""
        examples_by_category: dict[str, list[str]] = {}

        for pattern in cls.PATTERNS:
            if pattern.category not in examples_by_category:
                examples_by_category[pattern.category] = []
            examples_by_category[pattern.category].extend(pattern.examples)

        return examples_by_category
