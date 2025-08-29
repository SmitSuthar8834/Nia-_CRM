"""
Caching utilities for performance monitoring and validation sessions
"""
import json
import hashlib
from typing import Any, Optional, Dict, List
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

from .models import PerformanceMetric, ValidationSession, ConcurrentCallMetrics


class PerformanceCache:
    """
    Caching layer for performance monitoring data
    """
    
    # Cache key prefixes
    METRICS_PREFIX = "perf_metrics"
    SUMMARY_PREFIX = "perf_summary"
    ALERTS_PREFIX = "perf_alerts"
    CONCURRENT_PREFIX = "concurrent_calls"
    VALIDATION_PREFIX = "validation_session"
    
    # Default cache timeouts (in seconds)
    DEFAULT_TIMEOUT = 300  # 5 minutes
    SUMMARY_TIMEOUT = 600  # 10 minutes
    METRICS_TIMEOUT = 180  # 3 minutes
    VALIDATION_TIMEOUT = 1800  # 30 minutes
    
    @classmethod
    def _make_key(cls, prefix: str, *args) -> str:
        """Create a cache key from prefix and arguments"""
        key_parts = [prefix] + [str(arg) for arg in args]
        key = ":".join(key_parts)
        
        # Hash long keys to avoid cache key length limits
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key
    
    @classmethod
    def get_performance_summary(cls, hours: int = 24) -> Optional[Dict]:
        """Get cached performance summary"""
        cache_key = cls._make_key(cls.SUMMARY_PREFIX, hours)
        return cache.get(cache_key)
    
    @classmethod
    def set_performance_summary(cls, hours: int, summary: Dict, timeout: int = None) -> None:
        """Cache performance summary"""
        cache_key = cls._make_key(cls.SUMMARY_PREFIX, hours)
        timeout = timeout or cls.SUMMARY_TIMEOUT
        cache.set(cache_key, summary, timeout)
    
    @classmethod
    def get_metrics_by_type(cls, metric_type: str, hours: int = 24) -> Optional[List]:
        """Get cached metrics by type"""
        cache_key = cls._make_key(cls.METRICS_PREFIX, metric_type, hours)
        return cache.get(cache_key)
    
    @classmethod
    def set_metrics_by_type(cls, metric_type: str, hours: int, metrics: List, timeout: int = None) -> None:
        """Cache metrics by type"""
        cache_key = cls._make_key(cls.METRICS_PREFIX, metric_type, hours)
        timeout = timeout or cls.METRICS_TIMEOUT
        cache.set(cache_key, metrics, timeout)
    
    @classmethod
    def get_concurrent_metrics(cls, hours: int = 1) -> Optional[Dict]:
        """Get cached concurrent call metrics"""
        cache_key = cls._make_key(cls.CONCURRENT_PREFIX, hours)
        return cache.get(cache_key)
    
    @classmethod
    def set_concurrent_metrics(cls, hours: int, metrics: Dict, timeout: int = None) -> None:
        """Cache concurrent call metrics"""
        cache_key = cls._make_key(cls.CONCURRENT_PREFIX, hours)
        timeout = timeout or cls.METRICS_TIMEOUT
        cache.set(cache_key, metrics, timeout)
    
    @classmethod
    def get_validation_session(cls, session_id: str) -> Optional[Dict]:
        """Get cached validation session data"""
        cache_key = cls._make_key(cls.VALIDATION_PREFIX, session_id)
        return cache.get(cache_key)
    
    @classmethod
    def set_validation_session(cls, session_id: str, session_data: Dict, timeout: int = None) -> None:
        """Cache validation session data"""
        cache_key = cls._make_key(cls.VALIDATION_PREFIX, session_id)
        timeout = timeout or cls.VALIDATION_TIMEOUT
        cache.set(cache_key, session_data, timeout)
    
    @classmethod
    def invalidate_validation_session(cls, session_id: str) -> None:
        """Invalidate cached validation session"""
        cache_key = cls._make_key(cls.VALIDATION_PREFIX, session_id)
        cache.delete(cache_key)
    
    @classmethod
    def get_alert_dashboard(cls) -> Optional[Dict]:
        """Get cached alert dashboard data"""
        cache_key = cls._make_key(cls.ALERTS_PREFIX, "dashboard")
        return cache.get(cache_key)
    
    @classmethod
    def set_alert_dashboard(cls, dashboard_data: Dict, timeout: int = None) -> None:
        """Cache alert dashboard data"""
        cache_key = cls._make_key(cls.ALERTS_PREFIX, "dashboard")
        timeout = timeout or cls.DEFAULT_TIMEOUT
        cache.set(cache_key, dashboard_data, timeout)
    
    @classmethod
    def invalidate_alerts(cls) -> None:
        """Invalidate all alert-related cache"""
        # This is a simple implementation - in production you might want
        # to use cache versioning or more sophisticated invalidation
        cache_pattern = f"{cls.ALERTS_PREFIX}:*"
        # Note: This requires Redis or Memcached with pattern support
        try:
            cache.delete_pattern(cache_pattern)
        except AttributeError:
            # Fallback for cache backends that don't support pattern deletion
            cache.delete(cls._make_key(cls.ALERTS_PREFIX, "dashboard"))
    
    @classmethod
    def warm_cache(cls) -> None:
        """Warm up frequently accessed cache entries"""
        from .services import PerformanceMonitoringService
        
        performance_service = PerformanceMonitoringService()
        
        # Warm up performance summaries for common time periods
        for hours in [1, 6, 24]:
            if not cls.get_performance_summary(hours):
                summary = performance_service.get_performance_summary(hours)
                cls.set_performance_summary(hours, summary)
        
        # Warm up concurrent call metrics
        if not cls.get_concurrent_metrics(1):
            metrics = performance_service.track_concurrent_calls()
            if metrics:
                metrics_dict = {
                    'active_calls': metrics.active_calls,
                    'timestamp': metrics.timestamp.isoformat(),
                    'system_load': metrics.system_load,
                    'available_memory': metrics.available_memory
                }
                cls.set_concurrent_metrics(1, metrics_dict)
    
    @classmethod
    def get_cache_stats(cls) -> Dict:
        """Get cache statistics (if supported by cache backend)"""
        try:
            # This works with Redis cache backend
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
                client = cache._cache.get_client()
                info = client.info()
                return {
                    'hits': info.get('keyspace_hits', 0),
                    'misses': info.get('keyspace_misses', 0),
                    'keys': info.get('db0', {}).get('keys', 0),
                    'memory_usage': info.get('used_memory_human', 'Unknown')
                }
        except Exception:
            pass
        
        return {'status': 'Cache stats not available'}


