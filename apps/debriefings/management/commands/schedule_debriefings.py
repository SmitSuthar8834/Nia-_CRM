"""
Management command for automated debriefing scheduling
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.meetings.models import Meeting
from apps.debriefings.scheduling import AutomatedDebriefingScheduler


class Command(BaseCommand):
    help = 'Schedule debriefings for completed meetings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=2,
            help='Process meetings completed in the last N hours (default: 2)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reschedule existing debriefings'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Process meetings for specific user only'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        force = options['force']
        user_id = options.get('user_id')
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        # Find completed meetings without debriefings
        query = Meeting.objects.filter(
            status='completed',
            is_sales_meeting=True,
            end_time__gte=cutoff_time
        )
        
        if not force:
            query = query.filter(debriefing_scheduled=False)
        
        if user_id:
            query = query.filter(organizer_id=user_id)
        
        meetings = query.order_by('end_time')
        
        self.stdout.write(f"Processing {meetings.count()} meetings...")
        
        scheduler = AutomatedDebriefingScheduler()
        scheduled_count = 0
        
        for meeting in meetings:
            try:
                session = scheduler.schedule_debriefing_for_meeting(meeting, force_reschedule=force)
                if session:
                    scheduled_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Scheduled debriefing for meeting: {meeting.title}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error scheduling debriefing for {meeting.title}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully scheduled {scheduled_count} debriefings")
        )