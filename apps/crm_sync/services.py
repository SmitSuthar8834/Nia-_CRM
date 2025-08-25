"""
CRM Synchronization Services
"""
import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import transaction
from django.db import models
from celery import shared_task

from .adapters import CreatioAdapter, CreatioSyncError, CreatioAuthenticationError
from .models import CreatioSync, SyncConflict, SyncLog
from apps.leads.models import Lead
from apps.meetings.models import Meeting


logger = logging.getLogger(__name__)


class CRMSyncService:
    """
    Service for managing CRM synchronization operations
    """
    
    def __init__(self):
        self.adapter = CreatioAdapter()
    
    def sync_all_leads(self, force: bool = False) -> Dict[str, Any]:
        """
        Synchronize all leads bidirectionally
        """
        try:
            sync_result = self.adapter.sync_leads_bidirectional()
            
            # Log sync operation
            SyncLog.objects.create(
                log_level='info',
                operation_type='sync',
                message=f"Bidirectional sync completed: {sync_result}",
                request_data={'force': force},
                response_data=sync_result
            )
            
            return {
                'success': True,
                'result': sync_result
            }
            
        except (CreatioSyncError, CreatioAuthenticationError) as e:
            error_msg = f"CRM sync failed: {str(e)}"
            logger.error(error_msg)
            
            SyncLog.objects.create(
                log_level='error',
                operation_type='sync',
                message=error_msg,
                request_data={'force': force}
            )
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def sync_single_lead(self, lead_id: str, direction: str = 'bidirectional') -> Dict[str, Any]:
        """
        Synchronize a single lead
        """
        try:
            lead = Lead.objects.get(id=lead_id)
            
            if direction in ['to_creatio', 'bidirectional']:
                # Sync to Creatio
                creatio_data = self.adapter._convert_lead_to_creatio(lead)
                
                if lead.creatio_id:
                    response = self.adapter._make_request(
                        'PATCH',
                        f"{self.adapter.leads_endpoint}({lead.creatio_id})",
                        data=creatio_data
                    )
                else:
                    response = self.adapter._make_request(
                        'POST',
                        self.adapter.leads_endpoint,
                        data=creatio_data
                    )
                    
                    response_data = response.json()
                    creatio_id = response_data.get('Id')
                    if creatio_id:
                        lead.creatio_id = creatio_id
                        lead.save()
            
            if direction in ['from_creatio', 'bidirectional'] and lead.creatio_id:
                # Sync from Creatio
                response = self.adapter._make_request(
                    'GET',
                    f"{self.adapter.leads_endpoint}({lead.creatio_id})"
                )
                creatio_data = response.json()
                self.adapter._update_local_lead_from_creatio(lead, creatio_data)
            
            # Update sync record
            sync_record, _ = CreatioSync.objects.get_or_create(
                entity_type='lead',
                local_id=lead.id,
                defaults={
                    'creatio_id': lead.creatio_id,
                    'sync_direction': direction
                }
            )
            sync_record.mark_success(lead.creatio_id)
            
            return {
                'success': True,
                'lead_id': lead_id,
                'creatio_id': lead.creatio_id
            }
            
        except Lead.DoesNotExist:
            return {
                'success': False,
                'error': f'Lead {lead_id} not found'
            }
        except Exception as e:
            error_msg = f"Failed to sync lead {lead_id}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def create_meeting_activity(self, meeting_id: str) -> Dict[str, Any]:
        """
        Create activity in Creatio for meeting
        """
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            success = self.adapter.create_activity_for_meeting(meeting)
            
            return {
                'success': success,
                'meeting_id': meeting_id
            }
            
        except Meeting.DoesNotExist:
            return {
                'success': False,
                'error': f'Meeting {meeting_id} not found'
            }
        except Exception as e:
            error_msg = f"Failed to create activity for meeting {meeting_id}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def resolve_sync_conflict(self, conflict_id: str, resolution: str, 
                            resolved_value: Any = None, user=None) -> Dict[str, Any]:
        """
        Resolve synchronization conflict
        """
        try:
            conflict = SyncConflict.objects.get(id=conflict_id)
            
            if resolution == 'manual' and resolved_value is not None:
                # Apply manual resolution
                conflict.resolve('resolved_manual', resolved_value, user)
                
                # Apply the resolved value to local record
                if conflict.sync_record.entity_type == 'lead':
                    lead = Lead.objects.get(id=conflict.sync_record.local_id)
                    setattr(lead, conflict.field_name, resolved_value)
                    lead.save(update_fields=[conflict.field_name])
                    
                    # Schedule sync to Creatio
                    conflict.sync_record.sync_status = 'pending'
                    conflict.sync_record.save()
            else:
                # Use adapter's resolve method
                success = self.adapter.resolve_conflict(conflict_id, resolution, user)
                if not success:
                    return {
                        'success': False,
                        'error': 'Failed to resolve conflict'
                    }
            
            return {
                'success': True,
                'conflict_id': conflict_id,
                'resolution': resolution
            }
            
        except SyncConflict.DoesNotExist:
            return {
                'success': False,
                'error': f'Conflict {conflict_id} not found'
            }
        except Exception as e:
            error_msg = f"Failed to resolve conflict {conflict_id}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get comprehensive sync status
        """
        return self.adapter.get_sync_status()
    
    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """
        Get all pending conflicts
        """
        conflicts = SyncConflict.objects.filter(
            resolution_status='pending'
        ).select_related('sync_record')
        
        return [
            {
                'id': str(conflict.id),
                'entity_type': conflict.sync_record.entity_type,
                'entity_id': str(conflict.sync_record.local_id),
                'conflict_type': conflict.conflict_type,
                'field_name': conflict.field_name,
                'local_value': conflict.local_value,
                'creatio_value': conflict.creatio_value,
                'created_at': conflict.created_at.isoformat()
            }
            for conflict in conflicts
        ]
    
    def update_lead_from_meeting_data(self, lead_id: str, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update lead with meeting-derived data and sync to Creatio
        """
        try:
            success = self.adapter.update_lead_from_meeting(lead_id, meeting_data)
            
            if success:
                # Trigger async sync to Creatio
                sync_lead_to_creatio.delay(lead_id)
            
            return {
                'success': success,
                'lead_id': lead_id
            }
            
        except Exception as e:
            error_msg = f"Failed to update lead {lead_id} from meeting data: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }


