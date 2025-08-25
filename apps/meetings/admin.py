"""
Django Admin configuration for Meeting Intelligence
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Meeting, MeetingParticipant, MeetingNote


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    """Admin interface for Meeting model"""
    
    list_display = [
        'title', 'organizer', 'start_time', 'meeting_type', 
        'is_sales_meeting', 'confidence_score', 'status',
        'debriefing_status', 'participant_count'
    ]
    list_filter = [
        'meeting_type', 'is_sales_meeting', 'status', 
        'debriefing_scheduled', 'debriefing_completed',
        'calendar_provider', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'organizer__username', 
        'organizer__email', 'participants__email',
        'participants__name', 'participants__company'
    ]
    readonly_fields = [
        'id', 'calendar_event_id', 'duration_minutes', 
        'is_past', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'start_time'
    ordering = ['-start_time']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'calendar_event_id', 'calendar_provider',
                'title', 'description', 'organizer'
            )
        }),
        ('Schedule', {
            'fields': (
                'start_time', 'end_time', 'timezone', 
                'location', 'meeting_url', 'duration_minutes', 'is_past'
            )
        }),
        ('Meeting Intelligence', {
            'fields': (
                'meeting_type', 'is_sales_meeting', 'confidence_score', 'status'
            )
        }),
        ('Debriefing', {
            'fields': (
                'debriefing_scheduled', 'debriefing_completed', 'debriefing_due_at'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def debriefing_status(self, obj):
        """Display debriefing status with color coding"""
        if obj.debriefing_completed:
            return format_html(
                '<span style="color: green;">✓ Completed</span>'
            )
        elif obj.debriefing_scheduled:
            return format_html(
                '<span style="color: orange;">⏳ Scheduled</span>'
            )
        elif obj.is_sales_meeting:
            return format_html(
                '<span style="color: red;">❌ Not Scheduled</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">N/A</span>'
            )
    debriefing_status.short_description = 'Debriefing Status'
    
    def participant_count(self, obj):
        """Display participant count with link to participants"""
        count = obj.participants.count()
        if count > 0:
            url = reverse('admin:meetings_meetingparticipant_changelist')
            return format_html(
                '<a href="{}?meeting__id__exact={}">{} participants</a>',
                url, obj.id, count
            )
        return '0 participants'
    participant_count.short_description = 'Participants'
    
    actions = ['schedule_debriefing', 'mark_as_sales_meeting']
    
    def schedule_debriefing(self, request, queryset):
        """Admin action to schedule debriefing for selected meetings"""
        count = 0
        for meeting in queryset:
            if meeting.is_sales_meeting and not meeting.debriefing_scheduled:
                meeting.schedule_debriefing()
                count += 1
        
        self.message_user(
            request,
            f'Scheduled debriefing for {count} meetings.'
        )
    schedule_debriefing.short_description = 'Schedule debriefing for selected meetings'
    
    def mark_as_sales_meeting(self, request, queryset):
        """Admin action to mark meetings as sales meetings"""
        count = queryset.update(is_sales_meeting=True)
        self.message_user(
            request,
            f'Marked {count} meetings as sales meetings.'
        )
    mark_as_sales_meeting.short_description = 'Mark as sales meetings'


@admin.register(MeetingParticipant)
class MeetingParticipantAdmin(admin.ModelAdmin):
    """Admin interface for MeetingParticipant model"""
    
    list_display = [
        'display_name', 'email', 'company', 'meeting_title',
        'participant_type', 'is_external', 'match_status', 'match_confidence'
    ]
    list_filter = [
        'participant_type', 'response_status', 'is_external',
        'manual_verification_required', 'match_method', 'created_at'
    ]
    search_fields = [
        'name', 'email', 'company', 'title', 'phone',
        'meeting__title', 'matched_lead__first_name', 'matched_lead__last_name'
    ]
    readonly_fields = ['id', 'display_name', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Participant Information', {
            'fields': (
                'id', 'meeting', 'email', 'name', 'display_name',
                'company', 'title', 'phone'
            )
        }),
        ('Meeting Participation', {
            'fields': (
                'participant_type', 'response_status', 'is_external'
            )
        }),
        ('Lead Matching', {
            'fields': (
                'matched_lead', 'match_confidence', 'match_method',
                'manual_verification_required'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def meeting_title(self, obj):
        """Display meeting title with link"""
        url = reverse('admin:meetings_meeting_change', args=[obj.meeting.id])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.meeting.title
        )
    meeting_title.short_description = 'Meeting'
    
    def match_status(self, obj):
        """Display match status with color coding"""
        if obj.matched_lead:
            if obj.match_confidence >= 0.9:
                color = 'green'
                icon = '✓'
            elif obj.match_confidence >= 0.7:
                color = 'orange'
                icon = '~'
            else:
                color = 'red'
                icon = '?'
            
            return format_html(
                '<span style="color: {};">{} Matched ({:.0%})</span>',
                color, icon, obj.match_confidence
            )
        else:
            return format_html(
                '<span style="color: gray;">❌ Unmatched</span>'
            )
    match_status.short_description = 'Match Status'


@admin.register(MeetingNote)
class MeetingNoteAdmin(admin.ModelAdmin):
    """Admin interface for MeetingNote model"""
    
    list_display = [
        'title', 'meeting_title', 'author', 'note_type',
        'ai_generated', 'ai_confidence', 'created_at'
    ]
    list_filter = [
        'note_type', 'ai_generated', 'created_at', 'updated_at'
    ]
    search_fields = [
        'title', 'content', 'meeting__title', 'author__username'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Note Information', {
            'fields': (
                'id', 'meeting', 'author', 'title', 'content', 'note_type'
            )
        }),
        ('AI Processing', {
            'fields': (
                'ai_generated', 'ai_confidence'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def meeting_title(self, obj):
        """Display meeting title with link"""
        url = reverse('admin:meetings_meeting_change', args=[obj.meeting.id])
        return format_html(
            '<a href="{}">{}</a>',
            url, obj.meeting.title
        )
    meeting_title.short_description = 'Meeting'