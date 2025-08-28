from django.contrib import admin
from .models import AISession, AIInteraction


@admin.register(AISession)
class AISessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'meeting_id', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['session_id', 'meeting_id']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    list_display = ['interaction_type', 'success', 'processing_time', 'created_at']
    list_filter = ['interaction_type', 'success', 'created_at']
    search_fields = ['session__session_id', 'interaction_type']
    readonly_fields = ['created_at']
    ordering = ['-created_at']