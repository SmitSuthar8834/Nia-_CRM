"""
Management command to clean up expired data based on retention policies
"""
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from apps.accounts.models import (
    DataRetentionPolicy, DataDeletionRequest, EncryptedDataField,
    UserActivity, LoginAttempt, ConsentRecord, PrivacySettings
)
from meetings.models import CallBotSession, DraftSummary, ValidationSession


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired data based on retention policies'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--data-type',
            type=str,
            help='Only process specific data type',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force deletion even if user consent is required',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of records to process in each batch',
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        self.dry_run = options['dry_run']
        self.data_type_filter = options['data_type']
        self.force = options['force']
        self.batch_size = options['batch_size']
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be deleted')
            )
        
        # Get all retention policies
        policies = DataRetentionPolicy.objects.filter(auto_delete_enabled=True)
        
        if self.data_type_filter:
            policies = policies.filter(data_type=self.data_type_filter)
        
        if not policies.exists():
            self.stdout.write(
                self.style.WARNING('No retention policies found')
            )
            return
        
        total_deleted = 0
        
        for policy in policies:
            self.stdout.write(
                f'Processing retention policy for {policy.data_type} '
                f'({policy.retention_period_days} days)'
            )
            
            deleted_count = self._process_policy(policy)
            total_deleted += deleted_count
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {policy.data_type}: {deleted_count} records'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Total records processed: {total_deleted}'
            )
        )
    
    def _process_policy(self, policy):
        """Process a single retention policy"""
        cutoff_date = timezone.now() - policy.retention_period_timedelta
        deleted_count = 0
        
        try:
            if policy.data_type == 'meeting_transcripts':
                deleted_count = self._cleanup_meeting_transcripts(cutoff_date, policy)
            
            elif policy.data_type == 'call_recordings':
                deleted_count = self._cleanup_call_recordings(cutoff_date, policy)
            
            elif policy.data_type == 'user_profiles':
                deleted_count = self._cleanup_user_profiles(cutoff_date, policy)
            
            elif policy.data_type == 'login_attempts':
                deleted_count = self._cleanup_login_attempts(cutoff_date, policy)
            
            elif policy.data_type == 'activity_logs':
                deleted_count = self._cleanup_activity_logs(cutoff_date, policy)
            
            elif policy.data_type == 'consent_records':
                deleted_count = self._cleanup_consent_records(cutoff_date, policy)
            
            elif policy.data_type == 'crm_sync_data':
                deleted_count = self._cleanup_crm_sync_data(cutoff_date, policy)
            
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Unknown data type: {policy.data_type}'
                    )
                )
        
        except Exception as e:
            logger.error(f'Error processing policy {policy.data_type}: {str(e)}')
            self.stdout.write(
                self.style.ERROR(
                    f'Error processing {policy.data_type}: {str(e)}'
                )
            )
        
        return deleted_count
    
    def _cleanup_meeting_transcripts(self, cutoff_date, policy):
        """Clean up meeting transcripts"""
        # Find encrypted transcript data older than cutoff
        expired_transcripts = EncryptedDataField.objects.filter(
            field_type='transcript',
            created_at__lt=cutoff_date
        )
        
        if policy.require_user_consent and not self.force:
            # Only delete if user has auto-delete enabled
            user_ids_with_consent = PrivacySettings.objects.filter(
                auto_delete_transcripts=True
            ).values_list('user_id', flat=True)
            
            expired_transcripts = expired_transcripts.filter(
                owner_id__in=user_ids_with_consent
            )
        
        count = expired_transcripts.count()
        
        if not self.dry_run and count > 0:
            # Archive before delete if required
            if policy.archive_before_delete:
                self._archive_data('transcripts', expired_transcripts)
            
            # Delete in batches
            self._delete_in_batches(expired_transcripts)
        
        return count
    
    def _cleanup_call_recordings(self, cutoff_date, policy):
        """Clean up call recordings"""
        # Find call bot sessions older than cutoff
        expired_sessions = CallBotSession.objects.filter(
            join_time__lt=cutoff_date
        )
        
        count = expired_sessions.count()
        
        if not self.dry_run and count > 0:
            if policy.archive_before_delete:
                self._archive_data('call_recordings', expired_sessions)
            
            self._delete_in_batches(expired_sessions)
        
        return count
    
    def _cleanup_user_profiles(self, cutoff_date, policy):
        """Clean up inactive user profiles"""
        # Find users who haven't logged in for the retention period
        # and have requested account deletion
        inactive_users = User.objects.filter(
            last_login__lt=cutoff_date,
            is_active=False
        )
        
        # Only delete users with pending deletion requests
        users_with_deletion_requests = DataDeletionRequest.objects.filter(
            status='pending',
            data_types__contains=['user_profiles']
        ).values_list('user_id', flat=True)
        
        inactive_users = inactive_users.filter(id__in=users_with_deletion_requests)
        
        count = inactive_users.count()
        
        if not self.dry_run and count > 0:
            if policy.archive_before_delete:
                self._archive_data('user_profiles', inactive_users)
            
            # This is a critical operation - log it
            for user in inactive_users:
                logger.warning(f'Deleting inactive user: {user.username}')
            
            self._delete_in_batches(inactive_users)
        
        return count
    
    def _cleanup_login_attempts(self, cutoff_date, policy):
        """Clean up old login attempts"""
        expired_attempts = LoginAttempt.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = expired_attempts.count()
        
        if not self.dry_run and count > 0:
            self._delete_in_batches(expired_attempts)
        
        return count
    
    def _cleanup_activity_logs(self, cutoff_date, policy):
        """Clean up old activity logs"""
        expired_activities = UserActivity.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = expired_activities.count()
        
        if not self.dry_run and count > 0:
            if policy.archive_before_delete:
                self._archive_data('activity_logs', expired_activities)
            
            self._delete_in_batches(expired_activities)
        
        return count
    
    def _cleanup_consent_records(self, cutoff_date, policy):
        """Clean up old consent records"""
        # Only delete withdrawn or expired consent records
        expired_consents = ConsentRecord.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['withdrawn', 'expired']
        )
        
        count = expired_consents.count()
        
        if not self.dry_run and count > 0:
            if policy.archive_before_delete:
                self._archive_data('consent_records', expired_consents)
            
            self._delete_in_batches(expired_consents)
        
        return count
    
    def _cleanup_crm_sync_data(self, cutoff_date, policy):
        """Clean up old CRM sync data"""
        # This would clean up CRM sync records from meetings app
        # For now, we'll just return 0 as placeholder
        return 0
    
    def _delete_in_batches(self, queryset):
        """Delete records in batches to avoid memory issues"""
        total_count = queryset.count()
        deleted_count = 0
        
        while deleted_count < total_count:
            batch = queryset[:self.batch_size]
            batch_ids = list(batch.values_list('id', flat=True))
            
            if not batch_ids:
                break
            
            with transaction.atomic():
                queryset.filter(id__in=batch_ids).delete()
            
            deleted_count += len(batch_ids)
            
            self.stdout.write(f'Deleted batch: {deleted_count}/{total_count}')
    
    def _archive_data(self, data_type, queryset):
        """Archive data before deletion"""
        # This would implement data archiving logic
        # For now, just log that archiving would happen
        count = queryset.count()
        logger.info(f'Would archive {count} {data_type} records')
        
        if not self.dry_run:
            # In a real implementation, this would:
            # 1. Export data to archive storage (S3, etc.)
            # 2. Compress and encrypt archived data
            # 3. Create archive metadata records
            pass
    
    def _check_user_consent(self, user_id, data_type):
        """Check if user has consented to data deletion"""
        try:
            privacy_settings = PrivacySettings.objects.get(user_id=user_id)
            
            if data_type == 'meeting_transcripts':
                return privacy_settings.auto_delete_transcripts
            
            # Add other data type consent checks as needed
            return False
            
        except PrivacySettings.DoesNotExist:
            return False
    
    def _create_deletion_audit_log(self, data_type, count, policy):
        """Create audit log for data deletion"""
        logger.info(
            f'Data deletion completed: {data_type}, '
            f'count: {count}, policy: {policy.id}'
        )
        
        # In a real implementation, this would create a formal audit record