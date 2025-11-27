# Admin Commands Visual Guide

## What Admins See in Discord

### Command Discovery

When you type `/` in Discord, administrators will see three new commands:

```
/channels_list     List all configured analyzed channels
/channels_add      Add a channel for message analysis
/channels_remove   Remove a channel from analysis
```

**Note:** Regular users (non-admins) won't see these commands at all.

---

## Command Examples with Expected Output

### 1. `/channels_list` - View Current Configuration

**What you type:**
```
/channels_list
```

**What you see (Embed):**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 📋 Configured Analysis Channels          ┃
┃                                             ┃
┃ Currently monitoring 4 channel(s) in       ┃
┃ this server                                 ┃
┃                                             ┃
┃ 💬 Community Channels                       ┃
┃ • #stock-options (stock-options)           ┃
┃ • #stock-chat (stock-chat)                 ┃
┃ • #darkminer-moves (darkminer-moves)       ┃
┃                                             ┃
┃ 📰 News Channels                            ┃
┃ • #news (news)                             ┃
┃                                             ┃
┃ Use /channels_add or /channels_remove     ┃
┃ to modify                                   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Features:**
- ✅ Clean, professional embed format
- ✅ Color-coded (blue theme)
- ✅ Organized by category
- ✅ Channel mentions are clickable
- ✅ Ephemeral (only you see it)

---

### 2. `/channels_add` - Add a New Channel

**What you type:**
```
/channels_add channel:#trading-chat category:community
```

**Discord UI:**
- `channel` field shows a **native channel picker** (dropdown of all text channels)
- `category` field shows **two choices**: `community` or `news`

**What you see (Success):**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ✅ Channel Added                            ┃
┃                                             ┃
┃ Now analyzing messages from               ┃
┃ #trading-chat                              ┃
┃                                             ┃
┃ Channel: #trading-chat                     ┃
┃ Category: 💬 Community                      ┃
┃ Guild ID: 850508033041760256               ┃
┃                                             ┃
┃ Messages will be analyzed for trading      ┃
┃ insights                                    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**What you see (Error - No Permission):**

```
❌ I don't have permission to read messages in #private-channel
Please grant me `Read Messages` permission for that channel.
```

**Features:**
- ✅ Validates bot permissions before saving
- ✅ Warns about missing "Read Message History"
- ✅ Native Discord channel selector (no typos!)
- ✅ Clear success/error messages
- ✅ Shows all relevant metadata

---

### 3. `/channels_remove` - Remove a Channel

**What you type:**
```
/channels_remove channel:#old-trades
```

**Discord UI:**
- `channel` field shows a **native channel picker**

**What you see (Success):**

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ✅ Channel Removed                          ┃
┃                                             ┃
┃ No longer analyzing messages from         ┃
┃ #old-trades                                ┃
┃                                             ┃
┃ Channel: #old-trades                       ┃
┃ Guild ID: 850508033041760256               ┃
┃                                             ┃
┃ Use /channels_add to re-enable if needed   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**What you see (Info - Not Configured):**

```
ℹ️ #random-channel is not currently configured for analysis.
```

**Features:**
- ✅ Soft delete (can be re-added)
- ✅ Friendly error if channel wasn't configured
- ✅ Clear confirmation message

---

## User Experience Highlights

### ✨ Professional Features

1. **Permission Checks**
   - Bot validates its own permissions before saving
   - Prevents "broken" configurations
   - Clear error messages guide admins to fix

2. **Native Discord UI**
   - Channel selector shows all text channels
   - Dropdown prevents typos
   - Autocomplete for fast selection

3. **Ephemeral Responses**
   - Only the admin sees the command output
   - Doesn't clutter the channel
   - Private configuration changes

4. **Rich Embeds**
   - Color-coded by status (blue=info, green=success, orange=warning)
   - Organized with emojis for visual scanning
   - Professional appearance

5. **Helpful Footer Text**
   - Every response includes next steps
   - Guides users to related commands
   - Reduces support questions

---

## Comparison: CLI vs Discord Commands

### CLI Approach (Old)
```bash
# Admin needs server access
ssh user@server.com

# Navigate to bot directory
cd /opt/wheelhive

# Activate venv
source .bot_venv/bin/activate

# Run command with flags
python src/cli.py channels add \
  --guild-id 850508033041760256 \
  --channel-id 1415355798216773653 \
  --channel-name stock-options \
  --category sentiment

# Need to remember guild/channel IDs
# No validation of inputs
# Typos cause silent failures
```

**Time:** ~2-3 minutes
**Difficulty:** High (need server access, command syntax)
**Error-prone:** Yes (IDs, typos, flags)

---

### Discord Commands (New)
```
/channels_add channel:#stock-options category:community
```

**Time:** ~10 seconds
**Difficulty:** Low (point and click)
**Error-prone:** No (dropdowns, validation)

