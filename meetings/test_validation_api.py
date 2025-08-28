"""
Tests for validation session API endpoints
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
    Meeting, CallBotSession, DraftSummary, ValidationSession
)


class ValidationSessionAPITestCase(TestCase):
    """Test cases for ValidationSession API endpoints"""
    
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
    
    def test_create_validation_session_success(self):
        """Test successful creation of validation session"""
        url = reverse('create-validation-session')
        data = {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com',
            'session_duration_hours': 12
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('validation_session', response.data)
        
        # Check that session was created in database
        session = ValidationSession.objects.get(draft_summary=self.draft_summary)
        self.assertEqual(session.sales_rep_email, 'sales@ourcompany.com')
        self.assertEqual(session.validation_status, 'pending')
        self.assertTrue(len(session.validation_questions) > 0)
    
    def test_create_validation_session_invalid_data(self):
        """Test creation with invalid data"""
        url = reverse('create-validation-session')
        data = {
            'draft_summary_id': 99999,  # Non-existent ID
            'sales_rep_email': 'invalid-email',  # Invalid email
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_validation_session_success(self):
        """Test successful retrieval of validation session"""
        # Create validation session first
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {"id": "test_question", "type": "confirmation", "question": "Test?"}
            ],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('get-validation-session', kwargs={'session_id': session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], session.id)
        self.assertEqual(response.data['sales_rep_email'], 'sales@ourcompany.com')
        self.assertIn('meeting_info', response.data)
    
    def test_get_validation_session_not_found(self):
        """Test retrieval of non-existent validation session"""
        url = reverse('get-validation-session', kwargs={'session_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_list_validation_sessions_success(self):
        """Test listing validation sessions for a sales rep"""
        # Create multiple validation sessions
        session1 = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        # Create another draft summary and session
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
        
        session2 = ValidationSession.objects.create(
            draft_summary=draft_summary2,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='completed'
        )
        
        url = reverse('list-validation-sessions')
        response = self.client.get(url, {'sales_rep_email': 'sales@ourcompany.com'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['sessions']), 2)
        
        # Test with status filter
        response = self.client.get(url, {
            'sales_rep_email': 'sales@ourcompany.com',
            'status': 'pending'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
    
    def test_list_validation_sessions_missing_email(self):
        """Test listing without sales_rep_email parameter"""
        url = reverse('list-validation-sessions')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sales_rep_email parameter is required', response.data['error'])
    
    def test_submit_validation_response_success(self):
        """Test successful submission of validation response"""
        # Create validation session
        session = ValidationSession.objects.create(
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
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('submit-validation-response', kwargs={'session_id': session.id})
        data = {
            'question_id': 'summary_accuracy',
            'response': {'confirmed': True, 'notes': 'Looks good'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('validation_session', response.data)
        
        # Check that response was saved
        session.refresh_from_db()
        self.assertIn('summary_accuracy', session.rep_responses)
        self.assertEqual(session.validation_status, 'in_progress')
    
    def test_submit_validation_response_invalid_question(self):
        """Test submission with invalid question ID"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {"id": "valid_question", "type": "confirmation", "question": "Test?"}
            ],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('submit-validation-response', kwargs={'session_id': session.id})
        data = {
            'question_id': 'invalid_question',
            'response': {'confirmed': True}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_complete_validation_session_success(self):
        """Test successful completion of validation session"""
        # Create validation session with responses
        session = ValidationSession.objects.create(
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
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='in_progress'
        )
        
        url = reverse('complete-validation-session', kwargs={'session_id': session.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('final_summary', response.data)
        
        # Check that session was completed
        session.refresh_from_db()
        self.assertEqual(session.validation_status, 'completed')
        self.assertIsNotNone(session.completed_at)
    
    def test_complete_validation_session_missing_required(self):
        """Test completion with missing required responses"""
        session = ValidationSession.objects.create(
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
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='in_progress'
        )
        
        url = reverse('complete-validation-session', kwargs={'session_id': session.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_validation_questions(self):
        """Test getting validation questions for a session"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {
                    "id": "test_question",
                    "type": "confirmation",
                    "question": "Test question?",
                    "required": True
                }
            ],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('get-validation-questions', kwargs={'session_id': session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], session.id)
        self.assertEqual(len(response.data['validation_questions']), 1)
        self.assertEqual(response.data['validation_status'], 'pending')
    
    def test_get_validation_responses(self):
        """Test getting validation responses for a session"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            rep_responses={
                'test_question': {
                    'response': {'confirmed': True},
                    'timestamp': timezone.now().isoformat()
                }
            },
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='in_progress'
        )
        
        url = reverse('get-validation-responses', kwargs={'session_id': session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], session.id)
        self.assertIn('test_question', response.data['rep_responses'])
    
    def test_update_validation_session(self):
        """Test updating validation session metadata"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('update-validation-session', kwargs={'session_id': session.id})
        data = {
            'validated_summary': 'Updated final summary',
            'approved_crm_updates': {'stage': 'Closed Won'}
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check that session was updated
        session.refresh_from_db()
        self.assertEqual(session.validated_summary, 'Updated final summary')
        self.assertEqual(session.approved_crm_updates['stage'], 'Closed Won')
    
    def test_validation_session_status(self):
        """Test getting validation session status and progress"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {
                    "id": "question1",
                    "type": "confirmation",
                    "question": "Question 1?",
                    "required": True
                },
                {
                    "id": "question2",
                    "type": "text_edit",
                    "question": "Question 2?",
                    "required": False
                }
            ],
            rep_responses={
                'question1': {
                    'response': {'confirmed': True},
                    'timestamp': timezone.now().isoformat()
                }
            },
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='in_progress'
        )
        
        url = reverse('validation-session-status', kwargs={'session_id': session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session_id'], session.id)
        self.assertEqual(response.data['validation_status'], 'in_progress')
        
        progress = response.data['progress']
        self.assertEqual(progress['total_questions'], 2)
        self.assertEqual(progress['required_questions'], 1)
        self.assertEqual(progress['answered_questions'], 1)
        self.assertEqual(progress['answered_required'], 1)
        self.assertTrue(progress['can_complete'])
    
    def test_expire_old_validation_sessions(self):
        """Test manual expiration of old validation sessions"""
        # Create expired session
        past_time = timezone.now() - timedelta(hours=1)
        expired_session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=past_time - timedelta(hours=24),
            expires_at=past_time,
            validation_status='pending'
        )
        
        url = reverse('expire-old-validation-sessions')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['expired_sessions'], 1)
        
        # Check that session was marked as expired
        expired_session.refresh_from_db()
        self.assertEqual(expired_session.validation_status, 'expired')
    
    def test_authentication_required(self):
        """Test that authentication is required for all endpoints"""
        # Create unauthenticated client
        unauth_client = APIClient()
        
        # Test a few endpoints
        urls = [
            reverse('create-validation-session'),
            reverse('list-validation-sessions'),
            reverse('expire-old-validation-sessions'),
        ]
        
        for url in urls:
            response = unauth_client.get(url)
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
    
    def test_validation_session_serialization(self):
        """Test that validation session data is properly serialized"""
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {
                    "id": "test_question",
                    "type": "confirmation",
                    "question": "Test question?",
                    "required": True
                }
            ],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        url = reverse('get-validation-session', kwargs={'session_id': session.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that all expected fields are present
        expected_fields = [
            'id', 'draft_summary', 'sales_rep_email', 'validation_questions',
            'rep_responses', 'validated_summary', 'approved_crm_updates',
            'validation_status', 'changes_made', 'started_at', 'completed_at',
            'expires_at', 'is_expired', 'time_remaining', 'meeting_info'
        ]
        
        for field in expected_fields:
            self.assertIn(field, response.data)
        
        # Check meeting info structure
        meeting_info = response.data['meeting_info']
        self.assertIn('id', meeting_info)
        self.assertIn('title', meeting_info)
        self.assertIn('lead', meeting_info)
        
        # Check draft summary structure
        draft_summary_data = response.data['draft_summary']
        self.assertIn('ai_generated_summary', draft_summary_data)
        self.assertIn('confidence_score', draft_summary_data)