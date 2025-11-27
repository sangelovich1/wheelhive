# CLAUDE.md

Discord options trading bot with automated trade tracking, analytics, LLM-powered insights, and multi-brokerage support.

## Quick Start

```bash
# Setup & Run
python -m venv .bot_venv && source .bot_venv/bin/activate && pip install -r requirements.txt
python src/bot.py                    # Start bot
python src/cli.py --help             # CLI commands
./check.sh                           # Validate (syntax + types)
./unittests.sh                       # Run tests
```

**Required env:** `DISCORD_TOKEN`, `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`
**Note:** `./restart_and_run.sh` requires manual sudo execution for MCP server restart

## CRITICAL: Database Instantiation

```python
# ❌ WRONG - Creates in-memory database (silent failure)
db = Db('trades.db')  # String interpreted as truthy, becomes in_memory=True

# ✅ CORRECT - Use constants
import constants as const
db = Db(in_memory=False)  # Uses const.DATABASE_PATH internally

# ✅ CORRECT - For testing only
db = Db(in_memory=True)   # Explicitly creates in-memory DB
```

**Why this matters:** `Db.__init__` takes `in_memory: bool = False`. Python doesn't enforce type hints at runtime, so passing a string path silently creates an in-memory database where queries fail with "no such table" errors.

## Architecture Patterns

### Data Model: Singular/Plural Convention
- `{entity}.py` = Single model (parsing, validation, inherits `baseparser.py`)
- `{entity}s.py` = Collection ops (database queries, bulk operations)

### CLI Structure (Click-based)
Modular command groups in `cli/`: `admin`, `analytics`, `brokerage`, `channels`, `knowledge`, `llm`, `messages`, `reports`, `scanner`, `tickers`, `tx`, `watchlist`

### Discord Bot Structure (bot.py)
**Current:** Monolithic `bot.py` (~2,867 lines) with all commands in `main()` function
**Status:** Functional but could benefit from refactoring

**Known Issues:**
- All 30+ slash commands defined in single `main()` function
- Commands registered as `@client.tree.command()` decorators
- Admin commands (`/channels_*`, `/faq_*`) recently converted from Cog to tree commands
- Hard to navigate, test individual commands, or collaborate on

**Future Refactoring (Not Urgent):**
```
src/commands/
├── trading.py      # /trade, /positions, /my_trades
├── admin.py        # /channels_*, /faq_*
├── reports.py      # /profit, /activity, /download
├── llm.py          # /tutor, /ask, /catch_up
└── info.py         # /about, /help
```

**When to refactor:**
- Adding 5+ more commands
- Need to test commands in isolation
- Multiple contributors working on bot
- Finding bugs due to size/complexity

**For now:** Bot works, prioritize features over refactoring

### Code Quality Principles
**Prioritize clean, maintainable code over short-term convenience.**

When faced with design choices:
- ✅ **DO**: Fix root causes, standardize conventions, refactor for clarity
- ❌ **DON'T**: Add workarounds, maintain dual conventions, optimize for minimal effort

### Type Safety Goals
**CRITICAL: Zero Mypy Warnings Policy**

**Goal**: Maintain **ZERO** type warnings in our codebase at all times.

Current status (as of 2025-11-10):
- Total mypy output: ~63 errors
- Third-party library warnings (stubs not installed): ~1 (ignored)
- **Our codebase errors: 62** (target: **0**)

Track progress:
```bash
# Count total errors
mypy src/ scripts/ 2>&1 | tail -1

# Count only our code (exclude external lib stub warnings)
mypy src/ scripts/ 2>&1 | grep "error:" | grep -vE "stubs not installed|import-untyped" | wc -l

# View all errors
mypy src/ scripts/
```

**Strict commit policy**:
- ✅ Each commit MUST either maintain or reduce the error count
- ❌ NEVER commit code that increases the error count
- 🎯 All new code MUST be type-safe before merging
- 📋 Use proper type hints: function signatures, return types, variables where needed

Examples:
- Standardize naming (lowercase_with_underscores for Python)
- Eliminate duplicate code patterns
- Fix type inconsistencies at the source
- Document why decisions were made

**"Well-designed clean code, not minimizing effort"** - technical debt compounds; invest in quality.

