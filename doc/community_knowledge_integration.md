# Leveraging Discord Community Knowledge for LLM Analysis

**Date:** 2025-10-18 (Proposal) / 2025-10-19 (Implementation Complete)
**Status:** ✅ IMPLEMENTED - Community Sentiment Analysis Live!

---

## 🎉 Implementation Summary (Oct 19, 2025)

**What was built:** A hybrid approach combining message harvesting, ticker extraction, and LLM-powered sentiment analysis.

### Features Delivered

1. **Real-time Message Harvesting** ✅
   - Bot monitors `stock-options` and `stock-chat` channels
   - Automatically extracts and validates ticker symbols
   - Stores messages in SQLite with JSON backup
   - **Current stats:** 1,391 messages harvested (Oct 12-19)

2. **Hybrid Ticker Validation** ✅
   - Blacklist filtering (removes false positives like "PUT", "CALL", months, etc.)
   - Database lookup (S&P 500 + DOW + 55 curated community tickers)
   - Real-time API validation via yfinance
   - Auto-discovery: 104 new tickers added automatically
   - **Current stats:** 662 total tickers in database

3. **AI-Powered Sentiment Analysis** ✅
   - New command: `!sentiment <ticker>` (via DM to bot)
   - CLI: `python src/cmds.py community_sentiment --ticker MSTX`
   - Analyzes: sentiment, strategies, strikes, risks, price targets, insights
   - **Provider:** Claude Haiku (cost-efficient, fast)

### Usage Examples

**Discord DM:**
```
!sentiment MSTX
```

**Command Line:**
```bash
python src/cmds.py community_sentiment --ticker MSTX --limit 50
```

**Response includes:**
- Overall sentiment (bullish/bearish/neutral)
- Common trading strategies (puts/calls/wheeling)
- Key strike prices and expirations mentioned
- Risk concerns from community
- Price targets and expectations
- Notable insights and warnings
- Activity level

### What's Next

- Consider adding RAG (vector search) for semantic queries
- Weekly sentiment summaries
- Trending sentiment over time
- User contribution system (`/contribute_insight`)

---

## Problem Statement

The Discord trading bot community has many talented and seasoned options traders. A chat channel contains valuable insights, patterns, and warnings that flow organically. How can this information be leveraged by the LLM to provide better analysis and recommendations?

## Proposed Solutions

### Option 1: Discord Message Logging + RAG (Recommended for Scale)

**Description:** Log messages from trading channel, convert to vector embeddings, store in vector database for semantic search.

**How it works:**
1. Log messages from trading channel to database
2. Use embeddings to convert messages to vectors
3. Store in vector database (ChromaDB, Pinecone, Qdrant)
4. LLM searches for relevant past discussions when analyzing trades

**Example Use Case:**
- User asks: "Should I roll my MSTX covered calls?"
- LLM retrieves similar discussions from channel history
- Finds: "Last month traders discussed MSTX, consensus was to hold through earnings"
- Provides recommendation based on both your data AND community wisdom

**Pros:**
- ✅ Captures organic, real-time insights
- ✅ Finds relevant context even without exact keyword matches
- ✅ Builds knowledge over time

**Cons:**
- ⚠️ Privacy concerns (need consent from community)
- ⚠️ Requires embedding model (OpenAI, local Sentence Transformers)
- ⚠️ Some noise/irrelevant messages

**Implementation Sketch:**
```python
# New Discord bot listener
@client.event
async def on_message(message):
    if message.channel.name == "trading-chat":
        await store_message_with_embedding(
            content=message.content,
            author=message.author.name,  # or anonymized
            timestamp=message.created_at,
            symbol=extract_symbols(message.content)
        )

# New MCP tool
def search_community_discussions(query: str, symbol: Optional[str] = None):
    """Search past trading discussions for relevant insights"""
    results = vector_db.search(query, filters={"symbol": symbol})
    return summarize_discussions(results)
```

---

### Option 2: Structured Community Knowledge Base (Best Starting Point)

