"""
Performance monitoring app configuration
"""
from django.apps import AppConfig


class PerformanceMonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance_monitoring'
    verbose_name = 'Performance Monitoring'
    
    def ready(self):
        """Initialize performance monitoring when app is ready"""
        # Import signal handlers
        from . import signals