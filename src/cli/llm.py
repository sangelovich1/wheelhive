"""
LLM Command Group

User-facing commands for LLM model management and AI-powered analysis.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click

import constants as const
from db import Db
from llm_models import LLMModels
from user_preferences import UserPreferences


logger = logging.getLogger(__name__)


@click.group()
def llm():
    """
    LLM model preferences and AI-powered analysis.

    Manage your preferred AI model and use AI features for portfolio analysis,
    trading opportunities, and community insights.
    """


@llm.command("list-models")
@click.pass_context
def list_models(ctx):
    """
    List all available LLM models.

    Shows active models with their capabilities, speed, and cost tier.
    """
    db: Db = ctx.obj["db"]
    llm_models = LLMModels(db)

    try:
        models = llm_models.list_models(active_only=True)

        if not models:
            click.secho("No active models found.", fg="yellow")
            return

        # Get default model
        default_model = llm_models.get_default_model()
        default_key = default_model.model_key if default_model else None

        click.echo("\n📋 Available LLM Models:\n")

        for model in models:
            # Mark default with star
            marker = "⭐" if model.model_key == default_key else "  "

            # Color by cost tier
            tier_colors = {"free": "green", "budget": "cyan", "premium": "magenta"}
            color = tier_colors.get(model.cost_tier, "white")

            click.secho(f"{marker} {model.display_name}", fg=color, bold=True)
            click.echo(f"   Key: {model.model_key}")
            click.echo(f"   Provider: {model.provider}")
            click.echo(
                f"   Cost: {model.cost_tier.upper()} | Quality: {model.quality}/10 | Speed: {model.speed}"
            )
            click.echo(f"   Tool Calling: {'✓' if model.tool_calling else '✗'}")
            click.echo(f"   {model.description}")
            click.echo()

        if default_key:
            click.secho("⭐ = System default model", fg="blue")

    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        click.secho(f"✗ Error listing models: {e}", fg="red", err=True)


@llm.command("set-default")
@click.argument("model_key")
@click.option("--username", required=True, help="Username")
@click.pass_context
def set_default(ctx, model_key: str, username: str):
    """
    Set your preferred LLM model.

    MODEL_KEY: Model identifier (e.g., 'claude-sonnet', 'ollama-qwen-32b')
    """
    db: Db = ctx.obj["db"]
    prefs = UserPreferences(db)

    try:
        success = prefs.set_llm_preference(username, model_key)

        if success:
            click.secho(f"✓ Set default model to '{model_key}' for {username}", fg="green")
        else:
            click.secho(f"✗ Invalid or inactive model: {model_key}", fg="red", err=True)
            click.echo("\nRun 'cli.py llm list-models' to see available models.")

    except Exception as e:
        logger.error(f"Error setting default model: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("get-default")
@click.option("--username", required=True, help="Username")
@click.pass_context
def get_default(ctx, username: str):
    """
    Show your current default LLM model.
    """
    db: Db = ctx.obj["db"]
    prefs = UserPreferences(db)
    llm_models = LLMModels(db)

    try:
        model_key = prefs.get_llm_preference(username)
        model = llm_models.get_model(model_key)

        if model:
            click.echo(f"\n🤖 Current Model for {username}:\n")
            click.secho(f"   {model.display_name}", fg="cyan", bold=True)
            click.echo(f"   Key: {model.model_key}")
            click.echo(f"   Provider: {model.provider}")
            click.echo(f"   Cost: {model.cost_tier.upper()} | Quality: {model.quality}/10")
            click.echo(f"   {model.description}\n")
        else:
            click.secho(f"✗ Model not found: {model_key}", fg="red", err=True)

    except Exception as e:
        logger.error(f"Error getting default model: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("analyze")
@click.option("--username", required=True, help="Username")
@click.option("--account", default=const.ACCOUNT_ALL, help="Account to analyze (default: ALL)")
@click.option("--days", default=30, type=int, help="Days of history to analyze (default: 30)")
@click.pass_context
def analyze(ctx, username: str, account: str, days: int):
    """
    AI-powered portfolio analysis.

    Uses your preferred LLM model to analyze trading patterns, performance,
    and provide strategic insights.
    """
    db: Db = ctx.obj["db"]

    try:
        click.echo(f"\n🤖 Analyzing portfolio for {username}...")
        click.echo(f"   Account: {account}")
        click.echo(f"   History: {days} days")

        # Import here to avoid circular dependency
        from llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(db=db)
        result = analyzer.analyze_portfolio(username)

        click.echo("\n" + "=" * 70)
        click.echo(result)
        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error analyzing portfolio: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("opportunities")
@click.option("--username", required=True, help="Username")
@click.option("--symbol", help="Specific symbol to analyze (optional)")
@click.option(
    "--strategy",
    type=click.Choice(["conservative", "moderate", "aggressive"]),
    default="moderate",
    help="Risk strategy (default: moderate)",
)
@click.pass_context
def opportunities(ctx, username: str, symbol: str | None, strategy: str):
    """
    AI-powered trading opportunity analysis.

    Analyzes market conditions, portfolio positions, and community trends
    to identify potential trading opportunities.
    """
    db: Db = ctx.obj["db"]

    try:
        click.echo("\n🎯 Finding trading opportunities...")
        click.echo(f"   User: {username}")
        click.echo(f"   Strategy: {strategy}")
        if symbol:
            click.echo(f"   Symbol: {symbol}")

        # Import here to avoid circular dependency
        from llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(db=db)
        result = analyzer.find_opportunities(username)

        click.echo("\n" + "=" * 70)
        click.echo(result)
        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error finding opportunities: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("ask")
@click.argument("question", nargs=-1, required=True)
@click.option("--username", required=True, help="Username")
@click.option(
    "--context",
    type=click.Choice(["portfolio", "market", "general"]),
    default="general",
    help="Context for the question (default: general)",
)
@click.pass_context
def ask(ctx, question: tuple, username: str, context: str):
    """
    Ask the LLM a question.

    QUESTION: Your question (can be multiple words)

    Examples:
      cli.py llm ask --username user "What's my best performing trade?"
      cli.py llm ask --username user --context market "Should I buy TSLA calls?"
    """
    db: Db = ctx.obj["db"]

    try:
        # Join question words
        question_text = " ".join(question)

        click.echo(f"\n💬 Question: {question_text}")
        click.echo(f"   Context: {context}\n")

        # Import here to avoid circular dependency
        from llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(db=db)
        result = analyzer.analyze(username, question_text)

        click.echo("=" * 70)
        click.echo(result)
        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("community-sentiment")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--days", default=7, type=int, help="Days of history to analyze (default: 7)")
@click.option("--symbol", help="Specific symbol to analyze (optional)")
@click.pass_context
def community_sentiment(ctx, guild_id: int, days: int, symbol: str | None):
    """
    Analyze community sentiment from discussion channels.

    Uses AI to analyze trading discussions, sentiment, and trends
    in your Discord community.
    """
    db: Db = ctx.obj["db"]

    try:
        click.echo("\n💭 Analyzing community sentiment...")
        click.echo(f"   Guild: {guild_id}")
        click.echo(f"   History: {days} days")
        if symbol:
            click.echo(f"   Symbol: {symbol}")

        # Import here to avoid circular dependency
        from llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(db=db)
        # analyze_community_sentiment expects ticker (symbol), not guild_id
        result = analyzer.analyze_community_sentiment(ticker=symbol if symbol else "SPY")

        click.echo("\n" + "=" * 70)
        click.echo(result)
        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


@llm.command("community-news")
@click.option("--guild-id", type=int, required=True, help="Guild ID")
@click.option("--days", default=7, type=int, help="Days of history to analyze (default: 7)")
@click.pass_context
def community_news(ctx, guild_id: int, days: int):
    """
    Analyze news and announcements from news channels.

    Uses AI to summarize and analyze news, announcements, and market-moving
    information shared in your Discord community.
    """
    db: Db = ctx.obj["db"]

    try:
        click.echo("\n📰 Analyzing community news...")
        click.echo(f"   Guild: {guild_id}")
        click.echo(f"   History: {days} days")

        # Import here to avoid circular dependency
        from llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(db=db)
        result = analyzer.analyze_community_news(guild_id, days=days)  # type: ignore[attr-defined]

        click.echo("\n" + "=" * 70)
        click.echo(result)
        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Error analyzing news: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)


def _interactive_tutor_mode(db: Db, guild_id: int, username: str, model: str | None, verbose: bool):
    """
    Interactive conversation mode with context persistence.

    Maintains conversation history across multiple questions for natural
    multi-turn conversations with the AI tutor.
    """
    try:
        # Import here to avoid circular dependency
        from rag import WheelStrategyTutor
        from system_settings import get_settings

        # Get model from settings or use override
        settings = get_settings()
        if not model:
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

        # Initialize tutor
        click.echo("\n" + "=" * 70)
        click.secho("🎓 AI Tutor - Interactive Conversation Mode", fg="cyan", bold=True)
        click.echo("=" * 70)
        click.echo()
        click.echo(f"Model: {model}")
        click.echo(f"Guild: {guild_id}")
        click.echo(f"Username: {username}")
        click.echo()
        click.secho("Type your questions below.", fg="green")
        click.secho("Type 'exit', 'quit', or press Ctrl+C to end.", fg="green")
        click.secho("Type 'clear' to reset conversation context.", fg="green")
        if not verbose:
            click.secho("Type 'verbose on' to show source chunks.", fg="green")
        click.echo()

        tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id, username=username)

        # Conversation history for context
        conversation_history: list[tuple[str, str]] = []
        show_verbose = verbose

        while True:
            try:
                # Get user input
                user_input = click.prompt(click.style("You", fg="blue", bold=True), type=str)
                user_input = user_input.strip()

                # Handle special commands
                if user_input.lower() in ["exit", "quit", "q"]:
                    click.echo()
                    click.secho("👋 Goodbye!", fg="green")
                    break

                if user_input.lower() == "clear":
                    conversation_history = []
                    click.secho("✓ Conversation context cleared", fg="yellow")
                    continue

                if user_input.lower() == "verbose on":
                    show_verbose = True
                    click.secho("✓ Verbose mode enabled", fg="yellow")
                    continue

                if user_input.lower() == "verbose off":
                    show_verbose = False
                    click.secho("✓ Verbose mode disabled", fg="yellow")
                    continue

                if not user_input:
                    continue

                # Build context from conversation history
                context_prompt = user_input
                if conversation_history:
                    recent_context = "\n".join(
                        [
                            f"Previous Q: {q}\nPrevious A: {a[:200]}..."
                            for q, a in conversation_history[-2:]  # Last 2 exchanges for context
                        ]
                    )
                    context_prompt = f"{recent_context}\n\nCurrent question: {user_input}"

                # Determine question type
                question_indicators = [
                    "how",
                    "what",
                    "when",
                    "where",
                    "why",
                    "which",
                    "should",
                    "can",
                    "is",
                    "are",
                    "do",
                    "does",
                ]
                is_question_type = "?" in user_input or any(
                    user_input.lower().startswith(word) for word in question_indicators
                )

                # Query the tutor
                click.echo()
                click.secho("🤔 Thinking...", fg="yellow")

                if is_question_type:
                    result = tutor_instance.ask(
                        question=context_prompt, n_results=3, temperature=0.7
                    )
                else:
                    result = tutor_instance.explain_topic(
                        topic=context_prompt, n_results=5, temperature=0.7
                    )

                # Display answer
                click.echo()
                click.secho("AI:", fg="green", bold=True)
                click.echo(result["answer"])
                click.echo()

                # Show sources
                sources = result.get("sources", [])
                if sources:
                    click.secho("📖 Sources: " + ", ".join(sources), fg="blue", dim=True)
                    click.echo()

                # Show verbose details if enabled
                if show_verbose:
                    chunks = result.get("chunks", [])
                    if chunks:
                        click.echo("-" * 70)
                        click.secho("🔍 Source Chunks:", fg="yellow", dim=True)
                        for i, chunk in enumerate(chunks, 1):
                            click.echo(f"{i}. {chunk.get('text', 'N/A')[:150]}...")
                        click.echo("-" * 70)
                        click.echo()

                # Add to conversation history
                conversation_history.append((user_input, result["answer"]))

                # Keep only last 5 exchanges to avoid context bloat
                if len(conversation_history) > 5:
                    conversation_history = conversation_history[-5:]

            except KeyboardInterrupt:
                click.echo()
                click.secho("\n👋 Goodbye!", fg="green")
                break
            except EOFError:
                click.echo()
                click.secho("\n👋 Goodbye!", fg="green")
                break

    except FileNotFoundError as e:
        logger.error(f"Vector store not found: {e}", exc_info=True)
        click.secho("\n✗ AI Tutor Not Initialized", fg="red", err=True)
        click.echo("\nThe training materials vector store hasn't been created yet.")
        click.echo("\nSetup Required:")
        click.echo("  python scripts/rag/create_vector_store.py")
        click.echo()
    except Exception as e:
        logger.error(f"Error in interactive mode: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}", fg="red", err=True)


@llm.command("tutor")
@click.argument("question", required=False)
@click.option("--guild-id", type=int, required=True, help="Guild ID for guild-specific FAQs")
@click.option(
    "--username", type=str, required=True, help="Discord username for personalized responses"
)
@click.option("--model", default=None, help="Override default model (e.g., claude-sonnet, gpt-4)")
@click.option("--verbose", is_flag=True, help="Show source chunks and metadata")
@click.option("--interactive", is_flag=True, help="Start interactive conversation mode")
@click.pass_context
def tutor(
    ctx,
    question: str | None,
    guild_id: int,
    username: str,
    model: str | None,
    verbose: bool,
    interactive: bool,
):
    """
    Ask the AI tutor about wheel strategy with RAG-enhanced answers.

    The tutor uses Retrieval-Augmented Generation (RAG) to provide accurate
    answers based on training materials and guild-specific FAQs.

    Examples:

        # Ask a single question
        python src/cli.py llm tutor "What is STO?" --guild-id 1349592236375019520 --username sangelovich

        # Interactive conversation mode with context
        python src/cli.py llm tutor --interactive --guild-id 1349592236375019520 --username sangelovich

        # Ask with guild-specific context (includes user's watchlist, trades, etc.)
        python src/cli.py llm tutor "What are good tickers on my watchlist?" --guild-id 1349592236375019520 --username sangelovich

        # Use a specific model
        python src/cli.py llm tutor "Explain covered calls" --model claude-opus --guild-id 1349592236375019520 --username sangelovich

        # Show detailed sources
        python src/cli.py llm tutor "How to select strikes?" --verbose --guild-id 1349592236375019520 --username sangelovich
    """
    db: Db = ctx.obj["db"]

    # Handle interactive mode
    if interactive:
        _interactive_tutor_mode(db, guild_id, username, model, verbose)
        return

    # Single question mode - require question argument
    if not question:
        click.secho("✗ Error: Question required in single-question mode", fg="red", err=True)
        click.echo("Use --interactive for conversation mode, or provide a QUESTION argument")
        return

    try:
        click.echo("\n🎓 AI Tutor is thinking...")
        click.echo(f"   Guild: {guild_id}")
        click.echo(f"   Username: {username}")
        if model:
            click.echo(f"   Model: {model}")

        # Import here to avoid circular dependency
        from rag import WheelStrategyTutor
        from system_settings import get_settings

        # Get model from settings or use override
        settings = get_settings()
        if not model:
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

        # Initialize tutor with username
        tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id, username=username)

        # Determine if this is a question or topic to explain
        question_indicators = [
            "how",
            "what",
            "when",
            "where",
            "why",
            "which",
            "should",
            "can",
            "is",
            "are",
            "do",
            "does",
        ]
        is_question_type = "?" in question or any(
            question.lower().startswith(word) for word in question_indicators
        )

        # Run RAG query
        if is_question_type:
            result = tutor_instance.ask(question=question, n_results=3, temperature=0.7)
            query_type = "Question"
        else:
            result = tutor_instance.explain_topic(topic=question, n_results=5, temperature=0.7)
            query_type = "Topic"

        # Display results
        click.echo("\n" + "=" * 70)
        click.secho(f"{query_type}: {question}", fg="cyan", bold=True)
        click.echo("=" * 70)
        click.echo()
        click.echo(result["answer"])
        click.echo()

        # Show sources
        sources = result.get("sources", [])
        if sources:
            click.echo("=" * 70)
            click.secho("📖 Training Materials Used:", fg="blue", bold=True)
            click.echo("=" * 70)
            for i, source in enumerate(sources, 1):
                click.echo(f"{i}. {source}")
            click.echo()

        # Show verbose details if requested
        if verbose:
            chunks = result.get("chunks", [])
            if chunks:
                click.echo("=" * 70)
                click.secho("🔍 Source Chunks (Verbose):", fg="yellow", bold=True)
                click.echo("=" * 70)
                for i, chunk in enumerate(chunks, 1):
                    click.echo(f"\n--- Chunk {i} ---")
                    click.echo(f"Text: {chunk.get('text', 'N/A')[:200]}...")
                    click.echo(f"Metadata: {chunk.get('metadata', {})}")
                click.echo()

        click.secho("✓ Query completed successfully", fg="green")

    except FileNotFoundError as e:
        logger.error(f"Vector store not found: {e}", exc_info=True)
        click.secho("\n✗ AI Tutor Not Initialized", fg="red", err=True)
        click.echo("\nThe training materials vector store hasn't been created yet.")
        click.echo("\nSetup Required:")
        click.echo("  python scripts/rag/create_vector_store.py")
        click.echo()
    except Exception as e:
        logger.error(f"Error in tutor: {e}", exc_info=True)
        click.secho(f"✗ Error: {e}", fg="red", err=True)
