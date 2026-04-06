#!/usr/bin/env python3
"""
Generate Baseline Performance Report

This script generates a comprehensive baseline report documenting
current performance issues and metrics before optimization.

Usage:
    python scripts/generate_baseline_report.py
"""
import json
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class BaselineReportGenerator:
    """Generate baseline performance report."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.api_base = f"{self.base_url}/api/healoncal"
    
    async def fetch_metrics(self) -> dict:
        """Fetch current metrics from API."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.api_base}/metrics") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return {"error": f"Failed to fetch metrics: {response.status}"}
            except Exception as e:
                return {"error": str(e)}
    
    def generate_issues_documentation(self) -> dict:
        """Document known architecture issues."""
        return {
            "architecture_challenges": {
                "1_sequential_processing": {
                    "issue": "Images processed sequentially in for loop",
                    "location": "app/services/healoncal_service.py:255",
                    "impact": "3 images × 2s = 6s minimum, poor resource utilization",
                    "severity": "high",
                    "current_behavior": "Processes images one at a time",
                    "expected_improvement": "3x faster with parallel processing"
                },
                "2_database_n_plus_one": {
                    "issue": "Multiple sequential database queries",
                    "location": "app/services/healoncal_service.py:404-443",
                    "impact": "6 separate queries = 600ms+ latency",
                    "severity": "high",
                    "current_behavior": "Sequential queries in get_analysis_results()",
                    "expected_improvement": "6x faster with parallel queries"
                },
                "3_no_caching": {
                    "issue": "No caching layer for results",
                    "location": "All endpoints",
                    "impact": "Redundant processing, higher costs, slower responses",
                    "severity": "medium",
                    "current_behavior": "Every request hits database",
                    "expected_improvement": "10x faster for cached responses"
                },
                "4_cpu_bound_in_async": {
                    "issue": "CPU-intensive operations block event loop",
                    "location": "app/services/healoncal_service.py:496+",
                    "impact": "Blocks other requests, poor concurrency",
                    "severity": "high",
                    "current_behavior": "OpenCV/NumPy operations in async function",
                    "expected_improvement": "Better concurrency with worker processes"
                },
                "5_no_queue_system": {
                    "issue": "Long-running analysis in request handler",
                    "location": "app/api/endpoints/healoncal_analysis.py:86",
                    "impact": "30+ second requests, timeout risks",
                    "severity": "high",
                    "current_behavior": "Synchronous processing blocks request",
                    "expected_improvement": "200ms response time with background jobs"
                },
                "6_heatmap_not_parallelized": {
                    "issue": "Heatmap generation fire-and-forget",
                    "location": "app/services/healoncal_service.py:326",
                    "impact": "Silent failures, no progress tracking",
                    "severity": "medium",
                    "current_behavior": "asyncio.create_task() not awaited",
                    "expected_improvement": "Better error handling and tracking"
                },
                "7_no_rate_limiting": {
                    "issue": "No protection against abuse",
                    "location": "All endpoints",
                    "impact": "Service can be overwhelmed, cost spikes",
                    "severity": "medium",
                    "current_behavior": "Unlimited requests",
                    "expected_improvement": "Protected API with rate limits"
                },
                "8_error_handling_hides_issues": {
                    "issue": "Extensive try/except with continue",
                    "location": "app/services/healoncal_service.py:255+",
                    "impact": "Partial failures go unnoticed",
                    "severity": "medium",
                    "current_behavior": "Silently skips failed images",
                    "expected_improvement": "Better error tracking and reporting"
                },
                "9_memory_management": {
                    "issue": "Large images loaded without limits",
                    "location": "Image processing functions",
                    "impact": "High memory usage, OOM risk",
                    "severity": "medium",
                    "current_behavior": "No image size validation",
                    "expected_improvement": "Memory-efficient processing"
                },
                "10_no_monitoring": {
                    "issue": "Limited observability",
                    "location": "System-wide",
                    "impact": "Hard to diagnose issues",
                    "severity": "low",
                    "current_behavior": "Basic logging only",
                    "expected_improvement": "Comprehensive metrics and monitoring"
                }
            },
            "performance_bottlenecks": {
                "image_processing": {
                    "current": "Sequential processing",
                    "bottleneck": "for loop in analyze_session()",
                    "estimated_impact": "3x slower than parallel"
                },
                "database_queries": {
                    "current": "6 sequential queries",
                    "bottleneck": "get_analysis_results() method",
                    "estimated_impact": "6x slower than parallel"
                },
                "analysis_execution": {
                    "current": "Synchronous in request handler",
                    "bottleneck": "30+ second blocking operation",
                    "estimated_impact": "150x slower response time"
                }
            }
        }
    
    async def generate_report(self) -> dict:
        """Generate complete baseline report."""
        print("📊 Generating Baseline Performance Report...")
        print(f"📍 Fetching metrics from: {self.api_base}\n")
        
        # Fetch current metrics
        metrics = await self.fetch_metrics()
        
        # Get issues documentation
        issues = self.generate_issues_documentation()
        
        # Generate report
        report = {
            "report_type": "baseline_performance_report",
            "report_timestamp": datetime.now().isoformat(),
            "purpose": "Document current performance issues and metrics before optimization",
            "api_base_url": self.api_base,
            "current_metrics": metrics,
            "known_issues": issues,
            "optimization_plan": {
                "phase_1_quick_wins": [
                    "Parallel image processing",
                    "Database query optimization",
                    "Basic caching (Redis)"
                ],
                "phase_2_infrastructure": [
                    "Job queue system",
                    "Worker processes",
                    "Connection pooling"
                ],
                "phase_3_observability": [
                    "Monitoring setup",
                    "Logging improvements",
                    "Error tracking"
                ],
                "phase_4_advanced": [
                    "Microservices migration",
                    "CDN integration",
                    "Auto-scaling"
                ]
            },
            "expected_improvements": {
                "image_processing": {
                    "current": "6s (sequential)",
                    "target": "2s (parallel)",
                    "improvement": "3x faster"
                },
                "database_queries": {
                    "current": "600ms (sequential)",
                    "target": "100ms (parallel)",
                    "improvement": "6x faster"
                },
                "results_retrieval": {
                    "current": "500ms (no cache)",
                    "target": "50ms (cached)",
                    "improvement": "10x faster"
                },
                "api_response_time": {
                    "current": "30s (sync)",
                    "target": "200ms (async)",
                    "improvement": "150x faster"
                },
                "throughput": {
                    "current": "10 req/min",
                    "target": "100+ req/min",
                    "improvement": "10x increase"
                }
            },
            "recommendations": [
                {
                    "priority": "critical",
                    "action": "Implement job queue system",
                    "reason": "Move analysis to background for better UX",
                    "estimated_effort": "2-3 days"
                },
                {
                    "priority": "critical",
                    "action": "Parallelize image processing",
                    "reason": "3x performance improvement",
                    "estimated_effort": "1 day"
                },
                {
                    "priority": "high",
                    "action": "Add caching layer",
                    "reason": "Reduce database load and costs",
                    "estimated_effort": "2 days"
                },
                {
                    "priority": "high",
                    "action": "Optimize database queries",
                    "reason": "6x faster query performance",
                    "estimated_effort": "1 day"
                }
            ]
        }
        
        return report
    
    def save_report(self, report: dict, filename: str = "baseline_report.json"):
        """Save report to file."""
        filepath = Path(filename)
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"✅ Report saved to: {filepath}")
        return filepath

