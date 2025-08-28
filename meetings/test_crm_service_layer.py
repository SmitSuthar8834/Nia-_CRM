"""
Unit tests for multi-CRM service layer with OAuth2 authentication
Tests Salesforce, SAP C4C, and Creatio clients with mocked responses
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
import requests

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from meetings.crm_service import (
    CRMService,
    CRMSystem,
    CRMSyncStatus,
    CRMSyncResult,
    OAuth2Token,
    SalesforceClient,
    SAPC4CClient,
    CreatioClient,
    HubSpotClient,
    CRMAuthenticationError,
    CRMAPIError,
    CRMRateLimitError
)
from meetings.models import (
    Meeting,
    CallBotSession,
    DraftSummary,
    ValidationSession,
    CRMSyncRecord
)
from leads.models import Lead


class TestOAuth2Token(unittest.TestCase):
    """Test OAuth2Token dataclass"""
    
    def test_token_creation(self):
        """Test OAuth2Token creation"""
        expires_at = timezone.now() + timedelta(hours=1)
        token = OAuth2Token(
            access_token="test_token",
            refresh_token="refresh_token",
            expires_at=expires_at,
            token_type="Bearer",
            scope="api"
        )
        
        self.assertEqual(token.access_token, "test_token")
        self.assertEqual(token.refresh_token, "refresh_token")
        self.assertEqual(token.expires_at, expires_at)
        self.assertEqual(token.token_type, "Bearer")
        self.assertEqual(token.scope, "api")


class TestSalesforceClient(unittest.TestCase):
    """Test Salesforce CRM client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = SalesforceClient()
        self.mock_token = OAuth2Token(
            access_token="sf_test_token",
            expires_at=timezone.now() + timedelta(hours=1)
        )
    
    @patch('meetings.crm_service.getattr')
    def test_get_oauth_config(self, mock_getattr):
        """Test Salesforce OAuth configuration"""
        mock_getattr.side_effect = lambda obj, key, default='': {
            'SALESFORCE_INSTANCE_URL': 'https://test.salesforce.com',
            'SALESFORCE_CLIENT_ID': 'test_client_id',
            'SALESFORCE_CLIENT_SECRET': 'test_client_secret'
        }.get(key, default)
        
        config = self.client.get_oauth_config()
        
        self.assertEqual(config['token_url'], 'https://test.salesforce.com/services/oauth2/token')
        self.assertEqual(config['client_id'], 'test_client_id')
        self.assertEqual(config['client_secret'], 'test_client_secret')
        self.assertEqual(config['scope'], 'api')
    
    def test_format_meeting_data(self):
        """Test Salesforce meeting data formatting"""
        meeting_data = {
            'title': 'Test Meeting',
            'summary': 'Meeting summary',
            'meeting_date': '2024-01-15T10:00:00Z',
            'notes': 'Meeting notes',
            'key_points': ['Point 1', 'Point 2'],
            'action_items': ['Action 1', 'Action 2'],
            'next_steps': 'Follow up next week',
            'duration_minutes': 60
        }
        
        formatted = self.client.format_meeting_data(meeting_data)
        
        self.assertEqual(formatted['Subject'], 'Meeting: Test Meeting')
        self.assertEqual(formatted['Description'], 'Meeting summary')
        self.assertEqual(formatted['ActivityDate'], '2024-01-15T10:00:00Z')
        self.assertEqual(formatted['Status'], 'Completed')
        self.assertEqual(formatted['Type'], 'Meeting')
        self.assertEqual(formatted['Meeting_Notes__c'], 'Meeting notes')
        self.assertIn('• Point 1', formatted['Key_Points__c'])
        self.assertIn('• Action 1', formatted['Action_Items__c'])
        self.assertEqual(formatted['Next_Steps__c'], 'Follow up next week')
        self.assertEqual(formatted['Meeting_Duration__c'], 60)
    
    def test_format_task_data(self):
        """Test Salesforce task data formatting"""
        task_data = {
            'title': 'Follow-up Task',
            'description': 'Task description',
            'due_date': '2024-01-20',
            'priority': 'high',
            'owner_id': 'user123'
        }
        
        formatted = self.client.format_task_data(task_data)
        
        self.assertEqual(formatted['Subject'], 'Follow-up Task')
        self.assertEqual(formatted['Description'], 'Task description')
        self.assertEqual(formatted['ActivityDate'], '2024-01-20')
        self.assertEqual(formatted['Priority'], 'High')
        self.assertEqual(formatted['Status'], 'Not Started')
        self.assertEqual(formatted['Type'], 'Task')
        self.assertEqual(formatted['OwnerId'], 'user123')
    
    @patch('meetings.crm_service.getattr')
    @patch.object(SalesforceClient, '_make_request')
    def test_update_record(self, mock_make_request, mock_getattr):
        """Test Salesforce record update"""
        mock_getattr.return_value = 'https://test.salesforce.com'
        mock_response = Mock()
        mock_make_request.return_value = mock_response
        
        data = {'Subject': 'Updated Meeting'}
        result = self.client._update_record('record123', data)
        
        mock_make_request.assert_called_once_with(
            'PATCH',
            'https://test.salesforce.com/services/data/v58.0/sobjects/Activity/record123',
            data=data
        )
        self.assertEqual(result['Id'], 'record123')
        self.assertTrue(result['success'])
    
    @patch('meetings.crm_service.getattr')
    @patch.object(SalesforceClient, '_make_request')
    def test_create_task(self, mock_make_request, mock_getattr):
        """Test Salesforce task creation"""
        mock_getattr.return_value = 'https://test.salesforce.com'
        mock_response = Mock()
        mock_response.json.return_value = {'Id': 'task123', 'success': True}
        mock_make_request.return_value = mock_response
        
        task_data = {'Subject': 'New Task'}
        result = self.client._create_task('record123', task_data)
        
        expected_data = {'Subject': 'New Task', 'WhatId': 'record123'}
        mock_make_request.assert_called_once_with(
            'POST',
            'https://test.salesforce.com/services/data/v58.0/sobjects/Task',
            data=expected_data
        )
        self.assertEqual(result['Id'], 'task123')


