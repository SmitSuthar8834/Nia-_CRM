"""
Celery tasks for debriefing scheduling and notifications
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import DebriefingSession
from .services import DebriefingScheduler, DebriefingStateManager
from apps.meetings.models import Meeting

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def schedule_meeting_debriefing(self, meeting_id: str):
    """
    Schedule debriefing for a completed meeting using the new automated scheduler
    """
    try:
        meeting = Meeting.objects.get(id=meeting_id)
        
        # Use the new automated scheduler
        from .scheduling import AutomatedDebriefingScheduler
        scheduler = AutomatedDebriefingScheduler()
        
        session = scheduler.schedule_debriefing_for_meeting(meeting)
        if session:
            logger.info(f"Successfully scheduled debriefing {session.id} for meeting {meeting_id}")
            return str(session.id)
        else:
            logger.info(f"No debriefing scheduled for meeting {meeting_id}")
            return None
            
    except Meeting.DoesNotExist:
        logger.error(f"Meeting {meeting_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error scheduling debriefing for meeting {meeting_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return None


@shared_task(bind=True, max_retries=3)
def send_debriefing_reminder(self, session_id: str, reminder_number: int):
    """
    Send debriefing reminder notification
    """
    try:
        session = DebriefingSession.objects.get(id=session_id)
        
        # Skip if session is no longer scheduled
        if session.status != 'scheduled':
            logger.info(f"Skipping reminder for debriefing {session_id} - status: {session.status}")
            return
        
        # Send notification based on reminder number
        if reminder_number == 1:
            return _send_initial_reminder(session)
        elif reminder_number == 2:
            return _send_followup_reminder(session)
        elif reminder_number == 3:
            return _send_final_reminder(session)
        else:
            logger.warning(f"Invalid reminder number {reminder_number} for session {session_id}")
            
    except DebriefingSession.DoesNotExist:
        logger.error(f"Debriefing session {session_id} not found")
        return None
    except Exception as e:
        logger.error(f"Error sending reminder for session {session_id}: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        return None


def _send_initial_reminder(session: DebriefingSession) -> bool:
    """
    Send initial debriefing reminder (30 minutes before)
    """
    subject = f"Debriefing Ready: {session.meeting.title}"
    
    context = {
        'session': session,
        'meeting': session.meeting,
        'user': session.user,
        'debriefing_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}",
        'reminder_type': 'initial'
    }
    
    # Send email
    html_message = render_to_string('debriefings/emails/initial_reminder.html', context)
    text_message = render_to_string('debriefings/emails/initial_reminder.txt', context)
    
    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.user.email],
        fail_silently=False
    )
    
    # Send in-app notification
    _send_in_app_notification(session, 'initial_reminder', {
        'title': 'Debriefing Ready',
        'message': f"Your debriefing for '{session.meeting.title}' is ready to start.",
        'action_url': f"/debriefings/{session.id}",
        'priority': 'medium'
    })
    
    logger.info(f"Sent initial reminder for debriefing {session.id}")
    return True


def _send_followup_reminder(session: DebriefingSession) -> bool:
    """
    Send follow-up reminder (2 hours after scheduled time)
    """
    subject = f"Debriefing Pending: {session.meeting.title}"
    
    context = {
        'session': session,
        'meeting': session.meeting,
        'user': session.user,
        'debriefing_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}",
        'reschedule_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}/reschedule",
        'reminder_type': 'followup'
    }
    
    # Send email
    html_message = render_to_string('debriefings/emails/followup_reminder.html', context)
    text_message = render_to_string('debriefings/emails/followup_reminder.txt', context)
    
    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.user.email],
        fail_silently=False
    )
    
    # Send in-app notification
    _send_in_app_notification(session, 'followup_reminder', {
        'title': 'Debriefing Still Pending',
        'message': f"Don't forget to complete your debriefing for '{session.meeting.title}'.",
        'action_url': f"/debriefings/{session.id}",
        'priority': 'high'
    })
    
    logger.info(f"Sent follow-up reminder for debriefing {session.id}")
    return True


def _send_final_reminder(session: DebriefingSession) -> bool:
    """
    Send final reminder (6 hours after scheduled time)
    """
    subject = f"Final Reminder: Debriefing for {session.meeting.title}"
    
    context = {
        'session': session,
        'meeting': session.meeting,
        'user': session.user,
        'debriefing_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}",
        'quick_survey_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}/quick-survey",
        'reminder_type': 'final'
    }
    
    # Send email
    html_message = render_to_string('debriefings/emails/final_reminder.html', context)
    text_message = render_to_string('debriefings/emails/final_reminder.txt', context)
    
    send_mail(
        subject=subject,
        message=text_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.user.email],
        fail_silently=False
    )
    
    # Send in-app notification
    _send_in_app_notification(session, 'final_reminder', {
        'title': 'Last Chance: Complete Debriefing',
        'message': f"Complete your debriefing for '{session.meeting.title}' or take a quick survey.",
        'action_url': f"/debriefings/{session.id}",
        'priority': 'urgent'
    })
    
    logger.info(f"Sent final reminder for debriefing {session.id}")
    return True


@shared_task
def send_quick_survey_reminder(session_id: str):
    """
    Send quick survey reminder for skipped debriefings
    """
    try:
        session = DebriefingSession.objects.get(id=session_id)
        
        if session.status != 'skipped':
            logger.info(f"Skipping quick survey reminder - session {session_id} status: {session.status}")
            return
        
        subject = f"Quick Survey: {session.meeting.title}"
        
        context = {
            'session': session,
            'meeting': session.meeting,
            'user': session.user,
            'survey_url': f"{settings.FRONTEND_URL}/debriefings/{session.id}/quick-survey"
        }
        
        # Send email
        html_message = render_to_string('debriefings/emails/quick_survey.html', context)
        text_message = render_to_string('debriefings/emails/quick_survey.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[session.user.email],
            fail_silently=False
        )
        
        # Send in-app notification
        _send_in_app_notification(session, 'quick_survey', {
            'title': 'Quick Survey Available',
            'message': f"Take a 2-minute survey about '{session.meeting.title}'.",
            'action_url': f"/debriefings/{session.id}/quick-survey",
            'priority': 'medium'
        })
        
        logger.info(f"Sent quick survey reminder for debriefing {session.id}")
        
    except DebriefingSession.DoesNotExist:
        logger.error(f"Debriefing session {session_id} not found")
    except Exception as e:
        logger.error(f"Error sending quick survey reminder: {str(e)}")


@shared_task
def expire_overdue_debriefings():
    """
    Periodic task to expire overdue debriefings and create quick surveys
    """
    try:
        from .scheduling import QuickSurveyService
        from .notifications import DebriefingNotificationService
        
        # Find overdue debriefings (24+ hours past scheduled time)
        cutoff_time = timezone.now() - timedelta(hours=24)
        expire_cutoff = timezone.now() - timedelta(hours=72)
        
        overdue_sessions = DebriefingSession.objects.filter(
            status='scheduled',
            scheduled_time__lt=cutoff_time
        )
        
        notification_service = DebriefingNotificationService()
        survey_service = QuickSurveyService()
        
        expired_count = 0
        survey_count = 0
        
        for session in overdue_sessions:
            try:
                # Expire very old sessions (72+ hours)
                if session.scheduled_time < expire_cutoff:
                    session.status = 'expired'
                    session.save()
                    expired_count += 1
                else:
                    # Mark as skipped and create quick survey
                    session.status = 'skipped'
                    session.save()
                    
                    # Create quick survey
                    survey_service.create_quick_survey(session)
                    
                    # Send notification
                    notification_service.send_debriefing_notification(
                        session, 'quick_survey'
                    )
                    
                    survey_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing overdue session {session.id}: {str(e)}")
                continue
        
        logger.info(f"Expired {expired_count} debriefings, created {survey_count} quick surveys")
        return {'expired': expired_count, 'surveys_created': survey_count}
        
    except Exception as e:
        logger.error(f"Error expiring overdue debriefings: {str(e)}")
        return {'expired': 0, 'surveys_created': 0}


@shared_task
def consolidate_back_to_back_meetings():
    """
    Periodic task to identify and consolidate back-to-back meetings
    """
    try:
        from .scheduling import AutomatedDebriefingScheduler
        scheduler = AutomatedDebriefingScheduler()
        
        # Find meetings that ended in the last 2 hours and don't have debriefings
        cutoff_time = timezone.now() - timedelta(hours=2)
        recent_meetings = Meeting.objects.filter(
            end_time__gte=cutoff_time,
            is_sales_meeting=True,
            debriefing_scheduled=False,
            status='completed'
        )
        
        consolidated_count = 0
        processed_count = 0
        
        # Group by user to process back-to-back meetings
        users_with_meetings = recent_meetings.values_list('organizer', flat=True).distinct()
        
        for user_id in users_with_meetings:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
                user_processed = scheduler.handle_back_to_back_meetings(user, time_window_hours=2)
                processed_count += user_processed
                
                # Count consolidated sessions
                user_consolidated = DebriefingSession.objects.filter(
                    user=user,
                    created_at__gte=cutoff_time,
                    conversation_data__session_type='consolidated'
                ).count()
                consolidated_count += user_consolidated
                
            except Exception as e:
                logger.error(f"Error processing back-to-back meetings for user {user_id}: {str(e)}")
                continue
        
        logger.info(f"Processed {processed_count} meetings, created {consolidated_count} consolidated sessions")
        return {'processed': processed_count, 'consolidated': consolidated_count}
        
    except Exception as e:
        logger.error(f"Error consolidating meetings: {str(e)}")
        return {'processed': 0, 'consolidated': 0}


@shared_task
def send_debriefing_digest(user_id: int, period: str = 'daily'):
    """
    Send debriefing completion digest to users
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Calculate date range
        if period == 'daily':
            start_date = timezone.now() - timedelta(days=1)
        elif period == 'weekly':
            start_date = timezone.now() - timedelta(days=7)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        # Get user's debriefing statistics
        scheduler = DebriefingScheduler()
        stats = scheduler.get_debriefing_statistics(user, days=(timezone.now() - start_date).days)
        
        # Get pending debriefings
        pending_sessions = DebriefingSession.objects.filter(
            user=user,
            status='scheduled',
            scheduled_time__lte=timezone.now()
        ).order_by('scheduled_time')
        
        if stats['total'] == 0 and not pending_sessions:
            logger.info(f"No debriefing activity for user {user_id}, skipping digest")
            return
        
        subject = f"Debriefing Summary - {period.title()}"
        
        context = {
            'user': user,
            'period': period,
            'stats': stats,
            'pending_sessions': pending_sessions,
            'dashboard_url': f"{settings.FRONTEND_URL}/dashboard"
        }
        
        # Send email
        html_message = render_to_string('debriefings/emails/digest.html', context)
        text_message = render_to_string('debriefings/emails/digest.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        
        logger.info(f"Sent {period} debriefing digest to user {user_id}")
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
    except Exception as e:
        logger.error(f"Error sending debriefing digest to user {user_id}: {str(e)}")


def _send_in_app_notification(session: DebriefingSession, notification_type: str, data: Dict):
    """
    Send in-app notification (placeholder for notification system integration)
    """
    try:
        # This would integrate with your notification system
        # For now, we'll just log the notification
        logger.info(f"In-app notification for session {session.id}: {notification_type} - {data['title']}")
        
        # Example integration with a notification service:
        # from apps.notifications.services import NotificationService
        # NotificationService().send_notification(
        #     user=session.user,
        #     notification_type=notification_type,
        #     title=data['title'],
        #     message=data['message'],
        #     action_url=data['action_url'],
        #     priority=data['priority']
        # )
        
    except Exception as e:
        logger.error(f"Error sending in-app notification: {str(e)}")


@shared_task
def cleanup_old_debriefing_data():
    """
    Periodic cleanup of old debriefing data
    """
    try:
        # Archive debriefings older than 1 year
        cutoff_date = timezone.now() - timedelta(days=365)
        
        old_sessions = DebriefingSession.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'skipped', 'expired']
        )
        
        archived_count = 0
        for session in old_sessions:
            # Move to archive table or compress data
            # For now, just mark as archived in conversation_data
            session.conversation_data['archived'] = True
            session.conversation_data['archived_at'] = timezone.now().isoformat()
            session.save()
            archived_count += 1
        
        logger.info(f"Archived {archived_count} old debriefing sessions")
        return archived_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old debriefing data: {str(e)}")
        return 0


@shared_task
def generate_debriefing_analytics():
    """
    Generate analytics data for debriefing performance
    """
    try:
        from apps.analytics.services import DebriefingAnalytics
        
        analytics = DebriefingAnalytics()
        
        # Generate daily analytics
        daily_stats = analytics.generate_daily_stats()
        
        # Generate user performance metrics
        user_metrics = analytics.generate_user_metrics()
        
        # Generate meeting type analysis
        meeting_type_analysis = analytics.analyze_by_meeting_type()
        
        logger.info("Generated debriefing analytics successfully")
        
        return {
            'daily_stats': len(daily_stats),
            'user_metrics': len(user_metrics),
            'meeting_type_analysis': len(meeting_type_analysis)
        }
        
    except Exception as e:
        logger.error(f"Error generating debriefing analytics: {str(e)}")
        return None