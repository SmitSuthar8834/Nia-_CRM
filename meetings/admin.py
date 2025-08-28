from django.contrib import admin
from .models import Meeting, MeetingSession, ActionItem


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'lead', 'start_time', 'status', 'match_confidence']
    list_filter = ['status', 'start_time', 'match_confidence']
    search_fields = ['title', 'calendar_event_id', 'lead__name', 'lead__company']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-start_time']


@admin.register(MeetingSession)
class MeetingSessionAdmin(admin.ModelAdmin):
    list_display = ['meeting', 'started_at', 'ended_at', 'is_active']
    list_filter = ['started_at', 'ended_at']
    search_fields = ['meeting__title', 'ai_session_id']
    readonly_fields = ['started_at']


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = ['description', 'assignee', 'due_date', 'status', 'created_at']
    list_filter = ['status', 'due_date', 'created_at']
    search_fields = ['description', 'assignee', 'crm_task_id']
    readonly_fields = ['created_at', 'updated_at']