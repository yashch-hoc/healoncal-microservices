#!/usr/bin/env python3
"""
Quick Test Script for Phase 1.1 - Parallel Image Processing

This script tests the analyze endpoint to verify parallel processing is working.
"""

import asyncio
import aiohttp
import time
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000/api/healoncal"

async def test_analyze_performance():
    """Test analyze endpoint performance."""
    print("🧪 Testing Phase 1.1 - Parallel Image Processing")
    print("=" * 60)
    
    # First, check if we have a session with images
    test_user_id = "test-phase1-1"
    
    async with aiohttp.ClientSession() as session:
        # Check health
        print("\n1️⃣ Checking server health...")
        try:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Server is healthy: {data.get('status', 'unknown')}")
                else:
                    print(f"   ❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            print(f"   ❌ Cannot connect to server: {e}")
            print(f"   💡 Make sure server is running: uvicorn app.main_healoncal:app --reload")
            return False
        
        # Check if session exists
        print(f"\n2️⃣ Checking for existing session for user: {test_user_id}...")
        try:
            async with session.get(f"{BASE_URL}/session/{test_user_id}/latest") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success') and data.get('images_captured', 0) >= 3:
                        print(f"   ✅ Found session with {data['images_captured']} images")
                        session_id = data['session']['id']
                    else:
                        print(f"   ⚠️  No session with 3+ images found")
                        print(f"   💡 Please capture 3 images first using the UI")
                        return False
                else:
                    print(f"   ⚠️  No session found")
                    print(f"   💡 Please capture 3 images first using the UI")
                    return False
        except Exception as e:
            print(f"   ❌ Error checking session: {e}")
            return False
        
        # Test analyze endpoint
        print(f"\n3️⃣ Testing analyze endpoint (measuring performance)...")
        print(f"   User ID: {test_user_id}")
        
        start_time = time.time()
        try:
            async with session.post(
                f"{BASE_URL}/analyze",
                json={"user_id": test_user_id},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                duration = time.time() - start_time
                
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        print(f"   ✅ Analysis completed successfully!")
                        print(f"   ⏱️  Duration: {duration:.2f} seconds")
                        print(f"   📊 Processed: {data.get('processed_images', 0)} images")
                        
                        # Performance assessment
                        if duration < 5:
                            print(f"   🚀 EXCELLENT: Analysis is fast (< 5s)")
                        elif duration < 8:
                            print(f"   ✅ GOOD: Analysis is reasonably fast (< 8s)")
                        else:
                            print(f"   ⚠️  SLOW: Analysis took > 8s (may need more optimization)")
                        
                        return True
                    else:
                        print(f"   ❌ Analysis failed: {data.get('error', 'Unknown error')}")
                        return False
                else:
                    error_text = await response.text()
                    print(f"   ❌ Analysis failed: HTTP {response.status}")
                    print(f"   Error: {error_text[:200]}")
                    return False
                    
        except asyncio.TimeoutError:
            print(f"   ❌ Analysis timed out (> 60s)")
            return False
        except Exception as e:
            print(f"   ❌ Error during analysis: {e}")
            return False

async def check_metrics():
    """Check metrics endpoint for analyze performance."""
    print(f"\n4️⃣ Checking metrics for analyze endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/metrics/endpoint/analyze") as response:
                if response.status == 200:
                    data = await response.json()
                    if 'avg_latency_ms' in data:
                        avg_latency = data['avg_latency_ms']
                        print(f"   📊 Average latency: {avg_latency:.0f}ms")
                        print(f"   📈 Total requests: {data.get('total_requests', 0)}")
                        print(f"   ✅ Success rate: {data.get('success_rate', 0):.1f}%")
                    else:
                        print(f"   ⚠️  No metrics available yet (run some analyses first)")
                else:
                    print(f"   ⚠️  Could not fetch metrics: {response.status}")
        except Exception as e:
            print(f"   ⚠️  Error fetching metrics: {e}")

async def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("Phase 1.1 Performance Test")
    print("=" * 60)
    
    success = await test_analyze_performance()
    
    if success:
        await check_metrics()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TEST PASSED: Parallel processing appears to be working!")
        print("\n💡 Next steps:")
        print("   1. Check server logs for [HEALONCAL PARALLEL] messages")
        print("   2. Compare timing with previous sequential version")
        print("   3. Run full benchmark: python scripts/benchmark_api.py")
    else:
        print("❌ TEST FAILED: Please check errors above")
        print("\n💡 Troubleshooting:")
        print("   1. Make sure server is running")
        print("   2. Capture 3 images first using the UI")
        print("   3. Check server logs for errors")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
