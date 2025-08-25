"""
Django Admin configuration for Analytics
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db import models
from .models import PerformanceMetric, UserEngagementMetric, DataQualityMetric, SystemHealthMetric, Report


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    """Admin interface for Performance Metrics"""
    
    list_display = [
        'metric_name', 'metric_type', 'value', 'target_status',
        'aggregation_period', 'period_start', 'user', 'department'
    ]
    list_filter = [
        'metric_type', 'aggregation_period', 'department', 'period_start'
    ]
    search_fields = [
        'metric_name', 'user__username', 'department'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'period_start'
    ordering = ['-period_start']
    
    fieldsets = (
        ('Metric Information', {
            'fields': (
                'id', 'metric_type', 'metric_name', 'aggregation_period'
            )
        }),
        ('Time Period', {
            'fields': (
                'period_start', 'period_end'
            )
        }),
        ('Values', {
            'fields': (
                'value', 'count', 'target_value'
            )
        }),
        ('Context', {
            'fields': (
                'user', 'department'
            )
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def target_status(self, obj):
        """Display target achievement status"""
        if obj.target_value is None:
            return format_html('<span style="color: gray;">No Target</span>')
        
        if obj.is_meeting_target:
            return format_html('<span style="color: green;">✓ Meeting Target</span>')
        else:
            percentage = (obj.value / obj.target_value) * 100 if obj.target_value > 0 else 0
            return format_html(
                '<span style="color: red;">❌ Below Target ({:.1f}%)</span>',
                percentage
            )
    target_status.short_description = 'Target Status'
    
    actions = ['export_metrics', 'set_target_values']
    
    def export_metrics(self, request, queryset):
        """Admin action to export metrics"""
        # This would implement CSV export functionality
        count = queryset.count()
        self.message_user(request, f'Exported {count} metrics.')
    export_metrics.short_description = 'Export selected metrics'
    
    def set_target_values(self, request, queryset):
        """Admin action to set target values"""
        # This would open a form to set target values
        count = queryset.count()
        self.message_user(request, f'Ready to set targets for {count} metrics.')
    set_target_values.short_description = 'Set target values'


@admin.register(UserEngagementMetric)
class UserEngagementMetricAdmin(admin.ModelAdmin):
    """Admin interface for User Engagement Metrics"""
    
    list_display = [
        'user', 'engagement_type', 'duration_display', 'entity_info',
        'session_id', 'created_at'
    ]
    list_filter = [
        'engagement_type', 'entity_type', 'created_at'
    ]
    search_fields = [
        'user__username', 'session_id', 'entity_id'
    ]
    readonly_fields = [
        'id', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Engagement Details', {
            'fields': (
                'id', 'user', 'engagement_type', 'session_id', 'duration_seconds'
            )
        }),
        ('Context', {
            'fields': (
                'entity_type', 'entity_id'
            )
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def duration_display(self, obj):
        """Display duration in human-readable format"""
        if not obj.duration_seconds:
            return '-'
        
        if obj.duration_seconds < 60:
            return f"{obj.duration_seconds}s"
        elif obj.duration_seconds < 3600:
            return f"{obj.duration_seconds // 60}m {obj.duration_seconds % 60}s"
        else:
            hours = obj.duration_seconds // 3600
            minutes = (obj.duration_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    duration_display.short_description = 'Duration'
    
    def entity_info(self, obj):
        """Display entity information"""
        if obj.entity_type and obj.entity_id:
            return f"{obj.entity_type}: {str(obj.entity_id)[:8]}..."
        return '-'
    entity_info.short_description = 'Entity'
    
    def has_add_permission(self, request):
        """Disable adding engagement metrics through admin"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make engagement metrics read-only"""
        return False


@admin.register(DataQualityMetric)
class DataQualityMetricAdmin(admin.ModelAdmin):
    """Admin interface for Data Quality Metrics"""
    
    list_display = [
        'quality_type', 'entity_type', 'field_name', 'score_display',
        'confidence', 'measurement_date', 'user'
    ]
    list_filter = [
        'quality_type', 'entity_type', 'measurement_date'
    ]
    search_fields = [
        'entity_id', 'field_name', 'user__username'
    ]
    readonly_fields = [
        'id', 'created_at'
    ]
    date_hierarchy = 'measurement_date'
    ordering = ['-measurement_date']
    
    fieldsets = (
        ('Quality Metric', {
            'fields': (
                'id', 'quality_type', 'entity_type', 'field_name'
            )
        }),
        ('Scores', {
            'fields': (
                'score', 'confidence'
            )
        }),
        ('Context', {
            'fields': (
                'entity_id', 'user', 'measurement_date'
            )
        }),
        ('Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def score_display(self, obj):
        """Display score with color coding"""
        if obj.score >= 0.9:
            color = 'green'
        elif obj.score >= 0.7:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1%}</span>',
            color, obj.score
        )
    score_display.short_description = 'Quality Score'
    
    actions = ['identify_low_quality', 'export_quality_report']
    
    def identify_low_quality(self, request, queryset):
        """Admin action to identify low quality data"""
        low_quality = queryset.filter(score__lt=0.7)
        count = low_quality.count()
        self.message_user(request, f'Found {count} low quality data points.')
    identify_low_quality.short_description = 'Identify low quality data'
    
    def export_quality_report(self, request, queryset):
        """Admin action to export quality report"""
        count = queryset.count()
        self.message_user(request, f'Exported quality report for {count} metrics.')
    export_quality_report.short_description = 'Export quality report'


