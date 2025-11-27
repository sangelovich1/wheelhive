#!/usr/bin/env python3
"""
Chunk training materials into optimal sizes for RAG embeddings.

This script takes the extracted training text and splits it into semantically
meaningful chunks with overlap for better retrieval accuracy.

Chunking Strategy:
- Target: 500 tokens per chunk (balance between context and precision)
- Overlap: 50 tokens (preserve context across boundaries)
- Split on: Paragraphs, sentences, then whitespace (semantic boundaries)
- Metadata: Source file, page number, section headers, doc type

Usage:
    python scripts/rag/chunk_documents.py [--input-dir INPUT] [--output OUTPUT]

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def count_tokens_estimate(text: str) -> int:
    """
    Estimate token count (rough approximation: 1 token ≈ 4 characters).

    For production, use tiktoken for accurate counts.

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4


def extract_section_header(text: str) -> str:
    """
    Extract section header from chunk text (for metadata).

    Looks for common patterns:
    - "Step 1: Title"
    - "SECTION: Title"
    - Numbered lists

    Args:
        text: Chunk text

    Returns:
        Section header or "Unknown"
    """
    # Look for step numbers
    step_match = re.match(r"(\d+\.\s+Step \d+:.*?)(?:\n|•)", text)
    if step_match:
        return step_match.group(1).strip()

    # Look for headers (all caps or Title Case)
    header_match = re.match(r"([A-Z][A-Z\s]+)(?:\n|:)", text)
    if header_match:
        return header_match.group(1).strip()

    # Look for titles
    title_match = re.match(r"(.*?)(?:\n\n|\n[•\-])", text, re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
        if len(title) < 100:  # Reasonable header length
            return title

    return "Unknown Section"


def chunk_text(
    text: str,
    source_file: str,
    page_number: int,
    chunk_size: int = 500,
    overlap: int = 50,
    doc_type: str = "guide",
) -> list[dict[str, Any]]:
    """
    Split text into overlapping chunks with metadata.

    Args:
        text: Text to chunk
        source_file: Source PDF filename
        page_number: Page number in source
        chunk_size: Target tokens per chunk
        overlap: Overlap tokens between chunks
        doc_type: Document type (guide, reference, conceptual)

    Returns:
        List of chunk dicts with text and metadata
    """
    # Split on double newlines first (paragraphs)
    paragraphs = re.split(r"\n\n+", text)

    chunks = []
    current_chunk: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens_estimate(para)

        # If single paragraph exceeds chunk_size, split on sentences
        if para_tokens > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sentence in sentences:
                sentence_tokens = count_tokens_estimate(sentence)

                if current_tokens + sentence_tokens > chunk_size and current_chunk:
                    # Save current chunk
                    chunk_text = "\n\n".join(current_chunk)
                    chunks.append(
                        {
                            "text": chunk_text,
                            "tokens": current_tokens,
                            "source_file": source_file,
                            "page_number": page_number,
                            "doc_type": doc_type,
                            "section": extract_section_header(chunk_text),
                        }
                    )

                    # Start new chunk with overlap
                    # Keep last few sentences for context
                    overlap_text = current_chunk[-1] if current_chunk else ""
                    current_chunk = [overlap_text, sentence] if overlap_text else [sentence]
                    current_tokens = count_tokens_estimate(" ".join(current_chunk))
                else:
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
        # Add whole paragraph
        elif current_tokens + para_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                {
                    "text": chunk_text,
                    "tokens": current_tokens,
                    "source_file": source_file,
                    "page_number": page_number,
                    "doc_type": doc_type,
                    "section": extract_section_header(chunk_text),
                }
            )

            # Start new chunk with overlap
            overlap_text = current_chunk[-1] if current_chunk else ""
            current_chunk = [overlap_text, para] if overlap_text else [para]
            current_tokens = count_tokens_estimate("\n\n".join(current_chunk))
        else:
            current_chunk.append(para)
            current_tokens += para_tokens

    # Add final chunk
    if current_chunk:
        chunk_text = "\n\n".join(current_chunk)
        chunks.append(
            {
                "text": chunk_text,
                "tokens": current_tokens,
                "source_file": source_file,
                "page_number": page_number,
                "doc_type": doc_type,
                "section": extract_section_header(chunk_text),
            }
        )

    return chunks


