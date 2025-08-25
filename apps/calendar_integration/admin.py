"""
Django Admin configuration for Calendar Integration
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from .models import CalendarEvent, CalendarSyncStatus


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """Admin interface for Calendar Events"""
    
    list_display = [
        'title', 'provider', 'organizer_email', 'start_time',
        'duration_display', 'event_status', 'meeting_status',
        'attendee_count', 'user'
    ]
    list_filter = [
        'provider', 'event_status', 'is_all_day', 'is_recurring',
        'meeting_created', 'start_time'
    ]
    search_fields = [
        'title', 'description', 'organizer_email', 'organizer_name',
        'location', 'provider_event_id'
    ]
    readonly_fields = [
        'id', 'provider_event_id', 'calendar_id', 'duration_display',
        'attendee_count', 'external_attendee_count', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'start_time'
    ordering = ['-start_time']
    
    fieldsets = (
        ('Event Information', {
            'fields': (
                'id', 'provider', 'provider_event_id', 'calendar_id'
            )
        }),
        ('Event Details', {
            'fields': (
                'title', 'description', 'location', 'meeting_url'
            )
        }),
        ('Schedule', {
            'fields': (
                'start_time', 'end_time', 'timezone', 'duration_display',
                'is_all_day', 'is_recurring', 'recurrence_rule'
            )
        }),
        ('Status', {
            'fields': (
                'event_status',
            )
        }),
        ('Organizer & Attendees', {
            'fields': (
                'organizer_email', 'organizer_name', 'attendees',
                'attendee_count', 'external_attendee_count'
            ),
            'classes': ('collapse',)
        }),
        ('Meeting Intelligence', {
            'fields': (
                'meeting_created', 'meeting'
            )
        }),
        ('Sync Information', {
            'fields': (
                'user', 'last_modified', 'etag'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def duration_display(self, obj):
        """Display event duration"""
        duration = obj.duration_minutes
        if duration < 60:
            return f"{duration} min"
        else:
            hours = duration // 60
            minutes = duration % 60
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
    duration_display.short_description = 'Duration'
    
    def meeting_status(self, obj):
        """Display meeting creation status"""
        if obj.meeting_created and obj.meeting:
            url = reverse('admin:meetings_meeting_change', args=[obj.meeting.id])
            return format_html(
                '<a href="{}" style="color: green;">✓ Meeting Created</a>',
                url
            )
        elif obj.meeting_created:
            return format_html('<span style="color: orange;">⚠ Meeting Link Broken</span>')
        else:
            return format_html('<span style="color: gray;">❌ No Meeting</span>')
    meeting_status.short_description = 'Meeting Status'
    
    def attendee_count(self, obj):
        """Display total attendee count"""
        return len(obj.attendees) if obj.attendees else 0
    attendee_count.short_description = 'Attendees'
    
    def external_attendee_count(self, obj):
        """Display external attendee count"""
        return len(obj.external_attendees)
    external_attendee_count.short_description = 'External'
    
    actions = ['create_meetings', 'sync_events', 'mark_as_cancelled']
    
    def create_meetings(self, request, queryset):
        """Admin action to create meetings from calendar events"""
        count = 0
        for event in queryset.filter(meeting_created=False):
            # This would trigger meeting creation logic
            if len(event.external_attendees) > 0:  # Only create for events with external attendees
                event.meeting_created = True
                event.save()
                count += 1
        
        self.message_user(request, f'Created meetings for {count} calendar events.')
    create_meetings.short_description = 'Create meetings from selected events'
    
    def sync_events(self, request, queryset):
        """Admin action to trigger sync for selected events"""
        count = queryset.count()
        # This would trigger calendar sync
        self.message_user(request, f'Triggered sync for {count} events.')
    sync_events.short_description = 'Sync selected events'
    
    def mark_as_cancelled(self, request, queryset):
        """Admin action to mark events as cancelled"""
        count = queryset.update(event_status='cancelled')
        self.message_user(request, f'Marked {count} events as cancelled.')
    mark_as_cancelled.short_description = 'Mark as cancelled'


@admin.register(CalendarSyncStatus)
class CalendarSyncStatusAdmin(admin.ModelAdmin):
    """Admin interface for Calendar Sync Status"""
    
    list_display = [
        'user', 'provider', 'calendar_id_short', 'status_display',
        'last_successful_sync', 'events_processed', 'error_count',
        'sync_duration'
    ]
    list_filter = [
        'provider', 'status', 'last_successful_sync'
    ]
    search_fields = [
        'user__username', 'calendar_id', 'error_message'
    ]
    readonly_fields = [
        'id', 'sync_duration', 'created_at', 'updated_at'
    ]
    ordering = ['-last_successful_sync']
    
    fieldsets = (
        ('Sync Information', {
            'fields': (
                'id', 'user', 'provider', 'calendar_id'
            )
        }),
        ('Status', {
            'fields': (
                'status', 'last_sync_start', 'last_sync_end',
                'last_successful_sync', 'sync_duration'
            )
        }),
        ('Statistics', {
            'fields': (
                'events_processed', 'events_created', 'events_updated', 'events_deleted'
            )
        }),
        ('Error Handling', {
            'fields': (
                'error_message', 'error_count'
            )
        }),
        ('Sync Token', {
            'fields': ('sync_token',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def calendar_id_short(self, obj):
        """Display shortened calendar ID"""
        if len(obj.calendar_id) > 20:
            return obj.calendar_id[:20] + '...'
        return obj.calendar_id
    calendar_id_short.short_description = 'Calendar ID'
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'idle': 'gray',
            'syncing': 'orange',
            'success': 'green',
            'error': 'red'
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_display.short_description = 'Status'
    
    def sync_duration(self, obj):
        """Calculate and display sync duration"""
        if obj.last_sync_start and obj.last_sync_end:
            duration = (obj.last_sync_end - obj.last_sync_start).total_seconds()
            if duration < 60:
                return f"{duration:.1f}s"
            else:
                return f"{duration/60:.1f}m"
        return '-'
    sync_duration.short_description = 'Last Sync Duration'
    
    actions = ['trigger_sync', 'reset_sync_status', 'clear_errors']
    
    def trigger_sync(self, request, queryset):
        """Admin action to trigger calendar sync"""
        count = 0
        for sync_status in queryset:
            sync_status.start_sync()
            count += 1
        
        self.message_user(request, f'Triggered sync for {count} calendars.')
    trigger_sync.short_description = 'Trigger calendar sync'
    
    def reset_sync_status(self, request, queryset):
        """Admin action to reset sync status"""
        count = queryset.update(
            status='idle',
            error_message=None,
            error_count=0,
            sync_token=None
        )
        self.message_user(request, f'Reset sync status for {count} calendars.')
    reset_sync_status.short_description = 'Reset sync status'
    
    def clear_errors(self, request, queryset):
        """Admin action to clear error messages"""
        count = queryset.update(error_message=None, error_count=0)
        self.message_user(request, f'Cleared errors for {count} calendars.')
    clear_errors.short_description = 'Clear error messages'


# Custom admin site configuration
admin.site.site_header = 'NIA Meeting Intelligence - Calendar Integration Administration'
admin.site.site_title = 'Calendar Integration Admin'
admin.site.index_title = 'Calendar Integration Management'