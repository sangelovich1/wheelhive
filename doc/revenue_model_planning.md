# Revenue Model Planning & Implementation Guide

**Created:** 2025-10-21
**Status:** Planning Phase
**Current Default Tier:** `plus` (all users have full access)

---

## Executive Summary

The LLM multi-model integration is complete with tier-based infrastructure in place. Currently, all users default to the `plus` tier with access to all 9 AI models. This document outlines the steps needed to implement a revenue model when ready.

**Quick Start to Enable Paid Tiers:**
1. Change `DEFAULT_USER_TIER = 'free'` in `src/constants.py`
2. Implement admin tier management commands
3. Add usage tracking and cost monitoring
4. Set up payment processing
5. Configure tier upgrade workflow

---

## Current Architecture

### Tier System (Already Implemented)

**Three-tier structure in `src/constants.py`:**

```python
TIER_MODEL_ACCESS = {
    'free': [
        'ollama-llama-8b',      # Local, no cost
        'ollama-qwen-7b',       # Local, no cost
        'ollama-mistral-7b'     # Local, no cost
    ],
    'premium': [
        'claude-haiku',         # ~$0.50/M tokens
        'gpt-4o-mini',          # ~$0.60/M tokens
        'together-qwen-72b',    # ~$0.60/M tokens
        'together-llama-70b'    # ~$0.88/M tokens
    ] + free_models,
    'plus': list(AVAILABLE_MODELS.keys())  # All 9 models including:
        # 'claude-sonnet'  (~$15/M tokens)
        # 'gpt-4o'         (~$15/M tokens)
}
```

**Model Costs (Approximate per 1M tokens):**
- **Free Tier:** $0 (local Ollama models)
- **Premium Tier:** $0.50-$0.88 (budget cloud models)
- **Plus Tier:** $3-$15 (premium models like Claude Sonnet, GPT-4o)

### User Preferences System (Already Implemented)

**Database Schema (`user_preferences` table):**
```sql
CREATE TABLE user_preferences (
    username TEXT,
    preference_key TEXT,
    preference_value TEXT,
    updated_at TEXT,
    PRIMARY KEY (username, preference_key)
)
```

**Key-value pairs stored:**
- `llm_model`: User's selected AI model
- `user_tier`: Access tier (free/premium/plus)
- Extensible for future preferences

**Access via:**
- `src/user_preferences.py` - UserPreferences class
- `get_user_preferences()` - Singleton instance

### Discord Commands (Already Implemented)

1. **`/llm_models`** - List all models with tier indicators
2. **`/llm_select`** - Choose preferred model (validates tier access)
3. **`/llm_status`** - View current model and tier

**Current behavior:**
- Shows ALL models regardless of tier
- Uses 🔒 emoji for models requiring upgrade
- Validates tier when user tries to select model
- Blocks selection if user lacks access

---

## Implementation Roadmap

### Phase 1: Admin Tier Management (Required First)

**Goal:** Allow admins to manually set user tiers during beta/testing

**New Discord Commands Needed:**

```python
@client.tree.command(name="admin_set_tier", guilds=const.DEV_GUILD_IDS)
@app_commands.checks.has_permissions(administrator=True)
async def admin_set_tier(
    interaction: discord.Interaction,
    user: discord.User,
    tier: Literal['free', 'premium', 'plus']
):
    """[Admin Only] Set a user's access tier."""
    user_prefs = get_user_preferences()
    success = user_prefs.set_user_tier(user.name, tier)

    if success:
        await interaction.response.send_message(
            f"✓ Set {user.mention} to **{tier}** tier",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✗ Failed to update tier for {user.mention}",
            ephemeral=True
        )

@client.tree.command(name="admin_list_tiers", guilds=const.DEV_GUILD_IDS)
@app_commands.checks.has_permissions(administrator=True)
async def admin_list_tiers(interaction: discord.Interaction):
    """[Admin Only] List all users and their tiers."""
    db = Db()
    results = db.query(
        "SELECT username, preference_value as tier "
        "FROM user_preferences WHERE preference_key = 'user_tier' "
        "ORDER BY preference_value, username"
    )

    # Format and send results...
```

