"""
Comprehensive tests for Creatio CRM integration
"""
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status

from .adapters import CreatioAdapter, CreatioAuthenticationError, CreatioSyncError
from .models import CreatioSync, SyncConflict, SyncLog, CreatioConfiguration
from .services import CRMSyncService
from apps.leads.models import Lead
from apps.meetings.models import Meeting
from apps.accounts.models import UserProfile


class MockCreatioResponse:
    """Mock response for Creatio API calls"""
    
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@override_settings(
    CREATIO_API_URL='https://test-creatio.com',
    CREATIO_CLIENT_ID='test_client_id',
    CREATIO_CLIENT_SECRET='test_client_secret'
)
class CreatioAdapterTestCase(TestCase):
    """Test cases for CreatioAdapter"""
    
    def setUp(self):
        self.adapter = CreatioAdapter()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test lead
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            phone='+1234567890',
            status='new',
            source='meeting'
        )
        
        # Clear cache before each test
        cache.clear()
    
    def tearDown(self):
        cache.clear()
    
    @patch('apps.crm_sync.adapters.requests.post')
    def test_authenticate_success(self, mock_post):
        """Test successful OAuth 2.0 authentication"""
        mock_response = MockCreatioResponse({
            'access_token': 'test_access_token',
            'expires_in': 3600,
            'refresh_token': 'test_refresh_token'
        })
        mock_post.return_value = mock_response
        
        token = self.adapter.authenticate()
        
        self.assertEqual(token, 'test_access_token')
        self.assertEqual(cache.get('creatio_access_token'), 'test_access_token')
        self.assertEqual(cache.get('creatio_refresh_token'), 'test_refresh_token')
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('grant_type', call_args[1]['data'])
        self.assertEqual(call_args[1]['data']['grant_type'], 'client_credentials')
    
    @patch('apps.crm_sync.adapters.requests.post')
    def test_authenticate_failure(self, mock_post):
        """Test authentication failure"""
        mock_post.side_effect = Exception("Connection failed")
        
        with self.assertRaises(CreatioAuthenticationError):
            self.adapter.authenticate()
    
    @patch('apps.crm_sync.adapters.requests.post')
    def test_refresh_token_success(self, mock_post):
        """Test successful token refresh"""
        # Set existing refresh token
        cache.set('creatio_refresh_token', 'existing_refresh_token')
        
        mock_response = MockCreatioResponse({
            'access_token': 'new_access_token',
            'expires_in': 3600
        })
        mock_post.return_value = mock_response
        
        token = self.adapter._refresh_access_token('existing_refresh_token')
        
        self.assertEqual(token, 'new_access_token')
        self.assertEqual(cache.get('creatio_access_token'), 'new_access_token')
    
    def test_convert_lead_to_creatio(self):
        """Test lead conversion to Creatio format"""
        creatio_data = self.adapter._convert_lead_to_creatio(self.lead)
        
        expected_fields = {
            'Name': 'John',
            'Surname': 'Doe',
            'Email': 'john.doe@example.com',
            'AccountName': 'Test Company',
            'MobilePhone': '+1234567890',
            'QualifyStatus': 'New'
        }
        
        for creatio_field, expected_value in expected_fields.items():
            self.assertEqual(creatio_data[creatio_field], expected_value)
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_sync_local_leads_to_creatio_create(self, mock_request):
        """Test syncing new lead to Creatio"""
        mock_response = MockCreatioResponse({
            'Id': 'creatio-lead-id-123'
        })
        mock_request.return_value = mock_response
        
        result = self.adapter._sync_local_leads_to_creatio()
        
        self.assertEqual(result['created_count'], 1)
        self.assertEqual(result['synced_count'], 1)
        
        # Verify lead was updated with Creatio ID
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.creatio_id, 'creatio-lead-id-123')
        
        # Verify sync record was created
        sync_record = CreatioSync.objects.get(entity_type='lead', local_id=self.lead.id)
        self.assertEqual(sync_record.sync_status, 'success')
        self.assertEqual(sync_record.creatio_id, 'creatio-lead-id-123')
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_sync_local_leads_to_creatio_update(self, mock_request):
        """Test syncing existing lead to Creatio"""
        # Set existing Creatio ID
        self.lead.creatio_id = 'existing-creatio-id'
        self.lead.save()
        
        mock_response = MockCreatioResponse({})
        mock_request.return_value = mock_response
        
        result = self.adapter._sync_local_leads_to_creatio()
        
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(result['synced_count'], 1)
        
        # Verify PATCH request was made
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], 'PATCH')  # HTTP method
        self.assertIn('existing-creatio-id', call_args[0][1])  # URL contains ID
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_sync_creatio_leads_to_local(self, mock_request):
        """Test syncing leads from Creatio to local"""
        mock_response = MockCreatioResponse({
            'value': [
                {
                    'Id': 'creatio-lead-123',
                    'Name': 'Jane',
                    'Surname': 'Smith',
                    'Email': 'jane.smith@example.com',
                    'AccountName': 'Smith Corp',
                    'QualifyStatus': 'Qualified'
                }
            ]
        })
        mock_request.return_value = mock_response
        
        result = self.adapter._sync_creatio_leads_to_local()
        
        self.assertEqual(result['created_count'], 1)
        self.assertEqual(result['synced_count'], 1)
        
        # Verify lead was created
        new_lead = Lead.objects.get(creatio_id='creatio-lead-123')
        self.assertEqual(new_lead.first_name, 'Jane')
        self.assertEqual(new_lead.last_name, 'Smith')
        self.assertEqual(new_lead.email, 'jane.smith@example.com')
        self.assertEqual(new_lead.status, 'qualified')
    
    def test_detect_conflicts(self):
        """Test conflict detection between local and Creatio data"""
        # Create sync record with conflict
        sync_record = CreatioSync.objects.create(
            entity_type='lead',
            local_id=self.lead.id,
            creatio_id='creatio-lead-123',
            sync_status='conflict'
        )
        
        creatio_data = {
            'Name': 'John',
            'Surname': 'Doe',
            'Email': 'john.doe@different.com',  # Different email
            'AccountName': 'Different Company'  # Different company
        }
        
        conflicts = self.adapter._compare_lead_data(self.lead, creatio_data)
        
        self.assertIn('email', conflicts)
        self.assertIn('company', conflicts)
        self.assertEqual(conflicts['email']['local'], 'john.doe@example.com')
        self.assertEqual(conflicts['email']['creatio'], 'john.doe@different.com')
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_update_lead_from_meeting(self, mock_request):
        """Test updating lead with meeting-derived data"""
        meeting_data = {
            'qualification_insights': {
                'budget_discussed': True,
                'timeline_discussed': True,
                'decision_maker_identified': True
            },
            'meeting_type': 'demo',
            'estimated_budget': 50000,
            'estimated_close_date': '2024-12-31'
        }
        
        success = self.adapter.update_lead_from_meeting(str(self.lead.id), meeting_data)
        
        self.assertTrue(success)
        
        # Verify lead was updated
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.qualification_score, 35)  # 10 + 10 + 15
        self.assertEqual(self.lead.relationship_stage, 'hot')
        self.assertEqual(self.lead.estimated_budget, 50000)
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_create_activity_for_meeting(self, mock_request):
        """Test creating activity in Creatio for meeting"""
        meeting = Meeting.objects.create(
            calendar_event_id='cal-event-123',
            title='Sales Demo',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            meeting_type='demo',
            organizer=self.user,
            is_sales_meeting=True
        )
        
        mock_response = MockCreatioResponse({
            'Id': 'activity-123'
        })
        mock_request.return_value = mock_response
        
        success = self.adapter.create_activity_for_meeting(meeting)
        
        self.assertTrue(success)
        
        # Verify sync record was created
        sync_record = CreatioSync.objects.get(
            entity_type='activity',
            local_id=meeting.id
        )
        self.assertEqual(sync_record.creatio_id, 'activity-123')
        self.assertEqual(sync_record.sync_status, 'success')
    
    def test_resolve_conflict_local_wins(self):
        """Test resolving conflict with local value winning"""
        sync_record = CreatioSync.objects.create(
            entity_type='lead',
            local_id=self.lead.id,
            creatio_id='creatio-lead-123',
            sync_status='conflict'
        )
        
        conflict = SyncConflict.objects.create(
            sync_record=sync_record,
            conflict_type='data_mismatch',
            field_name='email',
            local_value='john.doe@example.com',
            creatio_value='john.doe@different.com'
        )
        
        success = self.adapter.resolve_conflict(str(conflict.id), 'local_wins', self.user)
        
        self.assertTrue(success)
        
        conflict.refresh_from_db()
        self.assertEqual(conflict.resolution_status, 'resolved_local')
        self.assertEqual(conflict.resolved_by, self.user)
        
        # Verify sync record is marked for retry
        sync_record.refresh_from_db()
        self.assertEqual(sync_record.sync_status, 'pending')


