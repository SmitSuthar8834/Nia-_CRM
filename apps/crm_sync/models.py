"""
CRM Synchronization Models for Creatio Integration
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CreatioSync(models.Model):
    """
    Track synchronization status between local entities and Creatio CRM
    """
    ENTITY_TYPE_CHOICES = [
        ('lead', 'Lead'),
        ('contact', 'Contact'),
        ('account', 'Account'),
        ('opportunity', 'Opportunity'),
        ('activity', 'Activity'),
        ('meeting', 'Meeting'),
        ('task', 'Task'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('conflict', 'Conflict'),
        ('manual_review', 'Manual Review Required'),
    ]
    
    SYNC_DIRECTION_CHOICES = [
        ('to_creatio', 'To Creatio'),
        ('from_creatio', 'From Creatio'),
        ('bidirectional', 'Bidirectional'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Entity Information
    entity_type = models.CharField(max_length=50, choices=ENTITY_TYPE_CHOICES)
    local_id = models.UUIDField(help_text="Local entity UUID")
    creatio_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Sync Status
    sync_status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default='pending')
    sync_direction = models.CharField(max_length=20, choices=SYNC_DIRECTION_CHOICES, default='to_creatio')
    last_sync = models.DateTimeField(blank=True, null=True)
    next_sync = models.DateTimeField(blank=True, null=True)
    
    # Error Handling
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    # Data Tracking
    local_data_hash = models.CharField(max_length=64, blank=True, null=True)
    creatio_data_hash = models.CharField(max_length=64, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'creatio_sync'
        unique_together = ['entity_type', 'local_id']
        indexes = [
            models.Index(fields=['entity_type', 'sync_status']),
            models.Index(fields=['creatio_id']),
            models.Index(fields=['sync_status', 'next_sync']),
            models.Index(fields=['last_sync']),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.entity_type} {self.local_id} - {self.sync_status}"

    @property
    def needs_retry(self):
        """Check if sync needs retry"""
        return (self.sync_status == 'failed' and 
                self.retry_count < self.max_retries)

    def mark_success(self, creatio_id=None):
        """Mark sync as successful"""
        self.sync_status = 'success'
        self.last_sync = timezone.now()
        self.error_message = None
        if creatio_id:
            self.creatio_id = creatio_id
        self.save()

    def mark_failed(self, error_message):
        """Mark sync as failed with error message"""
        self.sync_status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        if self.retry_count < self.max_retries:
            # Schedule retry with exponential backoff
            retry_delay = 2 ** self.retry_count  # 2, 4, 8 minutes
            self.next_sync = timezone.now() + timezone.timedelta(minutes=retry_delay)
        self.save()


class SyncConflict(models.Model):
    """
    Handle data conflicts during synchronization
    """
    CONFLICT_TYPE_CHOICES = [
        ('data_mismatch', 'Data Mismatch'),
        ('concurrent_update', 'Concurrent Update'),
        ('missing_dependency', 'Missing Dependency'),
        ('validation_error', 'Validation Error'),
        ('permission_denied', 'Permission Denied'),
    ]
    
    RESOLUTION_STATUS_CHOICES = [
        ('pending', 'Pending Resolution'),
        ('resolved_local', 'Resolved - Local Wins'),
        ('resolved_creatio', 'Resolved - Creatio Wins'),
        ('resolved_manual', 'Resolved - Manual Merge'),
        ('ignored', 'Ignored'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_record = models.ForeignKey(CreatioSync, on_delete=models.CASCADE, related_name='conflicts')
    
    # Conflict Details
    conflict_type = models.CharField(max_length=50, choices=CONFLICT_TYPE_CHOICES)
    field_name = models.CharField(max_length=100, blank=True, null=True)
    local_value = models.JSONField(blank=True, null=True)
    creatio_value = models.JSONField(blank=True, null=True)
    
    # Resolution
    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_STATUS_CHOICES, default='pending')
    resolved_value = models.JSONField(blank=True, null=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sync_conflicts'
        indexes = [
            models.Index(fields=['sync_record', 'resolution_status']),
            models.Index(fields=['conflict_type']),
            models.Index(fields=['resolved_by']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Conflict: {self.conflict_type} - {self.sync_record.entity_type}"

    def resolve(self, resolution_status, resolved_value=None, user=None, notes=None):
        """Resolve the conflict"""
        self.resolution_status = resolution_status
        self.resolved_value = resolved_value
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


class SyncLog(models.Model):
    """
    Detailed logging for sync operations
    """
    LOG_LEVEL_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    OPERATION_TYPE_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('read', 'Read'),
        ('sync', 'Sync'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_record = models.ForeignKey(CreatioSync, on_delete=models.CASCADE, related_name='logs', blank=True, null=True)
    
    # Log Details
    log_level = models.CharField(max_length=20, choices=LOG_LEVEL_CHOICES)
    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPE_CHOICES)
    message = models.TextField()
    
    # Context
    entity_type = models.CharField(max_length=50, blank=True, null=True)
    entity_id = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Technical Details
    request_data = models.JSONField(blank=True, null=True)
    response_data = models.JSONField(blank=True, null=True)
    execution_time_ms = models.IntegerField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sync_logs'
        indexes = [
            models.Index(fields=['log_level', 'created_at']),
            models.Index(fields=['operation_type', 'created_at']),
            models.Index(fields=['entity_type', 'created_at']),
            models.Index(fields=['sync_record']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.log_level.upper()}: {self.operation_type} - {self.message[:50]}"


class CreatioConfiguration(models.Model):
    """
    Configuration settings for Creatio CRM integration
    """
    CONFIG_TYPE_CHOICES = [
        ('api_endpoint', 'API Endpoint'),
        ('field_mapping', 'Field Mapping'),
        ('sync_schedule', 'Sync Schedule'),
        ('business_rule', 'Business Rule'),
        ('webhook', 'Webhook Configuration'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Configuration Details
    config_type = models.CharField(max_length=50, choices=CONFIG_TYPE_CHOICES)
    config_key = models.CharField(max_length=100, unique=True)
    config_value = models.JSONField()
    description = models.TextField(blank=True, null=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'creatio_configuration'
        indexes = [
            models.Index(fields=['config_type', 'is_active']),
            models.Index(fields=['config_key']),
        ]
        ordering = ['config_type', 'config_key']

    def __str__(self):
        return f"{self.config_type}: {self.config_key}"