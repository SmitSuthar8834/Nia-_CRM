"""
Unit tests for Meeting Intelligence API
"""
import json
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from .models import Meeting, MeetingParticipant, MeetingNote
from apps.leads.models import Lead


class MeetingModelTest(TestCase):
    """Test Meeting model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            title='Test Sales Meeting',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user,
            is_sales_meeting=True,
            meeting_type='discovery'
        )
    
    def test_meeting_creation(self):
        """Test meeting creation with required fields"""
        self.assertEqual(self.meeting.title, 'Test Sales Meeting')
        self.assertEqual(self.meeting.organizer, self.user)
        self.assertTrue(self.meeting.is_sales_meeting)
        self.assertEqual(self.meeting.meeting_type, 'discovery')
    
    def test_duration_minutes_property(self):
        """Test duration calculation"""
        self.assertEqual(self.meeting.duration_minutes, 60)
    
    def test_is_past_property(self):
        """Test is_past property"""
        # Future meeting
        self.assertFalse(self.meeting.is_past)
        
        # Past meeting
        past_meeting = Meeting.objects.create(
            calendar_event_id='past-event-123',
            title='Past Meeting',
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            organizer=self.user
        )
        self.assertTrue(past_meeting.is_past)
    
    def test_schedule_debriefing(self):
        """Test debriefing scheduling"""
        self.assertFalse(self.meeting.debriefing_scheduled)
        self.assertIsNone(self.meeting.debriefing_due_at)
        
        self.meeting.schedule_debriefing()
        
        self.assertTrue(self.meeting.debriefing_scheduled)
        self.assertIsNotNone(self.meeting.debriefing_due_at)
        expected_time = self.meeting.end_time + timedelta(minutes=30)
        self.assertEqual(self.meeting.debriefing_due_at, expected_time)


class MeetingParticipantModelTest(TestCase):
    """Test MeetingParticipant model functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            title='Test Meeting',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company'
        )
        
        self.participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='john.doe@example.com',
            name='John Doe',
            company='Test Company',
            matched_lead=self.lead,
            match_confidence=0.95
        )
    
    def test_participant_creation(self):
        """Test participant creation"""
        self.assertEqual(self.participant.email, 'john.doe@example.com')
        self.assertEqual(self.participant.name, 'John Doe')
        self.assertEqual(self.participant.matched_lead, self.lead)
        self.assertEqual(self.participant.match_confidence, 0.95)
    
    def test_display_name_property(self):
        """Test display name property"""
        # With name
        self.assertEqual(self.participant.display_name, 'John Doe')
        
        # Without name
        participant_no_name = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='jane.smith@example.com'
        )
        self.assertEqual(participant_no_name.display_name, 'Jane Smith')


