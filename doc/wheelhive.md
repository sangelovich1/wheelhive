# WheelHive User Guide

**Where Wheel Traders Multiply Their Intelligence**

Version 0.7 | wheelhive.ai

---

## Introduction

WheelHive is an AI-powered Discord bot designed exclusively for wheel strategy traders. Track trades, analyze performance, generate comprehensive reports, and leverage community intelligence—all inside Discord.

### Key Features

✅ **Multi-Account Support** - Track IRA, Joint, Taxable, and more
✅ **Automated Imports** - Upload broker CSVs (Fidelity, Schwab, IBKR, Robinhood)
✅ **Advanced Analytics** - Trading stats, profit reports, symbol analysis
✅ **Options Scanner** - Find trade opportunities based on Greeks, IV, and liquidity
✅ **Natural Language Entry** - Record trades with simple commands
✅ **PDF Reports** - Professional profit summaries and symbol breakdowns

---

## Getting Started

Type `/` in Discord to see all available commands. Look for **WheelHive** commands in the slash command menu.

### Multi-Account Support

WheelHive supports tracking multiple trading accounts. Most commands require you to specify an account:

- Use a specific account name: `IRA`, `Joint`, `Taxable`
- Use `ALL` (case-insensitive) to view data across all accounts

**Tip:** Use `/my_accounts` to see all your accounts with trade data.

---

## Quick Command Reference

| Command | Description |
|---------|-------------|
| `/about` | Bot version, author, contributors, and uptime |
| `/delete` | Delete a transaction by ID |
| `/delete_all` | Delete all transactions for a specific account |
| `/download` | Download your transactions as CSV files |
| `/extrinsic_value` | Calculate extrinsic value for options |
| `/help` | Download this user guide as PDF |
| `/my_accounts` | List all your trading accounts |
| `/my_trades` | View your trades, shares, dividends, or deposits |
| `/my_trade_stats` | View your trading statistics |
| `/my_watchlist` | View your watchlist symbols |
| `/my_watchlist_add` | Add symbols to your watchlist |
| `/report_profit` | Generate profit summary report |
| `/report_symbol` | Generate ETF/symbol details report |
| `/report_options_pivot` | Generate options pivot report (current year) |
| `/scan_puts` | Scan PUT options chains for trade candidates |
| `/scan_calls` | Scan CALL options chains for trade candidates |
| `/schedule_potus` | View the POTUS schedule |
| `/trade` | Record new transactions |
| `/upload` | Upload trades from broker CSV files |

---

## Command Details

### `/about`

Shows bot information including version, contributors, and uptime.

**Example:** `/about`

---

### `/delete`

Delete a specific transaction by its ID.

**Required Parameters:**
- **table**: Select the data type (Options, Dividends, Shares, Deposits, Watchlist)
- **id**: The transaction ID (visible in `/my_trades` or `/my_watchlist`)

**Example:** `/delete table:Options id:1234`

**Note:** To delete all transactions for an account, use `/delete_all` instead.

---

### `/delete_all`

Delete all transactions for a specific account. **Use with caution!**

**Required Parameters:**
- **account**: The account name (e.g., `IRA`, `Joint`)

**Example:** `/delete_all account:IRA`

**Important:** This permanently deletes all options, dividends, shares, and deposits for the specified account.

---

### `/download`

Download all your transactions as CSV files in a zip archive.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts

**Example:** `/download account:ALL`

**Result:** You'll receive a zip file containing:
- `trades.csv` - Options trades
- `dividends.csv` - Dividend payments
- `shares.csv` - Share transactions
- `deposits.csv` - Deposits and withdrawals

---

### `/extrinsic_value`

Calculate the intrinsic and extrinsic value for option strikes.

**Required Parameters:**
- **ticker**: Stock symbol (e.g., `AAPL`)
- **strikes**: Strike price(s) in flexible formats:
  - Single strike: `150`
  - List: `150,155,160`
  - Range: `150-170`
  - Range with increment: `150-170(5)` (150, 155, 160, 165, 170)
  - Combined: `150-170(5),175,180`

**Example:** `/extrinsic_value ticker:AAPL strikes:150-170(5)`

**Result:** Table showing intrinsic and extrinsic value for each strike.

---