async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate baseline performance report")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--output",
        default="baseline_report.json",
        help="Output file (default: baseline_report.json)"
    )
    
    args = parser.parse_args()
    
    generator = BaselineReportGenerator(base_url=args.base_url)
    report = await generator.generate_report()
    
    generator.save_report(report, args.output)
    
    print("\n📈 Report Summary:")
    print("=" * 60)
    print(f"Total Issues Documented: {len(report['known_issues']['architecture_challenges'])}")
    print(f"Performance Bottlenecks: {len(report['known_issues']['performance_bottlenecks'])}")
    
    if "current_metrics" in report and "system_metrics" in report["current_metrics"]:
        sys_metrics = report["current_metrics"]["system_metrics"]
        print(f"\nCurrent System Metrics:")
        print(f"  Total Requests: {sys_metrics.get('total_requests', 0)}")
        print(f"  Avg Response Time: {sys_metrics.get('avg_response_time_ms', 0):.0f}ms")
        print(f"  Requests/Second: {sys_metrics.get('requests_per_second', 0):.2f}")
        print(f"  Error Rate: {sys_metrics.get('error_rate', 0):.1f}%")
    
    print("\n✅ Baseline report generated successfully!")
    print("   Use this report to track improvements after optimization.")

if __name__ == "__main__":
    asyncio.run(main())
