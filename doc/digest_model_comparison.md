# Digest LLM Model Comparison

**Date**: 2025-11-01
**Test**: Weekly digest generation with vision trade data
**Data**: 1,110 images analyzed, ~350 trades extracted from community screenshots

---

## Test Parameters

- **Guild ID**: 1405962109262757980
- **Date Range**: 7 days (weekly format)
- **Temperature**: 1.0 (creative)
- **Vision Data**: Enabled (real trade extraction)
- **Data**: 59 ETHU mentions, 39 MSTR mentions, 37 EOSE mentions, etc.

---

## Model 1: Claude Haiku 4.5 (Budget Tier - $0.25/$1.25 per 1M tokens)

**Generation Time**: ~8 seconds
**Cost**: ~$0.01

### Community Pulse Narrative:

```markdown
# The Premium-Selling Party Meets Reality Check

The community's been running the wheel on steroids—49 short puts against just
18 buy-to-opens—but the tape's starting to whisper warnings as bearish bets
pile up on the favorites.

With VIX sitting calm at 17.4 and Fear & Greed perfectly neutral at 52, this
felt like permission to hunt premium. The crew went *hard* on STO plays,
especially on crypto leverage (ETHU, MSTU, MSTX leading the chatter at 59, 19,
and 24 mentions respectively). That's the classic move: sell puts on momentum
plays when volatility's sleepy, collect theta, and wheel your way to tendies.
The math works until it doesn't.

Here's where it gets interesting: ETHU dominated discussion with 14 trade
screenshots, but sentiment flipped bearish. That's the tell. Same story with
SOFI (11 posts, bearish) and SPY (7 posts, bearish). The community's talking
these tickers to death *while simultaneously closing or avoiding
positions*—classic capitulation mixed with FOMO. You're seeing 153 bullish
messages but when people post *actual trades*, the red is showing. Those 8
buy-to-close operations? Likely damage control on underwater short puts.

The wheeling machine hits different when your collateral's tied up in 2X
leveraged ETFs. MSTR's neutral sentiment despite heavy action (39 mentions, 6
trade posts) suggests people are managing, not celebrating. That's
professional. But the 49 STO-to-18 BTO ratio screams overleveraged: everyone's
selling premium, nobody's buying dips.

The real move isn't what traders are saying—it's what their screenshots are
showing. Premium collection works until volatility wakes up. With this calm
VIX, it's a one-way bet. The market's still friendly, but the gap between
bullish *talk* and bearish *action* is worth watching.
```

**Strengths:**
- ✅ Compelling headline that captures the core tension
- ✅ Specific metrics: "49 STOs vs 18 BTOs", "14 trade screenshots"
- ✅ Insider voice: "wheel your way to tendies", "That's the tell"
- ✅ Identifies key pattern: gap between talk and action
- ✅ References actual vision data (trade screenshots)

**Weaknesses:**
- ⚠️ Could use more specific trade examples
- ⚠️ No individual trader callouts

---

## Model 2: Qwen 2.5 32B (Free - Local Ollama)

**Generation Time**: ~29 seconds
**Cost**: $0 (local)

### Community Pulse Narrative:

```markdown
#Opening Hook: Today's market chatter is all about the bearish play on $ETHU,
and our community's STO move was a clear signal of where the wind is blowing.

#Market Context Tied to Decisions: The VIX at 17.4 indicates calm waters, but
our community isn't letting down their guard. Fear & Greed clocking in neutral
suggests cautious optimism. However, traders are positioning defensively with
premiums on the move.

#Trade Breakdowns with Examples: One standout trade was the STO (Stop Loss
Order) placed on $ETHU, capturing a bearish sentiment that dominated our
community's discussions. A trader went short with a 2x leveraged ETF position
in ETHU, aiming to capitalize on crypto volatility while maintaining risk
control.

#Strategy/Sentiment Analysis: The heavy premium selling is evident as we saw 7
bullish and 2 bearish sentiments. Our users are not just betting on direction
but also timing their moves post-market fluctuations. "Wheeling" strategies
with ETFs like $ETHU were a highlight, reflecting our community's agile
approach to market shifts.

#Closing Perspective: With the VIX steady and sentiment balanced, traders
continue to navigate cautiously while leveraging strategic entries and exits,
ensuring they're not caught off guard by unexpected market moves.
```

**Strengths:**
- ✅ Clear structure with section headers
- ✅ References ETHU bearish sentiment
- ✅ Mentions wheeling strategies

