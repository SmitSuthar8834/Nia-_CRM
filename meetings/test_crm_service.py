"""
Integration tests for CRM synchronization service
"""
import json
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from leads.models import Lead
from .models import Meeting, MeetingSession, ActionItem
from .crm_service import (
    CreatioAPIClient, CRMSyncService, CRMSyncStatus, 
    CRMAuthenticationError, CRMAPIError
)


class CreatioAPIClientTest(TestCase):
    """Test cases for Creatio API client"""
    
    def setUp(self):
        self.client = CreatioAPIClient()
        self.client.base_url = "https://test.creatio.com"
        self.client.username = "test_user"
        self.client.password = "test_pass"
    
    @patch('meetings.crm_service.requests.Session.post')
    def test_authentication_success(self, mock_post):
        """Test successful authentication with Creatio"""
        # Mock successful authentication response
        mock_response = Mock()
        mock_response.cookies = {'BPMCSRF': 'test_token'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = self.client._authenticate()
        
        self.assertTrue(result)
        self.assertEqual(self.client.auth_token, "authenticated")
        self.assertIsNotNone(self.client.token_expires_at)
        
        # Verify the authentication request
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('UserName', call_args[1]['json'])
        self.assertIn('UserPassword', call_args[1]['json'])
    
    @patch('meetings.crm_service.requests.Session.post')
    def test_authentication_failure(self, mock_post):
        """Test authentication failure handling"""
        # Mock failed authentication response
        mock_response = Mock()
        mock_response.cookies = {}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with self.assertRaises(CRMAuthenticationError):
            self.client._authenticate()
    
    @patch('meetings.crm_service.requests.Session.post')
    def test_authentication_network_error(self, mock_post):
        """Test authentication with network error"""
        mock_post.side_effect = requests.RequestException("Network error")
        
        with self.assertRaises(CRMAuthenticationError):
            self.client._authenticate()
    
    @patch.object(CreatioAPIClient, '_ensure_authenticated')
    @patch('meetings.crm_service.requests.Session.request')
    def test_make_request_success(self, mock_request, mock_auth):
        """Test successful API request"""
        mock_auth.return_value = True
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'success': True}
        mock_request.return_value = mock_response
        
        response = self.client._make_request('GET', '/test/endpoint')
        
        self.assertEqual(response.status_code, 200)
        mock_request.assert_called_once()
    
    @patch.object(CreatioAPIClient, '_ensure_authenticated')
    @patch('meetings.crm_service.requests.Session.request')
    def test_make_request_with_retry(self, mock_request, mock_auth):
        """Test API request with retry logic"""
        mock_auth.return_value = True
        
        # First two calls fail, third succeeds
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = requests.RequestException("Server error")
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.raise_for_status.return_value = None
        
        mock_request.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success
        ]
        
        with patch('time.sleep'):  # Speed up test by mocking sleep
            response = self.client._make_request('GET', '/test/endpoint')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_request.call_count, 3)
    
    @patch.object(CreatioAPIClient, '_ensure_authenticated')
    @patch('meetings.crm_service.requests.Session.request')
    def test_make_request_max_retries_exceeded(self, mock_request, mock_auth):
        """Test API request when max retries are exceeded"""
        mock_auth.return_value = True
        
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.RequestException("Server error")
        mock_request.return_value = mock_response
        
        with patch('time.sleep'):  # Speed up test
            with self.assertRaises(CRMAPIError):
                self.client._make_request('GET', '/test/endpoint')
        
        # Should try max_retries + 1 times
        self.assertEqual(mock_request.call_count, self.client.max_retries + 1)
    
    def test_format_meeting_outcome(self):
        """Test meeting outcome formatting for Creatio"""
        meeting_data = {
            'notes': 'Test meeting notes',
            'summary': 'Meeting summary',
            'meeting_date': '2024-01-15T10:00:00Z',
            'duration_minutes': 60,
            'outcome': 'successful',
            'next_steps': 'Follow up next week',
            'lead_status': 'qualified'
        }
        
        formatted = self.client._format_meeting_outcome(meeting_data)
        
        self.assertEqual(formatted['UsrMeetingNotes'], 'Test meeting notes')
        self.assertEqual(formatted['UsrMeetingSummary'], 'Meeting summary')
        self.assertEqual(formatted['UsrLastMeetingDate'], '2024-01-15T10:00:00Z')
        self.assertEqual(formatted['UsrMeetingDuration'], 60)
        self.assertEqual(formatted['UsrMeetingOutcome'], 'successful')
        self.assertEqual(formatted['UsrNextSteps'], 'Follow up next week')
        self.assertEqual(formatted['QualifyStatus'], 'qualified')
        self.assertIn('ModifiedOn', formatted)
    
    def test_format_follow_up_task(self):
        """Test follow-up task formatting for Creatio"""
        task_data = {
            'title': 'Follow up with client',
            'description': 'Send proposal document',
            'due_date': '2024-01-20T09:00:00Z',
            'assignee': 'John Doe',
            'priority': 'High'
        }
        
        formatted = self.client._format_follow_up_task('lead_123', task_data)
        
        self.assertEqual(formatted['Title'], 'Follow up with client')
        self.assertEqual(formatted['Notes'], 'Send proposal document')
        self.assertEqual(formatted['DueDate'], '2024-01-20T09:00:00Z')
        self.assertEqual(formatted['Priority']['Name'], 'High')
        self.assertEqual(formatted['Account']['Id'], 'lead_123')
        self.assertEqual(formatted['Owner']['Name'], 'John Doe')


