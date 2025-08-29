"""
Integration tests for performance monitoring system
"""
import time
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User

from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold
)
from .services import PerformanceMonitoringService, AlertingService
from meetings.models import Meeting, CallBotSession
from leads.models import Lead


class PerformanceMonitoringIntegrationTest(TestCase):
    """
    Integration test for the complete performance monitoring system
    """
    
    def setUp(self):
        self.performance_service = PerformanceMonitoringService()
        self.alerting_service = AlertingService()
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_INTEGRATION",
            name="Integration Test Lead",
            email="integration@example.com",
            company="Test Company"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="integration_test_meeting",
            lead=self.lead,
            title="Integration Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        
        self.call_bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="integration_test_bot",
            platform="meet",
            join_time=timezone.now(),
            connection_status="connected"
        )
    
    def test_complete_monitoring_workflow(self):
        """Test the complete monitoring workflow from metrics to alerts"""
        
        # Step 1: Track call bot performance
        performance = self.performance_service.track_call_bot_performance(
            call_bot_session=self.call_bot_session,
            connection_time=2.5,
            connection_success=True
        )
        
        self.assertIsNotNone(performance)
        self.assertEqual(performance.connection_time, 2.5)
        self.assertTrue(performance.connection_success)
        
        # Verify performance metric was created
        metric = PerformanceMetric.objects.filter(
            metric_type='call_bot_session',
            metric_name='connection_time'
        ).first()
        self.assertIsNotNone(metric)
        self.assertEqual(metric.value, 2.5)
        
        # Step 2: Update audio metrics
        self.performance_service.update_call_bot_audio_metrics(
            call_bot_session=self.call_bot_session,
            audio_quality_score=0.92,
            audio_dropouts=1,
            audio_latency=45.0
        )
        
        performance.refresh_from_db()
        self.assertEqual(performance.audio_quality_score, 0.92)
        self.assertEqual(performance.audio_dropouts, 1)
        self.assertEqual(performance.audio_latency, 45.0)
        
        # Step 3: Track AI processing
        ai_performance = self.performance_service.track_ai_processing(
            operation_type='transcription',
            operation_id='integration_test_transcription',
            processing_time=1.8,
            input_size=1200,
            output_size=950,
            confidence_score=0.89
        )
        
        self.assertIsNotNone(ai_performance)
        self.assertEqual(ai_performance.processing_time, 1.8)
        self.assertEqual(ai_performance.confidence_score, 0.89)
        
        # Step 4: Create performance threshold
        threshold = PerformanceThreshold.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            warning_threshold=2.0,
            error_threshold=5.0,
            critical_threshold=10.0,
            comparison_operator='>',
            is_active=True
        )
        
        # Step 5: Record metric that exceeds threshold
        self.performance_service.record_metric(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=6.0,  # Exceeds error threshold
            content_object=self.call_bot_session
        )
        
        # Verify alert was created
        alert = SystemAlert.objects.filter(
            alert_type='performance_degradation',
            component='call_bot_session.connection_time'
        ).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'error')
        self.assertIn('6.0', alert.description)
        
        # Step 6: Test alert workflow
        self.assertFalse(alert.acknowledged)
        alert.acknowledge('test_user@example.com')
        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.acknowledged_by, 'test_user@example.com')
        
        alert.resolve('test_user@example.com', 'Issue resolved during testing')
        self.assertTrue(alert.resolved)
        self.assertFalse(alert.is_active)
        
        # Step 7: Generate performance summary
        summary = self.performance_service.get_performance_summary(hours=1)
        
        self.assertIsInstance(summary, dict)
        self.assertGreater(summary['total_metrics'], 0)
        self.assertIn('call_bot_performance', summary)
        self.assertIn('ai_performance', summary)
        
        # Step 8: Test system health check
        self.alerting_service.check_system_health()
        
        # Verify the complete workflow worked
        total_metrics = PerformanceMetric.objects.count()
        total_alerts = SystemAlert.objects.count()
        
        self.assertGreater(total_metrics, 0)
        self.assertGreater(total_alerts, 0)
        
        print(f"Integration test completed successfully:")
        print(f"- Total metrics recorded: {total_metrics}")
        print(f"- Total alerts created: {total_alerts}")
        print(f"- Call bot performance score: {performance.overall_score:.2f}")
        print(f"- AI processing rate: {ai_performance.processing_rate:.1f} chars/sec")
    
    def test_concurrent_metrics_collection(self):
        """Test concurrent metrics collection doesn't cause issues"""
        
        # Create multiple metrics concurrently
        import threading
        
        def create_metrics(thread_id):
            for i in range(10):
                self.performance_service.record_metric(
                    metric_type='test_concurrent',
                    metric_name=f'thread_{thread_id}_metric_{i}',
                    value=float(i),
                    metadata={'thread_id': thread_id, 'iteration': i}
                )
        
        # Start multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=create_metrics, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all metrics were created
        concurrent_metrics = PerformanceMetric.objects.filter(
            metric_type='test_concurrent'
        ).count()
        
        self.assertEqual(concurrent_metrics, 50)  # 5 threads * 10 metrics each
    
    def test_performance_context_manager_integration(self):
        """Test performance tracking context manager integration"""
        
        # Test successful operation
        with self.performance_service.track_performance(
            metric_type='integration_test',
            metric_name='successful_operation',
            content_object=self.meeting,
            metadata={'test_type': 'integration'}
        ):
            time.sleep(0.1)  # Simulate work
        
        success_metric = PerformanceMetric.objects.filter(
            metric_type='integration_test',
            metric_name='successful_operation'
        ).first()
        
        self.assertIsNotNone(success_metric)
        self.assertEqual(success_metric.status, 'success')
        self.assertGreaterEqual(success_metric.value, 0.1)
        self.assertEqual(success_metric.metadata['test_type'], 'integration')
        
        # Test operation with error
        with self.assertRaises(ValueError):
            with self.performance_service.track_performance(
                metric_type='integration_test',
                metric_name='failed_operation'
            ):
                raise ValueError("Test error")
        
        error_metric = PerformanceMetric.objects.filter(
            metric_type='integration_test',
            metric_name='failed_operation'
        ).first()
        
        self.assertIsNotNone(error_metric)
        self.assertEqual(error_metric.status, 'error')
        self.assertIn("Test error", error_metric.error_message)


