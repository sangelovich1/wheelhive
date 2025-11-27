#!/usr/bin/env python3
"""
FAQ Manager for guild-specific knowledge base additions.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

import constants as const
from system_settings import get_settings


logger = logging.getLogger(__name__)


class FAQManager:
    """Manages FAQ additions to guild-specific vector stores with validation"""

    def __init__(self, guild_id: int | None = None):
        """
        Initialize FAQ manager.

        Args:
            guild_id: Optional guild ID for guild-specific FAQs
        """
        self.guild_id = guild_id

    def validate_faq_quality(self, question: str, answer: str) -> dict[str, Any]:
        """
        Validate that FAQ addition won't degrade knowledge base quality.

        Uses LLM to check:
        1. Question clarity and specificity
        2. Answer accuracy and completeness
        3. Relevance to wheel strategy
        4. Potential conflicts with existing content

        Args:
            question: The FAQ question
            answer: The FAQ answer

        Returns:
            Dict with keys:
            - is_valid: bool
            - score: float (0-1)
            - issues: List[str]
            - suggestions: List[str]
            - reasoning: str
        """
        try:
            from llm_provider import create_llm_provider

            # Get validation model from settings
            settings = get_settings()
            model = settings.get(const.SETTING_AI_TUTOR_MODEL, "claude-sonnet")

            # Create LLM provider
            llm = create_llm_provider(model)

            # Validation prompt
            validation_prompt = f"""You are a knowledge base quality validator. Evaluate this FAQ entry for a wheel strategy options trading knowledge base.

QUESTION: {question}

ANSWER: {answer}

Evaluate on these criteria:
1. **Question Quality**: Is it clear, specific, and well-formed?
2. **Answer Quality**: Is it accurate, complete, and helpful?
3. **Relevance**: Does it relate to wheel strategy, options trading, or risk management?
4. **Clarity**: Is the language clear and free of ambiguity?
5. **Accuracy**: Does the answer contain any misleading or incorrect information?

IMPORTANT: You must respond with ONLY valid JSON, no additional text before or after. Use this exact format:

{{
    "is_valid": true,
    "score": 0.85,
    "issues": [],
    "suggestions": ["Consider adding an example"],
    "reasoning": "High quality FAQ with clear explanation"
}}

Guidelines:
- is_valid: true if score >= 0.7, false otherwise
- score: 0.0 to 1.0 (0.7+ is acceptable)
- issues: Empty list if no major problems
- suggestions: Helpful tips even for good FAQs
- reasoning: Keep under 200 characters

Be fair but maintain quality standards."""

            # Get validation response
            messages = [{"role": "user", "content": validation_prompt}]
            response_obj = llm.completion(
                messages=messages,
                temperature=0.3,  # Low temperature for consistent validation
                max_tokens=500,
            )

            # Extract text from response
            response = response_obj.choices[0].message.content
            logger.debug(f"Raw LLM validation response: {response}")

            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks and extra text)
                response_text = response.strip()

                # Try to extract from code blocks first
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()

                # Try to find JSON object boundaries
                if "{" in response_text and "}" in response_text:
                    start = response_text.find("{")
                    end = response_text.rfind("}") + 1
                    response_text = response_text[start:end]

                logger.debug(f"Attempting to parse JSON: {response_text[:200]}...")
                validation_result: dict[str, Any] = json.loads(response_text)

                # Ensure required fields exist
                validation_result.setdefault("is_valid", False)
                validation_result.setdefault("score", 0.0)
                validation_result.setdefault("issues", [])
                validation_result.setdefault("suggestions", [])
                validation_result.setdefault("reasoning", "No reasoning provided")

                return validation_result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse validation JSON: {e}\nResponse: {response}")
                return {
                    "is_valid": False,
                    "score": 0.0,
                    "issues": ["Validation system error - please try again"],
                    "suggestions": [],
                    "reasoning": "JSON parsing failed",
                }

        except Exception as e:
            logger.error(f"Error validating FAQ: {e}", exc_info=True)
            return {
                "is_valid": False,
                "score": 0.0,
                "issues": [f"Validation error: {e!s}"],
                "suggestions": [],
                "reasoning": "Validation system error",
            }

    def add_faq_to_vector_db(self, question: str, answer: str, admin_user: str) -> bool:
        """
        Add FAQ to guild-specific vector database.

        Args:
            question: The FAQ question
            answer: The FAQ answer
            admin_user: Username of admin who added it

        Returns:
            bool: Success status
        """
        if not self.guild_id:
            logger.error("Cannot add FAQ without guild_id")
            return False

        try:
            # Ensure guild-specific directory exists
            guild_db_path = Path(f"training_materials/{self.guild_id}/vector_db")
            guild_db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect to guild-specific ChromaDB
            client = chromadb.PersistentClient(
                path=str(guild_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

            # Get or create FAQ collection
            try:
                collection = client.get_collection(name="training_materials")
            except Exception:
                # Create new collection if it doesn't exist
                collection = client.create_collection(
                    name="training_materials",
                    metadata={
                        "description": f"Guild {self.guild_id} training materials with FAQs",
                        "embedding_model": "default",
                    },
                )
                logger.info(f"Created new collection for guild {self.guild_id}")

            # Generate unique ID for this FAQ
            timestamp = datetime.now().isoformat()
            content_hash = hashlib.md5(f"{question}{answer}".encode()).hexdigest()[:8]
            faq_id = f"faq_{self.guild_id}_{timestamp}_{content_hash}"

            # Format as Q&A document
            document_text = f"""Question: {question}