**Description:** Create Discord command for traders to share curated insights in structured format.

**How it works:**
1. Create `/contribute_insight` Discord command
2. Store in structured format with categories/tags
3. LLM queries this curated knowledge base

**Example Insights:**
- "HOOD: IV crush after earnings is severe, avoid holding through"
- "MSTX: Tends to gap up on low volume, use wider strikes"
- "Wheel strategy: Works best on stocks with >30% IV"

**Pros:**
- ✅ High signal-to-noise ratio
- ✅ Structured and searchable
- ✅ No privacy concerns (opt-in contributions)
- ✅ Easy to implement

**Cons:**
- ⚠️ Requires active participation
- ⚠️ Might miss insights shared in casual chat

**Implementation Sketch:**
```python
# Discord command
@client.tree.command(name="contribute_insight")
async def contribute_insight(
    interaction: discord.Interaction,
    symbol: str,
    insight_type: Literal["pattern", "warning", "strategy", "earnings"],
    description: str
):
    knowledge_db.insert({
        "symbol": symbol,
        "type": insight_type,
        "insight": description,
        "contributor": interaction.user.name,
        "date": datetime.now(),
        "upvotes": 0
    })

# MCP tool
def get_community_insights(symbol: str, insight_type: Optional[str] = None):
    """Get curated insights from experienced traders"""
    return knowledge_db.query(symbol=symbol, type=insight_type)
```

**Database Schema:**
```sql
CREATE TABLE community_insights (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    insight_type TEXT CHECK(insight_type IN ('pattern', 'warning', 'strategy', 'earnings')),
    insight TEXT NOT NULL,
    contributor TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1
);
```

---

### Option 3: Weekly Discussion Summaries

**Description:** LLM reads channel messages and generates weekly summaries of key discussions.

**How it works:**
1. LLM reads channel messages daily/weekly
2. Generates summaries of key discussions
3. Stores summaries with topics and symbols mentioned
4. Future queries search these summaries

**Pros:**
- ✅ Condensed, relevant information
- ✅ Less storage than full message history
- ✅ Easy to read for LLM

**Cons:**
- ⚠️ Loses granular details
- ⚠️ Summarization quality depends on LLM

---

### Option 4: Real-Time Sentiment Analysis

**Description:** Monitor trading channel for symbol mentions and extract sentiment.

**How it works:**
1. Monitor trading channel for symbol mentions
2. Extract sentiment (bullish/bearish) and reasoning
3. Aggregate into sentiment scores with explanations
4. LLM uses this for context

**Pros:**
- ✅ Real-time community pulse
- ✅ Easy to understand (bullish/bearish counts)
- ✅ Identifies changing sentiment

**Cons:**
- ⚠️ Sentiment analysis can be inaccurate
- ⚠️ Doesn't capture nuanced strategies

---

### Option 5: Hybrid Approach (Long-term Goal)

**Description:** Combine multiple approaches for best results.

**Components:**
1. Structured knowledge base (curated insights)
2. RAG search (semantic search of all messages)
3. Real-time sentiment tracking
4. Weekly summaries

**MCP Tools to Add:**
```python
1. search_community_knowledge(query, symbol) → RAG search
2. get_community_insights(symbol, type) → Structured insights
3. get_community_sentiment(symbol) → Real-time sentiment
4. get_weekly_summary(symbol, weeks) → Digest of discussions
```

---

## Privacy & Consent Considerations

**CRITICAL REQUIREMENTS:**
- ✅ Get explicit opt-in from community members
- ✅ Anonymize or hash usernames
- ✅ Allow users to opt-out retroactively
- ✅ Don't share outside the community
- ✅ Consider a `/privacy` command showing what's stored
- ✅ Comply with Discord TOS regarding message logging

---

## Recommended Implementation Path

**Phase 1: Structured Knowledge Base** (Immediate)
1. Add `/contribute_insight` Discord command
2. Create `community_insights` database table
3. Add MCP tool: `get_community_insights(symbol, type)`
4. Add Discord command: `/search_insights` for community members

