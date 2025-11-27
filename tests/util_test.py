#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
import tempfile
import logging
from datetime import datetime, timedelta
from util import (
    currency_to_float, parse_string, to_db_date, is_date_db_format,
    week_start_end, month_start_end, month_iterator, current_year,
    create_pdf, create_zip_archive, get_logger, set_log_level, setup_logger
)

# def parse_string(s):
#     def parse_part(part):
#         if '-' in part:
#             try:
#                 start, end_step = part.split('-')
#                 start = float(start)
#                 if '(' in end_step:
#                     end, step = end_step.rstrip(')').split('(')
#                     end = float(end)
#                     step = float(step)
#                     return [start + i * step for i in range(int((end - start) / step) + 1)]
#                 else:
#                     end = float(end_step)
#                     return list(range(int(start), int(end) + 1))
#             except (ValueError, TypeError):
#                 raise ValueError(f"Invalid range format: {part}")
#         else:
#             try:
#                 return [float(part)]
#             except ValueError:
#                 raise ValueError(f"Invalid number format: {part}")

#     result = []
#     parts = s.split(',')
#     for part in parts:
#         part = part.strip()
#         result.extend(parse_part(part))
    
#     # Remove duplicates and sort the result to ensure correct order
#     return sorted(set(result))

class TestParseString(unittest.TestCase):
    def test_correct_range(self):
        self.assertEqual(parse_string("1-3"), [1, 2, 3])

    def test_multiple_ranges_and_numbers(self):
        self.assertEqual(parse_string("1-3,5,7-9"), [1, 2, 3, 5, 7, 8, 9])

    def test_range_with_step(self):
        self.assertEqual(parse_string("1-10(2)"), [1, 3, 5, 7, 9])

    def test_multiple_ranges_and_steps(self):
        self.assertEqual(parse_string("1-10(2),15"), [1, 3, 5, 7, 9, 15])

    def test_float_range_with_step(self):
        self.assertEqual(parse_string("1.5-4.5(1.2)"), [1.5, 2.7, 3.9])

    def test_float_range_with_step_0_5(self):
        self.assertEqual(parse_string("1.5-3.0(0.5)"), [1.5, 2.0, 2.5, 3.0])

    def test_incorrectly_formatted_input(self):
        with self.assertRaises(ValueError):
            parse_string("1-a")

    def test_incorrectly_formatted_input_with_x(self):
        with self.assertRaises(ValueError):
            parse_string("1,2,x")

class TestParseDate(unittest.TestCase):
    def test_dt1(self):
        self.assertEqual(to_db_date('1/1'), '2025-01-01')
    def test_dt2(self):
        self.assertEqual(to_db_date('1/1/25'), '2025-01-01')
    def test_dt3(self):
        self.assertEqual(to_db_date('1-1'), '2025-01-01')
    def test_d43(self):
        self.assertEqual(to_db_date('1-1-2025'), '2025-01-01')

class TestParseCurrenctyStr(unittest.TestCase):
    def test_s1(self):
        self.assertEqual(currency_to_float('.05'), .05)
    def test_s2(self):
        self.assertEqual(currency_to_float('-.05'), -.05)
    def test_s3(self):
        self.assertEqual(currency_to_float('$1.05'), 1.05)
    def test_s4(self):
        self.assertEqual(currency_to_float('$(1.05)'), -1.05)
    def test_s5(self):
        self.assertEqual(currency_to_float('(1.05)'), -1.05)
    def test_s6(self):
        self.assertEqual(currency_to_float('($1.05)'), -1.05)
    def test_s7(self):
        self.assertEqual(currency_to_float('1,101.05'), 1101.05)


class TestIsDateDbFormat(unittest.TestCase):
    """Test is_date_db_format() function"""

    def test_valid_db_format(self):
        """Test that valid YYYY-MM-DD format returns True"""
        self.assertTrue(is_date_db_format('2025-01-15'))
        self.assertTrue(is_date_db_format('2025-12-31'))
        self.assertTrue(is_date_db_format('2024-02-29'))  # Leap year

    def test_invalid_formats(self):
        """Test that invalid formats return False"""
        self.assertFalse(is_date_db_format('01/15/2025'))
        self.assertFalse(is_date_db_format('1/1'))
        self.assertFalse(is_date_db_format('2025-13-01'))  # Invalid month
        self.assertFalse(is_date_db_format('not-a-date'))
        self.assertFalse(is_date_db_format(''))


class TestWeekStartEnd(unittest.TestCase):
    """Test week_start_end() function"""

    def test_monday(self):
        """Test when input is Monday"""
        monday = datetime(2025, 1, 6)  # Monday
        start, end = week_start_end(monday)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-01-06')
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-01-10')  # Friday

    def test_wednesday(self):
        """Test when input is Wednesday (mid-week)"""
        wednesday = datetime(2025, 1, 8)  # Wednesday
        start, end = week_start_end(wednesday)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-01-06')  # Previous Monday
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-01-10')  # Same Friday

    def test_sunday(self):
        """Test when input is Sunday"""
        sunday = datetime(2025, 1, 12)  # Sunday
        start, end = week_start_end(sunday)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-01-06')  # Previous Monday
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-01-10')  # Previous Friday


