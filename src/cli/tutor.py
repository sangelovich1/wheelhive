"""
AI Tutor Command Group

Interactive AI tutor for learning the wheel strategy using RAG-enhanced responses.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

import click


logger = logging.getLogger(__name__)


@click.group()
def tutor():
    """
    AI tutor for learning the wheel strategy.

    Uses RAG (Retrieval-Augmented Generation) to answer questions using
    the community's official training materials.
    """


@tutor.command("ask")
@click.option("--question", "-q", required=True, help="Question to ask the AI tutor")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for security - prevents data leakage)")
@click.option("--model", default="claude-sonnet", help="LLM model to use (default: claude-sonnet)")
@click.option("--n-results", type=int, default=3, help="Number of training materials to retrieve (default: 3)")
@click.option("--temperature", type=float, default=0.7, help="LLM temperature 0.0-2.0 (default: 0.7)")
@click.option("--username", help="Optional username for personalized responses (watchlist, etc.)")
@click.option("--show-sources", is_flag=True, help="Show source documents cited")
@click.pass_context
def ask(ctx, question, model, n_results, temperature, guild_id, username, show_sources):
    """
    Ask the AI tutor a question about the wheel strategy.

    The tutor uses RAG to retrieve relevant training materials and generates
    educational responses with citations.

    SECURITY: guild-id is required to prevent cross-guild data leakage.
    Use your guild's ID (find it with: python src/cli.py admin list-guilds)

    Examples:
        python src/cli.py tutor ask -q "How do I pick a strike price?" --guild-id 1349592236375019520
        python src/cli.py tutor ask -q "What is assignment?" --guild-id 1349592236375019520 --show-sources
        python src/cli.py tutor ask -q "Explain covered calls" --guild-id 1405962109262757980 --model ollama-qwen-32b
    """
    try:
        click.echo("\n🤖 AI Wheel Strategy Tutor")
        click.echo(f"   Question: {question}")
        click.echo(f"   Model: {model}")
        click.echo()

        # Import here to avoid circular dependency
        from rag import WheelStrategyTutor

        tutor = WheelStrategyTutor(model=model, guild_id=guild_id, username=username)
        result = tutor.ask(
            question=question,
            n_results=n_results,
            temperature=temperature
        )

        click.echo("=" * 70)
        click.echo(result["answer"])
        click.echo("=" * 70)

        if show_sources and result["sources"]:
            click.echo()
            click.echo("📚 Sources cited:")
            for source in result["sources"]:
                click.echo(f"   • {source}")

        click.echo()

    except Exception as e:
        logger.error(f"Error in tutor: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}", fg="red", err=True)
        click.echo()
        if "vector store not initialized" in str(e).lower() or "No such file" in str(e):
            click.secho("💡 Hint: Run vector store setup first:", fg="yellow")
            click.secho("   python scripts/rag/create_vector_store.py", fg="yellow")


@tutor.command("learn")
@click.option("--topic", "-t", required=True, help="Topic to learn about")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for security - prevents data leakage)")
@click.option("--model", default="claude-sonnet", help="LLM model to use (default: claude-sonnet)")
@click.option("--n-results", type=int, default=5, help="Number of training materials (default: 5)")
@click.option("--temperature", type=float, default=0.7, help="LLM temperature 0.0-2.0 (default: 0.7)")
@click.option("--username", help="Optional username for personalized responses (watchlist, etc.)")
@click.option("--show-sources", is_flag=True, help="Show source documents used")
@click.pass_context
def learn(ctx, topic, model, n_results, temperature, guild_id, username, show_sources):
    """
    Learn about wheel strategy topics with comprehensive explanations.

    Use this for educational queries that need thorough coverage.

    SECURITY: guild-id is required to prevent cross-guild data leakage.

    Examples:
        python src/cli.py tutor learn -t "assignment" --guild-id 1349592236375019520
        python src/cli.py tutor learn -t "covered calls" --guild-id 1349592236375019520
        python src/cli.py tutor learn -t "strike selection" --guild-id 1405962109262757980 --show-sources
    """
    try:
        click.echo("\n🤖 AI Wheel Strategy Tutor")
        click.echo(f"   Topic: {topic}")
        click.echo(f"   Model: {model}")
        click.echo()

        # Import here to avoid circular dependency
        from rag import WheelStrategyTutor

        tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id, username=username)
        result = tutor_instance.explain_topic(
            topic=topic,
            n_results=n_results,
            temperature=temperature
        )

        click.echo("=" * 70)
        click.echo(result["answer"])
        click.echo("=" * 70)

        if show_sources and result["sources"]:
            click.echo()
            click.echo("📚 Training materials used:")
            for source in result["sources"]:
                click.echo(f"   • {source}")

        click.echo()

    except Exception as e:
        logger.error(f"Error in tutor: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}", fg="red", err=True)
        click.echo()
        if "vector store not initialized" in str(e).lower() or "No such file" in str(e):
            click.secho("💡 Hint: Run vector store setup first:", fg="yellow")
            click.secho("   python scripts/rag/create_vector_store.py", fg="yellow")


@tutor.command("interactive")
@click.option("--guild-id", type=int, required=True, help="Guild ID (required for security - prevents data leakage)")
@click.option("--model", default="claude-sonnet", help="LLM model to use (default: claude-sonnet)")
@click.option("--temperature", type=float, default=0.7, help="LLM temperature (default: 0.7)")
@click.pass_context
def interactive(ctx, model, temperature, guild_id):
    """
    Interactive tutor mode - ask multiple questions in a session.

    Type 'quit' or 'exit' to stop, 'help' for guidance.

    SECURITY: guild-id is required to prevent cross-guild data leakage.

    Examples:
        python src/cli.py tutor interactive --guild-id 1349592236375019520
        python src/cli.py tutor interactive --guild-id 1405962109262757980 --model ollama-qwen-32b
    """
    try:
        click.echo("\n🤖 AI Wheel Strategy Tutor - Interactive Mode")
        click.echo("=" * 70)
        click.echo("Ask questions about the wheel strategy.")
        click.echo("Commands: 'quit'/'exit' to stop, 'help' for guidance, 'stats' for info")
        click.echo()

        # Import here to avoid circular dependency
        from rag import WheelStrategyTutor

        tutor_instance = WheelStrategyTutor(model=model, guild_id=guild_id)

        while True:
            try:
                question = input("❓ Your question: ").strip()

                if not question:
                    continue

                if question.lower() in ["quit", "exit", "q"]:
                    click.echo("\n👋 Happy trading!")
                    break

                if question.lower() == "help":
                    click.echo()
                    click.echo("💡 Example questions:")
                    click.echo("   • How do I pick a strike price?")
                    click.echo("   • What happens if I get assigned?")
                    click.echo("   • Explain the wheel strategy")
                    click.echo("   • What does BTO mean?")
                    click.echo("   • How much capital do I need?")
                    click.echo()
                    continue

                if question.lower() == "stats":
                    stats = tutor_instance.get_stats()
                    click.echo()
                    click.echo("📊 Vector Store Statistics:")
                    click.echo(f"   Total chunks: {stats['total_chunks']}")
                    click.echo(f"   Collection: {stats['collection_name']}")
                    click.echo(f"   Embedding model: {stats['embedding_model']}")
                    click.echo()
                    continue

                click.echo()
                result = tutor_instance.ask(
                    question=question,
                    temperature=temperature
                )

                click.echo("─" * 70)
                click.echo(result["answer"])
                click.echo("─" * 70)

                if result["sources"]:
                    click.echo(f"\n📚 Sources: {', '.join(result['sources'])}")

                click.echo()

            except KeyboardInterrupt:
                click.echo("\n\n👋 Happy trading!")
                break

    except Exception as e:
        logger.error(f"Error in interactive tutor: {e}", exc_info=True)
        click.secho(f"\n✗ Error: {e}", fg="red", err=True)
        if "vector store not initialized" in str(e).lower() or "No such file" in str(e):
            click.echo()
            click.secho("💡 Hint: Run vector store setup first:", fg="yellow")
            click.secho("   python scripts/rag/create_vector_store.py", fg="yellow")
