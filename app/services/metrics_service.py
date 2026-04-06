"""
Performance Metrics Collection Service

This service collects and tracks performance metrics for the Healoncal API.
Use this to measure current performance before optimization.
"""
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import json
import statistics

logger = logging.getLogger(__name__)

@dataclass
class RequestMetric:
    """Single request metric."""
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

@dataclass
class EndpointMetrics:
    """Aggregated metrics for an endpoint."""
    endpoint: str
    method: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float  # Median
    p95_duration_ms: float  # 95th percentile
    p99_duration_ms: float  # 99th percentile
    error_rate: float
    requests_per_second: float
    last_request_time: Optional[datetime] = None

@dataclass
class SystemMetrics:
    """System-wide metrics."""
    total_requests: int
    total_errors: int
    avg_response_time_ms: float
    requests_per_second: float
    error_rate: float
    active_sessions: int
    processing_queue_size: int
    database_query_count: int
    database_avg_query_time_ms: float
    cache_hit_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float

class MetricsService:
    """
    Service for collecting and analyzing performance metrics.
    """
    
    def __init__(self, max_metrics: int = 10000):
        """Initialize metrics service."""
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.endpoint_metrics: Dict[str, EndpointMetrics] = {}
        self.database_queries: List[Dict[str, Any]] = []
        self.start_time = datetime.now()
        self._lock = asyncio.Lock()
        
        logger.info("[METRICS] Metrics service initialized")
    
    async def record_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Record a request metric."""
        async with self._lock:
            metric = RequestMetric(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                timestamp=datetime.now(),
                user_id=user_id,
                session_id=session_id,
                error=error
            )
            self.metrics.append(metric)
            
            # Update endpoint metrics
            self._update_endpoint_metrics(metric)
    
    def _update_endpoint_metrics(self, metric: RequestMetric):
        """Update aggregated endpoint metrics."""
        key = f"{metric.method}:{metric.endpoint}"
        
        if key not in self.endpoint_metrics:
            self.endpoint_metrics[key] = EndpointMetrics(
                endpoint=metric.endpoint,
                method=metric.method,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_duration_ms=0.0,
                min_duration_ms=float('inf'),
                max_duration_ms=0.0,
                p50_duration_ms=0.0,
                p95_duration_ms=0.0,
                p99_duration_ms=0.0,
                error_rate=0.0,
                requests_per_second=0.0
            )
        
        ep_metrics = self.endpoint_metrics[key]
        ep_metrics.total_requests += 1
        
        if metric.status_code < 400:
            ep_metrics.successful_requests += 1
        else:
            ep_metrics.failed_requests += 1
        
        # Update duration statistics
        durations = [m.duration_ms for m in self.metrics if m.endpoint == metric.endpoint and m.method == metric.method]
        
        if durations:
            ep_metrics.avg_duration_ms = statistics.mean(durations)
            ep_metrics.min_duration_ms = min(durations)
            ep_metrics.max_duration_ms = max(durations)
            
            if len(durations) >= 2:
                ep_metrics.p50_duration_ms = statistics.median(durations)
                if len(durations) >= 20:
                    sorted_durations = sorted(durations)
                    ep_metrics.p95_duration_ms = sorted_durations[int(len(sorted_durations) * 0.95)]
                    ep_metrics.p99_duration_ms = sorted_durations[int(len(sorted_durations) * 0.99)]
        
        ep_metrics.error_rate = (ep_metrics.failed_requests / ep_metrics.total_requests) * 100
        ep_metrics.last_request_time = metric.timestamp
        
        # Calculate requests per second (last 60 seconds)
        recent_metrics = [
            m for m in self.metrics
            if m.endpoint == metric.endpoint
            and m.method == metric.method
            and (datetime.now() - m.timestamp).total_seconds() <= 60
        ]
        if recent_metrics:
            time_span = (recent_metrics[-1].timestamp - recent_metrics[0].timestamp).total_seconds()
            if time_span > 0:
                ep_metrics.requests_per_second = len(recent_metrics) / time_span
    
    async def record_database_query(
        self,
        query_type: str,
        table: str,
        duration_ms: float,
        success: bool = True
    ):
        """Record a database query metric."""
        async with self._lock:
            self.database_queries.append({
                "query_type": query_type,
                "table": table,
                "duration_ms": duration_ms,
                "success": success,
                "timestamp": datetime.now()
            })
            
            # Keep only last 1000 queries
            if len(self.database_queries) > 1000:
                self.database_queries = self.database_queries[-1000:]
    
    def get_endpoint_metrics(self, endpoint: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for specific endpoint or all endpoints."""
        if endpoint:
            key = f"POST:{endpoint}"  # Adjust based on method
            if key in self.endpoint_metrics:
                return asdict(self.endpoint_metrics[key])
            return {}
        
        return {
            key: asdict(metrics)
            for key, metrics in self.endpoint_metrics.items()
        }
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get system-wide metrics."""
        if not self.metrics:
            return SystemMetrics(
                total_requests=0,
                total_errors=0,
                avg_response_time_ms=0.0,
                requests_per_second=0.0,
                error_rate=0.0,
                active_sessions=0,
                processing_queue_size=0,
                database_query_count=len(self.database_queries),
                database_avg_query_time_ms=0.0,
                cache_hit_rate=0.0,
                memory_usage_mb=0.0,
                cpu_usage_percent=0.0
            )
        
        total_requests = len(self.metrics)
        total_errors = sum(1 for m in self.metrics if m.status_code >= 400)
        avg_response_time = statistics.mean([m.duration_ms for m in self.metrics])
        
        # Calculate requests per second
        if len(self.metrics) >= 2:
            time_span = (self.metrics[-1].timestamp - self.metrics[0].timestamp).total_seconds()
            if time_span > 0:
                rps = len(self.metrics) / time_span
            else:
                rps = 0.0
        else:
            rps = 0.0
        
        # Database metrics
        if self.database_queries:
            db_avg_time = statistics.mean([q["duration_ms"] for q in self.database_queries])
        else:
            db_avg_time = 0.0
        
        # Get active sessions (unique session_ids in last hour)
        recent_metrics = [
            m for m in self.metrics
            if (datetime.now() - m.timestamp).total_seconds() <= 3600
        ]
        active_sessions = len(set(m.session_id for m in recent_metrics if m.session_id))
        
        # Memory usage (approximate)
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent(interval=0.1)
        
        return SystemMetrics(
            total_requests=total_requests,
            total_errors=total_errors,
            avg_response_time_ms=avg_response_time,
            requests_per_second=rps,
            error_rate=(total_errors / total_requests * 100) if total_requests > 0 else 0.0,
            active_sessions=active_sessions,
            processing_queue_size=0,  # TODO: Implement queue tracking
            database_query_count=len(self.database_queries),
            database_avg_query_time_ms=db_avg_time,
            cache_hit_rate=0.0,  # TODO: Implement cache tracking
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent
        )
    
    def get_database_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        if not self.database_queries:
            return {
                "total_queries": 0,
                "avg_query_time_ms": 0.0,
                "queries_by_table": {},
                "queries_by_type": {},
                "failed_queries": 0
            }
        
        queries_by_table = defaultdict(int)
        queries_by_type = defaultdict(int)
        failed_queries = sum(1 for q in self.database_queries if not q["success"])
        
        for query in self.database_queries:
            queries_by_table[query["table"]] += 1
            queries_by_type[query["query_type"]] += 1
        
        return {
            "total_queries": len(self.database_queries),
            "avg_query_time_ms": statistics.mean([q["duration_ms"] for q in self.database_queries]),
            "min_query_time_ms": min([q["duration_ms"] for q in self.database_queries]),
            "max_query_time_ms": max([q["duration_ms"] for q in self.database_queries]),
            "queries_by_table": dict(queries_by_table),
            "queries_by_type": dict(queries_by_type),
            "failed_queries": failed_queries,
            "success_rate": ((len(self.database_queries) - failed_queries) / len(self.database_queries) * 100) if self.database_queries else 0.0
        }
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive metrics report."""
        system_metrics = self.get_system_metrics()
        db_metrics = self.get_database_metrics()
        
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "report_timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": str(timedelta(seconds=int(uptime_seconds))),
            "system_metrics": asdict(system_metrics),
            "endpoint_metrics": {
                key: asdict(metrics)
                for key, metrics in self.endpoint_metrics.items()
            },
            "database_metrics": db_metrics,
            "top_slow_endpoints": self._get_slow_endpoints(limit=10),
            "top_error_endpoints": self._get_error_endpoints(limit=10),
            "performance_issues": self._identify_issues()
        }
    
    def _get_slow_endpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest endpoints."""
        endpoints = sorted(
            self.endpoint_metrics.values(),
            key=lambda x: x.avg_duration_ms,
            reverse=True
        )[:limit]
        
        return [
            {
                "endpoint": ep.endpoint,
                "method": ep.method,
                "avg_duration_ms": ep.avg_duration_ms,
                "p95_duration_ms": ep.p95_duration_ms,
                "total_requests": ep.total_requests
            }
            for ep in endpoints
        ]
    
    def _get_error_endpoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get endpoints with most errors."""
        endpoints = sorted(
            self.endpoint_metrics.values(),
            key=lambda x: x.error_rate,
            reverse=True
        )[:limit]
        
        return [
            {
                "endpoint": ep.endpoint,
                "method": ep.method,
                "error_rate": ep.error_rate,
                "failed_requests": ep.failed_requests,
                "total_requests": ep.total_requests
            }
            for ep in endpoints if ep.failed_requests > 0
        ]
    
    def _identify_issues(self) -> List[Dict[str, Any]]:
        """Identify performance issues based on metrics."""
        issues = []
        
        for ep_metrics in self.endpoint_metrics.values():
            # Slow endpoints
            if ep_metrics.avg_duration_ms > 5000:  # > 5 seconds
                issues.append({
                    "type": "slow_endpoint",
                    "severity": "high" if ep_metrics.avg_duration_ms > 10000 else "medium",
                    "endpoint": ep_metrics.endpoint,
                    "issue": f"Average response time is {ep_metrics.avg_duration_ms:.0f}ms (threshold: 5000ms)",
                    "recommendation": "Consider optimizing or moving to background job queue"
                })
            
            # High error rate
            if ep_metrics.error_rate > 5:  # > 5%
                issues.append({
                    "type": "high_error_rate",
                    "severity": "high" if ep_metrics.error_rate > 20 else "medium",
                    "endpoint": ep_metrics.endpoint,
                    "issue": f"Error rate is {ep_metrics.error_rate:.1f}% (threshold: 5%)",
                    "recommendation": "Investigate error causes and add retry logic"
                })
            
            # High p95 latency
            if ep_metrics.p95_duration_ms > 10000:  # > 10 seconds
                issues.append({
                    "type": "high_p95_latency",
                    "severity": "high",
                    "endpoint": ep_metrics.endpoint,
                    "issue": f"95th percentile latency is {ep_metrics.p95_duration_ms:.0f}ms",
                    "recommendation": "Optimize slow path or add caching"
                })
        
        # Database issues
        db_metrics = self.get_database_metrics()
        if db_metrics["avg_query_time_ms"] > 500:  # > 500ms
            issues.append({
                "type": "slow_database",
                "severity": "high",
                "issue": f"Average database query time is {db_metrics['avg_query_time_ms']:.0f}ms",
                "recommendation": "Add indexes, optimize queries, or add connection pooling"
            })
        
        return issues
    
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file."""
        report = self.generate_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"[METRICS] Metrics exported to {filepath}")
    
    def clear_metrics(self):
        """Clear all collected metrics."""
        self.metrics.clear()
        self.endpoint_metrics.clear()
        self.database_queries.clear()
        self.start_time = datetime.now()
        logger.info("[METRICS] All metrics cleared")

# Global instance
metrics_service = MetricsService()
