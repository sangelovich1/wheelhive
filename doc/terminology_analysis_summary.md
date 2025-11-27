# Terminology Change: "Harvest" → "Analyze"

## Decision

**Change:** Replace "harvest/harvesting" with "analyze/analysis" in all user-facing text

**Rationale:**
- ✅ More professional and value-focused
- ✅ Emphasizes insights over data collection
- ✅ Privacy-friendly (less aggressive)
- ✅ Industry-standard terminology
- ✅ Clearer purpose for users

## Scope

### Phase 1 (NOW): User-Facing ✅
- Admin command descriptions
- Discord embeds and messages
- Documentation files
- Website content
- Help text

### Phase 2 (LATER): Code References
- Function names
- Variable names
- Code comments
- Docstrings

## Replacement Patterns

| Before | After |
|--------|-------|
| harvest messages | analyze messages |
| harvesting channels | analyzed channels |
| for message harvesting | for message analysis |
| configured for harvesting | configured for analysis |
| harvest from | analyze |
| harvesting system | analysis system |
| message harvesting | message analysis |

## Files to Update (Phase 1)

**Code (user-facing strings only):**
- src/discord_admin_commands.py
- src/cli/channels.py
- src/guild_channels.py (docstrings)

**Documentation:**
- doc/admin_commands_reference.md
- doc/admin_guide.md
- doc/admin_commands_visual_guide.md
- doc/admin_quick_reference.md
- doc/sessions/session_20251112_admin_channel_commands.md

**Website:**
- (All website content files)

---

**Status:** Phase 1 in progress
**Date:** 2025-11-12
