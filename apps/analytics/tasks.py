"""
Celery tasks for analytics processing
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.cache import cache

from .services import AnalyticsService, ReportingService, RealTimeAnalyticsCollector
from .models import PerformanceMetric, Report, SystemHealthMetric
from .cache import AnalyticsCache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def collect_performance_metrics(self, period='daily', date_str=None, user_id=None):
    """
    Celery task to collect performance metrics
    """
    try:
        # Parse date
        if date_str:
            target_date = datetime.fromisoformat(date_str)
        else:
            target_date = timezone.now() - timedelta(days=1)
        
        # Calculate date range based on period
        if period == 'hourly':
            start_date = target_date.replace(minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(hours=1)
        elif period == 'daily':
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == 'weekly':
            days_since_monday = target_date.weekday()
            start_date = target_date - timedelta(days=days_since_monday)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=7)
        else:
            raise ValueError(f"Unsupported period: {period}")
        
        analytics_service = AnalyticsService()
        metrics_collected = 0
        
        # Get user if specified
        user = None
        if user_id:
            user = User.objects.get(id=user_id)
        
        # Collect debriefing completion metrics
        if not user:
            # Collect for all active users
            users = User.objects.filter(is_active=True)
        else:
            users = [user]
        
        for target_user in users:
            # Check if metric already exists
            existing = PerformanceMetric.objects.filter(
                metric_type='debriefing_completion',
                aggregation_period=period,
                period_start=start_date,
                user=target_user
            ).exists()
            
            if not existing:
                debriefing_data = analytics_service.calculate_debriefing_completion_rate(
                    start_date, end_date, target_user
                )
                
                analytics_service.store_performance_metric(
                    metric_type='debriefing_completion',
                    value=debriefing_data['completion_rate'],
                    aggregation_period=period,
                    period_start=start_date,
                    period_end=end_date,
                    user=target_user,
                    metadata=debriefing_data
                )
                metrics_collected += 1
        
        # Collect system-wide metrics
        system_metrics = [
            ('data_extraction_accuracy', 'calculate_data_extraction_accuracy'),
            ('meeting_detection_accuracy', 'calculate_meeting_detection_accuracy'),
            ('participant_matching_accuracy', 'calculate_participant_matching_accuracy'),
            ('crm_sync_success', 'calculate_crm_sync_success_rate'),
        ]
        
        for metric_type, method_name in system_metrics:
            existing = PerformanceMetric.objects.filter(
                metric_type=metric_type,
                aggregation_period=period,
                period_start=start_date,
                user__isnull=True
            ).exists()
            
            if not existing:
                method = getattr(analytics_service, method_name)
                data = method(start_date, end_date)
                
                # Extract the main value based on metric type
                if metric_type == 'data_extraction_accuracy':
                    value = data['extraction_accuracy']
                elif metric_type == 'meeting_detection_accuracy':
                    value = data['detection_accuracy']
                elif metric_type == 'participant_matching_accuracy':
                    value = data['accuracy_rate']
                elif metric_type == 'crm_sync_success':
                    value = data['success_rate']
                else:
                    value = 0
                
                analytics_service.store_performance_metric(
                    metric_type=metric_type,
                    value=value,
                    aggregation_period=period,
                    period_start=start_date,
                    period_end=end_date,
                    metadata=data
                )
                metrics_collected += 1
        
        # Invalidate related cache entries
        AnalyticsCache.clear_date_range_cache(start_date, end_date)
        
        logger.info(f"Collected {metrics_collected} performance metrics for {period} period")
        return {
            'status': 'success',
            'metrics_collected': metrics_collected,
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Performance metrics collection failed: {str(e)}")
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        raise


@shared_task(bind=True, max_retries=3)
def generate_scheduled_report(self, report_type, date_str=None, user_id=None):
    """
    Celery task to generate scheduled reports
    """
    try:
        # Parse date
        if date_str:
            target_date = datetime.fromisoformat(date_str)
        else:
            target_date = timezone.now()
        
        # Get user if specified
        user = None
        if user_id:
            user = User.objects.get(id=user_id)
        
        reporting_service = ReportingService()
        
        # Generate appropriate report
        if report_type == 'daily_summary':
            report = reporting_service.generate_daily_summary_report(target_date, user)
        elif report_type == 'weekly_performance':
            report = reporting_service.generate_weekly_performance_report(target_date, user)
        elif report_type == 'user_activity':
            if not user:
                raise ValueError("User is required for user activity reports")
            end_date = target_date + timedelta(days=30)
            report = reporting_service.generate_user_activity_report(
                target_date, end_date, user
            )
        else:
            raise ValueError(f"Unsupported report type: {report_type}")
        
        logger.info(f"Generated {report_type} report: {report.title}")
        return {
            'status': 'success',
            'report_id': str(report.id),
            'report_type': report_type,
            'report_title': report.title,
            'report_status': report.status
        }
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        raise


@shared_task
def collect_system_health_metrics():
    """
    Celery task to collect system health metrics
    """
    try:
        import psutil
        import time
        from django.db import connection
        
        metrics_collected = 0
        
        # Database performance check
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        RealTimeAnalyticsCollector.track_system_health(
            health_type='database_performance',
            component='postgresql',
            value=db_response_time,
            unit='ms',
            warning_threshold=100.0,
            critical_threshold=300.0
        )
        metrics_collected += 1
        
        # Memory usage
        memory = psutil.virtual_memory()
        RealTimeAnalyticsCollector.track_system_health(
            health_type='memory_usage',
            component='web_server',
            value=memory.percent,
            unit='%',
            warning_threshold=80.0,
            critical_threshold=95.0
        )
        metrics_collected += 1
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        RealTimeAnalyticsCollector.track_system_health(
            health_type='cpu_usage',
            component='web_server',
            value=cpu_percent,
            unit='%',
            warning_threshold=80.0,
            critical_threshold=95.0
        )
        metrics_collected += 1
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        RealTimeAnalyticsCollector.track_system_health(
            health_type='disk_usage',
            component='file_system',
            value=disk_percent,
            unit='%',
            warning_threshold=80.0,
            critical_threshold=95.0
        )
        metrics_collected += 1
        
        logger.info(f"Collected {metrics_collected} system health metrics")
        return {
            'status': 'success',
            'metrics_collected': metrics_collected
        }
        
    except Exception as e:
        logger.error(f"System health metrics collection failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def cleanup_old_analytics_data(days_to_keep=90):
    """
    Celery task to cleanup old analytics data
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Cleanup old performance metrics
        old_metrics = PerformanceMetric.objects.filter(created_at__lt=cutoff_date)
        metrics_deleted = old_metrics.count()
        old_metrics.delete()
        
        # Cleanup old system health metrics
        old_health = SystemHealthMetric.objects.filter(created_at__lt=cutoff_date)
        health_deleted = old_health.count()
        old_health.delete()
        
        # Cleanup old reports (keep completed reports longer)
        old_reports = Report.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['failed', 'generating']
        )
        reports_deleted = old_reports.count()
        old_reports.delete()
        
        logger.info(
            f"Cleaned up old analytics data: "
            f"{metrics_deleted} metrics, {health_deleted} health metrics, "
            f"{reports_deleted} reports"
        )
        
        return {
            'status': 'success',
            'metrics_deleted': metrics_deleted,
            'health_deleted': health_deleted,
            'reports_deleted': reports_deleted
        }
        
    except Exception as e:
        logger.error(f"Analytics data cleanup failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def invalidate_analytics_cache(cache_type=None, user_id=None):
    """
    Celery task to invalidate analytics cache
    """
    try:
        if user_id:
            # Clear cache for specific user
            cleared = AnalyticsCache.clear_user_cache(user_id)
            logger.info(f"Cleared {cleared} cache entries for user {user_id}")
        elif cache_type:
            # Clear cache for specific type
            pattern = f"analytics:{cache_type}:*"
            cleared = AnalyticsCache.invalidate_pattern(pattern)
            logger.info(f"Cleared {cleared} cache entries for type {cache_type}")
        else:
            # Clear all analytics cache
            pattern = "analytics:*"
            cleared = AnalyticsCache.invalidate_pattern(pattern)
            logger.info(f"Cleared {cleared} analytics cache entries")
        
        return {
            'status': 'success',
            'entries_cleared': cleared
        }
        
    except Exception as e:
        logger.error(f"Cache invalidation failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def aggregate_real_time_metrics():
    """
    Celery task to aggregate real-time metrics into performance metrics
    """
    try:
        from .cache import realtime_cache
        from apps.debriefings.models import DebriefingSession
        from apps.meetings.models import Meeting
        
        now = timezone.now()
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        
        # Aggregate debriefing completion for the current hour
        completed_debriefings = DebriefingSession.objects.filter(
            completed_at__gte=hour_start,
            completed_at__lt=hour_start + timedelta(hours=1),
            status='completed'
        ).count()
        
        total_meetings = Meeting.objects.filter(
            end_time__gte=hour_start,
            end_time__lt=hour_start + timedelta(hours=1),
            is_sales_meeting=True
        ).count()
        
        if total_meetings > 0:
            completion_rate = (completed_debriefings / total_meetings) * 100
            
            # Store as real-time metric
            realtime_cache.set_real_time_metric(
                'hourly_completion_rate',
                completion_rate
            )
        
        # Aggregate AI response times
        # This would typically come from AI service metrics
        # For now, we'll simulate it
        import random
        avg_response_time = random.uniform(100, 300)  # 100-300ms
        realtime_cache.set_real_time_metric(
            'ai_response_time',
            avg_response_time
        )
        
        logger.info("Aggregated real-time metrics")
        return {
            'status': 'success',
            'completion_rate': completion_rate if total_meetings > 0 else 0,
            'avg_response_time': avg_response_time
        }
        
    except Exception as e:
        logger.error(f"Real-time metrics aggregation failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task
def send_analytics_alerts():
    """
    Celery task to send analytics alerts based on thresholds
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        alerts_sent = 0
        
        # Check for critical system health metrics
        critical_metrics = SystemHealthMetric.objects.filter(
            status='critical',
            measured_at__gte=timezone.now() - timedelta(hours=1)
        ).distinct('component', 'health_type')
        
        if critical_metrics.exists():
            # Send alert email
            subject = "Critical System Health Alert - Meeting Intelligence"
            message = "The following system components are in critical state:\n\n"
            
            for metric in critical_metrics:
                message += f"- {metric.component} {metric.health_type}: {metric.value} {metric.unit or ''}\n"
            
            message += f"\nPlease check the system health dashboard for more details."
            
            # Send to administrators
            admin_emails = User.objects.filter(
                is_superuser=True,
                is_active=True
            ).values_list('email', flat=True)
            
            if admin_emails and hasattr(settings, 'DEFAULT_FROM_EMAIL'):
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(admin_emails),
                    fail_silently=True
                )
                alerts_sent += 1
        
        # Check for low performance metrics
        recent_metrics = PerformanceMetric.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24),
            metric_type='debriefing_completion'
        ).order_by('-created_at')[:10]
        
        low_performance_users = []
        for metric in recent_metrics:
            if metric.value < 50.0:  # Less than 50% completion rate
                low_performance_users.append(metric.user)
        
        if low_performance_users:
            # Send performance alert
            subject = "Low Debriefing Completion Rate Alert"
            message = f"The following users have low debriefing completion rates:\n\n"
            
            for user in low_performance_users:
                message += f"- {user.get_full_name() or user.username}\n"
            
            # Send to sales managers
            manager_emails = User.objects.filter(
                groups__name='sales_manager',
                is_active=True
            ).values_list('email', flat=True)
            
            if manager_emails and hasattr(settings, 'DEFAULT_FROM_EMAIL'):
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=list(manager_emails),
                    fail_silently=True
                )
                alerts_sent += 1
        
        logger.info(f"Sent {alerts_sent} analytics alerts")
        return {
            'status': 'success',
            'alerts_sent': alerts_sent
        }
        
    except Exception as e:
        logger.error(f"Analytics alerts failed: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }