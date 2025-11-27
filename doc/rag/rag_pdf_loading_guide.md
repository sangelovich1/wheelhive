# RAG PDF Loading Guide

Quick reference for adding PDFs to the RAG knowledge base (default/fallback location).

## Directory Structure

```
training_materials/
├── default/                    # Fallback content (all guilds)
│   ├── pdfs/                  # Source PDFs
│   ├── raw/                   # Extracted text (JSON)
│   ├── chunks.json            # Chunked documents
│   └── vector_db/             # ChromaDB vector store
└── {guild_id}/                # Guild-specific content (optional)
    ├── pdfs/
    ├── raw/
    ├── chunks.json
    └── vector_db/
```

## Adding PDFs to Default/Fallback Location

### Step 1: Place PDF in Directory

```bash
# Create directory if it doesn't exist
mkdir -p training_materials/default/pdfs

# Copy or download PDF to the directory
cp /path/to/your.pdf training_materials/default/pdfs/

# OR download directly
curl -o training_materials/default/pdfs/Your-PDF-Name.pdf https://example.com/your.pdf
```

### Step 2: Extract Text from PDF

```bash
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/default/pdfs \
  --output-dir training_materials/default/raw
```

**What this does:**
- Extracts text from all PDFs in the input directory
- Saves JSON files with page-by-page text
- Creates `all_materials.json` combining all documents

### Step 3: Chunk Documents

```bash
python scripts/rag/chunk_documents.py \
  --input-dir training_materials/default/raw \
  --output training_materials/default/chunks.json
```

**What this does:**
- Splits extracted text into semantic chunks (~500 tokens each)
- Preserves metadata (source file, page number, doc type)
- Creates overlapping chunks for better retrieval

**Optional parameters:**
- `--chunk-size 500` - Target tokens per chunk (default: 500)
- `--overlap 50` - Overlap tokens between chunks (default: 50)

### Step 4: Create/Update Vector Store

```bash
python scripts/rag/create_vector_store.py \
  --chunks training_materials/default/chunks.json
```

**What this does:**
- Creates ChromaDB vector database at `training_materials/default/vector_db`
- Generates embeddings using `all-MiniLM-L6-v2` model (384 dimensions)
- Runs test queries to verify retrieval
- **Note:** This will replace the existing default vector store!

**Optional parameters:**
- `--skip-test` - Skip test queries after creation

## Complete Workflow (One-Liner)

```bash
# After placing PDF in training_materials/default/pdfs/
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/default/pdfs \
  --output-dir training_materials/default/raw \
&& python scripts/rag/chunk_documents.py \
  --input-dir training_materials/default/raw \
  --output training_materials/default/chunks.json \
&& python scripts/rag/create_vector_store.py \
  --chunks training_materials/default/chunks.json
```

## Adding PDFs to Guild-Specific Location

Same process, but use guild ID in paths:

```bash
GUILD_ID=1349592236375019520  # Replace with actual guild ID

# Step 1: Place PDF
mkdir -p training_materials/${GUILD_ID}/pdfs
cp /path/to/your.pdf training_materials/${GUILD_ID}/pdfs/

# Step 2: Extract
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/${GUILD_ID}/pdfs \
  --output-dir training_materials/${GUILD_ID}/raw

# Step 3: Chunk
python scripts/rag/chunk_documents.py \
  --input-dir training_materials/${GUILD_ID}/raw \
  --output training_materials/${GUILD_ID}/chunks.json

# Step 4: Create vector store
python scripts/rag/create_vector_store.py \
  --chunks training_materials/${GUILD_ID}/chunks.json \
  --guild-id ${GUILD_ID}
```

## Cascading Search Behavior

When a user queries the AI Assistant:

1. **Guild-specific DB exists?** → Query guild DB first
2. **Not enough results?** → Supplement with default DB
3. **Guild DB doesn't exist?** → Use default DB only

Results are tagged with `vector_db_source` metadata:
- `'guild'` - From guild-specific content
- `'default'` - From fallback content

## Verifying Vector Store

```bash
# Test cascading search with both guild and default DBs
python scripts/test_cascading_search.py

# Check vector store statistics
python src/cli.py admin guild-vector-stats --guild-id GUILD_ID
```

## Example: Adding a New Options Trading PDF

```bash
# 1. Download PDF
curl -o training_materials/default/pdfs/New-Options-Guide.pdf \
  https://example.com/new-options-guide.pdf

# 2. Extract text
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/default/pdfs \
  --output-dir training_materials/default/raw

# 3. Chunk documents
python scripts/rag/chunk_documents.py \
  --input-dir training_materials/default/raw \
  --output training_materials/default/chunks.json

# 4. Update vector store
python scripts/rag/create_vector_store.py \
  --chunks training_materials/default/chunks.json

# 5. Verify
ls -lh training_materials/default/vector_db/
```

## Current Default PDFs (as of 2025-11-08)

1. **AAII-Wheel-Strategy.pdf** (626 KB)
   - Source: American Association of Individual Investors
   - Topics: Cash-secured puts, covered calls, assignment handling

2. **Fidelity-Options-Greeks-Demystified.pdf** (590 KB)
   - Source: Fidelity
   - Topics: Delta, gamma, theta, vega explained with examples

3. **Fidelity-Decoding-Greeks.pdf** (1.6 MB)
   - Source: Fidelity
   - Topics: Managing options trades, planning strategies

4. **Interactive-Brokers-FX-Greeks.pdf** (466 KB)
   - Source: Interactive Brokers
   - Topics: Technical Greeks explanation, formulas, hedging

**Total:** 129 pages, 127 chunks, ~9,789 tokens

## Troubleshooting

### "No PDF files found"
- Check that PDFs are in the correct directory
- Ensure filenames end with `.pdf` (case-sensitive)

### "Vector store not initialized" error in bot
- Verify `training_materials/default/vector_db/` exists
- Run create_vector_store.py to initialize

### "ChromaDB not installed"
```bash
pip install chromadb sentence-transformers
```

### Test queries return poor results
- Check distance scores (< 1.0 is excellent, > 1.5 is weak)
- May need more targeted PDFs on specific topics
- Consider adding FAQs for specific questions

## Advanced: Replacing Vector Store

If you need to completely replace the vector store:

```bash
# Backup existing (optional)
mv training_materials/default/vector_db training_materials/default/vector_db.backup

# Remove old chunks/raw data
rm -rf training_materials/default/raw training_materials/default/chunks.json

# Start fresh with new PDFs
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/default/pdfs \
  --output-dir training_materials/default/raw

python scripts/rag/chunk_documents.py \
  --input-dir training_materials/default/raw \
  --output training_materials/default/chunks.json

python scripts/rag/create_vector_store.py \
  --chunks training_materials/default/chunks.json
```

## See Also

- `doc/rag_knowledge_base_guide.md` - Complete RAG system documentation
- `doc/research/guild_specific_rag_design.md` - Architecture details
- `scripts/test_cascading_search.py` - Test cascading fallback logic
