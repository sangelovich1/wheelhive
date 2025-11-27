#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# Standard library imports
import logging
import os
import sqlite3
import zipfile
from collections.abc import Generator
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Third-party imports
from dateutil.relativedelta import relativedelta
from markdown_pdf import MarkdownPdf, Section

# Local application imports
import constants as const


# Module-level logger
logger = logging.getLogger(__name__)

def parse_string(s: str) -> list[float]:
    def parse_part(part: str) -> list[float]:
        if "-" in part:
            try:
                start_str, end_step = part.split("-")
                start_val = float(start_str)
                if "(" in end_step:
                    end_str, step_str = end_step.rstrip(")").split("(")
                    end_val = float(end_str)
                    step_val = float(step_str)
                    return [start_val + i * step_val for i in range(int((end_val - start_val) / step_val) + 1)]
                end_val = float(end_step)
                return list(range(int(start_val), int(end_val) + 1))
            except (ValueError, TypeError):
                raise ValueError(f"Invalid range format: {part}")
        else:
            try:
                return [float(part)]
            except ValueError:
                raise ValueError(f"Invalid number format: {part}")

    result = []
    parts = s.split(",")
    for part in parts:
        part = part.strip()
        result.extend(parse_part(part))

    # Remove duplicates and sort the result to ensure correct order
    return sorted(set(result))


