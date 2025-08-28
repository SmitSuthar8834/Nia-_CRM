"""
Django Admin configuration for CRM Sync
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db import models
from .models import CreatioSync, SyncConflict, SyncLog, CreatioConfiguration


@admin.register(CreatioSync)
class CreatioSyncAdmin(admin.ModelAdmin):
    """
    Admin interface for CreatioSync records
    """
    list_display = [
        'entity_type', 'local_id_short', 'creatio_id_short', 'sync_status',
        'sync_direction', 'last_sync', 'retry_count', 'needs_retry_display'
    ]
    list_filter = [
        'entity_type', 'sync_status', 'sync_direction', 'created_at', 'last_sync'
    ]
    search_fields = ['local_id', 'creatio_id', 'error_message']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'needs_retry_display',
        'local_data_hash', 'creatio_data_hash'
    ]
    fieldsets = (
        ('Entity Information', {
            'fields': ('entity_type', 'local_id', 'creatio_id')
        }),
        ('Sync Status', {
            'fields': ('sync_status', 'sync_direction', 'last_sync', 'next_sync')
        }),
        ('Error Handling', {
            'fields': ('error_message', 'retry_count', 'max_retries', 'needs_retry_display')
        }),
        ('Data Tracking', {
            'fields': ('local_data_hash', 'creatio_data_hash'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['retry_failed_syncs', 'mark_as_pending', 'reset_retry_count']
    
    def local_id_short(self, obj):
        """Display shortened local ID"""
        return str(obj.local_id)[:8] + '...'
    local_id_short.short_description = 'Local ID'
    
    def creatio_id_short(self, obj):
        """Display shortened Creatio ID"""
        if obj.creatio_id:
            return obj.creatio_id[:8] + '...' if len(obj.creatio_id) > 8 else obj.creatio_id
        return '-'
    creatio_id_short.short_description = 'Creatio ID'
    
    def needs_retry_display(self, obj):
        """Display retry status with color coding"""
        if obj.needs_retry:
            return format_html('<span style="color: orange;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')
    needs_retry_display.short_description = 'Needs Retry'
    
    def retry_failed_syncs(self, request, queryset):
        """Admin action to retry failed syncs"""
        failed_syncs = queryset.filter(sync_status='failed', retry_count__lt=models.F('max_retries'))
        count = 0
        
        for sync_record in failed_syncs:
            if sync_record.needs_retry:
                sync_record.sync_status = 'pending'
                sync_record.next_sync = timezone.now()
                sync_record.save()
                count += 1
        
        self.message_user(request, f'Marked {count} sync records for retry.')
    retry_failed_syncs.short_description = 'Retry failed syncs'
    
    def mark_as_pending(self, request, queryset):
        """Admin action to mark syncs as pending"""
        count = queryset.update(sync_status='pending', next_sync=timezone.now())
        self.message_user(request, f'Marked {count} sync records as pending.')
    mark_as_pending.short_description = 'Mark as pending'
    
    def reset_retry_count(self, request, queryset):
        """Admin action to reset retry count"""
        count = queryset.update(retry_count=0)
        self.message_user(request, f'Reset retry count for {count} sync records.')
    reset_retry_count.short_description = 'Reset retry count'


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    """
    Admin interface for SyncConflict records
    """
    list_display = [
        'sync_record_info', 'conflict_type', 'field_name', 'resolution_status',
        'resolved_by', 'created_at'
    ]
    list_filter = [
        'conflict_type', 'resolution_status', 'created_at', 'resolved_at'
    ]
    search_fields = [
        'sync_record__local_id', 'sync_record__creatio_id', 'field_name'
    ]
    readonly_fields = [
        'id', 'sync_record', 'created_at', 'updated_at', 'resolved_at'
    ]
    fieldsets = (
        ('Conflict Information', {
            'fields': ('sync_record', 'conflict_type', 'field_name')
        }),
        ('Values', {
            'fields': ('local_value', 'creatio_value')
        }),
        ('Resolution', {
            'fields': ('resolution_status', 'resolved_value', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_resolved_local', 'mark_as_resolved_creatio', 'mark_as_ignored']
    
    def sync_record_info(self, obj):
        """Display sync record information"""
        return f"{obj.sync_record.entity_type} - {str(obj.sync_record.local_id)[:8]}..."
    sync_record_info.short_description = 'Sync Record'
    
    def mark_as_resolved_local(self, request, queryset):
        """Admin action to resolve conflicts with local value"""
        count = 0
        for conflict in queryset.filter(resolution_status='pending'):
            conflict.resolve('resolved_local', conflict.local_value, request.user)
            count += 1
        
        self.message_user(request, f'Resolved {count} conflicts with local values.')
    mark_as_resolved_local.short_description = 'Resolve with local value'
    
    def mark_as_resolved_creatio(self, request, queryset):
        """Admin action to resolve conflicts with Creatio value"""
        count = 0
        for conflict in queryset.filter(resolution_status='pending'):
            conflict.resolve('resolved_creatio', conflict.creatio_value, request.user)
            count += 1
        
        self.message_user(request, f'Resolved {count} conflicts with Creatio values.')
    mark_as_resolved_creatio.short_description = 'Resolve with Creatio value'
    
    def mark_as_ignored(self, request, queryset):
        """Admin action to ignore conflicts"""
        count = 0
        for conflict in queryset.filter(resolution_status='pending'):
            conflict.resolve('ignored', None, request.user)
            count += 1
        
        self.message_user(request, f'Ignored {count} conflicts.')
    mark_as_ignored.short_description = 'Ignore conflicts'


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """
    Admin interface for SyncLog records
    """
    list_display = [
        'created_at', 'log_level', 'operation_type', 'entity_type',
        'message_short', 'user', 'execution_time_ms'
    ]
    list_filter = [
        'log_level', 'operation_type', 'entity_type', 'created_at'
    ]
    search_fields = ['message', 'entity_id', 'user__username']
    readonly_fields = [
        'id', 'sync_record', 'created_at', 'request_data', 'response_data'
    ]
    fieldsets = (
        ('Log Information', {
            'fields': ('log_level', 'operation_type', 'message')
        }),
        ('Context', {
            'fields': ('entity_type', 'entity_id', 'user', 'sync_record')
        }),
        ('Technical Details', {
            'fields': ('request_data', 'response_data', 'execution_time_ms'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    date_hierarchy = 'created_at'
    
    def message_short(self, obj):
        """Display shortened message"""
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Message'
    
    def has_add_permission(self, request):
        """Disable adding logs through admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing logs through admin"""
        return False


@admin.register(CreatioConfiguration)
class CreatioConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for CreatioConfiguration records
    """
    list_display = [
        'config_key', 'config_type', 'is_active', 'created_by', 'updated_at'
    ]
    list_filter = ['config_type', 'is_active', 'created_at']
    search_fields = ['config_key', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Configuration', {
            'fields': ('config_type', 'config_key', 'config_value', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_configs', 'deactivate_configs']
    
    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:  # Only set on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_configs(self, request, queryset):
        """Admin action to activate configurations"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'Activated {count} configurations.')
    activate_configs.short_description = 'Activate configurations'
    
    def deactivate_configs(self, request, queryset):
        """Admin action to deactivate configurations"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {count} configurations.')
    deactivate_configs.short_description = 'Deactivate configurations'


# Custom admin site configuration
admin.site.site_header = 'NIA Meeting Intelligence - CRM Sync Administration'
admin.site.site_title = 'CRM Sync Admin'
admin.site.index_title = 'CRM Synchronization Management'