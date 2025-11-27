# Digest Configuration Changes - November 2025

**Date**: 2025-11-01
**Status**: Production Ready

---

## Summary of Changes

The digest system has been updated to **always generate 7-day rolling window digests** instead of switching between daily and weekly formats. This change significantly improves content quality and makes better use of the vision-analyzed trade data.

---

## Changes Made

### 1. **daily_digest.py** - Always Use 7-Day Window

**File**: `src/daily_digest.py`

**Change**: `generate_digest()` method now always calls `_generate_weekly_digest()` regardless of day of week.

```python
def generate_digest(self, date: datetime = None) -> str:
    """
    Generate a community digest for the specified date.

    Always generates a rolling 7-day digest for better signal-to-noise ratio
    and more meaningful pattern detection from vision trade data.

    Args:
        date: Date to generate digest for (defaults to today)

    Returns:
        Formatted digest string (7-day rolling window)
    """
    if date is None:
        date = datetime.now()

    # Always use 7-day rolling window format for better insights
    return self._generate_weekly_digest(date)
```

**Rationale**:
- Daily digests (24 hours) have insufficient data for meaningful patterns
- Weekly format (7 days) provides:
  - 190+ trades from vision analysis vs 1-2 trades daily
  - Top 10 tickers with real volume (59 mentions) vs noisy single mentions
  - Statistical significance for pattern detection
  - More compelling narratives with specific insights

### 2. **bot.py** - Schedule Daily at 5pm MST, Start Nov 15

**File**: `src/bot.py`

**Change**: Added start date check and removed daily/weekly logic.

```python
@tasks.loop(hours=24)
async def daily_digest_task(self):
    """Generate daily digests for all guilds at 5pm MST every day (2 hours after market close at 2pm MST/4pm ET).

    Always generates 7-day rolling window digests for better signal-to-noise ratio.
    Starts November 15, 2025.
    """
    logger.info("Running daily digest task for all guilds...")

    try:
        today = datetime.now()

        # Check if we've reached the start date (November 15, 2025)
        start_date = datetime(2025, 11, 15)
        if today < start_date:
            logger.info(f"Digest generation not yet enabled. Will start on {start_date.strftime('%B %d, %Y')}")
            return

        logger.info(f"Generating 7-day rolling digests for {len(const.GUILDS)} guilds")
```

**Schedule**:
- **Frequency**: Daily at 5pm MST (2 hours after market close)
- **Start Date**: November 15, 2025
- **Format**: Always 7-day rolling window

### 3. **cli/reports.py** - Add LLM Model Selection

**File**: `src/cli/reports.py`

**Change**: Added `--llm-model` parameter to digest command.

```python
@click.option('--llm-model', type=str, default=None,
              help='LLM model key (e.g., ollama-qwen-32b, claude-sonnet, claude-haiku)')
```

**Usage**:
```bash
# Use Claude Haiku (default)
python src/cli.py reports digest --enable-llm

# Use Claude Sonnet for premium quality
python src/cli.py reports digest --enable-llm --llm-model claude-sonnet

# Use local Qwen (not recommended)
python src/cli.py reports digest --enable-llm --llm-model ollama-qwen-32b
```

---

## Model Comparison Results

### Winner: Claude Haiku 4.5 🏆

**Why Haiku is Production Default:**

| Metric | Claude Haiku | Qwen 32B | Claude Sonnet |
|--------|--------------|----------|---------------|
| **Cost** | $0.01 | $0.00 | $0.05 |
| **Speed** | 8s | 29s | 11s |
| **Quality** | Excellent | Poor | Excellent |
| **Accuracy** | ✅ Perfect | ❌ Errors | ✅ Perfect |
| **Specificity** | ✅ Very High | ❌ Low | ⚠️ Good |
| **Value** | 🏆 Best | ❌ Worst | ⚠️ Overpriced |

**Haiku Advantages:**
- 5x cheaper than Sonnet, same/better quality
- Superior data utilization: "49 STOs vs 18 BTOs", "14 trade screenshots"
- Perfect insider voice: "wheel your way to tendies", "That's the tell"
- Identifies key insight: "Gap between bullish talk and bearish action"

