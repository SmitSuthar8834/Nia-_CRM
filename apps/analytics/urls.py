"""
URL configuration for analytics app
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard and main analytics
    path('dashboard/', views.DashboardAnalyticsView.as_view(), name='dashboard'),
    path('dashboard-metrics/', views.DashboardAnalyticsView.as_view(), name='dashboard-metrics'),
    
    # Performance metrics
    path('metrics/performance/', views.PerformanceMetricsView.as_view(), name='performance-metrics'),
    
    # User engagement metrics
    path('metrics/engagement/', views.UserEngagementMetricsView.as_view(), name='engagement-metrics'),
    path('track-engagement/', views.track_engagement, name='track-engagement'),
    
    # Data quality metrics
    path('metrics/data-quality/', views.DataQualityMetricsView.as_view(), name='data-quality-metrics'),
    
    # System health metrics
    path('metrics/system-health/', views.SystemHealthMetricsView.as_view(), name='system-health-metrics'),
    path('system-health/status/', views.system_health_status, name='system-health-status'),
    
    # Reports
    path('reports/', views.ReportsView.as_view(), name='reports-list'),
    path('reports/<uuid:pk>/', views.ReportDetailView.as_view(), name='report-detail'),
    path('reports/generate/', views.generate_report, name='generate-report'),
    
    # Data export
    path('export/', views.export_analytics_data, name='export-data'),
]