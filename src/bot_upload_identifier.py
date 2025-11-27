"""
Brokerage CSV Format Identifier

This module provides functionality to automatically detect which brokerage
a CSV file originates from based on header patterns, column structures,
and content fingerprints.

Supported brokerages:
- Fidelity
- Robinhood
- Schwab
- Interactive Brokers (IBKR)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import csv
import logging
import os
from enum import Enum
from typing import Any


# Module-level logger
logger = logging.getLogger(__name__)


class BrokerageType(Enum):
    """Enumeration of supported brokerage types"""
    FIDELITY = "fidelity"
    ROBINHOOD = "robinhood"
    SCHWAB = "schwab"
    IBKR = "ibkr"
    UNKNOWN = "unknown"


class BotUploadIdentifier:
    """
    Identifies the brokerage format of a CSV file by analyzing its structure and content.

    Detection Strategy:
    1. Read first few lines to check for unique header patterns
    2. Analyze column names and structure
    3. Check for brokerage-specific keywords and formats
    4. Apply weighted scoring system for confidence
    """

    # Unique fingerprints for each brokerage
    FIDELITY_SIGNATURES: dict[str, Any] = {
        "headers": ["Run Date", "Account", "Account Number", "Action", "Price ($)", "Commission ($)",
                   "Fees ($)", "Accrued Interest ($)", "Settlement Date"],
        "footer_keywords": ["Fidelity Brokerage Services", "Date downloaded"],
        "action_patterns": ["YOU SOLD OPENING TRANSACTION", "YOU BOUGHT", "EXPIRED", "ASSIGNED",
                          "DIVIDEND RECEIVED", "JOURNALED"],
    }

    ROBINHOOD_SIGNATURES: dict[str, Any] = {
        "headers": ["Activity Date", "Process Date", "Settle Date", "Instrument",
                   "Description", "Trans Code"],
        "trans_codes": ["STO", "BTC", "BTO", "STC", "OEXP", "OASGN", "CDIV", "ITRF",
                       "ACH", "XENT_CC", "MINT"],
        "cusip_pattern": True,  # Has "CUSIP: " in descriptions
        "footer_keywords": ["Robinhood Crypto", "Robinhood Spending"],
    }

    SCHWAB_SIGNATURES: dict[str, Any] = {
        "headers": ["Date", "Action", "Symbol", "Description", "Quantity", "Price",
                   "Fees & Comm", "Amount"],
        "action_patterns": ["Sell to Open", "Buy to Close", "Buy to Open", "Sell to Close",
                          "Reinvest Shares", "Reinvest Dividend", "Cash Dividend",
                          "Expired", "Assigned"],
        "date_format": "MM/DD/YYYY",
    }

    IBKR_SIGNATURES: dict[str, Any] = {
        "headers": ["Statement", "Header", "Field Name", "Field Value"],
        "section_headers": ["Mark-to-Market Performance Summary",
                           "Realized & Unrealized Performance Summary",
                           "Open Positions", "Trades", "Financial Instrument Information",
                           "Codes"],
        "data_discriminator": True,  # Has "Data" discriminator column
    }

    def __init__(self):
        """Initialize the BotUploadIdentifier"""
        self.confidence_scores = {}

    def identify(self, file_path: str, max_lines: int = 50) -> tuple[BrokerageType, float]:
        """
        Identify the brokerage type from a CSV file.

        Args:
            file_path: Path to the CSV file
            max_lines: Maximum number of lines to read for detection (default: 50)

        Returns:
            Tuple of (BrokerageType, confidence_score)
            confidence_score is a float between 0.0 and 1.0
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.debug(f"Analyzing file: {file_path}")

        # Read first max_lines of the file
        lines = []
        with open(file_path, encoding="utf-8-sig") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.strip())

        if not lines:
            logger.warning(f"Empty file: {file_path}")
            return (BrokerageType.UNKNOWN, 0.0)

        # Also read the last 10 lines for footer detection
        footer_lines = []
        with open(file_path, encoding="utf-8-sig") as f:
            all_lines = f.readlines()
            footer_lines = [line.strip() for line in all_lines[-10:]]

        # Try to parse as CSV
        try:
            reader = csv.reader(lines)
            rows = list(reader)
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            return (BrokerageType.UNKNOWN, 0.0)

        # Score each brokerage type
        self.confidence_scores = {
            BrokerageType.FIDELITY: self._score_fidelity(rows, lines, footer_lines),
            BrokerageType.ROBINHOOD: self._score_robinhood(rows, lines, footer_lines),
            BrokerageType.SCHWAB: self._score_schwab(rows, lines),
            BrokerageType.IBKR: self._score_ibkr(rows, lines),
        }

        logger.debug(f"Confidence scores: {self.confidence_scores}")

        # Find the highest scoring brokerage
        best_match = max(self.confidence_scores.items(), key=lambda x: x[1])
        brokerage_type, confidence = best_match

        # If confidence is too low, return UNKNOWN
        if confidence < 0.3:
            logger.warning(f"Low confidence ({confidence:.1%}) for file: {file_path}")
            return (BrokerageType.UNKNOWN, confidence)

        logger.info(f"Identified {file_path} as {brokerage_type.value} with {confidence:.1%} confidence")
        return (brokerage_type, confidence)

    def _score_fidelity(self, rows: list, lines: list, footer_lines: list) -> float:
        """Score the likelihood that this is a Fidelity file"""
        score = 0.0
        total_checks = 0

        # Check 1: Header row (worth 0.4)
        total_checks += 1
        if rows:
            # Find the first non-empty row
            header_row = None
            for row in rows[:5]:
                if row and len(row) > 5:
                    header_row = row
                    break

            if header_row:
                header_matches = sum(1 for sig in self.FIDELITY_SIGNATURES["headers"]
                                   if any(sig in cell for cell in header_row))
                if header_matches >= 5:  # Need at least 5 matching headers
                    score += 0.4

        # Check 2: Footer keywords (worth 0.2)
        total_checks += 1
        footer_text = "\n".join(footer_lines)
        if any(keyword in footer_text for keyword in self.FIDELITY_SIGNATURES["footer_keywords"]):
            score += 0.2

        # Check 3: Action patterns (worth 0.3)
        total_checks += 1
        action_matches = 0

        # Find the Action column index dynamically (Fidelity has two formats with different column orders)
        action_col_idx = None
        if header_row:
            for i, cell in enumerate(header_row):
                if "Action" in cell:
                    action_col_idx = i
                    break

        # If we found the Action column, check for action patterns
        if action_col_idx is not None:
            for row in rows[1:20]:  # Check first 20 data rows
                if len(row) > action_col_idx:
                    action_col = row[action_col_idx]
                    if any(pattern in action_col for pattern in self.FIDELITY_SIGNATURES["action_patterns"]):
                        action_matches += 1
            if action_matches >= 2:
                score += 0.3

        # Check 4: Symbol format with negative sign (worth 0.1)
        total_checks += 1
        for row in rows[1:15]:
            if len(row) > 4:
                symbol_col = row[4] if len(row) > 4 else ""
                if symbol_col.startswith("-") and len(symbol_col) > 5:
                    score += 0.1
                    break

        return score

    def _score_robinhood(self, rows: list, lines: list, footer_lines: list) -> float:
        """Score the likelihood that this is a Robinhood file"""
        score = 0.0
        total_checks = 0

        # Check 1: Header row (worth 0.4)
        total_checks += 1
        if rows and len(rows) > 0:
            header_row = rows[0]
            header_matches = sum(1 for sig in self.ROBINHOOD_SIGNATURES["headers"]
                               if any(sig in cell for cell in header_row))
            if header_matches >= 4:  # Need at least 4 matching headers
                score += 0.4

        # Check 2: Trans Code column with specific codes (worth 0.3)
        total_checks += 1
        trans_code_idx = None
        if rows:
            header = rows[0]
            for i, col in enumerate(header):
                if "Trans Code" in col:
                    trans_code_idx = i
                    break

            if trans_code_idx is not None:
                trans_code_matches = 0
                for row in rows[1:20]:
                    if len(row) > trans_code_idx:
                        trans_code = row[trans_code_idx]
                        if trans_code in self.ROBINHOOD_SIGNATURES["trans_codes"]:
                            trans_code_matches += 1
                if trans_code_matches >= 2:
                    score += 0.3

        # Check 3: CUSIP patterns in description (worth 0.2)
        total_checks += 1
        for line in lines[1:20]:
            if "CUSIP:" in line:
                score += 0.2
                break

        # Check 4: Footer keywords (worth 0.1)
        total_checks += 1
        footer_text = "\n".join(footer_lines)
        if any(keyword in footer_text for keyword in self.ROBINHOOD_SIGNATURES["footer_keywords"]):
            score += 0.1

        return score

    def _score_schwab(self, rows: list, lines: list) -> float:
        """Score the likelihood that this is a Schwab file"""
        score = 0.0
        total_checks = 0

        # Check 1: Header row (worth 0.4)
        total_checks += 1
        if rows and len(rows) > 0:
            header_row = rows[0]
            header_matches = sum(1 for sig in self.SCHWAB_SIGNATURES["headers"]
                               if sig in header_row)
            if header_matches >= 6:  # Need exact match for Schwab
                score += 0.4

        # Check 2: Action patterns (worth 0.4)
        total_checks += 1
        action_idx = None
        if rows:
            header = rows[0]
            for i, col in enumerate(header):
                if col == "Action":
                    action_idx = i
                    break

            if action_idx is not None:
                action_matches = 0
                for row in rows[1:20]:
                    if len(row) > action_idx:
                        action = row[action_idx]
                        if any(pattern in action for pattern in self.SCHWAB_SIGNATURES["action_patterns"]):
                            action_matches += 1
                if action_matches >= 3:
                    score += 0.4

        # Check 3: "Fees & Comm" column (worth 0.2)
        total_checks += 1
        if rows and len(rows) > 0:
            if "Fees & Comm" in rows[0]:
                score += 0.2

        return score

    def _score_ibkr(self, rows: list, lines: list) -> float:
        """Score the likelihood that this is an IBKR file"""
        score = 0.0
        total_checks = 0

        # Check 1: Statement header format (worth 0.3)
        total_checks += 1
        if rows and len(rows) > 0:
            first_row = rows[0]
            if len(first_row) > 0 and first_row[0] == "Statement":
                score += 0.3

        # Check 2: Section headers (worth 0.4)
        total_checks += 1
        section_matches = 0
        for line in lines[:30]:
            for section in self.IBKR_SIGNATURES["section_headers"]:
                if section in line:
                    section_matches += 1
                    break
        if section_matches >= 2:
            score += 0.4

        # Check 3: "Data" discriminator pattern (worth 0.2)
        total_checks += 1
        for row in rows[:30]:
            if len(row) > 1 and row[1] == "Data":
                score += 0.2
                break

        # Check 4: "Codes" section (worth 0.1)
        total_checks += 1
        for line in lines:
            if "Codes,Header" in line or "Codes,Data" in line:
                score += 0.1
                break

        return score

    def get_confidence_scores(self) -> dict:
        """
        Get the confidence scores for all brokerage types from the last identification.

        Returns:
            Dictionary mapping BrokerageType to confidence score (0.0-1.0)
        """
        return self.confidence_scores.copy()


def main():
    """Example usage"""
    identifier = BotUploadIdentifier()

    # Example files
    test_files = [
        "uploads/schwab_example.csv",
        "uploads/capt10l.RH_september.csv",
        "uploads/sangelovich.Accounts_History-10.csv",
        "uploads/ibkr_example.csv",
    ]

    for file_path in test_files:
        if os.path.exists(file_path):
            brokerage, confidence = identifier.identify(file_path)
            logger.info(f"{file_path}: Detected {brokerage.value} with {confidence:.2%} confidence")
            print(f"{file_path}:")
            print(f"  Detected: {brokerage.value}")
            print(f"  Confidence: {confidence:.2%}")
            print(f"  All scores: {identifier.get_confidence_scores()}")
            print()


if __name__ == "__main__":
    main()