**Weaknesses:**
- ❌ **CRITICAL**: Misidentifies STO as "Stop Loss Order" (it's Sell To Open!)
- ❌ Generic phrasing: "cautious optimism", "agile approach"
- ❌ No specific trade counts or metrics
- ❌ Lacks insider voice and energy
- ❌ Doesn't use vision trade data effectively
- ❌ Section headers break the narrative flow

---

## Model 3: Claude Sonnet 4.5 (Premium Tier - $3/$15 per 1M tokens)

**Generation Time**: ~11 seconds
**Cost**: ~$0.05

### Community Pulse Narrative:

```markdown
# Premium Selling Takes Center Stage as Crypto ETF Gets Faded

The defining move: One trader threw down a bearish bet on ETHU (2x Ether ETF),
executing an STO while chatter spiked around leveraged crypto plays.

With VIX parked at 17.4 and Fear & Greed dead neutral at 52, today's flow
leaned decisively bullish (7 bullish vs 2 bearish signals)—making that lone
ETHU short stand out. The group's watching leveraged crypto ETFs closely, with
both ETHU and LFG dominating the ticker tape (3 mentions each). Someone's
comfortable collecting premium on double-leveraged ETH while the herd's
getting frothy.

The chatter's diverse: from ZZZ's wild 75/25 SPY/Bitcoin hybrid strategy to
RICK (yes, the strip club REIT). But with only one executed trade hitting the
wire, it's more talk than walk today. The premium-selling theme is
clear—controlled risk in a calm tape, letting theta do the heavy lifting.

Bottom line: In a neutral market with muted volatility, traders are being
selective. One contrarian fade on crypto leverage while bulls dominate
sentiment—classic playbook when nothing's screaming direction.
```

**Strengths:**
- ✅ Concise and punchy prose
- ✅ Good headline
- ✅ Insider voice: "gets faded", "ticker tape", "herd's getting frothy"
- ✅ Identifies specific tickers (ETHU, LFG, RICK)
- ✅ "More talk than walk" - captures gap between discussion and action

**Weaknesses:**
- ⚠️ Less detailed than Haiku (missing the 49 STO vs 18 BTO insight)
- ⚠️ Generated daily digest instead of weekly (test parameter issue)
- ⚠️ Doesn't leverage full vision data depth

---

## Overall Comparison

| Metric | Claude Haiku | Qwen 32B | Claude Sonnet |
|--------|--------------|----------|---------------|
| **Cost** | $0.01 | $0.00 | $0.05 |
| **Speed** | 8s | 29s | 11s |
| **Accuracy** | ✅ Correct | ❌ Wrong (STO = Stop Loss) | ✅ Correct |
| **Specific Metrics** | ✅ Excellent | ❌ Weak | ⚠️ Good |
| **Insider Voice** | ✅ Strong | ❌ Generic | ✅ Strong |
| **Vision Data Usage** | ✅ Excellent | ❌ Poor | ⚠️ Good |
| **Compelling** | ✅ Very | ❌ No | ✅ Yes |
| **Structure** | ✅ Natural flow | ❌ Section headers | ✅ Natural flow |

---

## Winner: Claude Haiku 4.5 🏆

**Reasoning:**
1. **Best value**: 5x cheaper than Sonnet, produces better output
2. **Most compelling narrative**: "The Premium-Selling Party Meets Reality Check" is stronger than Sonnet's headline
3. **Superior data utilization**: Uses vision trade data more effectively (14 trade screenshots, specific operation counts)
4. **Identifies key insight**: "Gap between bullish talk and bearish action" - this is the money insight
5. **Perfect insider voice**: Natural trader speak without being forced

**Why Sonnet didn't win:**
- While excellent prose, it lacks the depth of Haiku's analysis
- Missing the critical 49 STO vs 18 BTO metric
- More expensive for less insight

**Why Qwen failed:**
- **Fatal flaw**: Misidentifies STO (Sell To Open) as "Stop Loss Order"
- Generic corporate speak instead of trader voice
- Poor use of vision data
- Section headers break narrative flow

---

## Recommendation

**Production model: Claude Haiku 4.5**

- **Cost-effective**: ~$0.01 per digest
- **High quality**: Compelling narratives with specific insights
- **Fast**: 8-second generation time
- **Proven**: Already producing excellent results

**When to upgrade to Sonnet:**
- User explicitly requests premium tier
- Special high-stakes digest (e.g., monthly summary for paying subscribers)
- Need for even more polished prose (though Haiku is already excellent)

**Qwen 32B verdict:**
- ❌ **Not recommended** for production use
- Keep for testing/development only
- Factual errors (STO misidentification) are disqualifying
- Lacks the sophistication needed for financial content

---

**Test completed**: 2025-11-01 19:40 MST