### `/help`

Download the complete user guide as a PDF.

**Example:** `/help`

---

### `/my_accounts`

List all your trading accounts that have transaction data.

**Example:** `/my_accounts`

**Result:** Shows all account names with a tip about using `ALL` in commands.

---

### `/my_trades`

View your transactions with filtering and pagination.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts
- **table**: Type of data to view (Options, Dividends, Shares, Deposits)

**Optional Parameters:**
- **symbol**: Filter by ticker symbol (e.g., `TSLL`)
- **page**: Page number for paginated results (default: 1)

**Examples:**
- `/my_trades account:IRA table:Options` - View all options for IRA account
- `/my_trades account:Joint table:Dividends` - View dividends
- `/my_trades account:ALL table:Options symbol:TSLL` - View TSLL options across all accounts
- `/my_trades account:IRA table:Shares page:2` - View page 2 of share transactions

**Result:** Table of transactions sorted by date (newest first).

---

### `/my_trade_stats`

View trading statistics including monthly summaries and symbol breakdowns.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts

**Example:** `/my_trade_stats account:ALL`

**Result:**
- Monthly premium collected summary
- Current month breakdown by symbol
- Win/loss statistics

---

### `/my_watchlist`

View your watchlist symbols and their IDs.

**Example:** `/my_watchlist`

**Result:** Table showing ID and Symbol for each watchlist entry.

**Note:** Use the ID with `/delete` to remove symbols from your watchlist.

---

### `/my_watchlist_add`

Add symbols to your watchlist for use with the scanner.

**Required Parameters:**
- **symbols**: Comma or space-separated list of ticker symbols

**Examples:**
- `/my_watchlist_add symbols:TSLL MSTU CRCL`
- `/my_watchlist_add symbols:AAPL, MSFT, GOOGL`

**Result:** Confirmation of which symbols were added or already existed.

---

### `/report_profit`

Generate a profit summary PDF report showing performance across all traded symbols.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts

**Optional Parameters:**
- **symbol_exclude**: Space or comma-separated list of symbols to exclude from the report

**Examples:**
- `/report_profit account:ALL` - All symbols across all accounts
- `/report_profit account:IRA` - All symbols in IRA account
- `/report_profit account:Joint symbol_exclude:SPAXX` - Exclude SPAXX from report
- `/report_profit account:ALL symbol_exclude:SPAXX,FDRXX` - Exclude multiple symbols

**Result:** Downloadable PDF with:
- Summary statistics (premium collected, realized/unrealized gains, dividends)
- Overall income breakdown (options, dividends, stock gains)
- Per-symbol detailed breakdown in appendix

**Note:** Reports reflect the date range of your loaded transactions.

---

### `/report_symbol`

Generate a detailed ETF/symbol analysis PDF report for a specific ticker.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts
- **symbol**: Ticker symbol to analyze (e.g., `TSLL`, `AAPL`)

**Examples:**
- `/report_symbol account:IRA symbol:TSLL`
- `/report_symbol account:ALL symbol:AAPL`

**Result:** Downloadable PDF with:
- Summary statistics for the symbol (premium, dividends, gains, shares owned)
- Current market price and unrealized gains
- Complete transaction history in appendix (options, shares, dividends)

**Note:** Reports reflect the date range of your loaded transactions.

---

### `/report_options_pivot`

Generate an options pivot PDF report showing premium collected by symbol for the current year.

**Required Parameters:**
- **account**: Account name or `ALL` for all accounts

**Examples:**
- `/report_options_pivot account:IRA`
- `/report_options_pivot account:ALL`

**Result:** Downloadable PDF with:
- Summary table showing premium collected per symbol
- Sorted by premium (highest to lowest)
- Grand total at bottom
- Current year data only (2025)

**Note:** This report filters automatically to the current calendar year and includes both winning (positive premium) and losing (negative premium) trades.

---

### `/scan_puts` and `/scan_calls`

Scan PUT or CALL options chains to find trade candidates based on delta, expiration, and other criteria.

**Commands:**
- `/scan_puts` - Scan PUT options
- `/scan_calls` - Scan CALL options

