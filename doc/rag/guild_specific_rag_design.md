# Guild-Specific RAG Content Design

## Overview

Enable Discord guild admins to add custom content (FAQs, documents) to their guild-specific AI tutor knowledge base. This allows each community to customize the AI tutor with their own strategies, guidelines, and frequently asked questions.

## Use Cases

1. **Guild-Specific FAQs**: Quick Q&A pairs for common questions unique to the guild
2. **Custom Strategy Documents**: PDFs or markdown files describing guild-specific approaches
3. **Community Guidelines**: Trading rules, risk management policies, watchlist criteria
4. **Member Education**: Onboarding materials, beginner guides customized for the guild

## Architecture

### Storage Strategy

**Hierarchical Collections:**
```
ChromaDB Structure:
├── training_materials (default/global)
│   └── Official training PDFs, universal content
├── training_materials_guild_1234567890
│   └── Guild-specific FAQs, custom docs
├── training_materials_guild_9876543210
│   └── Another guild's custom content
```

**Collection Naming Convention:**
- Default: `training_materials`
- Guild-specific: `training_materials_guild_{guild_id}`

### Document Types

1. **FAQ Entries** (Text-based, no file upload)
   - Question/Answer pairs
   - Stored as single chunk
   - Metadata: `doc_type='faq'`, `question`, `added_by`, `added_date`

2. **PDF Documents**
   - Multi-page documents
   - Chunked using existing pipeline
   - Metadata: `doc_type='pdf'`, `filename`, `added_by`, `added_date`

3. **Markdown Files** (Future)
   - Plain text documentation
   - Chunked by section
   - Metadata: `doc_type='markdown'`, `filename`, `added_by`, `added_date`

### Metadata Schema

```python
{
    'doc_type': 'faq' | 'pdf' | 'markdown',
    'guild_id': str,
    'added_by': str,  # Discord username
    'added_date': str,  # ISO 8601 timestamp
    'source_file': str,  # For PDFs/markdown
    'question': str,  # For FAQs only
    'chunk_id': str,  # Unique identifier for removal
    'section': str,  # Section header (for PDFs)
    'page_number': int,  # For PDFs
    'tokens': int  # Chunk size
}
```

## Retrieval Strategy

### Hierarchical Query Logic

```python
def query(self, question: str, guild_id: Optional[int] = None):
    results = []

    # 1. Query guild-specific content FIRST (if guild_id provided)
    if guild_id:
        guild_results = query_collection(
            f"training_materials_guild_{guild_id}",
            question,
            n_results=3  # Prioritize guild content
        )
        results.extend(guild_results)

    # 2. Query default training materials
    default_results = query_collection(
        "training_materials",
        question,
        n_results=5 - len(results)  # Fill remaining slots
    )
    results.extend(default_results)

    # 3. Return combined, deduplicated results
    return deduplicate_by_similarity(results)
```

### Priority Rules

1. **Guild-specific content takes precedence** - Searched first, appears at top
2. **Default content fills gaps** - Used when guild content doesn't cover topic
3. **Total result limit** - Max 5 chunks total (configurable via `n_results`)
4. **Deduplication** - Remove near-duplicate chunks based on cosine similarity

## Commands

### Discord Bot Commands

#### `/ai_tutor_add_faq`
```
Description: Add a guild-specific FAQ to the AI tutor knowledge base
Permissions: Administrator only
Parameters:
  - question (required): The question users ask
  - answer (required): The answer to provide
  - category (optional): FAQ category (e.g., "strategy", "rules", "watchlist")

Example:
  /ai_tutor_add_faq
    question:"What's our guild's minimum account size?"
    answer:"We recommend starting with $10,000 for the wheel strategy."
    category:"guidelines"
```

#### `/ai_tutor_add_doc`
```
Description: Upload a PDF/markdown document to guild knowledge base
Permissions: Administrator only
Parameters:
  - file (required): PDF or markdown file attachment
  - description (optional): Brief description of document content

Example:
  /ai_tutor_add_doc [attach: guild_strategy_guide.pdf]
    description:"Our guild's comprehensive strategy guide for 2025"
```

