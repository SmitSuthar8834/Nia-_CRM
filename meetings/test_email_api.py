"""
Tests for email management API endpoints
"""
import json
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import (
    Meeting, CallBotSession, DraftSummary, ValidationSession,
    DraftEmail, EmailApproval
)
from leads.models import Lead


class EmailAPITestCase(TestCase):
    """
    Base test case for email API tests
    """
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test lead
        self.lead = Lead.objects.create(
            name='Test Lead',
            email='lead@example.com',
            company='Test Company',
            phone='+1234567890'
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            attendees=['test@example.com', 'lead@example.com'],
            status='completed'
        )
        
        # Create call bot session
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id='bot-session-123',
            platform='meet',
            join_time=self.meeting.start_time,
            leave_time=self.meeting.end_time,
            connection_status='disconnected',
            raw_transcript='This is a test transcript of the meeting.'
        )
        
        # Create draft summary
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary='This is a test AI-generated summary.',
            key_points=['Point 1', 'Point 2'],
            extracted_action_items=[
                {'id': '1', 'description': 'Follow up with client', 'assignee': 'test@example.com'}
            ],
            suggested_next_steps=['Schedule follow-up call'],
            decisions_made=['Decision 1'],
            suggested_crm_updates={'stage': 'qualified'},
            confidence_score=0.85
        )
        
        # Create validation session
        self.validation_session = ValidationSession.objects.create(
            draft_summary=self.draft_summary,
            sales_rep_email='test@example.com',
            validation_questions=[
                {'id': 'q1', 'question': 'Is the summary accurate?', 'type': 'boolean', 'required': True}
            ],
            rep_responses={'q1': True, 'next_steps': 'Schedule follow-up meeting'},
            validated_summary='This is the validated summary.',
            approved_crm_updates={'stage': 'qualified'},
            validation_status='completed',
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(minutes=30),
            expires_at=timezone.now() + timedelta(hours=23)
        )


