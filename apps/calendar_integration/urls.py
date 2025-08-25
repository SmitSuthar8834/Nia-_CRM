"""
URL configuration for calendar_integration app
"""
from django.urls import path
from . import views

app_name = 'calendar_integration'

urlpatterns = [
    # Calendar provider management
    path('providers/', views.get_calendar_providers, name='get_providers'),
    path('providers/<str:provider_name>/connect/', views.connect_calendar_provider, name='connect_provider'),
    path('providers/<str:provider_name>/disconnect/', views.disconnect_calendar_provider, name='disconnect_provider'),
    path('providers/<str:provider_name>/test/', views.test_calendar_connection, name='test_connection'),
    
    # OAuth callbacks
    path('callback/<str:provider_name>/', views.calendar_oauth_callback, name='oauth_callback'),
    
    # Calendar synchronization
    path('sync/', views.sync_calendars, name='sync_calendars'),
    path('sync/status/', views.get_sync_status, name='sync_status'),
    
    # Calendar events
    path('events/', views.get_calendar_events, name='get_events'),
    path('events/<uuid:event_id>/insights/', views.get_meeting_insights, name='meeting_insights'),
    
    # Meeting detection
    path('meetings/detect/', views.detect_meetings, name='detect_meetings'),
    path('conflicts/', views.get_scheduling_conflicts, name='scheduling_conflicts'),
    
    # Webhooks
    path('webhook/<str:provider_name>/', views.calendar_webhook, name='calendar_webhook'),
]