**Optional Parameters (all have defaults):**
- **symbols**: Comma-separated symbols to scan (e.g., `ETHU,TSLA,MSTU`). Default: your watchlist
- **delta_min**: Minimum delta threshold (default: 0.01)
- **delta_max**: Maximum delta threshold (default: 0.30)
- **max_expiration_days**: Maximum days to expiration (default: 7)
- **iv_min**: Minimum implied volatility % (default: 15.0)
- **open_interest_min**: Minimum open interest (default: 10)
- **volume_min**: Minimum volume (default: 0)
- **strike_proximity**: Maximum distance from current price % (default: 40%)
- **top_candidates**: Number of top results to return (default: 50)

**Examples:**
- Scan your watchlist: `/scan_puts`
- Scan specific symbols: `/scan_puts symbols:ETHU,TSLA,MSTU`
- Custom delta range: `/scan_puts delta_min:0.05 delta_max:0.20`
- Longer expiration: `/scan_puts max_expiration_days:14`
- High IV only: `/scan_puts iv_min:50`
- More results: `/scan_puts top_candidates:100`

**Result:** PNG image with top candidates (up to 50 by default), sorted by composite score (highest to lowest) and color-coded for quick analysis.

**Columns Displayed:**
- Symbol, Strike, Mon% (Moneyness), Exp, DTE (Days to Expiration)
- Bid, Delta, Theta, Gamma, Vol (Volume), OI (Open Interest), IV (Implied Volatility)
- Ret% (premium as percentage of strike), Score, Comment

**Comment Column:**
- **Δ Est.**: Delta was estimated using Black-Scholes model (provider data missing)
- *Blank*: All Greeks from market data provider

#### Scoring System

Options are sorted by a composite score (0-100, higher is better) based on:
- **Delta**: Moderate values preferred (optimal range 0.40-0.70)
- **Theta**: Time decay rate (higher is better for sellers)
- **Gamma**: Delta sensitivity (optimal range 0.10-0.30)
- **Open Interest**: Liquidity indicator (100+ is optimal)
- **IV**: Volatility level (20-100% range, higher provides more premium)

The score helps identify options with good liquidity, favorable Greeks, and strong premium potential.

#### Color Coding Guide

**Moneyness** (Strike vs Current Price):
- 🟢 **Green (-5% to -15%)**: Sweet spot - good premium with reasonable safety
- 🟡 **Yellow (-15% to -25%)**: Safe but far OTM - lower premium
- ⚪ **White (< -25%)**: Very far OTM - minimal premium
- 🔴 **Red (≥ 0%)**: ATM or ITM - risky, high assignment risk

**Implied Volatility (IV)**:
- 🟢 **Green (60-100%)**: Sweet spot - good premium without extreme risk
- 🟡 **Yellow (> 100%)**: High premium but very volatile/risky
- ⚪ **White (40-60%)**: Moderate volatility
- 🔴 **Red (< 40%)**: Low premium - not worth the capital

**Return %**:
- 🟢 **Green (≥ 2.0%)**: Excellent premium
- 🟡 **Yellow (≥ 1.0%)**: Good premium
- ⚪ **White (< 1.0%)**: Lower premium

#### Technical Details

- Scanner uses 3-minute cache to reduce API throttling
- Delta estimation: When market data providers don't return Greeks, the scanner estimates delta using the Black-Scholes model
- Multi-provider fallback: Finnhub → YFinance → AlphaVantage
- Long scans (30+ symbols) run in background thread to keep Discord responsive

#### Setup

Before using scan commands:
1. Add symbols to your watchlist with `/my_watchlist_add`
2. View your watchlist with `/my_watchlist`
3. Remove unwanted symbols with `/delete` (select Watchlist table)

Or use the `symbols` parameter to scan directly without modifying your watchlist.

---

### `/schedule_potus`

View the POTUS schedule from https://rollcall.com/factbase/trump/topic/calendar/

**Optional Parameters:**
- **sdate**: Schedule date in format `m/d` or `m/d/Y` (default: today)

**Examples:**
- `/schedule_potus` - Today's schedule
- `/schedule_potus sdate:5/28` - May 28 of current year
- `/schedule_potus sdate:5/28/2025` - May 28, 2025

**Result:** Image of the POTUS schedule for the requested date.

**Note:** Schedule must be cached by daily cron job to be available.

---

