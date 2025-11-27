#!/usr/bin/env python3
"""
Test the new MCP tools: scan_options_chain and calculate_extrinsic_value

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""


import requests


BASE_URL = "http://localhost:8000"

def test_extrinsic_value():
    """Test the calculate_extrinsic_value tool"""
    print("=" * 80)
    print("TEST 1: Calculate Extrinsic Value")
    print("=" * 80)

    payload = {
        "name": "calculate_extrinsic_value",
        "arguments": {
            "ticker": "HOOD",
            "strikes": [35, 40, 45]
        }
    }

    response = requests.post(f"{BASE_URL}/tools/call", json=payload)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"Error: {result.get('isError', False)}")
        print()

        if result.get("content"):
            for item in result["content"]:
                if "text" in item:
                    print(item["text"])
        print()
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)

    return response.status_code == 200

def test_scanner():
    """Test the scan_options_chain tool"""
    print("=" * 80)
    print("TEST 2: Scan Options Chain")
    print("=" * 80)

    payload = {
        "name": "scan_options_chain",
        "arguments": {
            "symbols": ["HOOD"],
            "chain": "PUT",
            "delta_min": 0.20,
            "delta_max": 0.40,
            "max_expiration_days": 14,
            "top_candidates": 5
        }
    }

    response = requests.post(f"{BASE_URL}/tools/call", json=payload)

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"Error: {result.get('isError', False)}")
        print()

        if result.get("content"):
            for item in result["content"]:
                if "text" in item:
                    print(item["text"])

                # Also show data if available
                if "data" in item and "opportunities" in item["data"]:
                    opps = item["data"]["opportunities"]
                    print(f"\n📊 Found {len(opps)} opportunities (data format)")
        print()
    else:
        print(f"❌ Failed: {response.status_code}")
        print(response.text)

    return response.status_code == 200

def main():
    print("\n🧪 Testing New MCP Tools\n")

    # Test 1: Extrinsic Value
    test1_passed = test_extrinsic_value()

    # Test 2: Scanner
    test2_passed = test_scanner()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Extrinsic Value Tool: {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Scanner Tool:         {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print()

    if test1_passed and test2_passed:
        print("🎉 All tests passed!")
        return 0
    print("⚠️  Some tests failed")
    return 1

if __name__ == "__main__":
    exit(main())
