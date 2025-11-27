# AI Assistant Configuration

**Date:** 2025-11-08
**Purpose:** Configuration and access control for `/ai_assistant` command

---

## Command Access

### **Current Configuration:**

| Command | Availability | Access Control |
|---------|--------------|----------------|
| `/ai_assistant` | All guilds (production) | Author only (`sangelovich`) |
| `/ai_assistant_faq add` | All guilds (production) | Author only (will become admin-only) |
| `/ai_assistant_faq list` | All guilds (production) | Author only (will become admin-only) |
| `/ai_assistant_faq rm` | All guilds (production) | Author only (will become admin-only) |

### **Access Logic:**

```python
# Check decorator restricts to author
async def is_author(interaction: discord.Interaction) -> bool:
    return interaction.user.name == const.AUTHOR

@app_commands.check(is_author)
async def ai_assistant(interaction: discord.Interaction):
    # Only visible/usable by author
```

**Why Author-Only (Current Phase):**
- Testing phase for production rollout
- Monitors RAG retrieval quality before wider release
- Controls API costs (Claude Sonnet 4.5 usage)
- Allows testing with real guild content

**Production Plan (FAQ Commands):**
Replace `@app_commands.check(is_author)` with `@app_commands.default_permissions(administrator=True)` to enable guild admins to manage FAQ content

---

## Model Configuration

### **System Setting:**

**Key:** `llm.ai_tutor_model`
**Default Value:** `claude-sonnet-4-5-20250929`
**Category:** `llm`
**Description:** Model for AI tutor/assistant RAG queries

### **Viewing/Changing Model:**

```bash
# View current setting
python src/cli.py admin settings-get --key llm.ai_tutor_model

# Change model
python src/cli.py admin settings-set \
  --key llm.ai_tutor_model \
  --value claude-sonnet-4-5-20250929 \
  --category llm \
  --description "Model for AI tutor/assistant RAG queries"
```

### **Available Models:**

| Model | Use Case | Cost | Speed |
|-------|----------|------|-------|
| `claude-sonnet-4-5-20250929` | Production (default) | Medium | Fast |
| `claude-opus` | Highest quality | High | Slower |
| `claude-haiku` | Fast testing | Low | Very fast |
| `ollama/qwen2.5-coder:7b` | Local/free | Free | Fast (local) |

---

## Usage Flow

### **User Experience:**

1. User types `/ai_assistant` in Discord
2. **Access check:**
   - If user ≠ `sangelovich` → Error message (ephemeral)
   - If user = `sangelovich` → Modal appears
3. Modal prompts for:
   - **Query:** Question or topic (required)
   - **Context:** Additional details (optional)
4. Bot determines query type:
   - **Question** (has `?` or starts with how/what/etc.) → `tutor.ask()`
   - **Topic** (no question words) → `tutor.explain_topic()`
5. RAG retrieval:
   - Queries guild-specific vector DB first
   - Falls back to default DB if needed
   - Returns top 3-5 chunks
6. Response generated with:
   - AI-generated answer
   - Source citations (PDF name, page number)
   - Analytics logged for future optimization

---

## Analytics Integration

Every query is logged to track effectiveness:

**Tables:**
- `rag_queries` - Query metadata
- `rag_sources_used` - Which PDFs/FAQs were retrieved

**View Analytics:**
```bash
# Overall stats (last 30 days)
python src/cli.py admin rag-stats

# Guild-specific
python src/cli.py admin rag-stats --guild-id 1405962109262757980

# Last 7 days
python src/cli.py admin rag-stats --days 7
```

---

## Guild-Specific Content

### **How Cascading Works:**

1. **Query:** "What does BTO mean?"
2. **Step 1:** Check guild-specific vector DB
   - Income Executive: Retrieves from Terminology.png (Distance: 1.35)
   - Sangelovich Dev: Retrieves from Greeks PDFs (Distance: varies)
3. **Step 2:** If insufficient results, query default DB
   - Default: AAII-Wheel-Strategy.pdf + Fidelity-Options-Greeks-Demystified.pdf
4. **Return:** Combined results, guild content prioritized

### **Current Guild Content:**

| Guild ID | Content | Chunks | Focus |
|----------|---------|--------|-------|
| **1405962109262757980** (Income Executive) | 4 custom PDFs | 23 | Wheel strategy, Terminology |
| **1349592236375019520** (Sangelovich Dev) | 4 Greeks PDFs | 127 | Greeks (all 4 PDFs) |
| **Default (fallback)** | 2 core PDFs | 24 | Wheel + Greeks basics |

---

## FAQ Management Commands

### **Command Group: `/ai_assistant_faq`**

Server admins can manage FAQ knowledge base content via Discord (no CLI access needed).

#### **`/ai_assistant_faq add`**
- Opens modal for question and answer input
- AI validates FAQ quality before adding
- Stores to guild-specific vector database
- Available via RAG retrieval in `/ai_assistant`

**Usage:**
1. Type `/ai_assistant_faq add`
2. Fill in question and answer in modal
3. Submit for AI validation
4. FAQ added to guild knowledge base

#### **`/ai_assistant_faq list`**
- Lists all FAQs for current guild
- Shows question, answer preview, metadata
- Includes FAQ ID for removal
- Auto-paginates if >2000 chars

**Example Output:**
```
📋 FAQ Knowledge Base (3 entries)

1. What does BTO mean?
   Buy To Open - Opens a long position...
   Added by sangelovich on 2025-11-08
   ID: faq_bto_definition

2. How do I roll a covered call?
   To roll a covered call, you BTC the...
   Added by admin on 2025-11-08
   ID: faq_roll_cc
```