**Phase 2: Sentiment Tracking** (Next)
1. Add basic sentiment analysis on symbol mentions
2. Track bullish/bearish counts per symbol
3. Add MCP tool: `get_community_sentiment(symbol)`

**Phase 3: RAG Implementation** (Future)
1. Implement vector database (ChromaDB or Qdrant)
2. Store message embeddings
3. Add semantic search capability
4. Add MCP tool: `search_community_discussions(query, symbol)`

**Phase 4: Summaries** (Advanced)
1. Implement weekly summary generation
2. Store and index summaries
3. Add MCP tool: `get_weekly_summary(symbol, weeks)`

---

## Example Use Cases

### Use Case 1: Pre-Trade Analysis
**User:** "Should I sell MSTX covered calls?"

**LLM Response (with community knowledge):**
```
Based on your position (900 shares @ $22.42) and community insights:

YOUR DATA:
- Current price: $16.42 (-27% from your cost basis)
- You've been running $18 strikes successfully (10 cycles, $88 net premium)

COMMUNITY INSIGHTS:
- Warning from @experienced_trader (2 weeks ago): "MSTX tends to gap up on
  low volume - use wider strikes or avoid weekly options"
- Pattern from @wheelmaster (1 month ago): "MSTX has shown 15%+ moves
  around earnings - consider 30-45 DTE instead of weeklies"

RECOMMENDATION:
Given the -27% unrealized loss and community warnings about volatility,
consider 30-45 DTE calls at $20 strike instead of your usual $18 weeklies.
This gives more recovery room if MSTX gaps up.
```

### Use Case 2: Risk Warning
**User:** "What are my HOOD positions?"

**LLM Response (with community knowledge):**
```
CURRENT POSITIONS:
- 500 shares HOOD @ $32.40 avg
- 5x $35C expiring in 7 days

COMMUNITY WARNING:
- Alert from @optionspro (yesterday): "HOOD earnings in 10 days - IV crush
  historically severe, avoid holding through earnings"
- Strategy from @thetagang (last week): "Close HOOD calls before earnings,
  reopen after IV crush for better premium"

RECOMMENDATION:
Close your $35C positions before earnings (in 10 days) to avoid IV crush.
```

---

## Technical Architecture

```
┌─────────────────────┐
│  Discord Channel    │
│  (Trading Chat)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Discord Bot Event Handlers             │
│  - on_message (RAG indexing)            │
│  - /contribute_insight (structured)     │
│  - Sentiment analysis                   │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Storage Layer                          │
│  ┌───────────────────────────────────┐  │
│  │ SQLite: community_insights        │  │
│  │ - Curated insights                │  │
│  │ - Sentiment scores                │  │
│  │ - Weekly summaries                │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ Vector DB: ChromaDB/Qdrant        │  │
│  │ - Message embeddings              │  │
│  │ - Semantic search                 │  │
│  └───────────────────────────────────┘  │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  MCP Server Tools                       │
│  - get_community_insights()             │
│  - search_community_discussions()       │
│  - get_community_sentiment()            │
│  - get_weekly_summary()                 │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│  LLM (via Open      │
│  WebUI or Claude)   │
│  - Combines your    │
│    trading data     │
│  - With community   │
│    knowledge        │
└─────────────────────┘
```

---

## Next Steps When Ready to Implement

1. Review this document with community leadership
2. Get consensus on privacy approach
3. Start with Phase 1 (Structured Knowledge Base)
4. Iterate based on community feedback
5. Gradually add more sophisticated features

---

## References

- WheelHive codebase: `src/`
- Discord bot: `src/bot.py`
- MCP server: `src/mcp/mcp_server.py`
- Database: `trades.db`

## Related Considerations

- Community moderation of insights (upvote/downvote system)
- Gamification (reputation points for quality contributions)
- Integration with existing `/my_trades`, `/report` commands
- Mobile-friendly interface for contributing insights
- Weekly leaderboard of top contributors