#### `/ai_tutor_list_custom`
```
Description: List all guild-specific content in the knowledge base
Permissions: Administrator only
Output:
  - Total custom entries
  - Breakdown by type (FAQs, PDFs, markdown)
  - List with chunk_id, type, title/question, added_by, added_date
```

#### `/ai_tutor_remove_custom`
```
Description: Remove a custom entry from guild knowledge base
Permissions: Administrator only
Parameters:
  - id (required): Chunk ID to remove (from list-custom output)

Example:
  /ai_tutor_remove_custom id:faq_abc123
```

### CLI Commands

```bash
# Add FAQ
python src/cli.py tutor add-faq \
  --guild-id 1234567890 \
  --question "What is our guild's preferred IV threshold?" \
  --answer "We target 30-45% IV for CSP entries." \
  --category "strategy"

# Add document
python src/cli.py tutor add-doc \
  --guild-id 1234567890 \
  --file "docs/guild_faq.pdf" \
  --description "Guild FAQ document"

# List custom content
python src/cli.py tutor list-custom --guild-id 1234567890

# Remove custom content
python src/cli.py tutor remove-custom --guild-id 1234567890 --id faq_abc123

# Export guild content (backup)
python src/cli.py tutor export-custom --guild-id 1234567890 --output guild_content.json

# Import guild content (restore)
python src/cli.py tutor import-custom --guild-id 1234567890 --input guild_content.json
```

## Implementation Plan

### Phase 1: Core Infrastructure
- [ ] Extend `TrainingMaterialsVectorStore` to support guild-specific collections
- [ ] Implement hierarchical query logic (guild → default fallback)
- [ ] Add collection creation/management methods
- [ ] Update `WheelStrategyTutor` to use hierarchical retrieval

### Phase 2: FAQ Support
- [ ] Implement FAQ chunk format (question + answer as single chunk)
- [ ] CLI command: `tutor add-faq`
- [ ] CLI command: `tutor list-custom`
- [ ] CLI command: `tutor remove-custom`
- [ ] Discord command: `/ai_tutor_add_faq` (admin-only)
- [ ] Discord command: `/ai_tutor_list_custom` (admin-only)
- [ ] Discord command: `/ai_tutor_remove_custom` (admin-only)

### Phase 3: Document Upload
- [ ] Implement PDF chunking for guild docs (reuse existing pipeline)
- [ ] CLI command: `tutor add-doc`
- [ ] Discord command: `/ai_tutor_add_doc` with file attachment
- [ ] File validation (size limits, format checking)
- [ ] Storage management (track total guild content size)

### Phase 4: Management Features
- [ ] Export/import guild content (backup/restore)
- [ ] Bulk operations (add multiple FAQs from CSV/JSON)
- [ ] Content versioning (track updates to FAQs)
- [ ] Analytics (which custom content is being retrieved most)

## Technical Considerations

### Permissions
```python
# Discord: Require administrator permission
@client.tree.command(name="ai_tutor_add_faq", guilds=const.DEV_GUILD_IDS)
@app_commands.default_permissions(administrator=True)
async def ai_tutor_add_faq(interaction: discord.Interaction, ...):
    # Only guild admins can add content
```

### Storage Limits
- **Per-guild FAQ limit**: 100 FAQs (prevent abuse)
- **Per-guild document limit**: 50 MB total storage
- **Max chunk size**: 1000 tokens per FAQ answer
- **Admin override**: CLI can bypass limits with `--force` flag

### Deduplication Strategy
```python
def deduplicate_by_similarity(results, threshold=0.95):
    """Remove near-duplicate chunks based on cosine similarity"""
    unique_results = []
    for result in results:
        if not any(similarity(result, existing) > threshold for existing in unique_results):
            unique_results.append(result)
    return unique_results
```

