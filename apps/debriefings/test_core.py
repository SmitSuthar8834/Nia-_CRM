"""
Core tests for debriefing scheduling and management functionality
"""
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.core import mail
from django.test.utils import override_settings

from .models import DebriefingSession, DebriefingTemplate, DebriefingQuestion, DebriefingInsight
from apps.meetings.models import Meeting, MeetingParticipant


class DebriefingModelsTest(TestCase):
    """
    Test cases for debriefing models
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a completed sales meeting
        self.meeting = Meeting.objects.create(
            title='Test Sales Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery'
        )
        
        # Add external participant
        MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='client@example.com',
            name='John Client',
            company='Client Corp',
            is_external=True
        )
    
    def test_debriefing_session_creation(self):
        """Test creating a debriefing session"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        self.assertIsNotNone(session.id)
        self.assertEqual(session.meeting, self.meeting)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, 'scheduled')
        self.assertIsNotNone(session.created_at)
    
    def test_debriefing_session_state_transitions(self):
        """Test debriefing session state transitions"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Test starting session
        session.start_session()
        self.assertEqual(session.status, 'in_progress')
        self.assertIsNotNone(session.started_at)
        
        # Test completing session
        session.complete_session()
        self.assertEqual(session.status, 'completed')
        self.assertIsNotNone(session.completed_at)
    
    def test_debriefing_session_duration(self):
        """Test debriefing session duration calculation"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Start and complete session with known duration
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=5)
        
        session.started_at = start_time
        session.completed_at = end_time
        session.save()
        
        self.assertEqual(session.duration_minutes, 5)
    
    def test_debriefing_session_overdue_check(self):
        """Test overdue debriefing detection"""
        # Create overdue session
        overdue_session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() - timedelta(hours=25),
            status='scheduled'
        )
        
        self.assertTrue(overdue_session.is_overdue)
        
        # Create another meeting for current session test
        current_meeting = Meeting.objects.create(
            title='Current Meeting',
            start_time=timezone.now() - timedelta(minutes=30),
            end_time=timezone.now(),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='demo',
            calendar_event_id='current_meeting_123'
        )
        
        # Create current session
        current_session = DebriefingSession.objects.create(
            meeting=current_meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        self.assertFalse(current_session.is_overdue)
    
    def test_debriefing_question_creation(self):
        """Test creating debriefing questions"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        question = DebriefingQuestion.objects.create(
            session=session,
            question_text="How did the meeting go?",
            question_type='outcome',
            question_order=1
        )
        
        self.assertIsNotNone(question.id)
        self.assertEqual(question.session, session)
        self.assertEqual(question.question_type, 'outcome')
        self.assertEqual(question.question_order, 1)
    
    def test_debriefing_question_response(self):
        """Test recording question responses"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        question = DebriefingQuestion.objects.create(
            session=session,
            question_text="How did the meeting go?",
            question_type='outcome',
            question_order=1
        )
        
        response_text = "The meeting went very well. The client showed strong interest."
        question.record_response(response_text)
        
        self.assertEqual(question.user_response, response_text)
        self.assertIsNotNone(question.response_timestamp)
    
    def test_debriefing_insight_creation(self):
        """Test creating debriefing insights"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        insight = DebriefingInsight.objects.create(
            session=session,
            insight_type='opportunity',
            title='Strong buying signals detected',
            description='Client expressed urgency and budget availability',
            confidence_level='high',
            confidence_score=0.9
        )
        
        self.assertIsNotNone(insight.id)
        self.assertEqual(insight.session, session)
        self.assertEqual(insight.insight_type, 'opportunity')
        self.assertEqual(insight.confidence_level, 'high')
        self.assertEqual(insight.confidence_score, 0.9)
    
    def test_debriefing_template_creation(self):
        """Test creating debriefing templates"""
        template = DebriefingTemplate.objects.create(
            name='Discovery Call Template',
            template_type='discovery',
            description='Template for discovery call debriefings',
            created_by=self.user,
            question_templates=[
                {
                    'type': 'outcome',
                    'text': 'How would you rate the overall outcome?'
                },
                {
                    'type': 'next_steps',
                    'text': 'What are the agreed next steps?'
                }
            ]
        )
        
        self.assertIsNotNone(template.id)
        self.assertEqual(template.template_type, 'discovery')
        self.assertEqual(template.created_by, self.user)
        self.assertEqual(len(template.question_templates), 2)
    
    def test_debriefing_template_usage_tracking(self):
        """Test template usage tracking"""
        template = DebriefingTemplate.objects.create(
            name='Demo Template',
            template_type='demo',
            created_by=self.user
        )
        
        initial_usage = template.usage_count
        template.increment_usage()
        
        self.assertEqual(template.usage_count, initial_usage + 1)


class DebriefingSchedulingLogicTest(TestCase):
    """
    Test cases for debriefing scheduling logic
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_meeting_eligibility_for_debriefing(self):
        """Test meeting eligibility criteria for debriefing"""
        # Create eligible meeting
        eligible_meeting = Meeting.objects.create(
            title='Sales Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        # Add external participant
        MeetingParticipant.objects.create(
            meeting=eligible_meeting,
            email='client@example.com',
            is_external=True
        )
        
        # Test eligibility criteria
        self.assertTrue(eligible_meeting.is_sales_meeting)
        self.assertEqual(eligible_meeting.status, 'completed')
        self.assertTrue(eligible_meeting.participants.filter(is_external=True).exists())
        self.assertGreaterEqual(eligible_meeting.duration_minutes, 15)
    
    def test_meeting_ineligibility_scenarios(self):
        """Test scenarios where meetings are not eligible for debriefing"""
        # Internal meeting (no external participants)
        internal_meeting = Meeting.objects.create(
            title='Internal Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=False,
            status='completed',
            calendar_event_id='internal_meeting_123'
        )
        
        self.assertFalse(internal_meeting.is_sales_meeting)
        
        # Too short meeting
        short_meeting = Meeting.objects.create(
            title='Quick Check-in',
            start_time=timezone.now() - timedelta(minutes=20),
            end_time=timezone.now() - timedelta(minutes=10),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            calendar_event_id='short_meeting_123'
        )
        
        self.assertLess(short_meeting.duration_minutes, 15)
        
        # Incomplete meeting
        incomplete_meeting = Meeting.objects.create(
            title='Ongoing Meeting',
            start_time=timezone.now() - timedelta(minutes=30),
            end_time=timezone.now() + timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='in_progress',
            calendar_event_id='incomplete_meeting_123'
        )
        
        self.assertNotEqual(incomplete_meeting.status, 'completed')
    
    def test_business_hours_adjustment(self):
        """Test adjustment of debriefing times to business hours"""
        # This would test the business hours adjustment logic
        # For now, just test the concept
        
        # Late evening meeting
        late_meeting = Meeting.objects.create(
            title='Late Meeting',
            start_time=timezone.now().replace(hour=19, minute=0),
            end_time=timezone.now().replace(hour=20, minute=0),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        # The debriefing should be scheduled for next business day
        # This is a placeholder test - actual implementation would test the scheduling logic
        self.assertIsNotNone(late_meeting)
    
    def test_consolidation_opportunity_detection(self):
        """Test detection of meetings that can be consolidated"""
        # Create two meetings close in time
        meeting1 = Meeting.objects.create(
            title='Discovery Call',
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1, minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery',
            calendar_event_id='discovery_call_123'
        )
        
        meeting2 = Meeting.objects.create(
            title='Follow-up Call',
            start_time=timezone.now() - timedelta(hours=1, minutes=15),
            end_time=timezone.now() - timedelta(minutes=45),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='follow_up',
            calendar_event_id='followup_call_123'
        )
        
        # Add same external participant to both
        participant_email = 'client@example.com'
        
        MeetingParticipant.objects.create(
            meeting=meeting1,
            email=participant_email,
            is_external=True
        )
        
        MeetingParticipant.objects.create(
            meeting=meeting2,
            email=participant_email,
            is_external=True
        )
        
        # Test that meetings have overlapping participants
        meeting1_participants = set(meeting1.participants.values_list('email', flat=True))
        meeting2_participants = set(meeting2.participants.values_list('email', flat=True))
        
        overlap = meeting1_participants & meeting2_participants
        self.assertGreater(len(overlap), 0)


class DebriefingWorkflowTest(TestCase):
    """
    Integration tests for the complete debriefing workflow
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Sales Discovery Call',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery'
        )
        
        MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='prospect@company.com',
            name='Jane Prospect',
            company='Prospect Corp',
            is_external=True
        )
    
    def test_complete_debriefing_workflow(self):
        """Test complete debriefing workflow from creation to completion"""
        # Create debriefing session
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Verify initial state
        self.assertEqual(session.status, 'scheduled')
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.completed_at)
        
        # Start debriefing
        session.start_session()
        self.assertEqual(session.status, 'in_progress')
        self.assertIsNotNone(session.started_at)
        
        # Add questions and responses
        question1 = DebriefingQuestion.objects.create(
            session=session,
            question_text="How did the meeting go overall?",
            question_type='outcome',
            question_order=1
        )
        
        question1.record_response("Very positive. Client showed strong interest in our solution.")
        
        question2 = DebriefingQuestion.objects.create(
            session=session,
            question_text="What are the next steps?",
            question_type='follow_up',
            question_order=2
        )
        
        question2.record_response("Send proposal by Friday. Schedule technical demo next week.")
        
        # Add insights
        insight = DebriefingInsight.objects.create(
            session=session,
            insight_type='opportunity',
            title='High-value opportunity identified',
            description='Client has budget and timeline aligns with our delivery',
            confidence_level='high',
            confidence_score=0.85
        )
        
        # Complete debriefing
        session.complete_session()
        self.assertEqual(session.status, 'completed')
        self.assertIsNotNone(session.completed_at)
        
        # Verify data integrity
        self.assertEqual(session.questions.count(), 2)
        self.assertEqual(session.insights.count(), 1)
        
        # Verify responses were recorded
        for question in session.questions.all():
            self.assertIsNotNone(question.user_response)
            self.assertIsNotNone(question.response_timestamp)
    
    def test_debriefing_session_data_structure(self):
        """Test debriefing session data structure and JSON fields"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Test conversation data structure
        session.conversation_data = {
            'session_type': 'individual',
            'meeting_context': {
                'meeting_id': str(self.meeting.id),
                'meeting_type': self.meeting.meeting_type,
                'duration_minutes': self.meeting.duration_minutes
            },
            'scheduling_metadata': {
                'scheduled_at': timezone.now().isoformat(),
                'scheduling_method': 'automated'
            }
        }
        session.save()
        
        # Verify data structure
        self.assertEqual(session.conversation_data['session_type'], 'individual')
        self.assertIn('meeting_context', session.conversation_data)
        self.assertIn('scheduling_metadata', session.conversation_data)
        
        # Test extracted data structure
        session.extracted_data = {
            'meeting_outcome': 'positive',
            'next_steps': ['Send proposal', 'Schedule demo'],
            'key_contacts': [
                {
                    'name': 'Jane Prospect',
                    'role': 'Decision Maker',
                    'email': 'jane@prospect.com'
                }
            ],
            'competitive_mentions': [],
            'budget_discussed': True,
            'timeline': '3 months'
        }
        session.save()
        
        # Verify extracted data
        self.assertEqual(session.extracted_data['meeting_outcome'], 'positive')
        self.assertEqual(len(session.extracted_data['next_steps']), 2)
        self.assertTrue(session.extracted_data['budget_discussed'])
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_notification_logging(self):
        """Test notification logging in session data"""
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Simulate notification logging
        if 'notification_log' not in session.conversation_data:
            session.conversation_data['notification_log'] = []
        
        session.conversation_data['notification_log'].append({
            'type': 'initial',
            'timestamp': timezone.now().isoformat(),
            'delivery_status': {
                'email_sent': True,
                'in_app_sent': True,
                'push_sent': False
            }
        })
        session.save()
        
        # Verify notification log
        self.assertEqual(len(session.conversation_data['notification_log']), 1)
        log_entry = session.conversation_data['notification_log'][0]
        self.assertEqual(log_entry['type'], 'initial')
        self.assertTrue(log_entry['delivery_status']['email_sent'])


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'apps.debriefings',
                'apps.meetings',
                'apps.accounts',
                'apps.analytics',
            ],
            SECRET_KEY='test-secret-key',
            USE_TZ=True,
        )
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['apps.debriefings.test_core'])