**TODO:**
- [ ] Implement `/admin_set_tier` command
- [ ] Implement `/admin_list_tiers` command
- [ ] Add permission checks (administrator role required)
- [ ] Add audit logging for tier changes

### Phase 2: Usage Tracking & Cost Monitoring

**Goal:** Track token usage and API costs per user

**New Database Table:**

```sql
CREATE TABLE llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    model_key TEXT NOT NULL,
    timestamp TEXT NOT NULL,

    -- Token usage
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,

    -- Cost tracking
    estimated_cost REAL NOT NULL,

    -- Context
    query_type TEXT,  -- 'analysis', 'digest', 'market_data', etc.
    success BOOLEAN NOT NULL,

    -- Performance
    latency_ms INTEGER,

    FOREIGN KEY (username) REFERENCES user_preferences(username)
);

CREATE INDEX idx_llm_usage_user ON llm_usage(username);
CREATE INDEX idx_llm_usage_timestamp ON llm_usage(timestamp);
CREATE INDEX idx_llm_usage_model ON llm_usage(model_key);
```

**Modify `src/llm_provider.py`:**

```python
class LLMProvider:
    async def acompletion(self, messages, system=None, tools=None, max_tokens=4096):
        """Async completion with usage tracking."""
        start_time = time.time()

        try:
            response = await acompletion(
                model=self.litellm_model,
                messages=messages,
                system=system,
                tools=tools,
                max_tokens=max_tokens
            )

            # Track usage
            await self._log_usage(
                response=response,
                success=True,
                latency_ms=int((time.time() - start_time) * 1000)
            )

            return response

        except Exception as e:
            await self._log_usage(
                response=None,
                success=False,
                latency_ms=int((time.time() - start_time) * 1000)
            )
            raise

    async def _log_usage(self, response, success, latency_ms):
        """Log token usage and estimated cost to database."""
        if not self.username:
            return  # Don't track anonymous usage

        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        estimated_cost = 0.0

        if response and hasattr(response, 'usage'):
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost based on model pricing
            estimated_cost = self._calculate_cost(prompt_tokens, completion_tokens)

        # Insert into database
        db = Db()
        db.execute(
            """
            INSERT INTO llm_usage (
                username, model_key, timestamp,
                prompt_tokens, completion_tokens, total_tokens,
                estimated_cost, success, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.username,
                self.model_key,
                datetime.now().isoformat(),
                prompt_tokens,
                completion_tokens,
                total_tokens,
                estimated_cost,
                success,
                latency_ms
            )
        )

    def _calculate_cost(self, prompt_tokens, completion_tokens):
        """Calculate estimated cost based on model pricing."""
        # Pricing per 1M tokens (update these from actual provider pricing)
        PRICING = {
            'claude-sonnet': {'input': 3.00, 'output': 15.00},
            'claude-haiku': {'input': 0.25, 'output': 1.25},
            'gpt-4o': {'input': 2.50, 'output': 10.00},
            'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
            'together-qwen-72b': {'input': 0.18, 'output': 0.18},
            'together-llama-70b': {'input': 0.88, 'output': 0.88},
            # Ollama models are free
            'ollama-llama-8b': {'input': 0.0, 'output': 0.0},
            'ollama-qwen-7b': {'input': 0.0, 'output': 0.0},
            'ollama-mistral-7b': {'input': 0.0, 'output': 0.0},
        }

        model_pricing = PRICING.get(self.model_key, {'input': 0.0, 'output': 0.0})

        input_cost = (prompt_tokens / 1_000_000) * model_pricing['input']
        output_cost = (completion_tokens / 1_000_000) * model_pricing['output']

        return input_cost + output_cost
```

**New Discord Commands:**