class TestSAPC4CClient(unittest.TestCase):
    """Test SAP C4C CRM client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = SAPC4CClient()
    
    @patch('meetings.crm_service.getattr')
    def test_get_oauth_config(self, mock_getattr):
        """Test SAP C4C OAuth configuration"""
        mock_getattr.side_effect = lambda obj, key, default='': {
            'SAP_C4C_BASE_URL': 'https://test.c4c.sap.com',
            'SAP_C4C_CLIENT_ID': 'c4c_client_id',
            'SAP_C4C_CLIENT_SECRET': 'c4c_client_secret'
        }.get(key, default)
        
        config = self.client.get_oauth_config()
        
        self.assertEqual(config['token_url'], 'https://test.c4c.sap.com/sap/bc/sec/oauth2/token')
        self.assertEqual(config['client_id'], 'c4c_client_id')
        self.assertEqual(config['client_secret'], 'c4c_client_secret')
        self.assertEqual(config['scope'], 'UIWC:CC_HOME')
    
    def test_format_meeting_data(self):
        """Test SAP C4C meeting data formatting"""
        meeting_data = {
            'title': 'C4C Meeting',
            'summary': 'C4C meeting summary',
            'meeting_date': '2024-01-15T10:00:00Z',
            'notes': 'C4C notes',
            'duration_minutes': 45,
            'next_steps': 'C4C next steps'
        }
        
        formatted = self.client.format_meeting_data(meeting_data)
        
        self.assertEqual(formatted['Subject'], 'Meeting: C4C Meeting')
        self.assertEqual(formatted['Description'], 'C4C meeting summary')
        self.assertEqual(formatted['ActivityDate'], '2024-01-15T10:00:00Z')
        self.assertEqual(formatted['ActivityType'], 'MEETING')
        self.assertEqual(formatted['Status'], 'COMPLETED')
        self.assertEqual(formatted['Notes'], 'C4C notes')
        self.assertEqual(formatted['Duration'], 45)
        self.assertEqual(formatted['NextSteps'], 'C4C next steps')
    
    def test_format_task_data(self):
        """Test SAP C4C task data formatting"""
        task_data = {
            'title': 'C4C Task',
            'description': 'C4C task description',
            'due_date': '2024-01-20',
            'priority': 'high'
        }
        
        formatted = self.client.format_task_data(task_data)
        
        self.assertEqual(formatted['Subject'], 'C4C Task')
        self.assertEqual(formatted['Description'], 'C4C task description')
        self.assertEqual(formatted['DueDate'], '2024-01-20')
        self.assertEqual(formatted['Priority'], 'HIGH')
        self.assertEqual(formatted['Status'], 'OPEN')
        self.assertEqual(formatted['ActivityType'], 'TASK')


class TestCreatioClient(unittest.TestCase):
    """Test Creatio CRM client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = CreatioClient()
    
    @patch('meetings.crm_service.getattr')
    def test_get_oauth_config(self, mock_getattr):
        """Test Creatio OAuth configuration"""
        mock_getattr.side_effect = lambda obj, key, default='': {
            'CREATIO_BASE_URI_IS': 'https://test-is.creatio.com',
            'CREATIO_CLIENT_ID': 'creatio_client_id',
            'CREATIO_CLIENT_SECRET': 'creatio_client_secret'
        }.get(key, default)
        
        config = self.client.get_oauth_config()
        
        self.assertEqual(config['token_url'], 'https://test-is.creatio.com/connect/token')
        self.assertEqual(config['client_id'], 'creatio_client_id')
        self.assertEqual(config['client_secret'], 'creatio_client_secret')
        self.assertEqual(config['scope'], 'api')
    
    def test_format_meeting_data(self):
        """Test Creatio meeting data formatting"""
        meeting_data = {
            'summary': 'Creatio meeting summary',
            'meeting_date': '2024-01-15T10:00:00Z',
            'notes': 'Creatio notes',
            'duration_minutes': 30,
            'outcome': 'successful',
            'next_steps': 'Creatio next steps'
        }
        
        formatted = self.client.format_meeting_data(meeting_data)
        
        self.assertEqual(formatted['UsrMeetingSummary'], 'Creatio meeting summary')
        self.assertEqual(formatted['UsrLastMeetingDate'], '2024-01-15T10:00:00Z')
        self.assertEqual(formatted['UsrMeetingNotes'], 'Creatio notes')
        self.assertEqual(formatted['UsrMeetingDuration'], 30)
        self.assertEqual(formatted['UsrMeetingOutcome'], 'successful')
        self.assertEqual(formatted['UsrNextSteps'], 'Creatio next steps')
        self.assertIn('ModifiedOn', formatted)
    
    def test_format_task_data(self):
        """Test Creatio task data formatting"""
        task_data = {
            'title': 'Creatio Task',
            'description': 'Creatio task description',
            'due_date': '2024-01-20',
            'priority': 'High'
        }
        
        formatted = self.client.format_task_data(task_data)
        
        self.assertEqual(formatted['Title'], 'Creatio Task')
        self.assertEqual(formatted['Notes'], 'Creatio task description')
        self.assertEqual(formatted['DueDate'], '2024-01-20')
        self.assertEqual(formatted['Priority']['Name'], 'High')
        self.assertEqual(formatted['Status']['Name'], 'Not started')
        self.assertEqual(formatted['Type']['Name'], 'Task')
        self.assertIn('StartDate', formatted)
    
    @patch('meetings.crm_service.getattr')
    def test_authenticate(self, mock_getattr):
        """Test Creatio OAuth2 authentication"""
        mock_getattr.side_effect = lambda obj, key, default='': {
            'CREATIO_BASE_URI_IS': 'https://test-is.creatio.com',
            'CREATIO_CLIENT_ID': 'creatio_client_id',
            'CREATIO_CLIENT_SECRET': 'creatio_client_secret'
        }.get(key, default)
        
        with patch.object(self.client.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                'access_token': 'creatio_access_token',
                'token_type': 'Bearer',
                'expires_in': 3600
            }
            mock_post.return_value = mock_response
            
            result = self.client._authenticate()
            
            self.assertTrue(result)
            self.assertIsNotNone(self.client.token)
            self.assertEqual(self.client.token.access_token, "creatio_access_token")
            self.assertEqual(self.client.token.token_type, "Bearer")
            
            mock_post.assert_called_once_with(
                'https://test-is.creatio.com/connect/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': 'creatio_client_id',
                    'client_secret': 'creatio_client_secret'
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )


