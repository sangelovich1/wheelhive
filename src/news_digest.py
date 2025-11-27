"""
News Digest Generator - LLM-Powered Summarization

Generates personalized and community news digests using LLM.
Reads from harvested_messages table (news articles posted by news_feed.py).

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

from db import Db
from messages import Messages


logger = logging.getLogger(__name__)


class NewsDigest:
    """
    Generate AI-powered news digests from harvested news messages
    """

    def __init__(self, db: Db | None = None):
        """
        Initialize news digest generator

        Args:
            db: Database instance (creates new if None)
        """
        self.db = db if db else Db(in_memory=False)
        self.messages = Messages(self.db)

    # TODO: Implement digest generation methods
    # This will be completed after news feed is working