```python
@client.tree.command(name="my_usage", guilds=const.DEV_GUILD_IDS)
async def my_usage(
    interaction: discord.Interaction,
    timeframe: Literal['today', 'week', 'month', 'all'] = 'month'
):
    """View your LLM usage and costs."""
    username = interaction.user.name
    db = Db()

    # Calculate date filter
    if timeframe == 'today':
        cutoff = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    elif timeframe == 'week':
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    elif timeframe == 'month':
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    else:
        cutoff = None

    # Query usage
    if cutoff:
        results = db.query_parameterized(
            """
            SELECT model_key,
                   COUNT(*) as query_count,
                   SUM(total_tokens) as total_tokens,
                   SUM(estimated_cost) as total_cost,
                   AVG(latency_ms) as avg_latency
            FROM llm_usage
            WHERE username = ? AND timestamp >= ?
            GROUP BY model_key
            ORDER BY total_cost DESC
            """,
            (username, cutoff)
        )
    else:
        results = db.query_parameterized(
            """
            SELECT model_key,
                   COUNT(*) as query_count,
                   SUM(total_tokens) as total_tokens,
                   SUM(estimated_cost) as total_cost,
                   AVG(latency_ms) as avg_latency
            FROM llm_usage
            WHERE username = ?
            GROUP BY model_key
            ORDER BY total_cost DESC
            """,
            (username,)
        )

    # Format response...
```

**Admin Analytics Command:**

```python
@client.tree.command(name="admin_usage_stats", guilds=const.DEV_GUILD_IDS)
@app_commands.checks.has_permissions(administrator=True)
async def admin_usage_stats(interaction: discord.Interaction):
    """[Admin Only] View aggregate usage statistics."""
    db = Db()

    # Top users by cost
    top_users = db.query(
        """
        SELECT username,
               COUNT(*) as queries,
               SUM(total_tokens) as tokens,
               SUM(estimated_cost) as cost
        FROM llm_usage
        WHERE timestamp >= date('now', '-30 days')
        GROUP BY username
        ORDER BY cost DESC
        LIMIT 10
        """
    )

    # Model usage distribution
    model_usage = db.query(
        """
        SELECT model_key,
               COUNT(*) as queries,
               SUM(estimated_cost) as cost
        FROM llm_usage
        WHERE timestamp >= date('now', '-30 days')
        GROUP BY model_key
        ORDER BY queries DESC
        """
    )

    # Format and send...
```

**TODO:**
- [ ] Create `llm_usage` table migration
- [ ] Implement usage tracking in `LLMProvider.acompletion()`
- [ ] Add cost calculation with current provider pricing
- [ ] Implement `/my_usage` command
- [ ] Implement `/admin_usage_stats` command
- [ ] Add cost alerts for high usage
- [ ] Create monthly usage reports

### Phase 3: Usage Limits & Throttling

**Goal:** Prevent abuse and control costs per tier

**Add to `src/constants.py`:**

```python
# Usage limits per tier (per month)
TIER_USAGE_LIMITS = {
    'free': {
        'max_queries_per_day': 10,
        'max_queries_per_month': 100,
        'max_cost_per_month': 0.0,  # Only free models
        'models_allowed': TIER_MODEL_ACCESS['free']
    },
    'premium': {
        'max_queries_per_day': 100,
        'max_queries_per_month': 2000,
        'max_cost_per_month': 5.00,  # $5/month spending cap
        'models_allowed': TIER_MODEL_ACCESS['premium']
    },
    'plus': {
        'max_queries_per_day': None,  # Unlimited
        'max_queries_per_month': None,  # Unlimited
        'max_cost_per_month': 50.00,  # $50/month spending cap (safety)
        'models_allowed': TIER_MODEL_ACCESS['plus']
    }
}
```

**Add Usage Checking in `src/llm_analyzer.py`:**

