#!/usr/bin/env python3
"""
Healoncal API Benchmarking Script

This script performs comprehensive benchmarking of the Healoncal API
to establish baseline metrics before optimization.

Usage:
    python scripts/benchmark_api.py --base-url http://localhost:8000
    python scripts/benchmark_api.py --output baseline_benchmark.json --append   # append run to file
"""
import asyncio
import aiohttp
import time
import json
import argparse
import statistics
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class APIBenchmark:
    """API Benchmarking tool."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/healoncal"
        self.results: List[Dict[str, Any]] = []
        
    async def health_check(self) -> Dict[str, Any]:
        """Test health endpoint."""
        async with aiohttp.ClientSession() as session:
            start = time.time()
            try:
                async with session.get(f"{self.api_base}/health") as response:
                    duration = (time.time() - start) * 1000
                    data = await response.json()
                    return {
                        "endpoint": "/health",
                        "method": "GET",
                        "status_code": response.status,
                        "duration_ms": duration,
                        "success": response.status == 200,
                        "data": data
                    }
            except Exception as e:
                return {
                    "endpoint": "/health",
                    "method": "GET",
                    "status_code": 0,
                    "duration_ms": (time.time() - start) * 1000,
                    "success": False,
                    "error": str(e)
                }
    
    def create_test_image(self, size: tuple = (512, 512)) -> bytes:
        """Create a test image and return raw bytes (JPEG)."""
        from PIL import Image
        import io
        img = Image.new('RGB', size, color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return buffer.getvalue()

    def _capture_form_data(self, user_id: str, angle: str, image_bytes: bytes) -> aiohttp.FormData:
        """Build multipart form for POST /capture."""
        form = aiohttp.FormData()
        form.add_field('user_id', user_id)
        form.add_field('angle', angle)
        form.add_field('file', image_bytes, filename='capture.jpg', content_type='image/jpeg')
        return form

    async def benchmark_capture(self, user_id: str, angle: str, iterations: int = 5) -> List[Dict[str, Any]]:
        """Benchmark image capture endpoint (multipart/form-data)."""
        results = []
        image_bytes = self.create_test_image()

        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start = time.time()
                form = self._capture_form_data(user_id, angle, image_bytes)
                try:
                    async with session.post(
                        f"{self.api_base}/capture",
                        data=form,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        duration = (time.time() - start) * 1000
                        data = await response.json()
                        results.append({
                            "iteration": i + 1,
                            "endpoint": "/capture",
                            "method": "POST",
                            "status_code": response.status,
                            "duration_ms": duration,
                            "success": response.status == 200,
                            "data": data
                        })
                except Exception as e:
                    results.append({
                        "iteration": i + 1,
                        "endpoint": "/capture",
                        "method": "POST",
                        "status_code": 0,
                        "duration_ms": (time.time() - start) * 1000,
                        "success": False,
                        "error": str(e)
                    })
                await asyncio.sleep(0.5)
        return results
    
    async def benchmark_analyze(self, user_id: str, iterations: int = 3) -> List[Dict[str, Any]]:
        """Benchmark analysis endpoint."""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start = time.time()
                try:
                    payload = {"user_id": user_id}
                    
                    async with session.post(
                        f"{self.api_base}/analyze",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        duration = (time.time() - start) * 1000
                        data = await response.json()
                        
                        results.append({
                            "iteration": i + 1,
                            "endpoint": "/analyze",
                            "method": "POST",
                            "status_code": response.status,
                            "duration_ms": duration,
                            "success": response.status == 200,
                            "data": data
                        })
                except Exception as e:
                    results.append({
                        "iteration": i + 1,
                        "endpoint": "/analyze",
                        "method": "POST",
                        "status_code": 0,
                        "duration_ms": (time.time() - start) * 1000,
                        "success": False,
                        "error": str(e)
                    })
                
                await asyncio.sleep(1)
        
        return results
    
    async def benchmark_results(self, session_id: str, iterations: int = 10) -> List[Dict[str, Any]]:
        """Benchmark results retrieval endpoint."""
        results = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(iterations):
                start = time.time()
                try:
                    async with session.get(
                        f"{self.api_base}/results/{session_id}",
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        duration = (time.time() - start) * 1000
                        data = await response.json() if response.status == 200 else None
                        
                        results.append({
                            "iteration": i + 1,
                            "endpoint": "/results/{session_id}",
                            "method": "GET",
                            "status_code": response.status,
                            "duration_ms": duration,
                            "success": response.status == 200,
                            "data_size": len(json.dumps(data)) if data else 0
                        })
                except Exception as e:
                    results.append({
                        "iteration": i + 1,
                        "endpoint": "/results/{session_id}",
                        "method": "GET",
                        "status_code": 0,
                        "duration_ms": (time.time() - start) * 1000,
                        "success": False,
                        "error": str(e)
                    })
                
                await asyncio.sleep(0.2)
        
        return results
    
    async def concurrent_load_test(self, endpoint: str, payload: Dict, concurrency: int = 10) -> List[Dict[str, Any]]:
        """Test endpoint under concurrent load (JSON body)."""
        async def single_request(session, index):
            start = time.time()
            try:
                async with session.post(
                    f"{self.api_base}{endpoint}",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    duration = (time.time() - start) * 1000
                    return {
                        "request_id": index,
                        "status_code": response.status,
                        "duration_ms": duration,
                        "success": response.status == 200
                    }
            except Exception as e:
                return {
                    "request_id": index,
                    "status_code": 0,
                    "duration_ms": (time.time() - start) * 1000,
                    "success": False,
                    "error": str(e)
                }
        
        async with aiohttp.ClientSession() as session:
            tasks = [single_request(session, i) for i in range(concurrency)]
            results = await asyncio.gather(*tasks)
        return list(results)

    async def concurrent_capture_load_test(self, user_id: str, angle: str = "front", concurrency: int = 10) -> List[Dict[str, Any]]:
        """Test /capture under concurrent load (multipart/form-data per request)."""
        image_bytes = self.create_test_image()

        async def single_capture(session, index):
            start = time.time()
            try:
                form = self._capture_form_data(user_id, angle, image_bytes)
                async with session.post(
                    f"{self.api_base}/capture",
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    duration = (time.time() - start) * 1000
                    return {
                        "request_id": index,
                        "status_code": response.status,
                        "duration_ms": duration,
                        "success": response.status == 200
                    }
            except Exception as e:
                return {
                    "request_id": index,
                    "status_code": 0,
                    "duration_ms": (time.time() - start) * 1000,
                    "success": False,
                    "error": str(e)
                }

        async with aiohttp.ClientSession() as session:
            tasks = [single_capture(session, i) for i in range(concurrency)]
            results = await asyncio.gather(*tasks)
        return list(results)
    
    def calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics from results."""
        if not results:
            return {}
        
        durations = [r["duration_ms"] for r in results if "duration_ms" in r]
        successes = [r for r in results if r.get("success", False)]
        
        if not durations:
            return {}
        
        return {
            "total_requests": len(results),
            "successful_requests": len(successes),
            "failed_requests": len(results) - len(successes),
            "success_rate": (len(successes) / len(results) * 100) if results else 0,
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "median_duration_ms": statistics.median(durations),
            "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 20 else None,
            "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)] if len(durations) >= 20 else None,
            "std_deviation_ms": statistics.stdev(durations) if len(durations) > 1 else 0
        }
    
    def generate_report(self, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive benchmark report."""
        report = {
            "benchmark_timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "summary": {},
            "detailed_results": all_results,
            "recommendations": []
        }
        
        # Calculate summary
        for endpoint, results in all_results.items():
            if isinstance(results, list) and results:
                stats = self.calculate_statistics(results)
                report["summary"][endpoint] = stats
                
                # Add recommendations
                if stats.get("avg_duration_ms", 0) > 5000:
                    report["recommendations"].append({
                        "endpoint": endpoint,
                        "issue": f"Slow response time: {stats['avg_duration_ms']:.0f}ms average",
                        "priority": "high" if stats['avg_duration_ms'] > 10000 else "medium",
                        "suggestion": "Consider optimization or background processing"
                    })
                
                if stats.get("success_rate", 100) < 95:
                    report["recommendations"].append({
                        "endpoint": endpoint,
                        "issue": f"Low success rate: {stats['success_rate']:.1f}%",
                        "priority": "high",
                        "suggestion": "Investigate error causes"
                    })
        
        return report
    
    async def run_full_benchmark(self) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        print("🚀 Starting Healoncal API Benchmark...")
        print(f"📍 Base URL: {self.base_url}\n")
        
        all_results = {}
        
        # 1. Health Check
        print("1️⃣ Testing Health Endpoint...")
        health_result = await self.health_check()
        all_results["health"] = [health_result]
        print(f"   ✅ Health check: {health_result['duration_ms']:.0f}ms\n")
        
        # 2. Capture Benchmark
        print("2️⃣ Benchmarking Capture Endpoint (5 iterations)...")
        user_id = f"benchmark_user_{int(time.time())}"
        capture_results = []
        for angle in ["front", "left", "right"]:
            print(f"   📸 Capturing {angle} images...")
            results = await self.benchmark_capture(user_id, angle, iterations=2)
            capture_results.extend(results)
        all_results["capture"] = capture_results
        stats = self.calculate_statistics(capture_results)
        print(f"   ✅ Capture: Avg {stats.get('avg_duration_ms', 0):.0f}ms, Success: {stats.get('success_rate', 0):.1f}%\n")
        
        # 3. Analyze Benchmark
        print("3️⃣ Benchmarking Analyze Endpoint (3 iterations)...")
        analyze_results = await self.benchmark_analyze(user_id, iterations=2)
        all_results["analyze"] = analyze_results
        stats = self.calculate_statistics(analyze_results)
        print(f"   ✅ Analyze: Avg {stats.get('avg_duration_ms', 0):.0f}ms, Success: {stats.get('success_rate', 0):.1f}%\n")
        
        # 4. Get session_id for results test
        session_id = None
        if analyze_results and analyze_results[0].get("success"):
            session_id = analyze_results[0].get("data", {}).get("session_id")
        
        if session_id:
            # 5. Results Benchmark
            print("4️⃣ Benchmarking Results Endpoint (10 iterations)...")
            results_bench = await self.benchmark_results(session_id, iterations=10)
            all_results["results"] = results_bench
            stats = self.calculate_statistics(results_bench)
            print(f"   ✅ Results: Avg {stats.get('avg_duration_ms', 0):.0f}ms, Success: {stats.get('success_rate', 0):.1f}%\n")
        
        # 6. Concurrent Load Test (multipart capture)
        print("5️⃣ Testing Concurrent Load (10 concurrent capture requests)...")
        load_user_id = f"load_test_{int(time.time())}"
        load_results = await self.concurrent_capture_load_test(load_user_id, angle="front", concurrency=10)
        all_results["concurrent_load"] = load_results
        stats = self.calculate_statistics(load_results)
        print(f"   ✅ Concurrent Load: Avg {stats.get('avg_duration_ms', 0):.0f}ms, Success: {stats.get('success_rate', 0):.1f}%\n")
        
        # Generate report
        report = self.generate_report(all_results)
        
        print("📊 Benchmark Complete!\n")
        return report

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Benchmark Healoncal API")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output file for results (default: benchmark_results.json)"
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append this run to the output file (creates/updates a 'runs' array)"
    )
    
    args = parser.parse_args()
    
    benchmark = APIBenchmark(base_url=args.base_url)
    report = await benchmark.run_full_benchmark()
    
    # Save report
    output_path = Path(args.output)
    if args.append:
        existing = {"runs": []}
        if output_path.exists():
            try:
                with open(output_path) as f:
                    existing = json.load(f)
                if not isinstance(existing.get("runs"), list):
                    existing["runs"] = []
            except Exception:
                existing = {"runs": []}
        existing.setdefault("runs", []).append(report)
        with open(output_path, "w") as f:
            json.dump(existing, f, indent=2, default=str)
        print(f"📄 Appended run to {output_path} ({len(existing['runs'])} runs total)")
    else:
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"📄 Report saved to: {output_path}")
    print("\n📈 Summary:")
    print("=" * 60)
    for endpoint, stats in report["summary"].items():
        print(f"\n{endpoint}:")
        print(f"  Avg Duration: {stats.get('avg_duration_ms', 0):.0f}ms")
        print(f"  Success Rate: {stats.get('success_rate', 0):.1f}%")
        print(f"  P95 Duration: {stats.get('p95_duration_ms', 0):.0f}ms" if stats.get('p95_duration_ms') else "  P95 Duration: N/A")
    
    if report["recommendations"]:
        print("\n⚠️  Recommendations:")
        for rec in report["recommendations"]:
            print(f"  [{rec['priority'].upper()}] {rec['endpoint']}: {rec['issue']}")

if __name__ == "__main__":
    asyncio.run(main())