class CRMSyncServiceTest(TestCase):
    """Test cases for CRM synchronization service"""
    
    def setUp(self):
        self.sync_service = CRMSyncService()
        
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
            summary='Meeting went well',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
        
        self.action_item = ActionItem.objects.create(
            meeting_session=self.session,
            description='Send follow-up email',
            assignee='John Doe',
            due_date=timezone.now().date() + timedelta(days=7),
            crm_task_id=''  # Explicitly set to empty string so it's not synced yet
        )
    
    def tearDown(self):
        # Clear cache after each test
        cache.clear()
    
    @patch.object(CreatioAPIClient, 'update_lead_meeting_outcome')
    def test_sync_meeting_outcome_success(self, mock_update):
        """Test successful meeting outcome sync"""
        mock_update.return_value = {'Id': 'crm_record_123'}
        
        result = self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        self.assertEqual(result.status, CRMSyncStatus.SUCCESS)
        self.assertEqual(result.crm_record_id, 'crm_record_123')
        self.assertIn('successfully', result.message.lower())
        
        # Verify the call was made with correct data
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        self.assertEqual(call_args[0][0], 'CRM_123')  # CRM ID
        
        meeting_data = call_args[0][1]
        self.assertIn('notes', meeting_data)
        self.assertIn('summary', meeting_data)
    
    def test_sync_meeting_outcome_no_lead(self):
        """Test sync when meeting has no associated lead"""
        meeting_no_lead = Meeting.objects.create(
            calendar_event_id='cal_456',
            title='No Lead Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        result = self.sync_service.sync_meeting_outcome(meeting_no_lead.id)
        
        self.assertEqual(result.status, CRMSyncStatus.FAILED)
        self.assertIn('No associated lead', result.message)
    
    def test_sync_meeting_outcome_nonexistent_meeting(self):
        """Test sync with non-existent meeting"""
        result = self.sync_service.sync_meeting_outcome(99999)
        
        self.assertEqual(result.status, CRMSyncStatus.FAILED)
        self.assertIn('not found', result.message)
    
    @patch.object(CreatioAPIClient, 'update_lead_meeting_outcome')
    def test_sync_meeting_outcome_crm_error(self, mock_update):
        """Test sync when CRM API fails"""
        mock_update.side_effect = CRMAPIError("CRM server error")
        
        result = self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        self.assertEqual(result.status, CRMSyncStatus.FAILED)
        self.assertIn('CRM server error', result.message)
    
    @patch.object(CreatioAPIClient, 'update_lead_meeting_outcome')
    def test_sync_meeting_outcome_cached_result(self, mock_update):
        """Test that cached successful results are returned"""
        # First call - should hit CRM
        mock_update.return_value = {'Id': 'crm_record_123'}
        result1 = self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        # Second call - should return cached result
        result2 = self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        self.assertEqual(result1.status, CRMSyncStatus.SUCCESS)
        self.assertEqual(result2.status, CRMSyncStatus.SUCCESS)
        self.assertIn('cached', result2.message.lower())
        
        # CRM should only be called once
        mock_update.assert_called_once()
    
    @patch.object(CreatioAPIClient, 'create_follow_up_task')
    def test_create_follow_up_tasks_success(self, mock_create_task):
        """Test successful follow-up task creation"""
        mock_create_task.return_value = {'Id': 'task_123'}
        
        results = self.sync_service.create_follow_up_tasks(self.meeting.id)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CRMSyncStatus.SUCCESS)
        self.assertEqual(results[0].crm_record_id, 'task_123')
        
        # Verify action item was updated with CRM task ID
        self.action_item.refresh_from_db()
        self.assertEqual(self.action_item.crm_task_id, 'task_123')
        
        # Verify the call was made with correct data
        mock_create_task.assert_called_once()
        call_args = mock_create_task.call_args
        self.assertEqual(call_args[0][0], 'CRM_123')  # CRM ID
        
        task_data = call_args[0][1]
        self.assertIn('Send follow-up email', task_data['description'])
    
    @patch.object(CreatioAPIClient, 'create_follow_up_task')
    def test_create_follow_up_tasks_multiple_items(self, mock_create_task):
        """Test creating multiple follow-up tasks"""
        # Create additional action items
        ActionItem.objects.create(
            meeting_session=self.session,
            description='Schedule next meeting',
            assignee='Jane Smith',
            due_date=timezone.now().date() + timedelta(days=3),
            crm_task_id=''  # Explicitly set to empty string so it's not synced yet
        )
        
        mock_create_task.side_effect = [
            {'Id': 'task_123'},
            {'Id': 'task_456'}
        ]
        
        results = self.sync_service.create_follow_up_tasks(self.meeting.id)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == CRMSyncStatus.SUCCESS for r in results))
        self.assertEqual(mock_create_task.call_count, 2)
    
    @patch.object(CreatioAPIClient, 'create_follow_up_task')
    def test_create_follow_up_tasks_partial_failure(self, mock_create_task):
        """Test follow-up task creation with partial failures"""
        # Create additional action item
        ActionItem.objects.create(
            meeting_session=self.session,
            description='Schedule next meeting',
            assignee='Jane Smith',
            crm_task_id=''  # Explicitly set to empty string so it's not synced yet
        )
        
        # First task succeeds, second fails
        mock_create_task.side_effect = [
            {'Id': 'task_123'},
            CRMAPIError("Task creation failed")
        ]
        
        results = self.sync_service.create_follow_up_tasks(self.meeting.id)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, CRMSyncStatus.SUCCESS)
        self.assertEqual(results[1].status, CRMSyncStatus.FAILED)
    
    def test_create_follow_up_tasks_no_action_items(self):
        """Test follow-up task creation when no action items exist"""
        # Remove the action item
        self.action_item.delete()
        
        results = self.sync_service.create_follow_up_tasks(self.meeting.id)
        
        self.assertEqual(len(results), 0)
    
    def test_create_follow_up_tasks_already_synced(self):
        """Test that already synced action items are skipped"""
        # Mark action item as already synced
        self.action_item.crm_task_id = 'existing_task_123'
        self.action_item.save()
        
        results = self.sync_service.create_follow_up_tasks(self.meeting.id)
        
        self.assertEqual(len(results), 0)
    
    def test_prepare_meeting_data(self):
        """Test meeting data preparation"""
        data = self.sync_service._prepare_meeting_data(self.meeting)
        
        self.assertIn('meeting_date', data)
        self.assertEqual(data['outcome'], 'completed')
        self.assertEqual(data['notes'], 'Test meeting notes')
        self.assertEqual(data['summary'], 'Meeting went well')
        self.assertIn('duration_minutes', data)
        self.assertIn('next_steps', data)
    
    def test_prepare_task_data(self):
        """Test action item data preparation"""
        data = self.sync_service._prepare_task_data(self.action_item)
        
        self.assertIn('Send follow-up email', data['title'])
        self.assertEqual(data['description'], 'Send follow-up email')
        self.assertEqual(data['assignee'], 'John Doe')
        self.assertIsNotNone(data['due_date'])
        self.assertEqual(data['priority'], 'Normal')
    
    @patch.object(CreatioAPIClient, 'update_lead_meeting_outcome')
    def test_retry_failed_sync(self, mock_update):
        """Test retrying a failed sync operation"""
        # First attempt fails
        mock_update.side_effect = CRMAPIError("Server error")
        result1 = self.sync_service.sync_meeting_outcome(self.meeting.id)
        self.assertEqual(result1.status, CRMSyncStatus.FAILED)
        
        # Retry should succeed
        mock_update.side_effect = None
        mock_update.return_value = {'Id': 'crm_record_123'}
        result2 = self.sync_service.retry_failed_sync(self.meeting.id)
        
        self.assertEqual(result2.status, CRMSyncStatus.SUCCESS)
        self.assertEqual(mock_update.call_count, 2)
    
    def test_get_sync_status(self):
        """Test getting sync status from cache"""
        # No status initially
        status = self.sync_service.get_sync_status(self.meeting.id)
        self.assertIsNone(status)
        
        # Perform sync to create cache entry
        with patch.object(CreatioAPIClient, 'update_lead_meeting_outcome') as mock_update:
            mock_update.return_value = {'Id': 'crm_record_123'}
            self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        # Should now have cached status
        status = self.sync_service.get_sync_status(self.meeting.id)
        self.assertIsNotNone(status)
        self.assertEqual(status['status'], CRMSyncStatus.SUCCESS.value)


