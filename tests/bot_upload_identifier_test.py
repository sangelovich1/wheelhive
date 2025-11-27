"""
Unit tests for BotUploadIdentifier class

Tests the automatic brokerage identification for CSV files from different brokerages.
Each test verifies that a known CSV file is correctly identified with high confidence.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from bot_upload_identifier import BotUploadIdentifier, BrokerageType
import constants as const


class TestBotUploadIdentifier(unittest.TestCase):
    """Test cases for BotUploadIdentifier"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests"""
        cls.identifier = BotUploadIdentifier()
        cls.min_confidence = 0.7  # Minimum confidence threshold for positive identification

    def test_identify_fidelity(self):
        """Test that Fidelity CSV is correctly identified with high confidence"""
        file_path = os.path.join(const.UPLOADS_DIR, 'sangelovich.Accounts_History-10.csv')

        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")

        brokerage_type, confidence = self.identifier.identify(file_path)

        self.assertEqual(brokerage_type, BrokerageType.FIDELITY,
                        f"Expected Fidelity but got {brokerage_type.value}")
        self.assertGreaterEqual(confidence, self.min_confidence,
                               f"Confidence {confidence:.1%} is below threshold {self.min_confidence:.1%}")

    def test_identify_robinhood(self):
        """Test that Robinhood CSV is correctly identified with high confidence"""
        file_path = os.path.join(const.UPLOADS_DIR, 'darkminer.3b67b712-69af-53c7-b872-2f4189ecc640.csv')

        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")

        brokerage_type, confidence = self.identifier.identify(file_path)

        self.assertEqual(brokerage_type, BrokerageType.ROBINHOOD,
                        f"Expected Robinhood but got {brokerage_type.value}")
        self.assertGreaterEqual(confidence, self.min_confidence,
                               f"Confidence {confidence:.1%} is below threshold {self.min_confidence:.1%}")

    def test_identify_schwab(self):
        """Test that Schwab CSV is correctly identified with high confidence"""
        file_path = os.path.join(const.UPLOADS_DIR, 'capt10l.schwab_2-1_to_8-29.csv')

        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")

        brokerage_type, confidence = self.identifier.identify(file_path)

        self.assertEqual(brokerage_type, BrokerageType.SCHWAB,
                        f"Expected Schwab but got {brokerage_type.value}")
        self.assertGreaterEqual(confidence, self.min_confidence,
                               f"Confidence {confidence:.1%} is below threshold {self.min_confidence:.1%}")

    def test_identify_ibkr(self):
        """Test that IBKR CSV is correctly identified with high confidence"""
        file_path = os.path.join(const.UPLOADS_DIR, 'ibkr_hrv_example.csv')

        if not os.path.exists(file_path):
            self.skipTest(f"Test file not found: {file_path}")

        brokerage_type, confidence = self.identifier.identify(file_path)

        self.assertEqual(brokerage_type, BrokerageType.IBKR,
                        f"Expected IBKR but got {brokerage_type.value}")
        self.assertGreaterEqual(confidence, self.min_confidence,
                               f"Confidence {confidence:.1%} is below threshold {self.min_confidence:.1%}")

    def test_unknown_format(self):
        """Test that unrecognized CSV format returns UNKNOWN"""
        # Create a temporary CSV with unknown format
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Random,Header,Columns\n")
            f.write("1,2,3\n")
            temp_file = f.name

        try:
            brokerage_type, confidence = self.identifier.identify(temp_file)

            self.assertEqual(brokerage_type, BrokerageType.UNKNOWN,
                           f"Expected UNKNOWN but got {brokerage_type.value}")
            self.assertLess(confidence, self.min_confidence,
                           f"Confidence {confidence:.1%} should be low for unknown format")
        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