class DraftEmailAPITests(EmailAPITestCase):
    """
    Tests for draft email API endpoints
    """
    
    def test_create_draft_email(self):
        """Test creating a draft email"""
        url = reverse('create-draft-email')
        data = {
            'validation_session_id': self.validation_session.id,
            'email_type': 'follow_up',
            'recipient_email': 'client@example.com',
            'recipient_name': 'John Doe',
            'include_meeting_summary': True,
            'include_action_items': True,
            'include_next_steps': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('draft_email', response.data)
        
        # Verify draft email was created
        draft_email = DraftEmail.objects.get(id=response.data['draft_email']['id'])
        self.assertEqual(draft_email.email_type, 'follow_up')
        self.assertEqual(draft_email.recipient_email, 'client@example.com')
        self.assertEqual(draft_email.status, 'draft')
    
    def test_list_draft_emails(self):
        """Test listing draft emails"""
        # Create test draft email
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='draft'
        )
        
        url = reverse('list-draft-emails')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['draft_emails']), 1)
    
    def test_get_draft_email(self):
        """Test getting a specific draft email"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='draft'
        )
        
        url = reverse('get-draft-email', kwargs={'email_id': draft_email.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], draft_email.id)
        self.assertEqual(response.data['subject'], 'Test Email')
    
    def test_update_draft_email(self):
        """Test updating a draft email"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='draft'
        )
        
        url = reverse('update-draft-email', kwargs={'email_id': draft_email.id})
        data = {
            'subject': 'Updated Test Email',
            'body_html': '<p>Updated test content</p>'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify email was updated
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.subject, 'Updated Test Email')
    
    def test_delete_draft_email(self):
        """Test deleting a draft email"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='draft'
        )
        
        url = reverse('delete-draft-email', kwargs={'email_id': draft_email.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify email was deleted
        self.assertFalse(DraftEmail.objects.filter(id=draft_email.id).exists())


class EmailApprovalAPITests(EmailAPITestCase):
    """
    Tests for email approval API endpoints
    """
    
    def test_request_email_approval(self):
        """Test requesting email approval"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='draft'
        )
        
        url = reverse('request-email-approval')
        data = {
            'draft_email_id': draft_email.id,
            'approver_email': 'approver@example.com',
            'approval_expires_hours': 24
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('approval', response.data)
        
        # Verify approval was created
        approval = EmailApproval.objects.get(id=response.data['approval']['id'])
        self.assertEqual(approval.approver_email, 'approver@example.com')
        self.assertEqual(approval.status, 'pending')
        
        # Verify draft email status was updated
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'pending_approval')
    
    def test_respond_to_email_approval(self):
        """Test responding to email approval"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='pending_approval'
        )
        
        approval = EmailApproval.objects.create(
            draft_email=draft_email,
            approver_email='approver@example.com',
            approval_token='test-token-123',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        url = reverse('respond-to-email-approval')
        data = {
            'approval_token': 'test-token-123',
            'action': 'approve'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['action'], 'approve')
        
        # Verify approval was processed
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'approved')
        
        # Verify draft email status was updated
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'approved')
    
    def test_respond_to_email_approval_reject(self):
        """Test rejecting email approval"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='pending_approval'
        )
        
        approval = EmailApproval.objects.create(
            draft_email=draft_email,
            approver_email='approver@example.com',
            approval_token='test-token-123',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        url = reverse('respond-to-email-approval')
        data = {
            'approval_token': 'test-token-123',
            'action': 'reject',
            'rejection_reason': 'Content needs revision'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['action'], 'reject')
        
        # Verify approval was processed
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'rejected')
        self.assertEqual(approval.rejection_reason, 'Content needs revision')
        
        # Verify draft email status was updated
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'rejected')
    
    def test_list_email_approvals(self):
        """Test listing email approvals"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='pending_approval'
        )
        
        approval = EmailApproval.objects.create(
            draft_email=draft_email,
            approver_email='approver@example.com',
            approval_token='test-token-123',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        url = reverse('list-email-approvals')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['approvals']), 1)


class ScheduledEmailAPITests(EmailAPITestCase):
    """
    Tests for scheduled email API endpoints
    """
    
    def test_schedule_email(self):
        """Test scheduling an email"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='approved'
        )
        
        url = reverse('schedule-email')
        scheduled_time = timezone.now() + timedelta(hours=2)
        data = {
            'draft_email_id': draft_email.id,
            'scheduled_send_time': scheduled_time.isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify email was scheduled
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'scheduled')
        self.assertIsNotNone(draft_email.scheduled_send_time)
    
    def test_list_scheduled_emails(self):
        """Test listing scheduled emails"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='scheduled',
            scheduled_send_time=timezone.now() + timedelta(hours=2)
        )
        
        url = reverse('list-scheduled-emails')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['scheduled_emails']), 1)
    
    def test_cancel_scheduled_email(self):
        """Test cancelling a scheduled email"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='scheduled',
            scheduled_send_time=timezone.now() + timedelta(hours=2)
        )
        
        url = reverse('cancel-scheduled-email', kwargs={'email_id': draft_email.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify email scheduling was cancelled
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'approved')
        self.assertIsNone(draft_email.scheduled_send_time)
    
    def test_send_email_immediately(self):
        """Test sending an email immediately"""
        draft_email = DraftEmail.objects.create(
            validation_session=self.validation_session,
            email_type='follow_up',
            recipient_email='client@example.com',
            subject='Test Email',
            body_html='<p>Test content</p>',
            body_text='Test content',
            status='approved'
        )
        
        url = reverse('send-email-immediately', kwargs={'email_id': draft_email.id})
        
        # Mock the email sending to avoid actually sending emails in tests
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify email status was updated
        draft_email.refresh_from_db()
        self.assertEqual(draft_email.status, 'sent')
        self.assertIsNotNone(draft_email.sent_at)