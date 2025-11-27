"""
Knowledge Base Management CLI

Commands for managing training materials, FAQs, PDFs, images, and vector database.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path

import click


logger = logging.getLogger(__name__)


@click.group()
def knowledge():
    """
    Manage training materials and knowledge base.

    This command group handles FAQs, PDFs, images, and vector database
    operations for guild-specific and default training materials.
    """


# =============================================================================
# FAQ Commands (moved from admin.py)
# =============================================================================


@knowledge.command("faq-add")
@click.option("--guild-id", type=int, required=True, help="Guild ID for FAQ")
@click.option("--question", type=str, required=True, help="FAQ question")
@click.option("--answer", type=str, required=True, help="FAQ answer")
@click.option("--username", default="cli_admin", help="Admin username")
@click.option("--skip-validation", is_flag=True, help="Skip quality validation (not recommended)")
@click.pass_context
def faq_add(ctx, guild_id: int, question: str, answer: str, username: str, skip_validation: bool):
    """
    Add FAQ to guild-specific knowledge base with validation.

    This command adds a new FAQ entry to the guild's RAG vector store
    after validating its quality using an LLM.

    Examples:
      cli.py knowledge faq-add --guild-id 123 --question "What is delta?" --answer "Delta measures..."
      cli.py knowledge faq-add --guild-id 123 --question "..." --answer "..." --skip-validation
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo(f"📚 Adding FAQ to guild {guild_id} knowledge base...")
        click.echo(f"   Question: {question[:60]}{'...' if len(question) > 60 else ''}")
        click.echo(f"   Answer length: {len(answer)} chars")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Step 1: Validate (unless skipped)
        if not skip_validation:
            click.echo("🔍 Validating FAQ quality...")
            validation_result = faq_mgr.validate_faq_quality(question, answer)

            # Display validation results
            click.echo(f"   Quality Score: {validation_result['score']:.1%}")
            click.echo(f"   Valid: {validation_result['is_valid']}")
            click.echo()

            if not validation_result["is_valid"]:
                click.secho("❌ VALIDATION FAILED", fg="red", bold=True)
                click.echo()
                click.echo("Issues:")
                for issue in validation_result["issues"]:
                    click.echo(f"  • {issue}")
                click.echo()

                if validation_result["suggestions"]:
                    click.echo("Suggestions:")
                    for sug in validation_result["suggestions"]:
                        click.echo(f"  • {sug}")
                    click.echo()

                click.echo(f"Reasoning: {validation_result.get('reasoning', 'N/A')}")
                click.echo()
                click.secho("FAQ not added. Please revise and try again.", fg="yellow")
                ctx.exit(1)

            # Show validation success
            click.secho("✓ Validation passed", fg="green")
            if validation_result["suggestions"]:
                click.echo("\nSuggestions for improvement:")
                for sug in validation_result["suggestions"][:3]:
                    click.echo(f"  • {sug}")
            click.echo()
        else:
            click.secho("⚠ Skipping validation (not recommended)", fg="yellow")
            click.echo()

        # Step 2: Add to vector DB
        click.echo("💾 Adding to vector database...")
        success = faq_mgr.add_faq_to_vector_db(question, answer, username)

        if not success:
            click.secho("\n✗ Failed to add FAQ to database\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ FAQ added successfully", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Added by: {username}")
        click.echo()

    except Exception as e:
        logger.error(f"Error adding FAQ: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("faq-list")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.pass_context
def faq_list(ctx, guild_id: int):
    """
    List all FAQs in guild's knowledge base.

    Examples:
      cli.py knowledge faq-list --guild-id 123
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo(f"📚 Listing FAQs for guild {guild_id}...")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Get FAQs
        faqs = faq_mgr.list_faqs()

        if not faqs:
            click.secho("No FAQs found for this guild", fg="yellow")
            click.echo()
            return

        # Display FAQs
        click.echo("=" * 80)
        click.secho(f"GUILD {guild_id} FAQS ({len(faqs)} total)", bold=True)
        click.echo("=" * 80)
        click.echo()

        for i, faq in enumerate(faqs, 1):
            click.secho(f"FAQ #{i}", bold=True)
            click.echo(f"  Question: {faq['question']}")
            click.echo(
                f"  Answer: {faq['answer'][:100]}{'...' if len(faq['answer']) > 100 else ''}"
            )
            click.echo(f"  Added by: {faq['added_by']} on {faq['added_at']}")
            click.echo(f"  ID: {faq['id']}")
            click.echo()

    except Exception as e:
        logger.error(f"Error listing FAQs: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("faq-remove")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--faq-id", type=str, required=True, help="FAQ ID to remove")
@click.option("--confirm", is_flag=True, help="Confirm deletion without prompt")
@click.pass_context
def faq_remove(ctx, guild_id: int, faq_id: str, confirm: bool):
    """
    Remove FAQ from guild's knowledge base.

    Get FAQ IDs using: cli.py knowledge faq-list --guild-id <id>

    Examples:
      cli.py knowledge faq-remove --guild-id 123 --faq-id faq_123_2025-01-15_abc123
      cli.py knowledge faq-remove --guild-id 123 --faq-id <id> --confirm
    """
    from faq_manager import FAQManager

    try:
        click.echo()
        click.echo(f"🗑️  Removing FAQ from guild {guild_id}...")
        click.echo(f"   FAQ ID: {faq_id}")
        click.echo()

        # Create FAQ manager
        faq_mgr = FAQManager(guild_id=guild_id)

        # Get FAQ details first
        faqs = faq_mgr.list_faqs()
        faq_to_remove = None
        for faq in faqs:
            if faq["id"] == faq_id:
                faq_to_remove = faq
                break

        if not faq_to_remove:
            click.secho(f"✗ FAQ ID not found: {faq_id}", fg="red")
            click.echo()
            click.echo("Use 'cli.py knowledge faq-list --guild-id <id>' to see available FAQs")
            ctx.exit(1)

        # Show what will be deleted (faq_to_remove is guaranteed non-None here)
        assert faq_to_remove is not None
        click.echo("FAQ to be removed:")
        click.echo(f"  Question: {faq_to_remove['question']}")
        click.echo(f"  Answer: {faq_to_remove['answer'][:100]}...")
        click.echo(f"  Added by: {faq_to_remove['added_by']}")
        click.echo()

        # Confirm deletion unless --confirm flag used
        if not confirm:
            if not click.confirm("Are you sure you want to remove this FAQ?"):
                click.secho("Cancelled", fg="yellow")
                ctx.exit(0)

        # Remove FAQ
        success = faq_mgr.remove_faq(faq_id)

        if not success:
            click.secho("\n✗ Failed to remove FAQ\n", fg="red", err=True)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ FAQ removed successfully", fg="green", bold=True)
        click.echo(f"  Guild: {guild_id}")
        click.echo(f"  Removed ID: {faq_id}")
        click.echo()

    except Exception as e:
        logger.error(f"Error removing FAQ: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


# =============================================================================
# Vector Database Rebuild Commands (Phase 1)
# =============================================================================


@knowledge.command("rebuild")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.pass_context
def rebuild(ctx, guild_id: int | None):
    """
    Rebuild vector store from existing chunks.

    Fast rebuild that uses existing chunks.json file without re-extracting
    or re-chunking. Use this after manual chunk edits.

    Examples:
      cli.py knowledge rebuild --guild-id 123
      cli.py knowledge rebuild  # Rebuild default materials
    """
    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "default"

        chunks_file = base_dir / "chunks.json"
        db_path = base_dir / "vector_db"

        click.echo()
        click.echo(f"🔄 Rebuilding vector store for {desc}...")
        click.echo(f"   Chunks: {chunks_file}")
        click.echo(f"   DB Path: {db_path}")
        click.echo()

        # Validate chunks file exists
        if not chunks_file.exists():
            click.secho(f"✗ Chunks file not found: {chunks_file}", fg="red")
            click.echo()
            click.echo("Run 'knowledge rebuild-full' to extract and chunk documents first.")
            ctx.exit(1)

        # Run vector store creation script
        click.echo("💾 Creating vector embeddings...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/rag/create_vector_store.py",
                "--chunks",
                str(chunks_file),
                "--db-path",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            click.secho("\n✗ Vector store creation failed\n", fg="red", err=True)
            click.echo(result.stderr)
            ctx.exit(1)

        # Success
        click.echo()
        click.secho("✓ Vector store rebuilt successfully", fg="green", bold=True)
        click.echo(f"  Location: {db_path}")
        click.echo()

        # Show summary from chunks file
        with open(chunks_file) as f:
            chunks_data = json.load(f)
            metadata = chunks_data.get("metadata", {})
            click.echo("📊 Summary:")
            click.echo(f"   Total documents: {metadata.get('total_documents', 'N/A')}")
            click.echo(f"   Total chunks: {metadata.get('total_chunks', 'N/A')}")
            click.echo(f"   Chunk size: {metadata.get('chunk_size', 'N/A')} chars")
            click.echo(f"   Overlap: {metadata.get('overlap', 'N/A')} chars")
            click.echo()

    except Exception as e:
        logger.error(f"Error rebuilding vector store: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("rebuild-full")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.pass_context
def rebuild_full(ctx, guild_id: int | None):
    """
    Full rebuild: extract PDFs → chunk → create vector store.

    Complete pipeline that re-extracts text from all PDFs, re-chunks
    documents, and rebuilds the vector store from scratch.

    Use this after adding/removing PDFs manually.

    Examples:
      cli.py knowledge rebuild-full --guild-id 123
      cli.py knowledge rebuild-full  # Rebuild default materials
    """
    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "default"

        pdfs_dir = base_dir / "pdfs"
        raw_dir = base_dir / "raw"
        chunks_file = base_dir / "chunks.json"
        db_path = base_dir / "vector_db"

        click.echo()
        click.echo(f"🔄 Full rebuild for {desc}...")
        click.echo(f"   PDFs: {pdfs_dir}")
        click.echo(f"   Output: {db_path}")
        click.echo()

        # Validate PDFs directory exists
        if not pdfs_dir.exists():
            click.secho(f"✗ PDFs directory not found: {pdfs_dir}", fg="red")
            click.echo()
            click.echo(f"Create directory and add PDFs: mkdir -p {pdfs_dir}")
            ctx.exit(1)

        # Check for PDFs
        pdf_files = list(pdfs_dir.glob("*.pdf"))
        if not pdf_files:
            click.secho(f"⚠ No PDF files found in {pdfs_dir}", fg="yellow")
            click.echo()
            click.echo("Add PDFs to this directory and try again.")
            ctx.exit(1)

        click.echo(f"Found {len(pdf_files)} PDF(s) to process:")
        for pdf in pdf_files:
            click.echo(f"  • {pdf.name}")
        click.echo()

        # Step 1: Extract PDFs
        click.echo("📄 Step 1/3: Extracting text from PDFs...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/rag/extract_pdfs.py",
                "--input-dir",
                str(pdfs_dir),
                "--output-dir",
                str(raw_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            click.secho("\n✗ PDF extraction failed\n", fg="red", err=True)
            click.echo(result.stderr)
            ctx.exit(1)

        click.secho("   ✓ Extraction complete", fg="green")
        click.echo()

        # Step 2: Chunk documents
        click.echo("✂️  Step 2/3: Chunking documents...")
        all_materials = raw_dir / "all_materials.json"

        if not all_materials.exists():
            click.secho(f"✗ Expected file not found: {all_materials}", fg="red")
            ctx.exit(1)

        result = subprocess.run(
            [
                sys.executable,
                "scripts/rag/chunk_documents.py",
                "--input",
                str(all_materials),
                "--output",
                str(chunks_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            click.secho("\n✗ Chunking failed\n", fg="red", err=True)
            click.echo(result.stderr)
            ctx.exit(1)

        click.secho("   ✓ Chunking complete", fg="green")
        click.echo()

        # Step 3: Create vector store
        click.echo("💾 Step 3/3: Creating vector embeddings...")
        result = subprocess.run(
            [
                sys.executable,
                "scripts/rag/create_vector_store.py",
                "--chunks",
                str(chunks_file),
                "--db-path",
                str(db_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            click.secho("\n✗ Vector store creation failed\n", fg="red", err=True)
            click.echo(result.stderr)
            ctx.exit(1)

        click.secho("   ✓ Vector store created", fg="green")
        click.echo()

        # Success
        click.secho("✓ Full rebuild complete!", fg="green", bold=True)
        click.echo()

        # Show summary
        with open(chunks_file) as f:
            chunks_data = json.load(f)
            metadata = chunks_data.get("metadata", {})
            stats = chunks_data.get("stats", {})

            click.echo("📊 Summary:")
            click.echo(f"   PDFs processed: {len(pdf_files)}")
            click.echo(f"   Total pages: {metadata.get('total_pages', 'N/A')}")
            click.echo(f"   Total chunks: {metadata.get('total_chunks', 'N/A')}")
            click.echo(f"   Chunk size: {metadata.get('chunk_size', 500)} chars")
            click.echo(f"   Overlap: {metadata.get('overlap', 50)} chars")
            click.echo()

            if "by_document" in stats:
                click.echo("By Document:")
                for doc_name, doc_stats in stats["by_document"].items():
                    click.echo(
                        f"   • {doc_name}: {doc_stats.get('pages', 0)} pages, "
                        f"{doc_stats.get('chunks', 0)} chunks"
                    )
                click.echo()

    except Exception as e:
        logger.error(f"Error in full rebuild: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("list")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.pass_context
def list_materials(ctx, guild_id: int | None):
    """
    List all training materials (PDFs, FAQs, vector DB stats).

    Shows comprehensive overview of knowledge base contents.

    Examples:
      cli.py knowledge list --guild-id 123
      cli.py knowledge list  # Show default materials
    """
    from faq_manager import FAQManager

    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"Guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "Default"

        click.echo()
        click.echo("=" * 80)
        click.secho(f"📚 Training Materials for {desc}", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Check if directory exists
        if not base_dir.exists():
            click.secho(f"⚠ Training materials directory not found: {base_dir}", fg="yellow")
            click.echo()
            click.echo("This location has no training materials yet.")
            click.echo()
            click.echo("To add materials:")
            click.echo(f"  1. Create directory: mkdir -p {base_dir / 'pdfs'}")
            click.echo(f"  2. Add PDFs to: {base_dir / 'pdfs'}")
            click.echo(f"  3. Run: cli.py knowledge rebuild-full --guild-id {guild_id or 'N/A'}")
            click.echo()
            return

        # PDFs
        pdfs_dir = base_dir / "pdfs"
        pdf_files = list(pdfs_dir.glob("*.pdf")) if pdfs_dir.exists() else []

        click.secho(f"PDFs ({len(pdf_files)}):", bold=True)
        if pdf_files:
            for pdf in sorted(pdf_files):
                size_kb = pdf.stat().st_size / 1024
                click.echo(f"  ✓ {pdf.name} ({size_kb:.1f} KB)")
        else:
            click.echo("  (none)")
        click.echo()

        # Images
        images_dir = base_dir / "images"
        image_files = list(images_dir.glob("*.png")) if images_dir.exists() else []
        image_files.extend(list(images_dir.glob("*.jpg")) if images_dir.exists() else [])

        click.secho(f"Images ({len(image_files)}):", bold=True)
        if image_files:
            for img in sorted(image_files):
                size_kb = img.stat().st_size / 1024
                click.echo(f"  ✓ {img.name} ({size_kb:.1f} KB)")
        else:
            click.echo("  (none)")
        click.echo()

        # FAQs
        if guild_id:
            faq_mgr = FAQManager(guild_id=guild_id)
            faqs = faq_mgr.list_faqs()

            click.secho(f"FAQs ({len(faqs)}):", bold=True)
            if faqs:
                for i, faq in enumerate(faqs[:5], 1):  # Show first 5
                    q = faq["question"]
                    if len(q) > 60:
                        q = q[:60] + "..."
                    click.echo(f"  {i}. {q}")
                if len(faqs) > 5:
                    click.echo(f"  ... and {len(faqs) - 5} more")
                click.echo()
                click.echo(f"  Run 'cli.py knowledge faq-list --guild-id {guild_id}' to see all")
            else:
                click.echo("  (none)")
        else:
            click.echo("FAQs:")
            click.echo("  (N/A for default materials - FAQs are guild-specific)")
        click.echo()

        # Vector Database
        db_path = base_dir / "vector_db"
        chunks_file = base_dir / "chunks.json"

        click.secho("Vector Database:", bold=True)
        if db_path.exists():
            # Get DB size
            db_file = db_path / "chroma.sqlite3"
            if db_file.exists():
                db_size_mb = db_file.stat().st_size / (1024 * 1024)
                click.echo(f"  ✓ Database exists ({db_size_mb:.2f} MB)")
            else:
                click.echo("  ✓ Database exists (size unknown)")

            # Get chunk stats
            if chunks_file.exists():
                with open(chunks_file) as f:
                    chunks_data = json.load(f)
                    metadata = chunks_data.get("metadata", {})
                    click.echo(f"  • Total chunks: {metadata.get('total_chunks', 'N/A')}")
                    click.echo(f"  • Chunk size: {metadata.get('chunk_size', 'N/A')} chars")
                    click.echo(f"  • Documents: {metadata.get('total_documents', 'N/A')}")

            click.echo(f"  • Location: {db_path}")
        else:
            click.secho("  ✗ No vector database", fg="yellow")
            click.echo()
            click.echo("  Run 'cli.py knowledge rebuild-full' to create vector database")

        click.echo()

    except Exception as e:
        logger.error(f"Error listing materials: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


# =============================================================================
# PDF Management Commands (Phase 2)
# =============================================================================


@knowledge.command("pdf-list")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.pass_context
def pdf_list(ctx, guild_id: int | None):
    """
    List all PDFs in training materials.

    Shows PDFs with extraction status, file size, page count, and chunk count.

    Examples:
      cli.py knowledge pdf-list --guild-id 123
      cli.py knowledge pdf-list  # List default materials
    """
    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"Guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "Default"

        pdfs_dir = base_dir / "pdfs"
        raw_dir = base_dir / "raw"
        chunks_file = base_dir / "chunks.json"

        click.echo()
        click.echo("=" * 80)
        click.secho(f"📚 Training PDFs for {desc}", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Check if PDFs directory exists
        if not pdfs_dir.exists():
            click.secho(f"⚠ PDFs directory not found: {pdfs_dir}", fg="yellow")
            click.echo()
            click.echo(f"Create directory: mkdir -p {pdfs_dir}")
            click.echo()
            return

        # Get all PDFs
        pdf_files = sorted(pdfs_dir.glob("*.pdf"))

        if not pdf_files:
            click.secho("No PDF files found", fg="yellow")
            click.echo()
            click.echo(f"Add PDFs to: {pdfs_dir}")
            click.echo(f"Then run: cli.py knowledge rebuild-full --guild-id {guild_id or 'N/A'}")
            click.echo()
            return

        # Load chunks data if available
        chunks_data = {}
        if chunks_file.exists():
            with open(chunks_file) as f:
                chunks_json = json.load(f)
                stats = chunks_json.get("stats", {})
                by_doc = stats.get("by_document", {})
                chunks_data = by_doc

        # Load raw extraction data if available
        raw_data = {}
        if raw_dir.exists():
            all_materials = raw_dir / "all_materials.json"
            if all_materials.exists():
                with open(all_materials) as f:
                    materials = json.load(f)
                    for doc in materials:
                        raw_data[doc["source_file"]] = doc

        click.secho(f"PDFs ({len(pdf_files)}):", bold=True)
        click.echo()

        total_pages = 0
        total_chunks = 0
        extracted_count = 0

        for pdf in pdf_files:
            size_kb = pdf.stat().st_size / 1024
            pdf_name = pdf.name

            # Check extraction status
            extracted = pdf_name in raw_data
            pages = raw_data[pdf_name].get("num_pages", "?") if extracted else "?"
            chunks = chunks_data.get(pdf_name, {}).get("chunks", 0)

            # Status indicator
            status = "✓" if extracted else "✗"
            status_color = "green" if extracted else "yellow"

            click.secho(f"  {status} {pdf_name}", fg=status_color, bold=True)
            click.echo(f"    Size: {size_kb:.1f} KB | Pages: {pages} | Chunks: {chunks}")

            if not extracted:
                click.secho(
                    f"    ⚠ Not extracted. Run 'knowledge rebuild-full --guild-id {guild_id or 'default'}'",
                    fg="yellow",
                )

            click.echo()

            # Update totals
            if extracted:
                extracted_count += 1
                if isinstance(pages, int):
                    total_pages += pages
                total_chunks += chunks

        # Summary
        click.echo("-" * 80)
        click.echo(f"Total: {len(pdf_files)} PDFs, {extracted_count} extracted")
        if extracted_count > 0:
            click.echo(f"Pages: {total_pages}, Chunks: {total_chunks}")
        click.echo()

        # Show next steps if not all extracted
        if extracted_count < len(pdf_files):
            click.echo("Next steps:")
            click.echo(
                f"  Run: cli.py knowledge rebuild-full --guild-id {guild_id or '[omit for default]'}"
            )
            click.echo()

    except Exception as e:
        logger.error(f"Error listing PDFs: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("pdf-add")
@click.option("--file", type=click.Path(exists=True), required=True, help="Path to PDF file")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.option(
    "--rebuild/--no-rebuild", default=True, help="Rebuild vector store after adding (default: yes)"
)
@click.pass_context
def pdf_add(ctx, file: str, guild_id: int | None, rebuild: bool):
    """
    Add PDF to training materials.

    Copies PDF to training directory and optionally rebuilds vector store.

    Examples:
      cli.py knowledge pdf-add --file path/to/guide.pdf --guild-id 123
      cli.py knowledge pdf-add --file guide.pdf --guild-id 123 --no-rebuild
      cli.py knowledge pdf-add --file guide.pdf  # Add to default
    """
    import shutil

    try:
        pdf_path = Path(file)

        # Validate it's a PDF
        if pdf_path.suffix.lower() != ".pdf":
            click.secho(f"✗ File is not a PDF: {pdf_path.suffix}", fg="red")
            ctx.exit(1)

        # Determine target directory
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "default"

        target_dir = base_dir / "pdfs"
        target_file = target_dir / pdf_path.name

        click.echo()
        click.echo(f"📄 Adding PDF to {desc}...")
        click.echo(f"   Source: {pdf_path}")
        click.echo(f"   Target: {target_file}")
        click.echo()

        # Check if file already exists
        if target_file.exists():
            click.secho(f"⚠ PDF already exists: {target_file}", fg="yellow")
            if not click.confirm("Overwrite existing file?"):
                click.secho("Cancelled", fg="yellow")
                ctx.exit(0)

        # Create directory if needed
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy PDF
        click.echo("📋 Copying PDF...")
        shutil.copy2(pdf_path, target_file)
        size_kb = target_file.stat().st_size / 1024
        click.secho(f"   ✓ Copied ({size_kb:.1f} KB)", fg="green")
        click.echo()

        # Rebuild if requested
        if rebuild:
            click.echo("🔄 Rebuilding vector store...")
            click.echo()

            # Call rebuild-full command
            result = subprocess.run(
                [
                    sys.executable,
                    "src/cli.py",
                    "knowledge",
                    "rebuild-full",
                    *(["--guild-id", str(guild_id)] if guild_id else []),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                click.secho("\n✗ Rebuild failed\n", fg="red", err=True)
                click.echo(result.stderr)
                click.echo()
                click.echo("PDF was copied but vector store not updated.")
                click.echo(
                    f"Run manually: cli.py knowledge rebuild-full --guild-id {guild_id or '[omit]'}"
                )
                ctx.exit(1)

            click.secho("✓ Vector store rebuilt", fg="green")
        else:
            click.secho("⚠ Skipping rebuild (--no-rebuild)", fg="yellow")
            click.echo()
            click.echo("To rebuild later:")
            click.echo(
                f"  cli.py knowledge rebuild-full --guild-id {guild_id or '[omit for default]'}"
            )

        click.echo()
        click.secho("✓ PDF added successfully", fg="green", bold=True)
        click.echo(f"  Location: {target_file}")
        click.echo()

    except Exception as e:
        logger.error(f"Error adding PDF: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("pdf-remove")
@click.option("--file", type=str, required=True, help="PDF filename to remove")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.option(
    "--rebuild/--no-rebuild", default=True, help="Rebuild vector store after removal (default: yes)"
)
@click.option("--confirm", is_flag=True, help="Confirm deletion without prompt")
@click.pass_context
def pdf_remove(ctx, file: str, guild_id: int | None, rebuild: bool, confirm: bool):
    """
    Remove PDF from training materials.

    Deletes PDF and its extracted data, optionally rebuilds vector store.

    Examples:
      cli.py knowledge pdf-remove --file AAII-Wheel-Strategy.pdf --guild-id 123
      cli.py knowledge pdf-remove --file guide.pdf --guild-id 123 --confirm
      cli.py knowledge pdf-remove --file guide.pdf --no-rebuild
    """
    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "default"

        pdf_file = base_dir / "pdfs" / file
        raw_file = base_dir / "raw" / f"{Path(file).stem}.json"

        click.echo()
        click.echo(f"🗑️  Removing PDF from {desc}...")
        click.echo(f"   PDF: {pdf_file}")
        click.echo()

        # Check if PDF exists
        if not pdf_file.exists():
            click.secho(f"✗ PDF not found: {pdf_file}", fg="red")
            click.echo()
            click.echo(
                f"Run 'cli.py knowledge pdf-list --guild-id {guild_id or '[omit]'}' to see available PDFs"
            )
            ctx.exit(1)

        # Show file info
        size_kb = pdf_file.stat().st_size / 1024
        click.echo(f"File: {file} ({size_kb:.1f} KB)")
        if raw_file.exists():
            click.echo(f"Extracted data: {raw_file}")
        click.echo()

        # Confirm deletion
        if not confirm:
            if not click.confirm(f"Are you sure you want to remove {file}?"):
                click.secho("Cancelled", fg="yellow")
                ctx.exit(0)

        # Delete PDF
        click.echo("🗑️  Deleting PDF...")
        pdf_file.unlink()
        click.secho("   ✓ PDF deleted", fg="green")

        # Delete raw extraction if exists
        if raw_file.exists():
            click.echo("🗑️  Deleting extracted data...")
            raw_file.unlink()
            click.secho("   ✓ Extracted data deleted", fg="green")

        click.echo()

        # Rebuild if requested
        if rebuild:
            click.echo("🔄 Rebuilding vector store...")
            click.echo()

            # Call rebuild-full command
            result = subprocess.run(
                [
                    sys.executable,
                    "src/cli.py",
                    "knowledge",
                    "rebuild-full",
                    *(["--guild-id", str(guild_id)] if guild_id else []),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                click.secho("\n✗ Rebuild failed\n", fg="red", err=True)
                click.echo(result.stderr)
                click.echo()
                click.echo("PDF was removed but vector store not updated.")
                click.echo(
                    f"Run manually: cli.py knowledge rebuild-full --guild-id {guild_id or '[omit]'}"
                )
                ctx.exit(1)

            click.secho("✓ Vector store rebuilt", fg="green")
        else:
            click.secho("⚠ Skipping rebuild (--no-rebuild)", fg="yellow")
            click.echo()
            click.echo("To rebuild later:")
            click.echo(
                f"  cli.py knowledge rebuild-full --guild-id {guild_id or '[omit for default]'}"
            )

        click.echo()
        click.secho("✓ PDF removed successfully", fg="green", bold=True)
        click.echo()

    except Exception as e:
        logger.error(f"Error removing PDF: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)


@knowledge.command("pdf-info")
@click.option("--file", type=str, required=True, help="PDF filename")
@click.option("--guild-id", type=int, help="Guild ID (omit for default)")
@click.pass_context
def pdf_info(ctx, file: str, guild_id: int | None):
    """
    Show detailed information about a PDF.

    Displays metadata, extraction status, chunk info, and sample content.

    Examples:
      cli.py knowledge pdf-info --file AAII-Wheel-Strategy.pdf --guild-id 123
      cli.py knowledge pdf-info --file guide.pdf  # Check default materials
    """
    try:
        # Determine paths
        if guild_id:
            base_dir = Path(f"training_materials/{guild_id}")
            desc = f"Guild {guild_id}"
        else:
            base_dir = Path("training_materials/default")
            desc = "Default"

        pdf_file = base_dir / "pdfs" / file
        raw_file = base_dir / "raw" / f"{Path(file).stem}.json"
        chunks_file = base_dir / "chunks.json"

        click.echo()
        click.echo("=" * 80)
        click.secho(f"📄 {file}", bold=True)
        click.echo("=" * 80)
        click.echo()

        # Check if PDF exists
        if not pdf_file.exists():
            click.secho(f"✗ PDF not found: {pdf_file}", fg="red")
            click.echo()
            ctx.exit(1)

        # File Info
        click.secho("File Info:", bold=True)
        size_kb = pdf_file.stat().st_size / 1024
        size_mb = size_kb / 1024
        click.echo(f"  Size: {size_kb:.1f} KB ({size_mb:.2f} MB)")
        click.echo(f"  Location: {pdf_file}")
        click.echo(f"  Collection: {desc}")
        click.echo()

        # Extraction Info
        click.secho("Extraction:", bold=True)
        if raw_file.exists():
            with open(raw_file) as f:
                raw_data = json.load(f)

            click.echo(f"  Method: {raw_data.get('extraction_method', 'N/A')}")
            click.echo(f"  Pages: {raw_data.get('num_pages', 'N/A')}")
            click.echo(f"  Characters: {len(raw_data.get('full_text', '')):,}")
            click.echo(f"  Extracted: {raw_file}")
        else:
            click.secho("  ✗ Not extracted", fg="yellow")
            click.echo(f"  Run: cli.py knowledge rebuild-full --guild-id {guild_id or '[omit]'}")
        click.echo()

        # Chunking Info
        click.secho("Chunking:", bold=True)
        if chunks_file.exists():
            with open(chunks_file) as f:
                chunks_data = json.load(f)

            stats = chunks_data.get("stats", {})
            by_doc = stats.get("by_document", {})
            doc_stats = by_doc.get(file, {})

            if doc_stats:
                click.echo(f"  Total chunks: {doc_stats.get('chunks', 0)}")
                metadata = chunks_data.get("metadata", {})
                click.echo(f"  Chunk size: {metadata.get('chunk_size', 'N/A')} chars")
                click.echo(f"  Overlap: {metadata.get('overlap', 'N/A')} chars")
                click.echo(f"  Doc type: {doc_stats.get('doc_type', 'N/A')}")

                # Estimate tokens
                num_chunks = doc_stats.get("chunks", 0)
                chunk_size = metadata.get("chunk_size", 500)
                estimated_tokens = (num_chunks * chunk_size) // 4
                click.echo(f"  Estimated tokens: ~{estimated_tokens:,}")
            else:
                click.secho("  ✗ Not chunked", fg="yellow")
        else:
            click.secho("  ✗ No chunks file", fg="yellow")
        click.echo()

        # Vector Store Status
        click.secho("Vector Store:", bold=True)
        db_path = base_dir / "vector_db"
        if db_path.exists():
            db_file = db_path / "chroma.sqlite3"
            if db_file.exists():
                click.secho("  ✓ Embedded in vector database", fg="green")
                click.echo("  Collection: training_materials")
                click.echo(f"  DB Path: {db_path}")

                # Show chunk IDs if available
                if chunks_file.exists() and doc_stats:
                    num_chunks = doc_stats.get("chunks", 0)
                    stem = Path(file).stem.lower().replace(" ", "-")
                    click.echo(f"  Chunk IDs: {stem}-p1-c0 through {stem}-p*-c{num_chunks-1}")
            else:
                click.secho("  ✗ Database exists but file missing", fg="yellow")
        else:
            click.secho("  ✗ Not in vector database", fg="yellow")
            click.echo(f"  Run: cli.py knowledge rebuild --guild-id {guild_id or '[omit]'}")
        click.echo()

        # Sample Content (if extracted)
        if raw_file.exists():
            click.secho("Sample Content:", bold=True)
            pages = raw_data.get("pages", [])
            if pages:
                first_page = pages[0]
                text = first_page.get("text", "")
                # Show first 300 chars
                sample = text[:300]
                if len(text) > 300:
                    sample += "..."
                click.echo(f'  "{sample}"')
                click.echo()

    except Exception as e:
        logger.error(f"Error getting PDF info: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}\n", fg="red", err=True)
        ctx.exit(1)
