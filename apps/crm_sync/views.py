"""
CRM Synchronization API Views
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.permissions import ManagerOrAdminPermission
from .services import CRMSyncService, sync_all_leads_task, sync_lead_to_creatio
from .models import CreatioSync, SyncConflict, SyncLog
from .serializers import (
    CreatioSyncSerializer, SyncConflictSerializer, SyncLogSerializer,
    SyncRequestSerializer, ConflictResolutionSerializer
)


class CRMSyncViewSet(viewsets.ViewSet):
    """
    ViewSet for CRM synchronization operations
    """
    permission_classes = [IsAuthenticated, ManagerOrAdminPermission]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_service = CRMSyncService()
    
    @action(detail=False, methods=['post'])
    def sync_all(self, request):
        """
        Trigger bidirectional synchronization of all leads
        """
        serializer = SyncRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        force = serializer.validated_data.get('force', False)
        async_sync = serializer.validated_data.get('async_execution', True)
        
        if async_sync:
            # Trigger async task
            task = sync_all_leads_task.delay(force=force)
            return Response({
                'message': 'Synchronization started',
                'task_id': task.id,
                'async': True
            }, status=status.HTTP_202_ACCEPTED)
        else:
            # Synchronous execution
            result = self.sync_service.sync_all_leads(force=force)
            return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='sync-lead')
    def sync_lead(self, request):
        """
        Synchronize a specific lead
        """
        lead_id = request.data.get('lead_id')
        direction = request.data.get('direction', 'bidirectional')
        async_sync = request.data.get('async_execution', True)
        
        if not lead_id:
            return Response({
                'error': 'lead_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if direction not in ['to_creatio', 'from_creatio', 'bidirectional']:
            return Response({
                'error': 'Invalid direction. Must be: to_creatio, from_creatio, or bidirectional'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if async_sync and direction in ['to_creatio', 'bidirectional']:
            # Trigger async task
            task = sync_lead_to_creatio.delay(lead_id)
            return Response({
                'message': 'Lead synchronization started',
                'task_id': task.id,
                'lead_id': lead_id,
                'async': True
            }, status=status.HTTP_202_ACCEPTED)
        else:
            # Synchronous execution
            result = self.sync_service.sync_single_lead(lead_id, direction)
            return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Get synchronization status overview
        """
        status_data = self.sync_service.get_sync_status()
        return Response(status_data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def conflicts(self, request):
        """
        Get pending synchronization conflicts
        """
        conflicts = self.sync_service.get_pending_conflicts()
        return Response({
            'conflicts': conflicts,
            'count': len(conflicts)
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='resolve-conflict')
    def resolve_conflict(self, request):
        """
        Resolve synchronization conflict
        """
        serializer = ConflictResolutionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        conflict_id = serializer.validated_data['conflict_id']
        resolution = serializer.validated_data['resolution']
        resolved_value = serializer.validated_data.get('resolved_value')
        
        result = self.sync_service.resolve_sync_conflict(
            conflict_id=conflict_id,
            resolution=resolution,
            resolved_value=resolved_value,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='create-activity')
    def create_meeting_activity(self, request):
        """
        Create activity in Creatio for meeting
        """
        meeting_id = request.data.get('meeting_id')
        
        if not meeting_id:
            return Response({
                'error': 'meeting_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = self.sync_service.create_meeting_activity(meeting_id)
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='update-lead-from-meeting')
    def update_lead_from_meeting(self, request):
        """
        Update lead with meeting-derived data
        """
        lead_id = request.data.get('lead_id')
        meeting_data = request.data.get('meeting_data', {})
        
        if not lead_id:
            return Response({
                'error': 'lead_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = self.sync_service.update_lead_from_meeting_data(lead_id, meeting_data)
        return Response(result, status=status.HTTP_200_OK)


class SyncRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing synchronization records
    """
    queryset = CreatioSync.objects.all()
    serializer_class = CreatioSyncSerializer
    permission_classes = [IsAuthenticated, ManagerOrAdminPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by entity type
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Filter by sync status
        sync_status = self.request.query_params.get('sync_status')
        if sync_status:
            queryset = queryset.filter(sync_status=sync_status)
        
        # Filter by sync direction
        sync_direction = self.request.query_params.get('sync_direction')
        if sync_direction:
            queryset = queryset.filter(sync_direction=sync_direction)
        
        return queryset.order_by('-updated_at')
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """
        Retry failed synchronization
        """
        sync_record = self.get_object()
        
        if sync_record.sync_status != 'failed':
            return Response({
                'error': 'Only failed sync records can be retried'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not sync_record.needs_retry:
            return Response({
                'error': 'Maximum retry attempts exceeded'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset status and trigger retry
        sync_record.sync_status = 'pending'
        sync_record.next_sync = timezone.now()
        sync_record.save()
        
        # Trigger appropriate sync task
        if sync_record.entity_type == 'lead':
            task = sync_lead_to_creatio.delay(str(sync_record.local_id))
            return Response({
                'message': 'Retry initiated',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        
        return Response({
            'message': 'Retry scheduled'
        }, status=status.HTTP_200_OK)


class ConflictViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing and managing synchronization conflicts
    """
    queryset = SyncConflict.objects.all()
    serializer_class = SyncConflictSerializer
    permission_classes = [IsAuthenticated, ManagerOrAdminPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by resolution status
        resolution_status = self.request.query_params.get('resolution_status')
        if resolution_status:
            queryset = queryset.filter(resolution_status=resolution_status)
        
        # Filter by conflict type
        conflict_type = self.request.query_params.get('conflict_type')
        if conflict_type:
            queryset = queryset.filter(conflict_type=conflict_type)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve specific conflict
        """
        conflict = self.get_object()
        
        if conflict.resolution_status != 'pending':
            return Response({
                'error': 'Conflict already resolved'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ConflictResolutionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        resolution = serializer.validated_data['resolution']
        resolved_value = serializer.validated_data.get('resolved_value')
        
        result = self.sync_service.resolve_sync_conflict(
            conflict_id=str(conflict.id),
            resolution=resolution,
            resolved_value=resolved_value,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing synchronization logs
    """
    queryset = SyncLog.objects.all()
    serializer_class = SyncLogSerializer
    permission_classes = [IsAuthenticated, ManagerOrAdminPermission]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by log level
        log_level = self.request.query_params.get('log_level')
        if log_level:
            queryset = queryset.filter(log_level=log_level)
        
        # Filter by operation type
        operation_type = self.request.query_params.get('operation_type')
        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        
        # Filter by entity type
        entity_type = self.request.query_params.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')