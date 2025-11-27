"""
User Preferences Management

Key-value store for user preferences including LLM model selection.
Extensible design allows adding new preference types without schema changes.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
from datetime import datetime
from typing import Any

# Local application imports
import constants as const
from db import Db
from system_settings import get_settings


# Get a logger instance
logger = logging.getLogger(__name__)


class UserPreferences:
    """
    Manages user preferences using a key-value store.

    Supports any preference type via key-value pairs:
    - llm_model: Which AI model to use for analysis
    - Future: notifications, display settings, alerts, etc.
    """

    # Preference keys (constants for type safety)
    PREF_LLM_MODEL = "llm_model"

    def __init__(self, db: Db) -> None:
        """
        Initialize user preferences manager.

        Args:
            db: Database instance
        """
        self.db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create user_preferences table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS user_preferences (
            username TEXT,
            preference_key TEXT,
            preference_value TEXT,
            updated_at TEXT,
            PRIMARY KEY (username, preference_key)
        )
        """
        try:
            self.db.create_table(query)
            logger.info("User preferences table initialized")
        except Exception as e:
            logger.error(f"Error creating user_preferences table: {e}", exc_info=True)
            raise

    def get_preference(self, username: str, key: str, default: str | None = None) -> str | None:
        """
        Get a preference value for a user.

        Args:
            username: Discord username
            key: Preference key
            default: Default value if preference not found

        Returns:
            Preference value or default if not found
        """
        try:
            result = self.db.query_parameterized(
                "SELECT preference_value FROM user_preferences WHERE username = ? AND preference_key = ?",
                (username, key)
            )

            if result and len(result) > 0 and result[0][0]:
                value: str = str(result[0][0])
                return value

            return default

        except Exception as e:
            logger.error(f"Error getting preference {key} for {username}: {e}", exc_info=True)
            return default

    def set_preference(self, username: str, key: str, value: str) -> bool:
        """
        Set a preference value for a user.

        Args:
            username: Discord username
            key: Preference key
            value: Preference value (stored as string)

        Returns:
            True if successful, False otherwise
        """
        try:
            query = """
                INSERT INTO user_preferences (username, preference_key, preference_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username, preference_key)
                DO UPDATE SET
                    preference_value = excluded.preference_value,
                    updated_at = excluded.updated_at
            """
            self.db.execute(query, (username, key, value, datetime.now().isoformat()))
            logger.info(f"Set preference {key}={value} for {username}")
            return True

        except Exception as e:
            logger.error(f"Error setting preference {key} for {username}: {e}", exc_info=True)
            return False

    def delete_preference(self, username: str, key: str) -> bool:
        """
        Delete a preference for a user.

        Args:
            username: Discord username
            key: Preference key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.execute(
                "DELETE FROM user_preferences WHERE username = ? AND preference_key = ?",
                (username, key)
            )
            logger.info(f"Deleted preference {key} for {username}")
            return True

        except Exception as e:
            logger.error(f"Error deleting preference {key} for {username}: {e}", exc_info=True)
            return False

    def get_all_preferences(self, username: str) -> dict[str, str]:
        """
        Get all preferences for a user.

        Args:
            username: Discord username

        Returns:
            Dictionary of key-value pairs
        """
        try:
            result = self.db.query_parameterized(
                "SELECT preference_key, preference_value FROM user_preferences WHERE username = ?",
                (username,)
            )

            preferences = {}
            if result:
                for row in result:
                    preferences[row[0]] = row[1]

            return preferences

        except Exception as e:
            logger.error(f"Error getting all preferences for {username}: {e}", exc_info=True)
            return {}

    # ============================================================
    # LLM Model Preference Helpers
    # ============================================================

    def get_llm_preference(self, username: str) -> str:
        """
        Get user's preferred LLM model.

        Args:
            username: Discord username

        Returns:
            Model key (e.g., 'claude-sonnet', 'ollama-qwen-32b')
            Returns system default if no preference set
        """
        from llm_models import LLMModels

        model_key = self.get_preference(username, self.PREF_LLM_MODEL, None)
        llm_models = LLMModels(self.db)

        # Validate model still exists in database and is active
        if model_key:
            model = llm_models.get_model(model_key)
            if model and model.is_active:
                return model_key
            logger.warning(f"User {username} preference {model_key} is invalid/inactive, using default")

        # No valid preference - return system default
        default_model = llm_models.get_default_model()
        if default_model:
            logger.info(f"Using system default model for {username}: {default_model.model_key}")
            return default_model.model_key

        # Final fallback - read from system settings
        settings = get_settings(self.db)
        fallback: str = str(settings.get(const.SETTING_DEFAULT_LLM_MODEL))
        logger.warning(f"No models available in database, using system settings fallback: {fallback}")
        return fallback

    def set_llm_preference(self, username: str, model_key: str) -> bool:
        """
        Set user's preferred LLM model with validation.

        Args:
            username: Discord username
            model_key: Model key (e.g., 'claude-sonnet', 'ollama-qwen-32b')

        Returns:
            True if successful, False otherwise
        """
        from llm_models import LLMModels

        llm_models = LLMModels(self.db)

        # Validate model exists and is active
        model = llm_models.get_model(model_key)
        if not model or not model.is_active:
            logger.error(f"Invalid or inactive model key: {model_key}")
            return False

        return self.set_preference(username, self.PREF_LLM_MODEL, model_key)

    def list_available_models(self) -> list[tuple]:
        """
        List all available active models.

        Returns:
            List of (model_key, LLMModel) tuples sorted by quality
        """
        from llm_models import LLMModels

        try:
            llm_models = LLMModels(self.db)
            models = llm_models.list_models(active_only=True)

            # Return list of (model_key, LLMModel) tuples
            # Already sorted by quality DESC in list_models()
            return [(model.model_key, model) for model in models]

        except Exception as e:
            logger.error(f"Error listing available models: {e}", exc_info=True)
            return []

    def get_user_summary(self, username: str) -> dict[str, Any]:
        """
        Get comprehensive summary of user's preferences and model details.

        Args:
            username: Discord username

        Returns:
            Dictionary with user preferences and model details
        """
        from llm_models import LLMModels

        try:
            llm_model = self.get_llm_preference(username)
            llm_models = LLMModels(self.db)
            model = llm_models.get_model(llm_model)

            # Get all active model keys for reference
            available_models = llm_models.get_active_model_keys()

            return {
                "username": username,
                "llm_model": llm_model,
                "model_display_name": model.display_name if model else "Unknown",
                "model_provider": model.provider if model else "unknown",
                "available_models": available_models,
                "model_count": len(available_models),
                "all_preferences": self.get_all_preferences(username)
            }

        except Exception as e:
            logger.error(f"Error getting user summary for {username}: {e}", exc_info=True)
            settings = get_settings(self.db)
            fallback_model = settings.get(const.SETTING_DEFAULT_LLM_MODEL)
            return {
                "username": username,
                "llm_model": fallback_model,
                "error": str(e)
            }


def get_user_preferences() -> UserPreferences:
    """
    Create a new UserPreferences instance with its own database connection.

    Each call creates a new instance to ensure thread safety. This is safe because:
    - SQLite connections aren't thread-safe by default
    - Discord bot runs slash commands in different threads
    - Creating new instances is cheap and avoids cross-thread connection usage

    Returns:
        UserPreferences instance with thread-local database connection
    """
    db = Db()
    return UserPreferences(db)
