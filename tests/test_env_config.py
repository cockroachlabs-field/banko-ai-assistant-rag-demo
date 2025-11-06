#!/usr/bin/env python3
"""Quick test to verify environment variable configuration"""

import os
import sys

print("="*70)
print("ENVIRONMENT VARIABLE TEST")
print("="*70)
print()

# Check current environment
print("Current Environment Variables:")
print(f"  CACHE_SIMILARITY_THRESHOLD = '{os.getenv('CACHE_SIMILARITY_THRESHOLD')}'")
print(f"  CACHE_STRICT_MODE = '{os.getenv('CACHE_STRICT_MODE')}'")
print(f"  CACHE_TTL_HOURS = '{os.getenv('CACHE_TTL_HOURS')}'")
print()

# Import and create cache manager
print("Creating Cache Manager...")
print()

from banko_ai.utils.cache_manager import BankoCacheManager
cache = BankoCacheManager()

print()
print("="*70)
print("VERIFICATION")
print("="*70)
print()

# Verify settings
expected_strict = os.getenv('CACHE_STRICT_MODE', 'true').lower() == 'true'
expected_threshold = float(os.getenv('CACHE_SIMILARITY_THRESHOLD', '0.75'))
expected_ttl = int(os.getenv('CACHE_TTL_HOURS', '24'))

all_correct = True

if cache.strict_mode == expected_strict:
    print(f"✅ Strict mode correct: {cache.strict_mode}")
else:
    print(f"❌ Strict mode WRONG: got {cache.strict_mode}, expected {expected_strict}")
    all_correct = False

if cache.similarity_threshold == expected_threshold:
    print(f"✅ Threshold correct: {cache.similarity_threshold}")
else:
    print(f"❌ Threshold WRONG: got {cache.similarity_threshold}, expected {expected_threshold}")
    all_correct = False

if cache.cache_ttl_hours == expected_ttl:
    print(f"✅ TTL correct: {cache.cache_ttl_hours}")
else:
    print(f"❌ TTL WRONG: got {cache.cache_ttl_hours}, expected {expected_ttl}")
    all_correct = False

print()
if all_correct:
    print("🎉 SUCCESS! All environment variables are working correctly!")
    sys.exit(0)
else:
    print("⚠️  PROBLEM: Some environment variables are not being read correctly")
    print()
    print("Make sure to set them BEFORE running this script:")
    print("  export CACHE_STRICT_MODE=false")
    print("  python test_env_config.py")
    sys.exit(1)
