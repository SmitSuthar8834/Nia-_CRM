"""
Admin dashboard views for system monitoring
"""
from django.contrib import admin
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from datetime import timedelta
from .models import SystemHealthMetric, PerformanceMetric, UserEngagementMetric, DataQualityMetric


class SystemDashboardAdmin(admin.ModelAdmin):
    """Custom admin for system dashboard"""
    
    def get_urls(self):
        """Add custom dashboard URLs"""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.dashboard_view), name='system_dashboard'),
            path('health-monitor/', self.admin_site.admin_view(self.health_monitor_view), name='health_monitor'),
            path('performance-metrics/', self.admin_site.admin_view(self.performance_metrics_view), name='performance_metrics'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Main system dashboard view"""
        context = self.get_dashboard_context()
        return render(request, 'admin/analytics/dashboard.html', context)
    
    def health_monitor_view(self, request):
        """System health monitoring view"""
        context = self.get_health_context()
        return render(request, 'admin/analytics/health_monitor.html', context)
    
    def performance_metrics_view(self, request):
        """Performance metrics view"""
        context = self.get_performance_context()
        return render(request, 'admin/analytics/performance_metrics.html', context)
    
    def get_dashboard_context(self):
        """Get context data for main dashboard"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        
        from django.db import models
        
        # System health summary
        latest_health_metrics = SystemHealthMetric.objects.filter(
            measured_at__gte=last_24h
        ).values('component').annotate(
            latest_status=models.Max('status'),
            avg_response_time=models.Avg('value')
        )
        
        # Performance summary
        performance_summary = PerformanceMetric.objects.filter(
            period_start__gte=last_7d
        ).aggregate(
            avg_meeting_completion=models.Avg('value', filter=models.Q(metric_name='meeting_completion_rate')),
            avg_debriefing_completion=models.Avg('value', filter=models.Q(metric_name='debriefing_completion_rate')),
            total_meetings=models.Sum('count', filter=models.Q(metric_name='total_meetings')),
            total_debriefings=models.Sum('count', filter=models.Q(metric_name='total_debriefings'))
        )
        
        # User engagement summary
        user_engagement = UserEngagementMetric.objects.filter(
            created_at__gte=last_7d
        ).values('engagement_type').annotate(
            total_sessions=models.Count('id'),
            avg_duration=models.Avg('duration_seconds')
        )
        
        # Data quality summary
        data_quality = DataQualityMetric.objects.filter(
            measurement_date__gte=last_7d
        ).aggregate(
            avg_quality_score=models.Avg('score'),
            low_quality_count=models.Count('id', filter=models.Q(score__lt=0.7))
        )
        
        # Recent alerts (simulated - would come from actual alerting system)
        alerts = self.get_recent_alerts()
        
        return {
            'title': 'System Dashboard',
            'health_metrics': latest_health_metrics,
            'performance_summary': performance_summary,
            'user_engagement': user_engagement,
            'data_quality': data_quality,
            'alerts': alerts,
            'last_updated': now,
        }
    
    def get_health_context(self):
        """Get context data for health monitoring"""
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        # Component health status
        component_health = {}
        components = ['database', 'cache', 'ai', 'crm', 'calendar']
        
        for component in components:
            latest_metric = SystemHealthMetric.objects.filter(
                component=component,
                measured_at__gte=last_24h
            ).order_by('-measured_at').first()
            
            if latest_metric:
                component_health[component] = {
                    'status': latest_metric.status,
                    'response_time': latest_metric.value,
                    'last_check': latest_metric.measured_at,
                    'details': latest_metric.details
                }
            else:
                component_health[component] = {
                    'status': 'unknown',
                    'response_time': None,
                    'last_check': None,
                    'details': 'No recent health checks'
                }
        
        # Health trends (last 24 hours)
        health_trends = SystemHealthMetric.objects.filter(
            measured_at__gte=last_24h
        ).values('component', 'measured_at', 'status', 'value').order_by('measured_at')
        
        return {
            'title': 'System Health Monitor',
            'component_health': component_health,
            'health_trends': health_trends,
            'last_updated': now,
        }
    
    def get_performance_context(self):
        """Get context data for performance metrics"""
        now = timezone.now()
        last_30d = now - timedelta(days=30)
        
        # Performance metrics by type
        performance_metrics = PerformanceMetric.objects.filter(
            period_start__gte=last_30d
        ).values('metric_type', 'metric_name').annotate(
            avg_value=models.Avg('value'),
            latest_value=models.Max('value'),
            trend=models.Count('id')
        ).order_by('metric_type', 'metric_name')
        
        # Top performing users/departments
        top_performers = PerformanceMetric.objects.filter(
            period_start__gte=last_30d,
            user__isnull=False
        ).values('user__username', 'department').annotate(
            avg_performance=models.Avg('value')
        ).order_by('-avg_performance')[:10]
        
        # Performance trends
        daily_trends = PerformanceMetric.objects.filter(
            period_start__gte=last_30d,
            aggregation_period='daily'
        ).values('period_start', 'metric_name').annotate(
            avg_value=models.Avg('value')
        ).order_by('period_start')
        
        return {
            'title': 'Performance Metrics',
            'performance_metrics': performance_metrics,
            'top_performers': top_performers,
            'daily_trends': daily_trends,
            'last_updated': now,
        }
    
    def get_recent_alerts(self):
        """Get recent system alerts"""
        # This would integrate with a real alerting system
        # For now, we'll simulate based on health metrics
        alerts = []
        
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        
        # Check for critical health issues
        critical_health = SystemHealthMetric.objects.filter(
            status='critical',
            measured_at__gte=last_24h
        ).order_by('-measured_at')[:5]
        
        for metric in critical_health:
            alerts.append({
                'type': 'critical',
                'component': metric.component,
                'message': f'{metric.component.title()} system critical: {metric.details}',
                'timestamp': metric.measured_at
            })
        
        # Check for slow response times
        slow_responses = SystemHealthMetric.objects.filter(
            value__gt=5000,  # > 5 seconds
            measured_at__gte=last_24h
        ).order_by('-measured_at')[:5]
        
        for metric in slow_responses:
            alerts.append({
                'type': 'warning',
                'component': metric.component,
                'message': f'{metric.component.title()} slow response: {metric.value}ms',
                'timestamp': metric.measured_at
            })
        
        # Check for low data quality
        low_quality = DataQualityMetric.objects.filter(
            score__lt=0.5,
            measurement_date__gte=last_24h
        ).order_by('-measurement_date')[:5]
        
        for metric in low_quality:
            alerts.append({
                'type': 'warning',
                'component': 'data_quality',
                'message': f'Low data quality in {metric.entity_type}: {metric.score:.1%}',
                'timestamp': metric.measurement_date
            })
        
        return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)[:10]


