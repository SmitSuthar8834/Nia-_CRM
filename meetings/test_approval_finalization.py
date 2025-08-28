"""
Comprehensive tests for validation completion, approval, and finalization logic
"""
import json
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from leads.models import Lead
from .models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession, 
    CRMSyncRecord
)
from .validation_service import ValidationService
from .crm_approval_service import CRMApprovalService


class ApprovalFinalizationTestCase(TestCase):
    """Test cases for approval and finalization logic"""
    
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
        
        # Initialize services
        self.validation_service = ValidationService()
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
            raw_transcript="This is a test transcript of the meeting with detailed discussion about pricing, timeline, and next steps.",
            speaker_mapping={"speaker_1": "John Doe", "speaker_2": "Sales Rep"}
        )
        
        # Create test draft summary
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Comprehensive meeting summary discussing pricing options, project timeline, and implementation approach. Client showed strong interest in the premium package.",
            key_points=[
                "Discussed three pricing tiers: Basic ($10k), Standard ($25k), Premium ($50k)",
                "Client prefers 6-month implementation timeline",
                "Integration with existing CRM system is critical",
                "Decision maker meeting scheduled for next week"
            ],
            extracted_action_items=[
                {
                    "description": "Send detailed proposal with pricing breakdown",
                    "assignee": "Sales Rep",
                    "due_date": "2024-01-15",
                    "priority": "high"
                },
                {
                    "description": "Schedule technical review meeting",
                    "assignee": "John Doe",
                    "due_date": "2024-01-18",
                    "priority": "medium"
                },
                {
                    "description": "Prepare CRM integration documentation",
                    "assignee": "Technical Team",
                    "due_date": "2024-01-20",
                    "priority": "medium"
                }
            ],
            suggested_next_steps=[
                "Send proposal within 48 hours",
                "Schedule decision maker meeting",
                "Prepare technical integration plan"
            ],
            decisions_made=[
                "Premium package is the preferred option",
                "6-month timeline is acceptable",
                "CRM integration is mandatory requirement"
            ],
            suggested_crm_updates={
                "stage": "Proposal Sent",
                "next_action": "Follow up on proposal",
                "deal_value": 50000,
                "probability": 75,
                "notes": "Strong interest in premium package, decision meeting scheduled"
            },
            confidence_score=0.92
        )
    
    def test_complete_validation_and_approval_workflow(self):
        """Test the complete workflow from validation creation to final approval"""
        
        # Step 1: Create validation session
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        self.assertEqual(session.validation_status, 'pending')
        self.assertTrue(len(session.validation_questions) > 0)
        
        # Step 2: Submit responses to ALL questions (not just required ones)
        all_questions = session.validation_questions
        
        for question in all_questions:
            if question['type'] == 'confirmation':
                response = {'confirmed': True, 'notes': 'Confirmed accurate'}
            elif question['type'] == 'multi_select':
                response = {'selected_options': question.get('options', [])[:2] if question.get('options') else ['option1']}
            elif question['type'] == 'action_items_review':
                response = {'approved_items': question.get('items', [])}
            elif question['type'] == 'text_edit':
                response = {'text': 'Updated and improved text content'}
            elif question['type'] == 'crm_approval':
                response = {'approved': True, 'modifications': {'priority': 'high'}}
            elif question['type'] == 'stage_selection':
                response = {'selected_stage': 'Proposal Sent'}
            else:
                response = {'confirmed': True, 'notes': 'Default response'}
            
            updated_session = self.validation_service.submit_validation_response(
                session_id=session.id,
                question_id=question['id'],
                response=response
            )
        
        # Verify session is in progress
        self.assertEqual(updated_session.validation_status, 'in_progress')
        
        # Step 3: Complete validation session
        completed_session, final_summary = self.validation_service.complete_validation_session(session.id)
        
        self.assertEqual(completed_session.validation_status, 'completed')
        self.assertIsNotNone(completed_session.completed_at)
        self.assertIsNotNone(final_summary)
        self.assertTrue(len(final_summary) > 0)
        self.assertIsNotNone(completed_session.approved_crm_updates)
        
        # Step 4: Approve CRM updates
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=completed_session.id,
            approved_systems=['salesforce', 'hubspot', 'creatio'],
            custom_updates={'urgency': 'high', 'follow_up_date': '2024-01-16'}
        )
        
        self.assertTrue(success)
        self.assertEqual(len(sync_records), 3)
        
        # Verify sync records were created with correct payloads
        for record in sync_records:
            self.assertEqual(record.sync_status, 'pending')
            self.assertIsNotNone(record.sync_payload)
            self.assertIn(record.crm_system, ['salesforce', 'hubspot', 'creatio'])
        
        # Step 5: Simulate CRM sync completion
        for record in sync_records:
            updated_record = self.approval_service.update_sync_record_status(
                sync_record_id=record.id,
                status='completed',
                crm_record_id=f"{record.crm_system.upper()}_RECORD_123"
            )
            self.assertEqual(updated_record.sync_status, 'completed')
            self.assertIsNotNone(updated_record.synced_at)
        
        # Step 6: Generate final approval summary
        approval_summary = self.approval_service.generate_approval_summary(completed_session.id)
        
        # Verify comprehensive summary structure
        self.assertIn('session_info', approval_summary)
        self.assertIn('meeting_info', approval_summary)
        self.assertIn('validation_metrics', approval_summary)
        self.assertIn('changes_summary', approval_summary)
        self.assertIn('crm_sync_status', approval_summary)
        self.assertIn('final_summary', approval_summary)
        self.assertIn('approved_crm_updates', approval_summary)
        self.assertIn('audit_trail', approval_summary)
        
        # Verify metrics
        metrics = approval_summary['validation_metrics']
        self.assertEqual(metrics['completion_rate'], 100.0)
        self.assertGreater(metrics['answered_questions'], 0)
        
        # Verify all CRM syncs completed
        crm_status = approval_summary['crm_sync_status']
        completed_syncs = [r for r in crm_status['sync_records'] if r['sync_status'] == 'completed']
        self.assertEqual(len(completed_syncs), 3)
    
    def test_audit_trail_comprehensive_tracking(self):
        """Test comprehensive audit trail tracking throughout the workflow"""
        
        # Create and complete validation session
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Track initial changes count
        initial_changes = len(session.changes_made)
        
        # Submit multiple responses
        questions = session.validation_questions[:3]  # Test with first 3 questions
        
        for i, question in enumerate(questions):
            if question['type'] == 'confirmation':
                response = {'confirmed': True, 'notes': f'Response {i+1}'}
            elif question['type'] == 'multi_select':
                response = {'selected_options': ['option1'], 'notes': f'Response {i+1}'}
            elif question['type'] == 'action_items_review':
                response = {'approved_items': question.get('items', []), 'notes': f'Response {i+1}'}
            elif question['type'] == 'text_edit':
                response = {'text': f'Updated text {i+1}'}
            elif question['type'] == 'crm_approval':
                response = {'approved': True, 'notes': f'Response {i+1}'}
            else:
                response = {'confirmed': True, 'notes': f'Response {i+1}'}
            
            self.validation_service.submit_validation_response(
                session_id=session.id,
                question_id=question['id'],
                response=response
            )
        
        # Check that each response was tracked
        session.refresh_from_db()
        response_changes = [c for c in session.changes_made if c['action'] == 'response_submitted']
        self.assertEqual(len(response_changes), 3)
        
        # Complete all required questions and finish session
        required_questions = [q for q in session.validation_questions if q.get('required', False)]
        
        for question in required_questions:
            if question['id'] not in [q['id'] for q in questions]:  # Skip already answered
                if question['type'] == 'confirmation':
                    response = {'confirmed': True}
                elif question['type'] == 'multi_select':
                    response = {'selected_options': question.get('options', [])[:1] if question.get('options') else ['option1']}
                elif question['type'] == 'action_items_review':
                    response = {'approved_items': question.get('items', [])}
                elif question['type'] == 'text_edit':
                    response = {'text': 'Default text for completion'}
                elif question['type'] == 'crm_approval':
                    response = {'approved': True}
                elif question['type'] == 'stage_selection':
                    response = {'selected_stage': question.get('suggested_stage', 'In Progress')}
                else:
                    response = {'confirmed': True}
                
                self.validation_service.submit_validation_response(
                    session_id=session.id,
                    question_id=question['id'],
                    response=response
                )
        
        # Complete session
        completed_session, _ = self.validation_service.complete_validation_session(session.id)
        
        # Check completion was tracked
        completion_changes = [c for c in completed_session.changes_made if c['action'] == 'session_completed']
        self.assertEqual(len(completion_changes), 1)
        
        # Approve CRM updates
        self.approval_service.approve_crm_updates(
            session_id=completed_session.id,
            approved_systems=['salesforce']
        )
        
        # Check approval was tracked
        completed_session.refresh_from_db()
        approval_changes = [c for c in completed_session.changes_made if c['action'] == 'crm_updates_approved']
        self.assertEqual(len(approval_changes), 1)
        
        # Verify audit trail structure
        for change in completed_session.changes_made:
            self.assertIn('action', change)
            self.assertIn('timestamp', change)
            
            # Verify timestamp format
            timestamp = change['timestamp']
            self.assertIsInstance(timestamp, str)
            self.assertIn('T', timestamp)  # ISO format
    
    def test_final_summary_generation_accuracy(self):
        """Test accuracy of final summary generation from validation responses"""
        
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Submit specific responses to test summary generation
        responses = {
            'summary_accuracy': {
                'confirmed': False,
                'edited_text': 'Enhanced meeting summary with additional client feedback and refined next steps.'
            },
            'key_points_validation': {
                'selected_options': [
                    "Discussed three pricing tiers: Basic ($10k), Standard ($25k), Premium ($50k)",
                    "Client prefers 6-month implementation timeline"
                ]
            },
            'action_items_validation': {
                'approved_items': [
                    {
                        "description": "Send detailed proposal with pricing breakdown",
                        "assignee": "Sales Rep",
                        "due_date": "2024-01-15",
                        "priority": "high"
                    }
                ]
            },
            'next_steps_confirmation': {
                'text': 'Priority actions:\n1. Send proposal by EOD tomorrow\n2. Schedule decision maker meeting\n3. Prepare technical documentation'
            },
            'additional_notes': {
                'text': 'Client expressed particular interest in the premium package features and emphasized the importance of seamless CRM integration.'
            }
        }
        
        # Submit all responses
        for question_id, response in responses.items():
            # Find the question in the session
            question = next((q for q in session.validation_questions if q['id'] == question_id), None)
            if question:
                self.validation_service.submit_validation_response(
                    session_id=session.id,
                    question_id=question_id,
                    response=response
                )
        
        # Submit remaining required responses
        for question in session.validation_questions:
            if question['id'] not in responses and question.get('required', False):
                if question['type'] == 'confirmation':
                    default_response = {'confirmed': True}
                elif question['type'] == 'multi_select':
                    default_response = {'selected_options': question.get('options', [])[:1] if question.get('options') else ['option1']}
                elif question['type'] == 'action_items_review':
                    default_response = {'approved_items': question.get('items', [])}
                elif question['type'] == 'text_edit':
                    default_response = {'text': 'Default text'}
                elif question['type'] == 'crm_approval':
                    default_response = {'approved': True}
                elif question['type'] == 'stage_selection':
                    default_response = {'selected_stage': question.get('suggested_stage', 'In Progress')}
                else:
                    default_response = {'confirmed': True}
                
                self.validation_service.submit_validation_response(
                    session_id=session.id,
                    question_id=question['id'],
                    response=default_response
                )
        
        # Complete session and get final summary
        completed_session, final_summary = self.validation_service.complete_validation_session(session.id)
        
        # Verify final summary contains expected content
        self.assertIn('Enhanced meeting summary', final_summary)
        self.assertIn('Key Points:', final_summary)
        self.assertIn('three pricing tiers', final_summary)
        self.assertIn('Action Items:', final_summary)
        self.assertIn('Send detailed proposal', final_summary)
        self.assertIn('Next Steps:', final_summary)
        self.assertIn('Priority actions:', final_summary)
        self.assertIn('Additional Notes:', final_summary)
        self.assertIn('premium package features', final_summary)
        
        # Verify summary structure and formatting
        lines = final_summary.split('\n')
        self.assertTrue(any('Key Points:' in line for line in lines))
        self.assertTrue(any('Action Items:' in line for line in lines))
        self.assertTrue(any('Next Steps:' in line for line in lines))
        self.assertTrue(any('Additional Notes:' in line for line in lines))
    
    def test_crm_update_approval_and_formatting(self):
        """Test CRM update approval and system-specific formatting"""
        
        # Create completed validation session
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            rep_responses={
                'crm_updates_approval': {
                    'response': {'approved': True, 'modifications': {'priority': 'urgent'}},
                    'timestamp': timezone.now().isoformat()
                },
                'deal_stage_update': {
                    'response': {'selected_stage': 'Proposal Sent'},
                    'timestamp': timezone.now().isoformat()
                }
            },
            validated_summary="Final validated summary with all corrections applied",
            approved_crm_updates={
                "deal_stage": "Proposal Sent",
                "deal_value": 50000,
                "probability": 75,
                "next_action": "Follow up on proposal",
                "priority": "urgent"
            },
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(minutes=30),
            expires_at=timezone.now() + timedelta(hours=23),
            validation_status='completed'
        )
        
        # Test approval for all CRM systems
        success, sync_records = self.approval_service.approve_crm_updates(
            session_id=session.id,
            approved_systems=['salesforce', 'hubspot', 'creatio'],
            custom_updates={'follow_up_date': '2024-01-16', 'campaign_source': 'webinar'}
        )
        
        self.assertTrue(success)
        self.assertEqual(len(sync_records), 3)
        
        # Test Salesforce formatting
        sf_record = next(r for r in sync_records if r.crm_system == 'salesforce')
        sf_payload = sf_record.sync_payload
        
        self.assertIn('Subject', sf_payload)
        self.assertIn('Description', sf_payload)
        self.assertIn('StageName', sf_payload)
        self.assertIn('NextStep', sf_payload)
        self.assertEqual(sf_payload['Subject'], self.meeting.title)
        self.assertEqual(sf_payload['StageName'], 'Proposal Sent')
        self.assertEqual(sf_payload['Status'], 'Completed')
        
        # Test HubSpot formatting
        hs_record = next(r for r in sync_records if r.crm_system == 'hubspot')
        hs_payload = hs_record.sync_payload
        
        self.assertIn('hs_meeting_title', hs_payload)
        self.assertIn('hs_meeting_body', hs_payload)
        self.assertIn('dealstage', hs_payload)
        self.assertEqual(hs_payload['hs_meeting_title'], self.meeting.title)
        self.assertEqual(hs_payload['dealstage'], 'Proposal Sent')
        self.assertEqual(hs_payload['hs_meeting_outcome'], 'COMPLETED')
        
        # Test Creatio formatting
        creatio_record = next(r for r in sync_records if r.crm_system == 'creatio')
        creatio_payload = creatio_record.sync_payload
        
        self.assertIn('Title', creatio_payload)
        self.assertIn('Notes', creatio_payload)
        self.assertIn('Stage', creatio_payload)
        self.assertEqual(creatio_payload['Title'], self.meeting.title)
        self.assertEqual(creatio_payload['Stage'], 'Proposal Sent')
        self.assertEqual(creatio_payload['Status'], 'Completed')
        
        # Verify custom updates were included
        for record in sync_records:
            payload = record.sync_payload
            self.assertIn('follow_up_date', payload)
            self.assertIn('campaign_source', payload)
            self.assertEqual(payload['follow_up_date'], '2024-01-16')
            self.assertEqual(payload['campaign_source'], 'webinar')
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms"""
        
        # Test validation completion with missing required responses
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Submit only partial responses
        first_question = session.validation_questions[0]
        self.validation_service.submit_validation_response(
            session_id=session.id,
            question_id=first_question['id'],
            response={'confirmed': True}
        )
        
        # Try to complete with missing required responses
        with self.assertRaises(ValidationError) as context:
            self.validation_service.complete_validation_session(session.id)
        
        self.assertIn("Required questions not answered", str(context.exception))
        
        # Test CRM approval for non-completed session
        with self.assertRaises(ValidationError) as context:
            self.approval_service.approve_crm_updates(
                session_id=session.id,
                approved_systems=['salesforce']
            )
        
        self.assertIn("Can only approve CRM updates for completed validation sessions", str(context.exception))
        
        # Create a separate draft summary for the retry test
        meeting2 = Meeting.objects.create(
            calendar_event_id="test_event_retry",
            title="Retry Test Meeting",
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            status="completed"
        )
        
        bot_session2 = CallBotSession.objects.create(
            meeting=meeting2,
            bot_session_id="bot_session_retry",
            platform="meet",
            join_time=timezone.now() - timedelta(hours=2),
            connection_status="disconnected"
        )
        
        draft_summary2 = DraftSummary.objects.create(
            bot_session=bot_session2,
            ai_generated_summary="Retry test summary",
            confidence_score=0.8
        )
        
        # Test retry mechanism for failed sync
        completed_session = ValidationSession.objects.create(
            draft_summary=draft_summary2,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            validated_summary="Test summary",
            approved_crm_updates={"stage": "Test"},
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(minutes=30),
            expires_at=timezone.now() + timedelta(hours=23),
            validation_status='completed'
        )
        
        # Create failed sync record
        failed_record = CRMSyncRecord.objects.create(
            validation_session=completed_session,
            crm_system='salesforce',
            sync_status='failed',
            error_message='Connection timeout',
            retry_count=0,
            sync_payload={'test': 'data'}
        )
        
        # Test retry
        retried_record = self.approval_service.retry_failed_sync(failed_record.id)
        
        self.assertEqual(retried_record.sync_status, 'pending')
        self.assertEqual(retried_record.error_message, '')
        self.assertEqual(retried_record.retry_count, 1)
        
        # Test retry of non-failed record
        retried_record.sync_status = 'completed'
        retried_record.save()
        
        with self.assertRaises(ValidationError) as context:
            self.approval_service.retry_failed_sync(retried_record.id)
        
        self.assertIn("Can only retry failed synchronizations", str(context.exception))
    
    def test_performance_and_scalability(self):
        """Test performance with multiple validation sessions and sync records"""
        
        # Create multiple validation sessions
        sessions = []
        for i in range(5):
            # Create separate meetings and draft summaries
            meeting = Meeting.objects.create(
                calendar_event_id=f"test_event_{i}",
                title=f"Meeting {i}",
                start_time=timezone.now() - timedelta(hours=2),
                end_time=timezone.now() - timedelta(hours=1),
                status="completed"
            )
            
            bot_session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f"bot_session_{i}",
                platform="meet",
                join_time=timezone.now() - timedelta(hours=2),
                connection_status="disconnected"
            )
            
            draft_summary = DraftSummary.objects.create(
                bot_session=bot_session,
                ai_generated_summary=f"Summary {i}",
                confidence_score=0.8
            )
            
            session = ValidationSession.objects.create(
                draft_summary=draft_summary,
                sales_rep_email="sales@ourcompany.com",
                validation_questions=[],
                validated_summary=f"Final summary {i}",
                approved_crm_updates={"stage": f"Stage {i}"},
                started_at=timezone.now() - timedelta(hours=1),
                completed_at=timezone.now() - timedelta(minutes=30),
                expires_at=timezone.now() + timedelta(hours=23),
                validation_status='completed'
            )
            sessions.append(session)
        
        # Approve CRM updates for all sessions
        all_sync_records = []
        for session in sessions:
            success, sync_records = self.approval_service.approve_crm_updates(
                session_id=session.id,
                approved_systems=['salesforce', 'hubspot']
            )
            self.assertTrue(success)
            all_sync_records.extend(sync_records)
        
        # Verify all sync records were created
        self.assertEqual(len(all_sync_records), 10)  # 5 sessions * 2 systems
        
        # Test bulk status updates
        for record in all_sync_records:
            self.approval_service.update_sync_record_status(
                sync_record_id=record.id,
                status='completed',
                crm_record_id=f"BULK_{record.id}"
            )
        
        # Verify all records were updated
        completed_records = CRMSyncRecord.objects.filter(sync_status='completed')
        self.assertEqual(completed_records.count(), 10)
        
        # Test approval summary generation for multiple sessions
        for session in sessions:
            summary = self.approval_service.generate_approval_summary(session.id)
            self.assertIn('session_info', summary)
            self.assertIn('crm_sync_status', summary)
            
            # Verify all syncs completed
            sync_status = summary['crm_sync_status']
            completed_syncs = [r for r in sync_status['sync_records'] if r['sync_status'] == 'completed']
            self.assertEqual(len(completed_syncs), 2)