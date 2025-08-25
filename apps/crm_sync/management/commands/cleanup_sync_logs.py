"""
Management command to clean up old CRM sync logs
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.crm_sync.models import SyncLog
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old CRM sync logs to maintain database performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Keep logs newer than this many days (default: 90)'
        )
        parser.add_argument(
            '--keep-errors',
            action='store_true',
            help='Keep error logs regardless of age'
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
        keep_errors = options['keep_errors']
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Build query for logs to delete
        logs_to_delete = SyncLog.objects.filter(created_at__lt=cutoff_date)
        
        if keep_errors:
            logs_to_delete = logs_to_delete.exclude(log_level='ERROR')
        
        total_logs = SyncLog.objects.count()
        logs_to_delete_count = logs_to_delete.count()
        
        self.stdout.write(f'Total sync logs: {total_logs}')
        self.stdout.write(f'Logs to delete (older than {days} days): {logs_to_delete_count}')
        
        from django.db import models
        
        # Show log level breakdown
        log_breakdown = logs_to_delete.values('log_level').annotate(
            count=models.Count('id')
        ).order_by('log_level')
        
        self.stdout.write('Breakdown by log level:')
        for item in log_breakdown:
            self.stdout.write(f'  {item["log_level"]}: {item["count"]} logs')
        
        # Show operation type breakdown
        operation_breakdown = logs_to_delete.values('operation_type').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10]
        
        self.stdout.write('Top operation types:')
        for item in operation_breakdown:
            self.stdout.write(f'  {item["operation_type"]}: {item["count"]} logs')
        
        if logs_to_delete_count == 0:
            self.stdout.write(self.style.SUCCESS('No sync logs to clean up'))
            return
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Confirm action
        if not force:
            percentage = (logs_to_delete_count / total_logs) * 100
            confirm = input(
                f'Delete {logs_to_delete_count} sync logs ({percentage:.1f}% of total)? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform cleanup
        try:
            with transaction.atomic():
                deleted_count = logs_to_delete.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {deleted_count} sync logs'
                    )
                )
                
                remaining_logs = SyncLog.objects.count()
                space_saved_percentage = ((total_logs - remaining_logs) / total_logs) * 100
                
                self.stdout.write(
                    f'Cleanup complete: {remaining_logs} logs remaining '
                    f'({space_saved_percentage:.1f}% space saved)'
                )
                
                logger.info(f'CRM sync log cleanup: deleted {deleted_count} logs, {remaining_logs} remaining')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {str(e)}')
            )
            logger.error(f'Error during sync log cleanup: {str(e)}')