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
from dividends import Dividends

class TestParse(unittest.TestCase):
    def test_1(self):
        dt = Dividends.parse("Divided 5/23 YMAX 15.01" )
        self.assertIsNotNone(dt)
        self.assertEqual(dt.Date, '2025-05-23')
        self.assertEqual(dt.Symbol, 'YMAX')
        self.assertEqual(dt.Amount, 15.01)

if __name__ == '__main__':
    unittest.main()

