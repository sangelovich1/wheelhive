#!/usr/bin/env python3
"""
Extract text content from training PDFs for RAG system.

This script reads the community training materials (PDFs) and extracts
clean text content with metadata for chunking and embedding.

Usage:
    python scripts/rag/extract_pdfs.py [--output-dir OUTPUT_DIR]

Copyright (c) 2025 Steve Angelovich. Licensed under the MIT License.
"""

import json
import sys
from pathlib import Path
from typing import Any


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import constants as const


def extract_with_pypdf2(pdf_path: Path) -> dict[str, Any]:
    """
    Extract text from PDF using PyPDF2 (simple extraction).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with extracted text and metadata
    """
    try:
        import PyPDF2
    except ImportError:
        print("❌ PyPDF2 not installed. Run: pip install pypdf2")
        sys.exit(1)

    print("  Extracting with PyPDF2...")

    pages: list[dict[str, Any]] = []
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        num_pages = len(reader.pages)

        for page_num in range(num_pages):
            page = reader.pages[page_num]
            text = page.extract_text()

            if text.strip():
                pages.append({"page_number": page_num + 1, "text": text.strip()})

    return {
        "source_file": pdf_path.name,
        "extraction_method": "pypdf2",
        "num_pages": num_pages,
        "pages": pages,
        "full_text": "\n\n".join([p["text"] for p in pages]),
    }


def extract_with_pdfplumber(pdf_path: Path) -> dict[str, Any]:
    """
    Extract text from PDF using pdfplumber (better layout preservation).

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with extracted text and metadata
    """
    try:
        import pdfplumber
    except ImportError:
        print("⚠️  pdfplumber not installed. Falling back to PyPDF2.")
        print("   For better extraction: pip install pdfplumber")
        return extract_with_pypdf2(pdf_path)

    print("  Extracting with pdfplumber...")

    pages: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()

            if text and text.strip():
                pages.append(
                    {
                        "page_number": page_num + 1,
                        "text": text.strip(),
                        "width": page.width,
                        "height": page.height,
                    }
                )

    return {
        "source_file": pdf_path.name,
        "extraction_method": "pdfplumber",
        "num_pages": num_pages,
        "pages": pages,
        "full_text": "\n\n".join([p["text"] for p in pages]),
    }


def extract_terminology_image(image_path: Path) -> dict[str, Any]:
    """
    Extract text from Terminology.png using OCR or manual transcription.

    For MVP, we'll use the manual transcription from TRADE_GLOSSARY in constants.py

    Args:
        image_path: Path to terminology image

    Returns:
        Dict with terminology content
    """
    print("  Using manual transcription from constants.TRADE_GLOSSARY...")

    # The terminology content is already manually transcribed in constants.py
    # as TRADE_GLOSSARY - we'll use that for RAG

    return {
        "source_file": image_path.name,
        "extraction_method": "manual_transcription",
        "num_pages": 1,
        "pages": [{"page_number": 1, "text": const.TRADE_GLOSSARY}],
        "full_text": const.TRADE_GLOSSARY,
    }


def main():
    """Extract text from all training materials."""
    import argparse

    parser = argparse.ArgumentParser(description="Extract text from training PDFs")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("doc/training"),
        help="Input directory containing PDFs (default: doc/training/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("training_materials/raw"),
        help="Output directory for extracted text (default: training_materials/raw/)",
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("📚 Extracting training materials...")
    print(f"   Input directory: {args.input_dir}")
    print(f"   Output directory: {output_dir}")
    print()

    # Find all PDFs and PNGs in input directory
    training_dir = args.input_dir
    if not training_dir.exists():
        print(f"❌ Input directory not found: {training_dir}")
        sys.exit(1)

    materials = list(training_dir.glob("*.pdf")) + list(training_dir.glob("*.png"))

    if not materials:
        print(f"⚠️  No PDF or PNG files found in {training_dir}")
        sys.exit(1)

    print(f"Found {len(materials)} files to process")
    print()

    extracted = []

    for material in materials:
        if not material.exists():
            print(f"⚠️  File not found: {material}")
            continue

        print(f"📄 Processing: {material.name}")

        # Extract based on file type
        if material.suffix == ".pdf":
            result = extract_with_pdfplumber(material)
        elif material.suffix == ".png":
            result = extract_terminology_image(material)
        else:
            print(f"  ⚠️  Unknown file type: {material.suffix}")
            continue

        # Save individual extraction
        output_file = output_dir / f"{material.stem}.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"  ✅ Extracted {result['num_pages']} pages ({len(result['full_text'])} chars)")
        print(f"  📝 Saved to: {output_file}")
        print()

        extracted.append(result)

    # Save combined extraction
    combined_file = output_dir / "all_materials.json"
    with open(combined_file, "w") as f:
        json.dump(extracted, f, indent=2)

    print("✅ Extraction complete!")
    print(f"   Total documents: {len(extracted)}")
    print(f"   Combined output: {combined_file}")
    print()

    # Show summary
    total_pages = sum(doc["num_pages"] for doc in extracted)
    total_chars = sum(len(doc["full_text"]) for doc in extracted)

    print("📊 Summary:")
    print(f"   Total pages: {total_pages}")
    print(f"   Total characters: {total_chars:,}")
    print(f"   Estimated tokens: ~{total_chars // 4:,} (rough estimate)")
    print()

    print("Next steps:")
    print("  1. Review extracted text in training_materials/raw/")
    print("  2. Run: python scripts/rag/chunk_documents.py")
    print("  3. Run: python scripts/rag/create_vector_store.py")


if __name__ == "__main__":
    main()
