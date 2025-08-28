"""
API tests for CRM approval endpoints
"""
import json
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from leads.models import Lead
from .models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession, 
    CRMSyncRecord
)


class CRMApprovalAPITestCase(TestCase):
    """Test cases for CRM Approval API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_001",
            name="John Doe",
            email="john.doe@example.com",
            company="Test Company",
            phone="+1234567890",
            status="qualified"
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_123",
            lead=self.lead,
            title="Sales Call with Test Company",
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            attendees=["john.doe@example.com", "sales@ourcompany.com"],
            status="completed"
        )
        
        # Create test call bot session
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="bot_session_123",
            platform="meet",
            join_time=timezone.now() - timedelta(hours=2),
            leave_time=timezone.now() - timedelta(hours=1),
            connection_status="disconnected",
            raw_transcript="This is a test transcript of the meeting.",
            speaker_mapping={"speaker_1": "John Doe", "speaker_2": "Sales Rep"}
        )
        
        # Create test draft summary
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Test meeting summary with key discussion points.",
            key_points=["Discussed pricing", "Reviewed timeline", "Next steps agreed"],
            extracted_action_items=[
                {"description": "Send proposal", "assignee": "Sales Rep", "due_date": "2024-01-15"},
                {"description": "Review contract", "assignee": "John Doe", "due_date": "2024-01-20"}
            ],
            suggested_next_steps=["Schedule follow-up call", "Prepare contract"],
            decisions_made=["Agreed on pricing structure", "Timeline confirmed"],
            suggested_crm_updates={
                "stage": "Proposal",
                "next_action": "Send proposal",
                "notes": "Positive meeting, ready to move forward"
            },
            confidence_score=0.85
        )
        
        # Create completed validation session
        self.validation_session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {
                    "id": "summary_accuracy",
                    "type": "confirmation",
                    "question": "Is this summary accurate?",
                    "required": True
                }
            ],
            rep_responses={
                'summary_accuracy': {
                    'response': {'confirmed': True},
                    'timestamp': timezone.now().isoformat()
                }
            },
            validated_summary="Final validated summary of the meeting",
            approved_crm_updates={
                "deal_stage": "Proposal",
                "next_action": "Send proposal",
                "meeting_summary": "Final validated summary of the meeting"
            },
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(minutes=30),
            expires_at=timezone.now() + timedelta(hours=23),
            validation_status='completed'
        )
    
    def test_approve_crm_updates_success(self):
        """Test successful approval of CRM updates"""
        url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {
            'approved_systems': ['salesforce', 'hubspot'],
            'custom_updates': {
                'deal_stage': 'Closed Won',
                'custom_field': 'Custom value'
            }
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['approved_systems']), 2)
        self.assertEqual(len(response.data['sync_records']), 2)
        
        # Check that sync records were created
        sync_records = CRMSyncRecord.objects.filter(validation_session=self.validation_session)
        self.assertEqual(sync_records.count(), 2)
        
        for record in sync_records:
            self.assertIn(record.crm_system, ['salesforce', 'hubspot'])
            self.assertEqual(record.sync_status, 'pending')
            self.assertIsNotNone(record.sync_payload)
    
    def test_approve_crm_updates_missing_systems(self):
        """Test approval with missing approved_systems"""
        url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('approved_systems is required', response.data['error'])
    
    def test_approve_crm_updates_invalid_session(self):
        """Test approval with invalid session ID"""
        url = reverse('approve-crm-updates', kwargs={'session_id': 99999})
        data = {'approved_systems': ['salesforce']}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_approve_crm_updates_not_completed(self):
        """Test approval for non-completed session"""
        self.validation_session.validation_status = 'in_progress'
        self.validation_session.save()
        
        url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {'approved_systems': ['salesforce']}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_reject_crm_updates_success(self):
        """Test successful rejection of CRM updates"""
        url = reverse('reject-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {'rejection_reason': 'Summary needs more details'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['rejection_reason'], 'Summary needs more details')
        
        # Check that session was updated
        self.validation_session.refresh_from_db()
        self.assertEqual(self.validation_session.approved_crm_updates, {})
        
        # Check audit trail
        last_change = self.validation_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_updates_rejected')
    
    def test_reject_crm_updates_missing_reason(self):
        """Test rejection with missing reason"""
        url = reverse('reject-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rejection_reason is required', response.data['error'])
    
    def test_get_crm_sync_status_success(self):
        """Test getting CRM sync status"""
        # Create some sync records first
        sync_record1 = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='SF_123',
            sync_payload={'test': 'data'}
        )
        
        sync_record2 = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='hubspot',
            sync_status='failed',
            error_message='Connection timeout',
            sync_payload={'test': 'data'}
        )
        
        url = reverse('get-crm-sync-status', kwargs={'session_id': self.validation_session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], self.validation_session.id)
        self.assertEqual(response.data['validation_status'], 'completed')
        self.assertTrue(response.data['has_approved_updates'])
        self.assertEqual(len(response.data['sync_records']), 2)
    
    def test_retry_failed_crm_sync_success(self):
        """Test successful retry of failed CRM sync"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='failed',
            error_message='Connection timeout',
            retry_count=1,
            sync_payload={'test': 'data'}
        )
        
        url = reverse('retry-failed-crm-sync', kwargs={'sync_record_id': sync_record.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check that record was updated
        sync_record.refresh_from_db()
        self.assertEqual(sync_record.sync_status, 'pending')
        self.assertEqual(sync_record.error_message, '')
        self.assertEqual(sync_record.retry_count, 2)
    
    def test_retry_failed_crm_sync_not_failed(self):
        """Test retry of non-failed sync"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            sync_payload={'test': 'data'}
        )
        
        url = reverse('retry-failed-crm-sync', kwargs={'sync_record_id': sync_record.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_update_crm_sync_status_success(self):
        """Test successful update of CRM sync status"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='in_progress',
            sync_payload={'test': 'data'}
        )
        
        url = reverse('update-crm-sync-status', kwargs={'sync_record_id': sync_record.id})
        data = {
            'status': 'completed',
            'crm_record_id': 'SF_456'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check that record was updated
        sync_record.refresh_from_db()
        self.assertEqual(sync_record.sync_status, 'completed')
        self.assertEqual(sync_record.crm_record_id, 'SF_456')
        self.assertIsNotNone(sync_record.synced_at)
    
    def test_update_crm_sync_status_with_error(self):
        """Test update of sync status with error"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='in_progress',
            sync_payload={'test': 'data'}
        )
        
        url = reverse('update-crm-sync-status', kwargs={'sync_record_id': sync_record.id})
        data = {
            'status': 'failed',
            'error_message': 'API rate limit exceeded'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check that record was updated
        sync_record.refresh_from_db()
        self.assertEqual(sync_record.sync_status, 'failed')
        self.assertEqual(sync_record.error_message, 'API rate limit exceeded')
    
    def test_update_crm_sync_status_invalid_status(self):
        """Test update with invalid status"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='pending',
            sync_payload={'test': 'data'}
        )
        
        url = reverse('update-crm-sync-status', kwargs={'sync_record_id': sync_record.id})
        data = {'status': 'invalid_status'}
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_approval_summary_success(self):
        """Test getting comprehensive approval summary"""
        # Create some sync records and changes
        CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='SF_123',
            sync_payload={'test': 'data'}
        )
        
        # Add some changes to audit trail
        self.validation_session.changes_made = [
            {
                'action': 'response_submitted',
                'timestamp': timezone.now().isoformat(),
                'question_id': 'summary_accuracy'
            },
            {
                'action': 'crm_updates_approved',
                'timestamp': timezone.now().isoformat(),
                'approved_systems': ['salesforce']
            }
        ]
        self.validation_session.save()
        
        url = reverse('get-approval-summary', kwargs={'session_id': self.validation_session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check summary structure
        self.assertIn('session_info', response.data)
        self.assertIn('meeting_info', response.data)
        self.assertIn('validation_metrics', response.data)
        self.assertIn('changes_summary', response.data)
        self.assertIn('crm_sync_status', response.data)
        self.assertIn('final_summary', response.data)
        self.assertIn('approved_crm_updates', response.data)
        self.assertIn('audit_trail', response.data)
        
        # Check session info
        session_info = response.data['session_info']
        self.assertEqual(session_info['id'], self.validation_session.id)
        self.assertEqual(session_info['sales_rep_email'], 'sales@ourcompany.com')
        self.assertEqual(session_info['validation_status'], 'completed')
        
        # Check validation metrics
        metrics = response.data['validation_metrics']
        self.assertEqual(metrics['total_questions'], 1)
        self.assertEqual(metrics['answered_questions'], 1)
        self.assertEqual(metrics['completion_rate'], 100.0)
    
    def test_get_approval_summary_invalid_session(self):
        """Test getting approval summary for invalid session"""
        url = reverse('get-approval-summary', kwargs={'session_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_crm_payload_formatting(self):
        """Test CRM payload formatting for different systems"""
        # Test Salesforce formatting
        url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {'approved_systems': ['salesforce']}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        sf_record = CRMSyncRecord.objects.get(
            validation_session=self.validation_session,
            crm_system='salesforce'
        )
        
        # Check Salesforce-specific fields
        payload = sf_record.sync_payload
        self.assertIn('Subject', payload)
        self.assertIn('Description', payload)
        self.assertIn('ActivityDate', payload)
        self.assertIn('Status', payload)
        self.assertIn('Type', payload)
        
        self.assertEqual(payload['Subject'], self.meeting.title)
        self.assertEqual(payload['Status'], 'Completed')
        self.assertEqual(payload['Type'], 'Meeting')
    
    def test_audit_trail_tracking(self):
        """Test that audit trail is properly tracked"""
        # Initial changes count
        initial_changes = len(self.validation_session.changes_made)
        
        # Approve CRM updates
        url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        data = {'approved_systems': ['salesforce']}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that audit trail was updated
        self.validation_session.refresh_from_db()
        self.assertEqual(len(self.validation_session.changes_made), initial_changes + 1)
        
        last_change = self.validation_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_updates_approved')
        self.assertEqual(last_change['approved_systems'], ['salesforce'])
        self.assertIn('timestamp', last_change)
    
    def test_authentication_required(self):
        """Test that authentication is required for all endpoints"""
        # Create unauthenticated client
        unauth_client = APIClient()
        
        # Test endpoints
        endpoints = [
            ('approve-crm-updates', {'session_id': self.validation_session.id}),
            ('reject-crm-updates', {'session_id': self.validation_session.id}),
            ('get-crm-sync-status', {'session_id': self.validation_session.id}),
            ('get-approval-summary', {'session_id': self.validation_session.id}),
        ]
        
        for endpoint_name, kwargs in endpoints:
            url = reverse(endpoint_name, kwargs=kwargs)
            response = unauth_client.get(url)
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_complete_approval_workflow(self):
        """Test the complete approval workflow from validation to CRM sync"""
        # Step 1: Approve CRM updates
        approve_url = reverse('approve-crm-updates', kwargs={'session_id': self.validation_session.id})
        approve_data = {
            'approved_systems': ['salesforce', 'hubspot'],
            'custom_updates': {'priority': 'high'}
        }
        
        approve_response = self.client.post(approve_url, approve_data, format='json')
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # Step 2: Check sync status
        status_url = reverse('get-crm-sync-status', kwargs={'session_id': self.validation_session.id})
        status_response = self.client.get(status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        sync_records = status_response.data['sync_records']
        self.assertEqual(len(sync_records), 2)
        
        # Step 3: Simulate external sync completion
        for record in sync_records:
            update_url = reverse('update-crm-sync-status', kwargs={'sync_record_id': record['id']})
            update_data = {
                'status': 'completed',
                'crm_record_id': f"{record['crm_system'].upper()}_123"
            }
            
            update_response = self.client.put(update_url, update_data, format='json')
            self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # Step 4: Get final approval summary
        summary_url = reverse('get-approval-summary', kwargs={'session_id': self.validation_session.id})
        summary_response = self.client.get(summary_url)
        self.assertEqual(summary_response.status_code, status.HTTP_200_OK)
        
        # Verify all syncs completed
        crm_status = summary_response.data['crm_sync_status']
        completed_syncs = [r for r in crm_status['sync_records'] if r['sync_status'] == 'completed']
        self.assertEqual(len(completed_syncs), 2)