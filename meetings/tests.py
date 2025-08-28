from django.test import TestCase
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Meeting, MeetingSession, ActionItem
from leads.models import Lead
import factory


class MeetingFactory(factory.django.DjangoModelFactory):
    """Factory for creating Meeting test instances"""
    
    class Meta:
        model = Meeting
    
    calendar_event_id = factory.Sequence(lambda n: f"event_{n}")
    title = factory.Faker('sentence', nb_words=4)
    start_time = factory.Faker('future_datetime', end_date='+30d')
    end_time = factory.LazyAttribute(lambda obj: obj.start_time + timedelta(hours=1))
    attendees = factory.LazyFunction(lambda: ['test@example.com'])
    status = 'scheduled'


class MeetingSessionFactory(factory.django.DjangoModelFactory):
    """Factory for creating MeetingSession test instances"""
    
    class Meta:
        model = MeetingSession
    
    meeting = factory.SubFactory(MeetingFactory)
    ai_session_id = factory.Faker('uuid4')
    notes = factory.Faker('text')
    started_at = factory.Faker('past_datetime', start_date='-1d')


class ActionItemFactory(factory.django.DjangoModelFactory):
    """Factory for creating ActionItem test instances"""
    
    class Meta:
        model = ActionItem
    
    meeting_session = factory.SubFactory(MeetingSessionFactory)
    description = factory.Faker('sentence')
    assignee = factory.Faker('name')
    due_date = factory.Faker('future_date', end_date='+30d')
    status = 'pending'


class MeetingModelTest(TestCase):
    """Test cases for Meeting model"""
    
    def test_meeting_creation(self):
        """Test creating a valid meeting"""
        meeting = MeetingFactory()
        self.assertTrue(isinstance(meeting, Meeting))
        self.assertEqual(meeting.status, 'scheduled')
        self.assertIsNotNone(meeting.created_at)
    
    def test_meeting_str_representation(self):
        """Test string representation of meeting"""
        meeting = MeetingFactory(title="Test Meeting")
        self.assertIn("Test Meeting", str(meeting))
    
    def test_meeting_validation_end_time_before_start(self):
        """Test validation for end time before start time"""
        start_time = timezone.now()
        end_time = start_time - timedelta(hours=1)
        meeting = MeetingFactory.build(start_time=start_time, end_time=end_time)
        with self.assertRaises(ValidationError):
            meeting.full_clean()
    
    def test_meeting_validation_invalid_confidence(self):
        """Test validation for invalid match confidence"""
        meeting = MeetingFactory.build(match_confidence=1.5)
        with self.assertRaises(ValidationError):
            meeting.full_clean()
    
    def test_meeting_with_lead_association(self):
        """Test meeting with associated lead"""
        from leads.tests import LeadFactory
        lead = LeadFactory()
        meeting = MeetingFactory(lead=lead, match_confidence=0.9)
        self.assertEqual(meeting.lead, lead)
        self.assertEqual(meeting.match_confidence, 0.9)


class MeetingSessionModelTest(TestCase):
    """Test cases for MeetingSession model"""
    
    def test_meeting_session_creation(self):
        """Test creating a valid meeting session"""
        session = MeetingSessionFactory()
        self.assertTrue(isinstance(session, MeetingSession))
        self.assertTrue(session.is_active)
    
    def test_meeting_session_str_representation(self):
        """Test string representation of meeting session"""
        meeting = MeetingFactory(title="Test Meeting")
        session = MeetingSessionFactory(meeting=meeting)
        self.assertIn("Test Meeting", str(session))
    
    def test_meeting_session_is_active_property(self):
        """Test is_active property"""
        session = MeetingSessionFactory()
        self.assertTrue(session.is_active)
        
        session.ended_at = timezone.now()
        session.save()
        self.assertFalse(session.is_active)
    
    def test_meeting_session_duration_property(self):
        """Test duration property calculation"""
        started_at = timezone.now() - timedelta(hours=1)
        ended_at = timezone.now()
        session = MeetingSessionFactory(started_at=started_at, ended_at=ended_at)
        
        duration = session.duration
        self.assertAlmostEqual(duration.total_seconds(), 3600, delta=60)


