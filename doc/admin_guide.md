# WheelHive Admin Guide

## Channel Management Commands

WheelHive provides intuitive slash commands for server administrators to configure which channels the bot monitors for trading discussions and news.

### Prerequisites

- **Administrator** permission in your Discord server
- Bot must have **Read Messages** and **Read Message History** permissions in channels you want to monitor

### Available Commands

All admin commands are slash commands (start with `/`) and are only visible to users with Administrator permissions.

---

## `/channels_list`

**List all configured analyzed channels**

Shows which channels are currently being monitored by the bot, organized by category.

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

**Notes:**
- Shows channel mentions for easy navigation
- Only shows channels for your current server
- Ephemeral (only you can see the response)

---

## `/channels_add`

**Add a channel for message analysis**

Configure the bot to monitor a specific channel for trading insights or news.

**Parameters:**
- `channel` (required): Select the channel from the dropdown
- `category` (required): Choose channel type
  - `community`: Trading discussions, strategy talk, general chat
  - `news`: Market news, stock news, earnings reports, economic data (provides AI context)

**Usage:**
```
/channels_add channel:#stock-chat category:community
/channels_add channel:#news category:news
```

**Example Output:**
```
✅ Channel Added
Now analyzing messages from #stock-chat

Channel: #stock-chat
Category: 💬 Community
Guild ID: 850508033041760256

Messages will be analyzed for trading insights
```

**Permission Validation:**
- Bot automatically checks if it can read the channel
- Warns if missing "Read Message History" permission
- Prevents configuration errors before they happen

**Notes:**
- Uses native Discord channel selector (can't make typos!)
- Duplicate channels are automatically updated (not errored)
- Changes take effect immediately

---

## `/channels_remove`

**Remove a channel from analysis**

Stop the bot from monitoring a specific channel.

**Parameters:**
- `channel` (required): Select the channel to remove

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

Use /channels_add to re-enable if needed
```

**Notes:**
- Soft delete (disables rather than deletes)
- Can be re-added later with `/channels_add`
- If channel isn't configured, you'll get a friendly info message

---

## Channel Categories Explained

### 💬 Community Channels
**Purpose:** Capture community trading discussions and sentiment

**Best for:**
- General trading chat (`#trading`, `#stock-chat`)
- Strategy discussions (`#options-strategy`, `#wheel-strategy`)
- Member trades and positions (`#my-trades`, `#trade-alerts`)
- Community sentiment channels

**What gets extracted:**
- Trade entries (e.g., "STO 2x MSTU 8/1 8P @ .16")
- Sentiment and opinions about tickers
- Strategy discussions
- Community insights

### 📰 News Channels
**Purpose:** Track official announcements and market news

**Best for:**
- Market news (`#news`, `#market-updates`)
- Server announcements (`#announcements`)
- Analyst updates (`#premium-alerts`)
- Official posts from admins/moderators

**What gets extracted:**
- Market-moving news
- Ticker mentions in announcements
- Important updates

---

## Best Practices

### 1. **Permission Setup**
Before adding channels, ensure the bot has:
```
✓ Read Messages
✓ Read Message History
```

To check: Right-click channel → Edit Channel → Permissions → WheelHive

### 2. **Channel Organization**
Recommended setup:
```
💬 Community Channels:
  - Main trading discussion channels
  - Member trade-sharing channels
  - Strategy and education channels

📰 News Channels:
  - Announcement channels only
  - Official news feeds
  - Admin/moderator updates only
```

### 3. **Privacy Considerations**
- Only add **public** channels (not private/NSFW)
- Don't add admin-only channels with sensitive info
- Remember: Bot stores messages for analysis

### 4. **Regular Review**
- Run `/channels_list` monthly to review configuration
- Remove inactive channels
- Add new channels as your server grows

---

## Troubleshooting

### "I don't have permission to read that channel"
**Solution:** Grant bot these permissions in the target channel:
1. Right-click channel → Edit Channel
2. Go to Permissions tab
3. Add `@WheelHive` role
4. Enable: `Read Messages`, `Read Message History`
5. Try `/channels_add` again

### Commands not showing up
**Solution:** Ensure you have Administrator permission. Commands are hidden from regular users.

### Changes not taking effect
**Solution:** Changes are immediate. If messages aren't being harvested:
1. Check bot is online
2. Verify permissions with `/channels_list`
3. Test by sending a message with a ticker symbol
4. Check bot logs (CLI: `python src/cli.py admin metrics`)

### Want to use CLI instead?
```bash
# List channels
python src/cli.py channels list

# Add channel
python src/cli.py channels add \
  --guild-id 850508033041760256 \
  --channel-id 1415355798216773653 \
  --channel-name stock-options \
  --category sentiment

# Remove channel
python src/cli.py channels rm \
  --guild-id 850508033041760256 \
  --channel-id 1415355798216773653
```

---

## Security Notes

### Who Can Use These Commands?
- **Requires:** Discord Administrator permission
- **Visibility:** Commands only visible to administrators
- **Responses:** Ephemeral (only you see the output)
- **Audit:** All changes logged with username

### Permissions Model
```
User Permission Check → Bot Permission Check → Database Update → Audit Log
```

1. Discord checks if user has Administrator role
2. Bot validates it can access the channel
3. Change is saved to database
4. Action is logged with timestamp and username

---

## Examples: Complete Server Setup

### Small Trading Server
```bash
# 1. List current configuration
/channels_list

# 2. Add main discussion channel
/channels_add channel:#trading-chat category:community

# 3. Add announcements
/channels_add channel:#news category:news

# 4. Verify setup
/channels_list
```

### Large Multi-Channel Server
```bash
# Add multiple community channels
/channels_add channel:#general-trading category:community
/channels_add channel:#options-strategy category:community
/channels_add channel:#wheel-strategy category:community
/channels_add channel:#my-trades category:community

# Add news channels
/channels_add channel:#market-news category:news
/channels_add channel:#announcements category:news

# Review configuration
/channels_list
```

### Migration from Old Setup
```bash
# Remove old channels
/channels_remove channel:#old-chat
/channels_remove channel:#deprecated-news

# Add new channels
/channels_add channel:#new-discussion category:community
/channels_add channel:#new-alerts category:news

# Confirm changes
/channels_list
```

---

## Advanced: Programmatic Management

For advanced users who prefer automation, the underlying Python API is available:

```python
from guild_channels import GuildChannels
from db import Db

db = Db()
guild_channels = GuildChannels(db)

# Add channel
guild_channels.add_channel(
    guild_id=850508033041760256,
    channel_id=1415355798216773653,
    channel_name="stock-options",
    category="sentiment"
)

# List channels
channels = guild_channels.get_channels_for_guild(850508033041760256)
for channel_id, name, category in channels:
    print(f"{name}: {category}")

# Remove channel
guild_channels.remove_channel(
    guild_id=850508033041760256,
    channel_id=1415355798216773653
)
```

---

## Related Documentation

- **User Guide:** `/doc/user_guide.md` - End-user commands
- **CLI Reference:** `/doc/cli_reference.md` - Command-line tools
- **Architecture:** `/CLAUDE.md` - System design and conventions

---

## Support

- **Issues:** https://github.com/anthropics/wheelhive/issues
- **Discord:** https://discord.gg/wheelhive
- **Website:** https://wheelhive.ai

---

*Last updated: 2025-11-12*
