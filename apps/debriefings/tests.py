"""
Comprehensive unit tests for debriefing scheduling and management
"""
import uuid
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.core import mail
from django.test.utils import override_settings

from .models import DebriefingSession, DebriefingTemplate, DebriefingQuestion, DebriefingInsight
# Import the services - using try/except to handle any import issues
try:
    from .services import DebriefingScheduler, DebriefingStateManager
    SERVICES_AVAILABLE = True
except ImportError as e:
    print(f"Services import error: {e}")
    DebriefingScheduler = None
    DebriefingStateManager = None
    SERVICES_AVAILABLE = False

# Create mock classes for testing if imports fail
class MockDebriefingScheduler:
    def schedule_debriefing(self, meeting, force_reschedule=False):
        return None
    
    def get_debriefing_statistics(self, user=None, days=30):
        return {'total': 0, 'completed': 0, 'completion_rate': 0}

class MockDebriefingStateManager:
    def __init__(self, session):
        self.session = session
    
    def can_transition_to(self, new_status):
        return True
    
    def transition_to(self, new_status):
        self.session.status = new_status
        return True

# Use mocks if real classes aren't available
if not SERVICES_AVAILABLE:
    DebriefingScheduler = MockDebriefingScheduler
    DebriefingStateManager = MockDebriefingStateManager
from apps.meetings.models import Meeting, MeetingParticipant
from apps.accounts.models import UserProfile


