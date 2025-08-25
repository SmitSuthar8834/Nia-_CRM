"""
Debriefing Scheduling and Management Services
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count
from celery import shared_task

from .models import DebriefingSession, DebriefingTemplate
from apps.meetings.models import Meeting
from apps.analytics.models import DebriefingMetrics

logger = logging.getLogger(__name__)


class DebriefingScheduler:
    """
    Automated debriefing scheduling and management service
    """
    
    def __init__(self):
        self.default_debriefing_delay = 30  # minutes after meeting ends
        self.consolidation_window = 60  # minutes for back-to-back meeting consolidation
        self.max_reminder_attempts = 3
        self.reminder_intervals = [30, 120, 360]  # minutes: 30min, 2hr, 6hr
    
    def schedule_debriefing(self, meeting: Meeting, force_reschedule: bool = False) -> Optional[DebriefingSession]:
        """
        Schedule a debriefing session for a meeting
        
        Args:
            meeting: Meeting instance
            force_reschedule: Whether to reschedule if already exists
            
        Returns:
            DebriefingSession instance or None
        """
        try:
            # Check if meeting qualifies for debriefing
            if not self._should_schedule_debriefing(meeting):
                logger.info(f"Meeting {meeting.id} does not qualify for debriefing")
                return None
            
            # Check for existing debriefing
            existing_session = DebriefingSession.objects.filter(meeting=meeting).first()
            if existing_session and not force_reschedule:
                logger.info(f"Debriefing already exists for meeting {meeting.id}")
                return existing_session
            
            # Check for consolidation opportunities
            consolidated_meetings = self._find_consolidation_candidates(meeting)
            
            with transaction.atomic():
                if consolidated_meetings:
                    return self._create_consolidated_debriefing(meeting, consolidated_meetings)
                else:
                    return self._create_individual_debriefing(meeting)
                    
        except Exception as e:
            logger.error(f"Error scheduling debriefing for meeting {meeting.id}: {str(e)}")
            return None
    
    def _should_schedule_debriefing(self, meeting: Meeting) -> bool:
        """
        Determine if a meeting should have a debriefing scheduled
        """
        # Must be a sales meeting
        if not meeting.is_sales_meeting:
            return False
        
        # Must be completed or in progress
        if meeting.status not in ['completed', 'in_progress']:
            return False
        
        # Must have external participants
        if not meeting.participants.filter(is_external=True).exists():
            return False
        
        # Must have minimum duration (15 minutes)
        if meeting.duration_minutes < 15:
            return False
        
        return True
    
    def _find_consolidation_candidates(self, meeting: Meeting) -> List[Meeting]:
        """
        Find meetings that can be consolidated into a single debriefing
        """
        # Look for meetings within consolidation window
        window_start = meeting.end_time - timedelta(minutes=self.consolidation_window)
        window_end = meeting.end_time + timedelta(minutes=self.consolidation_window)
        
        candidates = Meeting.objects.filter(
            organizer=meeting.organizer,
            is_sales_meeting=True,
            start_time__gte=window_start,
            end_time__lte=window_end,
            status__in=['completed', 'in_progress']
        ).exclude(id=meeting.id)
        
        # Filter out meetings that already have debriefings
        candidates = candidates.exclude(
            debriefing__isnull=False
        )
        
        # Check for overlapping participants
        consolidatable = []
        meeting_participants = set(
            meeting.participants.values_list('email', flat=True)
        )
        
        for candidate in candidates:
            candidate_participants = set(
                candidate.participants.values_list('email', flat=True)
            )
            
            # If there's significant participant overlap, consider for consolidation
            overlap = len(meeting_participants & candidate_participants)
            total_unique = len(meeting_participants | candidate_participants)
            
            if overlap > 0 and (overlap / total_unique) > 0.3:  # 30% overlap threshold
                consolidatable.append(candidate)
        
        return consolidatable
    
    def _create_individual_debriefing(self, meeting: Meeting) -> DebriefingSession:
        """
        Create an individual debriefing session
        """
        scheduled_time = self._calculate_optimal_time(meeting)
        
        session = DebriefingSession.objects.create(
            meeting=meeting,
            user=meeting.organizer,
            scheduled_time=scheduled_time,
            status='scheduled'
        )
        
        # Update meeting status
        meeting.debriefing_scheduled = True
        meeting.debriefing_due_at = scheduled_time
        meeting.save()
        
        # Schedule notifications
        self._schedule_notifications(session)
        
        logger.info(f"Created individual debriefing {session.id} for meeting {meeting.id}")
        return session
    
    def _create_consolidated_debriefing(self, primary_meeting: Meeting, 
                                     other_meetings: List[Meeting]) -> DebriefingSession:
        """
        Create a consolidated debriefing session for multiple meetings
        """
        # Use the latest meeting's end time as base
        all_meetings = [primary_meeting] + other_meetings
        latest_meeting = max(all_meetings, key=lambda m: m.end_time)
        
        scheduled_time = self._calculate_optimal_time(latest_meeting)
        
        # Create session for primary meeting
        session = DebriefingSession.objects.create(
            meeting=primary_meeting,
            user=primary_meeting.organizer,
            scheduled_time=scheduled_time,
            status='scheduled'
        )
        
        # Add consolidated meeting info to conversation data
        session.conversation_data['consolidated_meetings'] = [
            {
                'meeting_id': str(m.id),
                'title': m.title,
                'start_time': m.start_time.isoformat(),
                'end_time': m.end_time.isoformat(),
                'participants': list(m.participants.values_list('email', flat=True))
            }
            for m in other_meetings
        ]
        session.save()
        
        # Update all meetings
        for meeting in all_meetings:
            meeting.debriefing_scheduled = True
            meeting.debriefing_due_at = scheduled_time
            meeting.save()
        
        # Schedule notifications
        self._schedule_notifications(session)
        
        logger.info(f"Created consolidated debriefing {session.id} for {len(all_meetings)} meetings")
        return session
    
    def _calculate_optimal_time(self, meeting: Meeting) -> datetime:
        """
        Calculate optimal debriefing time based on meeting end and user availability
        """
        base_time = meeting.end_time + timedelta(minutes=self.default_debriefing_delay)
        
        # Adjust for business hours (9 AM - 6 PM in user's timezone)
        if base_time.hour < 9:
            base_time = base_time.replace(hour=9, minute=0, second=0, microsecond=0)
        elif base_time.hour >= 18:
            # Schedule for next business day
            base_time = base_time.replace(hour=9, minute=0, second=0, microsecond=0)
            base_time += timedelta(days=1)
            
            # Skip weekends
            while base_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                base_time += timedelta(days=1)
        
        return base_time
    
    def _schedule_notifications(self, session: DebriefingSession):
        """
        Schedule notification reminders for debriefing session
        """
        from .tasks import send_debriefing_reminder
        
        for i, interval_minutes in enumerate(self.reminder_intervals):
            reminder_time = session.scheduled_time - timedelta(minutes=interval_minutes)
            
            # Only schedule if reminder time is in the future
            if reminder_time > timezone.now():
                send_debriefing_reminder.apply_async(
                    args=[str(session.id), i + 1],
                    eta=reminder_time
                )
    
    def reschedule_debriefing(self, session: DebriefingSession, 
                            new_time: Optional[datetime] = None) -> DebriefingSession:
        """
        Reschedule a debriefing session with smart time suggestions
        """
        if session.status not in ['scheduled']:
            raise ValueError("Can only reschedule scheduled debriefings")
        
        if new_time is None:
            new_time = self._suggest_reschedule_time(session)
        
        # Update session
        session.scheduled_time = new_time
        session.save()
        
        # Update meeting
        session.meeting.debriefing_due_at = new_time
        session.meeting.save()
        
        # Reschedule notifications
        self._schedule_notifications(session)
        
        logger.info(f"Rescheduled debriefing {session.id} to {new_time}")
        return session
    
    def _suggest_reschedule_time(self, session: DebriefingSession) -> datetime:
        """
        Suggest optimal reschedule time based on user patterns and availability
        """
        user = session.user
        now = timezone.now()
        
        # Get user's typical debriefing completion patterns
        completed_sessions = DebriefingSession.objects.filter(
            user=user,
            status='completed',
            started_at__isnull=False
        ).order_by('-started_at')[:10]
        
        if completed_sessions:
            # Calculate average time between meeting end and debriefing start
            avg_delay_minutes = sum([
                (s.started_at - s.meeting.end_time).total_seconds() / 60
                for s in completed_sessions
            ]) / len(completed_sessions)
            
            # Use this pattern for suggestion
            suggested_delay = max(30, int(avg_delay_minutes))  # Minimum 30 minutes
        else:
            suggested_delay = 60  # Default to 1 hour
        
        # Suggest next available slot
        suggested_time = now + timedelta(minutes=suggested_delay)
        
        # Adjust for business hours
        if suggested_time.hour < 9:
            suggested_time = suggested_time.replace(hour=9, minute=0)
        elif suggested_time.hour >= 18:
            suggested_time = suggested_time.replace(hour=9, minute=0) + timedelta(days=1)
        
        return suggested_time
    
    def handle_skipped_debriefing(self, session: DebriefingSession) -> Dict:
        """
        Handle skipped debriefing with quick survey fallback
        """
        session.status = 'skipped'
        session.save()
        
        # Create quick survey data
        quick_survey = {
            'meeting_outcome': None,
            'next_steps': None,
            'key_insights': None,
            'follow_up_required': None,
            'survey_completed': False,
            'created_at': timezone.now().isoformat()
        }
        
        session.conversation_data['quick_survey'] = quick_survey
        session.save()
        
        # Schedule quick survey reminder
        from .tasks import send_quick_survey_reminder
        send_quick_survey_reminder.apply_async(
            args=[str(session.id)],
            countdown=300  # 5 minutes
        )
        
        logger.info(f"Handled skipped debriefing {session.id} with quick survey")
        return quick_survey
    
    def process_quick_survey(self, session: DebriefingSession, survey_data: Dict) -> bool:
        """
        Process quick survey responses for skipped debriefings
        """
        if session.status != 'skipped':
            raise ValueError("Quick survey only available for skipped debriefings")
        
        # Update survey data
        session.conversation_data['quick_survey'].update(survey_data)
        session.conversation_data['quick_survey']['survey_completed'] = True
        session.conversation_data['quick_survey']['completed_at'] = timezone.now().isoformat()
        
        # Extract basic insights from survey
        extracted_data = {
            'meeting_outcome': survey_data.get('meeting_outcome'),
            'next_steps': survey_data.get('next_steps', []),
            'key_insights': survey_data.get('key_insights', []),
            'follow_up_required': survey_data.get('follow_up_required', False),
            'extraction_method': 'quick_survey',
            'confidence_score': 0.6  # Lower confidence for survey data
        }
        
        session.extracted_data = extracted_data
        session.save()
        
        logger.info(f"Processed quick survey for debriefing {session.id}")
        return True
    
    def get_overdue_debriefings(self, user: Optional[User] = None) -> List[DebriefingSession]:
        """
        Get overdue debriefing sessions
        """
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        query = DebriefingSession.objects.filter(
            status='scheduled',
            scheduled_time__lt=cutoff_time
        )
        
        if user:
            query = query.filter(user=user)
        
        return list(query.order_by('scheduled_time'))
    
    def expire_overdue_debriefings(self) -> int:
        """
        Mark overdue debriefings as expired and handle with quick survey
        """
        overdue_sessions = self.get_overdue_debriefings()
        expired_count = 0
        
        for session in overdue_sessions:
            try:
                self.handle_skipped_debriefing(session)
                session.status = 'expired'
                session.save()
                expired_count += 1
            except Exception as e:
                logger.error(f"Error expiring debriefing {session.id}: {str(e)}")
        
        logger.info(f"Expired {expired_count} overdue debriefings")
        return expired_count
    
    def get_debriefing_statistics(self, user: Optional[User] = None, 
                                days: int = 30) -> Dict:
        """
        Get debriefing completion statistics
        """
        start_date = timezone.now() - timedelta(days=days)
        
        query = DebriefingSession.objects.filter(created_at__gte=start_date)
        if user:
            query = query.filter(user=user)
        
        stats = query.aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            skipped=Count('id', filter=Q(status='skipped')),
            expired=Count('id', filter=Q(status='expired')),
            in_progress=Count('id', filter=Q(status='in_progress'))
        )
        
        # Calculate rates
        total = stats['total'] or 1  # Avoid division by zero
        stats['completion_rate'] = (stats['completed'] / total) * 100
        stats['skip_rate'] = (stats['skipped'] / total) * 100
        stats['expiry_rate'] = (stats['expired'] / total) * 100
        
        return stats


class DebriefingStateManager:
    """
    Manages debriefing session state transitions and validation
    """
    
    VALID_TRANSITIONS = {
        'scheduled': ['in_progress', 'skipped', 'expired'],
        'in_progress': ['completed', 'skipped'],
        'completed': [],  # Terminal state
        'skipped': [],    # Terminal state
        'expired': []     # Terminal state
    }
    
    def __init__(self, session: DebriefingSession):
        self.session = session
    
    def can_transition_to(self, new_status: str) -> bool:
        """
        Check if session can transition to new status
        """
        current_status = self.session.status
        return new_status in self.VALID_TRANSITIONS.get(current_status, [])
    
    def transition_to(self, new_status: str, **kwargs) -> bool:
        """
        Transition session to new status with validation
        """
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Invalid transition from {self.session.status} to {new_status}"
            )
        
        old_status = self.session.status
        self.session.status = new_status
        
        # Handle status-specific logic
        if new_status == 'in_progress':
            self.session.started_at = timezone.now()
        elif new_status == 'completed':
            self.session.completed_at = timezone.now()
            self.session.meeting.debriefing_completed = True
            self.session.meeting.save()
        
        self.session.save()
        
        # Log transition
        logger.info(f"Debriefing {self.session.id} transitioned from {old_status} to {new_status}")
        
        # Record metrics
        self._record_transition_metrics(old_status, new_status)
        
        return True
    
    def _record_transition_metrics(self, old_status: str, new_status: str):
        """
        Record metrics for status transitions
        """
        try:
            # TODO: Implement metrics recording
            logger.info(f"Session {self.session.id} transitioned from {old_status} to {new_status}")
        except Exception as e:
            logger.error(f"Error recording transition metrics: {str(e)}")