def determine_doc_type(source_file: str) -> str:
    """
    Determine document type from filename.

    Args:
        source_file: Source filename

    Returns:
        Doc type: 'conceptual', 'execution_guide', or 'reference'
    """
    filename_lower = source_file.lower()

    if "main strategy" in filename_lower:
        return "conceptual"
    if "terminology" in filename_lower:
        return "reference"
    # CSP or CC guides
    return "execution_guide"


def clean_text(text: str) -> str:
    """
    Clean extracted text (remove URLs, page headers, excess whitespace).

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    # Remove URLs
    text = re.sub(r"https?://[^\s]+", "", text)

    # Remove page headers (date/time stamps)
    text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}\s+[AP]M", "", text)

    # Remove "Page X of Y" footers
    text = re.sub(r"Page \d+ of \d+", "", text)

    # Remove emoji in isolation
    text = re.sub(r"^\s*[📈💰💲💸]\s*$", "", text, flags=re.MULTILINE)

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


def main():
    """Chunk all extracted training materials."""
    import argparse

    parser = argparse.ArgumentParser(description="Chunk training materials for RAG")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("training_materials/raw"),
        help="Input directory with extracted JSON files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training_materials/chunks/training_chunks.json"),
        help="Output file for chunks",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500, help="Target tokens per chunk (default: 500)"
    )
    parser.add_argument(
        "--overlap", type=int, default=50, help="Overlap tokens between chunks (default: 50)"
    )
    args = parser.parse_args()

    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print("📦 Chunking training materials...")
    print(f"   Input: {args.input_dir}")
    print(f"   Output: {args.output}")
    print(f"   Chunk size: {args.chunk_size} tokens")
    print(f"   Overlap: {args.overlap} tokens")
    print()

    # Load all extracted documents
    all_materials_file = args.input_dir / "all_materials.json"
    if not all_materials_file.exists():
        print(f"❌ Input file not found: {all_materials_file}")
        print("   Run: python scripts/rag/extract_pdfs.py first")
        sys.exit(1)

    with open(all_materials_file) as f:
        documents = json.load(f)

    all_chunks = []
    stats: dict[str, Any] = {
        "total_documents": len(documents),
        "total_pages": 0,
        "total_chunks": 0,
        "by_document": {},
    }

    for doc in documents:
        source_file = doc["source_file"]
        doc_type = determine_doc_type(source_file)

        print(f"📄 Processing: {source_file} ({doc_type})")

        doc_chunks = []

        for page in doc["pages"]:
            page_num = page["page_number"]
            raw_text = page["text"]

            # Clean text
            clean = clean_text(raw_text)

            if not clean:
                continue

            # Chunk the page
            page_chunks = chunk_text(
                text=clean,
                source_file=source_file,
                page_number=page_num,
                chunk_size=args.chunk_size,
                overlap=args.overlap,
                doc_type=doc_type,
            )

            doc_chunks.extend(page_chunks)

        # Add chunk IDs
        for i, chunk in enumerate(doc_chunks):
            chunk["chunk_id"] = f"{source_file}:chunk_{i}"
            all_chunks.append(chunk)

        # Stats
        stats["total_pages"] += doc["num_pages"]
        stats["total_chunks"] += len(doc_chunks)
        stats["by_document"][source_file] = {
            "pages": doc["num_pages"],
            "chunks": len(doc_chunks),
            "doc_type": doc_type,
        }

        print(f"   ✅ Created {len(doc_chunks)} chunks")
        print()

    # Save chunks
    output = {
        "metadata": {
            "chunk_size": args.chunk_size,
            "overlap": args.overlap,
            "total_documents": stats["total_documents"],
            "total_pages": stats["total_pages"],
            "total_chunks": stats["total_chunks"],
        },
        "stats": stats,
        "chunks": all_chunks,
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print("✅ Chunking complete!")
    print(f"   Output: {args.output}")
    print()

    print("📊 Summary:")
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Total pages: {stats['total_pages']}")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Avg chunks/page: {stats['total_chunks'] / stats['total_pages']:.1f}")
    print()

    print("Per-document breakdown:")
    for doc_name, doc_stats in stats["by_document"].items():
        print(f"   {doc_name}")
        print(f"      Pages: {doc_stats['pages']}")
        print(f"      Chunks: {doc_stats['chunks']}")
        print(f"      Type: {doc_stats['doc_type']}")
    print()

    print("Next steps:")
    print("  1. Install ChromaDB: pip install chromadb sentence-transformers")
    print("  2. Run: python scripts/rag/create_vector_store.py")
    print("  3. Test RAG queries")


if __name__ == "__main__":
    main()