### Critical Rules
1. **Prefer Pandas over SQL**: Use `df_stats.py` and `.as_df()` methods (not `stats.py`)
2. **Use constants.py**: Never hardcode paths/strings (`const.UPLOADS_DIR`, `const.ISO_DATE_FMT`)
3. **Factory patterns**: `parsefactory.py` routes CSV imports, `market_data_factory.py` switches providers
4. **Date handling**: Internal = ISO 8601 via `util.to_db_date()`, User = flexible via `Trade.format_date()`
5. **LLM calls**: Direct completions = `create_llm_provider()`, MCP tools = `LLMAnalyzer`
6. **Namedtuple conventions**: All namedtuple fields use lowercase (e.g., `operation`, `date`, `symbol`)
7. **System Settings**: Use `SystemSettings` for runtime-configurable values (LLM models, feature flags, endpoints). Secrets stay in `.env`
8. **Data Export Pattern**: Classes should implement standardized export methods:
   - `as_df()`: Raw DataFrame with lowercase columns (programmatic access, further processing)
   - `styled_df()`: Formatted DataFrame with Title Case columns (human-readable display)
   - `as_dict()`: List of dicts with lowercase keys (JSON/MCP serialization, LLM consumption)
   - `as_table()`: Formatted string from styled DataFrame (terminal/Discord display)
   - `as_csv()`: CSV export (use `as_df().to_csv()` for raw data or `styled_df().to_csv()` for display)
   - Example: `Scanner` (src/scanner.py:396-574)

### Trade Parsing (Text + Image)
Two pipelines (`vision_strategy.py`): text-based (parses "STO 1x TSLL 11/9 15P at .10") + image-based (OCR → LLM). Messages with both merge results. Year inference: months ≥ current = current year, else next year. Config: `TRADE_PARSING_MODEL` (extraction), `VISION_OCR_MODEL` (OCR), `IMAGE_ANALYSIS_ENABLED`

### System Settings (Runtime Configuration)
**Production-ready alternative to hardcoded constants.**

Database-backed settings (src/system_settings.py) enable configuration changes without code deployment:

```python
from system_settings import get_settings

settings = get_settings()  # Singleton pattern
ollama_url = settings.get('llm.ollama_base_url', 'http://localhost:11434')
settings.set('llm.temperature', 0.7, username='admin', category='llm')
```

**CLI Management:**
```bash
python src/cli.py admin settings-list --category llm              # View settings
python src/cli.py admin settings-get --key llm.ollama_base_url    # Get specific
python src/cli.py admin settings-set --key llm.temperature --value 0.7 --category llm
python src/cli.py admin settings-export --output backup.json      # Backup
python src/cli.py admin settings-import --input backup.json       # Restore
```

**Categories:**
- `llm`: Model endpoints, API bases, temperatures
- `features`: Feature flags (image_analysis_enabled, sentiment_analysis_enabled)
- `market`: Market data provider selection
- `processing`: Queue/batch sizes, workers, thresholds

**Migration:** Run `python scripts/migrate_settings_to_db.py` to seed from constants.py

**Rule:** Settings that change between environments or need runtime updates → SystemSettings. Secrets (API keys, tokens) → `.env`

## Development Workflow

### Investigation Protocol
**Order matters:** CLI first → SQL only for final validation. CLI uses production code paths. Never skip to SQL.
```bash
python src/cli.py tx options list --username USER  # ✅ Primary
sqlite3 trades.db "SELECT COUNT(*) FROM trades;"   # ✅ Validation only
```

### Code Quality Standards
```bash
./check.sh                  # ALWAYS run after changes (syntax + mypy)
pytest tests/               # Unit tests
pytest --cov=src/           # With coverage
```

**Python requirements:** Type hints, PEP 8, docstrings, test coverage

## File Organization

```
src/                    # Core application code
├── bot.py             # Discord bot entry point
├── cli.py             # CLI entry point
├── cli/               # CLI command modules
├── mcp/               # MCP server implementation
│   └── mcp_server.py
├── {entity}.py        # Single entity models
├── {entity}s.py       # Collection/database operations
└── constants.py       # All configuration constants

scripts/               # Reusable utility scripts
└── generate_all_digests.py

tests/                 # Unit tests (*_test.py)
doc/                   # Documentation (non-session)
├── web/               # Web-accessible docs (admin.html)
temp/                  # Temporary files, experiments

daily_digest/          # Generated digests (gitignored)
reports/               # Generated reports (gitignored)
uploads/               # User uploads
downloads/             # User downloads
options_data/          # Cached market data

../wheelhive-site/     # Website (separate repo, auto-deploys via Hostinger webhook)
├── index.html         # Landing page
├── docs.html          # Documentation
├── admin.html         # Admin configuration guide
├── privacy.html       # Privacy policy
├── terms.html         # Terms of service
└── DEPLOYMENT.md      # Webhook auto-deployment setup guide
```

