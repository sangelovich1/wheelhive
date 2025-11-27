#!/usr/bin/env python3
"""
Test RAG retrieval system with interactive queries.

This script tests the production RAG classes to ensure semantic search
works correctly before integrating with the AI tutor.

Usage:
    python scripts/rag/test_rag_query.py [--query "your question"]
    python scripts/rag/test_rag_query.py --interactive

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from rag import TrainingMaterialsRetriever


def test_single_query(query: str, n_results: int = 3):
    """
    Test a single query.

    Args:
        query: Question to ask
        n_results: Number of results to retrieve
    """
    print(f"🔍 Query: \"{query}\"")
    print()

    # Initialize retriever
    retriever = TrainingMaterialsRetriever()

    # Retrieve materials
    result = retriever.retrieve_for_question(query, n_results=n_results)

    # Show results
    print(f"📚 Found {len(result['chunks'])} relevant chunks:")
    print()

    for i, chunk in enumerate(result['chunks'], 1):
        print(f"--- Result {i} ---")
        print(f"Source: {chunk['source_file']} (Page {chunk['page_number']})")
        print(f"Section: {chunk['section']}")
        print(f"Type: {chunk['doc_type']}")
        print(f"Distance: {chunk['distance']:.4f}")
        print(f"Preview: {chunk['text'][:200]}...")
        print()

    # Show formatted context (what LLM would see)
    print("=" * 80)
    print("LLM CONTEXT (formatted for AI tutor):")
    print("=" * 80)
    print(result['context'])


def interactive_mode():
    """Run in interactive query mode."""
    print("🤖 RAG Interactive Query Mode")
    print("=" * 80)
    print("Ask questions about the wheel strategy training materials.")
    print("Type 'quit' or 'exit' to stop, 'stats' to see vector store info.")
    print()

    retriever = TrainingMaterialsRetriever()

    while True:
        try:
            query = input("❓ Your question: ").strip()

            if not query:
                continue

            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!")
                break

            if query.lower() == 'stats':
                stats = retriever.get_stats()
                print()
                print("📊 Vector Store Statistics:")
                print(f"   Total chunks: {stats['total_chunks']}")
                print(f"   Collection: {stats['collection_name']}")
                print(f"   Embedding model: {stats['embedding_model']}")
                print(f"   Description: {stats['description']}")
                print()
                continue

            print()
            test_single_query(query, n_results=3)
            print()

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def run_predefined_tests():
    """Run a set of predefined test queries."""
    test_queries = [
        "How do I pick a strike price for my first cash-secured put?",
        "What happens if I get assigned?",
        "What does BTO mean?",
        "Explain the wheel strategy",
        "How much money do I need to start?",
        "What is a covered call?",
        "How do I select expiration dates?"
    ]

    print("🧪 Running predefined test queries...")
    print("=" * 80)
    print()

    for query in test_queries:
        test_single_query(query, n_results=2)
        print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Test RAG retrieval system')
    parser.add_argument('--query', type=str,
                       help='Single query to test')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Run in interactive mode')
    parser.add_argument('--test-suite', action='store_true',
                       help='Run predefined test queries')
    parser.add_argument('--n-results', type=int, default=3,
                       help='Number of results to retrieve (default: 3)')
    args = parser.parse_args()

    if args.test_suite:
        run_predefined_tests()
    elif args.interactive:
        interactive_mode()
    elif args.query:
        test_single_query(args.query, args.n_results)
    else:
        # Default to interactive mode
        interactive_mode()


if __name__ == '__main__':
    main()