**Qwen 32B Issues (Disqualified):**
- ❌ **CRITICAL**: Misidentifies STO as "Stop Loss Order" (it's Sell To Open!)
- Generic corporate speak instead of trader voice
- Poor utilization of vision trade data
- Section headers break narrative flow

**Sonnet Verdict:**
- Excellent prose, but less analytical depth than Haiku
- Missing critical metrics that Haiku captures
- 5x more expensive for marginal/no improvement
- Use only for premium subscribers or special reports

---

## Configuration Summary

### Current Production Setup

**LLM Model**: Claude Haiku 4.5 (`claude-haiku`)
- Model ID: `claude-haiku-4-5-20251001`
- Cost: ~$0.01 per digest
- Speed: 8 seconds

**Schedule**:
- **Start Date**: November 15, 2025
- **Frequency**: Daily at 5pm MST
- **Lookback**: Rolling 7 days

**Data Sources**:
- Text messages: Ticker mentions, sentiment
- Vision analysis: 1,110+ images, ~350 trades extracted
- Market data: VIX, Fear & Greed Index
- Scanner: Options opportunities

**Output Format**:
- Title: "WEEKLY DIGEST - Week Ending {date}"
- Sections:
  - Market Context (VIX, Fear & Greed)
  - Top 10 Trending Tickers (7-day window)
  - Community Pulse (LLM narrative with vision trade insights)
  - Market News Highlights (LLM summary)
- Saved to: `daily_digest/guild_{id}/{date}/`

---

## Testing & Validation

### Test Results (2025-11-01)

**Data Used:**
- 1,110 images analyzed
- 350+ trades extracted
- 59 ETHU mentions, 39 MSTR mentions, etc.
- 7-day window

**Models Tested:**
1. ✅ **Claude Haiku**: Excellent ("The Premium-Selling Party Meets Reality Check")
2. ❌ **Qwen 32B**: Failed (factual errors)
3. ⚠️ **Claude Sonnet**: Good but overpriced

**Winner**: Claude Haiku 4.5

---

## Migration Notes

### Breaking Changes

**None** - The changes are backward compatible:
- Old daily digest calls still work (just use 7-day window now)
- CLI parameters unchanged (except new optional `--llm-model`)
- Saved file structure unchanged

### Behavioral Changes

1. **Daily digests now cover 7 days** instead of 24 hours
   - Impact: Daily digests will be much more meaningful
   - Benefit: Consistent high-quality output every day

2. **Start date enforced** (November 15, 2025)
   - Impact: No digests generated before this date
   - Benefit: Allows time for vision data accumulation

### Rollback Plan

If needed, revert to daily/weekly split:

```python
# In daily_digest.py, replace:
return self._generate_weekly_digest(date)

# With:
is_friday = date.weekday() == 4
if is_friday:
    return self._generate_weekly_digest(date)
else:
    return self._generate_daily_digest(date)
```

---

## Next Steps

### Before November 15, 2025:

1. ✅ **Vision data accumulation**
   - Continue image analysis of all posted screenshots
   - Target: 2,000+ analyzed images by start date

2. ✅ **LLM model configuration**
   - Default: Claude Haiku 4.5
   - Database already configured

3. ✅ **Bot deployment**
   - Task already scheduled at 5pm MST
   - Will auto-start on November 15, 2025

### After November 15, 2025:

1. **Monitor first digest generation**
   - Check logs for successful generation
   - Verify markdown/PDF output quality

2. **Iterate on prompt if needed**
   - Temperature currently 1.0 (creative)
   - Can adjust based on output quality

3. **Consider premium tier**
   - Offer Sonnet-powered digests for $49/month subscribers
   - Keep Haiku for free/standard tiers

---

## Related Documents

- **Model Comparison**: `doc/digest_model_comparison.md`
- **Workflow Analysis**: `doc/digest_workflow_analysis.md`
- **Revenue Model**: `doc/market_analysis_revenue_potential.md`
- **Image Processing**: `doc/image_processing_architecture.md`

---

**Changes completed**: 2025-11-01
**Production ready**: ✅ Yes
**Start date**: November 15, 2025