Answer: {answer}"""

            # Add to vector store
            collection.add(
                ids=[faq_id],
                documents=[document_text],
                metadatas=[
                    {
                        "source_file": "guild_faq",
                        "page_number": 0,
                        "doc_type": "faq",
                        "section": question[:100],  # Use question as section
                        "tokens": len(document_text.split()),
                        "added_by": admin_user,
                        "added_at": timestamp,
                        "guild_id": str(self.guild_id),
                    }
                ],
            )

            logger.info(
                f"Added FAQ to guild {self.guild_id} vector DB: "
                f"'{question[:50]}...' by {admin_user}"
            )

            return True

        except Exception as e:
            logger.error(f"Error adding FAQ to vector DB: {e}", exc_info=True)
            return False

    def remove_faq(self, faq_id: str) -> bool:
        """
        Remove FAQ from guild's vector store by ID.

        Args:
            faq_id: The FAQ ID to remove

        Returns:
            bool: Success status
        """
        if not self.guild_id:
            logger.error("Cannot remove FAQ without guild_id")
            return False

        try:
            guild_db_path = Path(f"training_materials/{self.guild_id}/vector_db")
            if not guild_db_path.exists():
                logger.error(f"No FAQ database exists for guild {self.guild_id}")
                return False

            # Connect to guild-specific ChromaDB
            client = chromadb.PersistentClient(
                path=str(guild_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

            # Get collection
            collection = client.get_collection(name="training_materials")

            # Verify FAQ exists before deletion
            existing = collection.get(ids=[faq_id])
            if not existing or not existing.get("ids") or faq_id not in existing["ids"]:
                logger.warning(f"FAQ {faq_id} not found in guild {self.guild_id} vector store")
                return False

            # Delete the FAQ by ID
            collection.delete(ids=[faq_id])

            # Verify deletion
            check = collection.get(ids=[faq_id])
            if check and check.get("ids") and faq_id in check["ids"]:
                logger.error(f"FAQ {faq_id} still present after deletion attempt")
                return False

            logger.info(f"Successfully removed FAQ {faq_id} from guild {self.guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing FAQ: {e}", exc_info=True)
            return False

    def purge_all_faqs(self) -> bool:
        """
        Remove ALL FAQs from guild's vector store.

        WARNING: This is destructive and cannot be undone!
        Only removes items with doc_type='faq', preserves PDFs.

        Args:
            None

        Returns:
            bool: Success status
        """
        if not self.guild_id:
            logger.error("Cannot purge FAQs without guild_id")
            return False

        try:
            guild_db_path = Path(f"training_materials/{self.guild_id}/vector_db")
            if not guild_db_path.exists():
                logger.warning(f"No FAQ database exists for guild {self.guild_id}")
                return True  # Nothing to purge = success

            # Connect to guild-specific ChromaDB
            client = chromadb.PersistentClient(
                path=str(guild_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

            # Get collection
            collection = client.get_collection(name="training_materials")

            # Get all FAQ IDs
            results = collection.get(where={"doc_type": "faq"})

            if not results or not results.get("ids"):
                logger.info(f"No FAQs to purge for guild {self.guild_id}")
                return True

            faq_ids = results["ids"]

            # Delete all FAQ IDs
            collection.delete(ids=faq_ids)

            logger.info(f"Purged {len(faq_ids)} FAQs from guild {self.guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error purging FAQs: {e}", exc_info=True)
            return False

    def purge_entire_guild_db(self) -> bool:
        """
        Delete entire guild vector database (FAQs + PDFs + everything).

        WARNING: This is VERY destructive and cannot be undone!
        Deletes the entire guild-specific vector store directory.

        Args:
            None

        Returns:
            bool: Success status
        """
        if not self.guild_id:
            logger.error("Cannot purge database without guild_id")
            return False

        try:
            import shutil

            guild_db_path = Path(f"training_materials/{self.guild_id}")

            if not guild_db_path.exists():
                logger.warning(f"No database exists for guild {self.guild_id}")
                return True  # Nothing to purge = success

            # Delete the entire guild directory
            shutil.rmtree(guild_db_path)

            logger.info(f"Purged entire vector database for guild {self.guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error purging guild database: {e}", exc_info=True)
            return False

    def get_guild_vector_stats(self) -> dict:
        """
        Get statistics about guild's vector database.

        Returns:
            Dict with stats about FAQs, PDFs, and total documents
        """
        if not self.guild_id:
            logger.error("Cannot get stats without guild_id")
            return {}

        try:
            guild_db_path = Path(f"training_materials/{self.guild_id}/vector_db")

            if not guild_db_path.exists():
                return {
                    "guild_id": self.guild_id,
                    "exists": False,
                    "total_documents": 0,
                    "faqs": 0,
                    "pdfs": 0,
                    "other": 0,
                }

            # Connect to guild-specific ChromaDB
            client = chromadb.PersistentClient(
                path=str(guild_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

            # Get collection
            collection = client.get_collection(name="training_materials")

            # Get total count
            total_count = collection.count()

            # Count by doc_type
            faq_results = collection.get(where={"doc_type": "faq"})
            faq_count = len(faq_results["ids"]) if faq_results and faq_results.get("ids") else 0

            # Get all results to count doc types
            all_results = collection.get()
            doc_type_counts: dict[str, int] = {}

            if all_results and all_results.get("metadatas") and all_results["metadatas"]:
                for metadata in all_results["metadatas"]:
                    if isinstance(metadata, dict):
                        doc_type = metadata.get("doc_type", "unknown")
                        doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

            return {
                "guild_id": self.guild_id,
                "exists": True,
                "total_documents": total_count,
                "by_doc_type": doc_type_counts,
                "faqs": faq_count,
                "path": str(guild_db_path),
            }

        except Exception as e:
            logger.error(f"Error getting guild vector stats: {e}", exc_info=True)
            return {"guild_id": self.guild_id, "exists": True, "error": str(e)}

    def list_faqs(self) -> list:
        """
        List all FAQs in the guild's vector store.

        Returns:
            List of FAQ dicts with question, answer, added_by, added_at
        """
        if not self.guild_id:
            logger.error("Cannot list FAQs without guild_id")
            return []

        try:
            guild_db_path = Path(f"training_materials/{self.guild_id}/vector_db")
            if not guild_db_path.exists():
                logger.info(f"No FAQ database exists for guild {self.guild_id}")
                return []

            # Connect to guild-specific ChromaDB
            client = chromadb.PersistentClient(
                path=str(guild_db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

            # Get collection
            collection = client.get_collection(name="training_materials")

            # Query for FAQ entries
            results = collection.get(where={"doc_type": "faq"})

            faqs: list = []
            if results and results.get("documents") and results.get("metadatas"):
                documents = results["documents"]
                metadatas = results["metadatas"]
                ids = results["ids"]

                if documents and metadatas and ids:
                    for i, doc in enumerate(documents):
                        metadata = metadatas[i] if i < len(metadatas) else {}
                        doc_id = ids[i] if i < len(ids) else "unknown"
                        faqs.append(
                            {
                                "id": doc_id,
                                "question": metadata.get("section", "N/A")
                                if isinstance(metadata, dict)
                                else "N/A",
                                "answer": doc.split("Answer: ", 1)[1]
                                if isinstance(doc, str) and "Answer: " in doc
                                else str(doc),
                                "added_by": metadata.get("added_by", "unknown")
                                if isinstance(metadata, dict)
                                else "unknown",
                                "added_at": metadata.get("added_at", "unknown")
                                if isinstance(metadata, dict)
                                else "unknown",
                            }
                        )

            return faqs

        except Exception as e:
            logger.error(f"Error listing FAQs: {e}", exc_info=True)
            return []
