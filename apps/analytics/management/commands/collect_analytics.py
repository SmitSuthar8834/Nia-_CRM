"""
Management command for collecting and aggregating analytics data
"""
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.contrib.auth.models import User

from apps.analytics.services import AnalyticsService, RealTimeAnalyticsCollector
from apps.analytics.models import PerformanceMetric, SystemHealthMetric
from apps.meetings.models import Meeting, MeetingParticipant
from apps.debriefings.models import DebriefingSession
from apps.crm_sync.models import SyncLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Collect and aggregate analytics data for the meeting intelligence system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            choices=['hourly', 'daily', 'weekly', 'monthly'],
            default='daily',
            help='Aggregation period for metrics collection'
        )
        
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to collect metrics for (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--days-back',
            type=int,
            default=1,
            help='Number of days back to collect metrics for'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation of existing metrics'
        )
        
        parser.add_argument(
            '--system-health',
            action='store_true',
            help='Collect system health metrics'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            self.stdout.write(
                self.style.SUCCESS('Starting analytics data collection...')
            )
            
            # Determine date range
            if options['date']:
                target_date = datetime.strptime(options['date'], '%Y-%m-%d')
                target_date = timezone.make_aware(target_date)
            else:
                target_date = timezone.now() - timedelta(days=options['days_back'])
            
            period = options['period']
            force = options['force']
            
            # Calculate date range based on period
            if period == 'hourly':
                start_date = target_date.replace(minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(hours=1)
            elif period == 'daily':
                start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif period == 'weekly':
                # Start from Monday
                days_since_monday = target_date.weekday()
                start_date = target_date - timedelta(days=days_since_monday)
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=7)
            elif period == 'monthly':
                start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if start_date.month == 12:
                    end_date = start_date.replace(year=start_date.year + 1, month=1)
                else:
                    end_date = start_date.replace(month=start_date.month + 1)
            
            self.stdout.write(
                f'Collecting {period} metrics for period: {start_date} to {end_date}'
            )
            
            analytics_service = AnalyticsService()
            
            # Collect performance metrics
            self.collect_performance_metrics(
                analytics_service, start_date, end_date, period, force
            )
            
            # Collect system health metrics if requested
            if options['system_health']:
                self.collect_system_health_metrics()
            
            # Generate summary
            self.generate_collection_summary(start_date, end_date, period)
            
            self.stdout.write(
                self.style.SUCCESS('Analytics data collection completed successfully!')
            )
            
        except Exception as e:
            logger.error(f"Analytics collection error: {str(e)}")
            raise CommandError(f'Analytics collection failed: {str(e)}')
    
    def collect_performance_metrics(self, analytics_service, start_date, end_date, period, force):
        """Collect performance metrics for the specified period"""
        self.stdout.write('Collecting performance metrics...')
        
        # Get all users for user-specific metrics
        users = User.objects.filter(is_active=True)
        
        metrics_collected = 0
        
        # Collect debriefing completion rates
        for user in users:
            if self.should_collect_metric('debriefing_completion', period, start_date, user, force):
                debriefing_data = analytics_service.calculate_debriefing_completion_rate(
                    start_date, end_date, user
                )
                
                analytics_service.store_performance_metric(
                    metric_type='debriefing_completion',
                    value=debriefing_data['completion_rate'],
                    aggregation_period=period,
                    period_start=start_date,
                    period_end=end_date,
                    user=user,
                    metadata={
                        'total_meetings': debriefing_data['total_meetings'],
                        'completed_debriefings': debriefing_data['completed_debriefings']
                    }
                )
                metrics_collected += 1
        
        # Collect system-wide metrics (no user filter)
        if self.should_collect_metric('data_extraction_accuracy', period, start_date, None, force):
            extraction_data = analytics_service.calculate_data_extraction_accuracy(
                start_date, end_date
            )
            
            analytics_service.store_performance_metric(
                metric_type='data_extraction_accuracy',
                value=extraction_data['extraction_accuracy'],
                aggregation_period=period,
                period_start=start_date,
                period_end=end_date,
                metadata=extraction_data
            )
            metrics_collected += 1
        
        if self.should_collect_metric('meeting_detection_accuracy', period, start_date, None, force):
            meeting_data = analytics_service.calculate_meeting_detection_accuracy(
                start_date, end_date
            )
            
            analytics_service.store_performance_metric(
                metric_type='meeting_detection_accuracy',
                value=meeting_data['detection_accuracy'],
                aggregation_period=period,
                period_start=start_date,
                period_end=end_date,
                metadata=meeting_data
            )
            metrics_collected += 1
        
        if self.should_collect_metric('participant_matching_accuracy', period, start_date, None, force):
            participant_data = analytics_service.calculate_participant_matching_accuracy(
                start_date, end_date
            )
            
            analytics_service.store_performance_metric(
                metric_type='participant_matching_accuracy',
                value=participant_data['accuracy_rate'],
                aggregation_period=period,
                period_start=start_date,
                period_end=end_date,
                metadata=participant_data
            )
            metrics_collected += 1
        
        if self.should_collect_metric('crm_sync_success', period, start_date, None, force):
            crm_data = analytics_service.calculate_crm_sync_success_rate(
                start_date, end_date
            )
            
            analytics_service.store_performance_metric(
                metric_type='crm_sync_success',
                value=crm_data['success_rate'],
                aggregation_period=period,
                period_start=start_date,
                period_end=end_date,
                metadata=crm_data
            )
            metrics_collected += 1
        
        # Collect user engagement metrics
        for user in users:
            if self.should_collect_metric('user_engagement', period, start_date, user, force):
                engagement_data = analytics_service.calculate_user_engagement_metrics(
                    start_date, end_date, user
                )
                
                analytics_service.store_performance_metric(
                    metric_type='user_engagement',
                    value=engagement_data['total_engagements'],
                    aggregation_period=period,
                    period_start=start_date,
                    period_end=end_date,
                    user=user,
                    metadata=engagement_data
                )
                metrics_collected += 1
        
        self.stdout.write(f'Collected {metrics_collected} performance metrics')
    
    def should_collect_metric(self, metric_type, period, start_date, user, force):
        """Check if metric should be collected"""
        if force:
            return True
        
        # Check if metric already exists
        existing = PerformanceMetric.objects.filter(
            metric_type=metric_type,
            aggregation_period=period,
            period_start=start_date,
            user=user
        ).exists()
        
        return not existing
    
    def collect_system_health_metrics(self):
        """Collect current system health metrics"""
        self.stdout.write('Collecting system health metrics...')
        
        # Simulate system health checks
        # In a real implementation, these would check actual system components
        
        # API response time simulation
        import random
        api_response_time = random.uniform(50, 200)  # 50-200ms
        RealTimeAnalyticsCollector.track_system_health(
            health_type='api_response_time',
            component='gemini_api',
            value=api_response_time,
            unit='ms',
            warning_threshold=200.0,
            critical_threshold=500.0
        )
        
        # Database performance simulation
        db_response_time = random.uniform(10, 50)  # 10-50ms
        RealTimeAnalyticsCollector.track_system_health(
            health_type='database_performance',
            component='postgresql',
            value=db_response_time,
            unit='ms',
            warning_threshold=100.0,
            critical_threshold=300.0
        )
        
        # Memory usage simulation
        memory_usage = random.uniform(40, 80)  # 40-80%
        RealTimeAnalyticsCollector.track_system_health(
            health_type='memory_usage',
            component='web_server',
            value=memory_usage,
            unit='%',
            warning_threshold=80.0,
            critical_threshold=95.0
        )
        
        self.stdout.write('System health metrics collected')
    
    def generate_collection_summary(self, start_date, end_date, period):
        """Generate a summary of collected metrics"""
        self.stdout.write('\n=== Collection Summary ===')
        
        # Count metrics collected in this period
        metrics_count = PerformanceMetric.objects.filter(
            period_start=start_date,
            period_end=end_date,
            aggregation_period=period
        ).count()
        
        health_metrics_count = SystemHealthMetric.objects.filter(
            measured_at__gte=start_date,
            measured_at__lt=end_date
        ).count()
        
        self.stdout.write(f'Period: {start_date.date()} to {end_date.date()} ({period})')
        self.stdout.write(f'Performance metrics collected: {metrics_count}')
        self.stdout.write(f'System health metrics collected: {health_metrics_count}')
        
        # Show breakdown by metric type
        metric_breakdown = PerformanceMetric.objects.filter(
            period_start=start_date,
            period_end=end_date,
            aggregation_period=period
        ).values('metric_type').annotate(count=Count('id')).order_by('-count')
        
        if metric_breakdown:
            self.stdout.write('\nMetric breakdown:')
            for item in metric_breakdown:
                self.stdout.write(f'  {item["metric_type"]}: {item["count"]}')
        
        self.stdout.write('=========================\n')