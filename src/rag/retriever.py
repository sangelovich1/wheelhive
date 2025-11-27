"""
RAG retriever for AI wheel strategy tutor.

Combines training materials retrieval with conversation context.

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import logging
from typing import Any

from rag.vector_store import TrainingMaterialsVectorStore


logger = logging.getLogger(__name__)


class TrainingMaterialsRetriever:
    """
    Retrieves relevant training materials for AI tutor responses.

    Handles query expansion, filtering, and context assembly for LLM prompts.
    """

    def __init__(
        self,
        vector_store: TrainingMaterialsVectorStore | None = None,
        guild_id: int | None = None
    ):
        """
        Initialize retriever.

        Args:
            vector_store: Optional vector store instance (creates default if None)
            guild_id: Optional guild ID for guild-specific content
        """
        self.vector_store = vector_store or TrainingMaterialsVectorStore(guild_id=guild_id)
        self.guild_id = guild_id
        logger.info(f"Initialized TrainingMaterialsRetriever (guild_id={guild_id})")

    def retrieve_for_question(
        self,
        question: str,
        n_results: int = 3,
        doc_type: str | None = None
    ) -> dict[str, Any]:
        """
        Retrieve training materials relevant to a user question.

        Args:
            question: User's question
            n_results: Number of chunks to retrieve
            doc_type: Optional document type filter

        Returns:
            Dict with keys:
            - chunks: List of relevant chunks
            - context: Formatted context string for LLM
            - sources: List of unique source files
        """
        # Query vector store
        chunks = self.vector_store.query(
            query_text=question,
            n_results=n_results,
            doc_type=doc_type
        )

        # Debug: Log what was actually retrieved
        for i, chunk in enumerate(chunks, 1):
            logger.debug(
                f"Chunk {i}: source={chunk.get('source_file')}, "
                f"doc_type={chunk.get('doc_type')}, "
                f"distance={chunk.get('distance', 0):.3f}, "
                f"text={chunk.get('text', '')[:80]}..."
            )

        # Format for LLM
        context = self._build_context(chunks)

        # Extract unique sources
        sources = list(set(chunk["source_file"] for chunk in chunks))

        logger.info(
            f"Retrieved {len(chunks)} chunks from {len(sources)} sources "
            f"for question: '{question[:50]}...'"
        )

        return {
            "chunks": chunks,
            "context": context,
            "sources": sources
        }

    def retrieve_for_topic(
        self,
        topic: str,
        n_results: int = 5
    ) -> dict[str, Any]:
        """
        Retrieve training materials for a specific topic.

        Use this for educational queries like "explain assignment" vs
        specific questions like "what should I do if assigned?"

        Args:
            topic: Topic to retrieve (e.g., "assignment", "strike selection")
            n_results: Number of chunks to retrieve

        Returns:
            Dict with chunks, context, and sources
        """
        # Topic queries benefit from more results for comprehensive coverage
        return self.retrieve_for_question(
            question=f"Explain {topic} in the wheel strategy",
            n_results=n_results
        )

    def retrieve_conceptual(self, question: str, n_results: int = 3) -> dict[str, Any]:
        """
        Retrieve conceptual/overview materials.

        Args:
            question: User's question
            n_results: Number of chunks

        Returns:
            Dict with chunks, context, and sources
        """
        return self.retrieve_for_question(
            question=question,
            n_results=n_results,
            doc_type="conceptual"
        )

    def retrieve_execution_guide(
        self,
        question: str,
        n_results: int = 3
    ) -> dict[str, Any]:
        """
        Retrieve execution/how-to materials (CSP, CC guides).

        Args:
            question: User's question
            n_results: Number of chunks

        Returns:
            Dict with chunks, context, and sources
        """
        return self.retrieve_for_question(
            question=question,
            n_results=n_results,
            doc_type="execution_guide"
        )

    def retrieve_terminology(
        self,
        question: str,
        n_results: int = 2
    ) -> dict[str, Any]:
        """
        Retrieve terminology/reference materials.

        Args:
            question: User's question
            n_results: Number of chunks

        Returns:
            Dict with chunks, context, and sources
        """
        return self.retrieve_for_question(
            question=question,
            n_results=n_results,
            doc_type="reference"
        )

    def _build_context(self, chunks: list[dict[str, Any]]) -> str:
        """
        Build LLM context from retrieved chunks.

        Args:
            chunks: List of chunk dicts

        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant training materials found."

        parts = [
            "=== COMMUNITY TRAINING MATERIALS ===",
            "",
            "The following content is from the official wheel strategy training guides:",
            ""
        ]

        for i, chunk in enumerate(chunks, 1):
            parts.append(f"--- Training Material {i} ---")
            parts.append(f"Source: {chunk['source_file']} (Page {chunk['page_number']})")
            parts.append(f"Section: {chunk['section']}")
            parts.append("")
            parts.append(chunk["text"])
            parts.append("")

        parts.append("=== END TRAINING MATERIALS ===")

        return "\n".join(parts)

    def get_stats(self) -> dict[str, Any]:
        """
        Get retriever statistics.

        Returns:
            Dict with vector store stats
        """
        return self.vector_store.get_stats()
