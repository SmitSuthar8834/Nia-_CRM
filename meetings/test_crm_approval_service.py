"""
Unit tests for CRM approval service
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from leads.models import Lead
from .models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession, 
    CRMSyncRecord
)
from .crm_approval_service import CRMApprovalService


class CRMApprovalServiceTestCase(TestCase):
    """Test cases for CRMApprovalService"""
    
    def setUp(self):
        """Set up test data"""
        self.approval_service = CRMApprovalService()
        
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
        approved_systems = ['salesforce', 'hubspot']
        
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=self.validation_session.id,
            approved_systems=approved_systems
        )
        
        self.assertTrue(success)
        self.assertEqual(len(sync_records), 2)
        
        # Check that sync records were created
        for record in sync_records:
            self.assertIn(record.crm_system, approved_systems)
            self.assertEqual(record.sync_status, 'pending')
            self.assertIsNotNone(record.sync_payload)
        
        # Check audit trail was updated
        self.validation_session.refresh_from_db()
        last_change = self.validation_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_updates_approved')
        self.assertEqual(last_change['approved_systems'], approved_systems)
    
    def test_approve_crm_updates_with_custom_updates(self):
        """Test approval with custom updates"""
        approved_systems = ['salesforce']
        custom_updates = {
            'deal_stage': 'Closed Won',
            'custom_field': 'Custom value'
        }
        
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=self.validation_session.id,
            approved_systems=approved_systems,
            custom_updates=custom_updates
        )
        
        self.assertTrue(success)
        self.assertEqual(len(sync_records), 1)
        
        # Check that custom updates were included in payload
        sync_record = sync_records[0]
        self.assertIn('StageName', sync_record.sync_payload)  # Salesforce format
        self.assertEqual(sync_record.sync_payload['StageName'], 'Closed Won')
    
    def test_approve_crm_updates_invalid_session(self):
        """Test approval with invalid session"""
        with self.assertRaises(ValidationError) as context:
            self.approval_service.approve_crm_updates(
                session_id=99999,
                approved_systems=['salesforce']
            )
        
        self.assertIn("Invalid session", str(context.exception))
    
    def test_approve_crm_updates_not_completed(self):
        """Test approval for non-completed session"""
        self.validation_session.validation_status = 'in_progress'
        self.validation_session.save()
        
        with self.assertRaises(ValidationError) as context:
            self.approval_service.approve_crm_updates(
                session_id=self.validation_session.id,
                approved_systems=['salesforce']
            )
        
        self.assertIn("Can only approve CRM updates for completed validation sessions", str(context.exception))
    
    def test_approve_crm_updates_invalid_systems(self):
        """Test approval with invalid CRM systems"""
        with self.assertRaises(ValidationError) as context:
            self.approval_service.approve_crm_updates(
                session_id=self.validation_session.id,
                approved_systems=['invalid_crm', 'another_invalid']
            )
        
        self.assertIn("Invalid CRM systems", str(context.exception))
    
    def test_format_salesforce_payload(self):
        """Test Salesforce payload formatting"""
        approved_systems = ['salesforce']
        
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=self.validation_session.id,
            approved_systems=approved_systems
        )
        
        sf_record = sync_records[0]
        payload = sf_record.sync_payload
        
        # Check Salesforce-specific fields
        self.assertIn('Subject', payload)
        self.assertIn('Description', payload)
        self.assertIn('ActivityDate', payload)
        self.assertIn('Status', payload)
        self.assertIn('Type', payload)
        self.assertIn('StageName', payload)
        
        self.assertEqual(payload['Subject'], self.meeting.title)
        self.assertEqual(payload['Status'], 'Completed')
        self.assertEqual(payload['Type'], 'Meeting')
    
    def test_format_hubspot_payload(self):
        """Test HubSpot payload formatting"""
        approved_systems = ['hubspot']
        
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=self.validation_session.id,
            approved_systems=approved_systems
        )
        
        hs_record = sync_records[0]
        payload = hs_record.sync_payload
        
        # Check HubSpot-specific fields
        self.assertIn('hs_meeting_title', payload)
        self.assertIn('hs_meeting_body', payload)
        self.assertIn('hs_meeting_start_time', payload)
        self.assertIn('hs_meeting_outcome', payload)
        self.assertIn('dealstage', payload)
        
        self.assertEqual(payload['hs_meeting_title'], self.meeting.title)
        self.assertEqual(payload['hs_meeting_outcome'], 'COMPLETED')
    
    def test_format_creatio_payload(self):
        """Test Creatio payload formatting"""
        approved_systems = ['creatio']
        
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=self.validation_session.id,
            approved_systems=approved_systems
        )
        
        creatio_record = sync_records[0]
        payload = creatio_record.sync_payload
        
        # Check Creatio-specific fields
        self.assertIn('Title', payload)
        self.assertIn('Notes', payload)
        self.assertIn('StartDate', payload)
        self.assertIn('Status', payload)
        self.assertIn('Stage', payload)
        
        self.assertEqual(payload['Title'], self.meeting.title)
        self.assertEqual(payload['Status'], 'Completed')
    
    def test_reject_crm_updates_success(self):
        """Test successful rejection of CRM updates"""
        rejection_reason = "Summary needs more details"
        
        updated_session = self.approval_service.reject_crm_updates(
            session_id=self.validation_session.id,
            rejection_reason=rejection_reason
        )
        
        self.assertEqual(updated_session.approved_crm_updates, {})
        
        # Check audit trail was updated
        last_change = updated_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_updates_rejected')
        self.assertEqual(last_change['rejection_reason'], rejection_reason)
    
    def test_reject_crm_updates_not_completed(self):
        """Test rejection for non-completed session"""
        self.validation_session.validation_status = 'in_progress'
        self.validation_session.save()
        
        with self.assertRaises(ValidationError) as context:
            self.approval_service.reject_crm_updates(
                session_id=self.validation_session.id,
                rejection_reason="Test rejection"
            )
        
        self.assertIn("Can only reject CRM updates for completed validation sessions", str(context.exception))
    
    def test_get_crm_sync_status(self):
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
        
        sync_status = self.approval_service.get_crm_sync_status(self.validation_session.id)
        
        self.assertEqual(sync_status['session_id'], self.validation_session.id)
        self.assertEqual(sync_status['validation_status'], 'completed')
        self.assertTrue(sync_status['has_approved_updates'])
        self.assertEqual(len(sync_status['sync_records']), 2)
        
        # Check individual sync records
        sf_record = next(r for r in sync_status['sync_records'] if r['crm_system'] == 'salesforce')
        self.assertEqual(sf_record['sync_status'], 'completed')
        self.assertEqual(sf_record['crm_record_id'], 'SF_123')
        
        hs_record = next(r for r in sync_status['sync_records'] if r['crm_system'] == 'hubspot')
        self.assertEqual(hs_record['sync_status'], 'failed')
        self.assertEqual(hs_record['error_message'], 'Connection timeout')
    
    def test_retry_failed_sync_success(self):
        """Test successful retry of failed sync"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='failed',
            error_message='Connection timeout',
            retry_count=1,
            sync_payload={'test': 'data'}
        )
        
        updated_record = self.approval_service.retry_failed_sync(sync_record.id)
        
        self.assertEqual(updated_record.sync_status, 'pending')
        self.assertEqual(updated_record.error_message, '')
        self.assertEqual(updated_record.retry_count, 2)
        
        # Check audit trail was updated
        self.validation_session.refresh_from_db()
        last_change = self.validation_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_sync_retried')
        self.assertEqual(last_change['crm_system'], 'salesforce')
        self.assertEqual(last_change['retry_count'], 2)
    
    def test_retry_failed_sync_not_failed(self):
        """Test retry of non-failed sync"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            sync_payload={'test': 'data'}
        )
        
        with self.assertRaises(ValidationError) as context:
            self.approval_service.retry_failed_sync(sync_record.id)
        
        self.assertIn("Can only retry failed synchronizations", str(context.exception))
    
    def test_update_sync_record_status_success(self):
        """Test successful update of sync record status"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='in_progress',
            sync_payload={'test': 'data'}
        )
        
        updated_record = self.approval_service.update_sync_record_status(
            sync_record_id=sync_record.id,
            status='completed',
            crm_record_id='SF_456'
        )
        
        self.assertEqual(updated_record.sync_status, 'completed')
        self.assertEqual(updated_record.crm_record_id, 'SF_456')
        self.assertIsNotNone(updated_record.synced_at)
        
        # Check audit trail was updated
        self.validation_session.refresh_from_db()
        last_change = self.validation_session.changes_made[-1]
        self.assertEqual(last_change['action'], 'crm_sync_status_updated')
        self.assertEqual(last_change['new_status'], 'completed')
        self.assertEqual(last_change['crm_record_id'], 'SF_456')
    
    def test_update_sync_record_status_with_error(self):
        """Test update of sync record status with error"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='in_progress',
            sync_payload={'test': 'data'}
        )
        
        updated_record = self.approval_service.update_sync_record_status(
            sync_record_id=sync_record.id,
            status='failed',
            error_message='API rate limit exceeded'
        )
        
        self.assertEqual(updated_record.sync_status, 'failed')
        self.assertEqual(updated_record.error_message, 'API rate limit exceeded')
        self.assertIsNone(updated_record.synced_at)
    
    def test_update_sync_record_status_invalid_status(self):
        """Test update with invalid status"""
        sync_record = CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='pending',
            sync_payload={'test': 'data'}
        )
        
        with self.assertRaises(ValidationError) as context:
            self.approval_service.update_sync_record_status(
                sync_record_id=sync_record.id,
                status='invalid_status'
            )
        
        self.assertIn("Invalid status", str(context.exception))
    
    def test_generate_approval_summary(self):
        """Test generation of approval summary"""
        # Create some sync records and changes
        CRMSyncRecord.objects.create(
            validation_session=self.validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='SF_123',
            sync_payload={'test': 'data'}
        )
        
        # Add some changes to audit trail
        self.validation_session.changes_made.extend([
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
        ])
        self.validation_session.save()
        
        approval_summary = self.approval_service.generate_approval_summary(self.validation_session.id)
        
        # Check summary structure
        self.assertIn('session_info', approval_summary)
        self.assertIn('meeting_info', approval_summary)
        self.assertIn('validation_metrics', approval_summary)
        self.assertIn('changes_summary', approval_summary)
        self.assertIn('crm_sync_status', approval_summary)
        self.assertIn('final_summary', approval_summary)
        self.assertIn('approved_crm_updates', approval_summary)
        self.assertIn('audit_trail', approval_summary)
        
        # Check session info
        session_info = approval_summary['session_info']
        self.assertEqual(session_info['id'], self.validation_session.id)
        self.assertEqual(session_info['sales_rep_email'], 'sales@ourcompany.com')
        self.assertEqual(session_info['validation_status'], 'completed')
        
        # Check validation metrics
        metrics = approval_summary['validation_metrics']
        self.assertEqual(metrics['total_questions'], 1)
        self.assertEqual(metrics['answered_questions'], 1)
        self.assertEqual(metrics['completion_rate'], 100.0)
        
        # Check changes summary
        changes = approval_summary['changes_summary']
        self.assertEqual(changes['response_submissions'], 1)
        self.assertEqual(changes['crm_approvals'], 1)
    
    def test_analyze_validation_changes(self):
        """Test analysis of validation changes"""
        # Add various types of changes
        changes = [
            {
                'action': 'response_submitted',
                'timestamp': timezone.now().isoformat(),
                'question_id': 'test1'
            },
            {
                'action': 'response_submitted',
                'timestamp': timezone.now().isoformat(),
                'question_id': 'test2'
            },
            {
                'action': 'crm_updates_approved',
                'timestamp': timezone.now().isoformat(),
                'approved_systems': ['salesforce']
            },
            {
                'action': 'crm_updates_rejected',
                'timestamp': timezone.now().isoformat(),
                'rejection_reason': 'Test rejection'
            }
        ]
        
        self.validation_session.changes_made = changes
        
        changes_summary = self.approval_service._analyze_validation_changes(self.validation_session)
        
        self.assertEqual(changes_summary['total_changes'], 4)
        self.assertEqual(changes_summary['response_submissions'], 2)
        self.assertEqual(changes_summary['crm_approvals'], 1)
        self.assertEqual(changes_summary['crm_rejections'], 1)
        self.assertEqual(len(changes_summary['timeline']), 4)
    
    def test_format_change_description(self):
        """Test formatting of change descriptions"""
        # Test different change types
        changes = [
            {
                'action': 'response_submitted',
                'question_id': 'summary_accuracy'
            },
            {
                'action': 'session_completed'
            },
            {
                'action': 'crm_updates_approved',
                'approved_systems': ['salesforce', 'hubspot']
            },
            {
                'action': 'crm_updates_rejected',
                'rejection_reason': 'Needs more details'
            },
            {
                'action': 'crm_sync_status_updated',
                'crm_system': 'salesforce',
                'new_status': 'completed'
            }
        ]
        
        descriptions = [
            self.approval_service._format_change_description(change)
            for change in changes
        ]
        
        self.assertIn('summary_accuracy', descriptions[0])
        self.assertIn('completed', descriptions[1])
        self.assertIn('salesforce, hubspot', descriptions[2])
        self.assertIn('Needs more details', descriptions[3])
        self.assertIn('salesforce: completed', descriptions[4])