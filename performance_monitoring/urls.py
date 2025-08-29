"""
URL patterns for performance monitoring API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceMetricViewSet, CallBotPerformanceViewSet,
    AIProcessingPerformanceViewSet, SystemAlertViewSet,
    PerformanceThresholdViewSet, ConcurrentCallMetricsViewSet,
    PerformanceMonitoringAPIView
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'metrics', PerformanceMetricViewSet, basename='performancemetric')
router.register(r'call-bot-performance', CallBotPerformanceViewSet, basename='callbotperformance')
router.register(r'ai-performance', AIProcessingPerformanceViewSet, basename='aiprocessingperformance')
router.register(r'alerts', SystemAlertViewSet, basename='systemalert')
router.register(r'thresholds', PerformanceThresholdViewSet, basename='performancethreshold')
router.register(r'concurrent-calls', ConcurrentCallMetricsViewSet, basename='concurrentcallmetrics')
router.register(r'monitoring', PerformanceMonitoringAPIView, basename='performancemonitoring')

app_name = 'performance_monitoring'

urlpatterns = [
    path('api/', include(router.urls)),
]