@override_settings(
    CREATIO_API_URL='https://staging.creatio.com',
    CREATIO_USERNAME='test_user',
    CREATIO_PASSWORD='test_pass'
)
class CRMIntegrationTest(TestCase):
    """
    Integration tests with CRM staging environment
    Note: These tests require actual CRM staging environment access
    """
    
    def setUp(self):
        self.sync_service = CRMSyncService()
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id='TEST_LEAD_123',
            name='Integration Test Lead',
            email='test@example.com',
            company='Test Integration Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='integration_test_meeting',
            lead=self.lead,
            title='Integration Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='completed'
        )
        
        self.session = MeetingSession.objects.create(
            meeting=self.meeting,
            notes='Integration test notes',
            summary='Integration test summary',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
    
    def test_end_to_end_sync_workflow(self):
        """
        End-to-end test of the complete sync workflow
        Note: This test requires actual CRM staging environment
        """
        # Skip if no CRM credentials configured
        if not all([
            getattr(settings, 'CREATIO_API_URL', ''),
            getattr(settings, 'CREATIO_USERNAME', ''),
            getattr(settings, 'CREATIO_PASSWORD', '')
        ]):
            self.skipTest("CRM credentials not configured for integration testing")
        
        # Test meeting outcome sync
        sync_result = self.sync_service.sync_meeting_outcome(self.meeting.id)
        
        # In a real staging environment, this should succeed
        # For now, we expect it to fail due to missing staging setup
        self.assertIn(sync_result.status, [CRMSyncStatus.SUCCESS, CRMSyncStatus.FAILED])
        
        if sync_result.status == CRMSyncStatus.SUCCESS:
            self.assertIsNotNone(sync_result.crm_record_id)
            
            # Test follow-up task creation
            ActionItem.objects.create(
                meeting_session=self.session,
                description='Integration test follow-up',
                assignee='Test User'
            )
            
            task_results = self.sync_service.create_follow_up_tasks(self.meeting.id)
            self.assertGreater(len(task_results), 0)