```python
async def analyze_with_llm(self, username: str, user_question: str) -> str:
    """Analyze with usage limit checking."""

    # Check if user has exceeded limits
    usage_check = await self._check_usage_limits(username)

    if not usage_check['allowed']:
        return (
            f"⚠️ Usage limit reached: {usage_check['reason']}\n\n"
            f"Current usage: {usage_check['current_usage']}\n"
            f"Limit: {usage_check['limit']}\n\n"
            f"Consider upgrading to a higher tier with `/llm_upgrade` "
            f"or wait until {usage_check['reset_date']}."
        )

    # Continue with analysis...
    self.llm_provider = create_llm_provider(username=username)
    # ... rest of analysis

async def _check_usage_limits(self, username: str) -> dict:
    """Check if user has exceeded usage limits."""
    user_prefs = get_user_preferences()
    user_tier = user_prefs.get_user_tier(username)
    limits = const.TIER_USAGE_LIMITS[user_tier]

    db = Db()

    # Check daily query limit
    if limits['max_queries_per_day']:
        today = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        daily_queries = db.query_parameterized(
            "SELECT COUNT(*) FROM llm_usage WHERE username = ? AND timestamp >= ?",
            (username, today)
        )[0][0]

        if daily_queries >= limits['max_queries_per_day']:
            return {
                'allowed': False,
                'reason': 'Daily query limit exceeded',
                'current_usage': daily_queries,
                'limit': limits['max_queries_per_day'],
                'reset_date': (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            }

    # Check monthly query limit
    if limits['max_queries_per_month']:
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
        monthly_queries = db.query_parameterized(
            "SELECT COUNT(*) FROM llm_usage WHERE username = ? AND timestamp >= ?",
            (username, month_start)
        )[0][0]

        if monthly_queries >= limits['max_queries_per_month']:
            next_month = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1)
            return {
                'allowed': False,
                'reason': 'Monthly query limit exceeded',
                'current_usage': monthly_queries,
                'limit': limits['max_queries_per_month'],
                'reset_date': next_month.strftime('%Y-%m-%d')
            }

    # Check monthly cost limit
    if limits['max_cost_per_month']:
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
        monthly_cost = db.query_parameterized(
            "SELECT SUM(estimated_cost) FROM llm_usage WHERE username = ? AND timestamp >= ?",
            (username, month_start)
        )[0][0] or 0.0

        if monthly_cost >= limits['max_cost_per_month']:
            next_month = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1)
            return {
                'allowed': False,
                'reason': 'Monthly cost limit exceeded',
                'current_usage': f'${monthly_cost:.2f}',
                'limit': f'${limits["max_cost_per_month"]:.2f}',
                'reset_date': next_month.strftime('%Y-%m-%d')
            }

    return {'allowed': True}
```

**TODO:**
- [ ] Define usage limits per tier in constants
- [ ] Implement `_check_usage_limits()` in LLM analyzer
- [ ] Add limit warnings at 80% usage
- [ ] Create limit notification system
- [ ] Add override mechanism for admins

### Phase 4: Payment Integration

**Goal:** Allow users to upgrade tiers with payment

**Payment Provider Options:**
1. **Stripe** (Recommended)
   - Well-documented Discord bot integration
   - Subscription management built-in
   - PCI compliance handled
   - 2.9% + $0.30 per transaction

2. **PayPal**
   - Alternative for international users
   - Similar fee structure
   - Subscription support

3. **Cryptocurrency** (Optional)
   - For privacy-conscious users
   - Volatility risk
   - Manual processing

**Stripe Integration Example:**

