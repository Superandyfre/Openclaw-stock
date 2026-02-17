"""
System monitor for health checks
"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger


class SystemMonitor:
    """Monitors system health and performance"""
    
    def __init__(self):
        """Initialize system monitor"""
        self.health_checks: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics: List[Dict[str, Any]] = []
    
    async def check_api_health(self, api_name: str, check_func) -> Dict[str, Any]:
        """
        Check health of an API
        
        Args:
            api_name: Name of the API
            check_func: Async function to check API
        
        Returns:
            Health check result
        """
        start_time = datetime.now()
        
        try:
            await asyncio.wait_for(check_func(), timeout=5.0)
            status = "healthy"
            error = None
        except asyncio.TimeoutError:
            status = "timeout"
            error = "API check timed out"
        except Exception as e:
            status = "unhealthy"
            error = str(e)
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        
        result = {
            "api": api_name,
            "status": status,
            "response_time_ms": elapsed,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        self.health_checks[api_name] = result
        return result
    
    def check_data_latency(
        self,
        data_source: str,
        last_update: datetime,
        max_latency_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Check data latency
        
        Args:
            data_source: Name of data source
            last_update: Timestamp of last update
            max_latency_seconds: Maximum acceptable latency
        
        Returns:
            Latency check result
        """
        now = datetime.now()
        
        if isinstance(last_update, str):
            last_update = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        
        latency = (now - last_update).total_seconds()
        
        if latency > max_latency_seconds:
            status = "stale"
        else:
            status = "fresh"
        
        result = {
            "data_source": data_source,
            "status": status,
            "latency_seconds": latency,
            "max_latency": max_latency_seconds,
            "last_update": last_update.isoformat(),
            "timestamp": now.isoformat()
        }
        
        logger.debug(f"Data latency for {data_source}: {latency:.2f}s ({status})")
        return result
    
    def record_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = ""
    ):
        """
        Record a performance metric
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Unit of measurement
        """
        metric = {
            "metric": metric_name,
            "value": value,
            "unit": unit,
            "timestamp": datetime.now().isoformat()
        }
        
        self.performance_metrics.append(metric)
        
        # Keep only last 1000 metrics
        if len(self.performance_metrics) > 1000:
            self.performance_metrics = self.performance_metrics[-1000:]
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get overall system health summary
        
        Returns:
            Health summary
        """
        if not self.health_checks:
            return {
                "overall_status": "unknown",
                "healthy_apis": 0,
                "unhealthy_apis": 0,
                "total_apis": 0
            }
        
        healthy = sum(1 for check in self.health_checks.values() if check['status'] == 'healthy')
        total = len(self.health_checks)
        
        if healthy == total:
            overall = "healthy"
        elif healthy > 0:
            overall = "degraded"
        else:
            overall = "critical"
        
        return {
            "overall_status": overall,
            "healthy_apis": healthy,
            "unhealthy_apis": total - healthy,
            "total_apis": total,
            "checks": list(self.health_checks.values())
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance metrics summary
        
        Returns:
            Performance summary
        """
        if not self.performance_metrics:
            return {}
        
        # Group by metric name
        metrics_by_name = {}
        for metric in self.performance_metrics[-100:]:  # Last 100 metrics
            name = metric['metric']
            if name not in metrics_by_name:
                metrics_by_name[name] = []
            metrics_by_name[name].append(metric['value'])
        
        # Calculate statistics
        summary = {}
        for name, values in metrics_by_name.items():
            summary[name] = {
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values)
            }
        
        return summary
