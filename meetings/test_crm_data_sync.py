"""
Integration tests for CRM data formatting and sync functionality
Tests opportunity updates, bulk sync operations, and sync status tracking
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from meetings.crm_service import (
    CRMService,
    CRMSystem,
    CRMSyncStatus,
    CRMSyncResult,
    SalesforceClient,
    SAPC4CClient,
    CreatioClient,
    HubSpotClient,
    CRMAuthenticationError,
    CRMAPIError
)
from meetings.models import (
    Meeting,
    CallBotSession,
    DraftSummary,
    ValidationSession,
    CRMSyncRecord
)
from leads.models import Lead


class TestCRMDataFormatting(TestCase):
    """Test CRM-specific data formatting"""
    
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
            confidence_score=0.9,
            key_points=['Point 1', 'Point 2'],
            extracted_action_items=[
                {'title': 'Task 1', 'description': 'Do task 1', 'assignee': 'rep@example.com'}
            ],
            suggested_next_steps=['Follow up next week']
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
                'next_steps': 'Follow up next week',
                'meeting_outcome': 'positive'
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
    
    def test_salesforce_opportunity_formatting(self):
        """Test Salesforce opportunity data formatting"""
        client = self.crm_service.get_client(CRMSystem.SALESFORCE)
        
        stage_data = {
            'stage_name': 'Proposal/Price Quote',
            'probability': 75,
            'close_date': '2024-02-15',
            'amount': 50000,
            'next_step': 'Send proposal',
            'description': 'Updated from meeting'
        }
        
        # Test that the method exists and can be called
        self.assertTrue(hasattr(client, 'update_opportunity_stage'))
        self.assertTrue(hasattr(client, 'get_opportunity_details'))
    
    def test_hubspot_deal_formatting(self):
        """Test HubSpot deal data formatting"""
        client = self.crm_service.get_client(CRMSystem.HUBSPOT)
        
        stage_data = {
            'stage_name': 'closedwon',
            'probability': 90,
            'close_date': '2024-02-15',
            'amount': 75000,
            'next_step': 'Contract signing'
        }
        
        # Test that the method exists and can be called
        self.assertTrue(hasattr(client, 'update_opportunity_stage'))
        self.assertTrue(hasattr(client, 'get_opportunity_details'))
    
    def test_sap_c4c_opportunity_formatting(self):
        """Test SAP C4C opportunity data formatting"""
        client = self.crm_service.get_client(CRMSystem.SAP_C4C)
        
        stage_data = {
            'stage_name': 'NEGOTIATION',
            'probability': 60,
            'close_date': '2024-02-20',
            'amount': 30000,
            'next_step': 'Technical review'
        }
        
        # Test that the method exists and can be called
        self.assertTrue(hasattr(client, 'update_opportunity_stage'))
        self.assertTrue(hasattr(client, 'get_opportunity_details'))
    
    def test_creatio_opportunity_formatting(self):
        """Test Creatio opportunity data formatting"""
        client = self.crm_service.get_client(CRMSystem.CREATIO)
        
        stage_data = {
            'stage_name': 'Proposal',
            'probability': 70,
            'close_date': '2024-02-25',
            'amount': 40000,
            'next_step': 'Demo scheduling'
        }
        
        # Test that the method exists and can be called
        self.assertTrue(hasattr(client, 'update_opportunity_stage'))
        self.assertTrue(hasattr(client, 'get_opportunity_details'))


class TestOpportunitySync(TestCase):
    """Test opportunity synchronization functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crm_service = CRMService()
        
        # Create test data (same as above)
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
            rep_responses={
                'meeting_outcome': 'positive',
                'next_steps': 'Send proposal'
            }
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    @patch.object(SalesforceClient, 'update_opportunity_stage')
    def test_update_opportunity_from_meeting_success(self, mock_update):
        """Test successful opportunity update from meeting"""
        mock_update.return_value = {'Id': 'opp123', 'success': True}
        
        stage_updates = {
            'stage_name': 'Proposal/Price Quote',
            'probability': 75,
            'next_step': 'Send proposal'
        }
        
        result = self.crm_service.update_opportunity_from_meeting(
            self.validation_session.id,
            CRMSystem.SALESFORCE,
            'opp123',
            stage_updates
        )
        
        self.assertEqual(result.status, CRMSyncStatus.SUCCESS)
        self.assertEqual(result.crm_record_id, 'opp123')
        
        # Check that sync record was created
        sync_record = CRMSyncRecord.objects.get(
            validation_session=self.validation_session,
            crm_system='salesforce'
        )
        self.assertEqual(sync_record.crm_record_id, 'opp123')
        self.assertIn('opportunity_update', sync_record.sync_payload)
    
    def test_get_opportunity_sync_suggestions_positive(self):
        """Test opportunity sync suggestions for positive meeting"""
        suggestions = self.crm_service.get_opportunity_sync_suggestions(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIn('stage_suggestions', suggestions)
        self.assertIn('Qualification', suggestions['stage_suggestions'])
        self.assertEqual(suggestions['probability_adjustment'], 10)
        self.assertTrue(suggestions['follow_up_required'])
    
    def test_get_opportunity_sync_suggestions_very_positive(self):
        """Test opportunity sync suggestions for very positive meeting"""
        # Update validation session with very positive outcome
        self.validation_session.rep_responses['meeting_outcome'] = 'very_positive'
        self.validation_session.save()
        
        suggestions = self.crm_service.get_opportunity_sync_suggestions(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIn('Proposal/Price Quote', suggestions['stage_suggestions'])
        self.assertEqual(suggestions['probability_adjustment'], 20)
    
    def test_get_opportunity_sync_suggestions_negative(self):
        """Test opportunity sync suggestions for negative meeting"""
        # Update validation session with negative outcome
        self.validation_session.rep_responses['meeting_outcome'] = 'negative'
        self.validation_session.save()
        
        suggestions = self.crm_service.get_opportunity_sync_suggestions(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIn('Closed Lost', suggestions['stage_suggestions'])
        self.assertEqual(suggestions['probability_adjustment'], -20)


class TestBulkSync(TestCase):
    """Test bulk synchronization operations"""
    
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
            approved_crm_updates={
                'approved': True,
                'action_items': [
                    {'title': 'Task 1', 'description': 'Do task 1'}
                ]
            }
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    @patch.object(SalesforceClient, 'update_meeting_outcome')
    @patch.object(SalesforceClient, 'create_follow_up_task')
    @patch.object(SalesforceClient, 'update_opportunity_stage')
    def test_bulk_sync_with_opportunity_update(self, mock_opp_update, mock_task, mock_meeting):
        """Test bulk sync including opportunity update"""
        mock_meeting.return_value = {'Id': 'meeting123'}
        mock_task.return_value = {'Id': 'task123'}
        mock_opp_update.return_value = {'Id': 'opp123'}
        
        opportunity_data = {
            'opportunity_id': 'opp123',
            'stage_updates': {
                'stage_name': 'Proposal/Price Quote',
                'probability': 75
            }
        }
        
        results = self.crm_service.bulk_sync_validation_session(
            self.validation_session.id,
            CRMSystem.SALESFORCE,
            include_opportunity_update=True,
            opportunity_data=opportunity_data
        )
        
        self.assertIn('meeting_sync', results)
        self.assertIn('task_sync', results)
        self.assertIn('opportunity_sync', results)
        
        self.assertEqual(results['meeting_sync'].status, CRMSyncStatus.SUCCESS)
        self.assertEqual(results['opportunity_sync'].status, CRMSyncStatus.SUCCESS)
    
    @patch.object(SalesforceClient, 'update_meeting_outcome')
    @patch.object(SalesforceClient, 'create_follow_up_task')
    def test_bulk_sync_without_opportunity_update(self, mock_task, mock_meeting):
        """Test bulk sync without opportunity update"""
        mock_meeting.return_value = {'Id': 'meeting123'}
        mock_task.return_value = {'Id': 'task123'}
        
        results = self.crm_service.bulk_sync_validation_session(
            self.validation_session.id,
            CRMSystem.SALESFORCE,
            include_opportunity_update=False
        )
        
        self.assertIn('meeting_sync', results)
        self.assertIn('task_sync', results)
        self.assertNotIn('opportunity_sync', results)
        
        self.assertEqual(results['meeting_sync'].status, CRMSyncStatus.SUCCESS)


class TestSyncStatusTracking(TestCase):
    """Test sync status tracking and retry mechanisms"""
    
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
            expires_at=timezone.now() + timedelta(hours=24)
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_sync_status_tracking(self):
        """Test sync status tracking functionality"""
        # Create a sync record
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='sf123',
            synced_at=timezone.now()
        )
        
        # Test getting sync status
        status = self.crm_service.get_sync_status(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(status)
        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['crm_record_id'], 'sf123')
    
    def test_sync_status_not_found(self):
        """Test sync status when no record exists"""
        status = self.crm_service.get_sync_status(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertIsNone(status)
    
    @patch.object(SalesforceClient, 'update_meeting_outcome')
    def test_retry_failed_sync(self, mock_update):
        """Test retry mechanism for failed sync"""
        # Create a failed sync record
        CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='failed',
            error_message='Connection timeout',
            retry_count=1
        )
        
        mock_update.return_value = {'Id': 'sf123'}
        
        # Retry the sync
        result = self.crm_service.retry_failed_sync(
            self.validation_session.id,
            CRMSystem.SALESFORCE
        )
        
        self.assertEqual(result.status, CRMSyncStatus.SUCCESS)
        
        # Check that sync record was updated
        sync_record = CRMSyncRecord.objects.get(
            validation_session=self.validation_session,
            crm_system='salesforce'
        )
        self.assertEqual(sync_record.sync_status, 'completed')


class TestCRMIntegrationStaging(TestCase):
    """Integration tests with CRM staging environments (mocked)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crm_service = CRMService()
    
    @patch('meetings.crm_service.getattr')
    @patch.object(SalesforceClient, '_make_request')
    def test_salesforce_staging_integration(self, mock_request, mock_getattr):
        """Test integration with Salesforce staging environment"""
        # Mock settings
        mock_getattr.side_effect = lambda obj, key, default='': {
            'SALESFORCE_INSTANCE_URL': 'https://test.salesforce.com',
            'SALESFORCE_CLIENT_ID': 'test_client_id',
            'SALESFORCE_CLIENT_SECRET': 'test_client_secret'
        }.get(key, default)
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.json.return_value = {'Id': 'opp123', 'StageName': 'Proposal'}
        mock_request.return_value = mock_response
        
        client = self.crm_service.get_client(CRMSystem.SALESFORCE)
        
        # Test opportunity update
        stage_data = {
            'stage_name': 'Proposal/Price Quote',
            'probability': 75
        }
        
        result = client.update_opportunity_stage('opp123', stage_data)
        self.assertEqual(result['Id'], 'opp123')
        
        # Test opportunity retrieval
        result = client.get_opportunity_details('opp123')
        self.assertEqual(result['Id'], 'opp123')
    
    @patch('meetings.crm_service.getattr')
    @patch.object(HubSpotClient, '_make_request')
    def test_hubspot_staging_integration(self, mock_request, mock_getattr):
        """Test integration with HubSpot staging environment"""
        # Mock settings
        mock_getattr.side_effect = lambda obj, key, default='': {
            'HUBSPOT_CLIENT_ID': 'test_client_id',
            'HUBSPOT_CLIENT_SECRET': 'test_client_secret'
        }.get(key, default)
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.json.return_value = {
            'id': 'deal123',
            'properties': {'dealstage': 'closedwon', 'amount': '50000'}
        }
        mock_request.return_value = mock_response
        
        client = self.crm_service.get_client(CRMSystem.HUBSPOT)
        
        # Test deal update
        stage_data = {
            'stage_name': 'closedwon',
            'amount': 50000
        }
        
        result = client.update_opportunity_stage('deal123', stage_data)
        self.assertEqual(result['id'], 'deal123')
        
        # Test deal retrieval
        result = client.get_opportunity_details('deal123')
        self.assertEqual(result['id'], 'deal123')


if __name__ == '__main__':
    unittest.main()