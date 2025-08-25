"""
AI Engine URL Configuration
"""
from django.urls import path
from . import views
from . import optimization_views

app_name = 'ai_engine'

urlpatterns = [
    # Question Generation
    path('questions/generate/', views.generate_questions, name='generate_questions'),
    path('questions/follow-up/', views.generate_follow_up, name='generate_follow_up'),
    
    # Data Extraction
    path('extract/', views.extract_data, name='extract_data'),
    path('extract/specific/', views.extract_specific_data, name='extract_specific_data'),
    
    # System Health
    path('health/', views.health_status, name='health_status'),
    
    # Template Management
    path('templates/', views.list_templates, name='list_templates'),
    path('templates/create/', views.create_template, name='create_template'),
    
    # Interaction History
    path('interactions/', views.interaction_history, name='interaction_history'),
    
    # Optimization and Monitoring
    path('optimization/status/', optimization_views.optimization_status, name='optimization_status'),
    path('optimization/cache/metrics/', optimization_views.cache_metrics, name='cache_metrics'),
    path('optimization/cache/cleanup/', optimization_views.trigger_cache_cleanup, name='trigger_cache_cleanup'),
    path('optimization/batch/schedule/', optimization_views.schedule_batch_processing, name='schedule_batch_processing'),
    path('optimization/service/health/', optimization_views.service_health, name='service_health'),
    path('optimization/report/generate/', optimization_views.generate_report, name='generate_report'),
    path('optimization/test/', optimization_views.test_optimization, name='test_optimization'),
    path('optimization/suggestions/', optimization_views.optimization_suggestions, name='optimization_suggestions'),
    path('optimization/quick-status/', optimization_views.quick_status, name='quick_status'),
]