@admin.register(SystemHealthMetric)
class SystemHealthMetricAdmin(admin.ModelAdmin):
    """Admin interface for System Health Metrics"""
    
    list_display = [
        'component', 'health_type', 'value_display', 'unit',
        'status_display', 'measured_at'
    ]
    list_filter = [
        'health_type', 'component', 'status', 'measured_at'
    ]
    search_fields = [
        'component', 'health_type'
    ]
    readonly_fields = [
        'id', 'created_at'
    ]
    date_hierarchy = 'measured_at'
    ordering = ['-measured_at']
    
    fieldsets = (
        ('Health Metric', {
            'fields': (
                'id', 'health_type', 'component'
            )
        }),
        ('Values', {
            'fields': (
                'value', 'unit', 'status'
            )
        }),
        ('Thresholds', {
            'fields': (
                'warning_threshold', 'critical_threshold'
            )
        }),
        ('Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('measured_at', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def value_display(self, obj):
        """Display value with appropriate formatting"""
        if obj.unit == '%':
            return f"{obj.value:.1f}%"
        elif obj.unit in ['ms', 'MB', 'GB']:
            return f"{obj.value:.1f} {obj.unit}"
        else:
            return f"{obj.value}"
    value_display.short_description = 'Value'
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'healthy': 'green',
            'warning': 'orange',
            'critical': 'red',
            'down': 'darkred'
        }
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.upper()
        )
    status_display.short_description = 'Status'
    
    actions = ['update_status', 'set_thresholds']
    
    def update_status(self, request, queryset):
        """Admin action to update status based on thresholds"""
        count = 0
        for metric in queryset:
            metric.update_status()
            count += 1
        
        self.message_user(request, f'Updated status for {count} metrics.')
    update_status.short_description = 'Update status based on thresholds'
    
    def set_thresholds(self, request, queryset):
        """Admin action to set thresholds"""
        count = queryset.count()
        self.message_user(request, f'Ready to set thresholds for {count} metrics.')
    set_thresholds.short_description = 'Set warning/critical thresholds'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin interface for Reports"""
    
    list_display = [
        'title', 'report_type', 'status_display', 'period_display',
        'generated_at', 'generation_time_display', 'created_by'
    ]
    list_filter = [
        'report_type', 'status', 'is_public', 'created_at'
    ]
    search_fields = [
        'title', 'description', 'created_by__username'
    ]
    readonly_fields = [
        'id', 'generated_at', 'generation_time_seconds', 'created_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Report Information', {
            'fields': (
                'id', 'report_type', 'title', 'description'
            )
        }),
        ('Time Period', {
            'fields': (
                'period_start', 'period_end'
            )
        }),
        ('Generation Status', {
            'fields': (
                'status', 'generated_at', 'generation_time_seconds'
            )
        }),
        ('Report Data', {
            'fields': (
                'report_data', 'summary'
            ),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': (
                'created_by', 'is_public'
            )
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            'generating': 'orange',
            'completed': 'green',
            'failed': 'red'
        }
        
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status.title()
        )
    status_display.short_description = 'Status'
    
    def period_display(self, obj):
        """Display period in readable format"""
        return f"{obj.period_start.date()} to {obj.period_end.date()}"
    period_display.short_description = 'Period'
    
    def generation_time_display(self, obj):
        """Display generation time in readable format"""
        if not obj.generation_time_seconds:
            return '-'
        
        if obj.generation_time_seconds < 60:
            return f"{obj.generation_time_seconds}s"
        else:
            minutes = obj.generation_time_seconds // 60
            seconds = obj.generation_time_seconds % 60
            return f"{minutes}m {seconds}s"
    generation_time_display.short_description = 'Generation Time'
    
    def save_model(self, request, obj, form, change):
        """Set created_by when saving"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['regenerate_reports', 'make_public', 'make_private']
    
    def regenerate_reports(self, request, queryset):
        """Admin action to regenerate reports"""
        count = queryset.filter(status='failed').update(status='generating')
        self.message_user(request, f'Marked {count} reports for regeneration.')
    regenerate_reports.short_description = 'Regenerate failed reports'
    
    def make_public(self, request, queryset):
        """Admin action to make reports public"""
        count = queryset.update(is_public=True)
        self.message_user(request, f'Made {count} reports public.')
    make_public.short_description = 'Make reports public'
    
    def make_private(self, request, queryset):
        """Admin action to make reports private"""
        count = queryset.update(is_public=False)
        self.message_user(request, f'Made {count} reports private.')
    make_private.short_description = 'Make reports private'


# Custom admin site configuration
admin.site.site_header = 'NIA Meeting Intelligence - Analytics Administration'
admin.site.site_title = 'Analytics Admin'
admin.site.index_title = 'Analytics & Reporting Management'