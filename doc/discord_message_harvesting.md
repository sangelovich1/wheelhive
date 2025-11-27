# Discord Message Harvesting for LLM Knowledge Base

## Overview
Collect Discord messages from trading channels to build a knowledge base that enhances LLM analysis with community insights, strategies, and discussions.

## Use Cases
- **Community Insights**: "What does the community think about MSTX?"
- **Strategy Learning**: "What wheeling strategies has the community discussed?"
- **Historical Context**: "What were people saying about HOOD before it rallied?"
- **Sentiment Analysis**: "What's the community sentiment on leveraged ETFs?"

## Approach 1: Live Message Collection (Recommended)

### Implementation
```python
# In bot.py - add to on_message handler

# List of channels to harvest (add channel IDs)
HARVEST_CHANNELS = [
    1234567890,  # #trading-discussion
    1234567891,  # #options-strategies
    1234567892,  # #weekly-plays
]

async def on_message(self, message: discord.Message):
    # Don't process bot's own messages
    if message.author == self.user:
        return

    # EXISTING DM HANDLER (keep this)
    if message.guild is None:
        # ... existing DM code ...
        return

    # NEW: Harvest messages from specific channels
    if message.channel.id in HARVEST_CHANNELS:
        await self._harvest_message(message)

async def _harvest_message(self, message: discord.Message):
    """Store message for future LLM context"""
    # Store in database
    db.execute(
        "INSERT INTO community_messages (channel_id, channel_name, user_id, username, message_id, content, timestamp, mentions, attachments) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            message.channel.id,
            message.channel.name,
            message.author.id,
            message.author.name,
            message.id,
            message.content,
            message.created_at.isoformat(),
            ",".join([u.name for u in message.mentions]),
            ",".join([a.url for a in message.attachments])
        )
    )
```

### Database Schema
```sql
CREATE TABLE community_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    channel_name TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    message_id INTEGER UNIQUE NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    mentions TEXT,
    attachments TEXT,
    harvested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_channel_timestamp ON community_messages(channel_id, timestamp);
CREATE INDEX idx_content_search ON community_messages(content);
CREATE INDEX idx_username ON community_messages(username);
```

## Approach 2: Historical Message Fetching

Fetch past messages from channels (one-time or periodic):

```python
async def harvest_channel_history(channel_id: int, limit: int = 1000, after_date=None):
    """
    Fetch historical messages from a channel

    Args:
        channel_id: Discord channel ID
        limit: Max messages to fetch (None = unlimited, can be slow)
        after_date: Only fetch messages after this datetime
    """
    channel = client.get_channel(channel_id)

    if not channel:
        logger.error(f"Channel {channel_id} not found")
        return

    logger.info(f"Harvesting messages from #{channel.name}")

    count = 0
    async for message in channel.history(limit=limit, after=after_date):
        # Skip bot messages
        if message.author.bot:
            continue

        # Store message
        await _harvest_message(message)
        count += 1

        if count % 100 == 0:
            logger.info(f"Harvested {count} messages...")

    logger.info(f"Completed: Harvested {count} messages from #{channel.name}")
```

### CLI Command to Trigger Harvest
```python
# In cmds.py
harvest_parser = subparsers.add_parser("harvest_messages",
    help="Harvest historical messages from Discord channel")
harvest_parser.add_argument("--channel_id", type=int, required=True)
harvest_parser.add_argument("--limit", type=int, default=1000)
harvest_parser.add_argument("--days_back", type=int, default=30)

# Handler
if args.command == "harvest_messages":
    from datetime import datetime, timedelta
    after_date = datetime.now() - timedelta(days=args.days_back)
    asyncio.run(harvest_channel_history(args.channel_id, args.limit, after_date))
```

## Approach 3: Integration with LLM Analysis

### Method 1: RAG (Retrieval-Augmented Generation)

Add relevant community messages to LLM context:

