"""
Notification system for debriefing scheduling and reminders
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from django.utils import timezone
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class DebriefingNotificationService:
    """
    Service for managing debriefing notifications with decreasing frequency
    """
    
    def __init__(self):
        self.reminder_intervals = [30, 120, 360]  # minutes: 30min, 2hr, 6hr
        self.notification_types = {
            'initial': {'priority': 'medium', 'urgency': 'normal'},
            'followup': {'priority': 'high', 'urgency': 'high'},
            'final': {'priority': 'urgent', 'urgency': 'critical'},
            'quick_survey': {'priority': 'medium', 'urgency': 'normal'},
            'overdue': {'priority': 'urgent', 'urgency': 'critical'}
        }
    
    def send_debriefing_notification(self, session, notification_type: str, **kwargs) -> bool:
        """
        Send comprehensive debriefing notification (email + in-app + push)
        """
        try:
            # Validate notification type
            if notification_type not in self.notification_types:
                raise ValueError(f"Invalid notification type: {notification_type}")
            
            # For now, just log the notification
            logger.info(f"Sending {notification_type} notification for session {session.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification for session {session.id}: {str(e)}")
            return False
    
    def schedule_reminder_sequence(self, session):
        """
        Schedule the complete reminder sequence for a debriefing session
        """
        try:
            logger.info(f"Scheduling reminder sequence for session {session.id}")
            # In a real implementation, this would schedule Celery tasks
            
        except Exception as e:
            logger.error(f"Error scheduling reminder sequence: {str(e)}")
    
    def should_send_notification(self, session, notification_type: str) -> bool:
        """
        Check if notification should be sent based on user preferences and timing
        """
        try:
            # Check if session is still valid for notifications
            if session.status not in ['scheduled', 'skipped']:
                return False
            
            # Check if reminders were cancelled
            if session.conversation_data.get('reminders_cancelled', False):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking notification eligibility: {str(e)}")
            return True  # Default to sending if check fails


class SmartReschedulingService:
    """
    Service for intelligent debriefing rescheduling with smart time suggestions
    """
    
    def __init__(self):
        self.business_hours = {'start': 9, 'end': 18}
        self.preferred_gaps = [30, 60, 120, 240]  # minutes
        self.max_suggestions = 5
    
    def suggest_reschedule_times(self, session, count: int = None) -> List[Dict]:
        """
        Generate smart reschedule time suggestions
        """
        if count is None:
            count = self.max_suggestions
        
        try:
            now = timezone.now()
            suggestions = []
            
            # Generate default suggestions with increasing delays
            for i, minutes in enumerate([60, 240, 480, 1440]):  # 1hr, 4hr, 8hr, 24hr
                suggestion_time = now + timedelta(minutes=minutes)
                
                # Adjust to business hours
                if suggestion_time.hour < 9:
                    suggestion_time = suggestion_time.replace(hour=9, minute=0)
                elif suggestion_time.hour >= 18:
                    suggestion_time = suggestion_time.replace(hour=9, minute=0) + timedelta(days=1)
                
                # Skip weekends
                while suggestion_time.weekday() >= 5:
                    suggestion_time += timedelta(days=1)
                
                suggestions.append({
                    'time': suggestion_time,
                    'reason': f"In {minutes // 60} hour{'s' if minutes > 60 else ''}",
                    'confidence': 0.5 - (i * 0.1),
                    'type': 'default'
                })
                
                if len(suggestions) >= count:
                    break
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating reschedule suggestions: {str(e)}")
            return []