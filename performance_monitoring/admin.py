"""
Admin interface for performance monitoring
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold, ConcurrentCallMetrics
)


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    """Admin for PerformanceMetric model"""
    
    list_display = [
        'metric_name', 'metric_type', 'value', 'unit', 'status', 
        'timestamp', 'content_object_link'
    ]
    list_filter = [
        'metric_type', 'status', 'timestamp', 'unit'
    ]
    search_fields = ['metric_name', 'metric_type']
    readonly_fields = ['timestamp', 'duration']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('metric_type', 'metric_name', 'value', 'unit', 'status')
        }),
        ('Timing', {
            'fields': ('timestamp', 'start_time', 'end_time', 'duration')
        }),
        ('Context', {
            'fields': ('content_type', 'object_id', 'metadata')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    def content_object_link(self, obj):
        """Display link to related content object"""
        if obj.content_object:
            url = reverse(
                f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change',
                args=[obj.object_id]
            )
            return format_html('<a href="{}">{}</a>', url, str(obj.content_object))
        return '-'
    content_object_link.short_description = 'Related Object'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')


@admin.register(CallBotPerformance)
class CallBotPerformanceAdmin(admin.ModelAdmin):
    """Admin for CallBotPerformance model"""
    
    list_display = [
        'call_bot_session', 'connection_time', 'connection_success',
        'audio_quality_score', 'transcription_accuracy', 'error_count',
        'overall_score_display', 'created_at'
    ]
    list_filter = [
        'connection_success', 'created_at', 'call_bot_session__platform'
    ]
    search_fields = ['call_bot_session__bot_session_id', 'call_bot_session__meeting__title']
    readonly_fields = ['overall_score_display', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('call_bot_session',)
        }),
        ('Connection Metrics', {
            'fields': ('connection_time', 'connection_attempts', 'connection_success')
        }),
        ('Audio Quality', {
            'fields': ('audio_quality_score', 'audio_dropouts', 'audio_latency')
        }),
        ('Transcription', {
            'fields': ('transcription_accuracy', 'transcription_latency', 'words_per_minute')
        }),
        ('Error Tracking', {
            'fields': ('error_count', 'reconnection_count')
        }),
        ('Resource Usage', {
            'fields': ('cpu_usage_avg', 'memory_usage_avg')
        }),
        ('Performance Score', {
            'fields': ('overall_score_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def overall_score_display(self, obj):
        """Display overall performance score with color coding"""
        score = obj.overall_score
        if score >= 0.8:
            color = 'green'
        elif score >= 0.6:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.2f}</span>',
            color, score
        )
    overall_score_display.short_description = 'Overall Score'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'call_bot_session__meeting'
        )


@admin.register(AIProcessingPerformance)
class AIProcessingPerformanceAdmin(admin.ModelAdmin):
    """Admin for AIProcessingPerformance model"""
    
    list_display = [
        'operation_type', 'operation_id', 'processing_time',
        'confidence_score', 'processing_rate_display', 'error_occurred',
        'timestamp'
    ]
    list_filter = [
        'operation_type', 'error_occurred', 'timestamp', 'model_version'
    ]
    search_fields = ['operation_id', 'operation_type']
    readonly_fields = ['processing_rate_display', 'timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Operation Information', {
            'fields': ('operation_type', 'operation_id', 'model_version')
        }),
        ('Performance Metrics', {
            'fields': ('processing_time', 'input_size', 'output_size', 'processing_rate_display')
        }),
        ('Quality Metrics', {
            'fields': ('confidence_score', 'accuracy_score')
        }),
        ('Resource Usage', {
            'fields': ('tokens_used', 'api_cost')
        }),
        ('Error Information', {
            'fields': ('error_occurred', 'error_type', 'retry_count')
        }),
        ('Configuration', {
            'fields': ('parameters',),
            'classes': ('collapse',)
        }),
    )
    
    def processing_rate_display(self, obj):
        """Display processing rate"""
        rate = obj.processing_rate
        return f"{rate:.1f} chars/sec" if rate else '-'
    processing_rate_display.short_description = 'Processing Rate'


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    """Admin for SystemAlert model"""
    
    list_display = [
        'title', 'severity_display', 'alert_type', 'component',
        'is_active', 'acknowledged', 'resolved', 'first_occurred',
        'occurrence_count'
    ]
    list_filter = [
        'severity', 'alert_type', 'is_active', 'acknowledged', 'resolved',
        'first_occurred', 'component'
    ]
    search_fields = ['title', 'description', 'component']
    readonly_fields = [
        'first_occurred', 'last_occurred', 'occurrence_count',
        'created_at', 'updated_at'
    ]
    date_hierarchy = 'first_occurred'
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('alert_type', 'severity', 'title', 'description')
        }),
        ('Context', {
            'fields': ('component', 'metric_threshold', 'current_value')
        }),
        ('Status', {
            'fields': ('is_active', 'acknowledged', 'acknowledged_by', 'acknowledged_at')
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
        ('Occurrence Tracking', {
            'fields': ('first_occurred', 'last_occurred', 'occurrence_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['acknowledge_alerts', 'resolve_alerts']
    
    def severity_display(self, obj):
        """Display severity with color coding"""
        colors = {
            'info': 'blue',
            'warning': 'orange',
            'error': 'red',
            'critical': 'darkred'
        }
        color = colors.get(obj.severity, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.severity.upper()
        )
    severity_display.short_description = 'Severity'
    
    def acknowledge_alerts(self, request, queryset):
        """Bulk acknowledge alerts"""
        count = 0
        for alert in queryset.filter(acknowledged=False):
            alert.acknowledge(request.user.username)
            count += 1
        
        self.message_user(
            request,
            f"Successfully acknowledged {count} alerts."
        )
    acknowledge_alerts.short_description = "Acknowledge selected alerts"
    
    def resolve_alerts(self, request, queryset):
        """Bulk resolve alerts"""
        count = 0
        for alert in queryset.filter(resolved=False):
            alert.resolve(request.user.username, "Bulk resolved from admin")
            count += 1
        
        self.message_user(
            request,
            f"Successfully resolved {count} alerts."
        )
    resolve_alerts.short_description = "Resolve selected alerts"


@admin.register(PerformanceThreshold)
class PerformanceThresholdAdmin(admin.ModelAdmin):
    """Admin for PerformanceThreshold model"""
    
    list_display = [
        'metric_type', 'metric_name', 'warning_threshold',
        'error_threshold', 'critical_threshold', 'comparison_operator',
        'is_active', 'created_at'
    ]
    list_filter = ['metric_type', 'is_active', 'comparison_operator', 'created_at']
    search_fields = ['metric_type', 'metric_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_type', 'metric_name')
        }),
        ('Thresholds', {
            'fields': ('warning_threshold', 'error_threshold', 'critical_threshold')
        }),
        ('Configuration', {
            'fields': ('comparison_operator', 'time_window', 'min_occurrences')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ConcurrentCallMetrics)
class ConcurrentCallMetricsAdmin(admin.ModelAdmin):
    """Admin for ConcurrentCallMetrics model"""
    
    list_display = [
        'timestamp', 'active_calls', 'max_concurrent_calls',
        'successful_connections', 'failed_connections',
        'avg_connection_time', 'system_load'
    ]
    list_filter = ['timestamp']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Call Metrics', {
            'fields': (
                'timestamp', 'active_calls', 'max_concurrent_calls',
                'successful_connections', 'failed_connections'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'avg_connection_time', 'avg_processing_time',
                'avg_memory_usage', 'avg_cpu_usage'
            )
        }),
        ('System Health', {
            'fields': ('system_load', 'available_memory', 'disk_usage')
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual addition of concurrent call metrics"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make concurrent call metrics read-only"""
        return False


# Custom admin site configuration
admin.site.site_header = "NIA Performance Monitoring"
admin.site.site_title = "Performance Admin"
admin.site.index_title = "Performance Monitoring Dashboard"