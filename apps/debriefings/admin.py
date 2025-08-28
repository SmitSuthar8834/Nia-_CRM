"""
Django Admin configuration for Debriefings
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight, DebriefingTemplate


@admin.register(DebriefingSession)
class DebriefingSessionAdmin(admin.ModelAdmin):
    """Admin interface for Debriefing Sessions"""
    
    list_display = [
        'meeting_title', 'user', 'status_display', 'scheduled_time',
        'duration_display', 'progress_display', 'approval_status',
        'overdue_status'
    ]
    list_filter = [
        'status', 'user_approved', 'scheduled_time', 'user'
    ]
    search_fields = [
        'meeting__title', 'user__username', 'extracted_data'
    ]
    readonly_fields = [
        'id', 'duration_display', 'progress_display', 'overdue_status',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'scheduled_time'
    ordering = ['-scheduled_time']
    
    fieldsets = (
        ('Session Information', {
            'fields': (
                'id', 'meeting', 'user'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_time', 'started_at', 'completed_at',
                'status', 'duration_display', 'overdue_status'
            )
        }),
        ('Conversation Progress', {
            'fields': (
                'current_question_index', 'total_questions', 'progress_display'
            )
        }),
        ('AI Processing', {
            'fields': (
                'extracted_data', 'confidence_scores', 'ai_insights'
            ),
            'classes': ('collapse',)
        }),
        ('User Approval', {
            'fields': (
                'user_approved', 'approval_timestamp', 'user_feedback'
            )
        }),
        ('Conversation Data', {
            'fields': ('conversation_data',),
            'classes': ('collapse',)
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
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'scheduled': 'orange',
            'in_progress': 'blue',
            'completed': 'green',
            'skipped': 'gray',
            'expired': 'red'
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.replace('_', ' ').title()
        )
    status_display.short_description = 'Status'
    
    def duration_display(self, obj):
        """Display session duration"""
        duration = obj.duration_minutes
        if duration > 0:
            return f"{duration} min"
        return '-'
    duration_display.short_description = 'Duration'
    
    def progress_display(self, obj):
        """Display conversation progress"""
        if obj.total_questions > 0:
            percentage = (obj.current_question_index / obj.total_questions) * 100
            return format_html(
                '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
                '<div style="width: {}%; background-color: #007cba; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                '{:.0f}%'
                '</div></div>',
                percentage, percentage
            )
        return '-'
    progress_display.short_description = 'Progress'
    
    def approval_status(self, obj):
        """Display approval status"""
        if obj.user_approved:
            return format_html('<span style="color: green;">✓ Approved</span>')
        elif obj.status == 'completed':
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        else:
            return format_html('<span style="color: gray;">N/A</span>')
    approval_status.short_description = 'Approval'
    
    def overdue_status(self, obj):
        """Display overdue status"""
        if obj.is_overdue:
            return format_html('<span style="color: red;">⚠ Overdue</span>')
        return format_html('<span style="color: green;">✓ On Time</span>')
    overdue_status.short_description = 'Overdue Status'
    
    actions = ['start_sessions', 'complete_sessions', 'approve_sessions']
    
    def start_sessions(self, request, queryset):
        """Admin action to start debriefing sessions"""
        count = 0
        for session in queryset.filter(status='scheduled'):
            session.start_session()
            count += 1
        
        self.message_user(request, f'Started {count} debriefing sessions.')
    start_sessions.short_description = 'Start selected sessions'
    
    def complete_sessions(self, request, queryset):
        """Admin action to complete debriefing sessions"""
        count = 0
        for session in queryset.filter(status='in_progress'):
            session.complete_session()
            count += 1
        
        self.message_user(request, f'Completed {count} debriefing sessions.')
    complete_sessions.short_description = 'Complete selected sessions'
    
    def approve_sessions(self, request, queryset):
        """Admin action to approve completed sessions"""
        from django.utils import timezone
        count = queryset.filter(
            status='completed', 
            user_approved=False
        ).update(
            user_approved=True,
            approval_timestamp=timezone.now()
        )
        
        self.message_user(request, f'Approved {count} debriefing sessions.')
    approve_sessions.short_description = 'Approve completed sessions'


@admin.register(DebriefingQuestion)
class DebriefingQuestionAdmin(admin.ModelAdmin):
    """Admin interface for Debriefing Questions"""
    
    list_display = [
        'session_meeting', 'question_order', 'question_type',
        'question_preview', 'response_status', 'is_follow_up', 'processed'
    ]
    list_filter = [
        'question_type', 'is_follow_up', 'processed', 'created_at'
    ]
    search_fields = [
        'question_text', 'user_response', 'session__meeting__title'
    ]
    readonly_fields = [
        'id', 'response_timestamp', 'created_at', 'updated_at'
    ]
    ordering = ['session', 'question_order']
    
    fieldsets = (
        ('Question Information', {
            'fields': (
                'id', 'session', 'question_order', 'question_type',
                'is_follow_up', 'parent_question'
            )
        }),
        ('Question Content', {
            'fields': (
                'question_text',
            )
        }),
        ('AI Context', {
            'fields': (
                'ai_context', 'ai_prompt'
            ),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': (
                'user_response', 'response_timestamp'
            )
        }),
        ('Processing', {
            'fields': (
                'processed', 'extracted_entities'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def session_meeting(self, obj):
        """Display session meeting title"""
        return obj.session.meeting.title
    session_meeting.short_description = 'Meeting'
    
    def question_preview(self, obj):
        """Display question preview"""
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question'
    
    def response_status(self, obj):
        """Display response status"""
        if obj.user_response:
            return format_html('<span style="color: green;">✓ Answered</span>')
        else:
            return format_html('<span style="color: gray;">⏳ Pending</span>')
    response_status.short_description = 'Response'
    
    def has_add_permission(self, request):
        """Disable adding questions through admin"""
        return False


@admin.register(DebriefingInsight)
class DebriefingInsightAdmin(admin.ModelAdmin):
    """Admin interface for Debriefing Insights"""
    
    list_display = [
        'session_meeting', 'insight_type', 'title', 'confidence_display',
        'priority', 'user_validated', 'created_at'
    ]
    list_filter = [
        'insight_type', 'confidence_level', 'priority', 'user_validated', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'session__meeting__title'
    ]
    readonly_fields = [
        'id', 'confidence_score', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-confidence_score', '-created_at']
    
    fieldsets = (
        ('Insight Information', {
            'fields': (
                'id', 'session', 'insight_type', 'title', 'description'
            )
        }),
        ('Confidence & Priority', {
            'fields': (
                'confidence_level', 'confidence_score', 'priority'
            )
        }),
        ('Source', {
            'fields': (
                'source_question', 'source_text'
            ),
            'classes': ('collapse',)
        }),
        ('Actions', {
            'fields': (
                'suggested_actions',
            ),
            'classes': ('collapse',)
        }),
        ('User Feedback', {
            'fields': (
                'user_validated', 'user_feedback'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def session_meeting(self, obj):
        """Display session meeting title"""
        return obj.session.meeting.title
    session_meeting.short_description = 'Meeting'
    
    def confidence_display(self, obj):
        """Display confidence with color coding"""
        colors = {
            'very_high': 'darkgreen',
            'high': 'green',
            'medium': 'orange',
            'low': 'red'
        }
        
        return format_html(
            '<span style="color: {};">{} ({:.0%})</span>',
            colors.get(obj.confidence_level, 'gray'),
            obj.confidence_level.replace('_', ' ').title(),
            obj.confidence_score
        )
    confidence_display.short_description = 'Confidence'
    
    actions = ['validate_insights', 'mark_high_priority']
    
    def validate_insights(self, request, queryset):
        """Admin action to validate insights"""
        count = queryset.update(user_validated=True)
        self.message_user(request, f'Validated {count} insights.')
    validate_insights.short_description = 'Validate selected insights'
    
    def mark_high_priority(self, request, queryset):
        """Admin action to mark insights as high priority"""
        count = queryset.update(priority='high')
        self.message_user(request, f'Marked {count} insights as high priority.')
    mark_high_priority.short_description = 'Mark as high priority'


@admin.register(DebriefingTemplate)
class DebriefingTemplateAdmin(admin.ModelAdmin):
    """Admin interface for Debriefing Templates"""
    
    list_display = [
        'name', 'template_type', 'is_active', 'usage_count',
        'created_by', 'created_at'
    ]
    list_filter = [
        'template_type', 'is_active', 'created_at'
    ]
    search_fields = [
        'name', 'description', 'created_by__username'
    ]
    readonly_fields = [
        'id', 'usage_count', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Template Information', {
            'fields': (
                'id', 'name', 'template_type', 'description'
            )
        }),
        ('Configuration', {
            'fields': (
                'question_templates', 'ai_prompts', 'extraction_rules'
            ),
            'classes': ('collapse',)
        }),
        ('Usage', {
            'fields': (
                'is_active', 'usage_count'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_templates', 'deactivate_templates', 'reset_usage_count']
    
    def activate_templates(self, request, queryset):
        """Admin action to activate templates"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'Activated {count} templates.')
    activate_templates.short_description = 'Activate selected templates'
    
    def deactivate_templates(self, request, queryset):
        """Admin action to deactivate templates"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {count} templates.')
    deactivate_templates.short_description = 'Deactivate selected templates'
    
    def reset_usage_count(self, request, queryset):
        """Admin action to reset usage count"""
        count = queryset.update(usage_count=0)
        self.message_user(request, f'Reset usage count for {count} templates.')
    reset_usage_count.short_description = 'Reset usage count'


# Custom admin site configuration
admin.site.site_header = 'NIA Meeting Intelligence - Debriefings Administration'
admin.site.site_title = 'Debriefings Admin'
admin.site.index_title = 'Debriefing Management'