class MeetingAPITest(APITestCase):
    """Test Meeting API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test meetings
        self.meeting1 = Meeting.objects.create(
            calendar_event_id='event-1',
            title='Sales Discovery Call',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user,
            is_sales_meeting=True,
            meeting_type='discovery',
            status='scheduled'
        )
        
        self.meeting2 = Meeting.objects.create(
            calendar_event_id='event-2',
            title='Product Demo',
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            organizer=self.user,
            is_sales_meeting=True,
            meeting_type='demo',
            status='scheduled'
        )
        
        # Create participants
        self.participant1 = MeetingParticipant.objects.create(
            meeting=self.meeting1,
            email='prospect@example.com',
            name='John Prospect',
            company='Prospect Corp',
            is_external=True
        )
    
    def test_list_meetings(self):
        """Test listing meetings"""
        url = reverse('meetings:meeting-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data['results']), 2)
    
    def test_retrieve_meeting(self):
        """Test retrieving a specific meeting"""
        url = reverse('meetings:meeting-detail', kwargs={'pk': self.meeting1.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Sales Discovery Call')
        self.assertEqual(response.data['meeting_type'], 'discovery')
        self.assertTrue(response.data['is_sales_meeting'])
    
    def test_create_meeting(self):
        """Test creating a new meeting"""
        url = reverse('meetings:meeting-list')
        data = {
            'calendar_event_id': 'new-event-123',
            'title': 'New Sales Meeting',
            'start_time': (timezone.now() + timedelta(days=2)).isoformat(),
            'end_time': (timezone.now() + timedelta(days=2, hours=1)).isoformat(),
            'meeting_type': 'negotiation',
            'is_sales_meeting': True
        }
        
        response = self.client.post(url, data, format='json')
        
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Sales Meeting')
        self.assertEqual(response.data['organizer'], self.user.id)
    
    def test_update_meeting(self):
        """Test updating a meeting"""
        url = reverse('meetings:meeting-detail', kwargs={'pk': self.meeting1.pk})
        data = {
            'title': 'Updated Meeting Title',
            'meeting_type': 'follow_up'
        }
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Meeting Title')
        self.assertEqual(response.data['meeting_type'], 'follow_up')
    
    def test_delete_meeting(self):
        """Test deleting a meeting"""
        url = reverse('meetings:meeting-detail', kwargs={'pk': self.meeting1.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Meeting.objects.filter(pk=self.meeting1.pk).exists())
    
    def test_schedule_debriefing(self):
        """Test scheduling debriefing for a meeting"""
        url = reverse('meetings:meeting-schedule-debriefing', kwargs={'pk': self.meeting1.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('debriefing_due_at', response.data)
        
        # Refresh meeting from database
        self.meeting1.refresh_from_db()
        self.assertTrue(self.meeting1.debriefing_scheduled)
    
    def test_schedule_debriefing_non_sales_meeting(self):
        """Test scheduling debriefing for non-sales meeting should fail"""
        self.meeting1.is_sales_meeting = False
        self.meeting1.save()
        
        url = reverse('meetings:meeting-schedule-debriefing', kwargs={'pk': self.meeting1.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_upcoming_meetings(self):
        """Test getting upcoming meetings"""
        url = reverse('meetings:meeting-upcoming')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
    
    def test_sales_meetings_filter(self):
        """Test filtering sales meetings only"""
        # Create non-sales meeting
        Meeting.objects.create(
            calendar_event_id='internal-meeting',
            title='Internal Meeting',
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
            organizer=self.user,
            is_sales_meeting=False,
            meeting_type='internal'
        )
        
        url = reverse('meetings:meeting-sales-meetings')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)  # Only sales meetings
    
    def test_meeting_statistics(self):
        """Test getting meeting statistics"""
        url = reverse('meetings:meeting-statistics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_meetings', response.data)
        self.assertIn('sales_meetings', response.data)
        self.assertIn('meeting_types', response.data)
        self.assertEqual(response.data['total_meetings'], 2)
        self.assertEqual(response.data['sales_meetings'], 2)
    
    def test_detect_intelligence(self):
        """Test meeting intelligence detection"""
        url = reverse('meetings:meeting-detect-intelligence', kwargs={'pk': self.meeting1.pk})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('meeting_id', response.data)
        self.assertIn('confidence_score', response.data)
        self.assertIn('detected_participants', response.data)
    
    def test_search_meetings(self):
        """Test searching meetings"""
        url = reverse('meetings:meeting-list')
        
        # Search by title
        response = self.client.get(url, {'search': 'Discovery'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(response.data['results']), 1)
        
        # Filter by meeting type
        response = self.client.get(url, {'meeting_type': 'demo'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Filter by sales meetings
        response = self.client.get(url, {'is_sales_meeting': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)


class MeetingParticipantAPITest(APITestCase):
    """Test Meeting Participant API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='event-1',
            title='Test Meeting',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company'
        )
        
        self.participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='john.doe@example.com',
            name='John Doe',
            company='Test Company',
            is_external=True,
            matched_lead=self.lead,
            match_confidence=0.8
        )
    
    def test_list_participants(self):
        """Test listing meeting participants"""
        url = reverse('meetings:meeting-participant-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_participants_by_meeting(self):
        """Test filtering participants by meeting"""
        url = reverse('meetings:meeting-participant-list')
        response = self.client.get(url, {'meeting': self.meeting.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_external_participants(self):
        """Test filtering external participants only"""
        url = reverse('meetings:meeting-participant-list')
        response = self.client.get(url, {'external_only': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_verify_participant_match(self):
        """Test verifying a participant-lead match"""
        url = reverse('meetings:meeting-participant-verify-match', kwargs={'pk': self.participant.pk})
        data = {
            'verified': True,
            'lead_id': str(self.lead.id)
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Check participant was updated
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.match_confidence, 1.0)
        self.assertEqual(self.participant.match_method, 'manual_verification')
    
    def test_reject_participant_match(self):
        """Test rejecting a participant-lead match"""
        url = reverse('meetings:meeting-participant-verify-match', kwargs={'pk': self.participant.pk})
        data = {'verified': False}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check participant was updated
        self.participant.refresh_from_db()
        self.assertIsNone(self.participant.matched_lead)
        self.assertEqual(self.participant.match_confidence, 0.0)
    
    def test_unmatched_participants(self):
        """Test getting unmatched participants"""
        # Create unmatched participant
        MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='unmatched@example.com',
            name='Unmatched User',
            is_external=True
        )
        
        url = reverse('meetings:meeting-participant-unmatched')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class MeetingNoteAPITest(APITestCase):
    """Test Meeting Note API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='event-1',
            title='Test Meeting',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user
        )
        
        self.note = MeetingNote.objects.create(
            meeting=self.meeting,
            author=self.user,
            title='Meeting Outcome',
            content='Great discussion about requirements',
            note_type='outcome'
        )
    
    def test_list_notes(self):
        """Test listing meeting notes"""
        url = reverse('meetings:meeting-note-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_note(self):
        """Test creating a meeting note"""
        url = reverse('meetings:meeting-note-list')
        data = {
            'meeting': self.meeting.id,
            'title': 'Action Items',
            'content': 'Follow up with technical team',
            'note_type': 'action_item'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Action Items')
        self.assertEqual(response.data['author'], self.user.id)
    
    def test_filter_notes_by_meeting(self):
        """Test filtering notes by meeting"""
        url = reverse('meetings:meeting-note-list')
        response = self.client.get(url, {'meeting': self.meeting.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_filter_notes_by_type(self):
        """Test filtering notes by type"""
        url = reverse('meetings:meeting-note-list')
        response = self.client.get(url, {'note_type': 'outcome'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_notes_by_meeting_endpoint(self):
        """Test getting notes for a specific meeting"""
        url = reverse('meetings:meeting-note-by-meeting')
        response = self.client.get(url, {'meeting_id': self.meeting.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_notes_by_meeting_missing_id(self):
        """Test getting notes without meeting_id parameter"""
        url = reverse('meetings:meeting-note-by-meeting')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class MeetingPermissionsTest(APITestCase):
    """Test meeting API permissions"""
    
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='event-1',
            title='User1 Meeting',
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=2),
            organizer=self.user1
        )
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access meetings"""
        client = APIClient()
        url = reverse('meetings:meeting-list')
        response = client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_can_only_see_own_meetings(self):
        """Test that regular users can only see their own meetings"""
        client = APIClient()
        client.force_authenticate(user=self.user2)
        
        url = reverse('meetings:meeting-list')
        response = client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)  # User2 has no meetings
    
    def test_staff_user_can_see_all_meetings(self):
        """Test that staff users can see all meetings"""
        self.user2.is_staff = True
        self.user2.save()
        
        client = APIClient()
        client.force_authenticate(user=self.user2)
        
        url = reverse('meetings:meeting-list')
        response = client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Can see user1's meeting