```python
def get_relevant_community_context(query: str, limit: int = 10) -> str:
    """
    Retrieve relevant community messages based on query

    Simple keyword search (can be enhanced with vector embeddings)
    """
    # Extract key terms from query
    terms = extract_key_terms(query)  # e.g., ticker symbols, strategy keywords

    # Search database
    conditions = []
    for term in terms:
        conditions.append(f"content LIKE '%{term}%'")

    where_clause = " OR ".join(conditions)

    results = db.query(
        f"SELECT username, content, timestamp, channel_name FROM community_messages WHERE {where_clause} ORDER BY timestamp DESC LIMIT {limit}"
    )

    # Format for LLM context
    context = "**Relevant Community Discussions:**\n\n"
    for row in results:
        context += f"- [{row['channel_name']}] {row['username']} ({row['timestamp']}): {row['content']}\n"

    return context

# In llm_analyzer.py
def analyze(self, username: str, user_question: str) -> str:
    # Get community context
    community_context = get_relevant_community_context(user_question)

    # Enhance question with context
    enhanced_question = f"{user_question}\n\n{community_context}"

    # Normal analysis flow...
```

### Method 2: MCP Tool for Community Messages

Add a new MCP tool to query community knowledge:

```python
# In mcp_server.py
{
    "name": "search_community_discussions",
    "description": "Search community Discord messages for insights, strategies, and sentiment about symbols, strategies, or topics",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search terms (ticker, strategy, topic)"},
            "channel": {"type": "string", "description": "Optional channel name filter"},
            "days_back": {"type": "integer", "description": "How many days back to search (default: 30)"},
            "limit": {"type": "integer", "description": "Max results (default: 10)"}
        },
        "required": ["query"]
    }
}
```

Then Claude can autonomously search community discussions:
```
User: "!ask What does the community think about MSTX?"

Claude:
1. Calls search_community_discussions({"query": "MSTX", "days_back": 7})
2. Analyzes community sentiment from results
3. Provides summary
```

## Approach 4: Advanced - Vector Embeddings

For semantic search (finds conceptually similar discussions):

```python
# Install: pip install sentence-transformers chromadb

from sentence_transformers import SentenceTransformer
import chromadb

# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize vector database
chroma_client = chromadb.Client()
collection = chroma_client.create_collection("community_messages")

# Store message with embedding
def store_message_with_embedding(message):
    embedding = model.encode(message.content)

    collection.add(
        embeddings=[embedding.tolist()],
        documents=[message.content],
        metadatas=[{
            "username": message.author.name,
            "channel": message.channel.name,
            "timestamp": message.created_at.isoformat()
        }],
        ids=[str(message.id)]
    )

# Search semantically
def search_community_semantic(query: str, n_results: int = 10):
    query_embedding = model.encode(query)

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=n_results
    )

    return results
```

## Privacy & Compliance Considerations

**IMPORTANT:**
1. **Get Permission**: Ask community members for consent to harvest messages
2. **Channel Restrictions**: Only harvest public channels, not private/DMs
3. **Sensitive Data**: Filter out personal info (addresses, account numbers, etc.)
4. **Opt-Out**: Provide mechanism for users to exclude their messages
5. **Data Retention**: Set retention policy (e.g., 90 days)

### Opt-Out Implementation
```python
# Add to database
CREATE TABLE message_harvest_opt_outs (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    opted_out_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# Check before harvesting
def should_harvest_user(user_id: int) -> bool:
    result = db.query(f"SELECT 1 FROM message_harvest_opt_outs WHERE user_id = {user_id}")
    return len(result) == 0  # Harvest if NOT opted out
```

## Recommended Implementation Order

1. **Start Simple**: Add live message collection to 1-2 key channels
2. **Test Storage**: Verify messages are being stored correctly
3. **Add Search**: Implement basic keyword search MCP tool
4. **Integrate with LLM**: Let Claude search community discussions
5. **Enhance**: Add vector embeddings for semantic search
6. **Governance**: Add opt-out mechanism and privacy controls

## Example Usage After Implementation

```
!ask What strategies has the community discussed for wheeling MSTX?

Claude:
1. Calls search_community_discussions({"query": "MSTX wheeling", "days_back": 30})
2. Finds 15 relevant messages from #options-strategies
3. Synthesizes insights:
   "Based on 15 community discussions over the last 30 days:
    - Most users sell puts at 0.30 delta
    - Popular strikes: $8-10 range
    - @trader_joe mentioned good premium at 7-14 DTE
    - Several users rolled down when threatened
    - Community sentiment: Positive on MSTX volatility for premium"
```

Would you like me to implement any of these approaches? I'd recommend starting with Approach 1 (Live Collection) + MCP Tool integration.
