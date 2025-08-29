"""
URL configuration for intelligent_meeting_workflow project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import health

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Health check endpoints
    path('api/health/', health.health_check, name='health_check'),
    path('api/health/detailed/', health.health_detailed, name='health_detailed'),
    path('api/readiness/', health.readiness_check, name='readiness_check'),
    path('api/liveness/', health.liveness_check, name='liveness_check'),
    
    # Application URLs
    path('api/meetings/', include('meetings.urls')),
    path('api/leads/', include('leads.urls')),
    path('api/ai/', include('ai_assistant.urls')),
    path('api/performance/', include('performance_monitoring.urls')),
    
    # API root
    path('api/', include('meetings.urls')),  # Default API routes
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Add debug toolbar in development
if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns