#!/usr/bin/env python3
"""
Admin FAQ Modal for adding guild-specific content to RAG.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import asyncio
import logging

import discord

from faq_manager import FAQManager


logger = logging.getLogger(__name__)


class AdminFAQModal(discord.ui.Modal):
    """Modal for users to add FAQ entries to guild-specific RAG"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            title="AI Assistant - Add FAQ",
            *args,
            **kwargs
        )

        # FAQ Question (short)
        self.question_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Question",
            placeholder="e.g., 'What is the wheel strategy?'",
            style=discord.TextStyle.short,
            max_length=200,
            required=True
        )

        # FAQ Answer (long)
        self.answer_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Answer",
            placeholder="Provide a comprehensive answer...",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True
        )

        self.add_item(self.question_input)
        self.add_item(self.answer_input)

        # Store guild_id for guild-specific RAG
        self.guild_id: int | None = None

    def set_guild_id(self, guild_id: int | None) -> None:
        """Set the guild ID for guild-specific FAQ storage"""
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission with validation and vector DB insertion"""
        question = self.question_input.value.strip()
        answer = self.answer_input.value.strip()
        user = interaction.user.name

        logger.info(f"User {user} submitting FAQ: '{question[:50]}...'")

        # Defer response since validation + DB operations take time
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # Create FAQ manager
            faq_mgr = FAQManager(guild_id=self.guild_id)

            # Step 1: Validate FAQ quality
            validation_result = await asyncio.to_thread(
                faq_mgr.validate_faq_quality,
                question,
                answer
            )

            # Check validation result
            if not validation_result["is_valid"]:
                # FAQ failed validation - build response with length limits
                issues = validation_result.get("issues", [])[:5]  # Max 5 issues
                suggestions = validation_result.get("suggestions", [])[:3]  # Max 3 suggestions
                reasoning = validation_result.get("reasoning", "N/A")

                # Truncate reasoning if too long
                if len(reasoning) > 500:
                    reasoning = reasoning[:497] + "..."

                issues_text = "\n".join(f"• {issue[:150]}" for issue in issues)  # Truncate each issue
                suggestions_text = "\n".join(f"• {sug[:150]}" for sug in suggestions)  # Truncate each suggestion

                response_parts = [
                    f"❌ **FAQ Validation Failed** (Quality Score: {validation_result['score']:.1%})\n",
                    f"**Issues Found:**\n{issues_text}\n"
                ]

                if suggestions:
                    response_parts.append(f"**Suggestions:**\n{suggestions_text}\n")

                response_parts.extend([
                    f"**Reasoning:** {reasoning}\n",
                    "Please revise and try again."
                ])

                response = "\n".join(response_parts)

                # Final safety check - Discord has 2000 char limit
                if len(response) > 1900:
                    response = response[:1897] + "..."

                await interaction.followup.send(response, ephemeral=True)
                logger.info(f"FAQ rejected for {user}: score {validation_result['score']:.2f}")
                return

            # Step 2: Add to vector database
            success = await asyncio.to_thread(
                faq_mgr.add_faq_to_vector_db,
                question,
                answer,
                user
            )

            if not success:
                await interaction.followup.send(
                    "❌ **Database Error**\n\n"
                    "FAQ passed validation but failed to save to database.\n"
                    "Please try again or contact a developer.",
                    ephemeral=True
                )
                return

            # Step 3: Success response
            response_parts = [
                f"✅ **FAQ Added Successfully** (Quality Score: {validation_result['score']:.1%})\n",
                f"**Question:** {question[:150]}{'...' if len(question) > 150 else ''}\n",
                f"**Answer Preview:** {answer[:200]}{'...' if len(answer) > 200 else ''}\n",
                f"**Added by:** {user}\n"
            ]

            if validation_result.get("suggestions"):
                response_parts.append("\n**💡 Tips for Future FAQs:**")
                for sug in validation_result["suggestions"][:3]:  # Limit to 3 suggestions
                    response_parts.append(f"• {sug[:150]}")  # Truncate each suggestion

            response_parts.append("\n*Your FAQ is now available to the AI Assistant!*")

            response_text = "\n".join(response_parts)

            # Final safety check - Discord has 2000 char limit
            if len(response_text) > 1900:
                response_text = response_text[:1897] + "..."

            await interaction.followup.send(response_text, ephemeral=True)

            logger.info(
                f"FAQ successfully added by {user} to guild {self.guild_id} "
                f"(score: {validation_result['score']:.2f})"
            )

        except Exception as e:
            logger.error(f"Error in FAQ modal submission: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ **Unexpected Error**\n\n"
                f"Failed to process FAQ: {e!s}\n\n"
                f"Please try again or contact a developer.",
                ephemeral=True
            )
