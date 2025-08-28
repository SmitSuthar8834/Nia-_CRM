"""
Calendar Integration Models
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CalendarEvent(models.Model):
    """
    Cached calendar events from external providers
    """
    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Outlook Calendar'),
        ('exchange', 'Exchange Server'),
    ]
    
    EVENT_STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('tentative', 'Tentative'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Provider Information
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_event_id = models.CharField(max_length=200)
    calendar_id = models.CharField(max_length=200)
    
    # Event Details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    timezone = models.CharField(max_length=50, default='UTC')
    location = models.CharField(max_length=200, blank=True, null=True)
    meeting_url = models.URLField(blank=True, null=True)
    
    # Status
    event_status = models.CharField(max_length=20, choices=EVENT_STATUS_CHOICES, default='confirmed')
    is_all_day = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.TextField(blank=True, null=True)
    
    # Organizer and Attendees
    organizer_email = models.EmailField()
    organizer_name = models.CharField(max_length=200, blank=True, null=True)
    attendees = models.JSONField(default=list, help_text="List of attendee information")
    
    # Meeting Intelligence
    meeting_created = models.BooleanField(default=False)
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.SET_NULL, blank=True, null=True)
    
    # Sync Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_events')
    last_modified = models.DateTimeField()
    etag = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'calendar_events'
        unique_together = ['provider', 'provider_event_id', 'user']
        indexes = [
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['provider', 'calendar_id']),
            models.Index(fields=['organizer_email']),
            models.Index(fields=['meeting_created']),
            models.Index(fields=['start_time', 'end_time']),
        ]
        ordering = ['start_time']

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_minutes(self):
        """Calculate event duration in minutes"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return 0

    @property
    def external_attendees(self):
        """Get list of external attendees (not from our organization)"""
        # This would be implemented based on your organization's domain
        return [att for att in self.attendees if not att.get('email', '').endswith('@yourcompany.com')]


class CalendarSyncStatus(models.Model):
    """
    Track calendar synchronization status
    """
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('syncing', 'Syncing'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sync_statuses')
    provider = models.CharField(max_length=20)
    calendar_id = models.CharField(max_length=200)
    
    # Sync Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    last_sync_start = models.DateTimeField(blank=True, null=True)
    last_sync_end = models.DateTimeField(blank=True, null=True)
    last_successful_sync = models.DateTimeField(blank=True, null=True)
    
    # Sync Statistics
    events_processed = models.IntegerField(default=0)
    events_created = models.IntegerField(default=0)
    events_updated = models.IntegerField(default=0)
    events_deleted = models.IntegerField(default=0)
    
    # Error Handling
    error_message = models.TextField(blank=True, null=True)
    error_count = models.IntegerField(default=0)
    
    # Sync Token (for incremental sync)
    sync_token = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'calendar_sync_status'
        unique_together = ['user', 'provider', 'calendar_id']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['last_successful_sync']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.provider} - {self.status}"

    def start_sync(self):
        """Mark sync as started"""
        self.status = 'syncing'
        self.last_sync_start = timezone.now()
        self.save()

    def complete_sync(self, events_stats=None):
        """Mark sync as completed successfully"""
        self.status = 'success'
        self.last_sync_end = timezone.now()
        self.last_successful_sync = self.last_sync_end
        self.error_message = None
        self.error_count = 0
        
        if events_stats:
            self.events_processed = events_stats.get('processed', 0)
            self.events_created = events_stats.get('created', 0)
            self.events_updated = events_stats.get('updated', 0)
            self.events_deleted = events_stats.get('deleted', 0)
        
        self.save()

    def fail_sync(self, error_message):
        """Mark sync as failed"""
        self.status = 'error'
        self.last_sync_end = timezone.now()
        self.error_message = error_message
        self.error_count += 1
        self.save()