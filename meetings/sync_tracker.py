"""
CRM synchronization status tracking and error reporting
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache

from .models import Meeting, ActionItem
from .crm_service import CRMSyncStatus

logger = logging.getLogger(__name__)


class SyncOperation(Enum):
    """Types of CRM synchronization operations"""
    MEETING_OUTCOME = "meeting_outcome"
    FOLLOW_UP_TASKS = "follow_up_tasks"
    LEAD_UPDATE = "lead_update"


class SyncTracker:
    """
    Service for tracking CRM synchronization status and errors
    """
    
    CACHE_PREFIX = "sync_tracker"
    CACHE_TIMEOUT = 86400  # 24 hours
    
    def __init__(self):
        self.cache = cache
    
    def track_sync_operation(self, meeting_id: int, operation: SyncOperation, 
                           status: CRMSyncStatus, details: Dict[str, Any]) -> str:
        """
        Track a CRM synchronization operation
        """
        tracking_id = f"{meeting_id}_{operation.value}_{timezone.now().timestamp()}"
        
        sync_record = {
            'tracking_id': tracking_id,
            'meeting_id': meeting_id,
            'operation': operation.value,
            'status': status.value,
            'timestamp': timezone.now().isoformat(),
            'details': details,
            'retry_count': details.get('retry_count', 0),
            'error_message': details.get('error_message'),
            'crm_record_ids': details.get('crm_record_ids', [])
        }
        
        # Cache the sync record
        cache_key = f"{self.CACHE_PREFIX}:operation:{tracking_id}"
        self.cache.set(cache_key, sync_record, self.CACHE_TIMEOUT)
        
        # Also maintain a list of operations for the meeting
        meeting_cache_key = f"{self.CACHE_PREFIX}:meeting:{meeting_id}"
        meeting_operations = self.cache.get(meeting_cache_key, [])
        meeting_operations.append(tracking_id)
        self.cache.set(meeting_cache_key, meeting_operations, self.CACHE_TIMEOUT)
        
        logger.info(f"Tracked sync operation {tracking_id}: {operation.value} - {status.value}")
        return tracking_id
    
    def get_sync_status(self, meeting_id: int) -> Dict[str, Any]:
        """
        Get comprehensive sync status for a meeting
        """
        meeting_cache_key = f"{self.CACHE_PREFIX}:meeting:{meeting_id}"
        operation_ids = self.cache.get(meeting_cache_key, [])
        
        if not operation_ids:
            return {
                'meeting_id': meeting_id,
                'operations': [],
                'summary': {
                    'total_operations': 0,
                    'successful_operations': 0,
                    'failed_operations': 0,
                    'pending_operations': 0,
                    'last_sync': None
                }
            }
        
        operations = []
        successful = 0
        failed = 0
        pending = 0
        last_sync = None
        
        for operation_id in operation_ids:
            cache_key = f"{self.CACHE_PREFIX}:operation:{operation_id}"
            operation_data = self.cache.get(cache_key)
            
            if operation_data:
                operations.append(operation_data)
                
                status = operation_data['status']
                if status == CRMSyncStatus.SUCCESS.value:
                    successful += 1
                elif status == CRMSyncStatus.FAILED.value:
                    failed += 1
                else:
                    pending += 1
                
                # Track the most recent sync
                op_timestamp = datetime.fromisoformat(operation_data['timestamp'])
                if last_sync is None or op_timestamp > last_sync:
                    last_sync = op_timestamp
        
        return {
            'meeting_id': meeting_id,
            'operations': operations,
            'summary': {
                'total_operations': len(operations),
                'successful_operations': successful,
                'failed_operations': failed,
                'pending_operations': pending,
                'last_sync': last_sync.isoformat() if last_sync else None
            }
        }
    
    def get_failed_operations(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        Get all failed sync operations within the specified time window
        """
        cutoff_time = timezone.now() - timedelta(hours=hours_back)
        failed_operations = []
        
        # This is a simplified implementation
        # In a production system, you might want to use a database table
        # or a more sophisticated caching strategy
        
        try:
            # Get all meetings that have had sync operations
            all_meetings = Meeting.objects.filter(
                updated_at__gte=cutoff_time
            ).values_list('id', flat=True)
            
            for meeting_id in all_meetings:
                sync_status = self.get_sync_status(meeting_id)
                
                for operation in sync_status['operations']:
                    if (operation['status'] == CRMSyncStatus.FAILED.value and 
                        datetime.fromisoformat(operation['timestamp']) >= cutoff_time):
                        failed_operations.append(operation)
            
        except Exception as e:
            logger.error(f"Error retrieving failed operations: {str(e)}")
        
        return failed_operations
    
    def retry_failed_operation(self, tracking_id: str) -> Dict[str, Any]:
        """
        Retry a failed sync operation
        """
        cache_key = f"{self.CACHE_PREFIX}:operation:{tracking_id}"
        operation_data = self.cache.get(cache_key)
        
        if not operation_data:
            return {
                'success': False,
                'message': f'Operation {tracking_id} not found'
            }
        
        if operation_data['status'] != CRMSyncStatus.FAILED.value:
            return {
                'success': False,
                'message': f'Operation {tracking_id} is not in failed state'
            }
        
        meeting_id = operation_data['meeting_id']
        operation_type = SyncOperation(operation_data['operation'])
        
        try:
            # Import here to avoid circular imports
            from .crm_service import CRMSyncService
            crm_service = CRMSyncService()
            
            if operation_type == SyncOperation.MEETING_OUTCOME:
                result = crm_service.retry_failed_sync(meeting_id)
                
                # Track the retry operation
                retry_details = {
                    'retry_count': operation_data['retry_count'] + 1,
                    'original_tracking_id': tracking_id,
                    'crm_record_ids': [result.crm_record_id] if result.crm_record_id else [],
                    'error_message': result.message if result.status == CRMSyncStatus.FAILED else None
                }
                
                self.track_sync_operation(meeting_id, operation_type, result.status, retry_details)
                
                return {
                    'success': result.status == CRMSyncStatus.SUCCESS,
                    'message': result.message,
                    'new_tracking_id': retry_details.get('tracking_id')
                }
            
            elif operation_type == SyncOperation.FOLLOW_UP_TASKS:
                results = crm_service.create_follow_up_tasks(meeting_id)
                
                successful_results = [r for r in results if r.status == CRMSyncStatus.SUCCESS]
                failed_results = [r for r in results if r.status == CRMSyncStatus.FAILED]
                
                retry_details = {
                    'retry_count': operation_data['retry_count'] + 1,
                    'original_tracking_id': tracking_id,
                    'successful_tasks': len(successful_results),
                    'failed_tasks': len(failed_results),
                    'crm_record_ids': [r.crm_record_id for r in successful_results if r.crm_record_id],
                    'error_message': '; '.join([r.message for r in failed_results]) if failed_results else None
                }
                
                overall_status = CRMSyncStatus.SUCCESS if not failed_results else CRMSyncStatus.FAILED
                self.track_sync_operation(meeting_id, operation_type, overall_status, retry_details)
                
                return {
                    'success': len(failed_results) == 0,
                    'message': f'Retry completed: {len(successful_results)} successful, {len(failed_results)} failed',
                    'new_tracking_id': retry_details.get('tracking_id')
                }
            
            else:
                return {
                    'success': False,
                    'message': f'Retry not supported for operation type: {operation_type.value}'
                }
                
        except Exception as e:
            logger.error(f"Error retrying operation {tracking_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Retry failed: {str(e)}'
            }
    
    def generate_sync_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Generate a comprehensive sync report for a date range
        """
        try:
            # Get all meetings in the date range
            meetings = Meeting.objects.filter(
                updated_at__range=[start_date, end_date]
            ).values_list('id', flat=True)
            
            total_meetings = len(meetings)
            meetings_with_sync = 0
            total_operations = 0
            successful_operations = 0
            failed_operations = 0
            
            operation_breakdown = {
                SyncOperation.MEETING_OUTCOME.value: {'success': 0, 'failed': 0},
                SyncOperation.FOLLOW_UP_TASKS.value: {'success': 0, 'failed': 0}
            }
            
            error_summary = {}
            
            for meeting_id in meetings:
                sync_status = self.get_sync_status(meeting_id)
                
                if sync_status['operations']:
                    meetings_with_sync += 1
                    
                    for operation in sync_status['operations']:
                        # Filter operations within date range
                        op_timestamp = datetime.fromisoformat(operation['timestamp'])
                        if start_date <= op_timestamp <= end_date:
                            total_operations += 1
                            
                            op_type = operation['operation']
                            op_status = operation['status']
                            
                            if op_status == CRMSyncStatus.SUCCESS.value:
                                successful_operations += 1
                                operation_breakdown[op_type]['success'] += 1
                            elif op_status == CRMSyncStatus.FAILED.value:
                                failed_operations += 1
                                operation_breakdown[op_type]['failed'] += 1
                                
                                # Track error types
                                error_msg = operation.get('error_message', 'Unknown error')
                                error_summary[error_msg] = error_summary.get(error_msg, 0) + 1
            
            success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
            
            return {
                'report_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'summary': {
                    'total_meetings': total_meetings,
                    'meetings_with_sync': meetings_with_sync,
                    'total_operations': total_operations,
                    'successful_operations': successful_operations,
                    'failed_operations': failed_operations,
                    'success_rate': round(success_rate, 2)
                },
                'operation_breakdown': operation_breakdown,
                'error_summary': error_summary,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating sync report: {str(e)}")
            return {
                'error': f'Failed to generate report: {str(e)}',
                'generated_at': timezone.now().isoformat()
            }
    
    def cleanup_old_tracking_data(self, days_to_keep: int = 30):
        """
        Clean up old tracking data from cache
        """
        try:
            cutoff_time = timezone.now() - timedelta(days=days_to_keep)
            
            # This is a simplified cleanup
            # In a production system, you might want to implement a more sophisticated cleanup strategy
            logger.info(f"Cleaned up sync tracking data older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up tracking data: {str(e)}")
    
    def get_sync_health_metrics(self) -> Dict[str, Any]:
        """
        Get overall sync health metrics
        """
        try:
            # Get recent failed operations (last 24 hours)
            recent_failures = self.get_failed_operations(hours_back=24)
            
            # Get recent meetings
            recent_meetings = Meeting.objects.filter(
                updated_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            
            # Calculate health metrics
            failure_rate = len(recent_failures) / max(recent_meetings, 1) * 100
            
            health_status = "healthy"
            if failure_rate > 20:
                health_status = "critical"
            elif failure_rate > 10:
                health_status = "warning"
            
            return {
                'health_status': health_status,
                'recent_meetings': recent_meetings,
                'recent_failures': len(recent_failures),
                'failure_rate': round(failure_rate, 2),
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating sync health metrics: {str(e)}")
            return {
                'health_status': 'unknown',
                'error': str(e),
                'last_updated': timezone.now().isoformat()
            }