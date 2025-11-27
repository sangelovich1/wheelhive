# Admin Quick Reference

**WheelHive Administrator Commands - Quick Guide**

---

## 📋 Channel Management

### View Channels
```
/channels_list
```

### Add Channel
```
/channels_add channel:#CHANNEL-NAME category:CATEGORY
```

**Categories:**
- `community` - Trading discussions, chat, sentiment
- `news` - Market news, earnings alerts, stock news (AI context)

### Remove Channel
```
/channels_remove channel:#CHANNEL-NAME
```

---

## 💡 FAQ Management

### View FAQs
```
/faq_list
```

### Add FAQ
```
/faq_add
```
*Opens modal form - fill in question and answer*

### Remove FAQ
```
/faq_remove faq_id:FAQ_ID
```
*Get FAQ_ID from /faq_list*

---

## 🔧 Troubleshooting

### "You need Administrator permissions"
→ Contact server owner to grant you Admin role

### "I don't have permission to read that channel"
→ Fix bot permissions:
1. Right-click channel → Edit Channel
2. Permissions → Add @WheelHive
3. Enable: ✅ Read Messages ✅ Read Message History

### "FAQ Validation Failed"
→ Improve your FAQ:
- Make question more specific
- Provide complete, actionable answer
- Ensure relevance to wheel strategy

### Commands not appearing
→ Make sure you have Administrator permission

---

## ⚡ Quick Setup Examples

### New Server Setup
```bash
# Configure channels
/channels_add channel:#trading-chat category:community
/channels_add channel:#news category:news

# Add FAQs
/faq_add   # Fill in modal with Q&A

# Verify
/channels_list
/faq_list
```

### Add Server-Specific Knowledge
```bash
# Open FAQ form
/faq_add

# Example:
Question: What are our server's position sizing rules?
Answer: We recommend 1% of account per trade, max 5 simultaneous positions...

# Submit for AI validation
```

---

## 📖 Full Documentation

- **Complete Reference:** `doc/admin_commands_reference.md`
- **Admin Guide:** `doc/admin_guide.md` (channels only)
- **Visual Guide:** `doc/admin_commands_visual_guide.md`
- **Support:** https://wheelhive.ai

---

## 🔐 Permissions Required

**For admins:** Administrator role
**For bot:** Read Messages + Read Message History

---

**TIP:** All responses are private (ephemeral) - only you see them!

**Command Count:** 6 admin commands (3 channels + 3 FAQ)