#### **`/ai_assistant_faq rm`**
- Removes FAQ from guild knowledge base
- Requires FAQ ID (use `/ai_assistant_faq list` to find)
- Permanent deletion from vector store

**Usage:**
```
/ai_assistant_faq rm faq_id: faq_bto_definition
```

### **Current Access (Testing Phase):**
- All commands restricted to author (`sangelovich`)
- Available in all 3 production guilds
- Commands visible only to author via `@app_commands.check(is_author)`

### **Production Migration (Future):**

To enable guild admins to manage FAQs, replace in `src/bot.py`:

**Before (Author-only):**
```python
@faq_group.command(name="add", description="Add FAQ...")
@app_commands.guild_only()
@app_commands.check(is_author)
async def faq_add(interaction: discord.Interaction):
```

**After (Admin-only):**
```python
@faq_group.command(name="add", description="Add FAQ...")
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
async def faq_add(interaction: discord.Interaction):
```

Apply same change to `faq_list` and `faq_rm` commands.

---

## Expanding Access

### **Option 1: Specific Users**

Add users to an allow list:

```python
# In constants.py
AI_ASSISTANT_ALLOWED_USERS = ['sangelovich', 'darkminer', 'another_user']

# In bot.py
if interaction.user.name not in const.AI_ASSISTANT_ALLOWED_USERS:
    await interaction.response.send_message(
        "❌ This command is currently restricted.",
        ephemeral=True
    )
    return
```

### **Option 2: Specific Guild**

Limit to Income Executive guild:

```python
# In bot.py
ALLOWED_GUILD_ID = 1405962109262757980  # Income Executive

if not interaction.guild or interaction.guild.id != ALLOWED_GUILD_ID:
    await interaction.response.send_message(
        "❌ This command is only available in the Income Executive guild.",
        ephemeral=True
    )
    return
```

### **Option 3: Role-Based**

Require specific Discord role:

```python
# In bot.py
REQUIRED_ROLE_NAME = "Premium Member"

if not any(role.name == REQUIRED_ROLE_NAME for role in interaction.user.roles):
    await interaction.response.send_message(
        "❌ This command requires the 'Premium Member' role.",
        ephemeral=True
    )
    return
```

### **Option 4: Public Access**

Remove all restrictions:

```python
# In bot.py - just remove the access check
async def ai_assistant(interaction: discord.Interaction):
    """Open AI Assistant modal for RAG-enhanced learning and Q&A"""
    log_command(interaction, "ai_assistant")

    # Create and configure modal (no access check)
    modal = AIAssistantModal()
    modal.set_guild_id(interaction.guild.id if interaction.guild else None)

    # Send modal to user
    await interaction.response.send_modal(modal)
```

---

## Cost Considerations

### **Claude Sonnet 4.5 Pricing (Anthropic):**
- Input: $3 per million tokens
- Output: $15 per million tokens

### **Typical Query Costs:**

**Query Type:** "What does BTO mean?"
- RAG retrieval: 3 chunks × 500 tokens = 1,500 tokens
- System prompt + context: ~2,000 tokens
- User query: ~20 tokens
- **Total input:** ~3,520 tokens = **$0.011 per query**
- **Response:** ~200 tokens = **$0.003 per query**
- **Total cost:** ~**$0.014 per query**

**Monthly estimates:**
- 10 queries/day × 30 days = 300 queries
- 300 × $0.014 = **$4.20/month**
- 100 queries/day × 30 days = 3,000 queries
- 3,000 × $0.014 = **$42/month**

### **Cost Mitigation:**

1. **Use cheaper model for simple queries:**
   - Claude Haiku: ~5x cheaper
   - Ollama (local): Free

2. **Limit query frequency:**
   - Rate limiting: 5 queries per user per hour
   - Cooldown: 30 seconds between queries

3. **Cache common queries:**
   - Store frequent Q&As as FAQs
   - Direct FAQ lookup before LLM call

---

## Troubleshooting

### **Error: "Setting not found: llm.ai_tutor_model"**

**Solution:**
```bash
python src/cli.py admin settings-set \
  --key llm.ai_tutor_model \
  --value claude-sonnet-4-5-20250929 \
  --category llm
```

### **Error: "Vector store not initialized"**

**Solution:**
```bash
# Create default vector store
python scripts/rag/extract_pdfs.py \
  --input-dir training_materials/default/pdfs \
  --output-dir training_materials/default/raw

python scripts/rag/chunk_documents.py \
  --input-dir training_materials/default/raw \
  --output training_materials/default/chunks.json

python scripts/rag/create_vector_store.py \
  --chunks training_materials/default/chunks.json
```

### **Error: "Command not available"**

**Reason:** User is not `sangelovich`
**Solution:** Either update access control or use author account

---

## Future Enhancements

### **Planned Features:**

1. **Query caching** - Store common Q&As to reduce API calls
2. **User feedback** - Thumbs up/down on responses
3. **Source quality scoring** - Track which PDFs/FAQs are most helpful
4. **Conversation history** - Multi-turn conversations with context
5. **Suggested follow-ups** - Related questions to explore

### **Content Improvements:**

1. **More FAQs** - User-contributed via `/ai_assistant_add_faq`
2. **Better PDFs** - Find openly licensed wheel strategy materials
3. **Video transcripts** - Extract content from YouTube tutorials
4. **Community Q&A** - Incorporate Discord message history

---

## See Also

- `doc/rag_knowledge_base_guide.md` - Complete RAG system guide
- `doc/rag_pdf_loading_guide.md` - How to add PDFs to knowledge base
- `doc/research/greeks_pdf_analysis.md` - PDF quality analysis
- `doc/research/income_executive_guild_content.md` - Guild content review