class TestMonthStartEnd(unittest.TestCase):
    """Test month_start_end() function"""

    def test_january(self):
        """Test January (31 days)"""
        jan_15 = datetime(2025, 1, 15)
        start, end = month_start_end(jan_15)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-01-01')
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-01-31')

    def test_february_non_leap(self):
        """Test February in non-leap year (28 days)"""
        feb_15 = datetime(2025, 2, 15)
        start, end = month_start_end(feb_15)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-02-01')
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-02-28')

    def test_february_leap(self):
        """Test February in leap year (29 days)"""
        feb_15 = datetime(2024, 2, 15)
        start, end = month_start_end(feb_15)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2024-02-01')
        self.assertEqual(end.strftime('%Y-%m-%d'), '2024-02-29')

    def test_december(self):
        """Test December (last month of year)"""
        dec_15 = datetime(2025, 12, 15)
        start, end = month_start_end(dec_15)
        self.assertEqual(start.strftime('%Y-%m-%d'), '2025-12-01')
        self.assertEqual(end.strftime('%Y-%m-%d'), '2025-12-31')


class TestMonthIterator(unittest.TestCase):
    """Test month_iterator() function"""

    def test_same_month(self):
        """Test iteration within same month"""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)
        months = list(month_iterator(start, end))
        self.assertEqual(months, ['2025-01-01'])

    def test_three_months(self):
        """Test iteration across three months"""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 3, 15)
        months = list(month_iterator(start, end))
        self.assertEqual(months, ['2025-01-01', '2025-02-01', '2025-03-01'])

    def test_year_boundary(self):
        """Test iteration across year boundary"""
        start = datetime(2024, 11, 1)
        end = datetime(2025, 2, 1)
        months = list(month_iterator(start, end))
        self.assertEqual(months, ['2024-11-01', '2024-12-01', '2025-01-01', '2025-02-01'])


class TestCurrentYear(unittest.TestCase):
    """Test current_year() function"""

    def test_returns_integer(self):
        """Test that current_year returns an integer"""
        year = current_year()
        self.assertIsInstance(year, int)

    def test_reasonable_year(self):
        """Test that current_year returns a reasonable year"""
        year = current_year()
        self.assertGreaterEqual(year, 2024)
        self.assertLessEqual(year, 2030)


class TestCreatePdf(unittest.TestCase):
    """Test create_pdf() function"""

    def test_creates_pdf_from_markdown(self):
        """Test PDF creation from markdown file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a markdown file
            md_path = os.path.join(tmpdir, 'test.md')
            pdf_path = os.path.join(tmpdir, 'test.pdf')

            with open(md_path, 'w') as f:
                f.write('# Test Header\n\nTest content.')

            # Create PDF
            create_pdf(md_path, pdf_path)

            # Verify PDF was created
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 0)


class TestCreateZipArchive(unittest.TestCase):
    """Test create_zip_archive() function"""

    def test_creates_zip_with_multiple_files(self):
        """Test zip creation with multiple files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            file1 = os.path.join(tmpdir, 'file1.txt')
            file2 = os.path.join(tmpdir, 'file2.txt')
            with open(file1, 'w') as f:
                f.write('File 1 content')
            with open(file2, 'w') as f:
                f.write('File 2 content')

            # Create zip
            zip_path = os.path.join(tmpdir, 'archive.zip')
            create_zip_archive(zip_path, [file1, file2])

            # Verify zip was created
            self.assertTrue(os.path.exists(zip_path))
            self.assertGreater(os.path.getsize(zip_path), 0)

    def test_handles_missing_file(self):
        """Test that missing files are skipped with warning"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create one real file and reference one missing file
            file1 = os.path.join(tmpdir, 'file1.txt')
            file2 = os.path.join(tmpdir, 'missing.txt')
            with open(file1, 'w') as f:
                f.write('File 1 content')

            # Create zip (should succeed even with missing file)
            zip_path = os.path.join(tmpdir, 'archive.zip')
            create_zip_archive(zip_path, [file1, file2])

            # Verify zip was created with available file
            self.assertTrue(os.path.exists(zip_path))


class TestLoggerFunctions(unittest.TestCase):
    """Test logger-related functions"""

    def test_get_logger(self):
        """Test get_logger() returns logger instance"""
        logger = get_logger('test_module')
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'test_module')

    def test_setup_logger_with_name(self):
        """Test setup_logger() with explicit name"""
        # Clear any existing handlers
        test_logger = logging.getLogger('test_setup')
        test_logger.handlers.clear()

        logger = setup_logger('test_setup', level='DEBUG', console=False)
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'test_setup')
        self.assertGreater(len(logger.handlers), 0)

    def test_setup_logger_prevents_duplicate_handlers(self):
        """Test that setup_logger doesn't add duplicate handlers"""
        test_logger = logging.getLogger('test_dup')
        test_logger.handlers.clear()

        # First call
        logger1 = setup_logger('test_dup', level='INFO', console=False)
        handler_count_1 = len(logger1.handlers)

        # Second call should return same logger without adding handlers
        logger2 = setup_logger('test_dup', level='INFO', console=False)
        handler_count_2 = len(logger2.handlers)

        self.assertEqual(handler_count_1, handler_count_2)

    def test_set_log_level(self):
        """Test set_log_level() changes log level"""
        root_logger = logging.getLogger()
        original_level = root_logger.level

        # Change to DEBUG
        set_log_level('DEBUG')
        self.assertEqual(root_logger.level, logging.DEBUG)

        # Change to WARNING
        set_log_level('WARNING')
        self.assertEqual(root_logger.level, logging.WARNING)

        # Restore original level
        root_logger.setLevel(original_level)


if __name__ == '__main__':
    unittest.main()