```python
import stripe
stripe.api_key = os.getenv('STRIPE_API_KEY')

# Create pricing tiers
STRIPE_PRICES = {
    'premium': 'price_xxx',  # $4.99/month
    'plus': 'price_yyy'      # $19.99/month
}

@client.tree.command(name="upgrade", guilds=const.GUILD_IDS)
async def upgrade(
    interaction: discord.Interaction,
    tier: Literal['premium', 'plus']
):
    """Upgrade your account tier."""
    username = interaction.user.name
    user_prefs = get_user_preferences()
    current_tier = user_prefs.get_user_tier(username)

    # Check if already at or above this tier
    tier_hierarchy = {'free': 0, 'premium': 1, 'plus': 2}
    if tier_hierarchy[current_tier] >= tier_hierarchy[tier]:
        await interaction.response.send_message(
            f"You're already at the **{current_tier}** tier!",
            ephemeral=True
        )
        return

    # Create Stripe checkout session
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=interaction.user.email,  # May not be available
            client_reference_id=username,
            line_items=[{
                'price': STRIPE_PRICES[tier],
                'quantity': 1
            }],
            mode='subscription',
            success_url='https://your-domain.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://your-domain.com/cancel',
            metadata={
                'discord_username': username,
                'discord_user_id': str(interaction.user.id),
                'tier': tier
            }
        )

        # Send checkout link
        embed = discord.Embed(
            title=f"Upgrade to {tier.title()} Tier",
            description=f"Click the link below to complete your upgrade:",
            color=discord.Color.green()
        )
        embed.add_field(
            name="What you'll get:",
            value=_format_tier_benefits(tier),
            inline=False
        )
        embed.add_field(
            name="Payment Link:",
            value=f"[Complete Checkout]({checkout_session.url})",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        await interaction.response.send_message(
            "❌ Payment system error. Please contact support.",
            ephemeral=True
        )

# Webhook handler for Stripe events
@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        return 'Invalid signature', 400

    # Handle successful subscription
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        username = session['metadata']['discord_username']
        tier = session['metadata']['tier']

        # Upgrade user tier
        user_prefs = get_user_preferences()
        success = user_prefs.set_user_tier(username, tier)

        if success:
            # Log subscription
            db = Db()
            db.execute(
                """
                INSERT INTO subscriptions (
                    username, tier, stripe_subscription_id,
                    stripe_customer_id, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    tier,
                    session['subscription'],
                    session['customer'],
                    'active',
                    datetime.now().isoformat()
                )
            )

            logger.info(f"User {username} upgraded to {tier} tier")
        else:
            logger.error(f"Failed to upgrade {username} to {tier}")

    # Handle subscription cancellation
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']

        # Downgrade user to free tier
        db = Db()
        result = db.query_parameterized(
            "SELECT username FROM subscriptions WHERE stripe_subscription_id = ?",
            (subscription['id'],)
        )

        if result:
            username = result[0][0]
            user_prefs = get_user_preferences()
            user_prefs.set_user_tier(username, 'free')

            # Update subscription status
            db.execute(
                "UPDATE subscriptions SET status = 'cancelled' WHERE stripe_subscription_id = ?",
                (subscription['id'],)
            )

            logger.info(f"User {username} subscription cancelled, downgraded to free")

    return '', 200
```

**New Database Table:**

```sql
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    tier TEXT NOT NULL,
    stripe_subscription_id TEXT UNIQUE,
    stripe_customer_id TEXT,
    status TEXT NOT NULL,  -- 'active', 'cancelled', 'past_due'
    created_at TEXT NOT NULL,
    cancelled_at TEXT,

    FOREIGN KEY (username) REFERENCES user_preferences(username)
);

CREATE INDEX idx_subscriptions_username ON subscriptions(username);
CREATE INDEX idx_subscriptions_stripe_sub ON subscriptions(stripe_subscription_id);
```

**TODO:**
- [ ] Set up Stripe account and API keys
- [ ] Create product and pricing in Stripe dashboard
- [ ] Implement `/upgrade` command
- [ ] Create webhook endpoint for subscription events
- [ ] Add subscription status tracking in database
- [ ] Implement `/cancel_subscription` command
- [ ] Add billing portal access
- [ ] Create invoicing system
- [ ] Test payment flow end-to-end

### Phase 5: Pricing Strategy

**Recommended Pricing:**