class CRMSyncServiceTestCase(TestCase):
    """Test cases for CRMSyncService"""
    
    def setUp(self):
        self.service = CRMSyncService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new'
        )
    
    @patch('apps.crm_sync.services.CreatioAdapter.sync_leads_bidirectional')
    def test_sync_all_leads_success(self, mock_sync):
        """Test successful sync of all leads"""
        mock_sync.return_value = {
            'leads_synced_to_creatio': 5,
            'leads_synced_from_creatio': 3,
            'conflicts_detected': 1,
            'errors': []
        }
        
        result = self.service.sync_all_leads()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['result']['leads_synced_to_creatio'], 5)
        
        # Verify log was created
        log = SyncLog.objects.filter(operation_type='sync').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.log_level, 'info')
    
    @patch('apps.crm_sync.services.CreatioAdapter.sync_leads_bidirectional')
    def test_sync_all_leads_failure(self, mock_sync):
        """Test sync failure handling"""
        mock_sync.side_effect = CreatioSyncError("Connection failed")
        
        result = self.service.sync_all_leads()
        
        self.assertFalse(result['success'])
        self.assertIn('Connection failed', result['error'])
        
        # Verify error log was created
        log = SyncLog.objects.filter(log_level='error').first()
        self.assertIsNotNone(log)
    
    def test_get_pending_conflicts(self):
        """Test getting pending conflicts"""
        sync_record = CreatioSync.objects.create(
            entity_type='lead',
            local_id=self.lead.id,
            sync_status='conflict'
        )
        
        conflict = SyncConflict.objects.create(
            sync_record=sync_record,
            conflict_type='data_mismatch',
            field_name='email',
            local_value='local@example.com',
            creatio_value='creatio@example.com',
            resolution_status='pending'
        )
        
        conflicts = self.service.get_pending_conflicts()
        
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['id'], str(conflict.id))
        self.assertEqual(conflicts[0]['field_name'], 'email')