### `/trade`

Record one or more transactions using natural language format.

**Required Parameters:**
- **transaction_date**: Date in format `m/d/Y` (e.g., `5/28/2025`)
- **trade**: Transaction details (one per line)

**Optional Parameters:**
- **share_trade**: Post to channel if `true` (default: `false`)

#### Supported Transaction Formats

**Options:**
```
STO 2x MSTU 8/1 8P @ .16
STO 2x MSTU 8/1 $8P @ $.16
BTC 10x TSLL 8/1 10.5P @ .11
BTO 5x AAPL 9/15 150C @ 2.50
STC 5x AAPL 9/15 150C @ 3.00
```

**Dividends:**
```
Dividend QQQI 63.66
Dividend YMAX $13.47
```

**Deposits/Withdrawals:**
```
Deposit 20,000
Withdrawal 15,000
```

**Share Transactions:**
```
Buy 300 shares MSTU @ 10
Sell 400 shares CONL at 28
```

**Dollar signs and commas in amounts are optional.**

**Result:**
- If validation fails: Private message showing the first error and all entered data
- If successful: Private message confirming number of trades added

---

### `/upload`

Upload and import trades from your broker's CSV export. The bot automatically detects the broker format.

**Required Parameters:**
- **account**: Account name for these trades (e.g., `IRA`, `Joint`)
- **attachment**: Select CSV file from your computer

**Optional Parameters:**
- **append_only**: Set to `True` to append data without deleting existing trades (default: `False`)

**How It Works:**
1. Bot automatically identifies the broker (Fidelity, Robinhood, Schwab, IBKR)
2. Extracts options, dividends, shares, and deposits
3. Determines date range from transactions
4. Deletes existing transactions in that date range (unless append_only is True)
5. Imports new transactions

**Example:** `/upload account:IRA attachment:[file]`

**Supported Brokers:**
- Fidelity
- Robinhood
- Charles Schwab
- Interactive Brokers (IBKR)

**Result:** Summary showing:
- Detected broker format with confidence level
- Number of transactions imported by type
- Number of existing transactions deleted (if applicable)

**Tip:** Use append_only when importing from multiple brokerages or when you don't want to replace existing data.

---

## Tips and Best Practices

### Account Management
- Use descriptive account names: `IRA`, `Joint`, `Taxable`, etc.
- Check `/my_accounts` to see all your accounts
- Use `ALL` in commands to view aggregate data

### Data Import
- Upload broker CSVs regularly to keep data current
- The bot handles duplicates automatically by date range
- Use `/delete_all account:YourAccount` before a fresh import if needed

### Watchlist for Scanner
- Keep your watchlist updated with symbols you're actively trading
- Remove old symbols with `/delete` (Watchlist table)
- Scanner uses your watchlist to find opportunities

### Reports
- Reports reflect your loaded transaction history
- For accurate YTD reports, import all transactions from January 1
- Use `/report_profit` with `symbol_exclude:SPAXX,FDRXX` to exclude cash-like symbols
- Use `/report_symbol` to get detailed analysis for a specific ticker

### Transaction History
- Use `/my_trades` with filters to find specific transactions
- IDs shown in results can be used with `/delete`
- Download CSV backups with `/download` periodically

---

## Broker Export Guide

All broker formats are auto-detected by WheelHive when you upload.

### Fidelity

1. Log in to Fidelity.com
2. Navigate to "Accounts & Trade" → "Portfolio"
3. Click "Download" → "Transaction History"
4. Select date range and CSV format
5. Upload to bot with `/upload account:YourAccount attachment:[file]`

---

### Interactive Brokers (IBKR)

IBKR Activity Statements provide the most comprehensive transaction export. WheelHive automatically extracts options, stocks, and dividends from a single CSV file.

#### What Gets Imported

From a single IBKR Activity Statement, WheelHive extracts:
- ✅ **Options trades** (STO, BTC, BTO, STC) with strikes, expirations, premiums
- ✅ **Stock trades** (Buy, Sell) with quantities and prices
- ✅ **Dividends** with automatic symbol extraction

#### Step-by-Step Export (Web Portal)

1. **Log in to IBKR Client Portal**
   - Go to https://www.interactivebrokers.com
   - Click "Login" → "Client Portal"

