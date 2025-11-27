"""
Usage metrics tracking and analysis.

Provides centralized metrics tracking for:
- Discord command usage
- LLM API calls and costs
- MCP tool performance
- User activity patterns

Metrics are stored in SQLite and queried via CLI only (not exposed to Discord).

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
from datetime import datetime
from typing import Any

from db import Db


logger = logging.getLogger(__name__)


class MetricsTracker:
    """Track and query bot usage metrics."""

    # LLM pricing per 1K tokens (input, output)
    PRICING = {
        "claude-sonnet-4-5-20250929": (0.003, 0.015),
        "claude-haiku-4-5-20251001": (0.001, 0.005),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-3.5-turbo": (0.0015, 0.002),
        "ollama": (0.0, 0.0)  # Local models
    }

    def __init__(self, db: Db):
        """
        Initialize metrics tracker.

        Args:
            db: Database instance
        """
        self.db = db
        self._ensure_tables_exist()

    def _ensure_tables_exist(self) -> None:
        """Create metrics table if it doesn't exist."""

        # Single unified metrics table
        self.db.create_table("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                username TEXT NOT NULL,
                guild_id INTEGER,

                -- Universal fields
                name TEXT NOT NULL,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                response_time_ms INTEGER,

                -- Numeric metrics (for aggregation)
                tokens INTEGER,
                estimated_cost_usd REAL,

                -- Everything else
                metadata TEXT,

                -- Relationships
                parent_id INTEGER,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for fast queries
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_type_time ON metrics(event_type, timestamp DESC)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_user ON metrics(username)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_cost ON metrics(estimated_cost_usd) "
            "WHERE estimated_cost_usd > 0"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_metrics_parent ON metrics(parent_id) "
            "WHERE parent_id IS NOT NULL"
        )

        logger.info("Metrics table initialized")

    def track_command(
        self,
        command_name: str,
        username: str,
        guild_id: int | None = None,
        guild_name: str | None = None,
        parameters: dict | None = None,
        success: bool = True,
        error_message: str | None = None,
        response_time_ms: int | None = None
    ) -> int | None:
        """
        Track a Discord command execution.

        Args:
            command_name: Name of the command (e.g., 'analyze', 'scan_puts')
            username: Discord username
            guild_id: Discord guild ID
            guild_name: Discord guild name
            parameters: Command parameters as dict
            success: Whether command succeeded
            error_message: Error message if failed
            response_time_ms: Command execution time in milliseconds

        Returns:
            Event ID for linking related metrics (LLM, MCP calls)
        """
        timestamp = datetime.now().isoformat()

        metadata = {
            "guild_name": guild_name,
            "params": parameters or {}
        }

        query = """
            INSERT INTO metrics
            (timestamp, event_type, username, guild_id, name, success,
             error_message, response_time_ms, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = self.db.execute(query, (
            timestamp,
            "command",
            username,
            guild_id,
            command_name,
            success,
            error_message,
            response_time_ms,
            json.dumps(metadata)
        ))

        event_id = cursor.lastrowid
        logger.debug(f"Tracked command: {command_name} by {username} (event_id={event_id})")
        return event_id

    def track_llm_usage(
        self,
        username: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        finish_reason: str | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4096,
        tool_calls_count: int = 0,
        iterations: int = 1,
        parent_id: int | None = None
    ) -> int | None:
        """
        Track LLM API usage and calculate cost.

        Args:
            username: Discord username (or 'system' for background tasks)
            model: Model name (e.g., 'claude-sonnet-4-5-20250929')
            provider: Provider name (e.g., 'anthropic', 'openai')
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            finish_reason: Why completion stopped ('stop', 'tool_calls', 'length')
            temperature: LLM temperature setting
            max_tokens: Max tokens limit
            tool_calls_count: Number of MCP tools called
            iterations: Number of multi-step iterations
            parent_id: Parent event ID (links to command)

        Returns:
            LLM usage ID for linking MCP calls
        """
        timestamp = datetime.now().isoformat()
        total_tokens = prompt_tokens + completion_tokens

        # Calculate cost
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        metadata = {
            "provider": provider,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "finish_reason": finish_reason,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tool_calls_count": tool_calls_count,
            "iterations": iterations
        }

        query = """
            INSERT INTO metrics
            (timestamp, event_type, username, name, tokens,
             estimated_cost_usd, metadata, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = self.db.execute(query, (
            timestamp,
            "llm",
            username,
            model,  # name field = model
            total_tokens,
            cost,
            json.dumps(metadata),
            parent_id
        ))

        llm_id = cursor.lastrowid
        logger.debug(f"Tracked LLM usage: {model} for {username}, cost=${cost:.4f} (llm_id={llm_id})")
        return llm_id

    def track_mcp_call(
        self,
        tool_name: str,
        username: str,
        input_params: dict | None = None,
        success: bool = True,
        error_message: str | None = None,
        response_time_ms: int | None = None,
        parent_id: int | None = None,
        llm_usage_id: int | None = None
    ) -> int | None:
        """
        Track MCP tool call.

        Args:
            tool_name: Name of MCP tool (e.g., 'get_current_positions')
            username: Discord username
            input_params: Tool input parameters
            success: Whether call succeeded
            error_message: Error message if failed
            response_time_ms: Tool execution time in milliseconds
            parent_id: Parent event ID (links to command or LLM call)
            llm_usage_id: LLM usage ID if called during LLM analysis

        Returns:
            MCP call ID
        """
        timestamp = datetime.now().isoformat()

        metadata = {
            "input_params": input_params or {},
            "llm_usage_id": llm_usage_id
        }

        query = """
            INSERT INTO metrics
            (timestamp, event_type, username, name, success,
             error_message, response_time_ms, metadata, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = self.db.execute(query, (
            timestamp,
            "mcp",
            username,
            tool_name,  # name field = tool_name
            success,
            error_message,
            response_time_ms,
            json.dumps(metadata),
            parent_id
        ))

        call_id = cursor.lastrowid
        logger.debug(f"Tracked MCP call: {tool_name} by {username} (call_id={call_id})")
        return call_id

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate LLM API cost based on token usage.

        Args:
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Get pricing for model (default to Claude Sonnet if unknown)
        input_cost, output_cost = self.PRICING.get(model, (0.003, 0.015))

        # Cost per 1K tokens
        cost = (prompt_tokens * input_cost + completion_tokens * output_cost) / 1000.0
        return round(cost, 6)

    # === QUERY METHODS (for CLI) ===

    def get_command_stats(self, days: int = 7) -> list[tuple[str, int, int]]:
        """
        Get command usage statistics.

        Args:
            days: Number of days to look back

        Returns:
            List of (command_name, total_uses, unique_users)
        """
        query = """
            SELECT
                name,
                COUNT(*) as total_uses,
                COUNT(DISTINCT username) as unique_users
            FROM metrics
            WHERE event_type = 'command'
                AND timestamp >= datetime('now', ?)
            GROUP BY name
            ORDER BY total_uses DESC
        """

        days_param = f"-{days} days"
        results = self.db.query_parameterized(query, (days_param,))
        return results

    def get_llm_cost_summary(self, days: int = 7) -> dict[str, Any]:
        """
        Get LLM cost summary.

        Args:
            days: Number of days to look back

        Returns:
            {
                'total_cost': float,
                'total_tokens': int,
                'by_model': [(model, cost, tokens), ...],
                'by_user': [(username, cost, tokens), ...]
            }
        """
        days_param = f"-{days} days"

        # Total cost
        total_query = """
            SELECT
                COALESCE(SUM(estimated_cost_usd), 0) as total_cost,
                COALESCE(SUM(tokens), 0) as total_tokens
            FROM metrics
            WHERE event_type = 'llm'
                AND timestamp >= datetime('now', ?)
        """
        total = self.db.query_parameterized(total_query, (days_param,))[0]

        # By model
        model_query = """
            SELECT
                name as model,
                SUM(estimated_cost_usd) as cost,
                SUM(tokens) as tokens
            FROM metrics
            WHERE event_type = 'llm'
                AND timestamp >= datetime('now', ?)
            GROUP BY name
            ORDER BY cost DESC
        """
        by_model = self.db.query_parameterized(model_query, (days_param,))

        # By user
        user_query = """
            SELECT
                username,
                SUM(estimated_cost_usd) as cost,
                SUM(tokens) as tokens
            FROM metrics
            WHERE event_type = 'llm'
                AND timestamp >= datetime('now', ?)
            GROUP BY username
            ORDER BY cost DESC
        """
        by_user = self.db.query_parameterized(user_query, (days_param,))

        return {
            "total_cost": total[0],
            "total_tokens": total[1],
            "by_model": by_model,
            "by_user": by_user
        }

    def get_mcp_tool_stats(self, days: int = 7) -> list[tuple[str, int, int, float]]:
        """
        Get MCP tool usage statistics.

        Args:
            days: Number of days to look back

        Returns:
            List of (tool_name, total_calls, failures, avg_response_time_ms)
        """
        query = """
            SELECT
                name as tool_name,
                COUNT(*) as total_calls,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                AVG(response_time_ms) as avg_response_time
            FROM metrics
            WHERE event_type = 'mcp'
                AND timestamp >= datetime('now', ?)
            GROUP BY name
            ORDER BY total_calls DESC
        """

        days_param = f"-{days} days"
        results = self.db.query_parameterized(query, (days_param,))
        return results

    def get_user_activity(self, days: int = 7) -> list[tuple[str, int, int]]:
        """
        Get user activity statistics.

        Args:
            days: Number of days to look back

        Returns:
            List of (username, total_commands, total_llm_calls)
        """
        query = """
            SELECT
                username,
                SUM(CASE WHEN event_type = 'command' THEN 1 ELSE 0 END) as commands,
                SUM(CASE WHEN event_type = 'llm' THEN 1 ELSE 0 END) as llm_calls
            FROM metrics
            WHERE timestamp >= datetime('now', ?)
            GROUP BY username
            ORDER BY commands DESC
        """

        days_param = f"-{days} days"
        results = self.db.query_parameterized(query, (days_param,))
        return results

    def get_daily_activity(self, days: int = 30) -> list[tuple[str, int, int, float]]:
        """
        Get daily activity trend.

        Args:
            days: Number of days to look back

        Returns:
            List of (date, commands, llm_calls, cost)
        """
        query = """
            SELECT
                DATE(timestamp) as date,
                SUM(CASE WHEN event_type = 'command' THEN 1 ELSE 0 END) as commands,
                SUM(CASE WHEN event_type = 'llm' THEN 1 ELSE 0 END) as llm_calls,
                COALESCE(SUM(estimated_cost_usd), 0) as cost
            FROM metrics
            WHERE timestamp >= datetime('now', ?)
            GROUP BY date
            ORDER BY date DESC
        """

        days_param = f"-{days} days"
        results = self.db.query_parameterized(query, (days_param,))
        return results

    def get_error_summary(self, days: int = 7) -> list[tuple[str, str, int]]:
        """
        Get error summary.

        Args:
            days: Number of days to look back

        Returns:
            List of (event_type, name, error_count)
        """
        query = """
            SELECT
                event_type,
                name,
                COUNT(*) as error_count
            FROM metrics
            WHERE success = 0
                AND timestamp >= datetime('now', ?)
            GROUP BY event_type, name
            ORDER BY error_count DESC
        """

        days_param = f"-{days} days"
        results = self.db.query_parameterized(query, (days_param,))
        return results
