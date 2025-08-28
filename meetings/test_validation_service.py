"""
Unit tests for validation service
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock

from leads.models import Lead
from .models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession, 
    CRMSyncRecord
)
from .validation_service import ValidationService


class ValidationServiceTestCase(TestCase):
    """Test cases for ValidationService"""
    
    def setUp(self):
        """Set up test data"""
        self.validation_service = ValidationService()
        
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
    
    def test_create_validation_session_success(self):
        """Test successful creation of validation session"""
        sales_rep_email = "sales@ourcompany.com"
        
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email=sales_rep_email
        )
        
        self.assertIsInstance(session, ValidationSession)
        self.assertEqual(session.draft_summary, self.draft_summary)
        self.assertEqual(session.sales_rep_email, sales_rep_email)
        self.assertEqual(session.validation_status, 'pending')
        self.assertIsNotNone(session.validation_questions)
        self.assertTrue(len(session.validation_questions) > 0)
        
        # Check that expiration is set correctly
        expected_expiry = session.started_at + ValidationService.DEFAULT_SESSION_DURATION
        self.assertEqual(session.expires_at, expected_expiry)
    
    def test_create_validation_session_custom_duration(self):
        """Test creation with custom session duration"""
        custom_duration = timedelta(hours=12)
        
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com",
            session_duration=custom_duration
        )
        
        expected_expiry = session.started_at + custom_duration
        self.assertEqual(session.expires_at, expected_expiry)
    
    def test_create_validation_session_nonexistent_summary(self):
        """Test creation with non-existent draft summary"""
        with self.assertRaises(ValidationError) as context:
            self.validation_service.create_validation_session(
                draft_summary_id=99999,
                sales_rep_email="sales@ourcompany.com"
            )
        
        self.assertIn("Draft summary with ID 99999 not found", str(context.exception))
    
    def test_create_validation_session_already_exists(self):
        """Test creation when validation session already exists"""
        # Create first session
        self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Try to create second session
        with self.assertRaises(ValidationError) as context:
            self.validation_service.create_validation_session(
                draft_summary_id=self.draft_summary.id,
                sales_rep_email="sales@ourcompany.com"
            )
        
        self.assertIn("Validation session already exists", str(context.exception))
    
    def test_generate_validation_questions(self):
        """Test validation question generation"""
        questions = self.validation_service._generate_validation_questions(self.draft_summary)
        
        # Check that all expected question types are present
        question_ids = [q['id'] for q in questions]
        expected_ids = [
            'summary_accuracy',
            'key_points_validation',
            'action_items_validation',
            'next_steps_confirmation',
            'crm_updates_approval',
            'deal_stage_update',
            'additional_notes'
        ]
        
        for expected_id in expected_ids:
            self.assertIn(expected_id, question_ids)
        
        # Check question structure
        for question in questions:
            self.assertIn('id', question)
            self.assertIn('type', question)
            self.assertIn('question', question)
            self.assertIn('required', question)
    
    def test_get_validation_session_success(self):
        """Test successful retrieval of validation session"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        retrieved_session = self.validation_service.get_validation_session(session.id)
        self.assertEqual(retrieved_session.id, session.id)
    
    def test_get_validation_session_nonexistent(self):
        """Test retrieval of non-existent validation session"""
        with self.assertRaises(ValidationError) as context:
            self.validation_service.get_validation_session(99999)
        
        self.assertIn("Validation session with ID 99999 not found", str(context.exception))
    
    def test_get_validation_session_expired(self):
        """Test retrieval of expired validation session"""
        # Create session with past expiration
        past_time = timezone.now() - timedelta(hours=1)
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=past_time - timedelta(hours=24),
            expires_at=past_time,
            validation_status='pending'
        )
        
        with self.assertRaises(ValidationError) as context:
            self.validation_service.get_validation_session(session.id)
        
        self.assertIn("Validation session has expired", str(context.exception))
        
        # Check that session status was updated
        session.refresh_from_db()
        self.assertEqual(session.validation_status, 'expired')
    
    def test_submit_validation_response_success(self):
        """Test successful submission of validation response"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        response = {'confirmed': True, 'notes': 'Summary looks good'}
        
        updated_session = self.validation_service.submit_validation_response(
            session_id=session.id,
            question_id='summary_accuracy',
            response=response
        )
        
        self.assertEqual(updated_session.validation_status, 'in_progress')
        self.assertIn('summary_accuracy', updated_session.rep_responses)
        self.assertEqual(
            updated_session.rep_responses['summary_accuracy']['response'],
            response
        )
        
        # Check audit trail
        self.assertTrue(len(updated_session.changes_made) > 0)
        self.assertEqual(updated_session.changes_made[-1]['action'], 'response_submitted')
    
    def test_submit_validation_response_invalid_question(self):
        """Test submission with invalid question ID"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        with self.assertRaises(ValidationError) as context:
            self.validation_service.submit_validation_response(
                session_id=session.id,
                question_id='invalid_question',
                response={'confirmed': True}
            )
        
        self.assertIn("Question with ID invalid_question not found", str(context.exception))
    
    def test_submit_validation_response_completed_session(self):
        """Test submission to completed session"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        session.validation_status = 'completed'
        session.save()
        
        with self.assertRaises(ValidationError) as context:
            self.validation_service.submit_validation_response(
                session_id=session.id,
                question_id='summary_accuracy',
                response={'confirmed': True}
            )
        
        self.assertIn("Cannot submit responses to completed or expired session", str(context.exception))
    
    def test_validate_response_format_confirmation(self):
        """Test response format validation for confirmation questions"""
        question = {'type': 'confirmation', 'id': 'test'}
        
        # Valid response
        valid_response = {'confirmed': True}
        self.validation_service._validate_response_format(question, valid_response)
        
        # Invalid response - missing confirmed field
        with self.assertRaises(ValidationError):
            self.validation_service._validate_response_format(question, {})
        
        # Invalid response - wrong type
        with self.assertRaises(ValidationError):
            self.validation_service._validate_response_format(question, {'confirmed': 'yes'})
    
    def test_validate_response_format_multi_select(self):
        """Test response format validation for multi-select questions"""
        question = {'type': 'multi_select', 'id': 'test'}
        
        # Valid response
        valid_response = {'selected_options': ['option1', 'option2']}
        self.validation_service._validate_response_format(question, valid_response)
        
        # Invalid response - missing field
        with self.assertRaises(ValidationError):
            self.validation_service._validate_response_format(question, {})
        
        # Invalid response - wrong type
        with self.assertRaises(ValidationError):
            self.validation_service._validate_response_format(question, {'selected_options': 'option1'})
    
    def test_complete_validation_session_success(self):
        """Test successful completion of validation session"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Submit responses to all required questions
        required_questions = [q for q in session.validation_questions if q.get('required', False)]
        
        for question in required_questions:
            if question['type'] == 'confirmation':
                response = {'confirmed': True}
            elif question['type'] == 'multi_select':
                response = {'selected_options': question.get('options', [])}
            elif question['type'] == 'action_items_review':
                response = {'approved_items': question.get('items', [])}
            elif question['type'] == 'text_edit':
                response = {'text': 'Updated text'}
            elif question['type'] == 'crm_approval':
                response = {'approved': True}
            else:
                response = {'value': 'test'}
            
            self.validation_service.submit_validation_response(
                session_id=session.id,
                question_id=question['id'],
                response=response
            )
        
        # Complete the session
        completed_session, final_summary = self.validation_service.complete_validation_session(session.id)
        
        self.assertEqual(completed_session.validation_status, 'completed')
        self.assertIsNotNone(completed_session.completed_at)
        self.assertIsNotNone(final_summary)
        self.assertTrue(len(final_summary) > 0)
        self.assertIsNotNone(completed_session.approved_crm_updates)
    
    def test_complete_validation_session_missing_required(self):
        """Test completion with missing required responses"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Submit only one response
        self.validation_service.submit_validation_response(
            session_id=session.id,
            question_id='summary_accuracy',
            response={'confirmed': True}
        )
        
        with self.assertRaises(ValidationError) as context:
            self.validation_service.complete_validation_session(session.id)
        
        self.assertIn("Required questions not answered", str(context.exception))
    
    def test_complete_validation_session_wrong_status(self):
        """Test completion of session with wrong status"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        with self.assertRaises(ValidationError) as context:
            self.validation_service.complete_validation_session(session.id)
        
        self.assertIn("Can only complete sessions that are in progress", str(context.exception))
    
    def test_generate_final_summary(self):
        """Test final summary generation"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        # Add some responses
        session.rep_responses = {
            'summary_accuracy': {
                'response': {'confirmed': True},
                'timestamp': timezone.now().isoformat()
            },
            'key_points_validation': {
                'response': {'selected_options': ['Discussed pricing', 'Reviewed timeline']},
                'timestamp': timezone.now().isoformat()
            },
            'additional_notes': {
                'response': {'text': 'Client is very interested'},
                'timestamp': timezone.now().isoformat()
            }
        }
        
        final_summary = self.validation_service._generate_final_summary(session)
        
        self.assertIn(self.draft_summary.ai_generated_summary, final_summary)
        self.assertIn('Key Points:', final_summary)
        self.assertIn('Discussed pricing', final_summary)
        self.assertIn('Additional Notes:', final_summary)
        self.assertIn('Client is very interested', final_summary)
    
    def test_generate_approved_crm_updates(self):
        """Test approved CRM updates generation"""
        session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales@ourcompany.com"
        )
        
        session.rep_responses = {
            'crm_updates_approval': {
                'response': {'approved': True},
                'timestamp': timezone.now().isoformat()
            },
            'deal_stage_update': {
                'response': {'selected_stage': 'Proposal'},
                'timestamp': timezone.now().isoformat()
            }
        }
        session.validated_summary = "Final validated summary"
        
        approved_updates = self.validation_service._generate_approved_crm_updates(session)
        
        self.assertIn('deal_stage', approved_updates)
        self.assertEqual(approved_updates['deal_stage'], 'Proposal')
        self.assertIn('meeting_summary', approved_updates)
        self.assertEqual(approved_updates['meeting_summary'], "Final validated summary")
    
    def test_get_sessions_for_rep(self):
        """Test getting sessions for specific sales rep"""
        rep_email = "sales@ourcompany.com"
        
        # Create multiple sessions
        session1 = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email=rep_email
        )
        
        # Create a new bot session and draft summary for second session
        meeting2 = Meeting.objects.create(
            calendar_event_id="test_event_456",
            title="Second Meeting",
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now(),
            status="completed"
        )
        
        bot_session2 = CallBotSession.objects.create(
            meeting=meeting2,
            bot_session_id="bot_session_456",
            platform="teams",
            join_time=timezone.now() - timedelta(hours=1),
            connection_status="disconnected"
        )
        
        draft_summary2 = DraftSummary.objects.create(
            bot_session=bot_session2,
            ai_generated_summary="Second test summary",
            confidence_score=0.75
        )
        
        session2 = self.validation_service.create_validation_session(
            draft_summary_id=draft_summary2.id,
            sales_rep_email=rep_email
        )
        
        # Get sessions for rep
        sessions = self.validation_service.get_sessions_for_rep(rep_email)
        
        self.assertEqual(len(sessions), 2)
        self.assertIn(session1, sessions)
        self.assertIn(session2, sessions)
        
        # Test with status filter
        session1.validation_status = 'completed'
        session1.save()
        
        completed_sessions = self.validation_service.get_sessions_for_rep(rep_email, status='completed')
        self.assertEqual(len(completed_sessions), 1)
        self.assertEqual(completed_sessions[0], session1)
    
    def test_expire_old_sessions(self):
        """Test expiring old validation sessions"""
        # Create a separate draft summary for the expired session
        meeting2 = Meeting.objects.create(
            calendar_event_id="test_event_expired",
            title="Expired Meeting",
            start_time=timezone.now() - timedelta(hours=25),
            end_time=timezone.now() - timedelta(hours=24),
            status="completed"
        )
        
        bot_session2 = CallBotSession.objects.create(
            meeting=meeting2,
            bot_session_id="bot_session_expired",
            platform="meet",
            join_time=timezone.now() - timedelta(hours=25),
            connection_status="disconnected"
        )
        
        draft_summary2 = DraftSummary.objects.create(
            bot_session=bot_session2,
            ai_generated_summary="Expired test summary",
            confidence_score=0.75
        )
        
        # Create session with past expiration
        past_time = timezone.now() - timedelta(hours=1)
        expired_session = ValidationSession.objects.create(
            draft_summary=draft_summary2,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=past_time - timedelta(hours=24),
            expires_at=past_time,
            validation_status='pending'
        )
        
        # Create current session
        current_session = self.validation_service.create_validation_session(
            draft_summary_id=self.draft_summary.id,
            sales_rep_email="sales2@ourcompany.com"
        )
        
        # Expire old sessions
        expired_count = self.validation_service.expire_old_sessions()
        
        self.assertEqual(expired_count, 1)
        
        # Check that expired session status was updated
        expired_session.refresh_from_db()
        self.assertEqual(expired_session.validation_status, 'expired')
        
        # Check that current session was not affected
        current_session.refresh_from_db()
        self.assertEqual(current_session.validation_status, 'pending')
    
    def test_suggest_deal_stage(self):
        """Test deal stage suggestion logic"""
        # Test closed won
        self.draft_summary.ai_generated_summary = "We signed the contract today"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'Closed Won')
        
        # Test proposal
        self.draft_summary.ai_generated_summary = "Need to send pricing proposal"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'Proposal')
        
        # Test demo
        self.draft_summary.ai_generated_summary = "Scheduled product demo for next week"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'Demo Scheduled')
        
        # Test qualified
        self.draft_summary.ai_generated_summary = "Budget confirmed, timeline established"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'Qualified')
        
        # Test closed lost
        self.draft_summary.ai_generated_summary = "Not interested at this time"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'Closed Lost')
        
        # Test default
        self.draft_summary.ai_generated_summary = "General discussion about needs"
        stage = self.validation_service._suggest_deal_stage(self.draft_summary)
        self.assertEqual(stage, 'In Progress')