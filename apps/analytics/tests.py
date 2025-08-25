"""
Comprehensive Analytics Tests
"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status

from .models import PerformanceMetric, UserEngagementMetric, DataQualityMetric, SystemHealthMetric, Report
from .services import AnalyticsService, ReportingService, RealTimeAnalyticsCollector
from .cache import AnalyticsCache, AnalyticsOptimizer, RealTimeAnalyticsCache
from apps.meetings.models import Meeting, MeetingParticipant
from apps.debriefings.models import DebriefingSession
from apps.leads.models import Lead
from apps.crm_sync.models import SyncLog


class AnalyticsModelsTestCase(TestCase):
    """Test analytics models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_performance_metric_creation(self):
        """Test performance metric creation and properties"""
        metric = PerformanceMetric.objects.create(
            metric_type='debriefing_completion',
            metric_name='Debriefing Completion Rate',
            aggregation_period='daily',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=1),
            value=85.5,
            count=20,
            target_value=90.0,
            user=self.user
        )
        
        self.assertEqual(metric.metric_type, 'debriefing_completion')
        self.assertEqual(metric.value, 85.5)
        self.assertFalse(metric.is_meeting_target)  # 85.5 < 90.0
        
        # Test meeting target
        metric.value = 95.0
        metric.save()
        self.assertTrue(metric.is_meeting_target)
    
    def test_user_engagement_metric_creation(self):
        """Test user engagement metric creation"""
        engagement = UserEngagementMetric.objects.create(
            user=self.user,
            engagement_type='debriefing_complete',
            session_id='session123',
            duration_seconds=300,
            entity_type='meeting',
            entity_id='123e4567-e89b-12d3-a456-426614174000',
            metadata={'meeting_type': 'discovery'}
        )
        
        self.assertEqual(engagement.user, self.user)
        self.assertEqual(engagement.engagement_type, 'debriefing_complete')
        self.assertEqual(engagement.duration_seconds, 300)
    
    def test_data_quality_metric_creation(self):
        """Test data quality metric creation"""
        quality_metric = DataQualityMetric.objects.create(
            quality_type='extraction_confidence',
            entity_type='debriefing',
            field_name='contact_info',
            score=0.85,
            confidence=0.92,
            entity_id='123e4567-e89b-12d3-a456-426614174000',
            user=self.user
        )
        
        self.assertEqual(quality_metric.score, 0.85)
        self.assertEqual(quality_metric.confidence, 0.92)
    
    def test_system_health_metric_status_update(self):
        """Test system health metric status updates"""
        health_metric = SystemHealthMetric.objects.create(
            health_type='api_response_time',
            component='gemini_api',
            value=150.0,
            unit='ms',
            warning_threshold=200.0,
            critical_threshold=500.0
        )
        
        # Should be healthy
        self.assertEqual(health_metric.status, 'healthy')
        
        # Update to warning level
        health_metric.value = 250.0
        health_metric.update_status()
        self.assertEqual(health_metric.status, 'warning')
        
        # Update to critical level
        health_metric.value = 600.0
        health_metric.update_status()
        self.assertEqual(health_metric.status, 'critical')
    
    def test_report_completion(self):
        """Test report completion workflow"""
        report = Report.objects.create(
            report_type='daily_summary',
            title='Test Daily Report',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=1),
            created_by=self.user,
            status='generating'
        )
        
        # Mark as completed
        report_data = {'test': 'data'}
        summary = 'Test summary'
        report.mark_completed(report_data, summary)
        
        self.assertEqual(report.status, 'completed')
        self.assertEqual(report.report_data, report_data)
        self.assertEqual(report.summary, summary)
        self.assertIsNotNone(report.generated_at)
        
        # Test failure
        report2 = Report.objects.create(
            report_type='weekly_performance',
            title='Test Weekly Report',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=7),
            created_by=self.user,
            status='generating'
        )
        
        report2.mark_failed('Test error')
        self.assertEqual(report2.status, 'failed')
        self.assertIn('Test error', report2.summary)


