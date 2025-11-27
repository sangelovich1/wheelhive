# Admin Commands Reference

**Complete guide to WheelHive administrator commands**

---

## Overview

All admin commands require **Administrator** permission in your Discord server. Commands are accessed via Discord slash commands (type `/` to see available commands).

**Available Command Categories:**
- 📋 **Channel Management** - Configure which channels to monitor
- 💡 **FAQ Management** - Manage AI assistant knowledge base

---

## Channel Management Commands

Control which Discord channels the bot monitors for trading discussions and news.

### `/channels_list`

**List all configured analyzed channels**

Shows which channels are currently being monitored, organized by category.

**Usage:**
```
/channels_list
```

**Example Output:**
```
📋 Configured Analysis Channels
Currently monitoring 4 channel(s) in this server

💬 Community Channels
• #stock-options (stock-options)
• #stock-chat (stock-chat)
• #darkminer-moves (darkminer-moves)

📰 News Channels
• #news (news)
```

**Features:**
- Clean embed format
- Channel mentions are clickable
- Shows count by category
- Ephemeral (private response)

---

### `/channels_add`

**Add a channel for message analysis**

Configure the bot to monitor a specific channel.

**Parameters:**
- `channel` (required): Select from dropdown
- `category` (required): Choose type
  - `community`: Trading discussions, strategy talk
  - `news`: Market news, stock news, earnings reports (provides AI context)

**Usage:**
```
/channels_add channel:#trading-chat category:community
/channels_add channel:#announcements category:news
```

**Validation:**
- Bot checks if it can read the channel
- Warns if missing message history permission
- Prevents duplicate configurations

**Example Output:**
```
✅ Channel Added
Now analyzing messages from #trading-chat

Channel: #trading-chat
Category: 💬 Community
Guild ID: 850508033041760256
```

---

### `/channels_remove`

**Remove a channel from analysis**

Stop monitoring a specific channel.

**Parameters:**
- `channel` (required): Select channel to remove

**Usage:**
```
/channels_remove channel:#old-channel
```

**Example Output:**
```
✅ Channel Removed
No longer analyzing messages from #old-channel

Channel: #old-channel
Guild ID: 850508033041760256
```

---

## FAQ Management Commands

Manage the AI assistant's guild-specific knowledge base.

### `/faq_list`

**List all FAQs in knowledge base**

Shows all FAQs currently available to the AI assistant for your server.

**Usage:**
```
/faq_list
```

**Example Output:**
```
📋 FAQ Knowledge Base
Currently tracking 3 FAQ(s) for this server

1. What is the wheel strategy?
   A: The wheel strategy is a systematic options trading...
   Added by @admin
   ID: `faq_850508033041760256_2025-11-12T10:30:00_a1b2c3d4`

2. When should I roll my puts?
   A: Roll your puts when they reach 50% profit or...
   Added by @moderator
   ID: `faq_850508033041760256_2025-11-12T11:45:00_e5f6g7h8`
```

**Features:**
- Shows up to 25 FAQs per response
- Displays question, answer preview, author
- Includes FAQ ID for removal
- Rich embed format

---

### `/faq_add`

**Add FAQ to knowledge base**

Opens a modal form to add a new FAQ entry with AI validation.

**Usage:**
```
/faq_add
```

**What happens:**
1. Modal form appears with two fields:
   - Question (200 chars max)
   - Answer (2000 chars max)
2. You fill in the form and submit
3. AI validates quality (must score ≥0.7)
4. If valid, added to vector database
5. Immediately available to AI assistant

**Validation Criteria:**
- Question clarity and specificity
- Answer accuracy and completeness
- Relevance to wheel strategy/options trading
- Language clarity
- No misleading information

**Success Response:**
```
✅ FAQ Added Successfully (Quality Score: 85%)

Question: What is the wheel strategy?
Answer Preview: The wheel strategy is a systematic approach...
Added by: admin

💡 Tips for Future FAQs:
• Consider adding a practical example
• Link to related concepts

Your FAQ is now available to the AI Assistant!
```

