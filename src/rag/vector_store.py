"""
Vector store wrapper for RAG system.

Provides a clean interface to ChromaDB for querying training materials.

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


logger = logging.getLogger(__name__)


class TrainingMaterialsVectorStore:
    """
    Vector store for community training materials.

    Wraps ChromaDB with convenience methods for querying wheel strategy guides.
    """

    def __init__(
        self,
        db_path: Path = Path("training_materials/vector_db"),
        collection_name: str = "training_materials",
        guild_id: int | None = None,
    ):
        """
        Initialize vector store connection.

        Args:
            db_path: Path to ChromaDB storage directory
            collection_name: Name of the collection to use
            guild_id: Optional guild ID for guild-specific content
        """
        self.db_path = db_path
        self.collection_name = collection_name
        self.guild_id = guild_id
        self._client = None
        self._collection = None

        logger.info(
            f"Initialized TrainingMaterialsVectorStore (db_path={db_path}, guild_id={guild_id})"
        )

    def _get_guild_db_path(self) -> Path | None:
        """Get guild-specific database path if it exists."""
        if self.guild_id is None:
            return None

        guild_path = Path(f"training_materials/{self.guild_id}/vector_db")
        if guild_path.exists():
            return guild_path
        return None

    def _get_active_db_path(self) -> Path:
        """Get the active database path (guild-specific or default)."""
        # Check for guild-specific content first
        guild_path = self._get_guild_db_path()
        if guild_path:
            logger.debug(f"Using guild-specific content: {guild_path}")
            return guild_path

        # Fall back to default
        default_path = Path("training_materials/default/vector_db")
        if not default_path.exists():
            # Legacy fallback to old path
            default_path = self.db_path

        logger.debug(f"Using default content: {default_path}")
        return default_path

    @property
    def client(self) -> chromadb.ClientAPI:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            active_path = self._get_active_db_path()
            self._client = chromadb.PersistentClient(  # type: ignore[assignment]
                path=str(active_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )
            logger.debug(f"Connected to ChromaDB at {active_path}")
        return self._client  # type: ignore[return-value]

    @property
    def collection(self) -> chromadb.Collection:
        """Lazy-load collection."""
        if self._collection is None:
            try:
                self._collection = self.client.get_collection(  # type: ignore[assignment]
                    name=self.collection_name
                )
                logger.debug(f"Loaded collection: {self.collection_name}")
            except Exception as e:
                logger.error(
                    f"Failed to load collection '{self.collection_name}': {e}. "
                    f"Run: python scripts/rag/create_vector_store.py"
                )
                raise RuntimeError(
                    "Vector store not initialized. "
                    "Run: python scripts/rag/create_vector_store.py"
                ) from e
        return self._collection  # type: ignore[return-value]

    def reset_cache(self) -> None:
        """Reset cached client and collection to force reload on next access."""
        self._client = None
        self._collection = None
        logger.debug("Vector store cache cleared")

    def _query_single_db(
        self,
        db_path: Path,
        query_text: str,
        n_results: int,
        doc_type: str | None = None,
        source_label: str = "unknown",
    ) -> list[dict[str, Any]]:
        """
        Query a single vector database.

        Args:
            db_path: Path to the vector database
            query_text: User's question or search query
            n_results: Number of results to return
            doc_type: Optional filter by document type
            source_label: Label for source tracking ('guild' or 'default')

        Returns:
            List of chunk dicts with metadata
        """
        if not db_path.exists():
            logger.debug(f"Vector DB does not exist: {db_path}")
            return []

        try:
            # Connect to specific database
            client = chromadb.PersistentClient(
                path=str(db_path), settings=Settings(anonymized_telemetry=False, allow_reset=False)
            )

            # Get collection
            collection = client.get_collection(name=self.collection_name)

            # Build metadata filter
            where_filter = {}
            if doc_type:
                where_filter["doc_type"] = doc_type

            # Query ChromaDB
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_filter if where_filter else None,  # type: ignore[arg-type]
            )

            # Format results
            chunks = []
            if results and results.get("documents") and results["documents"][0]:  # type: ignore[index]
                for i in range(len(results["documents"][0])):  # type: ignore[index]
                    chunks.append(
                        {
                            "text": results["documents"][0][i],  # type: ignore[index]
                            "source_file": results["metadatas"][0][i]["source_file"],  # type: ignore[index]
                            "page_number": results["metadatas"][0][i]["page_number"],  # type: ignore[index]
                            "doc_type": results["metadatas"][0][i]["doc_type"],  # type: ignore[index]
                            "section": results["metadatas"][0][i]["section"],  # type: ignore[index]
                            "tokens": results["metadatas"][0][i]["tokens"],  # type: ignore[index]
                            "distance": results["distances"][0][i],  # type: ignore[index]
                            "vector_db_source": source_label,  # Tag source for analytics
                        }
                    )

            logger.debug(f"Retrieved {len(chunks)} chunks from {source_label} DB: {db_path}")
            return chunks

        except Exception as e:
            logger.warning(f"Failed to query {source_label} DB at {db_path}: {e}")
            return []

    def query(
        self, query_text: str, n_results: int = 3, doc_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Query training materials with cascading fallback.

        Searches guild-specific content first, then falls back to default
        content if insufficient results are found.

        Args:
            query_text: User's question or search query
            n_results: Number of results to return (default: 3)
            doc_type: Optional filter by document type
                     ('conceptual', 'execution_guide', 'reference')

        Returns:
            List of dicts with keys:
            - text: Chunk text
            - source_file: Source PDF filename
            - page_number: Page number in source
            - doc_type: Document type
            - section: Section header
            - distance: Embedding distance (lower = more similar)
            - vector_db_source: 'guild' or 'default' (which DB provided this)
        """
        results = []

        # Step 1: Try guild-specific database first
        if self.guild_id:
            guild_path = Path(f"training_materials/{self.guild_id}/vector_db")
            guild_results = self._query_single_db(
                db_path=guild_path,
                query_text=query_text,
                n_results=n_results,
                doc_type=doc_type,
                source_label="guild",
            )
            results.extend(guild_results)
            logger.info(f"Retrieved {len(guild_results)} chunks from guild {self.guild_id}")

        # Step 2: If we need more results, query default database
        if len(results) < n_results:
            needed = n_results - len(results)
            default_path = Path("training_materials/default/vector_db")

            # Try legacy path if default doesn't exist
            if not default_path.exists() and self.db_path.exists():
                default_path = self.db_path

            default_results = self._query_single_db(
                db_path=default_path,
                query_text=query_text,
                n_results=needed,
                doc_type=doc_type,
                source_label="default",
            )
            results.extend(default_results)
            logger.info(f"Retrieved {len(default_results)} chunks from default DB")

        # Limit to requested number
        final_results = results[:n_results]

        # Log summary
        guild_count = sum(1 for r in final_results if r.get("vector_db_source") == "guild")
        default_count = sum(1 for r in final_results if r.get("vector_db_source") == "default")

        logger.info(
            f"Retrieved {len(final_results)} total chunks for query '{query_text[:50]}...': "
            f"{guild_count} guild, {default_count} default"
        )

        return final_results

    def get_stats(self) -> dict[str, Any]:
        """
        Get vector store statistics.

        Returns:
            Dict with keys:
            - total_chunks: Total number of chunks
            - collection_name: Collection name
            - embedding_model: Embedding model used
        """
        count = self.collection.count()
        metadata = self.collection.metadata or {}

        return {
            "total_chunks": count,
            "collection_name": self.collection_name,
            "embedding_model": metadata.get("embedding_model", "unknown"),
            "description": metadata.get("description", ""),
        }

    def format_chunk_for_llm(self, chunk: dict[str, Any]) -> str:
        """
        Format a retrieved chunk for inclusion in LLM context.

        Args:
            chunk: Chunk dict from query()

        Returns:
            Formatted string with source citation
        """
        return f"""[Source: {chunk['source_file']}, Page {chunk['page_number']}]
Section: {chunk['section']}

{chunk['text']}"""

    def format_chunks_for_llm(self, chunks: list[dict[str, Any]]) -> str:
        """
        Format multiple chunks for LLM context.

        Args:
            chunks: List of chunk dicts from query()

        Returns:
            Formatted string with all chunks
        """
        formatted = []
        for i, chunk in enumerate(chunks, 1):
            formatted.append(f"--- Training Material {i} ---")
            formatted.append(self.format_chunk_for_llm(chunk))

        return "\n\n".join(formatted)
