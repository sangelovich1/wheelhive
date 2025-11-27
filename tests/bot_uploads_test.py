"""
Unit tests for BotUploads class

Tests the automatic brokerage identification and CSV upload processing
for all supported brokerage formats (Fidelity, Robinhood, Schwab, IBKR).

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
import glob
from db import Db
from trades import Trades
from dividends import Dividends
from shares import Shares
from deposits import Deposits
from bot_uploads import BotUploads
from bot_upload_identifier import BotUploadIdentifier, BrokerageType
from reports.profittreport import ProfitReport
import constants as const


class TestBotUploads(unittest.TestCase):
    """Test cases for BotUploads functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests"""
        # Use in-memory database for faster, isolated testing
        cls.db = Db(in_memory=True)
        cls.trades = Trades(cls.db)
        cls.dividends = Dividends(cls.db)
        cls.shares = Shares(cls.db)
        cls.deposits = Deposits(cls.db)
        cls.identifier = BotUploadIdentifier()
        cls.username = 'testuser'

    def setUp(self):
        """Set up before each test"""
        # Clean up existing test data
        self.trades.delete_all(self.username)
        self.dividends.delete_all(self.username)
        self.shares.delete_all(self.username)
        self.deposits.delete_all(self.username)

    def tearDown(self):
        """Clean up after each test"""
        # Clean up test data
        self.trades.delete_all(self.username)
        self.dividends.delete_all(self.username)
        self.shares.delete_all(self.username)
        self.deposits.delete_all(self.username)

    def test_upload_with_automatic_detection(self):
        """Test uploading CSV files with automatic format detection"""
        import random

        # Find all CSV files in the uploads directory
        all_csv_files = sorted(glob.glob(os.path.join(const.UPLOADS_DIR, '*.csv')))

        self.assertGreater(len(all_csv_files), 0, f"No CSV files found in {const.UPLOADS_DIR}")

        # Randomly select 5 files for testing (or fewer if less than 5 exist)
        num_files = min(5, len(all_csv_files))
        csv_files = random.sample(all_csv_files, num_files)

        print(f"\nTesting {num_files} randomly selected CSV files from {len(all_csv_files)} total files in {const.UPLOADS_DIR}")

        successful_uploads = 0
        successful_reports = 0
        failed_uploads = 0
        unknown_formats = 0

        for fname in csv_files:
            with self.subTest(file=fname):
                print(f'\n{"="*60}')
                print(f'Testing: {os.path.basename(fname)}')

                try:
                    # Automatically detect brokerage format
                    brokerage_type, confidence = self.identifier.identify(fname)
                    format = brokerage_type.value

                    print(f'Detected: {format} (confidence: {confidence:.1%})')

                    if brokerage_type == BrokerageType.UNKNOWN:
                        print(f'WARNING: Unable to identify format')
                        unknown_formats += 1
                        continue

                    # Verify confidence is reasonable
                    self.assertGreaterEqual(confidence, 0.3,
                                          f"Confidence too low for {fname}")

                    # Clean existing data
                    self.trades.delete_all(self.username)
                    self.dividends.delete_all(self.username)
                    self.shares.delete_all(self.username)
                    self.deposits.delete_all(self.username)

                    # Process the upload
                    bot_uploads = BotUploads(fname, format, self.trades,
                                            self.dividends, self.shares, self.deposits)
                    status, msg = bot_uploads.process(self.username)

                    print(f'Status: {status}')
                    print(f'Message: {msg}')

                    # Verify upload was successful
                    self.assertTrue(status, f"Upload failed for {fname}: {msg}")
                    successful_uploads += 1

                    # Generate report to verify data integrity
                    report = ProfitReport(self.db, self.username)
                    report_result = report.report()
                    self.assertIsNotNone(report_result, f"Report generation failed for {fname}")
                    successful_reports += 1

                except Exception as e:
                    print(f'ERROR: {str(e)}')
                    failed_uploads += 1
                    self.fail(f"Exception during upload of {fname}: {str(e)}")

        # Print summary
        print(f'\n{"="*60}')
        print("UPLOAD TEST SUMMARY")
        print(f'{"="*60}')
        print(f"Files tested: {len(csv_files)} (randomly selected from {len(all_csv_files)} total)")
        print(f"Successful: {successful_uploads}")
        print(f"Successful Reports: {successful_reports}")
        print(f"Failed: {failed_uploads}")
        print(f"Unknown format: {unknown_formats}")
        print(f'{"="*60}\n')

        # Verify all files successful upload
        self.assertEqual(successful_uploads, num_files, "Some files were not successfully uploaded")
        self.assertEqual(successful_uploads, successful_reports, "Report generation failed for some uploads")

    def test_specific_brokerage_formats(self):
        """Test that we can process at least one file from each brokerage"""
        test_files = {
            'fidelity': os.path.join(const.UPLOADS_DIR, 'sangelovich.Accounts_History-10.csv'),
            'robinhood': os.path.join(const.UPLOADS_DIR, 'darkminer.3b67b712-69af-53c7-b872-2f4189ecc640.csv'),
            'schwab': os.path.join(const.UPLOADS_DIR, 'capt10l.schwab_2-1_to_8-29.csv'),
            'ibkr': os.path.join(const.UPLOADS_DIR, 'ibkr_hrv_example.csv'),
        }

        for brokerage, filepath in test_files.items():
            with self.subTest(brokerage=brokerage):
                if not os.path.exists(filepath):
                    self.skipTest(f"Test file not found: {filepath}")

                print(f"\nTesting {brokerage} format with {filepath}")

                # Detect format
                brokerage_type, confidence = self.identifier.identify(filepath)
                detected_format = brokerage_type.value

                print(f"Detected: {detected_format} (confidence: {confidence:.1%})")

                # Verify correct detection
                self.assertEqual(detected_format, brokerage, f"Format mismatch for {brokerage}")

                # Clean and process
                self.trades.delete_all(self.username)
                self.dividends.delete_all(self.username)
                self.shares.delete_all(self.username)
                self.deposits.delete_all(self.username)

                bot_uploads = BotUploads(filepath, detected_format, self.trades,
                                        self.dividends, self.shares, self.deposits)
                status, msg = bot_uploads.process(self.username)

                self.assertTrue(status, f"Upload failed for {brokerage}: {msg}")
                print(f"✓ {brokerage} upload successful")

    def test_identifier_confidence_scores(self):
        """Test that identifier returns reasonable confidence scores"""
        csv_files = glob.glob(os.path.join(const.UPLOADS_DIR, '*.csv'))[:5]

        for fname in csv_files:
            with self.subTest(file=fname):
                brokerage_type, confidence = self.identifier.identify(fname)

                # Confidence should be between 0 and 1 (allowing for floating point precision)
                self.assertGreaterEqual(confidence, 0.0)
                self.assertAlmostEqual(confidence, min(confidence, 1.0), places=7,
                                      msg=f"Confidence {confidence} exceeds 1.0")

                # If identified (not UNKNOWN), confidence should be >= 0.3
                if brokerage_type != BrokerageType.UNKNOWN:
                    self.assertGreaterEqual(confidence, 0.3,
                                          f"Low confidence for identified file: {fname}")

    def test_formats_supported(self):
        """Test that formats_supported returns expected brokerages"""
        formats = BotUploads.formats_supported()

        expected_formats = ['fidelity', 'robinhood', 'schwab', 'ibkr']
        self.assertEqual(formats, expected_formats)


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
