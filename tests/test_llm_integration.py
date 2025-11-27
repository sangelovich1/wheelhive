#!/usr/bin/env python3
"""
Test script for multi-model LLM integration.

Tests:
1. User preferences database creation
2. Model selection and tier validation
3. LLM provider initialization
4. Available models listing

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from db import Db
from user_preferences import UserPreferences, get_user_preferences
from llm_provider import create_llm_provider, list_available_models
import constants as const


def test_database_creation():
    """Test 1: Database table creation"""
    print("=" * 60)
    print("TEST 1: Database Table Creation")
    print("=" * 60)

    try:
        db = Db()
        user_prefs = UserPreferences(db)
        print("✓ user_preferences table created successfully")

        # Check table exists
        result = db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if result:
            print(f"✓ Table confirmed in database: {result}")
        else:
            print("✗ Table not found in database")
            return False

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_user_preferences():
    """Test 2: User preference management"""
    print("\n" + "=" * 60)
    print("TEST 2: User Preference Management")
    print("=" * 60)

    try:
        user_prefs = get_user_preferences()
        test_user = "test_user"

        # Test default model
        default_model = user_prefs.get_llm_preference(test_user)
        print(f"✓ Default model for new user: {default_model}")
        print(f"  Display name: {const.AVAILABLE_MODELS[default_model]['display_name']}")

        # Test default tier - POSTPONED: tier feature not implemented yet
        # default_tier = user_prefs.get_user_tier(test_user)
        # print(f"✓ Default tier: {default_tier}")

        # Test setting a model
        print("\nTesting model selection...")
        # With 'plus' tier, we can use any model
        test_model = 'claude-haiku'  # Test with a cloud model
        success = user_prefs.set_llm_preference(test_user, test_model)
        if success:
            print(f"✓ Successfully set model to {test_model}")

            # Verify it was saved
            saved_model = user_prefs.get_llm_preference(test_user)
            if saved_model == test_model:
                print("✓ Model preference persisted correctly")
            else:
                print(f"✗ Model not saved correctly: {saved_model}")
                return False
        else:
            print(f"✗ Failed to set model preference to {test_model}")
            return False

        # Test tier access control
        print("\nTesting tier access control...")
        # With 'plus' tier, all models should be accessible
        if default_tier == 'plus':
            # Test that we can set any model
            success = user_prefs.set_llm_preference(test_user, 'claude-sonnet')
            if success:
                print("✓ Tier access control working (plus tier can access all models)")
                # Reset back to test model
                user_prefs.set_llm_preference(test_user, test_model)
            else:
                print("✗ Tier access control failed (plus tier should access all models)")
        else:
            # For other tiers, test restrictions
            success = user_prefs.set_llm_preference(test_user, 'claude-sonnet')
            if not success:
                print(f"✓ Tier access control working (blocked premium model for {default_tier} tier)")
            else:
                print(f"✗ Tier access control failed (allowed premium model for {default_tier} tier)")

        # Test listing available models
        print("\nTesting list_available_models...")
        available = user_prefs.list_available_models(test_user)
        print(f"✓ Found {len(available)} available models for tier '{default_tier}'")
        for model_key, model_info in available[:3]:  # Show first 3
            print(f"  - {model_info['display_name']} ({model_key})")

        # Test get_user_summary
        print("\nTesting get_user_summary...")
        summary = user_prefs.get_user_summary(test_user)
        print(f"✓ User summary retrieved:")
        print(f"  Current model: {summary['model_display_name']}")
        print(f"  Provider: {summary['model_provider']}")
        print(f"  Tier: {summary['user_tier']}")
        print(f"  Available models: {summary['model_count']}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_provider():
    """Test 3: LLM Provider initialization"""
    print("\n" + "=" * 60)
    print("TEST 3: LLM Provider Initialization")
    print("=" * 60)

    try:
        # Test with default model
        print("Testing default model initialization...")
        provider = create_llm_provider()
        model_info = provider.get_model_info()
        print(f"✓ LLM Provider created with default model")
        print(f"  Model: {model_info['display_name']}")
        print(f"  LiteLLM model: {model_info['litellm_model']}")
        print(f"  Provider: {model_info['provider']}")
        print(f"  Tool calling: {model_info['supports_tool_calling']}")
        print(f"  Quality: {model_info['quality']}/5")
        print(f"  Speed: {model_info['speed']}")

        # Test with specific user
        print("\nTesting user-specific model...")
        user_prefs = get_user_preferences()
        user_prefs.set_user_tier("test_user", "plus")  # Give access to all models
        user_prefs.set_llm_preference("test_user", "claude-haiku")

        provider2 = create_llm_provider(username="test_user")
        model_info2 = provider2.get_model_info()
        print(f"✓ LLM Provider created for test_user")
        print(f"  Model: {model_info2['display_name']}")
        print(f"  Provider: {model_info2['provider']}")

        # Test with explicit model override
        print("\nTesting explicit model override...")
        provider3 = create_llm_provider(model_key="claude-sonnet")
        model_info3 = provider3.get_model_info()
        print(f"✓ LLM Provider created with explicit model")
        print(f"  Model: {model_info3['display_name']}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_configurations():
    """Test 4: Model configurations"""
    print("\n" + "=" * 60)
    print("TEST 4: Model Configurations")
    print("=" * 60)

    try:
        print(f"Total models configured: {len(const.AVAILABLE_MODELS)}")
        print("\nModels by provider:")

        providers = {}
        for model_key, model_info in const.AVAILABLE_MODELS.items():
            provider = model_info['provider']
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(model_key)

        for provider, models in providers.items():
            print(f"\n{provider.upper()}:")
            for model_key in models:
                model_info = const.AVAILABLE_MODELS[model_key]
                tool_calling = "✓" if model_info['tool_calling'] else "✗"
                print(f"  [{tool_calling}] {model_info['display_name']:<30} ({model_key})")
                print(f"      Cost: {model_info['cost_tier']:<10} Quality: {model_info['quality']}/5  Speed: {model_info['speed']}")

        # Test tier configurations
        print(f"\n\nTier configurations:")
        for tier, models in const.TIER_MODEL_ACCESS.items():
            print(f"  {tier}: {len(models)} models")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_key_configuration():
    """Test 5: API key configuration"""
    print("\n" + "=" * 60)
    print("TEST 5: API Key Configuration")
    print("=" * 60)

    print("\nChecking API keys in environment:")

    keys = {
        'ANTHROPIC_API_KEY': const.ANTHROPIC_API_KEY,
        'OLLAMA_BASE_URL': const.OLLAMA_BASE_URL
    }

    for key_name, key_value in keys.items():
        if key_value:
            masked = key_value[:10] + "..." if len(key_value) > 10 else "***"
            print(f"  ✓ {key_name}: {masked}")
        else:
            print(f"  ✗ {key_name}: Not set")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MULTI-MODEL LLM INTEGRATION TEST SUITE")
    print("=" * 60)

    tests = [
        ("Database Creation", test_database_creation),
        ("User Preferences", test_user_preferences),
        ("LLM Provider", test_llm_provider),
        ("Model Configurations", test_model_configurations),
        ("API Key Configuration", test_api_key_configuration)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Multi-model LLM integration is working.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
