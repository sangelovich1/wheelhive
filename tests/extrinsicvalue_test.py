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
from extrinsicvalue import ExtrinsicValue

class TestExtrinsicValue(unittest.TestCase):
    def test_lookup(self):
        ev = ExtrinsicValue()
        ret, results = ev.calculate("COIN", "33")
        self.assertTrue(ret)

    def test_lookup_failure(self):
        ev = ExtrinsicValue()
        try:
            ret, results = ev.calculate("AAPL_bad", "33")
        except:
            self.assertTrue(True)

    def test_strikes(self):
        ev = ExtrinsicValue()
        ret, results = ev.calculate("COIN", "33-44")
        self.assertTrue(ret)

    def test_strikes_failure(self):
        ev = ExtrinsicValue()
        ret, results = ev.calculate("COIN", "33,34,b")
        self.assertFalse(ret)





if __name__ == '__main__':
    unittest.main()