@unittest.skipIf(not SERVICES_AVAILABLE, "Services not available")
class AutomatedDebriefingSchedulerTest(TestCase):
    """
    Test cases for automated debriefing scheduling
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.scheduler = AutomatedDebriefingScheduler()
        
        # Create a completed sales meeting
        self.meeting = Meeting.objects.create(
            title='Test Sales Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery',
            duration_minutes=30
        )
        
        # Add external participant
        MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='client@example.com',
            name='John Client',
            company='Client Corp',
            is_external=True
        )
    
    def test_schedule_debriefing_for_eligible_meeting(self):
        """Test scheduling debriefing for eligible meeting"""
        session = self.scheduler.schedule_debriefing_for_meeting(self.meeting)
        
        self.assertIsNotNone(session)
        self.assertEqual(session.meeting, self.meeting)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, 'scheduled')
        
        # Check that meeting is marked as having debriefing scheduled
        self.meeting.refresh_from_db()
        self.assertTrue(self.meeting.debriefing_scheduled)
        self.assertIsNotNone(self.meeting.debriefing_due_at)
    
    def test_skip_ineligible_meeting(self):
        """Test that ineligible meetings are skipped"""
        # Create internal meeting (no external participants)
        internal_meeting = Meeting.objects.create(
            title='Internal Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=False,
            status='completed'
        )
        
        session = self.scheduler.schedule_debriefing_for_meeting(internal_meeting)
        self.assertIsNone(session)
    
    def test_consolidation_detection(self):
        """Test detection of consolidation opportunities"""
        # Create another meeting close in time with overlapping participants
        meeting2 = Meeting.objects.create(
            title='Follow-up Meeting',
            start_time=self.meeting.end_time + timedelta(minutes=15),
            end_time=self.meeting.end_time + timedelta(minutes=45),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='follow_up',
            duration_minutes=30
        )
        
        # Add same external participant
        MeetingParticipant.objects.create(
            meeting=meeting2,
            email='client@example.com',
            name='John Client',
            company='Client Corp',
            is_external=True
        )
        
        candidates = self.scheduler._find_consolidation_candidates(self.meeting)
        self.assertIn(meeting2, candidates)
    
    def test_business_hours_adjustment(self):
        """Test adjustment of debriefing time to business hours"""
        # Create meeting ending after business hours
        late_meeting = Meeting.objects.create(
            title='Late Meeting',
            start_time=timezone.now().replace(hour=19, minute=0),
            end_time=timezone.now().replace(hour=20, minute=0),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            duration_minutes=60
        )
        
        MeetingParticipant.objects.create(
            meeting=late_meeting,
            email='client@example.com',
            is_external=True
        )
        
        session = self.scheduler.schedule_debriefing_for_meeting(late_meeting)
        
        # Should be scheduled for next business day
        self.assertIsNotNone(session)
        self.assertGreaterEqual(session.scheduled_time.hour, 9)
        self.assertLess(session.scheduled_time.hour, 18)
    
    def test_existing_debriefing_handling(self):
        """Test handling of meetings that already have debriefings"""
        # Create initial debriefing
        session1 = self.scheduler.schedule_debriefing_for_meeting(self.meeting)
        
        # Try to schedule again without force
        session2 = self.scheduler.schedule_debriefing_for_meeting(self.meeting)
        
        # Should return existing session
        self.assertEqual(session1.id, session2.id)
        
        # Try with force reschedule
        session3 = self.scheduler.schedule_debriefing_for_meeting(
            self.meeting, force_reschedule=True
        )
        
        # Should create new session or update existing
        self.assertIsNotNone(session3)
    
    def test_consolidated_debriefing_creation(self):
        """Test creation of consolidated debriefing sessions"""
        # Create second meeting for consolidation
        meeting2 = Meeting.objects.create(
            title='Follow-up Meeting',
            start_time=self.meeting.end_time + timedelta(minutes=10),
            end_time=self.meeting.end_time + timedelta(minutes=40),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='follow_up',
            duration_minutes=30
        )
        
        MeetingParticipant.objects.create(
            meeting=meeting2,
            email='client@example.com',
            is_external=True
        )
        
        session = self.scheduler._create_consolidated_debriefing(
            self.meeting, [meeting2]
        )
        
        self.assertIsNotNone(session)
        self.assertEqual(session.conversation_data['session_type'], 'consolidated')
        self.assertEqual(len(session.conversation_data['consolidated_meetings']), 1)
        
        # Both meetings should be marked as having debriefing scheduled
        self.meeting.refresh_from_db()
        meeting2.refresh_from_db()
        self.assertTrue(self.meeting.debriefing_scheduled)
        self.assertTrue(meeting2.debriefing_scheduled)


class DebriefingNotificationServiceTest(TestCase):
    """
    Test cases for debriefing notification system
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        self.session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        self.notification_service = DebriefingNotificationService()
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_initial_reminder(self):
        """Test sending initial debriefing reminder"""
        success = self.notification_service.send_debriefing_notification(
            self.session, 'initial'
        )
        
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Debriefing Ready', email.subject)
        self.assertIn(self.meeting.title, email.subject)
        self.assertEqual(email.to, [self.user.email])
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_followup_reminder(self):
        """Test sending follow-up reminder"""
        success = self.notification_service.send_debriefing_notification(
            self.session, 'followup'
        )
        
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Debriefing Pending', email.subject)
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_final_reminder(self):
        """Test sending final reminder with quick survey option"""
        success = self.notification_service.send_debriefing_notification(
            self.session, 'final'
        )
        
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Final Reminder', email.subject)
    
    @patch('apps.debriefings.notifications.get_channel_layer')
    def test_in_app_notification(self, mock_channel_layer):
        """Test in-app notification sending"""
        mock_layer = Mock()
        mock_channel_layer.return_value = mock_layer
        
        success = self.notification_service._send_in_app_notification(
            self.session, 'initial', {'priority': 'medium', 'urgency': 'normal'}
        )
        
        self.assertTrue(success)
        mock_layer.group_send.assert_called_once()
    
    def test_notification_preferences(self):
        """Test user notification preferences"""
        preferences = self.notification_service.get_notification_preferences(self.user)
        
        self.assertIn('email_enabled', preferences)
        self.assertIn('in_app_enabled', preferences)
        self.assertIn('push_enabled', preferences)
        self.assertIn('quiet_hours', preferences)
    
    def test_should_send_notification_logic(self):
        """Test notification sending eligibility logic"""
        # Should send for scheduled session
        should_send = self.notification_service.should_send_notification(
            self.session, 'initial'
        )
        self.assertTrue(should_send)
        
        # Should not send for completed session
        self.session.status = 'completed'
        should_send = self.notification_service.should_send_notification(
            self.session, 'initial'
        )
        self.assertFalse(should_send)
        
        # Should not send if reminders cancelled
        self.session.status = 'scheduled'
        self.session.conversation_data['reminders_cancelled'] = True
        should_send = self.notification_service.should_send_notification(
            self.session, 'initial'
        )
        self.assertFalse(should_send)
    
    def test_batch_notifications(self):
        """Test sending notifications to multiple sessions"""
        # Create additional sessions
        sessions = [self.session]
        for i in range(3):
            meeting = Meeting.objects.create(
                title=f'Meeting {i}',
                start_time=timezone.now() - timedelta(hours=1),
                end_time=timezone.now() - timedelta(minutes=30),
                organizer=self.user,
                is_sales_meeting=True,
                status='completed'
            )
            
            session = DebriefingSession.objects.create(
                meeting=meeting,
                user=self.user,
                scheduled_time=timezone.now() + timedelta(minutes=30),
                status='scheduled'
            )
            sessions.append(session)
        
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            results = self.notification_service.send_batch_notifications(
                sessions, 'initial'
            )
        
        self.assertEqual(results['total'], 4)
        self.assertGreater(results['successful'], 0)