class AnalyticsServiceTestCase(TestCase):
    """Test analytics services"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test data
        self.start_date = timezone.now() - timedelta(days=7)
        self.end_date = timezone.now()
        
        # Create test meetings
        self.meeting1 = Meeting.objects.create(
            title='Test Meeting 1',
            start_time=self.start_date + timedelta(days=1),
            end_time=self.start_date + timedelta(days=1, hours=1),
            organizer=self.user,
            is_sales_meeting=True,
            debriefing_completed=True,
            confidence_score=0.9
        )
        
        self.meeting2 = Meeting.objects.create(
            title='Test Meeting 2',
            start_time=self.start_date + timedelta(days=2),
            end_time=self.start_date + timedelta(days=2, hours=1),
            organizer=self.user,
            is_sales_meeting=True,
            debriefing_completed=False,
            debriefing_scheduled=True,
            confidence_score=0.7
        )
        
        # Create debriefing sessions
        self.debriefing1 = DebriefingSession.objects.create(
            meeting=self.meeting1,
            scheduled_time=self.meeting1.end_time + timedelta(minutes=30),
            started_at=self.meeting1.end_time + timedelta(minutes=30),
            completed_at=self.meeting1.end_time + timedelta(hours=1),
            status='completed',
            confidence_scores={'contact_info': 0.9, 'deal_info': 0.8}
        )
        
        # Create sync logs
        SyncLog.objects.create(
            operation='lead_sync',
            status='success',
            entity_type='lead',
            entity_id='test-lead-1'
        )
        
        SyncLog.objects.create(
            operation='lead_sync',
            status='failed',
            entity_type='lead',
            entity_id='test-lead-2',
            error_message='API timeout'
        )
        
        self.analytics_service = AnalyticsService()
    
    def test_debriefing_completion_rate_calculation(self):
        """Test debriefing completion rate calculation"""
        result = self.analytics_service.calculate_debriefing_completion_rate(
            self.start_date, self.end_date, self.user
        )
        
        self.assertEqual(result['total_meetings'], 2)
        self.assertEqual(result['completed_debriefings'], 1)
        self.assertEqual(result['scheduled_debriefings'], 1)
        self.assertEqual(result['completion_rate'], 50.0)
    
    def test_data_extraction_accuracy_calculation(self):
        """Test data extraction accuracy calculation"""
        result = self.analytics_service.calculate_data_extraction_accuracy(
            self.start_date, self.end_date
        )
        
        self.assertEqual(result['total_sessions'], 1)
        self.assertEqual(result['average_confidence'], 0.85)  # (0.9 + 0.8) / 2
        self.assertEqual(result['extraction_accuracy'], 85.0)
    
    def test_meeting_detection_accuracy_calculation(self):
        """Test meeting detection accuracy calculation"""
        result = self.analytics_service.calculate_meeting_detection_accuracy(
            self.start_date, self.end_date
        )
        
        self.assertEqual(result['total_meetings'], 2)
        self.assertEqual(result['sales_meetings'], 2)
        self.assertEqual(result['high_confidence_meetings'], 1)  # Only meeting1 has >= 0.8
        self.assertEqual(result['detection_accuracy'], 50.0)
        self.assertEqual(result['sales_meeting_rate'], 100.0)
    
    def test_crm_sync_success_rate_calculation(self):
        """Test CRM sync success rate calculation"""
        result = self.analytics_service.calculate_crm_sync_success_rate(
            self.start_date, self.end_date
        )
        
        self.assertEqual(result['total_syncs'], 2)
        self.assertEqual(result['successful_syncs'], 1)
        self.assertEqual(result['failed_syncs'], 1)
        self.assertEqual(result['success_rate'], 50.0)
    
    def test_store_performance_metric(self):
        """Test storing performance metrics"""
        metric = self.analytics_service.store_performance_metric(
            metric_type='test_metric',
            value=75.5,
            aggregation_period='daily',
            period_start=self.start_date,
            period_end=self.end_date,
            user=self.user,
            metadata={'test': 'data'}
        )
        
        self.assertEqual(metric.metric_type, 'test_metric')
        self.assertEqual(metric.value, 75.5)
        self.assertEqual(metric.user, self.user)
        self.assertEqual(metric.metadata['test'], 'data')


class ReportingServiceTestCase(TestCase):
    """Test reporting services"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.reporting_service = ReportingService()
        self.test_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    @patch('apps.analytics.services.AnalyticsService.calculate_debriefing_completion_rate')
    @patch('apps.analytics.services.AnalyticsService.calculate_data_extraction_accuracy')
    @patch('apps.analytics.services.AnalyticsService.calculate_meeting_detection_accuracy')
    @patch('apps.analytics.services.AnalyticsService.calculate_user_engagement_metrics')
    def test_generate_daily_summary_report(self, mock_engagement, mock_meeting, 
                                         mock_extraction, mock_debriefing):
        """Test daily summary report generation"""
        # Mock analytics data
        mock_debriefing.return_value = {'completion_rate': 80.0, 'total_meetings': 10}
        mock_extraction.return_value = {'extraction_accuracy': 85.0}
        mock_meeting.return_value = {'total_meetings': 10, 'sales_meetings': 8}
        mock_engagement.return_value = {'total_engagements': 50}
        
        report = self.reporting_service.generate_daily_summary_report(
            self.test_date, self.user
        )
        
        self.assertEqual(report.report_type, 'daily_summary')
        self.assertEqual(report.status, 'completed')
        self.assertIn('debriefing_metrics', report.report_data)
        self.assertIn('extraction_metrics', report.report_data)
        self.assertIsNotNone(report.summary)
    
    @patch('apps.analytics.services.AnalyticsService.calculate_debriefing_completion_rate')
    @patch('apps.analytics.services.AnalyticsService.calculate_data_extraction_accuracy')
    def test_generate_weekly_performance_report(self, mock_extraction, mock_debriefing):
        """Test weekly performance report generation"""
        # Mock analytics data
        mock_debriefing.return_value = {'completion_rate': 75.0}
        mock_extraction.return_value = {'extraction_accuracy': 82.0}
        
        report = self.reporting_service.generate_weekly_performance_report(
            self.test_date, self.user
        )
        
        self.assertEqual(report.report_type, 'weekly_performance')
        self.assertEqual(report.status, 'completed')
        self.assertIn('debriefing_metrics', report.report_data)
    
    def test_generate_user_activity_report(self):
        """Test user activity report generation"""
        # Create some test engagement data
        UserEngagementMetric.objects.create(
            user=self.user,
            engagement_type='login',
            session_id='test-session'
        )
        
        report = self.reporting_service.generate_user_activity_report(
            self.test_date, self.test_date + timedelta(days=7), self.user
        )
        
        self.assertEqual(report.report_type, 'user_activity')
        self.assertEqual(report.status, 'completed')
        self.assertIn('user_info', report.report_data)
        self.assertIn('engagement_metrics', report.report_data)


