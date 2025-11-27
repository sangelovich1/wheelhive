"""
System Settings

Manages system-wide configuration settings with database persistence.
Provides key-value storage with type conversion and caching.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
from typing import Any, Optional

from brokers.basetableprocessor import BaseTableProcessor
from db import Db


logger = logging.getLogger(__name__)


class SystemSettings(BaseTableProcessor):
    """
    System-wide configuration settings with database persistence.

    Inherits from BaseTableProcessor for consistency but overrides methods
    to provide key-value semantics and type conversion.

    Uses singleton pattern to ensure single instance with shared cache.
    """

    _instance: Optional["SystemSettings"] = None
    _initialized: bool = False

    def __new__(cls, db: Db | None = None):
        """Singleton pattern - only create one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db: Db | None = None):
        """Initialize only once, even if called multiple times."""
        if self._initialized:
            return

        if db is None:
            db = Db(in_memory=False)

        # Initialize parent with tablename (this calls create_table())
        super().__init__(db, "system_settings")

        self._cache: dict[str, Any] = {}  # In-memory cache for performance
        self._initialized = True
        logger.info("SystemSettings singleton initialized")

    def create_table(self) -> None:
        """Create system_settings table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL,
            category TEXT,
            description TEXT,
            default_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
        """
        self.db.create_table(query)

    @classmethod
    def headers(cls) -> tuple:
        """Return headers for DataFrame/tabulate display."""
        return ("Key", "Value", "Type", "Category", "Description", "Updated At", "Updated By")

    # Override query() since system_settings doesn't have username filtering
    def query(self, username: str | None = None, fields: list | None = None,
              condition: str | None = None) -> list[tuple]:
        """
        Query settings.

        Args:
            username: Ignored (settings are system-wide, not user-specific)
            fields: List of field names to select, or None for default columns
            condition: SQL WHERE condition string

        Returns:
            List of tuples matching query
        """
        if fields is None:
            fields_str = "key, value, value_type, category, description, updated_at, updated_by"
        else:
            fields_str = ", ".join(fields)

        select = f"SELECT {fields_str} FROM {self.tablename}"
        logger.debug(f"query select: {select}, condition: {condition}")
        return self.db.query(select=select, condition=condition, orderby="category, key")

    # Override as_df() since system_settings has no Date column
    def as_df(self, user: str | None = None, filter: str | None = None):
        """
        Return settings as DataFrame.

        Args:
            user: Ignored (settings are system-wide)
            filter: Optional SQL WHERE condition

        Returns:
            DataFrame with all settings matching filter
        """
        import pandas as pd
        results = self.query(condition=filter)
        if not results:
            return pd.DataFrame(columns=self.headers())
        return pd.DataFrame(results, columns=self.headers())

    # Override insert() - system_settings uses set() instead
    def insert(self, nt) -> None:  # type: ignore[override]
        """Not used - use set() method for key-value semantics."""
        raise NotImplementedError("Use set() method for SystemSettings")

    # Key-value specific methods
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting value with type conversion and caching.

        Args:
            key: Setting key (e.g., 'llm.ollama_base_url')
            default: Default value if key not found

        Returns:
            Setting value converted to appropriate Python type (int, bool, float, dict, str)
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Query database
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT value, value_type FROM system_settings WHERE key = ?
        """, (key,))
        row = cursor.fetchone()

        if not row:
            return default

        # Convert and cache
        value, value_type = row
        converted = self._convert_value(value, value_type)
        self._cache[key] = converted
        return converted

    def set(self, key: str, value: Any, username: str = "system",
            category: str | None = None, description: str | None = None) -> None:
        """
        Set setting value with automatic type detection.

        Args:
            key: Setting key (e.g., 'llm.ollama_base_url')
            value: Setting value (will be type-detected and serialized)
            username: User making the change (default: 'system')
            category: Optional category (e.g., 'llm', 'features', 'market')
            description: Optional human-readable description
        """
        value_type = self._detect_type(value)
        str_value = self._serialize_value(value, value_type)

        cursor = self.db.connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO system_settings
            (key, value, value_type, category, description, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """, (key, str_value, value_type, category, description, username))
        self.db.connection.commit()

        # Invalidate cache
        self._cache.pop(key, None)
        logger.info(f"Setting updated: {key} = {value} (by {username})")

    def delete_key(self, key: str) -> bool:
        """
        Delete a setting by key.

        Args:
            key: Setting key to delete

        Returns:
            True if deleted, False if key not found
        """
        cursor = self.db.connection.cursor()
        cursor.execute("DELETE FROM system_settings WHERE key = ?", (key,))
        self.db.connection.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            self._cache.pop(key, None)
            logger.info(f"Setting deleted: {key}")
        return deleted

    def get_by_category(self, category: str) -> dict:
        """
        Get all settings in a category as dict.

        Args:
            category: Category name (e.g., 'llm', 'features')

        Returns:
            Dict mapping keys to values (with type conversion)
        """
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT key, value, value_type FROM system_settings
            WHERE category = ?
            ORDER BY key
        """, (category,))

        return {
            row[0]: self._convert_value(row[1], row[2])
            for row in cursor.fetchall()
        }

    def get_all_as_dict(self) -> dict:
        """
        Get all settings as a flat dict (key -> value).

        Returns:
            Dict mapping all keys to their values (with type conversion)
        """
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT key, value, value_type FROM system_settings
        """)

        return {
            row[0]: self._convert_value(row[1], row[2])
            for row in cursor.fetchall()
        }

    def clear_cache(self) -> None:
        """Clear the in-memory cache (useful after bulk updates)."""
        self._cache.clear()
        logger.info("SystemSettings cache cleared")

    def export_to_json(self, filepath: str) -> None:
        """
        Export all settings to JSON file.

        Args:
            filepath: Path to output JSON file
        """
        cursor = self.db.connection.cursor()
        cursor.execute("""
            SELECT key, value, value_type, category, description, default_value
            FROM system_settings
            ORDER BY category, key
        """)

        settings = []
        for row in cursor.fetchall():
            settings.append({
                "key": row[0],
                "value": row[1],
                "value_type": row[2],
                "category": row[3],
                "description": row[4],
                "default_value": row[5]
            })

        with open(filepath, "w") as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Exported {len(settings)} settings to {filepath}")

    def import_from_json(self, filepath: str, username: str = "system") -> int:
        """
        Import settings from JSON file.

        Args:
            filepath: Path to input JSON file
            username: User performing the import

        Returns:
            Number of settings imported
        """
        with open(filepath) as f:
            settings = json.load(f)

        count = 0
        for setting in settings:
            self.set(
                key=setting["key"],
                value=self._convert_value(setting["value"], setting["value_type"]),
                username=username,
                category=setting.get("category"),
                description=setting.get("description")
            )
            count += 1

        logger.info(f"Imported {count} settings from {filepath}")
        return count

    # Type conversion helpers
    def _convert_value(self, value: str, value_type: str) -> Any:
        """Convert string value from database to appropriate Python type."""
        if value_type == "int":
            return int(value)
        if value_type == "float":
            return float(value)
        if value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        if value_type == "json":
            return json.loads(value)
        return value  # string

    def _detect_type(self, value: Any) -> str:
        """Detect Python type for database storage."""
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, (dict, list)):
            return "json"
        return "string"

    def _serialize_value(self, value: Any, value_type: str) -> str:
        """Serialize value to string for database storage."""
        if value_type == "json":
            return json.dumps(value)
        return str(value)


def get_settings(db: Db | None = None) -> SystemSettings:
    """
    Get the SystemSettings singleton instance.

    Args:
        db: Optional Db instance (only used on first call)

    Returns:
        SystemSettings singleton instance
    """
    return SystemSettings(db)
