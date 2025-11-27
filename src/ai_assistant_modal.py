#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import logging

import discord

import constants as const
from rag_analytics import RAGAnalytics
from system_settings import get_settings


# Get a logger instance
logger = logging.getLogger(__name__)


class AIAssistantModal(discord.ui.Modal):
    """Modal for AI Assistant interactions with RAG-enhanced learning"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            title="AI Wheel Strategy Assistant",
            *args,
            **kwargs
        )

        # Query type selection instruction (we'll handle this in the query field)
        self.query_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Your Question or Topic",
            placeholder="e.g., 'Explain covered calls' or 'How do I select strikes?'",
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=True
        )

        # Additional context for better RAG retrieval
        self.context_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Additional Context (Optional)",
            placeholder="Add any relevant details, experience level, or specific aspects you want to explore...",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False
        )

        self.add_item(self.query_input)
        self.add_item(self.context_input)

        # Store guild_id for guild-specific RAG
        self.guild_id: int | None = None

    def set_guild_id(self, guild_id: int | None) -> None:
        """Set the guild ID for guild-specific RAG content"""
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission and process AI assistant query"""
        query = self.query_input.value.strip()
        context = self.context_input.value.strip()
        user = interaction.user.name

        # Log the interaction
        logger.info(f"AI Assistant query from {user}: '{query[:100]}...'")

        # Defer response since RAG retrieval + LLM generation takes time
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            from rag import WheelStrategyTutor

            # Get AI tutor model from system settings
            settings = get_settings()
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

            # Initialize tutor with configured model and guild-specific content
            tutor_instance = WheelStrategyTutor(model=model, guild_id=self.guild_id)

            # Combine query with context
            full_query = query
            if context:
                full_query = f"{query}\n\nAdditional context: {context}"

            # Determine if this is a "learn" query (topic-focused) or "ask" query (question)
            # Simple heuristic: if it starts with question words or contains "?", treat as question
            question_indicators = ["how", "what", "when", "where", "why", "which", "should", "can", "is", "are", "do", "does"]
            is_question = (
                "?" in query or
                any(query.lower().startswith(word) for word in question_indicators)
            )

            # Run appropriate method in thread to avoid blocking event loop
            if is_question:
                result = await asyncio.to_thread(
                    tutor_instance.ask,
                    question=full_query,
                    n_results=3,
                    temperature=0.7
                )
                header_emoji = "❓"
                header_label = "Question"
            else:
                result = await asyncio.to_thread(
                    tutor_instance.explain_topic,
                    topic=full_query,
                    n_results=5,
                    temperature=0.7
                )
                header_emoji = "📚"
                header_label = "Learning"

            # Format response with sources
            response_parts = [
                f"{header_emoji} **{header_label}:** {query}\n",
                result["answer"]
            ]

            if result["sources"]:
                response_parts.append("\n\n📖 **Training Materials Used:**")
                for source in result["sources"]:
                    response_parts.append(f"• {source}")

            response_text = "\n".join(response_parts)

            # Log analytics
            try:
                analytics = RAGAnalytics()
                query_type = "ask" if is_question else "explain_topic"
                # Extract raw chunks with metadata for analytics
                chunks = result.get("chunks", [])
                await asyncio.to_thread(
                    analytics.log_query,
                    username=user,
                    query_type=query_type,
                    query_text=query,
                    sources=chunks,
                    guild_id=self.guild_id,
                    n_results=len(chunks),
                    model=model
                )
            except Exception as e:
                logger.warning(f"Failed to log RAG analytics: {e}")

            # Send response (handle long messages by chunking)
            await self._send_long_response(interaction, response_text)

            logger.info(f"AI Assistant responded to {user} using {len(result['sources'])} sources")

        except FileNotFoundError as e:
            logger.error(f"Vector store not found: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ **AI Assistant Not Initialized**\n\n"
                "The training materials vector store hasn't been created yet.\n\n"
                "**Setup Required:**\n"
                "```bash\n"
                "python scripts/rag/create_vector_store.py\n"
                "```\n"
                "Contact an administrator to set up the AI assistant.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error in AI Assistant modal: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error processing your request: {e!s}\n\n"
                f"Please try again or rephrase your query.",
                ephemeral=True
            )

    async def _send_long_response(self, interaction: discord.Interaction, text: str) -> None:
        """Send long responses by chunking if necessary"""
        # Discord message limit is 2000 characters
        max_length = 2000

        if len(text) <= max_length:
            await interaction.followup.send(text, ephemeral=True)
            return

        # Split into chunks at newlines to preserve formatting
        chunks = []
        current_chunk = ""

        for line in text.split("\n"):
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += line

        if current_chunk:
            chunks.append(current_chunk)

        # Send first chunk as followup, rest as new messages
        for i, chunk in enumerate(chunks):
            if i == 0:
                await interaction.followup.send(chunk, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"**...continued ({i+1}/{len(chunks)})**\n{chunk}",
                    ephemeral=True
                )