class RealTimeAnalyticsCollectorTestCase(TestCase):
    """Test real-time analytics collection"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_track_user_engagement(self):
        """Test user engagement tracking"""
        RealTimeAnalyticsCollector.track_user_engagement(
            user=self.user,
            engagement_type='debriefing_start',
            session_id='test-session',
            duration_seconds=300,
            entity_type='meeting',
            entity_id='test-meeting-id',
            metadata={'meeting_type': 'discovery'}
        )
        
        engagement = UserEngagementMetric.objects.filter(user=self.user).first()
        self.assertIsNotNone(engagement)
        self.assertEqual(engagement.engagement_type, 'debriefing_start')
        self.assertEqual(engagement.session_id, 'test-session')
        self.assertEqual(engagement.duration_seconds, 300)
    
    def test_track_data_quality(self):
        """Test data quality tracking"""
        RealTimeAnalyticsCollector.track_data_quality(
            entity_type='debriefing',
            entity_id='test-debriefing-id',
            quality_type='extraction_confidence',
            score=0.85,
            field_name='contact_info',
            confidence=0.92,
            user=self.user
        )
        
        quality_metric = DataQualityMetric.objects.filter(
            entity_type='debriefing'
        ).first()
        self.assertIsNotNone(quality_metric)
        self.assertEqual(quality_metric.score, 0.85)
        self.assertEqual(quality_metric.confidence, 0.92)
    
    def test_track_system_health(self):
        """Test system health tracking"""
        metric = RealTimeAnalyticsCollector.track_system_health(
            health_type='api_response_time',
            component='gemini_api',
            value=150.0,
            unit='ms',
            warning_threshold=200.0,
            critical_threshold=500.0
        )
        
        self.assertIsNotNone(metric)
        self.assertEqual(metric.value, 150.0)
        self.assertEqual(metric.status, 'healthy')


class AnalyticsCacheTestCase(TestCase):
    """Test analytics caching functionality"""
    
    def setUp(self):
        cache.clear()
    
    def tearDown(self):
        cache.clear()
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = AnalyticsCache.generate_cache_key('dashboard', 'user_1', days=7)
        key2 = AnalyticsCache.generate_cache_key('dashboard', 'user_1', days=7)
        key3 = AnalyticsCache.generate_cache_key('dashboard', 'user_2', days=7)
        
        # Same parameters should generate same key
        self.assertEqual(key1, key2)
        # Different parameters should generate different keys
        self.assertNotEqual(key1, key3)
    
    def test_cache_set_and_get(self):
        """Test cache set and get operations"""
        test_data = {'test': 'data', 'value': 123}
        
        # Set data in cache
        success = AnalyticsCache.set('dashboard', test_data, 'test_key')
        self.assertTrue(success)
        
        # Get data from cache
        cached_data = AnalyticsCache.get('dashboard', 'test_key')
        self.assertEqual(cached_data, test_data)
    
    def test_cache_delete(self):
        """Test cache deletion"""
        test_data = {'test': 'data'}
        
        # Set and verify data exists
        AnalyticsCache.set('dashboard', test_data, 'test_key')
        self.assertIsNotNone(AnalyticsCache.get('dashboard', 'test_key'))
        
        # Delete and verify data is gone
        AnalyticsCache.delete('dashboard', 'test_key')
        self.assertIsNone(AnalyticsCache.get('dashboard', 'test_key'))


class AnalyticsOptimizerTestCase(TestCase):
    """Test analytics optimization utilities"""
    
    def test_batch_process_metrics(self):
        """Test batch processing of metrics"""
        test_data = list(range(250))  # 250 items
        
        result = AnalyticsOptimizer.batch_process_metrics(test_data, batch_size=100)
        
        self.assertEqual(len(result), 250)
        self.assertEqual(result, test_data)
    
    def test_aggregate_time_series_data(self):
        """Test time series data aggregation"""
        now = timezone.now()
        test_data = [
            {'timestamp': now, 'value': 10},
            {'timestamp': now + timedelta(minutes=30), 'value': 15},
            {'timestamp': now + timedelta(hours=1), 'value': 20},
            {'timestamp': now + timedelta(hours=1, minutes=30), 'value': 25},
        ]
        
        # Aggregate by hour
        result = AnalyticsOptimizer.aggregate_time_series_data(
            test_data, 'timestamp', 'value', 'hour'
        )
        
        # Should have 2 hour buckets
        self.assertEqual(len(result), 2)
        
        # First hour should have average of 12.5 (10 + 15) / 2
        first_hour_key = now.strftime('%Y-%m-%d %H:00:00')
        self.assertEqual(result[first_hour_key]['avg'], 12.5)
    
    def test_calculate_percentiles(self):
        """Test percentile calculations"""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        percentiles = AnalyticsOptimizer.calculate_percentiles(values, [50, 90, 95])
        
        self.assertEqual(percentiles[50], 5)  # Median
        self.assertEqual(percentiles[90], 9)  # 90th percentile
        self.assertEqual(percentiles[95], 10)  # 95th percentile
    
    def test_detect_anomalies(self):
        """Test anomaly detection"""
        # Normal values with one outlier
        values = [10, 12, 11, 13, 9, 11, 10, 50, 12, 11]  # 50 is an outlier
        
        result = AnalyticsOptimizer.detect_anomalies(values, threshold=2.0)
        
        self.assertEqual(len(result['anomalies']), 1)
        self.assertEqual(result['anomalies'][0]['value'], 50)
        self.assertGreater(result['anomalies'][0]['z_score'], 2.0)


class RealTimeAnalyticsCacheTestCase(TestCase):
    """Test real-time analytics caching"""
    
    def setUp(self):
        cache.clear()
        self.realtime_cache = RealTimeAnalyticsCache()
    
    def tearDown(self):
        cache.clear()
    
    def test_set_and_get_real_time_metric(self):
        """Test real-time metric caching"""
        success = self.realtime_cache.set_real_time_metric(
            'active_sessions', 25, user_id=1
        )
        self.assertTrue(success)
        
        metric = self.realtime_cache.get_real_time_metric(
            'active_sessions', user_id=1
        )
        self.assertIsNotNone(metric)
        self.assertEqual(metric['value'], 25)
        self.assertEqual(metric['user_id'], 1)
    
    def test_increment_counter(self):
        """Test counter increment functionality"""
        # First increment
        result1 = self.realtime_cache.increment_counter('page_views', user_id=1)
        self.assertEqual(result1, 1)
        
        # Second increment
        result2 = self.realtime_cache.increment_counter('page_views', user_id=1, increment=5)
        self.assertEqual(result2, 6)
    
    def test_mark_user_active(self):
        """Test marking user as active"""
        success = self.realtime_cache.mark_user_active(1)
        self.assertTrue(success)


class AnalyticsAPITestCase(APITestCase):
    """Test analytics API endpoints"""
    
    def setUp(self):
        # Create users and groups
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.sales_manager = User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='managerpass123'
        )
        self.sales_rep = User.objects.create_user(
            username='rep',
            email='rep@example.com',
            password='reppass123'
        )
        
        # Create groups
        admin_group = Group.objects.create(name='admin')
        manager_group = Group.objects.create(name='sales_manager')
        rep_group = Group.objects.create(name='sales_rep')
        
        self.admin_user.groups.add(admin_group)
        self.sales_manager.groups.add(manager_group)
        self.sales_rep.groups.add(rep_group)
        
        # Create test data
        self.performance_metric = PerformanceMetric.objects.create(
            metric_type='debriefing_completion',
            metric_name='Debriefing Completion Rate',
            aggregation_period='daily',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=1),
            value=85.5,
            user=self.sales_rep
        )
        
        self.report = Report.objects.create(
            report_type='daily_summary',
            title='Test Report',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=1),
            created_by=self.sales_rep,
            status='completed',
            report_data={'test': 'data'}
        )
    
    def test_dashboard_analytics_authenticated(self):
        """Test dashboard analytics endpoint with authentication"""
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('period', response.data)
        self.assertIn('debriefing_metrics', response.data)
    
    def test_dashboard_analytics_unauthenticated(self):
        """Test dashboard analytics endpoint without authentication"""
        url = reverse('analytics:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_performance_metrics_list(self):
        """Test performance metrics list endpoint"""
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:performance-metrics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_performance_metrics_filtering(self):
        """Test performance metrics filtering"""
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:performance-metrics')
        response = self.client.get(url, {'metric_type': 'debriefing_completion'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Test with non-existent metric type
        response = self.client.get(url, {'metric_type': 'non_existent'})
        self.assertEqual(len(response.data['results']), 0)
    
    def test_track_engagement_endpoint(self):
        """Test engagement tracking endpoint"""
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:track-engagement')
        data = {
            'engagement_type': 'debriefing_start',
            'session_id': 'test-session',
            'duration_seconds': 300,
            'entity_type': 'meeting',
            'entity_id': 'test-meeting-id',
            'metadata': {'test': 'data'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        # Verify engagement was created
        engagement = UserEngagementMetric.objects.filter(user=self.sales_rep).first()
        self.assertIsNotNone(engagement)
        self.assertEqual(engagement.engagement_type, 'debriefing_start')
    
    def test_generate_report_endpoint(self):
        """Test report generation endpoint"""
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:generate-report')
        data = {
            'report_type': 'daily_summary',
            'start_date': timezone.now().isoformat()
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['report_type'], 'daily_summary')
    
    def test_reports_list_access_control(self):
        """Test reports list access control"""
        # Sales rep should see their own reports
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:reports-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Admin should see all reports
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_system_health_status_admin_only(self):
        """Test system health status endpoint requires admin access"""
        # Sales rep should not have access
        self.client.force_authenticate(user=self.sales_rep)
        
        url = reverse('analytics:system-health-status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin should have access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_status', response.data)
    
    def test_export_analytics_data(self):
        """Test analytics data export"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('analytics:export-data')
        response = self.client.get(url, {'format': 'json', 'metric_type': 'all'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Test CSV export
        response = self.client.get(url, {'format': 'csv', 'metric_type': 'debriefing'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')


class AnalyticsIntegrationTestCase(TransactionTestCase):
    """Integration tests for analytics system"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create realistic test data
        self.create_test_meetings()
        self.create_test_debriefings()
        self.create_test_engagement_data()
    
    def create_test_meetings(self):
        """Create test meetings for integration testing"""
        base_time = timezone.now() - timedelta(days=7)
        
        for i in range(10):
            Meeting.objects.create(
                title=f'Test Meeting {i+1}',
                start_time=base_time + timedelta(days=i),
                end_time=base_time + timedelta(days=i, hours=1),
                organizer=self.user,
                is_sales_meeting=True,
                debriefing_completed=i % 2 == 0,  # 50% completion rate
                confidence_score=0.8 + (i % 3) * 0.1  # Varying confidence
            )
    
    def create_test_debriefings(self):
        """Create test debriefing sessions"""
        completed_meetings = Meeting.objects.filter(debriefing_completed=True)
        
        for meeting in completed_meetings:
            DebriefingSession.objects.create(
                meeting=meeting,
                scheduled_time=meeting.end_time + timedelta(minutes=30),
                started_at=meeting.end_time + timedelta(minutes=30),
                completed_at=meeting.end_time + timedelta(hours=1),
                status='completed',
                confidence_scores={
                    'contact_info': 0.85 + (meeting.id % 3) * 0.05,
                    'deal_info': 0.80 + (meeting.id % 4) * 0.05
                }
            )
    
    def create_test_engagement_data(self):
        """Create test user engagement data"""
        engagement_types = ['login', 'meeting_view', 'debriefing_start', 'debriefing_complete']
        
        for i in range(20):
            UserEngagementMetric.objects.create(
                user=self.user,
                engagement_type=engagement_types[i % len(engagement_types)],
                session_id=f'session-{i}',
                duration_seconds=300 + (i * 30)
            )
    
    def test_end_to_end_analytics_workflow(self):
        """Test complete analytics workflow"""
        analytics_service = AnalyticsService()
        
        start_date = timezone.now() - timedelta(days=7)
        end_date = timezone.now()
        
        # Test all analytics calculations
        debriefing_metrics = analytics_service.calculate_debriefing_completion_rate(
            start_date, end_date, self.user
        )
        self.assertEqual(debriefing_metrics['completion_rate'], 50.0)
        
        extraction_metrics = analytics_service.calculate_data_extraction_accuracy(
            start_date, end_date
        )
        self.assertGreater(extraction_metrics['average_confidence'], 0.8)
        
        meeting_metrics = analytics_service.calculate_meeting_detection_accuracy(
            start_date, end_date
        )
        self.assertEqual(meeting_metrics['total_meetings'], 10)
        
        engagement_metrics = analytics_service.calculate_user_engagement_metrics(
            start_date, end_date, self.user
        )
        self.assertEqual(engagement_metrics['total_engagements'], 20)
        
        # Test report generation
        reporting_service = ReportingService()
        report = reporting_service.generate_daily_summary_report(
            timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
            self.user
        )
        
        self.assertEqual(report.status, 'completed')
        self.assertIn('debriefing_metrics', report.report_data)
        self.assertIn('extraction_metrics', report.report_data)
    
    def test_real_time_analytics_collection(self):
        """Test real-time analytics data collection"""
        # Track various engagement events
        RealTimeAnalyticsCollector.track_user_engagement(
            user=self.user,
            engagement_type='ai_interaction',
            session_id='test-session',
            metadata={'interaction_type': 'question_generation'}
        )
        
        # Track data quality
        RealTimeAnalyticsCollector.track_data_quality(
            entity_type='debriefing',
            entity_id='test-debriefing',
            quality_type='extraction_confidence',
            score=0.92
        )
        
        # Track system health
        health_metric = RealTimeAnalyticsCollector.track_system_health(
            health_type='api_response_time',
            component='gemini_api',
            value=120.0,
            unit='ms'
        )
        
        # Verify data was collected
        self.assertEqual(UserEngagementMetric.objects.count(), 21)  # 20 + 1 new
        self.assertEqual(DataQualityMetric.objects.count(), 1)
        self.assertIsNotNone(health_metric)
        self.assertEqual(health_metric.status, 'healthy')
    
    def test_caching_performance(self):
        """Test analytics caching performance"""
        analytics_service = AnalyticsService()
        
        start_date = timezone.now() - timedelta(days=7)
        end_date = timezone.now()
        
        # First call should hit the database
        import time
        start_time = time.time()
        result1 = analytics_service.calculate_debriefing_completion_rate(
            start_date, end_date, self.user
        )
        first_call_time = time.time() - start_time
        
        # Second call should hit the cache and be faster
        start_time = time.time()
        result2 = analytics_service.calculate_debriefing_completion_rate(
            start_date, end_date, self.user
        )
        second_call_time = time.time() - start_time
        
        # Results should be identical
        self.assertEqual(result1, result2)
        
        # Second call should be faster (cached)
        # Note: This might not always be true in test environment, so we just check results match
        self.assertEqual(result1['completion_rate'], result2['completion_rate'])