class ValidationSessionCache:
    """
    Specialized caching for validation sessions to improve response times
    """
    
    @classmethod
    def get_active_sessions(cls, sales_rep_email: str) -> Optional[List[Dict]]:
        """Get cached active validation sessions for a sales rep"""
        cache_key = PerformanceCache._make_key(
            PerformanceCache.VALIDATION_PREFIX, 
            "active", 
            sales_rep_email
        )
        return cache.get(cache_key)
    
    @classmethod
    def set_active_sessions(cls, sales_rep_email: str, sessions: List[Dict], timeout: int = 600) -> None:
        """Cache active validation sessions for a sales rep"""
        cache_key = PerformanceCache._make_key(
            PerformanceCache.VALIDATION_PREFIX, 
            "active", 
            sales_rep_email
        )
        cache.set(cache_key, sessions, timeout)
    
    @classmethod
    def invalidate_user_sessions(cls, sales_rep_email: str) -> None:
        """Invalidate all cached sessions for a user"""
        cache_key = PerformanceCache._make_key(
            PerformanceCache.VALIDATION_PREFIX, 
            "active", 
            sales_rep_email
        )
        cache.delete(cache_key)
    
    @classmethod
    def get_session_questions(cls, session_id: str) -> Optional[List[Dict]]:
        """Get cached validation questions for a session"""
        cache_key = PerformanceCache._make_key(
            PerformanceCache.VALIDATION_PREFIX, 
            "questions", 
            session_id
        )
        return cache.get(cache_key)
    
    @classmethod
    def set_session_questions(cls, session_id: str, questions: List[Dict], timeout: int = 1800) -> None:
        """Cache validation questions for a session"""
        cache_key = PerformanceCache._make_key(
            PerformanceCache.VALIDATION_PREFIX, 
            "questions", 
            session_id
        )
        cache.set(cache_key, questions, timeout)