| Tier | Monthly Price | Models Included | Use Case |
|------|---------------|-----------------|----------|
| **Free** | $0 | Local Ollama models (Llama 8B, Qwen 7B, Mistral 7B) | Casual users, privacy-focused, testing |
| **Premium** | $4.99 | Free + Budget cloud models (Claude Haiku, GPT-4o Mini, Together AI) | Active traders, daily analysis |
| **Plus** | $19.99 | Premium + Top-tier models (Claude Sonnet, GPT-4o) | Professional traders, advanced analysis |

**Pricing Rationale:**
- **Free tier:** Covers hosting costs, builds user base
- **Premium tier:** Covers API costs + small margin (~$3 profit after $2 API costs)
- **Plus tier:** Covers expensive models + healthy margin (~$15 profit after $5 API costs)

**Annual Pricing (Optional):**
- Premium: $49.99/year (save $10, ~17% discount)
- Plus: $199.99/year (save $40, ~17% discount)

**TODO:**
- [ ] Analyze actual API cost data from Phase 2
- [ ] Set pricing based on real usage patterns
- [ ] A/B test different price points
- [ ] Consider promotional pricing for early adopters
- [ ] Plan referral program incentives

---

## Activation Checklist

**When you're ready to enable paid tiers:**

### Step 1: Configuration
- [ ] Change `DEFAULT_USER_TIER = 'free'` in `src/constants.py`
- [ ] Set `TIER_USAGE_LIMITS` in constants
- [ ] Configure Stripe API keys in `.env`
- [ ] Update model pricing in `LLMProvider._calculate_cost()`

### Step 2: Database
- [ ] Run migration to create `llm_usage` table
- [ ] Run migration to create `subscriptions` table
- [ ] Backup existing `user_preferences` table
- [ ] Verify table indexes are created

### Step 3: Commands
- [ ] Deploy admin tier management commands
- [ ] Deploy `/my_usage` command
- [ ] Deploy `/upgrade` command
- [ ] Test all commands in dev guild first

### Step 4: Payment System
- [ ] Create Stripe products and prices
- [ ] Deploy webhook endpoint
- [ ] Test webhook with Stripe CLI
- [ ] Verify subscription lifecycle (create, cancel, renew)

### Step 5: Monitoring
- [ ] Set up cost alerts in Stripe dashboard
- [ ] Create daily usage reports
- [ ] Monitor top users by cost
- [ ] Track conversion rate (free → paid)

### Step 6: User Communication
- [ ] Announce tier system to users
- [ ] Provide migration period (e.g., 30 days grace)
- [ ] Send usage summaries before limiting
- [ ] Create FAQ about tiers and pricing

---

## Risk Mitigation

### API Cost Overruns
**Risk:** User makes thousands of expensive model queries

**Mitigations:**
- Implement usage limits per tier (Phase 3)
- Add cost alerts at 80% of limit
- Circuit breaker for runaway costs (auto-downgrade to free)
- Admin override to block abusive users

### Payment Failures
**Risk:** Stripe payment fails, but user still has access

**Mitigations:**
- Webhook handler downgrades on `subscription.deleted`
- Daily cron job to sync Stripe status
- Grace period (3 days) before downgrade
- Email notifications before downgrade

### Chargeback Fraud
**Risk:** User upgrades, uses expensive models, then disputes charge

**Mitigations:**
- Track usage per payment (can prove value delivered)
- Stripe fraud detection
- Require email verification for paid tiers
- Ban repeat offenders from paid tiers

### Model Pricing Changes
**Risk:** Anthropic/OpenAI increases API prices

**Mitigations:**
- Monitor provider pricing monthly
- Update `_calculate_cost()` when prices change
- Adjust tier pricing if costs increase significantly
- Communicate pricing changes to users 30 days in advance

---

## Future Enhancements

### Pay-As-You-Go Option
Allow users to pre-fund account and pay exact API costs + small markup:
- User deposits $10-$100
- Each query deducts actual cost × 1.5 markup
- No usage limits
- Refund unused balance on request