class CRMSyncAPITestCase(APITestCase):
    """Test cases for CRM Sync API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create user profile with appropriate role
        UserProfile.objects.create(
            user=self.user,
            role='sales_manager'
        )
        
        self.client.force_authenticate(user=self.user)
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new'
        )
    
    @patch('apps.crm_sync.services.sync_all_leads_task.delay')
    def test_sync_all_async(self, mock_task):
        """Test async sync all leads endpoint"""
        mock_task.return_value = Mock(id='task-123')
        
        response = self.client.post('/api/v1/crm/sync/sync_all/', {
            'async': True,
            'force': False
        })
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'task-123')
        self.assertTrue(response.data['async'])
        
        mock_task.assert_called_once_with(force=False)
    
    @patch('apps.crm_sync.services.CRMSyncService.sync_all_leads')
    def test_sync_all_sync(self, mock_sync):
        """Test synchronous sync all leads endpoint"""
        mock_sync.return_value = {
            'success': True,
            'result': {'leads_synced_to_creatio': 5}
        }
        
        response = self.client.post('/api/v1/crm/sync/sync_all/', {
            'async': False
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    @patch('apps.crm_sync.services.sync_lead_to_creatio.delay')
    def test_sync_lead_async(self, mock_task):
        """Test async sync single lead endpoint"""
        mock_task.return_value = Mock(id='task-456')
        
        response = self.client.post('/api/v1/crm/sync/sync-lead/', {
            'lead_id': str(self.lead.id),
            'direction': 'to_creatio',
            'async': True
        })
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'task-456')
        
        mock_task.assert_called_once_with(str(self.lead.id))
    
    def test_sync_lead_invalid_direction(self):
        """Test sync lead with invalid direction"""
        response = self.client.post('/api/v1/crm/sync/sync-lead/', {
            'lead_id': str(self.lead.id),
            'direction': 'invalid_direction'
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid direction', response.data['error'])
    
    @patch('apps.crm_sync.services.CRMSyncService.get_sync_status')
    def test_sync_status(self, mock_status):
        """Test sync status endpoint"""
        mock_status.return_value = {
            'sync_status': {'success': 10, 'pending': 2},
            'conflicts': {'pending': 1},
            'last_sync': None
        }
        
        response = self.client.get('/api/v1/crm/sync/status/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sync_status']['success'], 10)
    
    def test_resolve_conflict(self):
        """Test conflict resolution endpoint"""
        sync_record = CreatioSync.objects.create(
            entity_type='lead',
            local_id=self.lead.id,
            sync_status='conflict'
        )
        
        conflict = SyncConflict.objects.create(
            sync_record=sync_record,
            conflict_type='data_mismatch',
            field_name='email',
            local_value='local@example.com',
            creatio_value='creatio@example.com'
        )
        
        with patch('apps.crm_sync.services.CRMSyncService.resolve_sync_conflict') as mock_resolve:
            mock_resolve.return_value = {'success': True}
            
            response = self.client.post('/api/v1/crm/sync/resolve-conflict/', {
                'conflict_id': str(conflict.id),
                'resolution': 'local_wins'
            })
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])
    
    def test_create_meeting_activity(self):
        """Test create meeting activity endpoint"""
        meeting = Meeting.objects.create(
            calendar_event_id='cal-123',
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            organizer=self.user
        )
        
        with patch('apps.crm_sync.services.CRMSyncService.create_meeting_activity') as mock_create:
            mock_create.return_value = {'success': True}
            
            response = self.client.post('/api/v1/crm/sync/create-activity/', {
                'meeting_id': str(meeting.id)
            })
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data['success'])


class CreatioConfigurationTestCase(TestCase):
    """Test cases for Creatio configuration management"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
    
    def test_field_mapping_configuration(self):
        """Test field mapping configuration"""
        config = CreatioConfiguration.objects.create(
            config_type='field_mapping',
            config_key='lead_field_mapping',
            config_value={
                'first_name': 'Name',
                'last_name': 'Surname',
                'email': 'Email'
            },
            created_by=self.user
        )
        
        self.assertEqual(config.config_type, 'field_mapping')
        self.assertIn('first_name', config.config_value)
    
    def test_adapter_uses_custom_mapping(self):
        """Test that adapter uses custom field mapping"""
        # Create custom mapping
        CreatioConfiguration.objects.create(
            config_type='field_mapping',
            config_key='lead_field_mapping',
            config_value={
                'first_name': 'CustomName',
                'last_name': 'CustomSurname'
            },
            created_by=self.user,
            is_active=True
        )
        
        adapter = CreatioAdapter()
        mapping = adapter._get_lead_field_mapping()
        
        self.assertEqual(mapping['first_name'], 'CustomName')
        self.assertEqual(mapping['last_name'], 'CustomSurname')


class SyncLogTestCase(TestCase):
    """Test cases for sync logging functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company'
        )
    
    def test_sync_log_creation(self):
        """Test sync log creation"""
        sync_record = CreatioSync.objects.create(
            entity_type='lead',
            local_id=self.lead.id,
            sync_status='success'
        )
        
        log = SyncLog.objects.create(
            sync_record=sync_record,
            log_level='info',
            operation_type='sync',
            message='Lead synced successfully',
            entity_type='lead',
            entity_id=str(self.lead.id),
            user=self.user
        )
        
        self.assertEqual(log.log_level, 'info')
        self.assertEqual(log.operation_type, 'sync')
        self.assertEqual(log.sync_record, sync_record)
    
    def test_log_filtering_by_level(self):
        """Test filtering logs by level"""
        SyncLog.objects.create(
            log_level='info',
            operation_type='sync',
            message='Info message'
        )
        
        SyncLog.objects.create(
            log_level='error',
            operation_type='sync',
            message='Error message'
        )
        
        info_logs = SyncLog.objects.filter(log_level='info')
        error_logs = SyncLog.objects.filter(log_level='error')
        
        self.assertEqual(info_logs.count(), 1)
        self.assertEqual(error_logs.count(), 1)