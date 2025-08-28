"""
URL configuration for NIA Meeting Intelligence project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/settings/', include('apps.accounts.urls')),
    path('api/v1/meetings/', include('apps.meetings.urls')),
    path('api/v1/debriefings/', include('apps.debriefings.urls')),
    path('api/v1/leads/', include('apps.leads.urls')),
    path('api/v1/calendar/', include('apps.calendar_integration.urls')),
    path('api/v1/crm/', include('apps.crm_sync.urls')),
    path('api/v1/ai/', include('apps.ai_engine.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)