**Rejection Response:**
```
❌ FAQ Validation Failed (Quality Score: 45%)

Issues Found:
• Question is too vague
• Answer lacks specific guidance
• Missing relevance to wheel strategy

Suggestions:
• Be more specific in the question
• Provide actionable advice in the answer

Reasoning: The FAQ needs more focus on practical application

Please revise and try again.
```

---

### `/faq_remove`

**Remove FAQ from knowledge base**

Delete a specific FAQ by its ID.

**Parameters:**
- `faq_id` (required): The FAQ ID (get from `/faq_list`)

**Usage:**
```
/faq_remove faq_id:faq_850508033041760256_2025-11-12T10:30:00_a1b2c3d4
```

**Example Output:**
```
✅ FAQ Removed
Successfully removed FAQ from knowledge base

FAQ ID: `faq_850508033041760256_2025-11-12T10:30:00_a1b2c3d4`

Use /faq_list to see remaining FAQs
```

---

## Command Comparison Table

| Command | Purpose | Parameters | Permission |
|---------|---------|------------|------------|
| `/channels_list` | View configured channels | None | Administrator |
| `/channels_add` | Add monitoring channel | channel, category | Administrator |
| `/channels_remove` | Stop monitoring channel | channel | Administrator |
| `/faq_list` | View all FAQs | None | Administrator |
| `/faq_add` | Create new FAQ | None (modal) | Administrator |
| `/faq_remove` | Delete FAQ | faq_id | Administrator |

---

## Quick Start Workflows

### First-Time Server Setup

```bash
# Step 1: Configure channels
/channels_add channel:#trading-chat category:community
/channels_add channel:#news category:news

# Step 2: Verify configuration
/channels_list

# Step 3: Add initial FAQs
/faq_add
# (Fill in modal with server-specific Q&A)

# Step 4: Check FAQ database
/faq_list
```

**Time:** ~5 minutes

---

### Add Server-Specific FAQ

```bash
# Step 1: Open FAQ form
/faq_add

# Step 2: Fill in details
Question: What are our server's position sizing rules?
Answer: We recommend starting with 1% of account value per trade...

# Step 3: Submit for validation
# AI validates and either approves or suggests improvements

# Step 4: Verify it was added
/faq_list
```

**Time:** ~2 minutes

---

### Clean Up Old Channels

```bash
# Step 1: Review current channels
/channels_list

# Step 2: Remove inactive channels
/channels_remove channel:#old-trades
/channels_remove channel:#archived-chat

# Step 3: Confirm removal
/channels_list
```

**Time:** ~1 minute

---

## Permissions Required

### For Administrators

**Discord Role Permission:**
- ✅ Administrator

**What You Can Do:**
- Configure analyzed channels
- Add/remove FAQs
- View all admin commands

---

### For Bot

**Required Permissions (per channel):**
- ✅ Read Messages
- ✅ Read Message History

**To Grant:**
1. Right-click channel → Edit Channel
2. Permissions tab → Add @WheelHive
3. Enable both permissions above

---

## Troubleshooting

### "You need Administrator permissions"

**Cause:** Your Discord role doesn't have admin rights

**Solution:**
```
Server Settings → Roles → [Your Role] → Enable "Administrator"
```

---

### "I don't have permission to read that channel"

**Cause:** Bot lacks channel permissions

**Solution:**
```
1. Right-click channel → Edit Channel
2. Permissions → Add @WheelHive role
3. Enable: Read Messages + Read Message History
4. Try /channels_add again
```

---

###  "FAQ Validation Failed"

**Cause:** FAQ quality score below 70%

**Solutions:**
- Make question more specific
- Provide complete, accurate answer
- Ensure relevance to wheel strategy
- Use clear, unambiguous language
- Add practical examples

**Example Improvements:**

❌ **Bad FAQ:**
```
Q: What is delta?
A: It's an option thing.
```

✅ **Good FAQ:**
```
Q: How should I use delta when selecting strikes for the wheel strategy?
A: For cash-secured puts in the wheel strategy, target strikes with
   0.30-0.40 delta (30-40% probability of assignment). This provides
   a good balance between premium income and assignment risk. For
   covered calls, use 0.20-0.30 delta strikes to reduce early
   assignment while collecting meaningful premium.
```

---

### Commands Not Showing Up

**Cause 1:** No Administrator permission
- Solution: Ask server owner to grant admin role

**Cause 2:** Bot not synced
- Solution: Wait 1-2 minutes after bot restart
- Check bot is online (green status)

**Cause 3:** Wrong server
- Solution: Ensure you're in a server (not DMs)

---

## Best Practices

### Channel Management

**DO:**
- ✅ Regular review (monthly /channels_list)
- ✅ Configure permissions before adding
- ✅ Use "community" for discussions
- ✅ Use "news" for announcements only
- ✅ Test after configuration changes

**DON'T:**
- ❌ Add private/admin channels
- ❌ Add NSFW channels
- ❌ Add channels without bot permissions
- ❌ Leave inactive channels configured

---

### FAQ Management

**DO:**
- ✅ Focus on wheel strategy topics
- ✅ Provide specific, actionable advice
- ✅ Use clear, professional language
- ✅ Include practical examples
- ✅ Proofread before submitting
- ✅ Regular audit (remove outdated FAQs)

**DON'T:**
- ❌ Add generic options info (already in training data)
- ❌ Include financial advice disclaimers in every FAQ
- ❌ Duplicate existing knowledge base content
- ❌ Use vague or ambiguous language
- ❌ Add memes or jokes as FAQs

---

## FAQ Quality Guidelines

### High-Quality FAQ Example (Score: 90%)

```
Q: When should I roll a covered call that's deep in-the-money?

A: Roll a deep ITM covered call when:

1. **Before expiration**: Roll 7-14 days before expiry to maximize time value capture
2. **Price threshold**: When the stock price is 5-10% above your call strike
3. **Next expiry**: Roll to next monthly expiration at a strike above current price
4. **Credit requirement**: Ensure you receive a net credit (even if small)

Example: You sold a $50 call, stock now at $57
- Buy back $50 call (high premium due to ITM)
- Sell next month's $58 or $59 call
- Collect net credit of $0.20-0.50
- Repeat monthly to stay in the position
```

**Why it's good:**
- ✅ Specific question
- ✅ Clear criteria
- ✅ Actionable steps
- ✅ Practical example
- ✅ Relevant to wheel strategy

---

### Low-Quality FAQ Example (Score: 35%)

```
Q: How do options work?

A: Options give you the right to buy or sell. There are calls and puts.
```

**Why it failed:**
- ❌ Too generic (not wheel-specific)
- ❌ Incomplete answer
- ❌ No actionable guidance
- ❌ Already in base knowledge
- ❌ No practical value

---

## Command History

**Before (Old System):**
- `/ai_assistant_faq add` - Author only
- `/ai_assistant_faq list` - Author only
- `/ai_assistant_faq rm` - Author only
- No channel commands (required CLI)

**After (Current System):**
- `/faq_add` - Administrator
- `/faq_list` - Administrator
- `/faq_remove` - Administrator
- `/channels_list` - Administrator
- `/channels_add` - Administrator
- `/channels_remove` - Administrator

**Improvements:**
- ✅ Shorter command names
- ✅ Available to all admins (not just author)
- ✅ Unified admin command structure
- ✅ Better UX with rich embeds
- ✅ Comprehensive validation

---

## Related Documentation

- **Quick Reference:** `doc/admin_quick_reference.md` - Command cheat sheet
- **Visual Guide:** `doc/admin_commands_visual_guide.md` - UI screenshots
- **CLI Alternative:** `doc/cli_reference.md` - Command-line tools
- **Architecture:** `CLAUDE.md` - Technical implementation

---

## Support

**Issues:** https://github.com/anthropics/wheelhive/issues
**Discord:** https://discord.gg/wheelhive
**Website:** https://wheelhive.ai

---

*Last updated: 2025-11-12 - Unified admin commands (channels + FAQ)*
