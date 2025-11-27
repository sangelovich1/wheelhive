"""
AI Wheel Strategy Tutor with RAG integration.

Combines training materials retrieval with LLM generation for interactive learning.

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import anthropic
import requests

import constants as const
from llm_provider import LLMProvider, create_llm_provider
from rag.question_classifier import QuestionClassifier
from rag.retriever import TrainingMaterialsRetriever
from system_settings import get_settings


logger = logging.getLogger(__name__)


class WheelStrategyTutor:
    """
    AI tutor for the wheel strategy.

    Uses RAG to retrieve relevant training materials and LLM to generate
    educational responses with citations.
    """

    def __init__(
        self,
        retriever: TrainingMaterialsRetriever | None = None,
        model: str = "claude-sonnet",
        guild_id: int | None = None,
        username: str | None = None,
        mcp_url: str | None = None,
    ):
        """
        Initialize tutor.

        Args:
            retriever: Optional retriever instance (creates default if None)
            model: LLM model to use (default: claude-sonnet)
            guild_id: Guild ID for guild-specific training materials and community data (REQUIRED for security)
            username: Optional username for personalized responses (watchlist, etc.)
            mcp_url: Optional MCP server URL (default: from system settings)

        Raises:
            ValueError: If guild_id is None (prevents data leakage)
        """
        # SECURITY: Require guild_id to prevent cross-guild data leakage
        if guild_id is None:
            raise ValueError(
                "guild_id is required for WheelStrategyTutor. "
                "Passing None would allow tools like get_community_messages to access "
                "all guilds' data, creating a security/privacy risk. "
                "For testing, use a specific test guild_id."
            )

        self.retriever = retriever or TrainingMaterialsRetriever(guild_id=guild_id)
        self.model = model
        self.guild_id = guild_id
        self.username = username
        self.llm_provider: LLMProvider | None = None

        # MCP configuration for tool access
        if mcp_url:
            self.mcp_url = mcp_url
        else:
            settings = get_settings()
            self.mcp_url = settings.get(const.SETTING_TRADING_MCP_URL, "http://localhost:8000")

        self.anthropic_client: anthropic.Anthropic | None = None

        logger.info(
            f"Initialized WheelStrategyTutor (model={model}, guild_id={guild_id}, username={username}, mcp_url={self.mcp_url})"
        )

    def _get_llm_provider(self) -> LLMProvider:
        """Lazy-load LLM provider (for non-MCP calls)."""
        if self.llm_provider is None:
            self.llm_provider = create_llm_provider(model_key=self.model)
        return self.llm_provider

    def _get_anthropic_client(self) -> anthropic.Anthropic:
        """Lazy-load Anthropic client for MCP tool calls."""
        if self.anthropic_client is None:
            import os

            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set - required for MCP tool access")
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        return self.anthropic_client

    def _get_anthropic_model_id(self) -> str:
        """
        Convert model key to Anthropic model ID.

        Maps model keys like 'claude-sonnet' to actual API model IDs
        like 'claude-sonnet-4-5-20250929'.

        Returns:
            Anthropic model ID string
        """
        # Map model keys to Anthropic model IDs
        model_key_to_id = {
            "claude-sonnet": "claude-sonnet-4-5-20250929",
            "claude-haiku": "claude-haiku-4-5-20251001",
        }

        # If it's already a full model ID, return as-is
        if self.model in model_key_to_id.values():
            return self.model

        # Otherwise, map the key
        return model_key_to_id.get(self.model, self.model)

    def _get_tutor_tools(self) -> list[dict[str, Any]]:
        """
        Get market data tools for AI tutor (subset of all MCP tools).

        The tutor only needs market data tools for examples, not user portfolio tools.

        Returns:
            List of tools in Anthropic/OpenAI format
        """
        try:
            response = requests.get(f"{self.mcp_url}/tools/list", timeout=5)
            response.raise_for_status()
            all_tools = response.json()["tools"]

            # Tutor-specific tools (market data + community knowledge + personalization)
            tutor_tool_names = {
                # Market data tools
                "scan_options_chain",  # Get current option premiums
                "get_detailed_option_chain",  # Detailed chain with Greeks
                "get_option_expiration_dates",  # Available expirations
                "get_historical_stock_prices",  # Current/historical prices
                "get_market_sentiment",  # VIX, market conditions
                # Community knowledge tools
                "get_community_messages",  # Community discussions about tickers/users
                # Personalization tools
                "query_watchlist",  # User's watchlist for personalized recommendations
            }

            # Filter to tutor tools
            tutor_tools = [tool for tool in all_tools if tool["name"] in tutor_tool_names]

            # Convert to Anthropic/OpenAI format
            formatted_tools = []
            for tool in tutor_tools:
                input_schema = tool["inputSchema"].copy()

                # Remove guild_id/username from tools since we auto-inject them
                params_to_remove = []
                if tool["name"] in ["get_community_messages", "get_community_trades"]:
                    params_to_remove.append("guild_id")
                if tool["name"] in ["query_watchlist"]:
                    params_to_remove.extend(["username", "guild_id"])

                if params_to_remove and "properties" in input_schema:
                    # Deep copy to avoid modifying original
                    input_schema = {
                        "type": input_schema.get("type"),
                        "properties": {
                            k: v
                            for k, v in input_schema.get("properties", {}).items()
                            if k not in params_to_remove
                        },
                        "required": [
                            r for r in input_schema.get("required", []) if r not in params_to_remove
                        ],
                    }

                formatted_tools.append(
                    {
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": input_schema,
                    }
                )

            logger.info(
                f"Loaded {len(formatted_tools)} tools for tutor (market data + community knowledge)"
            )
            return formatted_tools

        except Exception as e:
            logger.warning(
                f"Failed to fetch MCP tools (tutor will work without real-time data): {e}"
            )
            return []

    def _call_mcp_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Call MCP server tool and return result.

        Args:
            tool_name: Name of the tool to call
            tool_input: Tool arguments

        Returns:
            Tool result as formatted string
        """
        try:
            # Auto-inject guild_id for community tools (not exposed to LLM, injected by tutor)
            if self.guild_id and tool_name in ["get_community_messages", "get_community_trades"]:
                tool_input["guild_id"] = str(self.guild_id)
                logger.info(f"Auto-injected guild_id={self.guild_id} for {tool_name}")

            # Auto-inject username and guild_id for personalization tools
            if tool_name in ["query_watchlist"]:
                if self.username:
                    tool_input["username"] = self.username
                    logger.info(f"Auto-injected username={self.username} for {tool_name}")
                if self.guild_id:
                    tool_input["guild_id"] = str(self.guild_id)
                    logger.info(f"Auto-injected guild_id={self.guild_id} for {tool_name}")

            logger.info(f"Calling MCP tool: {tool_name} with input: {tool_input}")

            # Timeout increased to 120s to handle batch operations like scanning multiple tickers
            response = requests.post(
                f"{self.mcp_url}/tools/call",
                json={"name": tool_name, "arguments": tool_input},
                timeout=120,
            )
            response.raise_for_status()

            result = response.json()

            if result.get("isError"):
                error_text = result["content"][0]["text"]
                logger.warning(f"MCP tool {tool_name} returned error: {error_text}")
                return f"Error: {error_text}"

            # Extract result
            content = result.get("content", [{}])[0]
            return content.get("text", "No result")  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}", exc_info=True)
            return f"Error calling tool: {e!s}"

    def _build_market_context(self) -> str:
        """
        Build live market context for more relevant examples.

        Returns:
            Formatted market context string with current date, upcoming expirations, etc.
        """
        now = datetime.now()

        # Calculate next few monthly expirations (3rd Friday of month)
        def get_third_friday(year: int, month: int) -> datetime:
            """Get 3rd Friday of the month."""
            # Find first day of month
            first_day = datetime(year, month, 1)
            # Find first Friday (weekday 4 = Friday)
            days_until_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_until_friday)
            # Add 2 weeks to get 3rd Friday
            third_friday = first_friday + timedelta(weeks=2)
            return third_friday

        # Get next 3 monthly expirations
        expirations = []
        current_month = now.month
        current_year = now.year

        for i in range(3):
            month = current_month + i
            year = current_year
            if month > 12:
                month -= 12
                year += 1

            exp_date = get_third_friday(year, month)
            if exp_date > now:  # Only future expirations
                expirations.append(exp_date)

        # Format market context
        context_parts = [
            "=== LIVE MARKET CONTEXT ===",
            "",
            f"Current Date: {now.strftime('%A, %B %d, %Y')}",
            f"Market Hours: {'OPEN' if now.weekday() < 5 and 9 <= now.hour < 16 else 'CLOSED'}",
            "",
            "Upcoming Monthly Options Expirations:",
        ]

        for i, exp_date in enumerate(expirations[:3], 1):
            days_away = (exp_date - now).days
            context_parts.append(f"  {i}. {exp_date.strftime('%b %d, %Y')} ({days_away} days away)")

        context_parts.extend(
            [
                "",
                "When providing examples:",
                "- Use realistic current/recent dates for trades",
                "- Reference upcoming expirations from the list above",
                "- Use typical wheel strategy tickers (TSLA, AAPL, NVDA, AMD, MSTR, etc.)",
                "- Use current price ranges (e.g., TSLA ~$250, AAPL ~$175, NVDA ~$130)",
                "- Make examples feel current and actionable",
                "",
            ]
        )

        return "\n".join(context_parts)

    def ask(self, question: str, n_results: int = 3, temperature: float = 0.7) -> dict[str, Any]:
        """
        Ask the AI tutor a question about the wheel strategy.

        Args:
            question: User's question
            n_results: Number of training material chunks to retrieve
            temperature: LLM temperature (0.0-2.0, default 0.7)

        Returns:
            Dict with keys:
            - answer: AI tutor's response
            - sources: List of source documents cited
            - chunks: Raw retrieved chunks (for debugging)
        """
        logger.info("=" * 80)
        logger.info("TUTOR ASK QUESTION")
        logger.info(f"Question: {question}")
        logger.info(f"Settings: n_results={n_results}, temperature={temperature}")
        logger.info("=" * 80)

        # Classify question to determine tool usage strategy
        classification = QuestionClassifier.classify(question)
        logger.info(
            f"Classification: {classification['category']} (confidence: {classification['confidence']})"
        )
        logger.info(f"Suggested tools: {classification['tools']}")

        # Retrieve relevant training materials
        retrieval_result = self.retriever.retrieve_for_question(
            question=question, n_results=n_results
        )

        logger.info(
            f"Retrieved {len(retrieval_result['chunks'])} chunks from {len(retrieval_result['sources'])} sources"
        )

        # Build LLM prompt with classification-based tool guidance
        prompt = self._build_tutor_prompt_with_classification(
            question=question,
            training_context=retrieval_result["context"],
            classification=classification,
        )

        # Determine which tools to make available
        if classification["category"] == "conceptual":
            # Conceptual questions: no tools needed
            tools = None
            logger.info("Conceptual question - tools disabled")
        else:
            # All other categories: tools available (LLM decides)
            tools = self._get_tutor_tools()
            logger.info(f"Tools available: {len(tools) if tools else 0}")

        # Generate response with tool calling
        response = self._generate_with_tools(
            prompt=prompt,
            temperature=temperature,
            max_tokens=2000,
            tools=tools,  # type: ignore[arg-type]
        )

        logger.info(
            f"Final answer: {len(response)} chars, {len(retrieval_result['sources'])} sources cited"
        )

        return {
            "answer": response,
            "sources": retrieval_result["sources"],
            "chunks": retrieval_result["chunks"],
        }

    def explain_topic(
        self, topic: str, n_results: int = 5, temperature: float = 0.7
    ) -> dict[str, Any]:
        """
        Get a comprehensive explanation of a topic.

        Use this for educational queries like "explain assignment" vs
        specific questions like "what should I do if assigned?"

        Args:
            topic: Topic to explain (e.g., "assignment", "covered calls")
            n_results: Number of chunks to retrieve
            temperature: LLM temperature

        Returns:
            Dict with answer, sources, and chunks
        """
        logger.info("=" * 80)
        logger.info("TUTOR EXPLAIN TOPIC")
        logger.info(f"Topic: {topic}")
        logger.info(f"Settings: n_results={n_results}, temperature={temperature}")
        logger.info("=" * 80)

        # Retrieve materials
        retrieval_result = self.retriever.retrieve_for_topic(topic=topic, n_results=n_results)

        logger.info(
            f"Retrieved {len(retrieval_result['chunks'])} chunks from {len(retrieval_result['sources'])} sources"
        )

        # Build educational prompt
        prompt = self._build_explanation_prompt(topic, retrieval_result["context"])

        # Get tools for live market data
        tools = self._get_tutor_tools()

        # Generate response with tool calling
        response = self._generate_with_tools(
            prompt=prompt, temperature=temperature, max_tokens=2500, tools=tools
        )

        logger.info(
            f"Final explanation: {len(response)} chars, {len(retrieval_result['sources'])} sources cited"
        )

        return {
            "answer": response,
            "sources": retrieval_result["sources"],
            "chunks": retrieval_result["chunks"],
        }

    def _generate_with_tools(
        self, prompt: str, temperature: float, max_tokens: int, tools: list[dict[str, Any]]
    ) -> str:
        """
        Generate response using Anthropic SDK with MCP tool calling.

        Args:
            prompt: System prompt with training materials and context
            temperature: LLM temperature
            max_tokens: Maximum tokens to generate
            tools: List of MCP tools available to the LLM

        Returns:
            Final text response from the LLM
        """
        client = self._get_anthropic_client()

        # Initial request
        messages = [{"role": "user", "content": prompt}]

        # Tool use loop (similar to LLMAnalyzer)
        max_iterations = 5
        iteration = 0
        all_tool_calls: list[Any] = []  # Track all tool calls for logging

        logger.info("=" * 80)
        logger.info("TUTOR GENERATION START")
        logger.info("=" * 80)

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"--- Iteration {iteration}/{max_iterations} ---")

            # Call Claude with tools (use Anthropic model ID, not model key)
            model_id = self._get_anthropic_model_id()
            response = client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,  # type: ignore[arg-type]
                tools=tools if tools else anthropic.NOT_GIVEN,  # type: ignore[arg-type]
            )

            # Check if we got a final answer
            text_blocks = [block for block in response.content if block.type == "text"]
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]

            # Log what we got back
            if text_blocks:
                logger.info(f"LLM returned text block ({len(text_blocks[0].text)} chars)")
            if tool_use_blocks:
                logger.info(f"LLM requesting {len(tool_use_blocks)} tool call(s)")

            # If no tool use, we're done
            if not tool_use_blocks:
                if text_blocks:
                    final_response = text_blocks[0].text
                    logger.info("=" * 80)
                    logger.info("TUTOR GENERATION COMPLETE")
                    logger.info(f"Total iterations: {iteration}")
                    logger.info(f"Total tool calls: {len(all_tool_calls)}")
                    logger.info(f"Response length: {len(final_response)} chars")
                    if all_tool_calls:
                        logger.info("Tools used:")
                        for tc in all_tool_calls:
                            logger.info(f"  - {tc['tool']}: {tc['input']}")
                    logger.info("FINAL RESPONSE:")
                    logger.info("-" * 80)
                    logger.info(final_response)
                    logger.info("=" * 80)
                    return final_response
                logger.warning("No text or tool_use blocks in response")
                return "Sorry, I couldn't generate a response."

            # Execute tool calls
            # Add assistant's response to messages
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,  # type: ignore[dict-item]
                }
            )

            # Execute tools and collect results
            tool_results = []
            for tool_use in tool_use_blocks:
                tool_name = tool_use.name
                tool_input = tool_use.input

                logger.info(f"  Tool {len(all_tool_calls)+1}: {tool_name}")
                logger.info(f"    Input: {tool_input}")

                result = self._call_mcp_tool(tool_name, tool_input)  # type: ignore[arg-type]
                result_preview = result[:200] + "..." if len(result) > 200 else result
                logger.info(f"    Result preview: {result_preview}")

                # Track for summary
                all_tool_calls.append(
                    {"tool": tool_name, "input": tool_input, "result_length": len(result)}
                )

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": tool_use.id, "content": result}
                )

            # Add tool results to messages
            messages.append(
                {
                    "role": "user",
                    "content": tool_results,  # type: ignore[dict-item]
                }
            )

            # Continue loop to get LLM's next response

        # If we hit max iterations
        logger.warning(f"Hit max iterations ({max_iterations}) in tool use loop")
        logger.warning(f"Total tool calls made: {len(all_tool_calls)}")
        return "Sorry, I couldn't complete the response (too many tool calls)."

    def _build_tutor_prompt(self, question: str, training_context: str) -> str:
        """
        Build LLM prompt for Q&A tutoring.

        Args:
            question: User's question
            training_context: Formatted training materials

        Returns:
            Complete prompt string
        """
        from datetime import datetime

        import pytz  # type: ignore[import-untyped]

        # Get current timestamp in MST
        mst = pytz.timezone("America/Denver")
        current_time = datetime.now(mst).strftime("%Y-%m-%d %H:%M MST")

        market_context = self._build_market_context()

        return f"""You are an AI tutor for the wheel strategy. Answer CONCISELY.

CURRENT DATE/TIME: {current_time}

RESPONSE FORMAT:
- MAXIMUM 2-3 short paragraphs (target: 400-600 chars total)
- Use examples FROM THE TRAINING MATERIALS ONLY - do NOT create your own examples with made-up prices
- If training materials have examples, use them exactly as written
- Only use tools for live market data if user asks about specific current prices/conditions
- End with: (Source: filename, p.X)

TOOL USAGE (use sparingly, only when needed):
- get_community_messages: User/ticker discussions
- scan_options_chain: Only if user asks for CURRENT premiums
- get_historical_stock_prices: Only if user asks for CURRENT prices
- get_market_sentiment: Only if user asks about CURRENT market conditions

IMPORTANT RULES:
- NEVER invent example prices or ticker prices
- If training materials have examples, use those EXACTLY
- If no example exists in training materials, explain conceptually without specific numbers
- If question mentions a username, call get_community_messages FIRST

{market_context}

{training_context}

Question: {question}

Give a BRIEF answer using training material examples ONLY. Target 400-600 chars. Cite sources."""

    def _build_tutor_prompt_with_classification(
        self, question: str, training_context: str, classification: dict[str, Any]
    ) -> str:
        """
        Build LLM prompt with strong tool usage guidance based on classification.

        Args:
            question: User's question
            training_context: Formatted training materials
            classification: Question classification result

        Returns:
            Complete prompt string with tool guidance
        """
        from datetime import datetime

        import pytz

        # Get current timestamp in MST
        mst = pytz.timezone("America/Denver")
        current_time = datetime.now(mst).strftime("%Y-%m-%d %H:%M MST")

        market_context = self._build_market_context()

        # Build tool usage guidance based on classification
        category = classification["category"]
        tools = classification["tools"]

        if category == "conceptual":
            tool_guidance = """TOOL USAGE: NONE REQUIRED
This is a conceptual question. Answer from training materials only.
DO NOT call any tools - all information needed is in the training materials below."""

        elif category == "recommendation":
            tools_list = "\n".join(f"- {tool} (REQUIRED - no exceptions)" for tool in tools)
            tool_guidance = f"""TOOL USAGE: REQUIRED

Based on this question type, you MUST call these tools AT MINIMUM:
{tools_list}

You MAY also call additional tools if relevant:
- get_market_sentiment (if market conditions affect the recommendation)
- get_community_messages (if ticker discussion would add value)

DO NOT answer without calling the required tools above.
Training materials provide strategy concepts, but you need CURRENT market data for recommendations."""

        elif category == "analysis":
            tools_list = " OR ".join(tools) if tools else "appropriate tools"
            tool_guidance = f"""TOOL USAGE: STRONGLY RECOMMENDED

Based on this question type, you should call:
- {tools_list} (at least one)

Additional tools available if needed:
- scan_options_chain (for current premiums/Greeks)
- get_market_sentiment (for market context)

You may answer without tools ONLY if training materials fully address the question."""

        elif category == "strategic_ticker":
            tools_list = "\n".join(f"- {tool} (STRONGLY RECOMMENDED)" for tool in tools)
            tool_guidance = f"""TOOL USAGE: STRONGLY RECOMMENDED

This question is about a SPECIFIC TICKER POSITION.
You should call at MINIMUM:
{tools_list}

Why these tools are needed:
- scan_options_chain: See current strikes, IV, and premium for this ticker
- get_community_messages: See what community is saying/trading

Training materials provide general strategy principles, but you need CURRENT market data
to give good advice about a specific ticker position."""

        else:  # strategic (general)
            tool_guidance = """TOOL USAGE: OPTIONAL

Training materials likely contain the answer.
Call tools only if you need current market data or community context that isn't in the materials."""

        return f"""You are an AI tutor for the wheel strategy. Answer CONCISELY.

CURRENT DATE/TIME: {current_time}

{tool_guidance}

RESPONSE FORMAT:
- MAXIMUM 2-3 short paragraphs (target: 400-600 chars total)
- Use examples FROM THE TRAINING MATERIALS ONLY - do NOT create your own examples with made-up prices
- If training materials have examples, use them exactly as written
- End with: (Source: filename, p.X)

IMPORTANT RULES:
- NEVER invent ticker prices or option premiums
- If training materials have examples, use those EXACTLY
- If no example exists in training materials, explain conceptually without specific numbers
- If question mentions a username, call get_community_messages FIRST

{market_context}

{training_context}

Question: {question}

Give a BRIEF answer using training material examples ONLY. Target 400-600 chars. Cite sources."""

    def _build_explanation_prompt(self, topic: str, training_context: str) -> str:
        """
        Build LLM prompt for topic explanation.

        Args:
            topic: Topic to explain
            training_context: Formatted training materials

        Returns:
            Complete prompt string
        """
        from datetime import datetime

        import pytz

        # Get current timestamp in MST
        mst = pytz.timezone("America/Denver")
        current_time = datetime.now(mst).strftime("%Y-%m-%d %H:%M MST")

        market_context = self._build_market_context()

        return f"""You are an AI tutor for the wheel strategy. Explain CONCISELY but thoroughly.

CURRENT DATE/TIME: {current_time}

RESPONSE FORMAT:
- MAXIMUM 4-5 paragraphs (target: 800-1200 chars total)
- Structure: definition → how it works → example (if available in materials) → key takeaway
- Use examples FROM THE TRAINING MATERIALS ONLY - do NOT create your own examples with made-up prices
- If training materials have examples, use them exactly as written
- Only use tools for live market data if needed to answer the specific question
- End with: (Source: filename, p.X)

TOOL USAGE (use sparingly - max 2-3 tools, only when needed):
- get_community_messages: User/ticker discussions
- scan_options_chain: Only if user asks for CURRENT premiums
- get_historical_stock_prices: Only if user asks for CURRENT prices
- get_market_sentiment: Only if user asks about CURRENT market conditions

IMPORTANT RULES:
- NEVER invent example prices or ticker prices
- If training materials have examples, use those EXACTLY
- If no example exists in training materials, explain conceptually without specific numbers
- If topic mentions a username, call get_community_messages FIRST

{market_context}

{training_context}

Topic: {topic}

Give a FOCUSED explanation using training material examples ONLY. Target 800-1200 chars. Cite sources."""

    def get_stats(self) -> dict[str, Any]:
        """
        Get tutor statistics.

        Returns:
            Dict with vector store stats
        """
        return self.retriever.get_stats()
