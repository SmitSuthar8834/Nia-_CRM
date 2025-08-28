"""
Integration tests for the complete validation workflow API
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


class ValidationWorkflowIntegrationTestCase(TestCase):
    """Integration test cases for the complete validation workflow"""
    
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
    
    def test_complete_validation_workflow(self):
        """Test the complete validation workflow from creation to completion"""
        
        # Step 1: Create validation session
        create_url = reverse('create-validation-session')
        create_data = {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com',
            'session_duration_hours': 24
        }
        
        create_response = self.client.post(create_url, create_data, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data['success'])
        
        session_id = create_response.data['validation_session']['id']
        
        # Step 2: Get validation questions
        questions_url = reverse('get-validation-questions', kwargs={'session_id': session_id})
        questions_response = self.client.get(questions_url)
        self.assertEqual(questions_response.status_code, status.HTTP_200_OK)
        
        questions = questions_response.data['validation_questions']
        self.assertTrue(len(questions) > 0)
        
        # Step 3: Submit responses to all questions
        for question in questions:
            response_url = reverse('submit-validation-response', kwargs={'session_id': session_id})
            
            # Create appropriate response based on question type
            if question['type'] == 'confirmation':
                response_payload = {'confirmed': True, 'notes': 'Test response'}
            elif question['type'] == 'text_edit':
                response_payload = {'text': question.get('suggested_text', 'Updated text'), 'notes': 'Test edit'}
            elif question['type'] == 'multi_select':
                response_payload = {'selected_options': ['option1'], 'notes': 'Test selection'}
            elif question['type'] == 'crm_field_update':
                response_payload = {'field_updates': {'stage': 'Proposal'}, 'notes': 'Test CRM update'}
            elif question['type'] == 'action_items_review':
                # Approve all action items from the question
                approved_items = question.get('items', [])
                response_payload = {'approved_items': approved_items, 'notes': 'All items approved'}
            elif question['type'] == 'crm_approval':
                response_payload = {'approved': True, 'updates': question.get('suggested_updates', {}), 'notes': 'CRM updates approved'}
            elif question['type'] == 'stage_selection':
                response_payload = {'selected_stage': question.get('suggested_stage', 'In Progress'), 'notes': 'Stage updated'}
            else:
                response_payload = {'confirmed': True, 'notes': 'Default response'}
            
            response_data = {
                'question_id': question['id'],
                'response': response_payload
            }
            
            submit_response = self.client.post(response_url, response_data, format='json')
            if submit_response.status_code != status.HTTP_200_OK:
                print(f"Question: {question}")
                print(f"Error submitting response: {submit_response.data}")
            self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(submit_response.data['success'])
        
        # Step 4: Check session status
        status_url = reverse('validation-session-status', kwargs={'session_id': session_id})
        status_response = self.client.get(status_url)
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        progress = status_response.data['progress']
        self.assertTrue(progress['can_complete'])
        
        # Step 5: Complete validation session
        complete_url = reverse('complete-validation-session', kwargs={'session_id': session_id})
        complete_response = self.client.post(complete_url)
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        self.assertTrue(complete_response.data['success'])
        
        # Verify session is completed
        final_session = ValidationSession.objects.get(id=session_id)
        self.assertEqual(final_session.validation_status, 'completed')
        self.assertIsNotNone(final_session.completed_at)
    
    def test_validation_session_status_tracking(self):
        """Test validation session status tracking and completion logic"""
        
        # Create validation session
        create_url = reverse('create-validation-session')
        create_data = {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com'
        }
        
        create_response = self.client.post(create_url, create_data, format='json')
        session_id = create_response.data['validation_session']['id']
        
        # Check initial status
        status_url = reverse('validation-session-status', kwargs={'session_id': session_id})
        status_response = self.client.get(status_url)
        
        progress = status_response.data['progress']
        self.assertEqual(progress['answered_questions'], 0)
        self.assertFalse(progress['can_complete'])
        
        # Submit one response
        questions_url = reverse('get-validation-questions', kwargs={'session_id': session_id})
        questions_response = self.client.get(questions_url)
        first_question = questions_response.data['validation_questions'][0]
        
        response_url = reverse('submit-validation-response', kwargs={'session_id': session_id})
        response_data = {
            'question_id': first_question['id'],
            'response': {'confirmed': True}
        }
        
        self.client.post(response_url, response_data, format='json')
        
        # Check updated status
        status_response = self.client.get(status_url)
        progress = status_response.data['progress']
        self.assertEqual(progress['answered_questions'], 1)
    
    def test_validation_session_expiration(self):
        """Test validation session expiration functionality"""
        
        # Create expired session manually
        expired_session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[
                {"id": "test_question", "type": "confirmation", "question": "Test?", "required": True}
            ],
            started_at=timezone.now() - timedelta(hours=25),
            expires_at=timezone.now() - timedelta(hours=1),
            validation_status='pending'
        )
        
        # Test expiration endpoint
        expire_url = reverse('expire-old-validation-sessions')
        expire_response = self.client.post(expire_url)
        
        self.assertEqual(expire_response.status_code, status.HTTP_200_OK)
        self.assertTrue(expire_response.data['success'])
        self.assertEqual(expire_response.data['expired_sessions'], 1)
        
        # Verify session was marked as expired
        expired_session.refresh_from_db()
        self.assertEqual(expired_session.validation_status, 'expired')
    
    def test_validation_session_list_filtering(self):
        """Test validation session listing with filters"""
        
        # Create multiple sessions with different statuses
        session1 = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        # Create another draft summary for second session
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
            validation_status='completed',
            completed_at=timezone.now()
        )
        
        # Test listing all sessions for rep
        list_url = reverse('list-validation-sessions')
        list_response = self.client.get(list_url, {'sales_rep_email': 'sales@ourcompany.com'})
        
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 2)
        
        # Test filtering by status
        pending_response = self.client.get(list_url, {
            'sales_rep_email': 'sales@ourcompany.com',
            'status': 'pending'
        })
        
        self.assertEqual(pending_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pending_response.data['count'], 1)
        
        completed_response = self.client.get(list_url, {
            'sales_rep_email': 'sales@ourcompany.com',
            'status': 'completed'
        })
        
        self.assertEqual(completed_response.status_code, status.HTTP_200_OK)
        self.assertEqual(completed_response.data['count'], 1)
    
    def test_validation_session_update(self):
        """Test updating validation session metadata"""
        
        # Create validation session
        session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email="sales@ourcompany.com",
            validation_questions=[],
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=24),
            validation_status='pending'
        )
        
        # Test updating session
        update_url = reverse('update-validation-session', kwargs={'session_id': session.id})
        update_data = {
            'validated_summary': 'Updated final summary',
            'approved_crm_updates': {'stage': 'Closed Won'}
        }
        
        update_response = self.client.put(update_url, update_data, format='json')
        
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(update_response.data['success'])
        
        # Verify updates were saved
        session.refresh_from_db()
        self.assertEqual(session.validated_summary, 'Updated final summary')
        self.assertEqual(session.approved_crm_updates['stage'], 'Closed Won')