class TestHubSpotClient(unittest.TestCase):
    """Test HubSpot CRM client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = HubSpotClient()
    
    @patch('meetings.crm_service.getattr')
    def test_get_oauth_config(self, mock_getattr):
        """Test HubSpot OAuth configuration"""
        mock_getattr.side_effect = lambda obj, key, default='': {
            'HUBSPOT_CLIENT_ID': 'hubspot_client_id',
            'HUBSPOT_CLIENT_SECRET': 'hubspot_client_secret'
        }.get(key, default)
        
        config = self.client.get_oauth_config()
        
        self.assertEqual(config['token_url'], 'https://api.hubapi.com/oauth/v1/token')
        self.assertEqual(config['client_id'], 'hubspot_client_id')
        self.assertEqual(config['client_secret'], 'hubspot_client_secret')
        self.assertEqual(config['scope'], 'contacts crm.objects.contacts.write crm.objects.deals.write')
    
    def test_format_meeting_data(self):
        """Test HubSpot meeting data formatting"""
        meeting_data = {
            'title': 'HubSpot Meeting',
            'summary': 'HubSpot meeting summary',
            'meeting_date': '2024-01-15T10:00:00Z',
            'meeting_end_date': '2024-01-15T11:00:00Z',
            'notes': 'HubSpot notes',
            'owner_id': 'owner123'
        }
        
        formatted = self.client.format_meeting_data(meeting_data)
        
        self.assertEqual(formatted['hs_meeting_title'], 'Meeting: HubSpot Meeting')
        self.assertEqual(formatted['hs_meeting_body'], 'HubSpot meeting summary')
        self.assertEqual(formatted['hs_meeting_start_time'], '2024-01-15T10:00:00Z')
        self.assertEqual(formatted['hs_meeting_end_time'], '2024-01-15T11:00:00Z')
        self.assertEqual(formatted['hs_meeting_outcome'], 'COMPLETED')
        self.assertEqual(formatted['hs_meeting_notes'], 'HubSpot notes')
        self.assertEqual(formatted['hubspot_owner_id'], 'owner123')
        self.assertEqual(formatted['hs_activity_type'], 'MEETING')
    
    def test_format_task_data(self):
        """Test HubSpot task data formatting"""
        task_data = {
            'title': 'HubSpot Task',
            'description': 'HubSpot task description',
            'due_date': '2024-01-20',
            'priority': 'high',
            'owner_id': 'owner123'
        }
        
        formatted = self.client.format_task_data(task_data)
        
        self.assertEqual(formatted['hs_task_subject'], 'HubSpot Task')
        self.assertEqual(formatted['hs_task_body'], 'HubSpot task description')
        self.assertEqual(formatted['hs_task_status'], 'NOT_STARTED')
        self.assertEqual(formatted['hs_task_priority'], 'HIGH')
        self.assertEqual(formatted['hs_task_type'], 'TODO')
        self.assertEqual(formatted['hs_timestamp'], '2024-01-20')
        self.assertEqual(formatted['hubspot_owner_id'], 'owner123')
    
    @patch.object(HubSpotClient, '_make_request')
    def test_update_record(self, mock_make_request):
        """Test HubSpot record update"""
        mock_response = Mock()
        mock_response.json.return_value = {'id': 'hubspot123', 'properties': {}}
        mock_make_request.return_value = mock_response
        
        data = {'hs_meeting_title': 'Updated Meeting'}
        result = self.client._update_record('record123', data)
        
        expected_data = {'properties': data}
        mock_make_request.assert_called_once_with(
            'PATCH',
            'https://api.hubapi.com/crm/v3/objects/contacts/record123',
            data=expected_data
        )
        self.assertEqual(result['id'], 'hubspot123')
    
    @patch.object(HubSpotClient, '_make_request')
    def test_create_task(self, mock_make_request):
        """Test HubSpot task creation"""
        mock_response = Mock()
        mock_response.json.return_value = {'id': 'task123', 'properties': {}}
        mock_make_request.return_value = mock_response
        
        task_data = {'hs_task_subject': 'New Task'}
        result = self.client._create_task('record123', task_data)
        
        expected_data = {
            'properties': task_data,
            'associations': [
                {
                    'to': {'id': 'record123'},
                    'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]
                }
            ]
        }
        mock_make_request.assert_called_once_with(
            'POST',
            'https://api.hubapi.com/crm/v3/objects/tasks',
            data=expected_data
        )
        self.assertEqual(result['id'], 'task123')


class TestCRMServiceIntegration(TestCase):
    """Integration tests for CRMService with database models"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crm_service = CRMService()
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id='lead123',
            name='Test Lead',
            email='test@example.com',
            company='Test Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='event123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id='bot123',
            platform='meet',
            join_time=timezone.now()
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary='Test summary',
            confidence_score=0.9
        )
        
        self.validation_session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email='rep@example.com',
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validated_summary='Validated summary',
            rep_responses={
                'meeting_notes': 'Validated notes',
                'key_points': ['Point 1', 'Point 2'],
                'action_items': [
                    {'title': 'Task 1', 'description': 'Do task 1', 'assignee': 'rep@example.com'}
                ],
                'next_steps': 'Follow up next week'
            },
            approved_crm_updates={
                'approved': True,
                'action_items': [
                    {'title': 'Task 1', 'description': 'Do task 1', 'assignee': 'rep@example.com'}
                ]
            }
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_get_client(self):
        """Test getting CRM clients"""
        sf_client = self.crm_service.get_client(CRMSystem.SALESFORCE)
        self.assertIsInstance(sf_client, SalesforceClient)
        
        c4c_client = self.crm_service.get_client('sap_c4c')
        self.assertIsInstance(c4c_client, SAPC4CClient)
        
        creatio_client = self.crm_service.get_client(CRMSystem.CREATIO)
        self.assertIsInstance(creatio_client, CreatioClient)
        
        hubspot_client = self.crm_service.get_client(CRMSystem.HUBSPOT)
        self.assertIsInstance(hubspot_client, HubSpotClient)
        
        with self.assertRaises(ValueError):
            self.crm_service.get_client('invalid_crm')
    
    @patch.object(SalesforceClient, 'update_meeting_outcome')
    def test_sync_meeting_outcome_success(self, mock_update):
        """Test successful meeting outcome sync"""
        mock_update.return_value = {'Id': 'sf_record123'}
        
        result = self.crm_service.sync_meeting_outcome(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertEqual(result.status, CRMSyncStatus.SUCCESS)
        self.assertEqual(result.crm_record_id, 'sf_record123')
        
        # Check CRM sync record was created
        sync_record = CRMSyncRecord.objects.get(
            validation_session=self.validation_session,
            crm_system='salesforce'
        )
        self.assertEqual(sync_record.sync_status, 'completed')
        self.assertEqual(sync_record.crm_record_id, 'sf_record123')
    
    def test_sync_meeting_outcome_no_lead(self):
        """Test sync failure when no lead is associated"""
        self.meeting.lead = None
        self.meeting.save()
        
        result = self.crm_service.sync_meeting_outcome(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertEqual(result.status, CRMSyncStatus.FAILED)
        self.assertIn("No associated lead", result.message)
    
    @patch.object(SalesforceClient, 'update_meeting_outcome')
    def test_sync_meeting_outcome_crm_error(self, mock_update):
        """Test sync failure due to CRM API error"""
        mock_update.side_effect = CRMAPIError("API connection failed")
        
        result = self.crm_service.sync_meeting_outcome(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertEqual(result.status, CRMSyncStatus.FAILED)
        self.assertIn("API connection failed", result.message)
    
    @patch.object(SalesforceClient, 'create_follow_up_task')
    def test_create_follow_up_tasks_success(self, mock_create_task):
        """Test successful follow-up task creation"""
        mock_create_task.return_value = {'Id': 'task123'}
        
        results = self.crm_service.create_follow_up_tasks(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, CRMSyncStatus.SUCCESS)
        self.assertEqual(results[0].crm_record_id, 'task123')
    
    def test_sync_to_multiple_crms(self):
        """Test syncing to multiple CRM systems"""
        with patch.object(SalesforceClient, 'update_meeting_outcome') as mock_sf, \
             patch.object(CreatioClient, 'update_meeting_outcome') as mock_creatio:
            
            mock_sf.return_value = {'Id': 'sf123'}
            mock_creatio.return_value = {'Id': 'creatio123'}
            
            results = self.crm_service.sync_to_multiple_crms(
                self.validation_session.id,
                [CRMSystem.SALESFORCE, CRMSystem.CREATIO]
            )
            
            self.assertEqual(len(results), 2)
            self.assertEqual(results['salesforce'].status, CRMSyncStatus.SUCCESS)
            self.assertEqual(results['creatio'].status, CRMSyncStatus.SUCCESS)
    
    def test_get_sync_status(self):
        """Test getting sync status"""
        # Create sync record
        CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='sf123',
            synced_at=timezone.now()
        )
        
        status = self.crm_service.get_sync_status(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(status)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['crm_record_id'], 'sf123')
    
    def test_test_connection(self):
        """Test CRM connection testing"""
        with patch.object(SalesforceClient, '_ensure_authenticated') as mock_auth:
            mock_auth.return_value = True
            
            result = self.crm_service.test_connection(CRMSystem.SALESFORCE)
            self.assertTrue(result)
            
            mock_auth.return_value = False
            result = self.crm_service.test_connection(CRMSystem.SALESFORCE)
            self.assertFalse(result)
    
    def test_prepare_meeting_data_from_validation(self):
        """Test preparing meeting data from validation session"""
        data = self.crm_service._prepare_meeting_data_from_validation(self.validation_session)
        
        self.assertEqual(data['title'], 'Test Meeting')
        self.assertEqual(data['summary'], 'Validated summary')
        self.assertEqual(data['outcome'], 'completed')
        self.assertEqual(data['notes'], 'Validated notes')
        self.assertEqual(data['key_points'], ['Point 1', 'Point 2'])
        self.assertEqual(data['next_steps'], 'Follow up next week')
    
    def test_prepare_task_data_from_validation(self):
        """Test preparing task data from validation"""
        action_item = {
            'title': 'Follow up',
            'description': 'Follow up with client',
            'due_date': '2024-01-20',
            'assignee': 'rep@example.com',
            'priority': 'High'
        }
        
        data = self.crm_service._prepare_task_data_from_validation(action_item)
        
        self.assertEqual(data['title'], 'Follow up')
        self.assertEqual(data['description'], 'Follow up with client')
        self.assertEqual(data['due_date'], '2024-01-20')
        self.assertEqual(data['assignee'], 'rep@example.com')
        self.assertEqual(data['priority'], 'High')


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = SalesforceClient()
        self.client.requests_per_minute = 2  # Low limit for testing
    
    def test_rate_limiting(self):
        """Test rate limiting enforcement"""
        import time
        
        # Make requests up to the limit
        self.client._check_rate_limit()
        self.client._check_rate_limit()
        
        # Next request should be delayed
        start_time = time.time()
        self.client._check_rate_limit()
        end_time = time.time()
        
        # Should have been delayed (allowing for some timing variance)
        self.assertGreater(end_time - start_time, 0.05)


class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = SalesforceClient()
    
    @patch('requests.Session')
    def test_authentication_error_handling(self, mock_session_class):
        """Test authentication error handling"""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.RequestException("Auth failed")
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        with self.assertRaises(CRMAuthenticationError):
            self.client._authenticate()
    
    @patch.object(SalesforceClient, '_ensure_authenticated')
    def test_api_error_retry_logic(self, mock_auth):
        """Test API error retry logic"""
        mock_auth.return_value = True
        
        # Set up a mock token
        self.client.token = OAuth2Token(
            access_token="test_token",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Mock failed requests
        with patch.object(self.client.session, 'request') as mock_request:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.RequestException("Connection error")
            mock_request.return_value = mock_response
            
            with self.assertRaises(CRMAPIError):
                self.client._make_request('GET', 'https://test.com/api')
            
            # Should have retried max_retries + 1 times
            self.assertEqual(mock_request.call_count, self.client.max_retries + 1)
    
    @patch.object(SalesforceClient, '_ensure_authenticated')
    def test_rate_limit_error_handling(self, mock_auth):
        """Test rate limit error handling"""
        mock_auth.return_value = True
        
        # Set up a mock token
        self.client.token = OAuth2Token(
            access_token="test_token",
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        # Mock rate limit response
        with patch.object(self.client.session, 'request') as mock_request:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.headers = {'Retry-After': '1'}
            mock_request.return_value = mock_response
            
            # Should handle rate limiting gracefully
            with patch('time.sleep') as mock_sleep:
                try:
                    self.client._make_request('GET', 'https://test.com/api')
                except CRMAPIError:
                    pass  # Expected after retries
                
                # Should have slept for retry-after duration
                mock_sleep.assert_called()


if __name__ == '__main__':
    unittest.main()