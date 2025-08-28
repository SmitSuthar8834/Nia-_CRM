"""
Settings configuration for AI optimization features
"""
from django.conf import settings

# AI Optimization Settings
AI_OPTIMIZATION_SETTINGS = {
    # Caching Configuration
    'CACHE_TTL_SECONDS': getattr(settings, 'AI_CACHE_TTL_SECONDS', 3600),  # 1 hour
    'MAX_CACHE_SIZE': getattr(settings, 'AI_MAX_CACHE_SIZE', 10000),
    'CACHE_HIT_THRESHOLD': getattr(settings, 'AI_CACHE_HIT_THRESHOLD', 0.1),
    'SIMILARITY_THRESHOLD': getattr(settings, 'AI_SIMILARITY_THRESHOLD', 0.85),
    'ENABLE_SEMANTIC_CACHING': getattr(settings, 'AI_ENABLE_SEMANTIC_CACHING', True),
    'ENABLE_CONTEXT_AWARE_CACHING': getattr(settings, 'AI_ENABLE_CONTEXT_AWARE_CACHING', True),
    
    # Context Optimization
    'MAX_CONTEXT_LENGTH': getattr(settings, 'AI_MAX_CONTEXT_LENGTH', 4000),
    'CONTEXT_COMPRESSION_RATIO': getattr(settings, 'AI_CONTEXT_COMPRESSION_RATIO', 0.7),
    
    # Batch Processing
    'BATCH_SIZE': getattr(settings, 'AI_BATCH_SIZE', 10),
    'BATCH_DELAY': getattr(settings, 'AI_BATCH_DELAY', 2),  # seconds
    'BATCH_TIMEOUT': getattr(settings, 'AI_BATCH_TIMEOUT', 300),  # 5 minutes
    
    # Cost Optimization
    'COST_PER_1K_TOKENS': getattr(settings, 'GEMINI_COST_PER_1K_TOKENS', 0.001),
    'ENABLE_COST_TRACKING': getattr(settings, 'AI_ENABLE_COST_TRACKING', True),
    
    # Fallback Configuration
    'ENABLE_FALLBACK': getattr(settings, 'AI_ENABLE_FALLBACK', True),
    'FALLBACK_TIMEOUT': getattr(settings, 'AI_FALLBACK_TIMEOUT', 5),  # seconds
    'HEALTH_CHECK_INTERVAL': getattr(settings, 'AI_HEALTH_CHECK_INTERVAL', 60),  # seconds
    
    # Monitoring and Alerts
    'ENABLE_USAGE_MONITORING': getattr(settings, 'AI_ENABLE_USAGE_MONITORING', True),
    'ALERT_ERROR_RATE_THRESHOLD': getattr(settings, 'AI_ALERT_ERROR_RATE_THRESHOLD', 0.1),
    'ALERT_RESPONSE_TIME_THRESHOLD': getattr(settings, 'AI_ALERT_RESPONSE_TIME_THRESHOLD', 5000),  # ms
    
    # Performance Optimization
    'ENABLE_RESPONSE_COMPRESSION': getattr(settings, 'AI_ENABLE_RESPONSE_COMPRESSION', True),
    'ENABLE_REQUEST_DEDUPLICATION': getattr(settings, 'AI_ENABLE_REQUEST_DEDUPLICATION', True),
    'OPTIMIZATION_REPORT_RETENTION_DAYS': getattr(settings, 'AI_OPTIMIZATION_REPORT_RETENTION_DAYS', 30),
}

# Celery Task Configuration for AI Optimization
CELERY_AI_OPTIMIZATION_TASKS = {
    # Cache maintenance - run every hour
    'cleanup-ai-cache': {
        'task': 'apps.ai_engine.tasks.cleanup_ai_cache',
        'schedule': 3600.0,  # 1 hour
    },
    
    # Usage report generation - run daily at 2 AM
    'generate-daily-usage-report': {
        'task': 'apps.ai_engine.tasks.generate_usage_report',
        'schedule': {
            'hour': 2,
            'minute': 0,
        },
        'kwargs': {'days': 1},
    },
    
    # Weekly usage report - run weekly on Monday at 8 AM
    'generate-weekly-usage-report': {
        'task': 'apps.ai_engine.tasks.generate_usage_report',
        'schedule': {
            'day_of_week': 1,  # Monday
            'hour': 8,
            'minute': 0,
        },
        'kwargs': {'days': 7},
    },
    
    # Performance optimization - run every 6 hours
    'optimize-ai-performance': {
        'task': 'apps.ai_engine.tasks.optimize_ai_performance',
        'schedule': 21600.0,  # 6 hours
    },
    
    # Health check - run every 5 minutes
    'health-check-ai-services': {
        'task': 'apps.ai_engine.tasks.health_check_ai_services',
        'schedule': 300.0,  # 5 minutes
    },
}

