# WheelHive

[![CI](https://github.com/sangelovich1/wheelhive/actions/workflows/ci.yml/badge.svg)](https://github.com/sangelovich1/wheelhive/actions/workflows/ci.yml)

Discord bot for options wheel strategy tracking with automated trade parsing, analytics, and AI-powered insights.

## Features

- **Automated Trade Tracking**: Parse trades from Discord messages and screenshots
- **Portfolio Analytics**: P/L tracking, position summaries, performance metrics
- **AI-Powered Insights**: LLM-based trade analysis, community sentiment, and AI tutor
- **Multi-Brokerage Support**: Import trades from Schwab, IBKR, Tastytrade, and more
- **Options Scanner**: Find optimal wheel strategy opportunities
- **Daily Digests**: Automated community activity summaries

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python src/bot.py          # Start Discord bot
python src/cli.py --help   # CLI commands
```

**Required environment variables:**
- `DISCORD_TOKEN` - Discord bot token
- `FINNHUB_API_KEY` - Market data API key
- `ANTHROPIC_API_KEY` - Claude API key for AI features

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

### AI-Assisted Development

Parts of this codebase were developed with assistance from Claude Code (Anthropic).
All AI-generated outputs are owned by the project and licensed under the MIT License.
