"""
LLM Models Management

Database-backed LLM model registry for dynamic model configuration.
Replaces hardcoded models in constants.py with runtime management.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from dataclasses import dataclass
from typing import Any

from db import Db


logger = logging.getLogger(__name__)


@dataclass
class LLMModel:
    """Single LLM model definition"""
    model_key: str
    litellm_model: str
    display_name: str
    description: str
    cost_tier: str  # free, budget, premium
    quality: int  # 1-10 rating
    speed: str  # very-fast, fast, medium, slow
    tool_calling: bool
    provider: str  # anthropic, ollama, openai, etc.
    is_active: bool = True
    is_default: bool = False


class LLMModels:
    """Collection of LLM models with database storage"""

    def __init__(self, db: Db) -> None:
        self.db = db
        self.tablename = "llm_models"
        self.create_table()

    def create_table(self) -> None:
        """Create llm_models table if it doesn't exist"""
        query = """
        CREATE TABLE IF NOT EXISTS llm_models (
            model_key TEXT PRIMARY KEY,
            litellm_model TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            cost_tier TEXT DEFAULT 'free',
            quality INTEGER DEFAULT 5,
            speed TEXT DEFAULT 'medium',
            tool_calling INTEGER DEFAULT 0,
            provider TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.db.create_table(query)
        logger.info("LLM models table initialized")

    def add_model(self, model: LLMModel) -> None:
        """
        Add or update an LLM model

        Args:
            model: LLMModel object to insert/update
        """
        query = """
        INSERT OR REPLACE INTO llm_models
        (model_key, litellm_model, display_name, description, cost_tier,
         quality, speed, tool_calling, provider, is_active, is_default, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        self.db.execute(query, (
            model.model_key,
            model.litellm_model,
            model.display_name,
            model.description,
            model.cost_tier,
            model.quality,
            model.speed,
            1 if model.tool_calling else 0,
            model.provider,
            1 if model.is_active else 0,
            1 if model.is_default else 0
        ))
        logger.info(f"Added/updated LLM model: {model.model_key}")

    def get_model(self, model_key: str) -> LLMModel | None:
        """
        Get model by key

        Args:
            model_key: Model key (e.g., 'claude-sonnet')

        Returns:
            LLMModel object if found, None otherwise
        """
        query = """
        SELECT model_key, litellm_model, display_name, description, cost_tier,
               quality, speed, tool_calling, provider, is_active, is_default
        FROM llm_models WHERE model_key = ?
        """
        result = self.db.query_parameterized(query, (model_key,))

        if not result:
            return None

        row = result[0]
        return LLMModel(
            model_key=row[0],
            litellm_model=row[1],
            display_name=row[2],
            description=row[3],
            cost_tier=row[4],
            quality=row[5],
            speed=row[6],
            tool_calling=bool(row[7]),
            provider=row[8],
            is_active=bool(row[9]),
            is_default=bool(row[10])
        )

    def list_models(self, active_only: bool = True) -> list[LLMModel]:
        """
        List all models

        Args:
            active_only: Only include active models

        Returns:
            List of LLMModel objects
        """
        query = """
        SELECT model_key, litellm_model, display_name, description, cost_tier,
               quality, speed, tool_calling, provider, is_active, is_default
        FROM llm_models
        """
        if active_only:
            query += " WHERE is_active = 1"

        query += " ORDER BY quality DESC, model_key ASC"

        result = self.db.query_parameterized(query)

        models = []
        for row in result:
            models.append(LLMModel(
                model_key=row[0],
                litellm_model=row[1],
                display_name=row[2],
                description=row[3],
                cost_tier=row[4],
                quality=row[5],
                speed=row[6],
                tool_calling=bool(row[7]),
                provider=row[8],
                is_active=bool(row[9]),
                is_default=bool(row[10])
            ))

        return models

    def get_default_model(self) -> LLMModel | None:
        """
        Get the default model

        Returns:
            LLMModel object for default model, or None if not set
        """
        query = """
        SELECT model_key, litellm_model, display_name, description, cost_tier,
               quality, speed, tool_calling, provider, is_active, is_default
        FROM llm_models WHERE is_default = 1 AND is_active = 1
        """
        result = self.db.query_parameterized(query)

        if not result:
            return None

        row = result[0]
        return LLMModel(
            model_key=row[0],
            litellm_model=row[1],
            display_name=row[2],
            description=row[3],
            cost_tier=row[4],
            quality=row[5],
            speed=row[6],
            tool_calling=bool(row[7]),
            provider=row[8],
            is_active=bool(row[9]),
            is_default=bool(row[10])
        )

    def set_default_model(self, model_key: str) -> bool:
        """
        Set a model as the default (unsets all others)

        Args:
            model_key: Model key to set as default

        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify model exists and is active
            model = self.get_model(model_key)
            if not model or not model.is_active:
                logger.error(f"Model {model_key} not found or inactive")
                return False

            # Unset all defaults
            self.db.execute("UPDATE llm_models SET is_default = 0")

            # Set new default
            self.db.execute(
                "UPDATE llm_models SET is_default = 1 WHERE model_key = ?",
                (model_key,)
            )

            logger.info(f"Set default model to: {model_key}")
            return True

        except Exception as e:
            logger.error(f"Error setting default model: {e}", exc_info=True)
            return False

    def delete_model(self, model_key: str) -> bool:
        """
        Soft delete a model (sets is_active = 0)

        Args:
            model_key: Model key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if it's the default model
            model = self.get_model(model_key)
            if model and model.is_default:
                logger.error(f"Cannot delete default model {model_key}. Set a new default first.")
                return False

            query = "UPDATE llm_models SET is_active = 0 WHERE model_key = ?"
            self.db.execute(query, (model_key,))
            logger.info(f"Soft deleted model: {model_key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting model: {e}", exc_info=True)
            return False

    def get_active_model_keys(self) -> list[str]:
        """
        Get all active model keys

        Returns:
            List of active model keys ordered by quality
        """
        query = """
        SELECT model_key FROM llm_models
        WHERE is_active = 1
        ORDER BY quality DESC
        """
        result = self.db.query_parameterized(query)
        return [row[0] for row in result]


def populate_default_models(db: Db) -> dict[str, Any]:
    """
    Populate database with default LLM models from original constants.py

    Args:
        db: Database instance

    Returns:
        Dictionary with stats: {'added': count, 'errors': []}
    """
    llm_models = LLMModels(db)
    stats: dict[str, Any] = {"added": 0, "errors": []}

    # Default models from original AVAILABLE_MODELS
    default_models = [
        LLMModel(
            model_key="claude-sonnet",
            litellm_model="claude-sonnet-4-5-20250929",
            display_name="Claude Sonnet 4.5",
            description="Most powerful - best for complex multi-step analysis and reasoning",
            cost_tier="premium",
            quality=9,
            speed="fast",
            tool_calling=True,
            provider="anthropic",
            is_active=True,
            is_default=False
        ),
        LLMModel(
            model_key="claude-haiku",
            litellm_model="claude-haiku-4-5-20251001",
            display_name="Claude Haiku 4.5",
            description="Fast and affordable - excellent for quick queries and high-volume tasks",
            cost_tier="budget",
            quality=7,
            speed="very-fast",
            tool_calling=True,
            provider="anthropic",
            is_active=True,
            is_default=False
        ),
        LLMModel(
            model_key="ollama-qwen-32b",
            litellm_model="ollama/qwen2.5:32b",
            display_name="Qwen 2.5 32B (Local)",
            description="FREE local model - excellent financial analysis, superior data extraction, full tool calling support",
            cost_tier="free",
            quality=8,
            speed="medium",
            tool_calling=True,
            provider="ollama",
            is_active=True,
            is_default=True  # Set as default
        )
    ]

    for model in default_models:
        try:
            llm_models.add_model(model)
            stats["added"] += 1
        except Exception as e:
            error_msg = f"Error adding {model.model_key}: {e}"
            logger.error(error_msg, exc_info=True)
            stats["errors"].append(error_msg)

    return stats