class PerformanceMonitoringAPITest(APITestCase):
    """
    API integration tests for performance monitoring endpoints
    """
    
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.performance_service = PerformanceMonitoringService()
        
        # Create some test metrics
        for i in range(5):
            self.performance_service.record_metric(
                metric_type='api_test',
                metric_name=f'test_metric_{i}',
                value=float(i),
                status='success' if i < 4 else 'error'
            )
    
    def test_performance_metrics_api(self):
        """Test performance metrics API endpoints"""
        
        # Test list metrics
        url = reverse('performance_monitoring:performancemetric-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # Test filter by metric type
        response = self.client.get(url, {'metric_type': 'api_test'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 5)
        
        # Test summary endpoint
        summary_url = reverse('performance_monitoring:performancemetric-summary')
        response = self.client.get(summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_metrics', response.data)
        self.assertIn('error_rate', response.data)
    
    def test_system_alerts_api(self):
        """Test system alerts API endpoints"""
        
        # Create test alert
        alert = SystemAlert.objects.create(
            alert_type='performance_degradation',
            severity='warning',
            title='API Test Alert',
            description='Test alert for API testing',
            component='api_test'
        )
        
        # Test list alerts
        url = reverse('performance_monitoring:systemalert-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # Test acknowledge alert
        acknowledge_url = reverse('performance_monitoring:systemalert-acknowledge', args=[alert.id])
        response = self.client.post(acknowledge_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('acknowledged_by', response.data)
        
        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)
        
        # Test resolve alert
        resolve_url = reverse('performance_monitoring:systemalert-resolve', args=[alert.id])
        response = self.client.post(resolve_url, {'notes': 'Resolved via API test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        alert.refresh_from_db()
        self.assertTrue(alert.resolved)
        self.assertFalse(alert.is_active)
        self.assertEqual(alert.resolution_notes, 'Resolved via API test')
        
        # Test dashboard endpoint
        dashboard_url = reverse('performance_monitoring:systemalert-dashboard')
        response = self.client.get(dashboard_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('active_alerts', response.data)
        self.assertIn('severity_breakdown', response.data)
    
    def test_monitoring_operations_api(self):
        """Test monitoring operations API endpoints"""
        
        # Test collect metrics endpoint
        collect_url = reverse('performance_monitoring:performancemonitoring-collect-metrics')
        response = self.client.post(collect_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('concurrent_calls', response.data)
        
        # Test health check endpoint
        health_url = reverse('performance_monitoring:performancemonitoring-health-check')
        response = self.client.post(health_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('health_status', response.data)
        self.assertIn('active_alerts', response.data)
        
        # Test system status endpoint
        status_url = reverse('performance_monitoring:performancemonitoring-system-status')
        response = self.client.get(status_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('system_resources', response.data)
        self.assertIn('active_calls', response.data)


if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'rest_framework',
                'performance_monitoring',
                'meetings',
                'leads',
            ],
            SECRET_KEY='test-secret-key',
            USE_TZ=True,
        )
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['performance_monitoring.test_integration'])
    
    if failures:
        exit(1)