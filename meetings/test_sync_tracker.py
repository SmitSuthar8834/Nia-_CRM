"""
Tests for CRM synchronization status tracking and error reporting
"""
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from leads.models import Lead
from .models import Meeting, MeetingSession, ActionItem
from .sync_tracker import SyncTracker, SyncOperation
from .crm_service import CRMSyncStatus


class SyncTrackerTest(TestCase):
    """Test cases for sync tracker"""
    
    def setUp(self):
        self.tracker = SyncTracker()
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id='CRM_123',
            name='John Doe',
            email='john@example.com',
            company='Test Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='cal_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='completed'
        )
        
        self.session = MeetingSession.objects.create(
            meeting=self.meeting,
            ai_session_id='ai_123',
            notes='Test meeting notes',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
    
    def tearDown(self):
        # Clear cache after each test
        cache.clear()
    
    def test_track_sync_operation(self):
        """Test tracking a sync operation"""
        details = {
            'crm_record_ids': ['crm_123'],
            'retry_count': 0
        }
        
        tracking_id = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details
        )
        
        self.assertIsNotNone(tracking_id)
        self.assertIn(str(self.meeting.id), tracking_id)
        self.assertIn(SyncOperation.MEETING_OUTCOME.value, tracking_id)
        
        # Verify the operation was cached
        cache_key = f"{self.tracker.CACHE_PREFIX}:operation:{tracking_id}"
        cached_data = cache.get(cache_key)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data['meeting_id'], self.meeting.id)
        self.assertEqual(cached_data['operation'], SyncOperation.MEETING_OUTCOME.value)
        self.assertEqual(cached_data['status'], CRMSyncStatus.SUCCESS.value)
        self.assertEqual(cached_data['details']['crm_record_ids'], ['crm_123'])
    
    def test_get_sync_status_no_operations(self):
        """Test getting sync status when no operations exist"""
        status = self.tracker.get_sync_status(self.meeting.id)
        
        self.assertEqual(status['meeting_id'], self.meeting.id)
        self.assertEqual(status['operations'], [])
        self.assertEqual(status['summary']['total_operations'], 0)
        self.assertEqual(status['summary']['successful_operations'], 0)
        self.assertEqual(status['summary']['failed_operations'], 0)
        self.assertIsNone(status['summary']['last_sync'])
    
    def test_get_sync_status_with_operations(self):
        """Test getting sync status with multiple operations"""
        # Track successful operation
        details1 = {'crm_record_ids': ['crm_123']}
        tracking_id1 = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details1
        )
        
        # Track failed operation
        details2 = {'error_message': 'API error'}
        tracking_id2 = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.FOLLOW_UP_TASKS,
            CRMSyncStatus.FAILED,
            details2
        )
        
        status = self.tracker.get_sync_status(self.meeting.id)
        
        self.assertEqual(status['meeting_id'], self.meeting.id)
        self.assertEqual(len(status['operations']), 2)
        self.assertEqual(status['summary']['total_operations'], 2)
        self.assertEqual(status['summary']['successful_operations'], 1)
        self.assertEqual(status['summary']['failed_operations'], 1)
        self.assertIsNotNone(status['summary']['last_sync'])
    
    def test_get_failed_operations(self):
        """Test getting failed operations within time window"""
        # Track a failed operation
        details = {'error_message': 'CRM API error'}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.FAILED,
            details
        )
        
        # Track a successful operation
        details2 = {'crm_record_ids': ['crm_123']}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.FOLLOW_UP_TASKS,
            CRMSyncStatus.SUCCESS,
            details2
        )
        
        failed_operations = self.tracker.get_failed_operations(hours_back=24)
        
        # Should only return the failed operation
        self.assertEqual(len(failed_operations), 1)
        self.assertEqual(failed_operations[0]['status'], CRMSyncStatus.FAILED.value)
        self.assertEqual(failed_operations[0]['operation'], SyncOperation.MEETING_OUTCOME.value)
    
    @patch('meetings.crm_service.CRMSyncService.retry_failed_sync')
    def test_retry_failed_operation_meeting_outcome(self, mock_retry):
        """Test retrying a failed meeting outcome sync"""
        from .crm_service import CRMSyncResult
        
        # Track a failed operation
        details = {'error_message': 'CRM API error', 'retry_count': 0}
        tracking_id = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.FAILED,
            details
        )
        
        # Mock successful retry
        mock_retry.return_value = CRMSyncResult(
            status=CRMSyncStatus.SUCCESS,
            message="Retry successful",
            crm_record_id="crm_456"
        )
        
        result = self.tracker.retry_failed_operation(tracking_id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], "Retry successful")
        self.assertIn('new_tracking_id', result)
        
        # Verify retry was called
        mock_retry.assert_called_once_with(self.meeting.id)
    
    @patch('meetings.crm_service.CRMSyncService.create_follow_up_tasks')
    def test_retry_failed_operation_follow_up_tasks(self, mock_create_tasks):
        """Test retrying failed follow-up task creation"""
        from .crm_service import CRMSyncResult
        
        # Track a failed operation
        details = {'error_message': 'Task creation failed', 'retry_count': 0}
        tracking_id = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.FOLLOW_UP_TASKS,
            CRMSyncStatus.FAILED,
            details
        )
        
        # Mock successful retry
        mock_create_tasks.return_value = [
            CRMSyncResult(
                status=CRMSyncStatus.SUCCESS,
                message="Task created",
                crm_record_id="task_123"
            )
        ]
        
        result = self.tracker.retry_failed_operation(tracking_id)
        
        self.assertTrue(result['success'])
        self.assertIn('1 successful, 0 failed', result['message'])
        
        # Verify retry was called
        mock_create_tasks.assert_called_once_with(self.meeting.id)
    
    def test_retry_failed_operation_not_found(self):
        """Test retrying a non-existent operation"""
        result = self.tracker.retry_failed_operation('nonexistent_id')
        
        self.assertFalse(result['success'])
        self.assertIn('not found', result['message'])
    
    def test_retry_failed_operation_not_failed(self):
        """Test retrying an operation that's not in failed state"""
        # Track a successful operation
        details = {'crm_record_ids': ['crm_123']}
        tracking_id = self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details
        )
        
        result = self.tracker.retry_failed_operation(tracking_id)
        
        self.assertFalse(result['success'])
        self.assertIn('not in failed state', result['message'])
    
    def test_generate_sync_report(self):
        """Test generating a sync report"""
        start_date = timezone.now() - timedelta(days=1)
        end_date = timezone.now() + timedelta(hours=1)  # Ensure end_date is in the future
        
        # Track some operations
        details1 = {'crm_record_ids': ['crm_123']}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details1
        )
        
        details2 = {'error_message': 'API error'}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.FOLLOW_UP_TASKS,
            CRMSyncStatus.FAILED,
            details2
        )
        
        report = self.tracker.generate_sync_report(start_date, end_date)
        
        self.assertIn('report_period', report)
        self.assertIn('summary', report)
        self.assertIn('operation_breakdown', report)
        self.assertIn('error_summary', report)
        
        # Check summary data
        summary = report['summary']
        self.assertGreaterEqual(summary['total_meetings'], 1)
        self.assertEqual(summary['total_operations'], 2)
        self.assertEqual(summary['successful_operations'], 1)
        self.assertEqual(summary['failed_operations'], 1)
        self.assertEqual(summary['success_rate'], 50.0)
        
        # Check operation breakdown
        breakdown = report['operation_breakdown']
        self.assertEqual(breakdown[SyncOperation.MEETING_OUTCOME.value]['success'], 1)
        self.assertEqual(breakdown[SyncOperation.FOLLOW_UP_TASKS.value]['failed'], 1)
        
        # Check error summary
        error_summary = report['error_summary']
        self.assertIn('API error', error_summary)
        self.assertEqual(error_summary['API error'], 1)
    
    def test_get_sync_health_metrics(self):
        """Test getting sync health metrics"""
        # Track some recent failures
        details = {'error_message': 'API error'}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.FAILED,
            details
        )
        
        metrics = self.tracker.get_sync_health_metrics()
        
        self.assertIn('health_status', metrics)
        self.assertIn('recent_meetings', metrics)
        self.assertIn('recent_failures', metrics)
        self.assertIn('failure_rate', metrics)
        self.assertIn('last_updated', metrics)
        
        # Health status should be determined based on failure rate
        self.assertIn(metrics['health_status'], ['healthy', 'warning', 'critical'])
    
    def test_cleanup_old_tracking_data(self):
        """Test cleanup of old tracking data"""
        # This is mostly a placeholder test since the actual implementation
        # would depend on the specific caching strategy
        try:
            self.tracker.cleanup_old_tracking_data(days_to_keep=30)
            # If no exception is raised, the test passes
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"cleanup_old_tracking_data raised an exception: {e}")
    
    def test_track_multiple_operations_same_meeting(self):
        """Test tracking multiple operations for the same meeting"""
        # Track multiple operations
        for i in range(3):
            details = {'crm_record_ids': [f'crm_{i}']}
            self.tracker.track_sync_operation(
                self.meeting.id,
                SyncOperation.MEETING_OUTCOME,
                CRMSyncStatus.SUCCESS,
                details
            )
        
        # Verify all operations are tracked
        status = self.tracker.get_sync_status(self.meeting.id)
        self.assertEqual(len(status['operations']), 3)
        self.assertEqual(status['summary']['total_operations'], 3)
        self.assertEqual(status['summary']['successful_operations'], 3)
    
    def test_track_operations_different_meetings(self):
        """Test tracking operations for different meetings"""
        # Create another meeting
        meeting2 = Meeting.objects.create(
            calendar_event_id='cal_456',
            lead=self.lead,
            title='Another Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        # Track operations for both meetings
        details1 = {'crm_record_ids': ['crm_123']}
        self.tracker.track_sync_operation(
            self.meeting.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details1
        )
        
        details2 = {'crm_record_ids': ['crm_456']}
        self.tracker.track_sync_operation(
            meeting2.id,
            SyncOperation.MEETING_OUTCOME,
            CRMSyncStatus.SUCCESS,
            details2
        )
        
        # Verify operations are tracked separately
        status1 = self.tracker.get_sync_status(self.meeting.id)
        status2 = self.tracker.get_sync_status(meeting2.id)
        
        self.assertEqual(len(status1['operations']), 1)
        self.assertEqual(len(status2['operations']), 1)
        self.assertEqual(status1['operations'][0]['meeting_id'], self.meeting.id)
        self.assertEqual(status2['operations'][0]['meeting_id'], meeting2.id)
    
    def test_error_handling_in_report_generation(self):
        """Test error handling in report generation"""
        # Test with invalid date range
        start_date = timezone.now()
        end_date = timezone.now() - timedelta(days=1)  # End before start
        
        report = self.tracker.generate_sync_report(start_date, end_date)
        
        # Should still return a valid report structure
        self.assertIn('summary', report)
        self.assertIn('operation_breakdown', report)
    
    def test_health_metrics_with_no_recent_activity(self):
        """Test health metrics when there's no recent activity"""
        # Don't track any operations
        metrics = self.tracker.get_sync_health_metrics()
        
        self.assertEqual(metrics['health_status'], 'healthy')
        self.assertEqual(metrics['recent_failures'], 0)
        self.assertEqual(metrics['failure_rate'], 0.0)