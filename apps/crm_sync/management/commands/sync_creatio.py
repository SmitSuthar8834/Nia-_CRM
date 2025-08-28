"""
Management command for Creatio CRM synchronization
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q, F
from django.db import models

from apps.crm_sync.services import CRMSyncService
from apps.crm_sync.models import CreatioSync, SyncConflict
from apps.leads.models import Lead


class Command(BaseCommand):
    """
    Management command for CRM synchronization operations
    """
    help = 'Manage Creatio CRM synchronization'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['sync-all', 'sync-lead', 'status', 'conflicts', 'retry-failed', 'test-connection'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--lead-id',
            type=str,
            help='Lead ID for single lead sync'
        )
        
        parser.add_argument(
            '--direction',
            choices=['to_creatio', 'from_creatio', 'bidirectional'],
            default='bidirectional',
            help='Sync direction'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if no changes detected'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        
        parser.add_argument(
            '--resolve-conflicts',
            choices=['local', 'creatio', 'ignore'],
            help='Auto-resolve conflicts with specified strategy'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'sync-all':
                self.handle_sync_all(options)
            elif action == 'sync-lead':
                self.handle_sync_lead(options)
            elif action == 'status':
                self.handle_status(options)
            elif action == 'conflicts':
                self.handle_conflicts(options)
            elif action == 'retry-failed':
                self.handle_retry_failed(options)
            elif action == 'test-connection':
                self.handle_test_connection(options)
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')
    
    def handle_sync_all(self, options):
        """Handle sync-all action"""
        self.stdout.write('Starting bidirectional synchronization...')
        
        if options['dry_run']:
            self.show_sync_preview()
            return
        
        service = CRMSyncService()
        result = service.sync_all_leads(force=options['force'])
        
        if result['success']:
            sync_result = result['result']
            self.stdout.write(
                self.style.SUCCESS(
                    f"Synchronization completed successfully:\n"
                    f"  - Leads synced to Creatio: {sync_result['leads_synced_to_creatio']}\n"
                    f"  - Leads synced from Creatio: {sync_result['leads_synced_from_creatio']}\n"
                    f"  - Conflicts detected: {sync_result['conflicts_detected']}\n"
                    f"  - Duration: {sync_result.get('duration_seconds', 0):.2f} seconds"
                )
            )
            
            if sync_result['errors']:
                self.stdout.write(
                    self.style.WARNING(
                        f"Errors encountered:\n" + 
                        "\n".join(f"  - {error}" for error in sync_result['errors'])
                    )
                )
        else:
            self.stdout.write(
                self.style.ERROR(f"Synchronization failed: {result['error']}")
            )
    
    def handle_sync_lead(self, options):
        """Handle sync-lead action"""
        lead_id = options.get('lead_id')
        if not lead_id:
            raise CommandError('--lead-id is required for sync-lead action')
        
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            raise CommandError(f'Lead with ID {lead_id} not found')
        
        self.stdout.write(f'Syncing lead: {lead.full_name} ({lead.email})')
        
        if options['dry_run']:
            self.stdout.write('DRY RUN: Would sync this lead')
            return
        
        service = CRMSyncService()
        result = service.sync_single_lead(lead_id, options['direction'])
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Lead synced successfully. Creatio ID: {result.get('creatio_id', 'N/A')}"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Lead sync failed: {result['error']}")
            )
    
    def handle_status(self, options):
        """Handle status action"""
        service = CRMSyncService()
        status_data = service.get_sync_status()
        
        self.stdout.write(self.style.SUCCESS('=== CRM Synchronization Status ==='))
        
        # Sync status summary
        self.stdout.write('\nSync Status Summary:')
        for status_name, count in status_data['sync_status'].items():
            self.stdout.write(f'  {status_name}: {count}')
        
        # Conflicts summary
        self.stdout.write('\nConflicts Summary:')
        for resolution_status, count in status_data['conflicts'].items():
            self.stdout.write(f'  {resolution_status}: {count}')
        
        # Last sync info
        last_sync = status_data.get('last_sync')
        if last_sync:
            self.stdout.write(f'\nLast successful sync: {last_sync.last_sync}')
        else:
            self.stdout.write('\nNo successful syncs found')
        
        # Pending syncs
        pending_count = CreatioSync.objects.filter(sync_status='pending').count()
        failed_count = CreatioSync.objects.filter(sync_status='failed').count()
        
        self.stdout.write(f'\nPending syncs: {pending_count}')
        self.stdout.write(f'Failed syncs: {failed_count}')
    
    def handle_conflicts(self, options):
        """Handle conflicts action"""
        conflicts = SyncConflict.objects.filter(resolution_status='pending')
        
        if not conflicts.exists():
            self.stdout.write(self.style.SUCCESS('No pending conflicts found'))
            return
        
        self.stdout.write(f'Found {conflicts.count()} pending conflicts:')
        
        for conflict in conflicts:
            self.stdout.write(
                f'\nConflict ID: {conflict.id}\n'
                f'  Entity: {conflict.sync_record.entity_type} ({conflict.sync_record.local_id})\n'
                f'  Field: {conflict.field_name}\n'
                f'  Local value: {conflict.local_value}\n'
                f'  Creatio value: {conflict.creatio_value}\n'
                f'  Type: {conflict.conflict_type}'
            )
        
        # Auto-resolve if requested
        resolve_strategy = options.get('resolve_conflicts')
        if resolve_strategy:
            self.auto_resolve_conflicts(conflicts, resolve_strategy)
    
    def handle_retry_failed(self, options):
        """Handle retry-failed action"""
        failed_syncs = CreatioSync.objects.filter(
            sync_status='failed',
            retry_count__lt=models.F('max_retries')
        )
        
        if not failed_syncs.exists():
            self.stdout.write(self.style.SUCCESS('No failed syncs to retry'))
            return
        
        self.stdout.write(f'Found {failed_syncs.count()} failed syncs to retry')
        
        if options['dry_run']:
            for sync_record in failed_syncs:
                self.stdout.write(
                    f'Would retry: {sync_record.entity_type} {sync_record.local_id} '
                    f'(attempt {sync_record.retry_count + 1}/{sync_record.max_retries})'
                )
            return
        
        # Reset failed syncs to pending
        count = 0
        for sync_record in failed_syncs:
            sync_record.sync_status = 'pending'
            sync_record.next_sync = timezone.now()
            sync_record.save()
            count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Marked {count} failed syncs for retry')
        )
    
    def handle_test_connection(self, options):
        """Handle test-connection action"""
        self.stdout.write('Testing Creatio connection...')
        
        try:
            from apps.crm_sync.adapters import CreatioAdapter
            
            adapter = CreatioAdapter()
            token = adapter.authenticate()
            
            if token:
                self.stdout.write(
                    self.style.SUCCESS('✓ Successfully connected to Creatio')
                )
                
                # Test a simple API call
                try:
                    response = adapter._make_request('GET', adapter.leads_endpoint + '?$top=1')
                    self.stdout.write(
                        self.style.SUCCESS('✓ API calls working correctly')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ Authentication successful but API call failed: {str(e)}')
                    )
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Failed to authenticate with Creatio')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Connection test failed: {str(e)}')
            )
    
    def show_sync_preview(self):
        """Show what would be synced in dry run mode"""
        self.stdout.write('DRY RUN - Sync Preview:')
        
        # Leads that would be synced to Creatio
        leads_to_creatio = Lead.objects.filter(
            Q(creatio_id__isnull=True) |  # New leads
            Q(updated_at__gt=models.F('creatiosync__last_sync'))  # Updated leads
        ).exclude(creatiosync__sync_status='in_progress')
        
        self.stdout.write(f'\nLeads to sync to Creatio: {leads_to_creatio.count()}')
        for lead in leads_to_creatio[:5]:  # Show first 5
            status = 'CREATE' if not lead.creatio_id else 'UPDATE'
            self.stdout.write(f'  [{status}] {lead.full_name} - {lead.email}')
        
        if leads_to_creatio.count() > 5:
            self.stdout.write(f'  ... and {leads_to_creatio.count() - 5} more')
        
        # Pending conflicts
        pending_conflicts = SyncConflict.objects.filter(resolution_status='pending').count()
        self.stdout.write(f'\nPending conflicts: {pending_conflicts}')
        
        # Failed syncs that would be retried
        failed_syncs = CreatioSync.objects.filter(
            sync_status='failed',
            retry_count__lt=models.F('max_retries')
        ).count()
        self.stdout.write(f'Failed syncs to retry: {failed_syncs}')
    
    def auto_resolve_conflicts(self, conflicts, strategy):
        """Auto-resolve conflicts with specified strategy"""
        self.stdout.write(f'\nAuto-resolving conflicts with strategy: {strategy}')
        
        service = CRMSyncService()
        resolved_count = 0
        
        for conflict in conflicts:
            try:
                if strategy == 'local':
                    resolution = 'local_wins'
                elif strategy == 'creatio':
                    resolution = 'creatio_wins'
                else:  # ignore
                    resolution = 'ignore'
                
                result = service.resolve_sync_conflict(
                    str(conflict.id),
                    resolution
                )
                
                if result['success']:
                    resolved_count += 1
                    self.stdout.write(f'  ✓ Resolved conflict {conflict.id}')
                else:
                    self.stdout.write(f'  ✗ Failed to resolve conflict {conflict.id}: {result["error"]}')
                    
            except Exception as e:
                self.stdout.write(f'  ✗ Error resolving conflict {conflict.id}: {str(e)}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Auto-resolved {resolved_count} conflicts')
        )