**Advantages:**
- ✅ No server access needed
- ✅ No command syntax to memorize
- ✅ Guild/Channel IDs handled automatically
- ✅ Permission validation before save
- ✅ Instant feedback
- ✅ Mobile-friendly
- ✅ Works in Discord app, web, or desktop

---

## Permission Model Visual

```
┌─────────────────────────────────────────────┐
│ User tries to run /channels_add            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Discord Permission Check                    │
│ • Does user have "Administrator"?           │
│   ├─ YES → Continue                         │
│   └─ NO  → Command hidden/blocked           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Bot Permission Check                        │
│ • Can bot read the target channel?          │
│ • Does bot have message history access?     │
│   ├─ YES → Continue                         │
│   └─ NO  → Show error with instructions     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Database Update                             │
│ • INSERT OR REPLACE guild_channels          │
│ • Log action (username, timestamp)          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Success Response                            │
│ • Show green embed                          │
│ • Display configuration                     │
│ • Suggest next steps                        │
└─────────────────────────────────────────────┘
```

---

## Mobile Experience

### Discord Mobile App

Commands work identically on mobile:

1. **Tap message box** → `/` appears
2. **Type `/cha`** → Autocomplete shows `/channels_add`
3. **Tap command** → Form appears with inputs
4. **Tap `channel` field** → Native channel picker
5. **Select channel** → Dropdown closes
6. **Tap `category` field** → Choose community/news
7. **Tap Send** → Command executes
8. **See result** → Embed appears (only to you)

**Time on mobile:** ~15 seconds
**Ease:** Very easy (all taps, no typing)

---

## Admin Workflow Examples

### First-Time Setup

**Goal:** Configure bot for new server

```
Step 1: See current state
→ /channels_list
← No channels configured

Step 2: Add main chat
→ /channels_add channel:#trading-chat category:community
← ✅ Channel Added

Step 3: Add news channel
→ /channels_add channel:#announcements category:news
← ✅ Channel Added

Step 4: Verify
→ /channels_list
← Shows 2 channels configured

Time: ~30 seconds total
```

---

### Troubleshooting Missing Messages

**Problem:** Bot not harvesting from #new-channel

```
Step 1: Check configuration
→ /channels_list
← Shows #new-channel NOT in list

Step 2: Add missing channel
→ /channels_add channel:#new-channel category:community
← ✅ Channel Added

Step 3: Test
→ Send message with ticker in #new-channel
→ Check if it appears in analytics

Resolution time: ~1 minute
```

---

### Server Reorganization

**Goal:** Remove old channels, add new ones

```
Step 1: Remove deprecated channels
→ /channels_remove channel:#old-trades
← ✅ Channel Removed

→ /channels_remove channel:#archived-chat
← ✅ Channel Removed

Step 2: Add new channels
→ /channels_add channel:#pro-trading category:community
← ✅ Channel Added

→ /channels_add channel:#market-alerts category:news
← ✅ Channel Added

Step 3: Review final config
→ /channels_list
← Shows updated channel list

Time: ~1 minute
```

---

## Error Scenarios & Solutions

### Error: "You need Administrator permissions"

**Cause:** User doesn't have admin role

**Solution:**
```
Server Settings → Roles → [User's Role] → Enable "Administrator"
```

---

### Error: "I don't have permission to read that channel"

**Cause:** Bot lacks channel permissions

**Solution:**
```
Right-click channel → Edit Channel → Permissions → Add @WheelHive
Enable: ✅ Read Messages, ✅ Read Message History
```

---

### Error: "This command can only be used in a server"

**Cause:** User tried command in DMs

**Solution:**
```
Use the command in a server text channel instead of DMs
```

---

## Best Practices Summary

### ✅ DO
- Use `/channels_list` regularly to review configuration
- Configure permissions BEFORE adding channels
- Use descriptive channel names
- Separate community vs news channels clearly
- Test after making changes

### ❌ DON'T
- Don't add private/admin-only channels
- Don't add NSFW channels
- Don't add channels bot can't access
- Don't configure the same channel twice (it updates, not duplicates)
- Don't forget to remove deleted channels from config

---

## Security & Privacy

### What's Stored?
```sql
CREATE TABLE guild_channels (
    guild_id INTEGER,      -- Your server ID
    channel_id INTEGER,    -- Channel ID
    channel_name TEXT,     -- Human-readable name
    category TEXT,         -- "sentiment" or "news"
    enabled INTEGER,       -- 1=active, 0=removed
    created_at TEXT        -- Timestamp
)
```

### What's NOT Stored?
- ❌ Message contents (stored separately in `messages` table)
- ❌ User passwords or tokens
- ❌ Private channel contents
- ❌ Admin permissions/roles

### Who Can Access?
- ✅ Server administrators (via `/channels_list`)
- ✅ Server owner (via CLI)
- ✅ Database admin (direct DB access)
- ❌ Regular users (commands hidden)
- ❌ Bot developer (no remote access)

---

*This guide shows the professional, user-friendly experience of Discord slash commands for admin configuration. The native UI, validation, and embeds provide a polished experience that's faster and safer than CLI alternatives.*
