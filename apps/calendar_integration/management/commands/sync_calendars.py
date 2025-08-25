"""
Management command to sync calendars for all users
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from apps.calendar_integration.services import CalendarIntegrationHub

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync calendars for all users or specific users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Sync calendars for specific user ID'
        )
        parser.add_argument(
            '--provider',
            type=str,
            choices=['google', 'outlook', 'exchange'],
            help='Sync only specific calendar provider'
        )
        parser.add_argument(
            '--detect-meetings',
            action='store_true',
            help='Also run meeting detection after sync'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
    
    def handle(self, *args, **options):
        """Handle the command execution"""
        self.stdout.write(
            self.style.SUCCESS('Starting calendar synchronization...')
        )
        
        # Get users to sync
        if options['user_id']:
            try:
                users = [User.objects.get(id=options['user_id'])]
                self.stdout.write(f"Syncing calendars for user ID: {options['user_id']}")
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User with ID {options['user_id']} not found")
                )
                return
        else:
            users = User.objects.filter(is_active=True)
            self.stdout.write(f"Syncing calendars for {users.count()} active users")
        
        # Get providers to sync
        providers = [options['provider']] if options['provider'] else None
        
        # Run sync
        if options['dry_run']:
            self._dry_run_sync(users, providers)
        else:
            asyncio.run(self._run_sync(users, providers, options['detect_meetings']))
    
    def _dry_run_sync(self, users, providers):
        """Show what would be synced without actually syncing"""
        self.stdout.write(self.style.WARNING("DRY RUN - No actual syncing will be performed"))
        
        integration_hub = CalendarIntegrationHub()
        
        for user in users:
            self.stdout.write(f"\nUser: {user.username} ({user.email})")
            
            # Check which providers are connected
            for provider_name in integration_hub.providers.keys():
                if providers and provider_name not in providers:
                    continue
                
                provider = integration_hub.get_provider(provider_name)
                
                # This would need to be made sync for dry run
                self.stdout.write(f"  {provider_name}: Would check connection status")
    
    async def _run_sync(self, users, providers, detect_meetings):
        """Run the actual synchronization"""
        integration_hub = CalendarIntegrationHub()
        
        total_users = len(users)
        successful_syncs = 0
        failed_syncs = 0
        
        for i, user in enumerate(users, 1):
            self.stdout.write(f"\n[{i}/{total_users}] Syncing calendars for {user.username}")
            
            try:
                # Sync user calendars
                sync_results = await integration_hub.sync_user_calendars(user, providers)
                
                # Report sync results
                for provider_name, result in sync_results.items():
                    if result.get('status') == 'success':
                        events_processed = result.get('total_events_processed', 0)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {provider_name}: {events_processed} events processed"
                            )
                        )
                    elif result.get('status') == 'not_connected':
                        self.stdout.write(
                            self.style.WARNING(f"  - {provider_name}: Not connected")
                        )
                    else:
                        error = result.get('error', 'Unknown error')
                        self.stdout.write(
                            self.style.ERROR(f"  ✗ {provider_name}: {error}")
                        )
                
                # Run meeting detection if requested
                if detect_meetings:
                    self.stdout.write("  Running meeting detection...")
                    await integration_hub.process_meetings_for_user(user)
                    
                    # Count newly detected meetings
                    from apps.meetings.models import Meeting
                    recent_meetings = Meeting.objects.filter(
                        organizer=user,
                        created_at__gte=timezone.now() - timedelta(minutes=5)
                    ).count()
                    
                    if recent_meetings > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Detected {recent_meetings} new meetings")
                        )
                
                successful_syncs += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Error syncing calendars: {str(e)}")
                )
                logger.error(f"Error syncing calendars for user {user.id}: {str(e)}")
                failed_syncs += 1
        
        # Summary
        self.stdout.write(f"\n" + "="*50)
        self.stdout.write(f"Synchronization Summary:")
        self.stdout.write(f"  Total users: {total_users}")
        self.stdout.write(
            self.style.SUCCESS(f"  Successful syncs: {successful_syncs}")
        )
        if failed_syncs > 0:
            self.stdout.write(
                self.style.ERROR(f"  Failed syncs: {failed_syncs}")
            )
        
        self.stdout.write(
            self.style.SUCCESS("Calendar synchronization completed!")
        )