### Error Handling
- **Collection doesn't exist**: Auto-create on first FAQ addition
- **Invalid guild_id**: Reject with error message
- **Malformed FAQ**: Validate question/answer length, format
- **Duplicate FAQ**: Check for similar questions before adding
- **Storage quota exceeded**: Return error with current usage stats

## FAQ Entry Format

### Chunk Structure
```python
{
    'text': f"Q: {question}\n\nA: {answer}",
    'metadata': {
        'doc_type': 'faq',
        'guild_id': '1234567890',
        'question': question,
        'category': 'strategy',
        'added_by': 'admin_username',
        'added_date': '2025-11-07T12:00:00Z',
        'chunk_id': 'faq_abc123',
        'tokens': 150
    }
}
```

### Query Matching
- **Semantic search**: ChromaDB finds FAQs similar to user question
- **Category filtering**: Optional `where={'category': 'strategy'}` filter
- **Recency boost**: Newer FAQs ranked slightly higher (optional)

## Examples

### Example 1: Guild-Specific Watchlist Criteria
```
Admin adds FAQ:
Q: What are our guild's watchlist criteria for wheel stocks?
A: We focus on high-quality stocks with:
   - Market cap > $5B
   - IV rank 30-70%
   - Liquid options (volume > 1000/day)
   - Price $20-200 per share
   - Avoid biotech and meme stocks
   - Prefer dividend payers

User asks: "How do I build a watchlist?"

AI Tutor response uses:
1. Guild FAQ (specific criteria) ← PRIORITY
2. Default training materials (general watchlist guidance)
```

### Example 2: Risk Management Policy
```
Admin uploads PDF: "guild_risk_policy.pdf"
Content:
- Position sizing: Max 5% portfolio per ticker
- Stop loss: 25% on underlying
- Max contracts: 10 per position
- Assignment handling procedures

User asks: "What's our position sizing rule?"

AI Tutor response:
"Based on our guild's risk management policy, the maximum position
size is 5% of your portfolio per ticker, with a limit of 10 contracts
per position. [Source: guild_risk_policy.pdf, page 2]"
```

### Example 3: Beginner Guidance
```
Admin adds multiple FAQs:
1. Q: What's the minimum account size to start?
   A: Our guild recommends $10,000 minimum for wheel strategy.

2. Q: What tickers should beginners start with?
   A: Start with TSLL, QQQI, and ETHU - lower price, high premium.

3. Q: How often should I roll positions?
   A: We recommend rolling at 21 DTE or 50% profit, whichever comes first.

User (new member) asks: "I have $8,000, can I start?"

AI Tutor response:
"Our guild recommends a minimum account size of $10,000 for the wheel
strategy. With $8,000, you might want to focus on the lower-priced tickers
like TSLL, QQQI, and ETHU to maintain proper position sizing. Consider
starting small while you build your account to the recommended level."
```

## Benefits

1. **Customization**: Each guild can tailor AI tutor to their specific strategy
2. **Community Knowledge**: Capture experienced members' insights as FAQs
3. **Onboarding**: New members get guild-specific guidance automatically
4. **Consistency**: Everyone gets the same answers to guild-specific questions
5. **Low Maintenance**: Admins add content once, AI tutor uses it forever
6. **Scalability**: Supports unlimited guilds, each with custom content
7. **Hierarchical Learning**: Guild content supplements (doesn't replace) official training

## Future Enhancements

1. **FAQ Voting**: Members vote on helpful FAQs (surface best content)
2. **Automatic FAQ Suggestions**: Bot detects frequently asked questions
3. **Content Analytics**: Track which custom content is retrieved most
4. **Collaborative Editing**: Multiple admins can manage guild content
5. **Content Approval Workflow**: Moderators review before publishing
6. **Multi-language Support**: Guild-specific content in different languages
7. **Template Libraries**: Pre-made FAQ sets for common guild types
8. **Version Control**: Track changes to FAQs over time, rollback capability
