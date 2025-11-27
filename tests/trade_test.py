#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

# test_trade.py
import sys
import os
# Add src to path for imports (needed when running test file directly)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from datetime import datetime
from trade import Trade

class TestTrade(unittest.TestCase):
    def setUp(self):
        self.username = "testuser"
        self.date = datetime.now().strftime("%m%d/%Y")

    def test_valid_trade_1(self):
        raw_trade_string = "STO 3x AAPL 5/23 $150P for $1.50"
        trade = Trade(self.username, self.date, raw_trade_string)
        trade.parse()
        self.assertEqual(trade.operation, "STO")
        self.assertEqual(trade.contracts, 3)
        self.assertEqual(trade.symbol, "AAPL")
        self.assertEqual(trade.expiration_date, "2025-05-23")
        self.assertEqual(trade.strike_price, 150)
        self.assertEqual(trade.option_type, "P")
        self.assertEqual(trade.premium, 1.50)
        self.assertFalse(trade.partial_result)

    def test_valid_trade_2(self):
        raw_trade_string = "STO 3x AAPL 5/23 $150P for $1.50"
        trade = Trade(self.username, self.date, raw_trade_string)
        trade.parse()
        self.assertEqual(trade.operation, "STO")
        self.assertEqual(trade.contracts, 3)
        self.assertEqual(trade.symbol, "AAPL")
        self.assertEqual(trade.expiration_date, "2025-05-23")
        self.assertEqual(trade.strike_price, 150)
        self.assertEqual(trade.option_type, "P")
        self.assertEqual(trade.premium, 1.50)
        self.assertFalse(trade.partial_result)

    def test_valid_trade_list(self):
        trades = list()
        trades.append('STO 1 TSLA 320P 5/30 @ 2.90')
        trades.append('BTO 1 TSLA 380C 8/15 @ 29.95')
        trades.append('BTC 20 TSLL 15C 5/23 @ .03')
        trades.append('STO 20 TSLL 15.5C 5/30 @ .41')
        trades.append('STO 2x nvda 117P  5/30  for $125')
        trades.append('STO 2x nvdl 40P  5/30 for $65')
        for trade_str in trades:
            trade = Trade(self.username, self.date, trade_str)
            trade.parse()
            self.assertFalse(trade.partial_result)

    def test_more_trade_list(self):
        trades = list()
        trades.append('STO 2x MSTU 8/1 8P .16')
        trades.append('BTC 10x TSLL 8/1 10.5P .11')
        trades.append('BTC 1x CRCL 9/19 180.0P 14')
        trades.append('STO 3x HOOD 8/1 92P .72')
        trades.append('STO 2x TSLL 8/8 13C .34')
        trades.append('STO 3x CONL 8/15 40P 1.15')
        trades.append('STO 3x 8/15 CONL 40P at 1.15')
        for trade_str in trades:
            trade = Trade(self.username, self.date, trade_str)
            trade.parse()
            self.assertFalse(trade.partial_result)

    def test_valid_trade_3(self):
        raw_trade_string = "STO 3x AAPL 5/23 $150P @$1.50"
        trade = Trade(self.username, self.date, raw_trade_string)
        trade.parse()
        self.assertEqual(trade.operation, "STO")
        self.assertEqual(trade.contracts, 3)
        self.assertEqual(trade.symbol, "AAPL")
        self.assertEqual(trade.expiration_date, "2025-05-23")
        self.assertEqual(trade.strike_price, 150)
        self.assertEqual(trade.option_type, "P")
        self.assertEqual(trade.premium, 1.50)
        self.assertFalse(trade.partial_result)


if __name__ == '__main__':
    unittest.main()