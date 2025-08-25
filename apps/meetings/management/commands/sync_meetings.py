"""
Management command to sync meetings from calendar systems
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import logging

from apps.calendar_integration.services import CalendarIntegrationHub
from apps.meetings.models import Meeting

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync meetings from calendar systems and detect sales meetings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Sync meetings for specific user ID'
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=7,
            help='Number of days back to sync (default: 7)'
        )
        parser.add_argument(
            '--days-forward',
            type=int,
            default=30,
            help='Number of days forward to sync (default: 30)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if recently synced'
        )
        parser.add_argument(
            '--detect-only',
            action='store_true',
            help='Only run meeting detection on existing meetings'
        )
    
    def handle(self, *args, **options):
        """Execute the sync command"""
        try:
            user_id = options.get('user_id')
            days_back = options.get('days_back', 7)
            days_forward = options.get('days_forward', 30)
            force = options.get('force', False)
            detect_only = options.get('detect_only', False)
            
            # Get users to sync
            if user_id:
                try:
                    users = [User.objects.get(id=user_id)]
                except User.DoesNotExist:
                    raise CommandError(f'User with ID {user_id} does not exist')
            else:
                users = User.objects.filter(is_active=True)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Starting meeting sync for {len(users)} users'
                )
            )
            
            total_synced = 0
            total_detected = 0
            
            for user in users:
                try:
                    if detect_only:
                        detected = self.detect_sales_meetings(user)
                        total_detected += detected
                        self.stdout.write(
                            f'Detected {detected} sales meetings for {user.username}'
                        )
                    else:
                        synced, detected = self.sync_user_meetings(
                            user, days_back, days_forward, force
                        )
                        total_synced += synced
                        total_detected += detected
                        self.stdout.write(
                            f'Synced {synced} meetings, detected {detected} sales meetings for {user.username}'
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error syncing meetings for {user.username}: {str(e)}'
                        )
                    )
                    logger.error(f'Meeting sync error for user {user.id}: {str(e)}')
            
            if detect_only:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Detection complete: {total_detected} sales meetings detected'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Sync complete: {total_synced} meetings synced, {total_detected} sales meetings detected'
                    )
                )
                
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')
    
    def sync_user_meetings(self, user, days_back, days_forward, force):
        """Sync meetings for a specific user"""
        calendar_hub = CalendarIntegrationHub()
        
        # Calculate date range
        start_date = timezone.now() - timedelta(days=days_back)
        end_date = timezone.now() + timedelta(days=days_forward)
        
        # Sync calendar events
        synced_count = calendar_hub.sync_user_calendar(
            user, start_date, end_date, force
        )
        
        # Detect sales meetings
        detected_count = self.detect_sales_meetings(user)
        
        return synced_count, detected_count
    
    def detect_sales_meetings(self, user):
        """Run sales meeting detection for user's meetings"""
        from apps.calendar_integration.meeting_detection import MeetingDetectionService
        
        detection_service = MeetingDetectionService()
        
        # Get recent meetings that haven't been processed
        recent_meetings = Meeting.objects.filter(
            organizer=user,
            start_time__gte=timezone.now() - timedelta(days=30),
            confidence_score=0.0  # Not yet processed
        )
        
        detected_count = 0
        
        for meeting in recent_meetings:
            try:
                # Run detection
                is_sales, confidence, meeting_type = detection_service.detect_sales_meeting(
                    meeting.title,
                    meeting.description or '',
                    [p.email for p in meeting.participants.all()]
                )
                
                # Update meeting
                meeting.is_sales_meeting = is_sales
                meeting.confidence_score = confidence
                meeting.meeting_type = meeting_type
                meeting.save()
                
                if is_sales:
                    detected_count += 1
                    
                    # Schedule debriefing if needed
                    if not meeting.debriefing_scheduled:
                        meeting.schedule_debriefing()
                        
            except Exception as e:
                logger.error(f'Detection error for meeting {meeting.id}: {str(e)}')
        
        return detected_count