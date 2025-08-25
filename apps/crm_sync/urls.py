"""
URL configuration for crm_sync app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CRMSyncViewSet, SyncRecordViewSet, ConflictViewSet, SyncLogViewSet

# Create router for ViewSets
router = DefaultRouter()
router.register(r'sync', CRMSyncViewSet, basename='crm-sync')
router.register(r'records', SyncRecordViewSet, basename='sync-records')
router.register(r'conflicts', ConflictViewSet, basename='sync-conflicts')
router.register(r'logs', SyncLogViewSet, basename='sync-logs')

app_name = 'crm_sync'

urlpatterns = [
    path('api/v1/crm/', include(router.urls)),
]