#!/usr/bin/env python3
"""
RAG Analytics - Track knowledge source effectiveness.

Tracks which PDF sources and FAQs are most frequently cited by the AI Assistant
to help optimize the knowledge base.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from db import Db


logger = logging.getLogger(__name__)


class RAGAnalytics:
    """Track and analyze RAG source usage"""

    def __init__(self, db: Db | None = None):
        """
        Initialize RAG analytics.

        Args:
            db: Database instance (creates new if None)
        """
        if db is None:
            db = Db()
        self.db = db
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create analytics tables if they don't exist"""
        schema = """
        CREATE TABLE IF NOT EXISTS rag_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            guild_id INTEGER,
            username TEXT NOT NULL,
            query_type TEXT NOT NULL,  -- 'ask' or 'explain_topic'
            query_text TEXT NOT NULL,
            n_results INTEGER,
            model TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rag_sources_used (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            doc_type TEXT NOT NULL,  -- 'pdf', 'faq', 'conceptual', etc.
            page_number INTEGER,
            section TEXT,
            distance REAL,  -- Embedding distance (lower = more relevant)
            rank INTEGER,  -- 1 = top result, 2 = second, etc.
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (query_id) REFERENCES rag_queries(id)
        );

        CREATE TABLE IF NOT EXISTS rag_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            guild_id INTEGER,
            username TEXT NOT NULL,
            query_text TEXT NOT NULL,
            helpful BOOLEAN NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_rag_queries_guild ON rag_queries(guild_id);
        CREATE INDEX IF NOT EXISTS idx_rag_queries_timestamp ON rag_queries(timestamp);
        CREATE INDEX IF NOT EXISTS idx_rag_sources_query ON rag_sources_used(query_id);
        CREATE INDEX IF NOT EXISTS idx_rag_sources_file ON rag_sources_used(source_file);
        CREATE INDEX IF NOT EXISTS idx_rag_sources_type ON rag_sources_used(doc_type);
        CREATE INDEX IF NOT EXISTS idx_rag_feedback_guild ON rag_feedback(guild_id);
        CREATE INDEX IF NOT EXISTS idx_rag_feedback_timestamp ON rag_feedback(timestamp);
        """

        conn = self.db.connection
        conn.executescript(schema)
        conn.commit()

    def log_query(
        self,
        username: str,
        query_type: str,
        query_text: str,
        sources: list[dict[str, Any]],
        guild_id: int | None = None,
        n_results: int = 3,
        model: str = "claude-sonnet",
    ) -> int:
        """
        Log a RAG query and its sources.

        Args:
            username: User who made the query
            query_type: 'ask' or 'explain_topic'
            query_text: The actual query text
            sources: List of source dicts from retriever
            guild_id: Optional guild ID
            n_results: Number of results requested
            model: LLM model used

        Returns:
            int: Query ID
        """
        conn = self.db.connection
        timestamp = datetime.now().isoformat()

        # Insert query
        cursor = conn.execute(
            """
            INSERT INTO rag_queries (timestamp, guild_id, username, query_type, query_text, n_results, model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, guild_id, username, query_type, query_text, n_results, model),
        )
        query_id: int = cursor.lastrowid  # type: ignore[assignment]

        # Insert sources
        for rank, source in enumerate(sources, start=1):
            conn.execute(
                """
                INSERT INTO rag_sources_used (query_id, source_file, doc_type, page_number, section, distance, rank)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    source.get("source_file", "unknown"),
                    source.get("doc_type", "unknown"),
                    source.get("page_number", 0),
                    source.get("section", ""),
                    source.get("distance", 0.0),
                    rank,
                ),
            )

        conn.commit()
        logger.info(f"Logged RAG query {query_id} with {len(sources)} sources")
        return query_id

    def log_feedback(
        self,
        username: str,
        query_text: str,
        helpful: bool,
        guild_id: int | None = None,
    ) -> int:
        """
        Log user feedback on AI Assistant responses.

        Args:
            username: User who provided feedback
            query_text: The original query
            helpful: True if helpful, False if not helpful
            guild_id: Optional guild ID

        Returns:
            int: Feedback ID
        """
        conn = self.db.connection
        timestamp = datetime.now().isoformat()

        cursor = conn.execute(
            """
            INSERT INTO rag_feedback (timestamp, guild_id, username, query_text, helpful)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, guild_id, username, query_text, helpful),
        )
        feedback_id: int = cursor.lastrowid  # type: ignore[assignment]
        conn.commit()

        feedback_type = "positive" if helpful else "negative"
        logger.info(f"Logged {feedback_type} feedback from {username}: {feedback_id}")
        return feedback_id

    def get_source_stats(
        self, days: int = 30, guild_id: int | None = None, doc_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get statistics on which sources are most used.

        Args:
            days: Look back period in days
            guild_id: Filter by guild ID
            doc_type: Filter by document type ('pdf', 'faq', etc.)

        Returns:
            List of dicts with source usage stats
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
        SELECT
            s.source_file,
            s.doc_type,
            COUNT(*) as times_cited,
            AVG(s.distance) as avg_distance,
            AVG(s.rank) as avg_rank,
            MIN(s.rank) as best_rank,
            COUNT(DISTINCT q.username) as unique_users
        FROM rag_sources_used s
        JOIN rag_queries q ON s.query_id = q.id
        WHERE q.timestamp >= ?
        """

        params: list[Any] = [since]

        if guild_id is not None:
            query += " AND q.guild_id = ?"
            params.append(guild_id)

        if doc_type:
            query += " AND s.doc_type = ?"
            params.append(doc_type)

        query += """
        GROUP BY s.source_file, s.doc_type
        ORDER BY times_cited DESC
        """

        conn = self.db.connection
        cursor = conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append(
                {
                    "source_file": row[0],
                    "doc_type": row[1],
                    "times_cited": row[2],
                    "avg_distance": round(row[3], 4),
                    "avg_rank": round(row[4], 2),
                    "best_rank": row[5],
                    "unique_users": row[6],
                }
            )

        return results

    def get_query_stats(self, days: int = 30, guild_id: int | None = None) -> dict[str, Any]:
        """
        Get overall query statistics.

        Args:
            days: Look back period
            guild_id: Filter by guild

        Returns:
            Dict with query statistics
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
        SELECT
            COUNT(*) as total_queries,
            COUNT(DISTINCT username) as unique_users,
            COUNT(DISTINCT CASE WHEN query_type = 'ask' THEN id END) as ask_queries,
            COUNT(DISTINCT CASE WHEN query_type = 'explain_topic' THEN id END) as explain_queries,
            AVG(n_results) as avg_results_requested
        FROM rag_queries
        WHERE timestamp >= ?
        """

        params: list[Any] = [since]
        if guild_id is not None:
            query += " AND guild_id = ?"
            params.append(guild_id)

        conn = self.db.connection
        cursor = conn.execute(query, params)
        row = cursor.fetchone()

        return {
            "total_queries": row[0],
            "unique_users": row[1],
            "ask_queries": row[2],
            "explain_queries": row[3],
            "avg_results_requested": round(row[4], 1) if row[4] else 0,
        }

    def get_popular_topics(
        self, days: int = 30, guild_id: int | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get most frequently queried topics based on section names.

        Args:
            days: Look back period
            guild_id: Filter by guild
            limit: Max results to return

        Returns:
            List of popular topics
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
        SELECT
            s.section,
            COUNT(*) as times_cited,
            COUNT(DISTINCT q.username) as unique_users
        FROM rag_sources_used s
        JOIN rag_queries q ON s.query_id = q.id
        WHERE q.timestamp >= ?
          AND s.section != ''
        """

        params: list[Any] = [since]
        if guild_id is not None:
            query += " AND q.guild_id = ?"
            params.append(guild_id)

        query += """
        GROUP BY s.section
        ORDER BY times_cited DESC
        LIMIT ?
        """
        params.append(limit)

        conn = self.db.connection
        cursor = conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            results.append({"section": row[0], "times_cited": row[1], "unique_users": row[2]})

        return results

    def get_faq_effectiveness(self, days: int = 30, guild_id: int | None = None) -> dict[str, Any]:
        """
        Compare FAQ vs PDF usage.

        Args:
            days: Look back period
            guild_id: Filter by guild

        Returns:
            Dict with FAQ vs PDF statistics
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
        SELECT
            s.doc_type,
            COUNT(*) as times_cited,
            AVG(s.distance) as avg_distance,
            AVG(s.rank) as avg_rank
        FROM rag_sources_used s
        JOIN rag_queries q ON s.query_id = q.id
        WHERE q.timestamp >= ?
        """

        params: list[Any] = [since]
        if guild_id is not None:
            query += " AND q.guild_id = ?"
            params.append(guild_id)

        query += """
        GROUP BY s.doc_type
        ORDER BY times_cited DESC
        """

        conn = self.db.connection
        cursor = conn.execute(query, params)

        results = {}
        for row in cursor.fetchall():
            results[row[0]] = {
                "times_cited": row[1],
                "avg_distance": round(row[2], 4),
                "avg_rank": round(row[3], 2),
            }

        return results
