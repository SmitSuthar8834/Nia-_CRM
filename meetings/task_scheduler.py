"""
Follow-up task scheduling and reminder service
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from django.utils import timezone
from django.core.cache import cache
from django.db import models, transaction
from celery import shared_task

from .models import Meeting, MeetingSession, ActionItem
from .crm_service import CRMSyncService, CRMSyncStatus

logger = logging.getLogger(__name__)


class ReminderType(Enum):
    """Types of reminders for follow-up tasks"""
    EMAIL = "email"
    NOTIFICATION = "notification"
    WEBHOOK = "webhook"


class ReminderStatus(Enum):
    """Status of reminder scheduling"""
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReminderConfig:
    """Configuration for follow-up reminders"""
    reminder_type: ReminderType
    days_before_due: int
    recipient: str
    message_template: str


class FollowUpTaskScheduler:
    """
    Service for scheduling follow-up tasks and reminders
    """
    
    CACHE_PREFIX = "task_scheduler"
    CACHE_TIMEOUT = 86400  # 24 hours
    
    # Default reminder configurations
    DEFAULT_REMINDERS = [
        ReminderConfig(
            reminder_type=ReminderType.EMAIL,
            days_before_due=3,
            recipient="assignee",
            message_template="Reminder: You have a follow-up task due in 3 days: {task_description}"
        ),
        ReminderConfig(
            reminder_type=ReminderType.EMAIL,
            days_before_due=1,
            recipient="assignee",
            message_template="Urgent: Follow-up task due tomorrow: {task_description}"
        ),
        ReminderConfig(
            reminder_type=ReminderType.NOTIFICATION,
            days_before_due=0,
            recipient="assignee",
            message_template="Follow-up task is due today: {task_description}"
        )
    ]
    
    def __init__(self):
        self.cache = cache
        self.crm_service = CRMSyncService()
    
    def schedule_follow_up_tasks(self, meeting_id: int, 
                               reminder_configs: Optional[List[ReminderConfig]] = None) -> Dict:
        """
        Schedule follow-up tasks and reminders for a meeting
        """
        if reminder_configs is None:
            reminder_configs = self.DEFAULT_REMINDERS
        
        try:
            meeting = Meeting.objects.select_related('lead', 'meetingsession').get(id=meeting_id)
            
            if not hasattr(meeting, 'meetingsession'):
                return {
                    'success': False,
                    'message': 'No meeting session found',
                    'scheduled_tasks': 0,
                    'scheduled_reminders': 0
                }
            
            session = meeting.meetingsession
            action_items = ActionItem.objects.filter(
                meeting_session=session
            ).filter(
                models.Q(crm_task_id__isnull=True) | models.Q(crm_task_id='')
            )
            
            if not action_items.exists():
                return {
                    'success': True,
                    'message': 'No action items to schedule',
                    'scheduled_tasks': 0,
                    'scheduled_reminders': 0
                }
            
            scheduled_tasks = 0
            scheduled_reminders = 0
            errors = []
            
            # Create CRM tasks first
            crm_results = self.crm_service.create_follow_up_tasks(meeting_id)
            
            for i, action_item in enumerate(action_items):
                try:
                    # Check if CRM task was created successfully
                    if i < len(crm_results) and crm_results[i].status == CRMSyncStatus.SUCCESS:
                        scheduled_tasks += 1
                        
                        # Schedule reminders for this task
                        if action_item.due_date:
                            reminder_count = self._schedule_reminders(
                                action_item, reminder_configs
                            )
                            scheduled_reminders += reminder_count
                        
                        logger.info(f"Scheduled follow-up task and reminders for action item {action_item.id}")
                    else:
                        error_msg = f"Failed to create CRM task for action item {action_item.id}"
                        if i < len(crm_results):
                            error_msg += f": {crm_results[i].message}"
                        errors.append(error_msg)
                        
                except Exception as e:
                    error_msg = f"Error scheduling task for action item {action_item.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Cache the scheduling results
            cache_key = f"{self.CACHE_PREFIX}:meeting:{meeting_id}"
            self.cache.set(cache_key, {
                'scheduled_at': timezone.now().isoformat(),
                'scheduled_tasks': scheduled_tasks,
                'scheduled_reminders': scheduled_reminders,
                'errors': errors
            }, self.CACHE_TIMEOUT)
            
            return {
                'success': len(errors) == 0,
                'message': f'Scheduled {scheduled_tasks} tasks and {scheduled_reminders} reminders',
                'scheduled_tasks': scheduled_tasks,
                'scheduled_reminders': scheduled_reminders,
                'errors': errors
            }
            
        except Meeting.DoesNotExist:
            return {
                'success': False,
                'message': f'Meeting {meeting_id} not found',
                'scheduled_tasks': 0,
                'scheduled_reminders': 0
            }
        except Exception as e:
            logger.error(f"Unexpected error scheduling follow-up tasks for meeting {meeting_id}: {str(e)}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}',
                'scheduled_tasks': 0,
                'scheduled_reminders': 0
            }
    
    def _schedule_reminders(self, action_item: ActionItem, 
                          reminder_configs: List[ReminderConfig]) -> int:
        """
        Schedule reminders for a specific action item
        """
        scheduled_count = 0
        
        for config in reminder_configs:
            try:
                # Calculate reminder date
                reminder_date = action_item.due_date - timedelta(days=config.days_before_due)
                
                # Don't schedule reminders for past dates
                if reminder_date < timezone.now().date():
                    continue
                
                # Schedule the reminder task
                reminder_datetime = timezone.make_aware(
                    datetime.combine(reminder_date, datetime.min.time().replace(hour=9))
                )
                
                # Use Celery to schedule the reminder
                send_follow_up_reminder.apply_async(
                    args=[action_item.id, config.reminder_type.value, config.message_template],
                    eta=reminder_datetime
                )
                
                scheduled_count += 1
                logger.debug(f"Scheduled {config.reminder_type.value} reminder for action item {action_item.id} at {reminder_datetime}")
                
            except Exception as e:
                logger.error(f"Error scheduling reminder for action item {action_item.id}: {str(e)}")
        
        return scheduled_count
    
    def get_scheduling_status(self, meeting_id: int) -> Optional[Dict]:
        """
        Get cached scheduling status for a meeting
        """
        cache_key = f"{self.CACHE_PREFIX}:meeting:{meeting_id}"
        return self.cache.get(cache_key)
    
    def cancel_scheduled_reminders(self, action_item_id: int) -> bool:
        """
        Cancel scheduled reminders for an action item
        """
        try:
            # This would typically involve canceling Celery tasks
            # For now, we'll just mark the action item as cancelled
            action_item = ActionItem.objects.get(id=action_item_id)
            action_item.status = 'cancelled'
            action_item.save(update_fields=['status'])
            
            logger.info(f"Cancelled reminders for action item {action_item_id}")
            return True
            
        except ActionItem.DoesNotExist:
            logger.error(f"Action item {action_item_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error cancelling reminders for action item {action_item_id}: {str(e)}")
            return False
    
    def reschedule_task(self, action_item_id: int, new_due_date: datetime.date) -> bool:
        """
        Reschedule a follow-up task with a new due date
        """
        try:
            with transaction.atomic():
                action_item = ActionItem.objects.select_for_update().get(id=action_item_id)
                old_due_date = action_item.due_date
                
                # Update the due date
                action_item.due_date = new_due_date
                action_item.save(update_fields=['due_date'])
                
                # Cancel old reminders and schedule new ones
                self.cancel_scheduled_reminders(action_item_id)
                
                # Schedule new reminders
                reminder_count = self._schedule_reminders(action_item, self.DEFAULT_REMINDERS)
                
                logger.info(f"Rescheduled action item {action_item_id} from {old_due_date} to {new_due_date}, scheduled {reminder_count} reminders")
                return True
                
        except ActionItem.DoesNotExist:
            logger.error(f"Action item {action_item_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error rescheduling action item {action_item_id}: {str(e)}")
            return False


# Celery tasks for reminder scheduling

@shared_task(bind=True, max_retries=3)
def send_follow_up_reminder(self, action_item_id: int, reminder_type: str, message_template: str):
    """
    Celery task to send follow-up reminders
    """
    try:
        action_item = ActionItem.objects.select_related(
            'meeting_session__meeting__lead'
        ).get(id=action_item_id)
        
        # Skip if task is already completed or cancelled
        if action_item.status in ['completed', 'cancelled']:
            logger.info(f"Skipping reminder for action item {action_item_id} - status: {action_item.status}")
            return
        
        # Format the message
        message = message_template.format(
            task_description=action_item.description,
            assignee=action_item.assignee,
            due_date=action_item.due_date.strftime('%Y-%m-%d') if action_item.due_date else 'No due date',
            lead_name=action_item.meeting_session.meeting.lead.name if action_item.meeting_session.meeting.lead else 'Unknown'
        )
        
        # Send the reminder based on type
        if reminder_type == ReminderType.EMAIL.value:
            success = _send_email_reminder(action_item, message)
        elif reminder_type == ReminderType.NOTIFICATION.value:
            success = _send_notification_reminder(action_item, message)
        elif reminder_type == ReminderType.WEBHOOK.value:
            success = _send_webhook_reminder(action_item, message)
        else:
            logger.error(f"Unknown reminder type: {reminder_type}")
            return
        
        if success:
            logger.info(f"Successfully sent {reminder_type} reminder for action item {action_item_id}")
        else:
            logger.error(f"Failed to send {reminder_type} reminder for action item {action_item_id}")
            
    except ActionItem.DoesNotExist:
        logger.error(f"Action item {action_item_id} not found for reminder")
    except Exception as e:
        logger.error(f"Error sending reminder for action item {action_item_id}: {str(e)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))


def _send_email_reminder(action_item: ActionItem, message: str) -> bool:
    """
    Send email reminder (placeholder implementation)
    """
    # This would integrate with an email service like SendGrid, SES, etc.
    logger.info(f"Email reminder sent to {action_item.assignee}: {message}")
    return True


def _send_notification_reminder(action_item: ActionItem, message: str) -> bool:
    """
    Send in-app notification reminder (placeholder implementation)
    """
    # This would integrate with a notification system
    logger.info(f"Notification sent to {action_item.assignee}: {message}")
    return True


def _send_webhook_reminder(action_item: ActionItem, message: str) -> bool:
    """
    Send webhook reminder (placeholder implementation)
    """
    # This would send a webhook to an external system like Slack, Teams, etc.
    logger.info(f"Webhook reminder sent for {action_item.assignee}: {message}")
    return True


@shared_task
def cleanup_completed_reminders():
    """
    Periodic task to clean up completed or cancelled reminders
    """
    try:
        # This would clean up any reminder tracking data
        # For now, it's a placeholder
        logger.info("Cleaned up completed reminders")
        
    except Exception as e:
        logger.error(f"Error cleaning up reminders: {str(e)}")


@shared_task
def sync_overdue_tasks():
    """
    Periodic task to sync overdue tasks and send notifications
    """
    try:
        overdue_items = ActionItem.objects.filter(
            due_date__lt=timezone.now().date(),
            status='pending'
        ).select_related('meeting_session__meeting__lead')
        
        for item in overdue_items:
            logger.warning(f"Action item {item.id} is overdue: {item.description}")
            
            # Send overdue notification
            send_follow_up_reminder.delay(
                item.id,
                ReminderType.EMAIL.value,
                "OVERDUE: Follow-up task was due on {due_date}: {task_description}"
            )
        
        logger.info(f"Processed {overdue_items.count()} overdue tasks")
        
    except Exception as e:
        logger.error(f"Error syncing overdue tasks: {str(e)}")