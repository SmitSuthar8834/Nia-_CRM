"""
Tests for follow-up task scheduling and reminder service
"""
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache
from celery import current_app

from leads.models import Lead
from .models import Meeting, MeetingSession, ActionItem
from .task_scheduler import (
    FollowUpTaskScheduler, ReminderType, ReminderConfig,
    send_follow_up_reminder, cleanup_completed_reminders, sync_overdue_tasks
)
from .crm_service import CRMSyncStatus, CRMSyncResult


class FollowUpTaskSchedulerTest(TestCase):
    """Test cases for follow-up task scheduler"""
    
    def setUp(self):
        self.scheduler = FollowUpTaskScheduler()
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id='CRM_123',
            name='John Doe',
            email='john@example.com',
            company='Test Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='cal_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='completed'
        )
        
        self.session = MeetingSession.objects.create(
            meeting=self.meeting,
            ai_session_id='ai_123',
            notes='Test meeting notes',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
        
        self.action_item = ActionItem.objects.create(
            meeting_session=self.session,
            description='Send follow-up email',
            assignee='John Doe',
            due_date=timezone.now().date() + timedelta(days=7),
            crm_task_id=''  # Not synced yet
        )
    
    def tearDown(self):
        # Clear cache after each test
        cache.clear()
    
    @patch.object(FollowUpTaskScheduler, '_schedule_reminders')
    @patch('meetings.task_scheduler.CRMSyncService.create_follow_up_tasks')
    def test_schedule_follow_up_tasks_success(self, mock_crm_sync, mock_schedule_reminders):
        """Test successful follow-up task scheduling"""
        # Mock successful CRM sync
        mock_crm_sync.return_value = [
            CRMSyncResult(
                status=CRMSyncStatus.SUCCESS,
                message="Task created successfully",
                crm_record_id="crm_task_123"
            )
        ]
        
        # Mock reminder scheduling
        mock_schedule_reminders.return_value = 3
        
        result = self.scheduler.schedule_follow_up_tasks(self.meeting.id)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['scheduled_tasks'], 1)
        self.assertEqual(result['scheduled_reminders'], 3)
        self.assertIn('1 tasks and 3 reminders', result['message'])
        
        # Verify CRM sync was called
        mock_crm_sync.assert_called_once_with(self.meeting.id)
        
        # Verify reminders were scheduled
        mock_schedule_reminders.assert_called_once()
    
    def test_schedule_follow_up_tasks_no_session(self):
        """Test scheduling when meeting has no session"""
        meeting_no_session = Meeting.objects.create(
            calendar_event_id='cal_456',
            lead=self.lead,
            title='No Session Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        result = self.scheduler.schedule_follow_up_tasks(meeting_no_session.id)
        
        self.assertFalse(result['success'])
        self.assertIn('No meeting session found', result['message'])
        self.assertEqual(result['scheduled_tasks'], 0)
    
    def test_schedule_follow_up_tasks_no_action_items(self):
        """Test scheduling when no action items exist"""
        # Remove the action item
        self.action_item.delete()
        
        result = self.scheduler.schedule_follow_up_tasks(self.meeting.id)
        
        self.assertTrue(result['success'])
        self.assertIn('No action items to schedule', result['message'])
        self.assertEqual(result['scheduled_tasks'], 0)
    
    @patch('meetings.task_scheduler.CRMSyncService.create_follow_up_tasks')
    def test_schedule_follow_up_tasks_crm_failure(self, mock_crm_sync):
        """Test scheduling when CRM sync fails"""
        # Mock failed CRM sync
        mock_crm_sync.return_value = [
            CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message="CRM API error"
            )
        ]
        
        result = self.scheduler.schedule_follow_up_tasks(self.meeting.id)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['scheduled_tasks'], 0)
        self.assertEqual(len(result['errors']), 1)
        self.assertIn('Failed to create CRM task', result['errors'][0])
    
    @patch('meetings.task_scheduler.send_follow_up_reminder.apply_async')
    def test_schedule_reminders(self, mock_apply_async):
        """Test reminder scheduling"""
        reminder_configs = [
            ReminderConfig(
                reminder_type=ReminderType.EMAIL,
                days_before_due=3,
                recipient="assignee",
                message_template="Reminder: {task_description}"
            ),
            ReminderConfig(
                reminder_type=ReminderType.NOTIFICATION,
                days_before_due=1,
                recipient="assignee",
                message_template="Urgent: {task_description}"
            )
        ]
        
        count = self.scheduler._schedule_reminders(self.action_item, reminder_configs)
        
        self.assertEqual(count, 2)
        self.assertEqual(mock_apply_async.call_count, 2)
        
        # Verify the calls were made with correct parameters
        calls = mock_apply_async.call_args_list
        self.assertEqual(calls[0][1]['args'][0], self.action_item.id)  # action_item_id
        self.assertEqual(calls[0][1]['args'][1], ReminderType.EMAIL.value)  # reminder_type
    
    @patch('meetings.task_scheduler.send_follow_up_reminder.apply_async')
    def test_schedule_reminders_past_date(self, mock_apply_async):
        """Test that reminders are not scheduled for past dates"""
        # Set due date to yesterday
        self.action_item.due_date = timezone.now().date() - timedelta(days=1)
        self.action_item.save()
        
        reminder_configs = [
            ReminderConfig(
                reminder_type=ReminderType.EMAIL,
                days_before_due=3,
                recipient="assignee",
                message_template="Reminder: {task_description}"
            )
        ]
        
        count = self.scheduler._schedule_reminders(self.action_item, reminder_configs)
        
        self.assertEqual(count, 0)
        mock_apply_async.assert_not_called()
    
    def test_get_scheduling_status(self):
        """Test getting scheduling status from cache"""
        # No status initially
        status = self.scheduler.get_scheduling_status(self.meeting.id)
        self.assertIsNone(status)
        
        # Schedule tasks to create cache entry
        with patch('meetings.task_scheduler.CRMSyncService.create_follow_up_tasks') as mock_crm_sync:
            mock_crm_sync.return_value = [
                CRMSyncResult(status=CRMSyncStatus.SUCCESS, message="Success", crm_record_id="123")
            ]
            
            with patch.object(FollowUpTaskScheduler, '_schedule_reminders', return_value=2):
                self.scheduler.schedule_follow_up_tasks(self.meeting.id)
        
        # Should now have cached status
        status = self.scheduler.get_scheduling_status(self.meeting.id)
        self.assertIsNotNone(status)
        self.assertEqual(status['scheduled_tasks'], 1)
        self.assertEqual(status['scheduled_reminders'], 2)
    
    def test_cancel_scheduled_reminders(self):
        """Test cancelling scheduled reminders"""
        success = self.scheduler.cancel_scheduled_reminders(self.action_item.id)
        
        self.assertTrue(success)
        
        # Verify action item status was updated
        self.action_item.refresh_from_db()
        self.assertEqual(self.action_item.status, 'cancelled')
    
    def test_cancel_scheduled_reminders_not_found(self):
        """Test cancelling reminders for non-existent action item"""
        success = self.scheduler.cancel_scheduled_reminders(99999)
        
        self.assertFalse(success)
    
    @patch.object(FollowUpTaskScheduler, 'cancel_scheduled_reminders')
    @patch.object(FollowUpTaskScheduler, '_schedule_reminders')
    def test_reschedule_task(self, mock_schedule_reminders, mock_cancel_reminders):
        """Test rescheduling a task"""
        mock_cancel_reminders.return_value = True
        mock_schedule_reminders.return_value = 2
        
        new_due_date = timezone.now().date() + timedelta(days=14)
        success = self.scheduler.reschedule_task(self.action_item.id, new_due_date)
        
        self.assertTrue(success)
        
        # Verify due date was updated
        self.action_item.refresh_from_db()
        self.assertEqual(self.action_item.due_date, new_due_date)
        
        # Verify old reminders were cancelled and new ones scheduled
        mock_cancel_reminders.assert_called_once_with(self.action_item.id)
        mock_schedule_reminders.assert_called_once()


