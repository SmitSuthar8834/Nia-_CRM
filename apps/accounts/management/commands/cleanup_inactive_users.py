"""
Management command to clean up inactive users and related data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up inactive users and related data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Number of days of inactivity before cleanup (default: 365)'
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
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find inactive users
        inactive_users = User.objects.filter(
            last_login__lt=cutoff_date,
            is_active=True,
            is_staff=False,
            is_superuser=False
        )
        
        self.stdout.write(
            self.style.WARNING(
                f'Found {inactive_users.count()} inactive users '
                f'(last login before {cutoff_date.date()})'
            )
        )
        
        if inactive_users.count() == 0:
            self.stdout.write(self.style.SUCCESS('No inactive users to clean up'))
            return
        
        # Show details
        for user in inactive_users[:10]:  # Show first 10
            last_login = user.last_login.date() if user.last_login else 'Never'
            self.stdout.write(f'  - {user.username} ({user.email}) - Last login: {last_login}')
        
        if inactive_users.count() > 10:
            self.stdout.write(f'  ... and {inactive_users.count() - 10} more')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run completed - no changes made'))
            return
        
        # Confirm action
        if not force:
            confirm = input(f'Are you sure you want to deactivate {inactive_users.count()} users? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        # Perform cleanup
        try:
            with transaction.atomic():
                # Deactivate users instead of deleting to preserve data integrity
                updated_count = inactive_users.update(is_active=False)
                
                # Log the cleanup
                from apps.accounts.models import UserActivity
                for user in inactive_users:
                    UserActivity.objects.create(
                        user=user,
                        activity_type='account_deactivated',
                        description=f'Account deactivated due to {days} days of inactivity',
                        ip_address='127.0.0.1'  # System action
                    )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deactivated {updated_count} inactive users'
                    )
                )
                
                logger.info(f'Deactivated {updated_count} inactive users after {days} days of inactivity')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during cleanup: {str(e)}')
            )
            logger.error(f'Error during user cleanup: {str(e)}')