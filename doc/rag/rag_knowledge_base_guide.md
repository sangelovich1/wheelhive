# RAG Knowledge Base Guide: PDF Recommendations + Analytics

**Created:** 2025-01-08
**Purpose:** Guide for building and optimizing the wheel strategy knowledge base using PDFs and FAQs with analytics tracking.

---

## Table of Contents
1. [PDF Recommendations](#pdf-recommendations)
2. [Analytics System Overview](#analytics-system-overview)
3. [Using the Analytics System](#using-the-analytics-system)
4. [Decision Framework](#decision-framework)
5. [FAQ vs PDF Comparison](#faq-vs-pdf-comparison)

---

## PDF Recommendations

### Foundation Layer PDFs (Download These)

#### 1. **Wheel Strategy Guide**
- **Source:** AAII (American Association of Individual Investors)
- **URL:** https://aaiisandiego.com/wp-content/uploads/2022/02/AAII-Options-Trading-SIG-2-5-22-The-Wheel-Strategy.pdf
- **Best for:** Core wheel strategy mechanics
- **Topics:** Cash-secured puts, covered calls, assignment handling

#### 2. **Options Greeks Explained**
- **Source:** Fidelity - "Option Greeks Demystified"
- **URL:** https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/OptionGreeks_Webinar.pdf
- **Best for:** Understanding delta, theta, gamma, vega
- **Topics:** Practical examples, IV impact, decay calculations

#### 3. **Greeks Reference (Alternative)**
- **Source:** Interactive Brokers - "Understanding FX Option Greeks"
- **URL:** https://www.interactivebrokers.com/download/en/ISE_FX_Greeks_121207.pdf
- **Best for:** More technical/mathematical approach
- **Topics:** Formulas, hedging, delta manufacturing

#### 4. **Options Greeks Cheat Sheet**
- **Source:** OptionsTrading.org
- **URL:** https://www.optionstrading.org/blog/option-greeks-made-simple-cheat-sheet/
- **Best for:** Quick reference guide
- **Topics:** Delta, gamma, theta, vega, rho summaries

### Books to Consider (Amazon/Purchase)

1. **"The Options Wheel Strategy"** by Freeman Publications
   - Complete beginner-friendly guide
   - Covers mechanics, strike selection, risk management
   - ~$15-20 on Amazon
   - Available as PDF companion

2. **"The Wheel Options Trading Strategy"** by Markus Heitkoetter
   - Beginner-focused with high win-rate strategies
   - Systematic approach to consistent income
   - ~$20-25 on Amazon

---

## Analytics System Overview

### What Gets Tracked

Every time a user uses `/ai_assistant`, the system automatically logs:
- ✅ **User:** Who asked the question
- ✅ **Query Text:** What they asked
- ✅ **Sources Retrieved:** Which PDFs/FAQs were retrieved
- ✅ **Relevance Scores:** Embedding distances (lower = more relevant)
- ✅ **Source Rankings:** Position in results (1 = top match)
- ✅ **Guild ID:** Server-specific tracking
- ✅ **Timestamp:** When the query occurred
- ✅ **Query Type:** Ask (question) vs Explain (topic)

### Database Schema

**Tables:**
- `rag_queries` - Each AI Assistant query
- `rag_sources_used` - Which sources were cited for each query

**Indexes:**
- Guild ID, timestamp, source file, doc type for fast querying

---

## Using the Analytics System

### View Overall Statistics

```bash
# Overall stats (last 30 days)
python src/cli.py admin rag-stats

# Guild-specific
python src/cli.py admin rag-stats --guild-id 123456

# Last 7 days
python src/cli.py admin rag-stats --days 7

# FAQ performance only
python src/cli.py admin rag-stats --doc-type faq

# PDF performance only
python src/cli.py admin rag-stats --doc-type pdf
```

### Example Output

```
📊 RAG Knowledge Source Analytics
   Period: Last 30 days

================================================================================
QUERY STATISTICS
================================================================================
Total Queries:        245
Unique Users:         12
Ask Queries:          178
Explain Queries:      67
Avg Results/Query:    3.2

================================================================================
TOP KNOWLEDGE SOURCES
================================================================================
+----+------------------------------------------+-------+-------+------------+----------+------+-------+
|  # | Source File                              | Type  |  Cit. | Avg Dist   | Avg Rank | Best | Users |
+====+==========================================+=======+=======+============+==========+======+=======+
|  1 | AAII-Wheel-Strategy.pdf                  | pdf   |   89  | 0.2145     | 1.3      | 1    | 11    |
|  2 | guild_faq                                | faq   |   45  | 0.1823     | 1.8      | 1    | 8     |
|  3 | Fidelity-Greeks-Demystified.pdf          | pdf   |   42  | 0.2456     | 2.1      | 1    | 9     |
|  4 | Freeman-Wheel-Strategy.pdf               | pdf   |   28  | 0.2891     | 2.5      | 2    | 7     |
+----+------------------------------------------+-------+-------+------------+----------+------+-------+

================================================================================
FAQ vs PDF EFFECTIVENESS
================================================================================
+----------+-----------+--------------+-----------+
| Doc Type | Citations | Avg Distance | Avg Rank  |
+==========+===========+==============+===========+
| pdf      | 159       | 0.2497       | 1.97      |
| faq      | 45        | 0.1823       | 1.80      |
+----------+-----------+--------------+-----------+

📌 Interpretation:
  • Lower distance = more relevant/similar to query
  • Lower rank = appears higher in results (1 = top)
  • More citations = used more frequently

================================================================================
TOP 10 POPULAR TOPICS
================================================================================
+----+--------------------------------------------------------------+-----------+-------+
|  # | Topic/Section                                                | Citations | Users |
+====+==============================================================+===========+=======+
|  1 | Cash-Secured Puts: Mechanics and Risk                        | 34        | 9     |
|  2 | Covered Calls: Strike Selection                              | 28        | 8     |
|  3 | Assignment Risk and Management                               | 22        | 7     |
|  4 | Delta: Understanding Directional Risk                        | 19        | 6     |
+----+--------------------------------------------------------------+-----------+-------+
```

### Understanding the Metrics

**Distance (Lower is Better)**
- Measures semantic similarity between query and source chunk
- Range: 0.0 (perfect match) to 2.0+ (very dissimilar)
- < 0.2 = Excellent match
- 0.2-0.4 = Good match
- > 0.4 = Weak match

**Rank (Lower is Better)**
- Position in retrieval results (1 = top result)
- Avg Rank of 1.5 means typically in top 2 results
- Best Rank shows the highest position ever achieved

**Citations**
- Total number of times this source was retrieved
- High citations = frequently relevant source

---

## Decision Framework

### Week 1-2: Foundation Setup

1. **Download Free PDFs**
   - Download all 4 recommended PDFs above
   - Save to `training_materials/default/pdfs/`

2. **Process Into Vector Store**
   ```bash
   python scripts/rag/extract_pdfs.py
   python scripts/rag/chunk_documents.py
   python scripts/rag/create_vector_store.py
   ```

3. **Enable AI Assistant**
   - `/ai_assistant` available in dev guild
   - `/ai_assistant_add_faq` for user contributions

4. **Initial Testing**
   - Ask test questions to verify retrieval
   - Check that sources are being cited

### Week 3-4: Monitor & Optimize

```bash
# Check analytics weekly
python src/cli.py admin rag-stats --days 7 --guild-id YOUR_GUILD_ID
```

**Look for:**
- ❓ **High citation sources** → Keep, these are valuable
- ❓ **Low citation sources** → May be too generic or off-topic
- ❓ **FAQ vs PDF ratio** → Are users finding answers in FAQs or PDFs?
- ❓ **Popular topics** → What are users asking about most?

### Optimization Signals

| Signal | Action |
|--------|--------|
| FAQs have lower avg_distance than PDFs | FAQs are more targeted - add more! |
| Specific PDF never cited | Consider removing or replacing |
| Same question asked 3+ times | Create targeted FAQ via `/ai_assistant_add_faq` |
| Popular topic has no good sources | Add PDF or FAQ for that topic |
| Users mostly "ask" vs "explain" | Need more Q&A style content (FAQs) |
| Avg distance > 0.4 for top results | Knowledge base has gaps, add content |
| Specific sections highly cited | Consider expanding coverage of those topics |

### Monthly Review Checklist

- [ ] Run `rag-stats` for last 30 days
- [ ] Identify top 5 most cited sources
- [ ] Identify sources with 0 citations (remove?)
- [ ] Check FAQ vs PDF effectiveness ratio
- [ ] Review popular topics vs coverage gaps
- [ ] Add FAQs for recurring questions
- [ ] Consider purchasing additional books if needed

---

## FAQ vs PDF Comparison

### FAQs - Better for:

✅ **Pros:**
1. **Precision targeting** - Each Q&A directly addresses a specific question users actually ask
2. **Community-specific knowledge** - Captures your guild's unique strategies, preferences, and terminology
3. **Rapid iteration** - Easy to add/update based on common questions in Discord
4. **Quality control** - AI validation ensures each entry meets standards
5. **Source attribution** - Users see exactly which FAQ answered their question
6. **Gap filling** - Addresses specific topics missing from general PDFs
7. **Lower barrier to entry** - Any user can contribute via `/ai_assistant_add_faq`

❌ **Cons:**
1. Limited depth - Short Q&A may oversimplify complex topics
2. Fragmented knowledge - Individual entries lack narrative flow
3. Potential inconsistency - Different users may explain concepts differently
4. Maintenance overhead - Many small entries to manage

### PDFs - Better for:

✅ **Pros:**
1. **Comprehensive coverage** - Detailed explanations with examples, diagrams, tables
2. **Structured learning** - Organized chapters build knowledge progressively
3. **Professional quality** - Authoritative sources (textbooks, official guides)
4. **Contextual understanding** - Shows how concepts relate to each other
5. **Edge cases** - Covers nuances and special situations
6. **Consistent terminology** - One author/source = consistent language

❌ **Cons:**
1. Static content - Can't easily update for market changes or new strategies
2. Generic - May not address your community's specific approaches
3. Higher barrier - Requires admin to source, review, and upload PDFs
4. Less targeted - Users may get general answers when they need specific ones
5. No community voice - Lacks the practical wisdom from experienced traders in your guild

### Recommended Hybrid Approach

**Foundation Layer: PDFs (80% coverage)**
- 3-5 high-quality PDFs covering fundamentals
- Provides authoritative "textbook" knowledge

**Precision Layer: FAQs (20% coverage)**
- Community-specific Q&As
- Provides practical "field notes"

**When to Add FAQ:**
- ✅ Same question asked 3+ times in Discord
- ✅ PDF answer exists but users want simpler explanation
- ✅ Community has unique approach not in PDFs
- ✅ Recent market event requires updated context
- ✅ "Gotchas" or common mistakes to warn about

**When to Add PDF:**
- ✅ Entire topic missing from knowledge base
- ✅ Multiple related FAQs could be consolidated
- ✅ Need diagrams, tables, or visual explanations
- ✅ Authoritative source for controversial topic
- ✅ Foundational knowledge all users should have

---

## Implementation Checklist

### Phase 1: Setup (Week 1)
- [ ] Download 4 recommended free PDFs
- [ ] Extract and chunk PDFs: `python scripts/rag/extract_pdfs.py`
- [ ] Create vector store: `python scripts/rag/create_vector_store.py`
- [ ] Test `/ai_assistant` with sample questions
- [ ] Verify analytics are being logged

### Phase 2: Initial Data Collection (Weeks 2-4)
- [ ] Monitor Discord for common questions
- [ ] Encourage `/ai_assistant` usage
- [ ] Add 5-10 initial FAQs via `/ai_assistant_add_faq`
- [ ] Run weekly analytics: `python src/cli.py admin rag-stats --days 7`

### Phase 3: Optimization (Month 2)
- [ ] Review 30-day analytics
- [ ] Identify underperforming sources
- [ ] Add targeted FAQs for recurring questions
- [ ] Consider purchasing Freeman or Heitkoetter books
- [ ] Remove or replace low-citation sources

### Phase 4: Maintenance (Ongoing)
- [ ] Weekly: Quick check of popular topics
- [ ] Monthly: Full `rag-stats` review
- [ ] Quarterly: Comprehensive knowledge base audit
- [ ] As needed: Add FAQs for new questions
- [ ] As needed: Update or add PDFs for new strategies

---

## CLI Commands Reference

### FAQ Management
```bash
# Add FAQ (with validation)
python src/cli.py admin faq-add \
  --guild-id 123456 \
  --question "What is delta?" \
  --answer "Delta measures..."

# List FAQs
python src/cli.py admin faq-list --guild-id 123456

# Remove FAQ
python src/cli.py admin faq-remove \
  --guild-id 123456 \
  --faq-id faq_123456_2025-01-08_abc123
```

### Analytics
```bash
# Overall stats
python src/cli.py admin rag-stats

# Guild-specific
python src/cli.py admin rag-stats --guild-id 123456

# Time period
python src/cli.py admin rag-stats --days 7

# Filter by type
python src/cli.py admin rag-stats --doc-type faq
python src/cli.py admin rag-stats --doc-type pdf
```

### Vector Store Management
```bash
# Create/update vector store
python scripts/rag/extract_pdfs.py
python scripts/rag/chunk_documents.py
python scripts/rag/create_vector_store.py

# Test query
python scripts/rag/test_rag_query.py
```

---

## Discord Commands Reference

### User Commands
- `/ai_assistant` - Ask questions or learn topics (modal interface)
- `/ai_assistant_add_faq` - Contribute FAQ (AI-validated, dev guild only)

### Admin Commands
None currently - all admin functions via CLI for better control

---

## Files Created for This System

### Core Analytics
- `src/rag_analytics.py` - Analytics tracking and reporting
- `src/faq_manager.py` - FAQ CRUD operations with validation
- `src/admin_faq_modal.py` - Discord modal for FAQ submission
- `src/ai_assistant_modal.py` - Discord modal for AI queries (with analytics)

### CLI Commands
- `src/cli/admin.py` - Added: `faq-add`, `faq-list`, `faq-remove`, `rag-stats`

### Database Schema
- `rag_queries` table - Query tracking
- `rag_sources_used` table - Source citation tracking

---

## Success Metrics

### After 1 Week
- ✅ 10+ AI Assistant queries logged
- ✅ Top 3 sources identified
- ✅ At least 5 FAQs added

### After 1 Month
- ✅ 100+ queries logged
- ✅ Clear FAQ vs PDF effectiveness data
- ✅ Popular topics identified
- ✅ Knowledge base gaps identified
- ✅ 10-20 high-quality FAQs

### After 3 Months
- ✅ 500+ queries logged
- ✅ Optimized source mix (PDF + FAQ)
- ✅ <0.3 avg distance on top sources
- ✅ Active user contributions via `/ai_assistant_add_faq`
- ✅ Quarterly review process established

---

## Troubleshooting

### No Analytics Data
**Symptom:** `rag-stats` shows 0 queries
**Solution:**
1. Verify `/ai_assistant` command is being used
2. Check database file exists: `trades.db`
3. Check for errors in bot logs: `grep "RAG analytics" bot.log`

### Low Citation Counts
**Symptom:** All sources have very few citations
**Solution:**
1. Users may not be using `/ai_assistant` - promote it!
2. Check if vector store exists: `ls training_materials/*/vector_db/`
3. Verify PDFs were processed: `python scripts/rag/test_rag_query.py`

### High Distance Scores (>0.5)
**Symptom:** All sources have high avg_distance
**Solution:**
1. Knowledge base may have gaps - add more targeted content
2. Questions may be too specific - add FAQs
3. PDFs may be too general - find more specific resources

### FAQs Not Showing Up
**Symptom:** FAQ doc_type doesn't appear in stats
**Solution:**
1. Check FAQs were added: `python src/cli.py admin faq-list --guild-id XXX`
2. Verify guild-specific vector store exists: `ls training_materials/GUILD_ID/`
3. Ensure users are querying from correct guild

---

## Additional Resources

### Learning More About RAG
- ChromaDB Documentation: https://docs.trychroma.com/
- Vector Embeddings Explained: https://www.pinecone.io/learn/vector-embeddings/

### Options Trading Resources
- Option Alpha: https://optionalpha.com/
- TastyTrade: https://www.tastytrade.com/
- CBOE Options Institute: https://www.cboe.com/education/

---

**Last Updated:** 2025-01-08
**Maintainer:** See CLAUDE.md for development guidelines
