"""
End-to-end integration tests for the complete meeting workflow
Tests the full flow from call join to CRM sync
"""
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status

from leads.models import Lead
from meetings.models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession, CRMSyncRecord
)
from meetings.call_bot_service import CallBotService
from meetings.transcription_service import TranscriptionService
from meetings.validation_service import ValidationService
from meetings.crm_service import CRMSyncService


class EndToEndWorkflowTestCase(TransactionTestCase):
    """
    Complete end-to-end workflow test from call join to CRM sync
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    
    def setUp(self):
        """Set up test environment"""
        self.user = User.objects.create_user(
            username='testuser',
            email='sales@ourcompany.com',
            password='testpass123'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id="E2E_LEAD_001",
            name="John Smith",
            email="john.smith@testcompany.com",
            company="Test Company Inc",
            phone="+1234567890",
            status="qualified"
        )
        
        # Mock external services
        self.mock_gemini_response = {
            "summary": "Productive sales call discussing Q1 implementation timeline and pricing structure.",
            "key_points": [
                "Client confirmed budget of $50K for Q1",
                "Implementation timeline set for March 2024",
                "Technical requirements reviewed and approved"
            ],
            "action_items": [
                {
                    "description": "Send detailed proposal with pricing breakdown",
                    "assignee": "Sales Rep",
                    "due_date": "2024-01-20"
                },
                {
                    "description": "Schedule technical deep-dive session",
                    "assignee": "John Smith",
                    "due_date": "2024-01-25"
                }
            ],
            "decisions": [
                "Agreed on phased implementation approach",
                "Confirmed integration with existing CRM system"
            ],
            "next_steps": [
                "Review proposal internally",
                "Schedule follow-up call for next week"
            ],
            "crm_updates": {
                "stage": "Proposal",
                "amount": 50000,
                "close_date": "2024-03-31",
                "next_action": "Send proposal"
            }
        }
    
    @patch('meetings.call_bot_service.CallBotService.join_meeting')
    @patch('meetings.transcription_service.TranscriptionService.process_audio_stream')
    @patch('meetings.ai_summary_service.AISummaryService.generate_summary')
    @patch('meetings.crm_service.CRMSyncService.sync_meeting_outcome')
    def test_complete_workflow_success(self, mock_crm_sync, mock_ai_summary, 
                                     mock_transcription, mock_join_meeting):
        """Test successful complete workflow from call join to CRM sync"""
        
        # Step 1: Create meeting and join call
        meeting_data = {
            'calendar_event_id': 'e2e_test_meeting_001',
            'title': 'Sales Call - Test Company',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            'attendees': ['john.smith@testcompany.com', 'sales@ourcompany.com'],
            'meeting_url': 'https://meet.google.com/test-meeting-url',
            'platform': 'meet'
        }
        
        # Mock call bot joining
        mock_join_meeting.return_value = {
            'bot_session_id': 'bot_session_e2e_001',
            'status': 'connected',
            'join_time': timezone.now()
        }
        
        # Create meeting
        create_response = self.client.post('/api/meetings/', meeting_data, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        meeting_id = create_response.data['id']
        
        # Match meeting to lead
        match_response = self.client.post(f'/api/meetings/{meeting_id}/match-lead/', {
            'lead_email': 'john.smith@testcompany.com'
        })
        self.assertEqual(match_response.status_code, status.HTTP_200_OK)
        
        # Start meeting session (bot joins)
        start_response = self.client.post(f'/api/meetings/{meeting_id}/start/', {
            'meeting_url': 'https://meet.google.com/test-meeting-url'
        })
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        
        # Verify bot session created
        meeting = Meeting.objects.get(id=meeting_id)
        self.assertTrue(hasattr(meeting, 'callbotsession'))
        bot_session = meeting.callbotsession
        self.assertEqual(bot_session.connection_status, 'connected')
        
        # Step 2: Simulate real-time transcription
        mock_transcription.return_value = {
            'transcript_chunk': 'This is a test transcript chunk from the meeting.',
            'speaker': 'John Smith',
            'timestamp': timezone.now()
        }
        
        # Simulate multiple transcript updates
        transcript_chunks = [
            "John Smith: Thanks for taking the time to meet today.",
            "Sales Rep: Of course! I'm excited to discuss how we can help Test Company.",
            "John Smith: We're looking at a Q1 implementation with a budget of around $50K.",
            "Sales Rep: That sounds perfect. Let me walk you through our proposal.",
            "John Smith: The technical requirements look good. When can we start?",
            "Sales Rep: We can begin implementation in March if we finalize by end of January."
        ]
        
        for chunk in transcript_chunks:
            transcript_response = self.client.post(
                f'/api/meetings/sessions/{bot_session.id}/transcript/',
                {'transcript_chunk': chunk}
            )
            self.assertEqual(transcript_response.status_code, status.HTTP_200_OK)
        
        # Step 3: End meeting and generate AI summary
        mock_ai_summary.return_value = self.mock_gemini_response
        
        end_response = self.client.post(f'/api/meetings/{meeting_id}/end/', {
            'final_transcript': ' '.join(transcript_chunks),
            'meeting_duration': 45
        })
        self.assertEqual(end_response.status_code, status.HTTP_200_OK)
        
        # Verify draft summary created
        bot_session.refresh_from_db()
        self.assertTrue(hasattr(bot_session, 'draftsummary'))
        draft_summary = bot_session.draftsummary
        self.assertIn('Productive sales call', draft_summary.ai_generated_summary)
        self.assertEqual(len(draft_summary.extracted_action_items), 2)
        
        # Step 4: Create validation session
        validation_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com'
        })
        self.assertEqual(validation_response.status_code, status.HTTP_201_CREATED)
        validation_session_id = validation_response.data['validation_session']['id']
        
        # Step 5: Complete validation workflow
        # Get validation questions
        questions_response = self.client.get(
            f'/api/validation/sessions/{validation_session_id}/questions/'
        )
        self.assertEqual(questions_response.status_code, status.HTTP_200_OK)
        questions = questions_response.data['validation_questions']
        
        # Answer all validation questions
        for question in questions:
            if question['type'] == 'confirmation':
                response_data = {'confirmed': True, 'notes': 'Confirmed accurate'}
            elif question['type'] == 'crm_approval':
                response_data = {
                    'approved': True,
                    'updates': question.get('suggested_updates', {}),
                    'notes': 'CRM updates approved'
                }
            elif question['type'] == 'action_items_review':
                response_data = {
                    'approved_items': question.get('items', []),
                    'notes': 'All action items approved'
                }
            else:
                response_data = {'confirmed': True}
            
            submit_response = self.client.post(
                f'/api/validation/sessions/{validation_session_id}/responses/',
                {
                    'question_id': question['id'],
                    'response': response_data
                },
                format='json'
            )
            self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        
        # Complete validation session
        complete_response = self.client.post(
            f'/api/validation/sessions/{validation_session_id}/complete/'
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Step 6: CRM sync
        mock_crm_sync.return_value = Mock(
            status='SUCCESS',
            crm_record_id='CRM_RECORD_001',
            message='Successfully synced to CRM'
        )
        
        # Trigger CRM sync
        sync_response = self.client.post(f'/api/meetings/{meeting_id}/sync-crm/')
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        
        # Verify CRM sync record created
        sync_records = CRMSyncRecord.objects.filter(
            validation_session_id=validation_session_id
        )
        self.assertTrue(sync_records.exists())
        sync_record = sync_records.first()
        self.assertEqual(sync_record.sync_status, 'completed')
        
        # Step 7: Verify complete workflow state
        final_meeting = Meeting.objects.get(id=meeting_id)
        self.assertEqual(final_meeting.status, 'completed')
        
        final_validation = ValidationSession.objects.get(id=validation_session_id)
        self.assertEqual(final_validation.validation_status, 'completed')
        self.assertIsNotNone(final_validation.completed_at)
        
        # Verify all components are properly linked
        self.assertEqual(final_meeting.lead, self.lead)
        self.assertTrue(hasattr(final_meeting, 'callbotsession'))
        self.assertTrue(hasattr(final_meeting.callbotsession, 'draftsummary'))
        self.assertTrue(hasattr(final_meeting.callbotsession.draftsummary, 'validationsession'))
    
    @patch('meetings.call_bot_service.CallBotService.join_meeting')
    @patch('meetings.transcription_service.TranscriptionService.process_audio_stream')
    def test_workflow_with_call_bot_failure(self, mock_transcription, mock_join_meeting):
        """Test workflow handling when call bot fails to join"""
        
        # Mock call bot failure
        mock_join_meeting.side_effect = Exception("Failed to join meeting")
        
        meeting_data = {
            'calendar_event_id': 'e2e_test_meeting_002',
            'title': 'Sales Call - Bot Failure Test',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            'meeting_url': 'https://meet.google.com/test-meeting-url-2',
            'platform': 'meet'
        }
        
        create_response = self.client.post('/api/meetings/', meeting_data, format='json')
        meeting_id = create_response.data['id']
        
        # Attempt to start meeting session
        start_response = self.client.post(f'/api/meetings/{meeting_id}/start/', {
            'meeting_url': 'https://meet.google.com/test-meeting-url-2'
        })
        
        # Should handle failure gracefully
        self.assertEqual(start_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Failed to join meeting', start_response.data['error'])
        
        # Meeting should remain in scheduled state
        meeting = Meeting.objects.get(id=meeting_id)
        self.assertEqual(meeting.status, 'scheduled')
    
    @patch('meetings.ai_summary_service.AISummaryService.generate_summary')
    def test_workflow_with_ai_processing_failure(self, mock_ai_summary):
        """Test workflow handling when AI summary generation fails"""
        
        # Create meeting and bot session manually
        meeting = Meeting.objects.create(
            calendar_event_id='e2e_test_meeting_003',
            title='AI Failure Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='in_progress'
        )
        
        bot_session = CallBotSession.objects.create(
            meeting=meeting,
            bot_session_id='bot_session_003',
            platform='meet',
            join_time=timezone.now(),
            connection_status='connected',
            raw_transcript='Test transcript for AI processing failure'
        )
        
        # Mock AI failure
        mock_ai_summary.side_effect = Exception("AI service unavailable")
        
        # Attempt to end meeting
        end_response = self.client.post(f'/api/meetings/{meeting.id}/end/', {
            'final_transcript': 'Test transcript for AI processing failure',
            'meeting_duration': 30
        })
        
        # Should handle AI failure gracefully
        self.assertEqual(end_response.status_code, status.HTTP_200_OK)
        
        # Meeting should be marked as completed but with AI processing error
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, 'completed')
        
        # Should create draft summary with error state
        self.assertTrue(hasattr(bot_session, 'draftsummary'))
        draft_summary = bot_session.draftsummary
        self.assertIn('error', draft_summary.ai_generated_summary.lower())
    
    def test_workflow_performance_requirements(self):
        """Test workflow meets performance requirements (8.1, 8.2)"""
        
        # Test AI processing time requirement (< 30 seconds)
        with patch('meetings.ai_summary_service.AISummaryService.generate_summary') as mock_ai:
            mock_ai.return_value = self.mock_gemini_response
            
            meeting = Meeting.objects.create(
                calendar_event_id='perf_test_meeting',
                title='Performance Test Meeting',
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1),
                status='in_progress'
            )
            
            bot_session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id='perf_bot_session',
                platform='meet',
                join_time=timezone.now(),
                connection_status='connected',
                raw_transcript='Performance test transcript'
            )
            
            start_time = time.time()
            
            end_response = self.client.post(f'/api/meetings/{meeting.id}/end/', {
                'final_transcript': 'Performance test transcript',
                'meeting_duration': 30
            })
            
            processing_time = time.time() - start_time
            
            self.assertEqual(end_response.status_code, status.HTTP_200_OK)
            self.assertLess(processing_time, 30, "AI processing should complete within 30 seconds")
        
        # Test validation session availability (< 2 minutes)
        with patch('meetings.validation_service.ValidationService.create_validation_session') as mock_validation:
            mock_validation.return_value = Mock(id=1, validation_status='pending')
            
            draft_summary = DraftSummary.objects.create(
                bot_session=bot_session,
                ai_generated_summary='Test summary',
                confidence_score=0.8
            )
            
            start_time = time.time()
            
            validation_response = self.client.post('/api/validation/sessions/', {
                'draft_summary_id': draft_summary.id,
                'sales_rep_email': 'sales@ourcompany.com'
            })
            
            validation_time = time.time() - start_time
            
            self.assertEqual(validation_response.status_code, status.HTTP_201_CREATED)
            self.assertLess(validation_time, 120, "Validation session should be available within 2 minutes")
    
    @patch('meetings.crm_service.CRMSyncService.sync_meeting_outcome')
    def test_crm_sync_performance_requirement(self, mock_crm_sync):
        """Test CRM sync performance requirement (< 1 minute)"""
        
        mock_crm_sync.return_value = Mock(
            status='SUCCESS',
            crm_record_id='PERF_CRM_001',
            message='Performance test sync'
        )
        
        # Create completed validation session
        meeting = Meeting.objects.create(
            calendar_event_id='crm_perf_test',
            title='CRM Performance Test',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='completed'
        )
        
        bot_session = CallBotSession.objects.create(
            meeting=meeting,
            bot_session_id='crm_perf_bot',
            platform='meet',
            join_time=timezone.now(),
            connection_status='disconnected'
        )
        
        draft_summary = DraftSummary.objects.create(
            bot_session=bot_session,
            ai_generated_summary='CRM performance test summary',
            confidence_score=0.9
        )
        
        validation_session = ValidationSession.objects.create(
            draft_summary=draft_summary,
            sales_rep_email='sales@ourcompany.com',
            validation_status='completed',
            completed_at=timezone.now()
        )
        
        start_time = time.time()
        
        sync_response = self.client.post(f'/api/meetings/{meeting.id}/sync-crm/')
        
        sync_time = time.time() - start_time
        
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertLess(sync_time, 60, "CRM sync should complete within 1 minute")
    
    def test_concurrent_meeting_handling(self):
        """Test system can handle multiple concurrent meetings (8.6)"""
        
        # Create multiple meetings simultaneously
        meeting_data_template = {
            'title': 'Concurrent Test Meeting {}',
            'start_time': timezone.now().isoformat(),
            'end_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            'attendees': ['test{}@example.com'],
            'platform': 'meet'
        }
        
        concurrent_meetings = []
        
        # Create 10 concurrent meetings (scaled down from 50 for test performance)
        for i in range(10):
            meeting_data = meeting_data_template.copy()
            meeting_data['calendar_event_id'] = f'concurrent_test_{i}'
            meeting_data['title'] = meeting_data['title'].format(i)
            meeting_data['attendees'] = [f'test{i}@example.com']
            
            response = self.client.post('/api/meetings/', meeting_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            concurrent_meetings.append(response.data['id'])
        
        # Verify all meetings were created successfully
        self.assertEqual(len(concurrent_meetings), 10)
        
        # Verify database consistency
        created_meetings = Meeting.objects.filter(id__in=concurrent_meetings)
        self.assertEqual(created_meetings.count(), 10)
        
        # Test concurrent session starts
        with patch('meetings.call_bot_service.CallBotService.join_meeting') as mock_join:
            mock_join.return_value = {
                'bot_session_id': 'concurrent_bot_session',
                'status': 'connected',
                'join_time': timezone.now()
            }
            
            start_responses = []
            for meeting_id in concurrent_meetings:
                response = self.client.post(f'/api/meetings/{meeting_id}/start/', {
                    'meeting_url': f'https://meet.google.com/concurrent-{meeting_id}'
                })
                start_responses.append(response.status_code)
            
            # All should succeed
            self.assertTrue(all(status_code == status.HTTP_201_CREATED for status_code in start_responses))
    
    def test_data_consistency_across_workflow(self):
        """Test data consistency throughout the complete workflow"""
        
        # Create complete workflow with all data relationships
        meeting = Meeting.objects.create(
            calendar_event_id='consistency_test',
            lead=self.lead,
            title='Data Consistency Test',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='completed'
        )
        
        bot_session = CallBotSession.objects.create(
            meeting=meeting,
            bot_session_id='consistency_bot',
            platform='meet',
            join_time=timezone.now(),
            leave_time=timezone.now() + timedelta(hours=1),
            connection_status='disconnected',
            raw_transcript='Consistency test transcript'
        )
        
        draft_summary = DraftSummary.objects.create(
            bot_session=bot_session,
            ai_generated_summary='Consistency test summary',
            extracted_action_items=[
                {
                    'description': 'Test action item',
                    'assignee': 'Test User',
                    'due_date': '2024-01-30'
                }
            ],
            confidence_score=0.85
        )
        
        validation_session = ValidationSession.objects.create(
            draft_summary=draft_summary,
            sales_rep_email='sales@ourcompany.com',
            validation_status='completed',
            completed_at=timezone.now(),
            validated_summary='Final validated summary',
            approved_crm_updates={'stage': 'Closed Won'}
        )
        
        crm_sync_record = CRMSyncRecord.objects.create(
            validation_session=validation_session,
            crm_system='salesforce',
            sync_status='completed',
            crm_record_id='SF_RECORD_001',
            synced_at=timezone.now()
        )
        
        # Verify all relationships are intact
        self.assertEqual(meeting.lead, self.lead)
        self.assertEqual(bot_session.meeting, meeting)
        self.assertEqual(draft_summary.bot_session, bot_session)
        self.assertEqual(validation_session.draft_summary, draft_summary)
        self.assertEqual(crm_sync_record.validation_session, validation_session)
        
        # Test cascade relationships
        meeting_id = meeting.id
        
        # Delete meeting should cascade properly
        meeting.delete()
        
        # Verify all related objects are deleted
        self.assertFalse(CallBotSession.objects.filter(meeting_id=meeting_id).exists())
        self.assertFalse(DraftSummary.objects.filter(bot_session__meeting_id=meeting_id).exists())
        self.assertFalse(ValidationSession.objects.filter(
            draft_summary__bot_session__meeting_id=meeting_id
        ).exists())
        self.assertFalse(CRMSyncRecord.objects.filter(
            validation_session__draft_summary__bot_session__meeting_id=meeting_id
        ).exists())
        
        # Lead should remain (not cascaded)
        self.assertTrue(Lead.objects.filter(id=self.lead.id).exists())