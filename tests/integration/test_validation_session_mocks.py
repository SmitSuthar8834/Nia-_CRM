"""
Integration tests for validation session with mock user interactions
Tests the complete validation workflow with simulated user responses
"""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from leads.models import Lead
from meetings.models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession
)
from meetings.validation_service import ValidationService


class MockUserValidationTestCase(TestCase):
    """
    Integration tests with mock user interactions for validation sessions
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
        
        self.validation_service = ValidationService()
        
        # Create comprehensive test data
        self.lead = Lead.objects.create(
            crm_id="MOCK_LEAD_001",
            name="Sarah Johnson",
            email="sarah.johnson@techcorp.com",
            company="TechCorp Solutions",
            phone="+1555123456",
            status="qualified"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="mock_validation_meeting",
            lead=self.lead,
            title="Discovery Call - TechCorp Solutions",
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            attendees=["sarah.johnson@techcorp.com", "sales@ourcompany.com"],
            status="completed"
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="mock_validation_bot",
            platform="teams",
            join_time=timezone.now() - timedelta(hours=2),
            leave_time=timezone.now() - timedelta(hours=1),
            connection_status="disconnected",
            raw_transcript=self._get_sample_transcript(),
            speaker_mapping={
                "speaker_1": "Sarah Johnson",
                "speaker_2": "Sales Rep"
            }
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary=self._get_sample_summary(),
            key_points=self._get_sample_key_points(),
            extracted_action_items=self._get_sample_action_items(),
            suggested_next_steps=self._get_sample_next_steps(),
            decisions_made=self._get_sample_decisions(),
            suggested_crm_updates=self._get_sample_crm_updates(),
            confidence_score=0.87
        )
    
    def _get_sample_transcript(self):
        """Get sample meeting transcript"""
        return """
        Sales Rep: Good morning Sarah, thanks for taking the time to meet with us today.
        Sarah Johnson: Good morning! I'm excited to learn more about your solution.
        Sales Rep: Great! Can you tell me about your current challenges with project management?
        Sarah Johnson: We're struggling with team coordination and deadline tracking. Our current tools are fragmented.
        Sales Rep: I understand. How many team members would be using the system?
        Sarah Johnson: We have about 50 people across 5 departments who would need access.
        Sales Rep: Perfect. Our enterprise solution would be ideal for your needs. The pricing starts at $15 per user per month.
        Sarah Johnson: That sounds reasonable. What's the implementation timeline?
        Sales Rep: Typically 4-6 weeks for full deployment. We can start with a pilot program if you prefer.
        Sarah Johnson: I'd like to discuss this with my team. Can you send me a detailed proposal?
        Sales Rep: Absolutely. I'll have that to you by Friday. Should we schedule a follow-up for next week?
        Sarah Johnson: Yes, let's plan for Tuesday afternoon.
        """
    
    def _get_sample_summary(self):
        """Get sample AI-generated summary"""
        return """
        Productive discovery call with TechCorp Solutions discussing project management challenges and solution fit.
        
        Key Discussion Points:
        - Current pain points: fragmented tools, poor team coordination, deadline tracking issues
        - Team size: 50 users across 5 departments
        - Budget considerations: $15/user/month pricing discussed and well-received
        - Implementation approach: 4-6 week timeline, option for pilot program
        - Decision process: Sarah needs to discuss with team before proceeding
        
        Meeting Outcome: Positive engagement, clear next steps established
        """
    
    def _get_sample_key_points(self):
        """Get sample key points"""
        return [
            "TechCorp has 50 users across 5 departments needing project management solution",
            "Current challenges: fragmented tools, poor coordination, deadline tracking",
            "Pricing of $15/user/month was well-received",
            "Implementation timeline: 4-6 weeks with pilot option available",
            "Decision maker needs to consult with team before proceeding"
        ]
    
    def _get_sample_action_items(self):
        """Get sample action items"""
        return [
            {
                "description": "Send detailed proposal with pricing breakdown",
                "assignee": "Sales Rep",
                "due_date": "2024-01-19",
                "priority": "High"
            },
            {
                "description": "Review proposal with internal team",
                "assignee": "Sarah Johnson",
                "due_date": "2024-01-22",
                "priority": "High"
            },
            {
                "description": "Schedule follow-up call for Tuesday afternoon",
                "assignee": "Sales Rep",
                "due_date": "2024-01-23",
                "priority": "Medium"
            }
        ]
    
    def _get_sample_next_steps(self):
        """Get sample next steps"""
        return [
            "Prepare comprehensive proposal including ROI analysis",
            "Include pilot program details and timeline",
            "Schedule follow-up meeting for next Tuesday",
            "Prepare technical requirements documentation"
        ]
    
    def _get_sample_decisions(self):
        """Get sample decisions made"""
        return [
            "Agreed on enterprise solution approach for 50 users",
            "Confirmed $15/user/month pricing is within budget range",
            "Decided on 4-6 week implementation timeline",
            "Established Tuesday follow-up meeting schedule"
        ]
    
    def _get_sample_crm_updates(self):
        """Get sample CRM updates"""
        return {
            "stage": "Proposal/Price Quote",
            "amount": 9000,  # 50 users * $15 * 12 months
            "close_date": "2024-02-15",
            "next_action": "Send proposal",
            "probability": 65,
            "competitor": "None identified",
            "decision_criteria": "Team coordination, ease of use, implementation speed"
        }
    
    def test_complete_validation_workflow_with_mock_user(self):
        """Test complete validation workflow with simulated user interactions"""
        
        # Step 1: Create validation session
        create_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com',
            'session_duration_hours': 24
        })
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        session_id = create_response.data['validation_session']['id']
        
        # Step 2: Get validation questions
        questions_response = self.client.get(
            f'/api/validation/sessions/{session_id}/questions/'
        )
        self.assertEqual(questions_response.status_code, status.HTTP_200_OK)
        questions = questions_response.data['validation_questions']
        
        # Step 3: Simulate user responses to each question type
        user_responses = self._simulate_user_responses(questions)
        
        # Step 4: Submit all responses
        for question_id, response_data in user_responses.items():
            submit_response = self.client.post(
                f'/api/validation/sessions/{session_id}/responses/',
                {
                    'question_id': question_id,
                    'response': response_data
                },
                format='json'
            )
            
            self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
            self.assertTrue(submit_response.data['success'])
        
        # Step 5: Check session completion status
        status_response = self.client.get(
            f'/api/validation/sessions/{session_id}/status/'
        )
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        
        progress = status_response.data['progress']
        self.assertTrue(progress['can_complete'])
        self.assertEqual(progress['answered_questions'], len(questions))
        
        # Step 6: Complete validation session
        complete_response = self.client.post(
            f'/api/validation/sessions/{session_id}/complete/'
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Step 7: Verify final state
        final_session = ValidationSession.objects.get(id=session_id)
        self.assertEqual(final_session.validation_status, 'completed')
        self.assertIsNotNone(final_session.completed_at)
        self.assertIsNotNone(final_session.validated_summary)
        self.assertTrue(len(final_session.approved_crm_updates) > 0)
    
    def _simulate_user_responses(self, questions):
        """Simulate realistic user responses to validation questions"""
        responses = {}
        
        for question in questions:
            question_id = question['id']
            question_type = question['type']
            
            if question_type == 'summary_confirmation':
                # User confirms summary with minor edit
                responses[question_id] = {
                    'confirmed': True,
                    'edited_text': question['text'] + " [Confirmed by sales rep]",
                    'notes': 'Summary looks accurate, added confirmation note.'
                }
            
            elif question_type == 'key_points_review':
                # User approves most key points, edits one
                key_points = question.get('items', [])
                approved_points = key_points.copy()
                if approved_points:
                    approved_points[0] = approved_points[0] + " (verified with customer)"
                
                responses[question_id] = {
                    'approved_items': approved_points,
                    'notes': 'Added verification note to first key point.'
                }
            
            elif question_type == 'action_items_review':
                # User approves all action items, adds due date to one
                action_items = question.get('items', [])
                approved_items = []
                
                for item in action_items:
                    approved_item = item.copy()
                    if 'due_date' not in approved_item or not approved_item['due_date']:
                        approved_item['due_date'] = '2024-01-25'
                    approved_items.append(approved_item)
                
                responses[question_id] = {
                    'approved_items': approved_items,
                    'notes': 'Added missing due dates where needed.'
                }
            
            elif question_type == 'crm_field_update':
                # User approves CRM updates with modifications
                suggested_updates = question.get('suggested_updates', {})
                approved_updates = suggested_updates.copy()
                
                # Modify probability based on user judgment
                if 'probability' in approved_updates:
                    approved_updates['probability'] = 70  # Increase confidence
                
                # Add additional context
                approved_updates['sales_rep_notes'] = 'Customer very engaged, strong fit for solution'
                
                responses[question_id] = {
                    'approved': True,
                    'field_updates': approved_updates,
                    'notes': 'Increased probability to 70% based on customer engagement level.'
                }
            
            elif question_type == 'stage_selection':
                # User selects appropriate stage
                suggested_stage = question.get('suggested_stage', 'Proposal/Price Quote')
                responses[question_id] = {
                    'selected_stage': suggested_stage,
                    'stage_reason': 'Customer requested detailed proposal, moving to proposal stage.',
                    'notes': 'Stage progression appropriate based on meeting outcome.'
                }
            
            elif question_type == 'next_steps_confirmation':
                # User confirms and adds to next steps
                next_steps = question.get('suggested_steps', [])
                confirmed_steps = next_steps + [
                    'Prepare ROI calculator for customer review',
                    'Research customer\'s current tool stack for integration planning'
                ]
                
                responses[question_id] = {
                    'confirmed_steps': confirmed_steps,
                    'notes': 'Added additional preparation steps for stronger proposal.'
                }
            
            elif question_type == 'decision_confirmation':
                # User confirms decisions made
                decisions = question.get('decisions', [])
                responses[question_id] = {
                    'confirmed_decisions': decisions,
                    'additional_context': 'All decisions align with customer stated needs and budget.',
                    'notes': 'Decisions accurately captured.'
                }
            
            elif question_type == 'competitor_information':
                # User provides competitor context
                responses[question_id] = {
                    'competitors_mentioned': ['Asana', 'Monday.com'],
                    'competitive_position': 'Our solution offers better enterprise features and integration capabilities',
                    'notes': 'Customer mentioned evaluating Asana and Monday.com but likes our enterprise focus.'
                }
            
            elif question_type == 'budget_confirmation':
                # User confirms budget information
                responses[question_id] = {
                    'budget_confirmed': True,
                    'budget_amount': 108000,  # Annual budget
                    'budget_timeframe': 'Annual',
                    'budget_authority': 'Sarah has budget authority up to $150K',
                    'notes': 'Budget confirmed, customer has authority to make decision.'
                }
            
            else:
                # Default confirmation response
                responses[question_id] = {
                    'confirmed': True,
                    'notes': f'Confirmed {question_type} question.'
                }
        
        return responses
    
    def test_validation_with_user_corrections(self):
        """Test validation workflow where user makes significant corrections"""
        
        # Create validation session
        create_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com'
        })
        session_id = create_response.data['validation_session']['id']
        
        # Get questions
        questions_response = self.client.get(
            f'/api/validation/sessions/{session_id}/questions/'
        )
        questions = questions_response.data['validation_questions']
        
        # Simulate user making corrections
        corrections_made = 0
        
        for question in questions:
            question_id = question['id']
            
            if question['type'] == 'summary_confirmation':
                # User significantly edits the summary
                corrected_summary = """
                CORRECTED: Discovery call with TechCorp Solutions revealed strong interest in our enterprise solution.
                
                Key corrections:
                - Team size is actually 75 users, not 50
                - Budget range is $20/user/month, not $15
                - Implementation must be completed by Q2, not flexible timeline
                - Sarah is the final decision maker, no team consultation needed
                
                Meeting outcome: Very positive, ready to move forward quickly
                """
                
                response_data = {
                    'confirmed': False,
                    'edited_text': corrected_summary,
                    'notes': 'Made significant corrections to team size, budget, and timeline requirements.'
                }
                corrections_made += 1
            
            elif question['type'] == 'crm_field_update':
                # User corrects CRM data
                corrected_updates = {
                    'stage': 'Negotiation/Review',  # More advanced stage
                    'amount': 18000,  # 75 users * $20 * 12 months
                    'close_date': '2024-01-31',  # Faster close
                    'probability': 85,  # Higher probability
                    'next_action': 'Prepare contract'
                }
                
                response_data = {
                    'approved': False,
                    'field_updates': corrected_updates,
                    'notes': 'Corrected team size, pricing, and timeline based on actual customer requirements.'
                }
                corrections_made += 1
            
            elif question['type'] == 'action_items_review':
                # User modifies action items
                corrected_items = [
                    {
                        'description': 'Prepare contract for 75 users at $20/user/month',
                        'assignee': 'Sales Rep',
                        'due_date': '2024-01-20',
                        'priority': 'High'
                    },
                    {
                        'description': 'Review and sign contract',
                        'assignee': 'Sarah Johnson',
                        'due_date': '2024-01-25',
                        'priority': 'High'
                    }
                ]
                
                response_data = {
                    'approved_items': corrected_items,
                    'notes': 'Updated action items to reflect correct pricing and faster timeline.'
                }
                corrections_made += 1
            
            else:
                # Default approval for other questions
                response_data = {
                    'confirmed': True,
                    'notes': 'No corrections needed.'
                }
            
            # Submit response
            submit_response = self.client.post(
                f'/api/validation/sessions/{session_id}/responses/',
                {
                    'question_id': question_id,
                    'response': response_data
                },
                format='json'
            )
            
            self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        
        # Complete validation
        complete_response = self.client.post(
            f'/api/validation/sessions/{session_id}/complete/'
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Verify corrections were applied
        final_session = ValidationSession.objects.get(id=session_id)
        self.assertIn('CORRECTED', final_session.validated_summary)
        self.assertEqual(final_session.approved_crm_updates['amount'], 18000)
        self.assertEqual(final_session.approved_crm_updates['probability'], 85)
        
        # Verify correction tracking
        self.assertGreater(corrections_made, 0)
    
    def test_validation_with_user_rejection(self):
        """Test validation workflow where user rejects AI suggestions"""
        
        # Create validation session
        create_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com'
        })
        session_id = create_response.data['validation_session']['id']
        
        # Get questions
        questions_response = self.client.get(
            f'/api/validation/sessions/{session_id}/questions/'
        )
        questions = questions_response.data['validation_questions']
        
        # Find CRM update question and reject it
        crm_question = None
        for question in questions:
            if question['type'] == 'crm_field_update':
                crm_question = question
                break
        
        self.assertIsNotNone(crm_question, "Should have CRM update question")
        
        # User rejects CRM updates
        rejection_response = self.client.post(
            f'/api/validation/sessions/{session_id}/responses/',
            {
                'question_id': crm_question['id'],
                'response': {
                    'approved': False,
                    'rejection_reason': 'Customer not ready for proposal stage, need more discovery',
                    'alternative_updates': {
                        'stage': 'Qualification',
                        'next_action': 'Schedule technical discovery call',
                        'probability': 30
                    },
                    'notes': 'Need additional discovery before moving to proposal stage.'
                }
            },
            format='json'
        )
        
        self.assertEqual(rejection_response.status_code, status.HTTP_200_OK)
        
        # Answer remaining questions with approvals
        for question in questions:
            if question['id'] != crm_question['id']:
                self.client.post(
                    f'/api/validation/sessions/{session_id}/responses/',
                    {
                        'question_id': question['id'],
                        'response': {'confirmed': True}
                    },
                    format='json'
                )
        
        # Complete validation
        complete_response = self.client.post(
            f'/api/validation/sessions/{session_id}/complete/'
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # Verify rejection was applied
        final_session = ValidationSession.objects.get(id=session_id)
        self.assertEqual(final_session.approved_crm_updates['stage'], 'Qualification')
        self.assertEqual(final_session.approved_crm_updates['probability'], 30)
    
    def test_validation_session_timeout_handling(self):
        """Test handling of validation session timeouts"""
        
        # Create validation session with short timeout
        create_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com',
            'session_duration_hours': 1  # Short timeout for testing
        })
        session_id = create_response.data['validation_session']['id']
        
        # Manually expire the session
        session = ValidationSession.objects.get(id=session_id)
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save()
        
        # Try to submit response to expired session
        questions_response = self.client.get(
            f'/api/validation/sessions/{session_id}/questions/'
        )
        
        if questions_response.status_code == status.HTTP_200_OK:
            questions = questions_response.data['validation_questions']
            if questions:
                response = self.client.post(
                    f'/api/validation/sessions/{session_id}/responses/',
                    {
                        'question_id': questions[0]['id'],
                        'response': {'confirmed': True}
                    },
                    format='json'
                )
                
                # Should reject expired session
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('expired', response.data['error'].lower())
    
    def test_validation_performance_with_mock_user(self):
        """Test validation session performance with simulated user interactions"""
        
        import time
        
        # Create validation session
        start_time = time.time()
        
        create_response = self.client.post('/api/validation/sessions/', {
            'draft_summary_id': self.draft_summary.id,
            'sales_rep_email': 'sales@ourcompany.com'
        })
        
        creation_time = time.time() - start_time
        self.assertLess(creation_time, 2.0, "Session creation should be under 2 seconds")
        
        session_id = create_response.data['validation_session']['id']
        
        # Get questions
        questions_start = time.time()
        questions_response = self.client.get(
            f'/api/validation/sessions/{session_id}/questions/'
        )
        questions_time = time.time() - questions_start
        
        self.assertLess(questions_time, 1.0, "Question generation should be under 1 second")
        
        questions = questions_response.data['validation_questions']
        
        # Submit responses (simulate user thinking time)
        total_response_time = 0
        
        for question in questions:
            response_start = time.time()
            
            self.client.post(
                f'/api/validation/sessions/{session_id}/responses/',
                {
                    'question_id': question['id'],
                    'response': {'confirmed': True}
                },
                format='json'
            )
            
            response_time = time.time() - response_start
            total_response_time += response_time
            
            # Each response should be processed quickly
            self.assertLess(response_time, 0.5, f"Response processing should be under 0.5 seconds")
        
        # Complete validation
        complete_start = time.time()
        complete_response = self.client.post(
            f'/api/validation/sessions/{session_id}/complete/'
        )
        complete_time = time.time() - complete_start
        
        self.assertLess(complete_time, 2.0, "Session completion should be under 2 seconds")
        
        # Total workflow should be efficient
        total_time = time.time() - start_time
        self.assertLess(total_time, 10.0, "Complete validation workflow should be under 10 seconds")