"""
LLM Provider Abstraction Layer

Unified interface for multiple LLM providers using LiteLLM.
Supports Claude (Anthropic), Ollama, and future models.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
import os
from typing import Any

# Third-party imports
import litellm
from litellm import acompletion, completion

# Local application imports
import constants as const
from db import Db
from llm_models import LLMModels
from user_preferences import get_user_preferences


# Get a logger instance
logger = logging.getLogger(__name__)

# Configure LiteLLM
litellm.set_verbose = False  # Set to True for debugging


class LLMProvider:
    """
    Unified LLM provider using LiteLLM for multi-model support.

    Handles:
    - Model selection based on user preferences
    - Tool calling for supported models
    - Fallback strategies for non-tool-calling models
    - API key management and provider configuration
    """

    def __init__(self, username: str | None = None, model_key: str | None = None, metrics_tracker=None, db: Db | None = None):
        """
        Initialize LLM provider.

        Args:
            username: Discord username (used to fetch user's model preference)
            model_key: Override model key (if None, uses user preference or default)
            metrics_tracker: Optional MetricsTracker instance for usage tracking
            db: Database instance (if None, creates new connection)
        """
        self.username = username
        self.user_prefs = get_user_preferences()
        self.metrics_tracker = metrics_tracker

        # Initialize database and LLM models
        if db is None:
            db = Db()
        self.db = db  # Store for later use in _configure_provider()
        self.llm_models = LLMModels(db)

        # Determine which model to use
        if model_key:
            # Explicit model override
            self.model_key = model_key
        elif username:
            # Get user's preference
            self.model_key = self.user_prefs.get_llm_preference(username)
        else:
            # Use default model from database
            default_model = self.llm_models.get_default_model()
            if default_model:
                self.model_key = default_model.model_key
            else:
                raise Exception("No default LLM model configured. Run 'cli.py admin set-default-model <key>' to set one.")

        # Get model configuration from database
        model = self.llm_models.get_model(self.model_key)
        if not model:
            logger.error(f"Invalid model key: {self.model_key}, falling back to default")
            default_model = self.llm_models.get_default_model()
            if not default_model:
                raise Exception("No default LLM model configured. Run 'cli.py admin set-default-model <key>' to set one.")
            model = default_model
            self.model_key = model.model_key

        # Convert LLMModel to dict format for compatibility
        self.model_config = {
            "litellm_model": model.litellm_model,
            "provider": model.provider,
            "tool_calling": model.tool_calling,
            "display_name": model.display_name,
            "quality": model.quality,
            "speed": model.speed,
            "cost_tier": model.cost_tier
        }

        # Get LiteLLM model name
        self.litellm_model = self.model_config["litellm_model"]
        self.provider = self.model_config["provider"]
        self.supports_tool_calling = self.model_config.get("tool_calling", False)

        # Configure provider-specific settings
        self._configure_provider()

        logger.info(
            f"LLM Provider initialized: model={self.model_key}, "
            f"litellm_model={self.litellm_model}, "
            f"provider={self.provider}, "
            f"tool_calling={self.supports_tool_calling}"
        )

    def _configure_provider(self) -> None:
        """Configure provider-specific settings (API keys, base URLs)."""
        if self.provider == "anthropic":
            if not const.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            os.environ["ANTHROPIC_API_KEY"] = const.ANTHROPIC_API_KEY

        elif self.provider == "ollama":
            # Ollama uses base URL, no API key needed
            # Read from SystemSettings (use const.OLLAMA_BASE_URL as fallback)
            from system_settings import get_settings
            settings = get_settings(self.db)
            ollama_url = settings.get(const.SETTING_OLLAMA_BASE_URL, const.OLLAMA_BASE_URL)
            os.environ["OLLAMA_API_BASE"] = ollama_url
            logger.info(f"Ollama configured: base_url={ollama_url}")

    async def acompletion(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Any:
        """
        Async completion call using LiteLLM.

        Args:
            messages: Conversation messages in OpenAI format
            system: System prompt (for Anthropic models)
            tools: Tool definitions (if model supports tool calling)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            LiteLLM completion response
        """
        try:
            # Build completion parameters
            params = {
                "model": self.litellm_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            # Anthropic models use 'system' parameter, others use system message
            if self.provider == "anthropic" and system:
                params["system"] = system
            elif system:
                # Prepend system message for non-Anthropic models
                messages = [{"role": "system", "content": system}] + messages

            # Add tools if supported
            if tools and self.supports_tool_calling:
                params["tools"] = tools

            # Log request (abbreviated)
            logger.info(
                f"LLM request: model={self.litellm_model}, "
                f"messages={len(messages)}, tools={len(tools) if tools else 0}"
            )

            # Call LiteLLM
            response = await acompletion(**params)

            logger.info(f"LLM response received: finish_reason={response.choices[0].finish_reason}")

            return response

        except Exception as e:
            logger.error(f"Error in LLM completion: {e}", exc_info=True)
            raise

    def completion(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Any:
        """
        Synchronous completion call using LiteLLM.

        Args:
            messages: Conversation messages in OpenAI format
            system: System prompt (for Anthropic models)
            tools: Tool definitions (if model supports tool calling)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            LiteLLM completion response
        """
        try:
            # Build completion parameters
            params = {
                "model": self.litellm_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            # Anthropic models use 'system' parameter, others use system message
            if self.provider == "anthropic" and system:
                params["system"] = system
            elif system:
                # Prepend system message for non-Anthropic models
                messages = [{"role": "system", "content": system}] + messages

            # Add tools if supported
            if tools and self.supports_tool_calling:
                params["tools"] = tools

            # Log request (abbreviated)
            logger.info(
                f"LLM request: model={self.litellm_model}, "
                f"messages={len(messages)}, tools={len(tools) if tools else 0}"
            )

            # Call LiteLLM
            response = completion(**params)

            logger.info(f"LLM response received: finish_reason={response.choices[0].finish_reason}")

            # Track usage in metrics
            if self.metrics_tracker and hasattr(response, "usage"):
                try:
                    usage = response.usage
                    self.metrics_tracker.track_llm_usage(
                        username=self.username or "system",
                        model=self.litellm_model,
                        provider=self.provider,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        finish_reason=response.choices[0].finish_reason,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tool_calls_count=len(tools) if tools else 0
                    )
                except Exception as e:
                    logger.warning(f"Failed to track LLM usage in metrics: {e}")

            return response

        except Exception as e:
            logger.error(f"Error in LLM completion: {e}", exc_info=True)
            raise

    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the currently selected model.

        Returns:
            Dictionary with model metadata
        """
        return {
            "model_key": self.model_key,
            "litellm_model": self.litellm_model,
            "display_name": self.model_config.get("display_name"),
            "provider": self.provider,
            "supports_tool_calling": self.supports_tool_calling,
            "quality": self.model_config.get("quality"),
            "speed": self.model_config.get("speed"),
            "cost_tier": self.model_config.get("cost_tier")
        }


def create_llm_provider(username: str | None = None, model_key: str | None = None, metrics_tracker=None, db: Db | None = None) -> LLMProvider:
    """
    Factory function to create LLMProvider instance.

    Args:
        username: Discord username (for fetching user's model preference)
        model_key: Override model key (if None, uses user preference or default)
        metrics_tracker: Optional MetricsTracker instance for usage tracking
        db: Database instance (if None, creates new connection)

    Returns:
        LLMProvider instance
    """
    return LLMProvider(username=username, model_key=model_key, metrics_tracker=metrics_tracker, db=db)


# Utility functions for common operations

def simple_completion_sync(
    prompt: str,
    username: str | None = None,
    model_key: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048
) -> str:
    """
    Synchronous simple completion for a single prompt (no tool calling).

    Args:
        prompt: User prompt
        username: Discord username (for model selection)
        model_key: Override model key
        system: System prompt
        max_tokens: Maximum response tokens

    Returns:
        LLM response text
    """
    try:
        provider = create_llm_provider(username=username, model_key=model_key)

        messages = [{"role": "user", "content": prompt}]

        response = provider.completion(
            messages=messages,
            system=system,
            max_tokens=max_tokens
        )

        # Extract text from response
        content: str = str(response.choices[0].message.content)
        return content

    except Exception as e:
        logger.error(f"Error in simple completion: {e}", exc_info=True)
        return f"Error: {e!s}"


async def simple_completion(
    prompt: str,
    username: str | None = None,
    model_key: str | None = None,
    system: str | None = None,
    max_tokens: int = 2048
) -> str:
    """
    Async simple completion for a single prompt (no tool calling).

    Args:
        prompt: User prompt
        username: Discord username (for model selection)
        model_key: Override model key
        system: System prompt
        max_tokens: Maximum response tokens

    Returns:
        LLM response text
    """
    try:
        provider = create_llm_provider(username=username, model_key=model_key)

        messages = [{"role": "user", "content": prompt}]

        response = await provider.acompletion(
            messages=messages,
            system=system,
            max_tokens=max_tokens
        )

        # Extract text from response
        content: str = str(response.choices[0].message.content)
        return content

    except Exception as e:
        logger.error(f"Error in simple completion: {e}", exc_info=True)
        return f"Error: {e!s}"


def list_available_models(username: str) -> list[dict[str, Any]]:
    """
    List models available to a user based on their tier.

    Args:
        username: Discord username

    Returns:
        List of model info dictionaries
    """
    user_prefs = get_user_preferences()
    available = user_prefs.list_available_models()

    models_info = []
    for model_key, model_config in available:
        models_info.append({
            "model_key": model_key,
            "display_name": model_config["display_name"],
            "description": model_config["description"],
            "provider": model_config["provider"],
            "cost_tier": model_config["cost_tier"],
            "quality": model_config["quality"],
            "speed": model_config["speed"],
            "tool_calling": model_config["tool_calling"]
        })

    return models_info
