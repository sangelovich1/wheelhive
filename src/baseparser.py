#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from typing import Any


# Get a logger instance
logger = logging.getLogger(__name__)

class BaseParser:

    def as_named_tuple(self) -> Any:
        """Return a namedtuple representation of the parsed data"""
        raise NotImplementedError("Subclass needs to implement this method")

    def parse(self) -> None:
        raise NotImplementedError("Subclass needs to implement this method")

    def is_valid(self) -> bool:
        raise NotImplementedError("Subclass needs to implement this method")


