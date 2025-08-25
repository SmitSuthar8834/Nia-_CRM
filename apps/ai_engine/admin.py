"""
Django Admin configuration for AI Engine
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from .models import AIPromptTemplate, AIInteraction, AICache, AIFeedback


@admin.register(AIPromptTemplate)
class AIPromptTemplateAdmin(admin.ModelAdmin):
    """Admin interface for AI Prompt Templates"""
    
    list_display = [
        'name', 'template_type', 'context', 'is_active', 
        'usage_count', 'success_rate_display', 'average_response_time',
        'version', 'created_by'
    ]
    list_filter = [
        'template_type', 'context', 'is_active', 'version', 'created_at'
    ]
    search_fields = [
        'name', 'prompt_template', 'system_prompt', 'created_by__username'
    ]
    readonly_fields = [
        'id', 'usage_count', 'average_response_time', 'success_rate',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Template Information', {
            'fields': (
                'id', 'name', 'template_type', 'context', 'version'
            )
        }),
        ('Prompt Content', {
            'fields': (
                'prompt_template', 'system_prompt'
            )
        }),
        ('AI Configuration', {
            'fields': (
                'temperature', 'max_tokens'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'usage_count', 'average_response_time', 'success_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_templates', 'deactivate_templates', 'reset_usage_stats']
    
    def success_rate_display(self, obj):
        """Display success rate with color coding"""
        if obj.success_rate >= 0.9:
            color = 'green'
        elif obj.success_rate >= 0.7:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, obj.success_rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
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
    
    def reset_usage_stats(self, request, queryset):
        """Admin action to reset usage statistics"""
        count = queryset.update(usage_count=0, average_response_time=0.0, success_rate=0.0)
        self.message_user(request, f'Reset usage statistics for {count} templates.')
    reset_usage_stats.short_description = 'Reset usage statistics'


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    """Admin interface for AI Interactions"""
    
    list_display = [
        'created_at', 'interaction_type', 'user', 'status',
        'response_time_display', 'confidence_score', 'token_count',
        'cost_estimate', 'retry_count'
    ]
    list_filter = [
        'interaction_type', 'status', 'entity_type', 'created_at'
    ]
    search_fields = [
        'user__username', 'formatted_prompt', 'ai_response', 'error_message'
    ]
    readonly_fields = [
        'id', 'created_at', 'completed_at', 'response_time_ms'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Interaction Details', {
            'fields': (
                'id', 'interaction_type', 'user', 'prompt_template'
            )
        }),
        ('Request', {
            'fields': (
                'input_data', 'formatted_prompt'
            ),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': (
                'ai_response', 'parsed_response', 'confidence_score'
            ),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': (
                'status', 'response_time_ms', 'token_count', 'cost_estimate'
            )
        }),
        ('Error Handling', {
            'fields': (
                'error_message', 'retry_count'
            )
        }),
        ('Context', {
            'fields': (
                'entity_type', 'entity_id'
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'completed_at'),
            'classes': ('collapse',)
        })
    )
    
    def response_time_display(self, obj):
        """Display response time with color coding"""
        if not obj.response_time_ms:
            return '-'
        
        if obj.response_time_ms < 1000:
            color = 'green'
        elif obj.response_time_ms < 3000:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{} ms</span>',
            color, obj.response_time_ms
        )
    response_time_display.short_description = 'Response Time'
    
    def has_add_permission(self, request):
        """Disable adding interactions through admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make interactions read-only"""
        return False


@admin.register(AICache)
class AICacheAdmin(admin.ModelAdmin):
    """Admin interface for AI Cache"""
    
    list_display = [
        'interaction_type', 'hit_count', 'last_accessed',
        'expires_at', 'is_expired_display', 'confidence_score'
    ]
    list_filter = [
        'interaction_type', 'expires_at', 'created_at'
    ]
    search_fields = [
        'prompt_hash', 'original_prompt', 'cached_response'
    ]
    readonly_fields = [
        'id', 'prompt_hash', 'hit_count', 'last_accessed', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Cache Information', {
            'fields': (
                'id', 'prompt_hash', 'interaction_type', 'template_used'
            )
        }),
        ('Cached Data', {
            'fields': (
                'cached_response', 'cached_parsed_data', 'confidence_score'
            ),
            'classes': ('collapse',)
        }),
        ('Cache Metadata', {
            'fields': (
                'hit_count', 'last_accessed', 'expires_at'
            )
        }),
        ('Original Request', {
            'fields': ('original_prompt',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['clear_expired_cache', 'extend_cache_expiry']
    
    def is_expired_display(self, obj):
        """Display expiry status with color coding"""
        if obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        elif obj.expires_at:
            return format_html('<span style="color: green;">Valid</span>')
        else:
            return format_html('<span style="color: blue;">No Expiry</span>')
    is_expired_display.short_description = 'Status'
    
    def clear_expired_cache(self, request, queryset):
        """Admin action to clear expired cache entries"""
        from django.utils import timezone
        expired_count = queryset.filter(expires_at__lt=timezone.now()).delete()[0]
        self.message_user(request, f'Cleared {expired_count} expired cache entries.')
    clear_expired_cache.short_description = 'Clear expired cache entries'
    
    def extend_cache_expiry(self, request, queryset):
        """Admin action to extend cache expiry by 24 hours"""
        from django.utils import timezone
        count = 0
        for cache_entry in queryset:
            if cache_entry.expires_at:
                cache_entry.expires_at += timezone.timedelta(hours=24)
                cache_entry.save()
                count += 1
        
        self.message_user(request, f'Extended expiry for {count} cache entries.')
    extend_cache_expiry.short_description = 'Extend cache expiry by 24 hours'


@admin.register(AIFeedback)
class AIFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for AI Feedback"""
    
    list_display = [
        'interaction_type', 'user', 'feedback_type', 'rating',
        'created_at'
    ]
    list_filter = [
        'feedback_type', 'rating', 'interaction__interaction_type', 'created_at'
    ]
    search_fields = [
        'user__username', 'comments', 'improvement_notes'
    ]
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Feedback Details', {
            'fields': (
                'id', 'interaction', 'user', 'feedback_type', 'rating'
            )
        }),
        ('Comments', {
            'fields': (
                'comments', 'suggested_response', 'improvement_notes'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def interaction_type(self, obj):
        """Display interaction type"""
        return obj.interaction.interaction_type
    interaction_type.short_description = 'Interaction Type'
    
    def has_change_permission(self, request, obj=None):
        """Make feedback read-only after creation"""
        return False


# Custom admin site configuration
admin.site.site_header = 'NIA Meeting Intelligence - AI Engine Administration'
admin.site.site_title = 'AI Engine Admin'
admin.site.index_title = 'AI Engine Management'