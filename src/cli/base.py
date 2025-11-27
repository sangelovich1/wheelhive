"""
Base Command Class

All CLI commands inherit from BaseCommand to provide consistent structure.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from abc import ABC, abstractmethod

from db import Db


logger = logging.getLogger(__name__)


class BaseCommand(ABC):
    """
    Base class for all CLI commands.

    Each command should:
    1. Override add_parser() to define arguments
    2. Override execute() to implement command logic
    3. Access self.db for database operations
    """

    def __init__(self, db: Db):
        """
        Initialize command with database connection.

        Args:
            db: Database instance (shared across commands)
        """
        self.db = db

    @abstractmethod
    def add_parser(self, subparsers):
        """
        Add this command's parser to the subparsers.

        Args:
            subparsers: argparse subparsers object

        Returns:
            The created parser object

        Example:
            parser = subparsers.add_parser('my_command', help='Do something')
            parser.add_argument('--arg1', help='Argument 1')
            return parser
        """

    @abstractmethod
    def execute(self, args):
        """
        Execute the command with parsed arguments.

        Args:
            args: Parsed command-line arguments (argparse Namespace)

        Returns:
            Exit code (0 for success, non-zero for error)
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the command name (matches args.command).

        Returns:
            Command name string
        """

    def matches(self, command_name: str) -> bool:
        """
        Check if this command matches the given command name.

        Args:
            command_name: The command name from args.command

        Returns:
            True if this command should handle it
        """
        return self.name == command_name
