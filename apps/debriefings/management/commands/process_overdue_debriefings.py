"""
Management command for processing overdue debriefings
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.debriefings.models import DebriefingSession
from apps.debriefings.scheduling import QuickSurveyService
from apps.debriefings.notifications import DebriefingNotificationService


class Command(BaseCommand):
    help = 'Process overdue debriefings and create quick surveys'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Mark debriefings overdue after N hours (default: 24)'
        )
        parser.add_argument(
            '--expire',
            action='store_true',
            help='Expire very old debriefings (72+ hours)'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        expire_old = options['expire']
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        expire_cutoff = timezone.now() - timedelta(hours=72)
        
        # Find overdue debriefings
        overdue_sessions = DebriefingSession.objects.filter(
            status='scheduled',
            scheduled_time__lt=cutoff_time
        )
        
        self.stdout.write(f"Processing {overdue_sessions.count()} overdue debriefings...")
        
        notification_service = DebriefingNotificationService()
        survey_service = QuickSurveyService()
        
        processed_count = 0
        expired_count = 0
        
        for session in overdue_sessions:
            try:
                # Check if should be expired
                if expire_old and session.scheduled_time < expire_cutoff:
                    session.status = 'expired'
                    session.save()
                    expired_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"Expired debriefing: {session.meeting.title}")
                    )
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
                    
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created quick survey for: {session.meeting.title}")
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing session {session.id}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed_count} overdue debriefings, expired {expired_count}"
            )
        )