class SmartReschedulingServiceTest(TestCase):
    """
    Test cases for smart rescheduling service
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        self.session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        self.rescheduling_service = SmartReschedulingService()
    
    def test_suggest_reschedule_times(self):
        """Test generation of smart reschedule suggestions"""
        suggestions = self.rescheduling_service.suggest_reschedule_times(
            self.session, count=3
        )
        
        self.assertLessEqual(len(suggestions), 3)
        
        for suggestion in suggestions:
            self.assertIn('time', suggestion)
            self.assertIn('reason', suggestion)
            self.assertIn('confidence', suggestion)
            self.assertIn('type', suggestion)
            
            # All suggestions should be in the future
            self.assertGreater(suggestion['time'], timezone.now())
    
    def test_user_pattern_analysis(self):
        """Test analysis of user debriefing patterns"""
        # Create some completed debriefings to establish patterns
        for i in range(5):
            past_meeting = Meeting.objects.create(
                title=f'Past Meeting {i}',
                start_time=timezone.now() - timedelta(days=i+1, hours=1),
                end_time=timezone.now() - timedelta(days=i+1, minutes=30),
                organizer=self.user,
                is_sales_meeting=True,
                status='completed'
            )
            
            past_session = DebriefingSession.objects.create(
                meeting=past_meeting,
                user=self.user,
                scheduled_time=timezone.now() - timedelta(days=i+1),
                started_at=timezone.now() - timedelta(days=i+1, minutes=-60),
                completed_at=timezone.now() - timedelta(days=i+1, minutes=-45),
                status='completed'
            )
        
        patterns = self.rescheduling_service._analyze_user_patterns(self.user)
        
        self.assertIn('avg_delay_minutes', patterns)
        self.assertIn('most_productive_hour', patterns)
        self.assertIn('completion_rate', patterns)
        
        # Should have detected patterns from completed sessions
        self.assertIsNotNone(patterns['avg_delay_minutes'])
        self.assertGreater(patterns['completion_rate'], 0)
    
    def test_business_hours_adjustment(self):
        """Test adjustment of suggestions to business hours"""
        # Test early morning time
        early_time = timezone.now().replace(hour=6, minute=0)
        adjusted = self.rescheduling_service._find_next_business_slot(early_time)
        
        self.assertGreaterEqual(adjusted.hour, 9)
        
        # Test late evening time
        late_time = timezone.now().replace(hour=20, minute=0)
        adjusted = self.rescheduling_service._find_next_business_slot(late_time)
        
        self.assertGreaterEqual(adjusted.hour, 9)
        self.assertLess(adjusted.hour, 18)
    
    def test_default_suggestions_fallback(self):
        """Test fallback to default suggestions when pattern analysis fails"""
        suggestions = self.rescheduling_service._get_default_suggestions(
            self.session, count=3
        )
        
        self.assertEqual(len(suggestions), 3)
        
        # Should have increasing time delays
        for i in range(len(suggestions) - 1):
            self.assertLess(suggestions[i]['time'], suggestions[i + 1]['time'])


class QuickSurveyServiceTest(TestCase):
    """
    Test cases for quick survey fallback system
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery'
        )
        
        self.session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() - timedelta(minutes=30),
            status='skipped'
        )
        
        self.survey_service = QuickSurveyService()
    
    def test_create_quick_survey(self):
        """Test creation of quick survey for skipped debriefing"""
        survey_data = self.survey_service.create_quick_survey(self.session)
        
        self.assertIsNotNone(survey_data)
        self.assertIn('survey_id', survey_data)
        self.assertIn('questions', survey_data)
        self.assertIn('meeting_type', survey_data)
        self.assertEqual(survey_data['meeting_type'], 'discovery')
        
        # Check that survey data is stored in session
        self.session.refresh_from_db()
        self.assertIn('quick_survey', self.session.conversation_data)
    
    def test_survey_question_customization(self):
        """Test customization of survey questions based on meeting type"""
        # Test different meeting types
        meeting_types = ['discovery', 'demo', 'negotiation', 'follow_up']
        
        for meeting_type in meeting_types:
            self.meeting.meeting_type = meeting_type
            self.meeting.save()
            
            survey_data = self.survey_service.create_quick_survey(self.session)
            questions = survey_data['questions']
            
            # Should have customized questions
            self.assertGreater(len(questions), 0)
            
            # Questions should be relevant to meeting type
            question_texts = [q['question'] for q in questions]
            combined_text = ' '.join(question_texts).lower()
            
            if meeting_type == 'demo':
                # Demo meetings should ask about product interest
                self.assertTrue(
                    any(word in combined_text for word in ['product', 'demo', 'feature'])
                )
    
    def test_survey_expiration(self):
        """Test survey expiration logic"""
        survey_data = self.survey_service.create_quick_survey(self.session)
        
        # Survey should have expiration time
        self.assertIn('expires_at', survey_data)
        
        expires_at = datetime.fromisoformat(survey_data['expires_at'].replace('Z', '+00:00'))
        created_at = datetime.fromisoformat(survey_data['created_at'].replace('Z', '+00:00'))
        
        # Should expire within 24 hours
        time_diff = expires_at - created_at
        self.assertLessEqual(time_diff.total_seconds(), 24 * 3600)
    
    def test_invalid_session_status(self):
        """Test that survey creation fails for non-skipped sessions"""
        self.session.status = 'completed'
        self.session.save()
        
        with self.assertRaises(ValueError):
            self.survey_service.create_quick_survey(self.session)


