#!/usr/bin/env python3
"""
Create ChromaDB vector store from chunked training materials.

This script loads the chunked documents, generates embeddings using
sentence-transformers, and stores them in ChromaDB for fast semantic search.

Embedding Model: all-MiniLM-L6-v2 (local, fast, good quality)
- 384 dimensions
- ~14K vocab
- Optimized for semantic similarity

Usage:
    python scripts/rag/create_vector_store.py [--chunks CHUNKS] [--db-path DB_PATH]

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import json
import sys
from pathlib import Path
from typing import Any


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import chromadb
from chromadb.config import Settings


def load_chunks(chunks_file: Path) -> list[dict[str, Any]]:
    """
    Load chunked documents from JSON.

    Args:
        chunks_file: Path to training_chunks.json

    Returns:
        List of chunk dicts
    """
    with open(chunks_file) as f:
        data = json.load(f)

    return data["chunks"]  # type: ignore[no-any-return]


def create_vector_store(
    chunks: list[dict[str, Any]], db_path: Path, collection_name: str = "training_materials"
) -> chromadb.Collection:
    """
    Create ChromaDB vector store with embeddings.

    Args:
        chunks: List of chunk dicts with text and metadata
        db_path: Path to ChromaDB storage directory
        collection_name: Name for the collection

    Returns:
        ChromaDB collection
    """
    # Create ChromaDB client (persistent)
    client = chromadb.PersistentClient(
        path=str(db_path), settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )

    # Delete existing collection if it exists (for clean rebuild)
    try:
        client.delete_collection(name=collection_name)
        print(f"   Deleted existing collection: {collection_name}")
    except:
        pass

    # Create collection with embedding function
    # sentence-transformers model: all-MiniLM-L6-v2 (default)
    # This is a local model (no API calls needed)
    collection = client.create_collection(
        name=collection_name,
        metadata={
            "description": "Community wheel strategy training materials",
            "embedding_model": "all-MiniLM-L6-v2",
        },
    )

    print(f"   Created collection: {collection_name}")

    return collection


def add_chunks_to_collection(collection: chromadb.Collection, chunks: list[dict[str, Any]]) -> None:
    """
    Add chunks to ChromaDB collection with embeddings.

    Args:
        collection: ChromaDB collection
        chunks: List of chunk dicts
    """
    # Prepare data for batch insert
    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["text"])
        metadatas.append(
            {
                "source_file": chunk["source_file"],
                "page_number": chunk["page_number"],
                "doc_type": chunk["doc_type"],
                "section": chunk["section"],
                "tokens": chunk["tokens"],
            }
        )

    # Add to collection (embeddings generated automatically)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,  # type: ignore[arg-type]
    )

    print(f"   Added {len(chunks)} chunks to collection")


def test_query(collection: chromadb.Collection, query: str, n_results: int = 3):
    """
    Test the vector store with a sample query.

    Args:
        collection: ChromaDB collection
        query: Test query string
        n_results: Number of results to return
    """
    print(f'\n🔍 Testing query: "{query}"')
    print()

    results = collection.query(query_texts=[query], n_results=n_results)

    print(f"Top {n_results} results:")
    print()

    for i, (doc, metadata, distance) in enumerate(
        zip(
            results["documents"][0],  # type: ignore[index]
            results["metadatas"][0],  # type: ignore[index]
            results["distances"][0],  # type: ignore[index]
            strict=False,
        )
    ):
        print(f"{i+1}. Source: {metadata['source_file']} (page {metadata['page_number']})")
        print(f"   Section: {metadata['section']}")
        print(f"   Type: {metadata['doc_type']}")
        print(f"   Distance: {distance:.4f}")
        print(f"   Text preview: {doc[:150]}...")
        print()


def main():
    """Create vector store from training chunks."""
    import argparse

    parser = argparse.ArgumentParser(description="Create ChromaDB vector store")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("training_materials/chunks/training_chunks.json"),
        help="Input chunks JSON file",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("training_materials/default/vector_db"),
        help="ChromaDB storage directory (default for all guilds)",
    )
    parser.add_argument("--guild-id", type=int, help="Optional guild ID for guild-specific content")
    parser.add_argument("--skip-test", action="store_true", help="Skip test query")
    args = parser.parse_args()

    # If guild_id specified, adjust db_path
    if args.guild_id:
        args.db_path = Path(f"training_materials/{args.guild_id}/vector_db")

    print("🔧 Creating ChromaDB vector store...")
    print(f"   Chunks: {args.chunks}")
    print(f"   Database: {args.db_path}")
    if args.guild_id:
        print(f"   Guild ID: {args.guild_id} (guild-specific content)")
    else:
        print("   Scope: Default (all guilds)")
    print()

    # Create database directory
    args.db_path.mkdir(parents=True, exist_ok=True)

    # Load chunks
    print("📦 Loading chunks...")
    chunks = load_chunks(args.chunks)
    print(f"   Loaded {len(chunks)} chunks")
    print()

    # Create vector store
    print("🗄️  Creating vector store...")
    collection = create_vector_store(chunks=chunks, db_path=args.db_path)
    print()

    # Add chunks with embeddings
    print("🔢 Generating embeddings and adding to collection...")
    print("   (This may take 30-60 seconds for sentence-transformers to download the model)")
    add_chunks_to_collection(collection, chunks)
    print()

    # Test queries
    if not args.skip_test:
        test_queries = [
            "How do I pick a strike price?",
            "What is assignment?",
            "What does BTO mean?",
        ]

        for query in test_queries:
            test_query(collection, query, n_results=3)

    print("✅ Vector store created successfully!")
    print()
    print("📊 Summary:")
    print("   Collection: training_materials")
    print(f"   Chunks: {len(chunks)}")
    print("   Embedding model: all-MiniLM-L6-v2 (384 dimensions)")
    print(f"   Storage: {args.db_path}")
    print()

    print("Next steps:")
    print("  1. Create src/rag/vector_store.py (wrapper class)")
    print("  2. Create src/rag/retriever.py (query interface)")
    print("  3. Integrate with AI tutor")


if __name__ == "__main__":
    main()
