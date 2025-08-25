"""
Analytics Caching and Optimization
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Union
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from functools import wraps

logger = logging.getLogger(__name__)


class AnalyticsCache:
    """Advanced caching system for analytics data"""
    
    # Cache timeout configurations (in seconds)
    CACHE_TIMEOUTS = {
        'dashboard': 300,      # 5 minutes
        'metrics': 600,        # 10 minutes
        'reports': 1800,       # 30 minutes
        'system_health': 60,   # 1 minute
        'competitive': 900,    # 15 minutes
        'user_activity': 300,  # 5 minutes
    }
    
    # Cache key prefixes
    KEY_PREFIXES = {
        'dashboard': 'analytics:dashboard',
        'metrics': 'analytics:metrics',
        'reports': 'analytics:reports',
        'system_health': 'analytics:health',
        'competitive': 'analytics:competitive',
        'user_activity': 'analytics:user',
    }
    
    @classmethod
    def generate_cache_key(cls, cache_type: str, *args, **kwargs) -> str:
        """Generate a unique cache key"""
        prefix = cls.KEY_PREFIXES.get(cache_type, 'analytics:general')
        
        # Create a hash of the arguments
        key_data = {
            'args': args,
            'kwargs': kwargs,
            'timestamp': timezone.now().strftime('%Y-%m-%d-%H')  # Hour-based invalidation
        }
        
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"{prefix}:{key_hash}"   
 
    @classmethod
    def get(cls, cache_type: str, *args, **kwargs) -> Optional[Any]:
        """Get data from cache"""
        cache_key = cls.generate_cache_key(cache_type, *args, **kwargs)
        try:
            return cache.get(cache_key)
        except Exception as e:
            logger.error(f"Cache get error for key {cache_key}: {str(e)}")
            return None
    
    @classmethod
    def set(cls, cache_type: str, data: Any, *args, timeout: Optional[int] = None, **kwargs) -> bool:
        """Set data in cache"""
        cache_key = cls.generate_cache_key(cache_type, *args, **kwargs)
        cache_timeout = timeout or cls.CACHE_TIMEOUTS.get(cache_type, 300)
        
        try:
            cache.set(cache_key, data, cache_timeout)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {cache_key}: {str(e)}")
            return False
    
    @classmethod
    def delete(cls, cache_type: str, *args, **kwargs) -> bool:
        """Delete data from cache"""
        cache_key = cls.generate_cache_key(cache_type, *args, **kwargs)
        try:
            cache.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {cache_key}: {str(e)}")
            return False


class AnalyticsOptimizer:
    """Performance optimization utilities for analytics"""
    
    @staticmethod
    def batch_process_metrics(metrics_data: list, batch_size: int = 100) -> list:
        """Process metrics in batches to avoid memory issues"""
        results = []
        
        for i in range(0, len(metrics_data), batch_size):
            batch = metrics_data[i:i + batch_size]
            # Process batch
            batch_results = []
            for metric in batch:
                # Process individual metric
                batch_results.append(metric)
            
            results.extend(batch_results)
        
        return results
    
    @staticmethod
    def calculate_percentiles(values: list, percentiles: list = [50, 75, 90, 95, 99]) -> Dict[int, float]:
        """Calculate percentiles for a list of values"""
        if not values:
            return {p: 0 for p in percentiles}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        result = {}
        for p in percentiles:
            index = int((p / 100) * (n - 1))
            result[p] = sorted_values[index]
        
        return result


class RealTimeAnalyticsCache:
    """Real-time analytics caching with automatic invalidation"""
    
    def __init__(self):
        self.cache_prefix = "realtime:analytics"
        self.default_timeout = 60  # 1 minute for real-time data
    
    def set_real_time_metric(self, metric_type: str, value: Any, 
                           user_id: Optional[int] = None) -> bool:
        """Set a real-time metric value"""
        cache_key = f"{self.cache_prefix}:{metric_type}"
        if user_id:
            cache_key += f":user_{user_id}"
        
        try:
            cache.set(cache_key, {
                'value': value,
                'timestamp': timezone.now().isoformat(),
                'user_id': user_id
            }, self.default_timeout)
            return True
        except Exception as e:
            logger.error(f"Real-time cache set error: {str(e)}")
            return False
    
    def get_real_time_metric(self, metric_type: str, 
                           user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get a real-time metric value"""
        cache_key = f"{self.cache_prefix}:{metric_type}"
        if user_id:
            cache_key += f":user_{user_id}"
        
        try:
            return cache.get(cache_key)
        except Exception as e:
            logger.error(f"Real-time cache get error: {str(e)}")
            return None


# Global instances
analytics_cache = AnalyticsCache()
analytics_optimizer = AnalyticsOptimizer()
realtime_cache = RealTimeAnalyticsCache()