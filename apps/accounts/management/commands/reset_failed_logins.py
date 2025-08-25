"""
Management command to reset failed login attempts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from apps.accounts.models import LoginAttempt
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reset failed login attempts for security maintenance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Reset attempts older than this many hours (default: 24)'
        )
        parser.add_argument(
            '--ip',
            type=str,
            help='Reset attempts for specific IP address'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Reset attempts for specific username'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually doing it'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        ip_address = options['ip']
        username = options['username']
        dry_run = options['dry_run']
        
        # Build query
        query = LoginAttempt.objects.filter(status='failed')
        
        if hours:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            query = query.filter(created_at__lt=cutoff_time)
        
        if ip_address:
            query = query.filter(ip_address=ip_address)
        
        if username:
            query = query.filter(username=username)
        
        failed_attempts = query.all()
        
        self.stdout.write(
            self.style.WARNING(
                f'Found {failed_attempts.count()} failed login attempts to reset'
            )
        )
        
        if failed_attempts.count() == 0:
            self.stdout.write(self.style.SUCCESS('No failed login attempts to reset'))
            return
        
        # Show summary by IP and username
        ip_summary = {}
        username_summary = {}
        
        for attempt in failed_attempts:
            ip_summary[attempt.ip_address] = ip_summary.get(attempt.ip_address, 0) + 1
            username_summary[attempt.username] = username_summary.get(attempt.username, 0) + 1
        
        self.stdout.write('Summary by IP address:')
        for ip, count in sorted(ip_summary.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {ip}: {count} attempts')
        
        self.stdout.write('Summary by username:')
        for user, count in sorted(username_summary.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f'  {user}: {count} attempts')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Perform reset
        try:
            with transaction.atomic():
                deleted_count = failed_attempts.delete()[0]
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully reset {deleted_count} failed login attempts'
                    )
                )
                
                logger.info(f'Reset {deleted_count} failed login attempts')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during reset: {str(e)}')
            )
            logger.error(f'Error during login attempt reset: {str(e)}')