**Implementation:**
```sql
CREATE TABLE account_balance (
    username TEXT PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0.0,
    last_deposit TEXT,
    FOREIGN KEY (username) REFERENCES user_preferences(username)
);
```

### Team/Organization Plans
Allow Discord server owners to pay for all members:
- Server-level subscription
- All members get Premium/Plus tier
- Aggregate usage reporting
- Bulk pricing discounts

**Implementation:**
```sql
CREATE TABLE organization_subscriptions (
    guild_id TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    max_users INTEGER,
    stripe_subscription_id TEXT UNIQUE,
    status TEXT NOT NULL
);
```

### Custom Model Fine-Tuning
Allow Plus tier users to fine-tune models on their trading data:
- Upload trade history and outcomes
- Fine-tune Llama/Qwen on user's strategy
- Personal model hosted on user's API key
- Privacy-preserving (data never shared)

**Pricing:** $99 setup + $9.99/month hosting

### Referral Program
Reward users for bringing in paying customers:
- Free tier user refers Premium → 1 month free Premium
- Premium user refers Plus → $5 credit
- Plus user refers Plus → $10 credit

**Implementation:**
```sql
CREATE TABLE referrals (
    referrer_username TEXT,
    referred_username TEXT,
    tier_purchased TEXT,
    reward_amount REAL,
    created_at TEXT,
    FOREIGN KEY (referrer_username) REFERENCES user_preferences(username),
    FOREIGN KEY (referred_username) REFERENCES user_preferences(username)
);
```

---

## Analytics & Metrics

**Key Performance Indicators (KPIs) to Track:**

1. **User Acquisition:**
   - New users per day/week/month
   - Conversion rate (free → paid)
   - Churn rate (paid → cancelled)

2. **Revenue:**
   - Monthly Recurring Revenue (MRR)
   - Average Revenue Per User (ARPU)
   - Lifetime Value (LTV)

3. **Usage:**
   - Queries per user per tier
   - Average cost per query per tier
   - Most popular models per tier

4. **Costs:**
   - Total API costs per month
   - API cost per tier
   - Profit margin per tier

**Dashboard Queries:**

```sql
-- MRR by tier
SELECT tier, COUNT(*) as users, COUNT(*) * price as mrr
FROM subscriptions
WHERE status = 'active'
GROUP BY tier;

-- Conversion funnel
SELECT
    (SELECT COUNT(*) FROM user_preferences WHERE preference_key = 'user_tier' AND preference_value = 'free') as free_users,
    (SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND tier = 'premium') as premium_users,
    (SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND tier = 'plus') as plus_users;

-- Top users by usage cost
SELECT username, SUM(estimated_cost) as total_cost
FROM llm_usage
WHERE timestamp >= date('now', '-30 days')
GROUP BY username
ORDER BY total_cost DESC
LIMIT 20;

-- Model popularity
SELECT model_key, COUNT(*) as queries, SUM(estimated_cost) as cost
FROM llm_usage
WHERE timestamp >= date('now', '-30 days')
GROUP BY model_key
ORDER BY queries DESC;
```

---

## Legal & Compliance

**Required Documentation:**
- [ ] Terms of Service (mention API usage, limits, refunds)
- [ ] Privacy Policy (how usage data is stored)
- [ ] Refund Policy (pro-rated refunds within 30 days?)
- [ ] Acceptable Use Policy (no abuse, no reselling)

