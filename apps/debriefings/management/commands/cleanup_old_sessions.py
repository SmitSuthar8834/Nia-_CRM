"""
Management command to clean up old debriefing sessions
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.debriefings.models import DebriefingSession
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old debriefing sessions and related data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=180,
            help='Keep sessions newer than this many days (default: 180)'
        )
        parser.add_argument(
            '--keep-completed',
            action='store_true',
            help='Keep completed sessions regardless of age'
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
        keep_completed = options['keep_completed']
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Build query for sessions to delete
        sessions_to_delete = DebriefingSession.objects.filter(
            scheduled_time__lt=cutoff_date
        )
        
        if keep_completed:
            sessions_to_delete = sessions_to_delete.exclude(status='completed')
        
        total_sessions = DebriefingSession.objects.count()
        sessions_to_delete_count = sessions_to_delete.count()
        
        self.stdout.write(f'Total debriefing sessions: {total_sessions}')
        self.stdout.write(f'Sessions to delete (older than {days} days): {sessions_to_delete_count}')
        
        from django.db import models
        
        # Show status breakdown
        status_breakdown = sessions_to_delete.values('status').annotate(
            count=models.Count('id')
        ).order_by('status')
        
        self.stdout.write('Breakdown by status:')
        for item in status_breakdown:
            self.stdout.write(f'  {item["status"]}: {item["count"]} sessions')
        
        # Show user breakdown (top 10)
        user_breakdown = sessions_to_delete.values('user__username').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        self.stdout.write('Top users with sessions to delete:')
        for item in user_breakdown:
            username = item['user__username'] or 'Unknown'
            self.stdout.write(f'  {username}: {item["count"]} sessions')
        
        if sessions_to_delete_count == 0:
            self.stdout.write(self.style.SUCCESS('No debriefing sessions to clean up'))
            return
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Confirm action
        if not force:
            percentage = (sessions_to_delete_count / total_sessions) * 100
            confirm = input(
                f'Delete {sessions_to_delete_count} debriefing sessions ({percentage:.1f}% of total)? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform cleanup
        try:
            with transaction.atomic():
                # Count related objects that will be deleted
                from apps.debriefings.models import DebriefingQuestion, DebriefingInsight
                
                questions_count = DebriefingQuestion.objects.filter(
                    session__in=sessions_to_delete
                ).count()
                insights_count = DebriefingInsight.objects.filter(
                    session__in=sessions_to_delete
                ).count()
                
                deleted_count = sessions_to_delete.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {deleted_count} debriefing sessions'
                    )
                )
                self.stdout.write(f'  - {questions_count} related questions deleted')
                self.stdout.write(f'  - {insights_count} related insights deleted')
                
                remaining_sessions = DebriefingSession.objects.count()
                space_saved_percentage = ((total_sessions - remaining_sessions) / total_sessions) * 100
                
                self.stdout.write(
                    f'Cleanup complete: {remaining_sessions} sessions remaining '
                    f'({space_saved_percentage:.1f}% space saved)'
                )
                
                logger.info(
                    f'Debriefing session cleanup: deleted {deleted_count} sessions, '
                    f'{questions_count} questions, {insights_count} insights'
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {str(e)}')
            )
            logger.error(f'Error during debriefing session cleanup: {str(e)}')