2. **Navigate to Reports**
   - Click "Performance & Reports" in the top menu
   - Select "Statements" from the dropdown

3. **Generate Activity Statement**
   - **Report Type:** Activity
   - **Format:** CSV (required)
   - **Period:** Choose your date range
     - "Last 30 Days" for recent activity
     - "Custom Date Range" for specific periods
   - **Language:** English

4. **Configure Sections (Optional)**
   - Click "Customize" to reduce file size
   - Minimum required sections:
     - ☑️ Trades (for options and stocks)
     - ☑️ Dividends (for dividend tracking)
   - All other sections are ignored by WheelHive

5. **Generate & Download**
   - Click "Run" or "Generate"
   - Wait for report generation (~30 seconds)
   - Click "Download" and save the CSV

#### Step-by-Step Export (Desktop TWS)

1. Open **Trader Workstation (TWS)**
2. Click **Reports** → **Activity Statement**
3. Select:
   - **Format:** CSV
   - **Date Range:** Your desired period
4. Ensure "Trades" and "Dividends" sections are enabled
5. Click **Generate** and save the CSV

#### Uploading to WheelHive

Once you have the CSV file:

```
/upload account:IBKR_Main attachment:[select your CSV file]
```

**Result Example:**
```
Format: ibkr (detected with 95% confidence)
Processing trades
   Trades processed 91
Processing dividends
   Dividends processed 2
Processing shares
   Shares processed 10
```

#### Account Naming Tips

Use descriptive account names when uploading:
- `IBKR_Main` - Your primary IBKR account
- `IBKR_Roth` - IBKR Roth IRA
- `IBKR_Trading` - IBKR active trading account

This allows you to:
- Track multiple IBKR accounts separately
- Filter reports by account
- View combined data with `account:ALL`

#### Important Notes

**File Format:**
- Must be CSV format (not PDF, Excel, or HTML)
- File starts with `Statement,Header,Field Name,Field Value`
- WheelHive automatically detects the correct sections

**Date Handling:**
- IBKR uses YYYY-MM-DD format (handled automatically)
- WheelHive determines date range from your transactions
- Existing transactions in that date range are replaced (unless you use `append_only:True`)

**Multi-Section Files:**
- IBKR exports contain many sections (performance, positions, etc.)
- WheelHive scans the entire file and extracts only relevant sections
- No need to manually edit or clean the file

#### Common Issues

**"Format not supported"**
- Verify you selected CSV format (not PDF or Excel)
- Check that the file isn't corrupted (can it open in a spreadsheet?)

**"No transactions found"**
- Ensure your date range includes actual trades
- Verify "Trades" and "Dividends" sections were enabled in the export
- Try a different date range with known activity

**Duplicate transactions after upload**
- By default, WheelHive replaces existing transactions in the date range
- If you see duplicates, use `/delete_all account:YourAccount` and re-upload
- Or use `/my_trades` to identify and `/delete` specific duplicates

#### Advanced: Append Mode

If you want to add transactions without replacing existing data:

```
/upload account:IBKR_Main attachment:[file] append_only:True
```

**Use append mode when:**
- Importing from multiple date ranges
- Adding trades to an existing account without disrupting other data
- Testing imports before committing

**Use replace mode (default) when:**
- Re-importing corrected data
- Starting fresh with clean data
- Updating an existing time period

---

### Robinhood

1. Log in to Robinhood.com (web version)
2. Profile → "Account" → "Statements & History"
3. Select month and download CSV
4. Upload to bot with `/upload account:YourAccount attachment:[file]`

---

### Schwab

1. Log in to Schwab.com
2. Navigate to "Accounts" → "History"
3. Select "Export" → "All Transactions"
4. Choose CSV format and date range
5. Upload to bot with `/upload account:YourAccount attachment:[file]`

---

## Support

For issues or questions:
- Check this documentation with `/help`
- Visit [wheelhive.ai](https://wheelhive.ai)
- Join our Discord community

**Version:** 0.7
**Author:** sangelovich
**Contributors:** sangelovich, darkminer, brockhamilton.88, spam4elvis, mslick1, crazymonkey7543

---

**WheelHive** - Where Wheel Traders Multiply Their Intelligence

wheelhive.ai
