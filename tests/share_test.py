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
from datetime import datetime
from share import Share

class TestShare(unittest.TestCase):
    def setUp(self):
        self.username = "testuser"
        self.date = datetime.now().strftime("%m/%d/%Y")

    def test_1(self):
        raw_string = 'Buy 300 shares MSTU @ 10'
        share = Share(self.username, self.date, raw_string)
        share.parse()
        self.assertEqual(share.action, 'Buy')
        self.assertEqual(share.quantity, 300)
        self.assertEqual(share.symbol, 'MSTU')
        self.assertEqual(share.price, 10.0)

    def test_2(self):
        raw_string = 'Buy 300 MSTU @ 10'
        share = Share(self.username, self.date, raw_string)
        share.parse()
        self.assertEqual(share.action, 'Buy')
        self.assertEqual(share.quantity, 300)
        self.assertEqual(share.symbol, 'MSTU')
        self.assertEqual(share.price, 10.0)

    def test_3(self):
        raw_string = 'Buy 300 MSTU 10'
        share = Share(self.username, self.date, raw_string)
        share.parse()
        self.assertEqual(share.action, 'Buy')
        self.assertEqual(share.quantity, 300)
        self.assertEqual(share.symbol, 'MSTU')
        self.assertEqual(share.price, 10.0)



    def test_valid_trades(self):
        trades = [
            'Buy 300 shares MSTU @ 10',
            'Buy 300 shares MSTU @ $10',
            'Buy 300 MSTU @ $10',
            'Buy 300 MSTU $10',
            'Buy 250 shares MSTU @ 8.35', 
            'Sell 400 shares CONL at 28', 
            'Buy 200 shares ULTY @ 6.41',
            'Buy 1000 shares TSLL at 11.34', 
            'Buy 5 CRCL at 201.81 5', 
            'Sell 60 ETHT at 41.19',
            ]
        for trade in trades:
            share = Share(self.username, self.date, trade)
            share.parse()



if __name__ == '__main__':
    unittest.main()