**Compliance Considerations:**
- **PCI DSS:** Stripe handles this (don't store card numbers)
- **GDPR:** Allow users to export/delete their data
- **CCPA:** Same as GDPR for California users
- **Tax:** Stripe Tax can handle sales tax automatically

**TODO:**
- [ ] Draft Terms of Service
- [ ] Draft Privacy Policy
- [ ] Add `/export_data` command (GDPR compliance)
- [ ] Add `/delete_account` command (GDPR compliance)
- [ ] Consult lawyer for final review

---

## Testing Strategy

**Before Launch:**

1. **Unit Tests:**
   - Test tier access validation
   - Test usage limit calculations
   - Test cost estimation accuracy

2. **Integration Tests:**
   - Test Stripe checkout flow
   - Test webhook processing
   - Test subscription lifecycle

3. **Load Tests:**
   - Simulate 100 concurrent users
   - Test rate limiting
   - Test database performance under load

4. **Beta Testing:**
   - Invite 10-20 trusted users
   - Offer free Premium for feedback
   - Monitor costs daily
   - Iterate on pricing based on feedback

**Test Scenarios:**
```python
# tests/revenue_model_test.py

def test_tier_access_validation():
    """Test that free tier can't access premium models."""
    user_prefs = UserPreferences(Db())
    user_prefs.set_user_tier('test_user', 'free')

    # Should fail - premium model
    success = user_prefs.set_llm_preference('test_user', 'claude-sonnet')
    assert not success

    # Should succeed - free model
    success = user_prefs.set_llm_preference('test_user', 'ollama-llama-8b')
    assert success

def test_usage_limits():
    """Test daily query limit enforcement."""
    # Create 10 queries today
    for i in range(10):
        create_test_query('test_user', 'ollama-llama-8b')

    # 11th query should be blocked for free tier
    result = check_usage_limits('test_user')
    assert not result['allowed']
    assert 'daily' in result['reason'].lower()

def test_cost_calculation():
    """Test API cost estimation."""
    provider = LLMProvider(model_key='claude-sonnet')

    # Test known token counts
    cost = provider._calculate_cost(
        prompt_tokens=1000,      # 1K tokens
        completion_tokens=500    # 500 tokens
    )

    # Claude Sonnet: $3/M input, $15/M output
    expected_cost = (1000/1_000_000)*3 + (500/1_000_000)*15
    assert abs(cost - expected_cost) < 0.001

def test_stripe_webhook():
    """Test subscription activation via webhook."""
    # Simulate Stripe webhook event
    event = {
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'metadata': {
                    'discord_username': 'test_user',
                    'tier': 'premium'
                },
                'subscription': 'sub_test123',
                'customer': 'cus_test456'
            }
        }
    }

    # Process webhook
    handle_stripe_webhook(event)

    # Verify tier upgraded
    user_prefs = UserPreferences(Db())
    tier = user_prefs.get_user_tier('test_user')
    assert tier == 'premium'
```

---

## Summary

**Current State:**
- ✅ Multi-model LLM integration complete
- ✅ Tier infrastructure in place
- ✅ User preferences system working
- ✅ All users default to 'plus' tier
- ✅ Commands show all models transparently

**To Enable Revenue Model:**
1. Change DEFAULT_USER_TIER to 'free' (1 line)
2. Implement usage tracking (Phase 2)
3. Implement usage limits (Phase 3)
4. Integrate Stripe payment (Phase 4)
5. Set pricing strategy (Phase 5)

**Estimated Implementation Time:**
- Phase 1 (Admin commands): 2-4 hours
- Phase 2 (Usage tracking): 4-6 hours
- Phase 3 (Limits): 2-3 hours
- Phase 4 (Payments): 6-8 hours
- Phase 5 (Pricing): 1-2 hours

**Total:** ~15-23 hours of development

**ROI Projections:**
- 100 free users → $0/month
- 20 premium users → $100/month (minus ~$40 API costs) = **$60 profit**
- 10 plus users → $200/month (minus ~$50 API costs) = **$150 profit**

**Total potential:** $210/month profit with 130 total users

---

## Contact & Support

**Questions about implementation?**
- Check this document first
- Review `src/user_preferences.py` for tier logic
- Review `src/llm_provider.py` for provider abstraction
- Test changes in dev guild first (`const.DEV_GUILD_IDS`)

**When you're ready to launch:**
1. Complete Phases 1-4
2. Beta test with trusted users
3. Announce publicly with 30-day grace period
4. Monitor costs daily
5. Iterate based on feedback

Good luck with monetization! 🚀
