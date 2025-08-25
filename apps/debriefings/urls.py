"""
URL configuration for debriefings app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'sessions', views.DebriefingSessionViewSet, basename='debriefing-session')
router.register(r'questions', views.DebriefingQuestionViewSet, basename='debriefing-question')
router.register(r'insights', views.DebriefingInsightViewSet, basename='debriefing-insight')
router.register(r'templates', views.DebriefingTemplateViewSet, basename='debriefing-template')

app_name = 'debriefings'

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Analytics endpoints
    path('analytics/', views.DebriefingAnalyticsView.as_view(), name='debriefing-analytics'),
    path('analytics/system/', views.SystemAnalyticsView.as_view(), name='system-analytics'),
    
    # Export endpoints
    path('export/', views.DebriefingExportView.as_view(), name='debriefing-export'),
    
    # Utility endpoints
    path('sessions/active/', views.get_active_sessions, name='active-sessions'),
    path('sessions/timeout-check/', views.check_session_timeout, name='timeout-check'),
]