class ActionItemModelTest(TestCase):
    """Test cases for ActionItem model"""
    
    def test_action_item_creation(self):
        """Test creating a valid action item"""
        action_item = ActionItemFactory()
        self.assertTrue(isinstance(action_item, ActionItem))
        self.assertEqual(action_item.status, 'pending')
    
    def test_action_item_str_representation(self):
        """Test string representation of action item"""
        action_item = ActionItemFactory(
            description="Test action item description",
            assignee="John Doe"
        )
        self.assertIn("Test action item", str(action_item))
        self.assertIn("John Doe", str(action_item))
    
    def test_action_item_validation_empty_description(self):
        """Test validation for empty description"""
        action_item = ActionItemFactory.build(description="")
        with self.assertRaises(ValidationError):
            action_item.full_clean()
    
    def test_action_item_validation_empty_assignee(self):
        """Test validation for empty assignee"""
        action_item = ActionItemFactory.build(assignee="")
        with self.assertRaises(ValidationError):
            action_item.full_clean()


class MeetingAPITest(APITestCase):
    """Test cases for Meeting API endpoints"""
    
    def setUp(self):
        """Set up test user and authentication"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_meeting_list_endpoint(self):
        """Test GET /api/meetings/"""
        MeetingFactory.create_batch(3)
        response = self.client.get('/api/meetings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_meeting_create_endpoint(self):
        """Test POST /api/meetings/"""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        data = {
            'calendar_event_id': 'test_event_123',
            'title': 'Test Meeting',
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'attendees': ['test@example.com']
        }
        response = self.client.post('/api/meetings/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Meeting.objects.count(), 1)
    
    def test_meeting_match_lead_endpoint(self):
        """Test POST /api/meetings/match-lead/"""
        from leads.tests import LeadFactory
        lead = LeadFactory(email='test@example.com')
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        data = {
            'calendar_event_id': 'test_event_123',
            'title': 'Test Meeting',
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'attendees': ['test@example.com']
        }
        response = self.client.post('/api/meetings/match-lead/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['matched_lead_id'], lead.id)
        self.assertGreater(response.data['match_confidence'], 0)
    
    def test_start_meeting_session_endpoint(self):
        """Test POST /api/meetings/{id}/start/"""
        meeting = MeetingFactory()
        data = {'ai_session_id': 'test_session_123'}
        response = self.client.post(f'/api/meetings/{meeting.id}/start/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, 'in_progress')
        self.assertTrue(hasattr(meeting, 'meetingsession'))
    
    def test_end_meeting_session_endpoint(self):
        """Test POST /api/meetings/{id}/end/"""
        session = MeetingSessionFactory()
        meeting = session.meeting
        
        data = {
            'notes': 'Meeting notes',
            'summary': 'Meeting summary'
        }
        response = self.client.post(f'/api/meetings/{meeting.id}/end/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        session.refresh_from_db()
        meeting.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(meeting.status, 'completed')
    
    def test_meeting_filtering(self):
        """Test meeting filtering by status and lead"""
        from leads.tests import LeadFactory
        lead = LeadFactory()
        MeetingFactory(status='scheduled', lead=lead)
        MeetingFactory(status='completed')
        
        # Filter by status
        response = self.client.get('/api/meetings/?status=scheduled')
        self.assertEqual(len(response.data['results']), 1)
        
        # Filter by lead
        response = self.client.get(f'/api/meetings/?lead_id={lead.id}')
        self.assertEqual(len(response.data['results']), 1)


class MeetingSessionServiceTest(TestCase):
    """Test cases for MeetingSessionService"""
    
    def setUp(self):
        """Set up test data"""
        from .services import MeetingSessionService
        self.service = MeetingSessionService()
        self.meeting = MeetingFactory()
    
    def test_initialize_session(self):
        """Test session initialization"""
        ai_session_id = "test_ai_session_123"
        session = self.service.initialize_session(self.meeting.id, ai_session_id)
        
        self.assertIsInstance(session, MeetingSession)
        self.assertEqual(session.ai_session_id, ai_session_id)
        self.assertTrue(session.is_active)
        
        # Check meeting status updated
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'in_progress')
    
    def test_initialize_session_already_exists(self):
        """Test error when session already exists"""
        MeetingSessionFactory(meeting=self.meeting)
        
        with self.assertRaises(ValueError):
            self.service.initialize_session(self.meeting.id)
    
    def test_initialize_session_invalid_meeting(self):
        """Test error with invalid meeting ID"""
        with self.assertRaises(ValueError):
            self.service.initialize_session(99999)
    
    def test_get_session_state(self):
        """Test getting session state"""
        session = MeetingSessionFactory(meeting=self.meeting)
        
        session_data = self.service.get_session_state(session.id)
        
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data['id'], session.id)
        self.assertEqual(session_data['meeting_id'], self.meeting.id)
        self.assertTrue(session_data['is_active'])
    
    def test_get_session_state_not_found(self):
        """Test getting state for non-existent session"""
        session_data = self.service.get_session_state(99999)
        self.assertIsNone(session_data)
    
    def test_update_session_notes(self):
        """Test updating session notes"""
        session = MeetingSessionFactory(meeting=self.meeting)
        notes = "Updated meeting notes"
        
        success = self.service.update_session_notes(session.id, notes)
        
        self.assertTrue(success)
        
        # Check cached data
        session_data = self.service.get_session_state(session.id)
        self.assertEqual(session_data['notes'], notes)
    
    def test_update_session_transcript(self):
        """Test updating session transcript"""
        session = MeetingSessionFactory(meeting=self.meeting)
        transcript = "Meeting transcript content"
        
        success = self.service.update_session_transcript(session.id, transcript)
        
        self.assertTrue(success)
        
        # Check cached data
        session_data = self.service.get_session_state(session.id)
        self.assertEqual(session_data['transcript'], transcript)
    
    def test_add_action_item(self):
        """Test adding action item"""
        session = MeetingSessionFactory(meeting=self.meeting)
        description = "Follow up with client"
        assignee = "John Doe"
        
        success = self.service.add_action_item(session.id, description, assignee)
        
        self.assertTrue(success)
        
        # Check action item created
        action_items = ActionItem.objects.filter(meeting_session=session)
        self.assertEqual(action_items.count(), 1)
        self.assertEqual(action_items.first().description, description)
    
    def test_end_session(self):
        """Test ending session"""
        session = MeetingSessionFactory(meeting=self.meeting)
        notes = "Final meeting notes"
        summary = "Meeting summary"
        
        success = self.service.end_session(session.id, notes, summary)
        
        self.assertTrue(success)
        
        # Check session ended
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(session.notes, notes)
        self.assertEqual(session.summary, summary)
        
        # Check meeting status
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, 'completed')
    
    def test_end_session_already_ended(self):
        """Test error when ending already ended session"""
        session = MeetingSessionFactory(meeting=self.meeting, ended_at=timezone.now())
        
        success = self.service.end_session(session.id)
        
        self.assertFalse(success)
    
    def test_force_save_session(self):
        """Test force saving session to database"""
        session = MeetingSessionFactory(meeting=self.meeting)
        notes = "Notes to be saved"
        
        # Update notes in cache
        self.service.update_session_notes(session.id, notes, auto_save=False)
        
        # Force save
        success = self.service.force_save_session(session.id)
        
        self.assertTrue(success)
        
        # Check database updated
        session.refresh_from_db()
        self.assertEqual(session.notes, notes)


class MeetingSessionManagementAPITest(APITestCase):
    """Test cases for meeting session management API endpoints"""
    
    def setUp(self):
        """Set up test user and authentication"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.meeting = MeetingFactory()
    
    def test_update_session_notes_endpoint(self):
        """Test POST /api/meetings/sessions/{id}/notes/"""
        session = MeetingSessionFactory(meeting=self.meeting)
        data = {
            'notes': 'Updated notes via API',
            'auto_save': True
        }
        
        response = self.client.post(f'/api/meetings/sessions/{session.id}/notes/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_update_session_transcript_endpoint(self):
        """Test POST /api/meetings/sessions/{id}/transcript/"""
        session = MeetingSessionFactory(meeting=self.meeting)
        data = {
            'transcript': 'Meeting transcript via API'
        }
        
        response = self.client.post(f'/api/meetings/sessions/{session.id}/transcript/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_get_session_state_endpoint(self):
        """Test GET /api/meetings/sessions/{id}/state/"""
        session = MeetingSessionFactory(meeting=self.meeting)
        
        response = self.client.get(f'/api/meetings/sessions/{session.id}/state/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], session.id)
        self.assertEqual(response.data['meeting_id'], self.meeting.id)
    
    def test_add_action_item_endpoint(self):
        """Test POST /api/meetings/sessions/{id}/action-items/"""
        session = MeetingSessionFactory(meeting=self.meeting)
        data = {
            'description': 'Follow up task',
            'assignee': 'John Doe',
            'due_date': '2025-09-01'
        }
        
        response = self.client.post(f'/api/meetings/sessions/{session.id}/action-items/', data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Check action item created
        action_items = ActionItem.objects.filter(meeting_session=session)
        self.assertEqual(action_items.count(), 1)
    
    def test_add_action_item_missing_data(self):
        """Test adding action item with missing required data"""
        session = MeetingSessionFactory(meeting=self.meeting)
        data = {
            'description': 'Task without assignee'
        }
        
        response = self.client.post(f'/api/meetings/sessions/{session.id}/action-items/', data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_force_save_session_endpoint(self):
        """Test POST /api/meetings/sessions/{id}/save/"""
        session = MeetingSessionFactory(meeting=self.meeting)
        
        response = self.client.post(f'/api/meetings/sessions/{session.id}/save/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_session_lifecycle_integration(self):
        """Test complete session lifecycle"""
        # Start session
        start_data = {'ai_session_id': 'integration_test_session'}
        start_response = self.client.post(f'/api/meetings/{self.meeting.id}/start/', start_data)
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        
        session_id = start_response.data['id']
        
        # Update notes
        notes_data = {'notes': 'Integration test notes'}
        notes_response = self.client.post(f'/api/meetings/sessions/{session_id}/notes/', notes_data)
        self.assertEqual(notes_response.status_code, status.HTTP_200_OK)
        
        # Add action item
        action_data = {
            'description': 'Integration test action',
            'assignee': 'Test User'
        }
        action_response = self.client.post(f'/api/meetings/sessions/{session_id}/action-items/', action_data)
        self.assertEqual(action_response.status_code, status.HTTP_200_OK)
        
        # Get session state
        state_response = self.client.get(f'/api/meetings/sessions/{session_id}/state/')
        self.assertEqual(state_response.status_code, status.HTTP_200_OK)
        self.assertEqual(state_response.data['notes'], 'Integration test notes')
        
        # End session
        end_data = {
            'notes': 'Final integration test notes',
            'summary': 'Integration test summary'
        }
        end_response = self.client.post(f'/api/meetings/{self.meeting.id}/end/', end_data)
        self.assertEqual(end_response.status_code, status.HTTP_200_OK)
        
        # Verify session ended
        final_state = self.client.get(f'/api/meetings/sessions/{session_id}/state/')
        self.assertEqual(final_state.status_code, status.HTTP_200_OK)
        self.assertFalse(final_state.data['is_active'])