# Celery Tasks for Asynchronous Processing

@shared_task(bind=True, max_retries=3)
def sync_all_leads_task(self, force=False):
    """
    Celery task for bidirectional lead synchronization
    """
    try:
        service = CRMSyncService()
        result = service.sync_all_leads(force=force)
        
        if not result['success']:
            # Retry on failure
            raise Exception(result['error'])
        
        return result
        
    except Exception as e:
        logger.error(f"Sync task failed: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
            raise self.retry(countdown=retry_delay, exc=e)
        
        # Final failure
        SyncLog.objects.create(
            log_level='critical',
            operation_type='sync',
            message=f"Sync task failed after {self.max_retries} retries: {str(e)}"
        )
        
        raise e


@shared_task(bind=True, max_retries=3)
def sync_lead_to_creatio(self, lead_id):
    """
    Celery task for syncing single lead to Creatio
    """
    try:
        service = CRMSyncService()
        result = service.sync_single_lead(lead_id, direction='to_creatio')
        
        if not result['success']:
            raise Exception(result['error'])
        
        return result
        
    except Exception as e:
        logger.error(f"Lead sync task failed for {lead_id}: {str(e)}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 30  # 30s, 1m, 2m
            raise self.retry(countdown=retry_delay, exc=e)
        
        # Mark sync record as failed
        try:
            sync_record = CreatioSync.objects.get(
                entity_type='lead',
                local_id=lead_id
            )
            sync_record.mark_failed(str(e))
        except CreatioSync.DoesNotExist:
            pass
        
        raise e


@shared_task(bind=True, max_retries=3)
def create_meeting_activity_task(self, meeting_id):
    """
    Celery task for creating meeting activity in Creatio
    """
    try:
        service = CRMSyncService()
        result = service.create_meeting_activity(meeting_id)
        
        if not result['success']:
            raise Exception(result['error'])
        
        return result
        
    except Exception as e:
        logger.error(f"Meeting activity creation failed for {meeting_id}: {str(e)}")
        
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries * 30
            raise self.retry(countdown=retry_delay, exc=e)
        
        raise e


@shared_task
def scheduled_sync_task():
    """
    Scheduled task for regular synchronization
    """
    try:
        service = CRMSyncService()
        
        # Sync pending records
        pending_syncs = CreatioSync.objects.filter(
            sync_status='pending',
            next_sync__lte=timezone.now()
        )
        
        for sync_record in pending_syncs:
            if sync_record.entity_type == 'lead':
                sync_lead_to_creatio.delay(str(sync_record.local_id))
            elif sync_record.entity_type == 'activity':
                create_meeting_activity_task.delay(str(sync_record.local_id))
        
        # Retry failed syncs
        failed_syncs = CreatioSync.objects.filter(
            sync_status='failed',
            retry_count__lt=models.F('max_retries'),
            next_sync__lte=timezone.now()
        )
        
        for sync_record in failed_syncs:
            if sync_record.entity_type == 'lead':
                sync_lead_to_creatio.delay(str(sync_record.local_id))
        
        logger.info(f"Scheduled sync processed {pending_syncs.count()} pending and {failed_syncs.count()} failed syncs")
        
    except Exception as e:
        logger.error(f"Scheduled sync task failed: {str(e)}")
        raise e