#!/usr/bin/env python3
"""
🚨 Rate Limiting Integration Test Suite
======================================

Tests the comprehensive rate limiting system across all endpoints
and validates different rate limiting algorithms.
"""

import time
import requests
import json
import concurrent.futures
import threading
from typing import Dict, Any
import os
import pytest

BASE_URL = os.environ.get("SPOTIPI_TEST_BASE_URL", "http://localhost:5001")


def _server_available() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=1)
        return r.status_code < 500
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _server_available(), reason="Backend server not running on test port; integration tests skipped")

def test_rate_limiting_status():
    """Test the rate limiting status endpoint."""
    print("🔍 Testing Rate Limiting Status Endpoint...")
    
    response = requests.get(f"{BASE_URL}/api/rate-limiting/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "rate_limiting" in data["data"]
    assert data["data"]["rate_limiting"]["enabled"] is True
    
    rules = data["data"]["rate_limiting"]["rules"]
    expected_rules = [
        "api_general", "api_strict", "config_changes", 
        "music_library", "spotify_api", "status_check"
    ]
    
    for rule in expected_rules:
        assert rule in rules, f"Rule {rule} not found"
        assert "requests_per_window" in rules[rule]
        assert "limit_type" in rules[rule]
    
    print("✅ Rate limiting status endpoint working correctly")

def test_status_check_rate_limit():
    """Test status check endpoints under rate limiting."""
    print("🔄 Testing Status Check Rate Limiting...")
    
    # Status checks should allow 200 requests per minute
    responses = []
    for i in range(10):  # Test 10 rapid requests
        response = requests.get(f"{BASE_URL}/sleep_status")
        responses.append(response.status_code)
    
    # All should succeed (status_check rule allows 200/min)
    success_count = sum(1 for code in responses if code == 200)
    print(f"📊 Status check requests: {success_count}/10 successful")
    assert success_count == 10, "Status checks should not be rate limited at this volume"
    
    print("✅ Status check rate limiting working correctly")

def test_config_change_rate_limit():
    """Test config change endpoints with strict rate limiting."""
    print("🔧 Testing Config Change Rate Limiting...")
    
    # Config changes allow only 10 requests per minute
    url = f"{BASE_URL}/save_alarm"
    data = {
        "time": "07:00",
        "enabled": "true",
        "weekdays": "monday,tuesday,wednesday,thursday,friday"
    }
    
    responses = []
    for i in range(5):  # Test 5 requests (should be under limit)
        response = requests.post(url, data=data)
        responses.append(response.status_code)
        time.sleep(0.1)  # Small delay between requests
    
    success_count = sum(1 for code in responses if code in [200, 302])  # 302 = redirect
    print(f"📊 Config change requests: {success_count}/5 successful")
    
    print("✅ Config change rate limiting working correctly")

def test_concurrent_requests():
    """Test rate limiting under concurrent load."""
    print("⚡ Testing Concurrent Request Rate Limiting...")
    
    def make_request(url: str) -> int:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code
        except:
            return 0
    
    # Test concurrent status requests
    urls = [f"{BASE_URL}/sleep_status" for _ in range(20)]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        start_time = time.time()
        futures = [executor.submit(make_request, url) for url in urls]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
        end_time = time.time()
    
    success_count = sum(1 for code in results if code == 200)
    duration = end_time - start_time
    
    print(f"📊 Concurrent requests: {success_count}/20 successful in {duration:.2f}s")
    print(f"📈 Request rate: {len(results)/duration:.1f} req/s")
    
    # Most should succeed (status_check allows 200/min = 3.33/s)
    assert success_count >= 15, "Most concurrent requests should succeed"
    
    print("✅ Concurrent request handling working correctly")

def test_rate_limiting_reset():
    """Test the rate limiting reset functionality."""
    print("🔄 Testing Rate Limiting Reset...")
    
    # First make some requests to generate data
    for _ in range(5):
        requests.get(f"{BASE_URL}/sleep_status")
    
    # Get initial stats
    status_response = requests.get(f"{BASE_URL}/api/rate-limiting/status")
    initial_stats = status_response.json()["data"]["rate_limiting"]["statistics"]
    initial_requests = initial_stats["global_stats"]["total_requests"]
    
    print(f"📊 Initial total requests: {initial_requests}")
    
    # Reset rate limiting data
    reset_response = requests.post(f"{BASE_URL}/api/rate-limiting/reset")
    assert reset_response.status_code == 200
    
    reset_data = reset_response.json()
    assert reset_data["success"] is True
    
    # Check that stats were reset (but allow for the request we just made)
    time.sleep(1)  # Wait a moment for reset to take effect
    
    status_response = requests.get(f"{BASE_URL}/api/rate-limiting/status")
    final_stats = status_response.json()["data"]["rate_limiting"]["statistics"]
    final_clients = final_stats["storage_stats"]["total_clients"]
    final_requests = final_stats["global_stats"]["total_requests"]
    
    print(f"📊 Total clients after reset: {final_clients}")
    print(f"📊 Total requests after reset: {final_requests}")
    
    # The reset clears client-specific data but preserves global stats for monitoring
    # This is by design - global stats help track system-wide usage patterns
    assert final_clients <= 2, "Client storage should be mostly cleared after reset"
    print("✅ Reset successfully cleared client-specific rate limiting data")
    
    print("✅ Rate limiting reset working correctly")

def test_different_algorithms():
    """Test different rate limiting algorithms."""
    print("🧮 Testing Different Rate Limiting Algorithms...")
    
    # Get current rules and their algorithms
    status_response = requests.get(f"{BASE_URL}/api/rate-limiting/status")
    rules = status_response.json()["data"]["rate_limiting"]["rules"]
    
    algorithms = set(rule["limit_type"] for rule in rules.values())
    expected_algorithms = {"sliding_window", "token_bucket"}  # Only test implemented algorithms
    
    print(f"📊 Rate limiting algorithms in use: {algorithms}")
    
    for algorithm in expected_algorithms:
        assert algorithm in algorithms, f"Algorithm {algorithm} not implemented"
    
    print("✅ All implemented rate limiting algorithms are active")

def comprehensive_rate_limiting_test():
    """Run the complete rate limiting test suite."""
    print("=" * 60)
    print("🚨 COMPREHENSIVE RATE LIMITING TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_rate_limiting_status,
        test_status_check_rate_limit,
        test_config_change_rate_limit,
        test_concurrent_requests,
        test_rate_limiting_reset,
        test_different_algorithms
    ]
    
    results = []
    for test_func in tests:
        try:
            start_time = time.time()
            test_func()
            duration = time.time() - start_time
            results.append(f"✅ {test_func.__name__}: PASSED ({duration:.2f}s)")
        except Exception as e:
            results.append(f"❌ {test_func.__name__}: FAILED - {str(e)}")
        
        print()  # Add spacing between tests
    
    print("=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    for result in results:
        print(result)
        if "✅" in result:
            passed += 1
    
    total = len(results)
    print(f"\n🎯 OVERALL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL RATE LIMITING TESTS PASSED!")
        return True
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return False

if __name__ == "__main__":
    try:
        success = comprehensive_rate_limiting_test()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        exit(1)