# Default fallback responses for different interaction types
DEFAULT_FALLBACK_RESPONSES = {
    'question_generation': [
        "How would you summarize the key outcomes of this meeting?",
        "What were the main topics discussed during the conversation?",
        "Were there any action items or next steps identified?",
        "What concerns or questions were raised by the participants?",
        "How would you rate the overall effectiveness of this meeting?",
        "What follow-up activities are needed based on this discussion?",
        "Were there any decisions made during the meeting?",
        "What additional information or clarification is needed?"
    ],
    
    'data_extraction': {
        'contacts': [],
        'action_items': [],
        'competitive_intelligence': [],
        'deal_information': {
            'budget': None,
            'timeline': None,
            'decision_makers': [],
            'requirements': []
        },
        'meeting_outcome': 'Unable to analyze - AI service temporarily unavailable',
        'next_steps': [],
        'concerns_raised': [],
        'technical_requirements': []
    },
    
    'follow_up_question': "Could you provide more details about that topic?",
    
    'meeting_classification': 'general',
    
    'competitive_analysis': {
        'competitors_mentioned': [],
        'competitive_advantages': [],
        'competitive_concerns': [],
        'competitive_timeline': None
    }
}

# Cache eviction policies
CACHE_EVICTION_POLICIES = {
    'LRU': 'least_recently_used',
    'LFU': 'least_frequently_used',
    'TTL': 'time_to_live',
    'HYBRID': 'hybrid_lru_lfu'
}

# Optimization strategies based on usage patterns
OPTIMIZATION_STRATEGIES = {
    'high_volume': {
        'description': 'Optimized for high-volume usage',
        'cache_ttl_multiplier': 1.5,
        'batch_size_multiplier': 1.2,
        'enable_aggressive_caching': True,
        'enable_request_deduplication': True
    },
    
    'low_latency': {
        'description': 'Optimized for low-latency responses',
        'cache_ttl_multiplier': 0.8,
        'batch_size_multiplier': 0.8,
        'enable_aggressive_caching': True,
        'enable_response_compression': True
    },
    
    'cost_optimized': {
        'description': 'Optimized for cost reduction',
        'cache_ttl_multiplier': 2.0,
        'batch_size_multiplier': 1.5,
        'enable_aggressive_caching': True,
        'enable_semantic_caching': True
    },
    
    'balanced': {
        'description': 'Balanced optimization',
        'cache_ttl_multiplier': 1.0,
        'batch_size_multiplier': 1.0,
        'enable_aggressive_caching': True,
        'enable_context_optimization': True
    }
}

# Monitoring thresholds and alerts
MONITORING_THRESHOLDS = {
    'cache_hit_rate': {
        'excellent': 0.8,
        'good': 0.6,
        'acceptable': 0.4,
        'poor': 0.2
    },
    
    'error_rate': {
        'excellent': 0.01,
        'good': 0.05,
        'acceptable': 0.1,
        'poor': 0.2
    },
    
    'response_time_ms': {
        'excellent': 1000,
        'good': 2000,
        'acceptable': 5000,
        'poor': 10000
    },
    
    'cost_per_interaction': {
        'excellent': 0.001,
        'good': 0.005,
        'acceptable': 0.01,
        'poor': 0.02
    }
}

# Feature flags for gradual rollout
OPTIMIZATION_FEATURE_FLAGS = {
    'ENABLE_INTELLIGENT_CACHING': getattr(settings, 'AI_ENABLE_INTELLIGENT_CACHING', True),
    'ENABLE_CONTEXT_OPTIMIZATION': getattr(settings, 'AI_ENABLE_CONTEXT_OPTIMIZATION', True),
    'ENABLE_BATCH_PROCESSING': getattr(settings, 'AI_ENABLE_BATCH_PROCESSING', True),
    'ENABLE_USAGE_MONITORING': getattr(settings, 'AI_ENABLE_USAGE_MONITORING', True),
    'ENABLE_FALLBACK_MECHANISMS': getattr(settings, 'AI_ENABLE_FALLBACK_MECHANISMS', True),
    'ENABLE_COST_OPTIMIZATION': getattr(settings, 'AI_ENABLE_COST_OPTIMIZATION', True),
    'ENABLE_PERFORMANCE_ALERTS': getattr(settings, 'AI_ENABLE_PERFORMANCE_ALERTS', True),
    'ENABLE_SEMANTIC_SIMILARITY': getattr(settings, 'AI_ENABLE_SEMANTIC_SIMILARITY', True),
}


def get_optimization_config():
    """Get the current optimization configuration"""
    return {
        'settings': AI_OPTIMIZATION_SETTINGS,
        'celery_tasks': CELERY_AI_OPTIMIZATION_TASKS,
        'fallback_responses': DEFAULT_FALLBACK_RESPONSES,
        'cache_policies': CACHE_EVICTION_POLICIES,
        'strategies': OPTIMIZATION_STRATEGIES,
        'thresholds': MONITORING_THRESHOLDS,
        'feature_flags': OPTIMIZATION_FEATURE_FLAGS
    }


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a specific optimization feature is enabled"""
    return OPTIMIZATION_FEATURE_FLAGS.get(feature_name, False)


def get_optimization_strategy(strategy_name: str = 'balanced'):
    """Get optimization strategy configuration"""
    return OPTIMIZATION_STRATEGIES.get(strategy_name, OPTIMIZATION_STRATEGIES['balanced'])


def get_monitoring_threshold(metric_name: str, level: str = 'acceptable'):
    """Get monitoring threshold for a specific metric"""
    metric_thresholds = MONITORING_THRESHOLDS.get(metric_name, {})
    return metric_thresholds.get(level, 0)