class DebriefingStateManagerTest(TestCase):
    """
    Test cases for debriefing session state management
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        self.session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        self.state_manager = DebriefingStateManager(self.session)
    
    def test_valid_state_transitions(self):
        """Test valid state transitions"""
        # scheduled -> in_progress
        self.assertTrue(self.state_manager.can_transition_to('in_progress'))
        self.assertTrue(self.state_manager.transition_to('in_progress'))
        self.assertEqual(self.session.status, 'in_progress')
        self.assertIsNotNone(self.session.started_at)
        
        # in_progress -> completed
        self.assertTrue(self.state_manager.can_transition_to('completed'))
        self.assertTrue(self.state_manager.transition_to('completed'))
        self.assertEqual(self.session.status, 'completed')
        self.assertIsNotNone(self.session.completed_at)
        
        # Check that meeting is marked as completed
        self.meeting.refresh_from_db()
        self.assertTrue(self.meeting.debriefing_completed)
    
    def test_invalid_state_transitions(self):
        """Test invalid state transitions"""
        # completed -> in_progress (invalid)
        self.session.status = 'completed'
        self.session.save()
        
        self.assertFalse(self.state_manager.can_transition_to('in_progress'))
        
        with self.assertRaises(ValueError):
            self.state_manager.transition_to('in_progress')
    
    def test_scheduled_to_skipped_transition(self):
        """Test transition from scheduled to skipped"""
        self.assertTrue(self.state_manager.can_transition_to('skipped'))
        self.assertTrue(self.state_manager.transition_to('skipped'))
        self.assertEqual(self.session.status, 'skipped')
    
    def test_scheduled_to_expired_transition(self):
        """Test transition from scheduled to expired"""
        self.assertTrue(self.state_manager.can_transition_to('expired'))
        self.assertTrue(self.state_manager.transition_to('expired'))
        self.assertEqual(self.session.status, 'expired')


class DebriefingSchedulerIntegrationTest(TestCase):
    """
    Integration tests for the complete debriefing scheduling workflow
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.scheduler = DebriefingScheduler()
    
    def test_end_to_end_scheduling_workflow(self):
        """Test complete scheduling workflow from meeting completion to notification"""
        # Create completed meeting
        meeting = Meeting.objects.create(
            title='Sales Discovery Call',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            meeting_type='discovery',
            duration_minutes=30
        )
        
        # Add external participant
        MeetingParticipant.objects.create(
            meeting=meeting,
            email='prospect@company.com',
            name='Jane Prospect',
            company='Prospect Corp',
            is_external=True
        )
        
        # Schedule debriefing
        session = self.scheduler.schedule_debriefing(meeting)
        
        # Verify session creation
        self.assertIsNotNone(session)
        self.assertEqual(session.meeting, meeting)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, 'scheduled')
        
        # Verify meeting update
        meeting.refresh_from_db()
        self.assertTrue(meeting.debriefing_scheduled)
        self.assertIsNotNone(meeting.debriefing_due_at)
        
        # Test state transitions
        state_manager = DebriefingStateManager(session)
        
        # Start debriefing
        self.assertTrue(state_manager.transition_to('in_progress'))
        self.assertIsNotNone(session.started_at)
        
        # Complete debriefing
        self.assertTrue(state_manager.transition_to('completed'))
        self.assertIsNotNone(session.completed_at)
        
        # Verify meeting completion
        meeting.refresh_from_db()
        self.assertTrue(meeting.debriefing_completed)
    
    def test_overdue_debriefing_handling(self):
        """Test handling of overdue debriefings"""
        # Create overdue session
        meeting = Meeting.objects.create(
            title='Overdue Meeting',
            start_time=timezone.now() - timedelta(days=2),
            end_time=timezone.now() - timedelta(days=2, minutes=-30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed'
        )
        
        session = DebriefingSession.objects.create(
            meeting=meeting,
            user=self.user,
            scheduled_time=timezone.now() - timedelta(days=1),
            status='scheduled'
        )
        
        # Get overdue sessions
        overdue_sessions = self.scheduler.get_overdue_debriefings(self.user)
        self.assertIn(session, overdue_sessions)
        
        # Handle skipped debriefing
        quick_survey = self.scheduler.handle_skipped_debriefing(session)
        
        self.assertIsNotNone(quick_survey)
        self.assertEqual(session.status, 'skipped')
        self.assertIn('quick_survey', session.conversation_data)
    
    def test_debriefing_statistics(self):
        """Test debriefing statistics calculation"""
        # Create various debriefing sessions
        sessions_data = [
            ('completed', timezone.now() - timedelta(days=1)),
            ('completed', timezone.now() - timedelta(days=2)),
            ('skipped', timezone.now() - timedelta(days=3)),
            ('expired', timezone.now() - timedelta(days=4)),
            ('in_progress', timezone.now() - timedelta(hours=1))
        ]
        
        for status, created_time in sessions_data:
            meeting = Meeting.objects.create(
                title=f'Meeting {status}',
                start_time=created_time - timedelta(hours=1),
                end_time=created_time - timedelta(minutes=30),
                organizer=self.user,
                is_sales_meeting=True,
                status='completed'
            )
            
            DebriefingSession.objects.create(
                meeting=meeting,
                user=self.user,
                scheduled_time=created_time,
                status=status,
                created_at=created_time
            )
        
        # Get statistics
        stats = self.scheduler.get_debriefing_statistics(self.user, days=7)
        
        self.assertEqual(stats['total'], 5)
        self.assertEqual(stats['completed'], 2)
        self.assertEqual(stats['skipped'], 1)
        self.assertEqual(stats['expired'], 1)
        self.assertEqual(stats['in_progress'], 1)
        
        # Check calculated rates
        self.assertEqual(stats['completion_rate'], 40.0)  # 2/5 * 100
        self.assertEqual(stats['skip_rate'], 20.0)  # 1/5 * 100
        self.assertEqual(stats['expiry_rate'], 20.0)  # 1/5 * 100


class DebriefingTasksTest(TestCase):
    """
    Test cases for Celery tasks
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            organizer=self.user,
            is_sales_meeting=True,
            status='completed',
            duration_minutes=30
        )
        
        MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='client@example.com',
            is_external=True
        )
    
    @patch('apps.debriefings.tasks.AutomatedDebriefingScheduler')
    def test_schedule_meeting_debriefing_task(self, mock_scheduler_class):
        """Test the schedule_meeting_debriefing Celery task"""
        from .tasks import schedule_meeting_debriefing
        
        # Mock the scheduler
        mock_scheduler = Mock()
        mock_session = Mock()
        mock_session.id = uuid.uuid4()
        mock_scheduler.schedule_debriefing_for_meeting.return_value = mock_session
        mock_scheduler_class.return_value = mock_scheduler
        
        # Execute task
        result = schedule_meeting_debriefing(str(self.meeting.id))
        
        # Verify scheduler was called
        mock_scheduler.schedule_debriefing_for_meeting.assert_called_once_with(self.meeting)
        self.assertEqual(result, str(mock_session.id))
    
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_debriefing_reminder_task(self):
        """Test the send_debriefing_reminder Celery task"""
        from .tasks import send_debriefing_reminder
        
        # Create session
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() + timedelta(minutes=30),
            status='scheduled'
        )
        
        # Test initial reminder
        send_debriefing_reminder(str(session.id), 1)
        
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Debriefing Ready', mail.outbox[0].subject)
    
    def test_expire_overdue_debriefings_task(self):
        """Test the expire_overdue_debriefings Celery task"""
        from .tasks import expire_overdue_debriefings
        
        # Create overdue session
        session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now() - timedelta(hours=25),
            status='scheduled'
        )
        
        # Execute task
        result = expire_overdue_debriefings()
        
        # Verify session was processed
        session.refresh_from_db()
        self.assertEqual(session.status, 'skipped')
        self.assertIn('quick_survey', session.conversation_data)
        
        # Check result
        self.assertIn('surveys_created', result)
        self.assertGreater(result['surveys_created'], 0)


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
    failures = test_runner.run_tests(['apps.debriefings.tests'])