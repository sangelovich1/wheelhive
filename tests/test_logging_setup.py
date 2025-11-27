#!/usr/bin/env python3
"""
Test script to verify the new logging setup in util.py

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import util
import logging

def test_basic_setup():
    """Test basic logger setup"""
    print("=" * 60)
    print("Test 1: Basic Logger Setup")
    print("=" * 60)

    # Setup root logger
    util.setup_logger(name=None, level='INFO', console=True)

    # Get module-specific logger
    logger = util.get_logger(__name__)

    logger.debug("This is a DEBUG message (should not appear in console with INFO level)")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")

    print("\n✓ Basic logging test completed\n")


def test_get_logger():
    """Test get_logger helper"""
    print("=" * 60)
    print("Test 2: get_logger() Helper")
    print("=" * 60)

    logger1 = util.get_logger("test.module1")
    logger2 = util.get_logger("test.module2")

    logger1.info("Message from module1")
    logger2.info("Message from module2")

    print("\n✓ get_logger() test completed\n")


def test_level_change():
    """Test dynamic level change"""
    print("=" * 60)
    print("Test 3: Dynamic Level Change")
    print("=" * 60)

    logger = util.get_logger(__name__)

    logger.info("Before level change - INFO level")
    logger.debug("Before level change - DEBUG (should not appear)")

    print("\nChanging log level to DEBUG...\n")
    util.set_log_level('DEBUG')

    logger.info("After level change - INFO level")
    logger.debug("After level change - DEBUG (should now appear)")

    print("\nChanging log level back to INFO...\n")
    util.set_log_level('INFO')

    logger.info("After reverting - INFO level")
    logger.debug("After reverting - DEBUG (should not appear again)")

    print("\n✓ Level change test completed\n")


def test_file_logging():
    """Test that logs are written to file"""
    print("=" * 60)
    print("Test 4: File Logging")
    print("=" * 60)

    logger = util.get_logger(__name__)

    logger.info("This message should be in bot.log")
    logger.debug("This debug message should also be in bot.log (file captures DEBUG)")

    # Check if log file exists
    if os.path.exists('bot.log'):
        with open('bot.log', 'r') as f:
            lines = f.readlines()
            print(f"\nLog file contains {len(lines)} lines")
            print("Last 5 log entries:")
            for line in lines[-5:]:
                print(f"  {line.rstrip()}")
        print("\n✓ Log file created and contains entries\n")
    else:
        print("\n✗ Log file not found!\n")


def test_no_duplicate_handlers():
    """Test that calling setup_logger multiple times doesn't create duplicates"""
    print("=" * 60)
    print("Test 5: No Duplicate Handlers")
    print("=" * 60)

    logger1 = util.setup_logger(name=None, level='INFO', console=True)
    handler_count_1 = len(logging.getLogger().handlers)
    print(f"After first setup: {handler_count_1} handlers")

    logger2 = util.setup_logger(name=None, level='INFO', console=True)
    handler_count_2 = len(logging.getLogger().handlers)
    print(f"After second setup: {handler_count_2} handlers")

    if handler_count_1 == handler_count_2:
        print("✓ No duplicate handlers created\n")
    else:
        print("✗ Duplicate handlers detected!\n")


def test_exception_logging():
    """Test exception logging with traceback"""
    print("=" * 60)
    print("Test 6: Exception Logging")
    print("=" * 60)

    logger = util.get_logger(__name__)

    try:
        # Trigger an exception
        result = 1 / 0
    except Exception as e:
        logger.error(f"Caught exception: {e}", exc_info=True)

    print("\n✓ Exception logged with traceback\n")


def main():
    print("\n" + "=" * 60)
    print("Testing New Logging Setup")
    print("=" * 60 + "\n")

    # Clean up old log file for testing
    if os.path.exists('bot.log'):
        os.remove('bot.log')
        print("Cleaned up old bot.log\n")

    try:
        test_basic_setup()
        test_get_logger()
        test_level_change()
        test_file_logging()
        test_no_duplicate_handlers()
        test_exception_logging()

        print("=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        print("\nCheck bot.log for detailed file output")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