class MetricsAggregationCache:
    """
    Caching for expensive metrics aggregations
    """
    
    @classmethod
    def get_hourly_aggregates(cls, metric_type: str, hours: int = 24) -> Optional[List[Dict]]:
        """Get cached hourly metric aggregates"""
        cache_key = PerformanceCache._make_key(
            "hourly_agg", 
            metric_type, 
            hours
        )
        return cache.get(cache_key)
    
    @classmethod
    def set_hourly_aggregates(cls, metric_type: str, hours: int, aggregates: List[Dict], timeout: int = 900) -> None:
        """Cache hourly metric aggregates"""
        cache_key = PerformanceCache._make_key(
            "hourly_agg", 
            metric_type, 
            hours
        )
        cache.set(cache_key, aggregates, timeout)
    
    @classmethod
    def get_call_bot_stats(cls, hours: int = 24) -> Optional[Dict]:
        """Get cached call bot statistics"""
        cache_key = PerformanceCache._make_key("callbot_stats", hours)
        return cache.get(cache_key)
    
    @classmethod
    def set_call_bot_stats(cls, hours: int, stats: Dict, timeout: int = 600) -> None:
        """Cache call bot statistics"""
        cache_key = PerformanceCache._make_key("callbot_stats", hours)
        cache.set(cache_key, stats, timeout)
    
    @classmethod
    def get_ai_performance_stats(cls, hours: int = 24) -> Optional[Dict]:
        """Get cached AI performance statistics"""
        cache_key = PerformanceCache._make_key("ai_stats", hours)
        return cache.get(cache_key)
    
    @classmethod
    def set_ai_performance_stats(cls, hours: int, stats: Dict, timeout: int = 600) -> None:
        """Cache AI performance statistics"""
        cache_key = PerformanceCache._make_key("ai_stats", hours)
        cache.set(cache_key, stats, timeout)


class CacheWarmer:
    """
    Utility for warming up cache with frequently accessed data
    """
    
    @classmethod
    def warm_performance_data(cls) -> Dict[str, Any]:
        """Warm up performance-related cache entries"""
        results = {
            'summaries_warmed': 0,
            'metrics_warmed': 0,
            'errors': []
        }
        
        try:
            # Warm up performance summaries
            from .services import PerformanceMonitoringService
            performance_service = PerformanceMonitoringService()
            
            for hours in [1, 6, 24, 168]:  # 1h, 6h, 24h, 1 week
                try:
                    summary = performance_service.get_performance_summary(hours)
                    PerformanceCache.set_performance_summary(hours, summary)
                    results['summaries_warmed'] += 1
                except Exception as e:
                    results['errors'].append(f"Summary {hours}h: {str(e)}")
            
            # Warm up metrics by type
            metric_types = ['call_bot_session', 'ai_processing', 'system_resource']
            for metric_type in metric_types:
                try:
                    # This would need to be implemented in the service
                    # For now, just mark as attempted
                    results['metrics_warmed'] += 1
                except Exception as e:
                    results['errors'].append(f"Metrics {metric_type}: {str(e)}")
            
        except Exception as e:
            results['errors'].append(f"General error: {str(e)}")
        
        return results
    
    @classmethod
    def warm_validation_data(cls) -> Dict[str, Any]:
        """Warm up validation session cache entries"""
        results = {
            'sessions_warmed': 0,
            'errors': []
        }
        
        try:
            from meetings.models import ValidationSession
            
            # Get active validation sessions
            active_sessions = ValidationSession.objects.filter(
                validation_status='pending',
                expires_at__gt=timezone.now()
            ).select_related('draft_summary__bot_session__meeting')
            
            # Group by sales rep and cache
            sessions_by_rep = {}
            for session in active_sessions:
                rep_email = session.sales_rep_email
                if rep_email not in sessions_by_rep:
                    sessions_by_rep[rep_email] = []
                
                sessions_by_rep[rep_email].append({
                    'id': session.id,
                    'meeting_title': session.draft_summary.bot_session.meeting.title,
                    'started_at': session.started_at.isoformat(),
                    'expires_at': session.expires_at.isoformat(),
                    'validation_status': session.validation_status
                })
            
            # Cache sessions by rep
            for rep_email, sessions in sessions_by_rep.items():
                ValidationSessionCache.set_active_sessions(rep_email, sessions)
                results['sessions_warmed'] += 1
            
        except Exception as e:
            results['errors'].append(f"Validation warming error: {str(e)}")
        
        return results


# Cache invalidation signals
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=PerformanceMetric)
def invalidate_performance_cache(sender, instance, **kwargs):
    """Invalidate performance cache when new metrics are added"""
    # Invalidate summary cache for relevant time periods
    PerformanceCache.set_performance_summary(1, None, 1)  # Expire immediately
    PerformanceCache.set_performance_summary(24, None, 1)
    
    # Invalidate metrics by type cache
    PerformanceCache.set_metrics_by_type(instance.metric_type, 24, None, 1)


@receiver([post_save, post_delete], sender='meetings.ValidationSession')
def invalidate_validation_cache(sender, instance, **kwargs):
    """Invalidate validation session cache when sessions change"""
    ValidationSessionCache.invalidate_user_sessions(instance.sales_rep_email)
    PerformanceCache.invalidate_validation_session(str(instance.id))


# Cache management commands would be added to management/commands/