## CLI Command Groups

Use `python src/cli.py --help` for full reference. Key groups:
- **tx**: Transactions (options, dividends, shares, deposits) - `list`, `get`, `rm`
- **analytics**: Stats (`my-stats`, `symbol-stats`)
- **brokerage**: Import/export (`upload`, `download`)
- **reports**: PDF generation (`positions`, `profit`, `digest`, `activity`)
- **messages**: Message analysis (`list`, `by-ticker`, `extracted-trades`, `analyze-image`)
- **llm**: AI analysis (`analyze`, `opportunities`, `ask`, `community-sentiment`)
- **admin**: Management (`list-users`, `analyze`, `batch-analyze-images`, `metrics`)
- **tickers**: Ticker DB (`list`, `add`, `rm`, `blacklist-*`)
- **channels**: Discord config (`list`, `add`, `rm`) - configures which channels to analyze
- **scanner**: Options chain (`scan-puts`, `scan-calls`)
- **knowledge**: Training materials (PDFs, FAQs, vector DB) - see below for details

### knowledge - Training Materials & Knowledge Base

Manage training materials, FAQs, PDFs, and vector database for RAG system.

**FAQ Management:**
```bash
# Add FAQ with LLM validation
python src/cli.py knowledge faq-add --guild-id 123 --question "What is delta?" --answer "Delta measures..."
python src/cli.py knowledge faq-add --guild-id 123 --question "..." --answer "..." --skip-validation

# List all FAQs
python src/cli.py knowledge faq-list --guild-id 123

# Remove FAQ
python src/cli.py knowledge faq-remove --guild-id 123 --faq-id faq_123_2025-01-15_abc123 --confirm
```

**PDF Management:**
```bash
# List PDFs with extraction status
python src/cli.py knowledge pdf-list --guild-id 123
python src/cli.py knowledge pdf-list  # List default materials

# Add PDF (auto-rebuilds vector store)
python src/cli.py knowledge pdf-add --file path/to/guide.pdf --guild-id 123
python src/cli.py knowledge pdf-add --file guide.pdf --guild-id 123 --no-rebuild  # Skip rebuild

# Remove PDF (auto-rebuilds vector store)
python src/cli.py knowledge pdf-remove --file AAII-Wheel-Strategy.pdf --guild-id 123 --confirm
python src/cli.py knowledge pdf-remove --file guide.pdf --no-rebuild  # Skip rebuild

# Show PDF details (metadata, chunks, embeddings)
python src/cli.py knowledge pdf-info --file AAII-Wheel-Strategy.pdf --guild-id 123
```

**Vector Database:**
```bash
# Quick rebuild from existing chunks
python src/cli.py knowledge rebuild --guild-id 123

# Full rebuild: extract → chunk → embed (replaces manual 3-step process)
python src/cli.py knowledge rebuild-full --guild-id 123
```

**Overview:**
```bash
# List all materials (PDFs, FAQs, vector DB stats)
python src/cli.py knowledge list --guild-id 123
python src/cli.py knowledge list  # Show default materials
```

**Notes:**
- All commands support `--guild-id` for guild-specific materials
- Omit `--guild-id` to work with default materials
- PDF add/remove auto-rebuild by default (use `--no-rebuild` to skip)
- FAQs are guild-specific only (no default FAQs)

## Trade Entry Formats
- Options: `STO 2x MSTU 8/1 8P @ .16`, `BTC 10x TSLL 8/1 10.5P @ .11`
- Shares: `Buy 300 shares MSTU @ 10`
- Dividends: `Dividend QQQI 63.66`
- Deposits: `Deposit 20,000`

## Key Implementation Details

### CSV Import Flow
Auto-detect → parse → delete date range → insert → return stats. 92.5% format detection accuracy.

### Reports & Digests
Markdown → PDF via `util.create_pdf()`. Daily digests: Mon-Thu (24h, top 5), Fri (7d, top 10, leaderboards). LLM temp 1.0.

### Dependencies
`discord.py`, `pandas`, `yfinance`, `litellm`, `matplotlib`, `markdown_pdf`, `playwright`
