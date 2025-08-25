"""
Management command to clean up old meeting data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.meetings.models import Meeting, MeetingParticipant, MeetingNote
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old meeting data while preserving important records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Keep meetings newer than this many days (default: 365)'
        )
        parser.add_argument(
            '--keep-sales-meetings',
            action='store_true',
            help='Keep sales meetings regardless of age'
        )
        parser.add_argument(
            '--keep-with-debriefings',
            action='store_true',
            help='Keep meetings that have completed debriefings'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without actually doing it'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        keep_sales_meetings = options['keep_sales_meetings']
        keep_with_debriefings = options['keep_with_debriefings']
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Build query for meetings to delete
        meetings_to_delete = Meeting.objects.filter(start_time__lt=cutoff_date)
        
        if keep_sales_meetings:
            meetings_to_delete = meetings_to_delete.exclude(is_sales_meeting=True)
        
        if keep_with_debriefings:
            meetings_to_delete = meetings_to_delete.exclude(debriefing_completed=True)
        
        total_meetings = Meeting.objects.count()
        meetings_to_delete_count = meetings_to_delete.count()
        
        self.stdout.write(f'Total meetings: {total_meetings}')
        self.stdout.write(f'Meetings to delete (older than {days} days): {meetings_to_delete_count}')
        
        from django.db import models
        
        # Show meeting type breakdown
        type_breakdown = meetings_to_delete.values('meeting_type').annotate(
            count=models.Count('id')
        ).order_by('-count')
        
        self.stdout.write('Breakdown by meeting type:')
        for item in type_breakdown:
            meeting_type = item['meeting_type'] or 'Unknown'
            self.stdout.write(f'  {meeting_type}: {item["count"]} meetings')
        
        # Show sales meeting breakdown
        sales_breakdown = meetings_to_delete.values('is_sales_meeting').annotate(
            count=models.Count('id')
        )
        
        self.stdout.write('Sales meeting breakdown:')
        for item in sales_breakdown:
            is_sales = 'Sales' if item['is_sales_meeting'] else 'Non-sales'
            self.stdout.write(f'  {is_sales}: {item["count"]} meetings')
        
        if meetings_to_delete_count == 0:
            self.stdout.write(self.style.SUCCESS('No meetings to clean up'))
            return
        
        # Count related objects
        participants_count = MeetingParticipant.objects.filter(
            meeting__in=meetings_to_delete
        ).count()
        notes_count = MeetingNote.objects.filter(
            meeting__in=meetings_to_delete
        ).count()
        
        self.stdout.write(f'Related data to be deleted:')
        self.stdout.write(f'  - {participants_count} meeting participants')
        self.stdout.write(f'  - {notes_count} meeting notes')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Confirm action
        if not force:
            percentage = (meetings_to_delete_count / total_meetings) * 100
            confirm = input(
                f'Delete {meetings_to_delete_count} meetings ({percentage:.1f}% of total) '
                f'and {participants_count + notes_count} related records? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform cleanup
        try:
            with transaction.atomic():
                deleted_count = meetings_to_delete.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {deleted_count} meetings and related data'
                    )
                )
                
                remaining_meetings = Meeting.objects.count()
                space_saved_percentage = ((total_meetings - remaining_meetings) / total_meetings) * 100
                
                self.stdout.write(
                    f'Cleanup complete: {remaining_meetings} meetings remaining '
                    f'({space_saved_percentage:.1f}% space saved)'
                )
                
                logger.info(
                    f'Meeting cleanup: deleted {deleted_count} meetings, '
                    f'{participants_count} participants, {notes_count} notes'
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {str(e)}')
            )
            logger.error(f'Error during meeting cleanup: {str(e)}')