class CeleryTaskTest(TestCase):
    """Test cases for Celery tasks"""
    
    def setUp(self):
        # Create test data
        self.lead = Lead.objects.create(
            crm_id='CRM_123',
            name='John Doe',
            email='john@example.com',
            company='Test Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='cal_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.session = MeetingSession.objects.create(
            meeting=self.meeting,
            ai_session_id='ai_123',
            notes='Test meeting notes',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
        
        self.action_item = ActionItem.objects.create(
            meeting_session=self.session,
            description='Send follow-up email',
            assignee='John Doe',
            due_date=timezone.now().date() + timedelta(days=7)
        )
    
    @patch('meetings.task_scheduler._send_email_reminder')
    def test_send_follow_up_reminder_email(self, mock_send_email):
        """Test sending email reminder"""
        mock_send_email.return_value = True
        
        # Call the task directly (not through Celery)
        send_follow_up_reminder(
            self.action_item.id,
            ReminderType.EMAIL.value,
            "Reminder: {task_description}"
        )
        
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args[0]
        self.assertEqual(call_args[0].id, self.action_item.id)
        self.assertIn('Send follow-up email', call_args[1])
    
    @patch('meetings.task_scheduler._send_notification_reminder')
    def test_send_follow_up_reminder_notification(self, mock_send_notification):
        """Test sending notification reminder"""
        mock_send_notification.return_value = True
        
        send_follow_up_reminder(
            self.action_item.id,
            ReminderType.NOTIFICATION.value,
            "Notification: {task_description}"
        )
        
        mock_send_notification.assert_called_once()
    
    def test_send_follow_up_reminder_completed_task(self):
        """Test that reminders are skipped for completed tasks"""
        # Mark task as completed
        self.action_item.status = 'completed'
        self.action_item.save()
        
        with patch('meetings.task_scheduler._send_email_reminder') as mock_send_email:
            send_follow_up_reminder(
                self.action_item.id,
                ReminderType.EMAIL.value,
                "Reminder: {task_description}"
            )
            
            mock_send_email.assert_not_called()
    
    def test_send_follow_up_reminder_nonexistent_item(self):
        """Test reminder for non-existent action item"""
        with patch('meetings.task_scheduler._send_email_reminder') as mock_send_email:
            send_follow_up_reminder(
                99999,
                ReminderType.EMAIL.value,
                "Reminder: {task_description}"
            )
            
            mock_send_email.assert_not_called()
    
    @patch('meetings.task_scheduler.send_follow_up_reminder.delay')
    def test_sync_overdue_tasks(self, mock_send_reminder):
        """Test syncing overdue tasks"""
        # Create an overdue action item
        overdue_item = ActionItem.objects.create(
            meeting_session=self.session,
            description='Overdue task',
            assignee='Jane Doe',
            due_date=timezone.now().date() - timedelta(days=1),
            status='pending'
        )
        
        sync_overdue_tasks()
        
        # Verify reminder was scheduled for overdue task
        mock_send_reminder.assert_called_once()
        call_args = mock_send_reminder.call_args[0]
        self.assertEqual(call_args[0], overdue_item.id)
        self.assertEqual(call_args[1], ReminderType.EMAIL.value)
    
    def test_cleanup_completed_reminders(self):
        """Test cleanup of completed reminders"""
        # This is mostly a placeholder test since the actual implementation
        # would depend on the specific reminder tracking system
        try:
            cleanup_completed_reminders()
            # If no exception is raised, the test passes
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"cleanup_completed_reminders raised an exception: {e}")


class ReminderFunctionTest(TestCase):
    """Test cases for reminder helper functions"""
    
    def setUp(self):
        self.lead = Lead.objects.create(
            crm_id='CRM_123',
            name='John Doe',
            email='john@example.com',
            company='Test Company'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='cal_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.session = MeetingSession.objects.create(
            meeting=self.meeting,
            ai_session_id='ai_123',
            started_at=timezone.now() - timedelta(hours=1),
            ended_at=timezone.now()
        )
        
        self.action_item = ActionItem.objects.create(
            meeting_session=self.session,
            description='Test task',
            assignee='John Doe',
            due_date=timezone.now().date() + timedelta(days=7)
        )
    
    def test_send_email_reminder(self):
        """Test email reminder function"""
        from meetings.task_scheduler import _send_email_reminder
        
        result = _send_email_reminder(self.action_item, "Test message")
        
        # Since this is a placeholder implementation, it should always return True
        self.assertTrue(result)
    
    def test_send_notification_reminder(self):
        """Test notification reminder function"""
        from meetings.task_scheduler import _send_notification_reminder
        
        result = _send_notification_reminder(self.action_item, "Test message")
        
        # Since this is a placeholder implementation, it should always return True
        self.assertTrue(result)
    
    def test_send_webhook_reminder(self):
        """Test webhook reminder function"""
        from meetings.task_scheduler import _send_webhook_reminder
        
        result = _send_webhook_reminder(self.action_item, "Test message")
        
        # Since this is a placeholder implementation, it should always return True
        self.assertTrue(result)