# Register the dashboard
class DashboardAdminSite(admin.AdminSite):
    """Custom admin site with dashboard"""
    site_header = 'NIA Meeting Intelligence - System Dashboard'
    site_title = 'System Dashboard'
    index_title = 'System Monitoring & Analytics'
    
    def get_urls(self):
        """Add dashboard URLs to admin site"""
        urls = super().get_urls()
        dashboard_urls = [
            path('dashboard/', self.admin_view(SystemDashboardAdmin().dashboard_view), name='system_dashboard'),
            path('health/', self.admin_view(SystemDashboardAdmin().health_monitor_view), name='health_monitor'),
            path('performance/', self.admin_view(SystemDashboardAdmin().performance_metrics_view), name='performance_metrics'),
        ]
        return dashboard_urls + urls
    
    def index(self, request, extra_context=None):
        """Custom admin index with dashboard links"""
        extra_context = extra_context or {}
        extra_context.update({
            'dashboard_available': True,
            'dashboard_url': 'admin:system_dashboard',
            'health_monitor_url': 'admin:health_monitor',
            'performance_metrics_url': 'admin:performance_metrics',
        })
        return super().index(request, extra_context)


# Create dashboard admin instance
dashboard_admin = SystemDashboardAdmin(SystemHealthMetric, admin.site)