def setup_logger(name: str | None = None, level: str | None = None, console: bool = True, log_file: str | None = None) -> logging.Logger:
    """
    Setup a logger with file and optional console output.

    Args:
        name: Logger name (use __name__ from calling module). If None, configures root logger.
        level: Logging level (DEBUG, INFO, WARNING, ERROR). Defaults to INFO or env LOG_LEVEL.
        console: Whether to also log to console (default True for main apps)
        log_file: Custom log filename (defaults to const.LOG_FILE)

    Returns:
        logging.Logger: Configured logger instance

    Example:
        # For application entry point (bot.py, cmds.py):
        util.setup_logger(name=None, level='INFO', console=True)
        logger = logging.getLogger(__name__)

        # For MCP server with custom log file:
        util.setup_logger(name=None, level='INFO', console=True, log_file='mcp_server.log')
        logger = logging.getLogger(__name__)

        # For library modules:
        logger = util.get_logger(__name__)
    """
    # Determine log level from parameter, environment, or default to INFO
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, level, logging.INFO)

    # Get or create logger
    logger = logging.getLogger(name) if name else logging.getLogger()

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    logger.setLevel(numeric_level)

    # Create formatters
    # Include logger name and module info for better tracking
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S"
    )

    # Use custom log file or default
    log_filename = log_file if log_file else const.LOG_FILE

    # File handler with rotation (don't delete on startup)
    file_handler = RotatingFileHandler(
        filename=log_filename,
        maxBytes=const.MAX_LOG_SIZE,
        backupCount=const.BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(logging.DEBUG)  # Capture everything to file
    logger.addHandler(file_handler)

    # Console handler (optional, with less verbose format)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(numeric_level)  # Respect configured level
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a module-specific logger. This is the standard way to get loggers in library modules.

    Args:
        name: Use __name__ from the calling module

    Returns:
        logging.Logger: Logger instance for the module

    Example:
        logger = util.get_logger(__name__)
        logger.info("Processing started")
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Dynamically change log level for all loggers.
    Useful for debugging without restart.

    Args:
        level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example:
        util.set_log_level('DEBUG')  # Enable debug logging
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Update console handlers to new level (keep file at DEBUG)
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(numeric_level)

def week_start_end(any_day: datetime) -> tuple[datetime, datetime]:
    start_date = any_day - timedelta(days=any_day.weekday())
    end_date = start_date + timedelta(days=4) # 4 days after Monday is Friday
    return start_date, end_date

def month_start_end(any_day: datetime) -> tuple[datetime, datetime]:
    y = int(any_day.strftime("%Y"))
    m = int(any_day.strftime("%m"))
    sstart = f"{y}-{m}-01"
    start_date = datetime.strptime(sstart, "%Y-%m-%d")
    # The day 28 exists in every month. 4 days later, it's always next month
    next_month = any_day.replace(day=28) + timedelta(days=4)
    # subtracting the number of the current day brings us back one month
    end_date = next_month - timedelta(days=next_month.day)
    return start_date, end_date

def month_iterator(start_date: datetime, end_date: datetime) -> Generator[str, None, None]:
    current_date = start_date
    while current_date <= end_date:
        yield current_date.strftime("%Y-%m-%d")
        current_date += relativedelta(months=1)

def current_year() -> int:
    now = datetime.now()
    year = now.strftime("%Y")
    return int(year)

def create_pdf(source: str, output: str) -> None:

    # Read your Markdown content from a file or string
    with open(source) as f:
        markdown_content = f.read()

    # Create a MarkdownPdf instance
    pdf = MarkdownPdf()

    # Add the Markdown content as a section
    pdf.add_section(Section(markdown_content))

    # Save the PDF
    pdf.save(output)



def is_date_db_format(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def to_db_date(date_str: str) -> str:

    if is_date_db_format(date_str):
        return date_str

    # Converts 'MM/DD/YYYY' to 'YYYY-MM-DD'
    # Converts 'MM/DD' to 'YYYY-MM-DD'

    # Handle - as a separator
    date_str = date_str.replace("-", "/")

    # Handled 2 digit year
    if date_str.count("/") == 1:
        Y = datetime.now().strftime("%Y")
        date_str = f"{date_str}/{Y}"

    parts = date_str.split("/")
    if len(parts[2]) == 2:
        date_str = f"{parts[0]}/{parts[1]}/20{parts[2]}"

    dt = datetime.strptime(date_str, "%m/%d/%Y")

    return dt.strftime("%Y-%m-%d")

def currency_to_float(input_str: str) -> float:
    input_str = input_str.replace(",", "")
    input_str = input_str.replace("$(", "-")
    input_str = input_str.replace("($", "-")

    input_str = input_str.replace("(", "-")
    input_str = input_str.replace(")", "")
    input_str = input_str.replace("$", "")

    return float(input_str)


def create_zip_archive(output_zip_path: str, files_to_add: list[str]) -> None:
    """
    Creates a zip archive containing multiple specified files.

    Args:
        output_zip_path (str): The full path and filename for the output zip archive.
        files_to_add (list): A list of full paths to the files to be added to the archive.
    """
    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_add:
                if os.path.exists(file_path):
                    # Add the file to the zip archive, preserving its base filename
                    zipf.write(file_path, os.path.basename(file_path))
                    logger.debug(f"Added {file_path} to archive")
                else:
                    logger.warning(f"File not found in zip archive: {file_path}")
        logger.info(f"Created zip archive: {output_zip_path}")
    except Exception as e:
        logger.error(f"Failed to create zip archive: {e}", exc_info=True)
        raise


def add_column_if_not_exists(db_connection: sqlite3.Connection, tablename: str, column_name: str, column_def: str) -> None:
    """
    Add a column to a database table only if it doesn't already exist.
    This is a utility function for safe schema migrations.

    Args:
        db_connection: Database connection object with execute() method
        tablename: Name of the table to modify
        column_name: Name of the column to add
        column_def: SQL column definition (e.g., 'INTEGER DEFAULT NULL', 'TEXT DEFAULT "default"')

    Example:
        util.add_column_if_not_exists(self.db.connection, 'trades', 'guild_id', 'INTEGER DEFAULT NULL')
        util.add_column_if_not_exists(self.db.connection, 'trades', 'account', 'TEXT DEFAULT "default"')
    """
    try:
        # Check if column exists by querying table info
        cursor = db_connection.execute(f"PRAGMA table_info({tablename})")
        columns = [row[1] for row in cursor.fetchall()]

        if column_name not in columns:
            logger.info(f"Adding column {column_name} to {tablename} table")
            db_connection.execute(f"ALTER TABLE {tablename} ADD COLUMN {column_name} {column_def}")
            db_connection.commit()
            logger.info(f"Column {column_name} added successfully to {tablename}")
        else:
            logger.debug(f"Column {column_name} already exists in {tablename}")
    except Exception as e:
        logger.error(f"Error adding column {column_name} to {tablename}: {e}")
        raise


def get_user_accounts(db, username: str) -> list[str]:
    """
    Get all distinct accounts for a given username across all tables.

    Args:
        db: Database instance with query_parameterized() method
        username: Username to query accounts for

    Returns:
        List of account names sorted alphabetically. Returns empty list if no accounts found.

    Example:
        accounts = util.get_user_accounts(client.db, 'sangelovich')
        # Returns: ['Alaska', 'Joint', 'default']
    """
    # Query distinct accounts from all tables
    trades_accounts = db.query_parameterized("SELECT DISTINCT account FROM trades WHERE username=?", params=(username,))
    dividends_accounts = db.query_parameterized("SELECT DISTINCT account FROM dividends WHERE username=?", params=(username,))
    shares_accounts = db.query_parameterized("SELECT DISTINCT account FROM shares WHERE username=?", params=(username,))
    deposits_accounts = db.query_parameterized("SELECT DISTINCT account FROM deposits WHERE username=?", params=(username,))

    # Combine all unique accounts
    all_accounts = set()
    for result in trades_accounts:
        if result[0]:  # Skip None values
            all_accounts.add(result[0])
    for result in dividends_accounts:
        if result[0]:
            all_accounts.add(result[0])
    for result in shares_accounts:
        if result[0]:
            all_accounts.add(result[0])
    for result in deposits_accounts:
        if result[0]:
            all_accounts.add(result[0])

    # Sort alphabetically and return as list
    return sorted(all_accounts)


def smart_split_message(text: str, max_length: int) -> list[str]:
    """
    Intelligently split text into chunks respecting markdown structure and readability.

    Priority order for split points:
    1. Section boundaries (--- or ## headers)
    2. Paragraph boundaries (\n\n)
    3. Sentence boundaries (. \n or .\n)
    4. Line boundaries (\n)
    5. Word boundaries (space)
    6. Character limit (last resort)

    Args:
        text: Text to split
        max_length: Maximum length per chunk

    Returns:
        List of text chunks

    Example:
        chunks = smart_split_message(long_text, 2000)
        for chunk in chunks:
            await channel.send(chunk)
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Find the best split point within max_length
        chunk = remaining[:max_length]
        split_point = -1

        # Try to split at section boundary (--- or ## header)
        # Look for --- on its own line or ## at start of line
        for separator in ["\n---\n", "\n## ", "\n### ", "\n#### "]:
            idx = chunk.rfind(separator)
            if idx > max_length * 0.3:  # Don't split too early (at least 30% through)
                split_point = idx + len(separator)
                break

        # Try to split at paragraph boundary
        if split_point == -1:
            idx = chunk.rfind("\n\n")
            if idx > max_length * 0.3:
                split_point = idx + 2

        # Try to split at sentence boundary
        if split_point == -1:
            for pattern in [". \n", ".\n"]:
                idx = chunk.rfind(pattern)
                if idx > max_length * 0.5:  # At least 50% through
                    split_point = idx + len(pattern)
                    break

        # Try to split at line boundary
        if split_point == -1:
            idx = chunk.rfind("\n")
            if idx > max_length * 0.5:
                split_point = idx + 1

        # Try to split at word boundary
        if split_point == -1:
            idx = chunk.rfind(" ")
            if idx > max_length * 0.7:  # At least 70% through
                split_point = idx + 1

        # Last resort: split at max_length
        if split_point == -1:
            split_point = max_length

        chunks.append(remaining[:split_point])
        remaining = remaining[split_point:]

    return chunks


def format_portfolio_json_for_discord(json_data: dict) -> str:
    """
    Format portfolio analysis JSON into Discord-friendly text with clean tables.

    Args:
        json_data: Structured portfolio analysis from LLM

    Returns:
        Formatted text ready for Discord display
    """
    from tabulate import tabulate

    output = []

    # Overview section
    if "overview" in json_data:
        overview = json_data["overview"]
        output.append("📊 **Portfolio Overview**\n")

        if "key_metrics" in overview:
            table = tabulate(
                [[m["metric"], m["value"]] for m in overview["key_metrics"]],
                headers=["Metric", "Value"],
                tablefmt="simple"
            )
            output.append(f"```\n{table}\n```\n")

    # Critical positions requiring action
    if json_data.get("critical_positions"):
        output.append("🚨 **Critical Positions (<14 DTE)**\n")

        positions = json_data["critical_positions"]
        table_data = []
        for p in positions:
            table_data.append([
                p.get("symbol", ""),
                f"${p.get('strike', '')}",
                p.get("type", ""),
                p.get("expiration", ""),
                p.get("dte", ""),
                p.get("status", ""),
                p.get("risk_level", "")
            ])

        table = tabulate(
            table_data,
            headers=["Symbol", "Strike", "Type", "Expiration", "DTE", "Status", "Risk"],
            tablefmt="simple"
        )
        output.append(f"```\n{table}\n```\n")

    # Stock positions table
    if json_data.get("positions_table"):
        output.append("📈 **Stock Positions**\n")

        positions = json_data["positions_table"]
        table_data = []
        for p in positions:
            unrealized_pl = p.get("unrealized_pl", 0)
            unrealized_pl_pct = p.get("unrealized_pl_pct", 0)
            pl_str = f"${unrealized_pl:,.0f} ({unrealized_pl_pct:+.1f}%)"

            table_data.append([
                p.get("symbol", ""),
                f"{p.get('shares', 0):,}",
                f"${p.get('avg_cost', 0):.2f}",
                f"${p.get('current_price', 0):.2f}",
                f"${p.get('market_value', 0):,.0f}",
                pl_str
            ])

        table = tabulate(
            table_data,
            headers=["Symbol", "Shares", "Avg Cost", "Current", "Value", "Unrealized P/L"],
            tablefmt="simple"
        )
        output.append(f"```\n{table}\n```\n")

    # Winners and losers
    if json_data.get("winners"):
        output.append("🏆 **Top Winners**\n")
        winners = json_data["winners"][:3]  # Top 3
        table_data = [[w.get("symbol", ""), f"${w.get('unrealized_pl', 0):,.0f}", f"{w.get('unrealized_pl_pct', 0):+.1f}%"] for w in winners]
        table = tabulate(table_data, headers=["Symbol", "P/L", "Return"], tablefmt="simple")
        output.append(f"```\n{table}\n```\n")

    if json_data.get("losers"):
        output.append("📉 **Top Losers**\n")
        losers = json_data["losers"][:3]  # Top 3
        table_data = [[l.get("symbol", ""), f"${l.get('unrealized_pl', 0):,.0f}", f"{l.get('unrealized_pl_pct', 0):+.1f}%"] for l in losers]
        table = tabulate(table_data, headers=["Symbol", "P/L", "Return"], tablefmt="simple")
        output.append(f"```\n{table}\n```\n")

    # Recommendations
    if json_data.get("recommendations"):
        output.append("💡 **Recommendations**\n")
        for i, rec in enumerate(json_data["recommendations"], 1):
            priority = rec.get("priority", "").upper()
            emoji = "🚨" if priority == "URGENT" else "⚠️" if priority == "HIGH" else "📌"
            output.append(f"{emoji} **{i}. {rec.get('title', '')}**")
            output.append(f"**Action:** {rec.get('action', '')}")
            output.append(f"**Rationale:** {rec.get('rationale', '')}\n")

    # Narrative/analysis
    if "narrative" in json_data:
        output.append("---")
        output.append(json_data["narrative"])

    # Disclaimer
    output.append("\n---")
    output.append("⚠️ **Disclaimer**: This analysis is for informational and educational purposes only and does not constitute financial, investment, or trading advice. Options trading involves substantial risk of loss. Past performance does not guarantee future results. Consult a licensed financial advisor before making investment decisions.")

    return "\n".join(output)


def format_tables_for_discord(text: str) -> str:
    """
    Convert markdown tables in text to Discord-friendly format using code blocks.

    Markdown tables don't render well in Discord - they show as raw pipe characters.
    This function detects markdown tables and reformats them as clean, aligned code blocks.

    Args:
        text: Text containing markdown tables

    Returns:
        Text with markdown tables converted to Discord-friendly code blocks

    Example:
        input:  "| Name | Value |\n|------|-------|\n| Foo | 123 |"
        output: "```\nName   Value\nFoo    123\n```"
    """
    import re

    from tabulate import tabulate

    # Pattern to match markdown tables
    # Matches: header row, separator row, and data rows
    table_pattern = re.compile(
        r"(?:^|\n)(\|.+\|)\n(\|[\s:-]+\|)\n((?:\|.+\|\n?)+)",
        re.MULTILINE
    )

    def parse_markdown_table(match):
        """Parse a markdown table match into headers and rows."""
        header_line = match.group(1)
        data_lines = match.group(3).strip().split("\n")

        # Parse header
        headers = [cell.strip() for cell in header_line.split("|")[1:-1]]

        # Parse data rows
        rows = []
        for line in data_lines:
            if line.strip():
                cells = [cell.strip() for cell in line.split("|")[1:-1]]
                rows.append(cells)

        return headers, rows

    def replace_table(match):
        """Replace markdown table with Discord-friendly code block."""
        try:
            headers, rows = parse_markdown_table(match)

            # Use tabulate to create clean aligned format
            # 'simple' format works well in Discord code blocks
            formatted = tabulate(rows, headers=headers, tablefmt="simple")

            # Wrap in code block for Discord
            return f"\n```\n{formatted}\n```\n"

        except Exception as e:
            logger.warning(f"Failed to parse markdown table: {e}")
            # Return original table if parsing fails
            return match.group(0)

    # Replace all markdown tables
    result = table_pattern.sub(replace_table, text)

    return result


def normalize_channel_name(channel_name: str) -> str:
    """
    Normalize Discord channel name by removing emoji prefixes and suffixes.

    Discord channels often have emoji decorations (💰, 💲, 💸, etc.) at the
    beginning or end that make CLI usage difficult. This function strips
    emoji characters and trims whitespace to create consistent, CLI-friendly
    channel names.

    Args:
        channel_name: Raw channel name from Discord (may include emojis)

    Returns:
        Normalized channel name without emojis

    Examples:
        >>> normalize_channel_name('💰stock-talk-options')
        'stock-talk-options'
        >>> normalize_channel_name('💲darkminer-moves')
        'darkminer-moves'
        >>> normalize_channel_name('news💰')
        'news'
        >>> normalize_channel_name('💸trading-chat💸')
        'trading-chat'
        >>> normalize_channel_name('news')
        'news'
    """
    import re

    # Remove all emoji characters (Unicode ranges for emojis)
    # This covers most common emoji ranges including:
    # - Emoticons (1F600-1F64F)
    # - Miscellaneous Symbols (1F300-1F5FF)
    # - Transport and Map Symbols (1F680-1F6FF)
    # - Supplemental Symbols (1F900-1F9FF)
    # - Dingbats (2700-27BF)
    # - Currency symbols (including 💲 at U+1F4B2)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U00002700-\U000027BF"  # dingbats
        "\U0001F4B0-\U0001F4B9"  # currency symbols (includes 💰💱💲)
        "]+",
        flags=re.UNICODE
    )

    normalized = emoji_pattern.sub("", channel_name).strip()
    return normalized
