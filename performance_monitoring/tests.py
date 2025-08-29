"""
Performance monitoring tests
"""
import time
import threading
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.test.utils import override_settings
from django.utils import timezone
from datetime import timedelta

from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold, ConcurrentCallMetrics
)
from .services import PerformanceMonitoringService, AlertingService
from meetings.models import Meeting, CallBotSession


# Disable signal handlers during tests
@override_settings(USE_TZ=True)
class BasePerformanceTestCase(TestCase):
    """Base test case that disables signal handlers"""
    
    def setUp(self):
        # Disconnect signal handlers to avoid interference
        from django.db.models.signals import post_save
        from . import signals
        
        post_save.disconnect(
            signals.track_call_bot_session_created,
            sender=CallBotSession
        )
        post_save.disconnect(
            signals.update_call_bot_performance_on_status_change,
            sender=CallBotSession
        )
    
    def tearDown(self):
        # Reconnect signal handlers
        from django.db.models.signals import post_save
        from . import signals
        
        post_save.connect(
            signals.track_call_bot_session_created,
            sender=CallBotSession
        )
        post_save.connect(
            signals.update_call_bot_performance_on_status_change,
            sender=CallBotSession
        )


class PerformanceMetricModelTest(BasePerformanceTestCase):
    """Test PerformanceMetric model"""
    
    def test_create_performance_metric(self):
        """Test creating a performance metric"""
        metric = PerformanceMetric.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=2.5,
            unit='seconds',
            status='success'
        )
        
        self.assertEqual(metric.metric_type, 'call_bot_session')
        self.assertEqual(metric.metric_name, 'connection_time')
        self.assertEqual(metric.value, 2.5)
        self.assertEqual(metric.unit, 'seconds')
        self.assertEqual(metric.status, 'success')
    
    def test_duration_property(self):
        """Test duration calculation"""
        start_time = timezone.now()
        end_time = start_time + timedelta(seconds=5)
        
        metric = PerformanceMetric.objects.create(
            metric_type='test',
            metric_name='test_metric',
            value=5.0,
            start_time=start_time,
            end_time=end_time
        )
        
        self.assertEqual(metric.duration, 5.0)


class CallBotPerformanceModelTest(BasePerformanceTestCase):
    """Test CallBotPerformance model"""
    
    def setUp(self):
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.call_bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id='bot-123',
            platform='meet',
            join_time=timezone.now()
        )
    
    def test_create_call_bot_performance(self):
        """Test creating call bot performance record"""
        performance = CallBotPerformance.objects.create(
            call_bot_session=self.call_bot_session,
            connection_time=3.2,
            connection_attempts=1,
            connection_success=True,
            audio_quality_score=0.95,
            transcription_accuracy=0.92
        )
        
        self.assertEqual(performance.connection_time, 3.2)
        self.assertTrue(performance.connection_success)
        self.assertEqual(performance.audio_quality_score, 0.95)
        self.assertEqual(performance.transcription_accuracy, 0.92)
    
    def test_overall_score_calculation(self):
        """Test overall performance score calculation"""
        performance = CallBotPerformance.objects.create(
            call_bot_session=self.call_bot_session,
            connection_time=5.0,  # 5 seconds connection time
            connection_success=True,
            audio_quality_score=0.9,
            transcription_accuracy=0.85,
            error_count=1
        )
        
        score = performance.overall_score
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)


class PerformanceMonitoringServiceTest(BasePerformanceTestCase):
    """Test PerformanceMonitoringService"""
    
    def setUp(self):
        self.service = PerformanceMonitoringService()
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-456',
            title='Test Meeting 2',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.call_bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id='bot-456',
            platform='teams',
            join_time=timezone.now()
        )
    
    def test_record_metric(self):
        """Test recording a performance metric"""
        metric = self.service.record_metric(
            metric_type='test',
            metric_name='test_operation',
            value=1.5,
            unit='seconds',
            status='success'
        )
        
        self.assertIsNotNone(metric)
        self.assertEqual(metric.metric_name, 'test_operation')
        self.assertEqual(metric.value, 1.5)
    
    def test_track_performance_context_manager(self):
        """Test performance tracking context manager"""
        with self.service.track_performance('test', 'context_test'):
            time.sleep(0.1)  # Simulate work
        
        # Check that metric was recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='test',
            metric_name='context_test'
        )
        self.assertEqual(metrics.count(), 1)
        self.assertGreater(metrics.first().value, 0.05)  # Should be at least 0.05 seconds
    
    def test_track_performance_with_error(self):
        """Test performance tracking with error"""
        try:
            with self.service.track_performance('test', 'error_test'):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Check that error metric was recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='test',
            metric_name='error_test',
            status='error'
        )
        self.assertEqual(metrics.count(), 1)
        self.assertIn("Test error", metrics.first().error_message)
    
    def test_track_call_bot_performance(self):
        """Test tracking call bot performance"""
        performance = self.service.track_call_bot_performance(
            call_bot_session=self.call_bot_session,
            connection_time=2.8,
            connection_attempts=1,
            connection_success=True
        )
        
        self.assertIsNotNone(performance)
        self.assertEqual(performance.connection_time, 2.8)
        self.assertTrue(performance.connection_success)
        
        # Check that general metric was also recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='call_bot_session',
            metric_name='connection_time'
        )
        self.assertEqual(metrics.count(), 1)
    
    def test_track_ai_processing(self):
        """Test tracking AI processing performance"""
        ai_performance = self.service.track_ai_processing(
            operation_type='transcription',
            operation_id='op-123',
            processing_time=4.2,
            input_size=1000,
            output_size=800,
            confidence_score=0.88,
            tokens_used=150
        )
        
        self.assertIsNotNone(ai_performance)
        self.assertEqual(ai_performance.operation_type, 'transcription')
        self.assertEqual(ai_performance.processing_time, 4.2)
        self.assertEqual(ai_performance.confidence_score, 0.88)
        
        # Check processing rate calculation
        expected_rate = 1000 / 4.2  # input_size / processing_time
        self.assertAlmostEqual(ai_performance.processing_rate, expected_rate, places=2)
    
    @patch('performance_monitoring.services.psutil')
    def test_collect_system_metrics(self, mock_psutil):
        """Test collecting system metrics"""
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 45.2
        mock_psutil.virtual_memory.return_value = MagicMock(
            percent=62.1,
            available=2048 * 1024 * 1024  # 2GB in bytes
        )
        mock_psutil.disk_usage.return_value = MagicMock(percent=78.5)
        mock_psutil.net_io_counters.return_value = MagicMock(
            bytes_sent=1024000,
            bytes_recv=2048000
        )
        
        self.service.collect_system_metrics()
        
        # Check that metrics were recorded
        cpu_metrics = PerformanceMetric.objects.filter(
            metric_type='system_resource',
            metric_name='cpu_usage'
        )
        self.assertEqual(cpu_metrics.count(), 1)
        self.assertEqual(cpu_metrics.first().value, 45.2)
        
        memory_metrics = PerformanceMetric.objects.filter(
            metric_type='system_resource',
            metric_name='memory_usage'
        )
        self.assertEqual(memory_metrics.count(), 1)
        self.assertEqual(memory_metrics.first().value, 62.1)
    
    def test_get_performance_summary(self):
        """Test getting performance summary"""
        # Create some test metrics
        PerformanceMetric.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=2.5,
            status='success'
        )
        
        PerformanceMetric.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=3.2,
            status='error'
        )
        
        PerformanceMetric.objects.create(
            metric_type='ai_processing',
            metric_name='transcription_processing_time',
            value=5.1,
            status='success'
        )
        
        summary = self.service.get_performance_summary(hours=24)
        
        self.assertIn('total_metrics', summary)
        self.assertIn('error_rate', summary)
        self.assertIn('call_bot_performance', summary)
        self.assertIn('ai_performance', summary)
        self.assertEqual(summary['total_metrics'], 3)
        self.assertAlmostEqual(summary['error_rate'], 33.33, places=2)


class AlertingServiceTest(BasePerformanceTestCase):
    """Test AlertingService"""
    
    def setUp(self):
        self.alerting_service = AlertingService()
    
    def test_create_alert(self):
        """Test creating an alert"""
        alert = self.alerting_service.create_alert(
            alert_type='performance_degradation',
            severity='warning',
            title='Test Alert',
            description='This is a test alert',
            component='test_component',
            metric_threshold=10.0,
            current_value=15.0
        )
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, 'performance_degradation')
        self.assertEqual(alert.severity, 'warning')
        self.assertEqual(alert.title, 'Test Alert')
        self.assertTrue(alert.is_active)
        self.assertFalse(alert.acknowledged)
    
    @patch('performance_monitoring.services.psutil')
    def test_check_resource_usage_high_cpu(self, mock_psutil):
        """Test resource usage check with high CPU"""
        # Mock high CPU usage
        mock_psutil.cpu_percent.return_value = 95.0
        mock_psutil.virtual_memory.return_value = MagicMock(
            percent=50.0,
            available=4096 * 1024 * 1024
        )
        mock_psutil.disk_usage.return_value = MagicMock(percent=60.0)
        
        self.alerting_service._check_resource_usage()
        
        # Check that CPU alert was created
        alerts = SystemAlert.objects.filter(
            alert_type='resource_exhaustion',
            component='cpu'
        )
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.first().severity, 'critical')
    
    def test_check_error_rates(self):
        """Test error rate checking"""
        # Create metrics with high error rate
        for i in range(10):
            status = 'error' if i < 7 else 'success'  # 70% error rate
            PerformanceMetric.objects.create(
                metric_type='test',
                metric_name='test_metric',
                value=1.0,
                status=status,
                timestamp=timezone.now()
            )
        
        self.alerting_service._check_error_rates()
        
        # Check that error rate alert was created
        alerts = SystemAlert.objects.filter(
            alert_type='high_error_rate'
        )
        self.assertEqual(alerts.count(), 1)
        self.assertEqual(alerts.first().severity, 'critical')  # 70% > 50%


class ConcurrentCallLoadTest(BasePerformanceTestCase):
    """Test concurrent call handling performance"""
    
    def setUp(self):
        self.service = PerformanceMonitoringService()
    
    def test_concurrent_call_tracking(self):
        """Test tracking concurrent calls"""
        # Create multiple active call bot sessions
        meetings = []
        sessions = []
        
        for i in range(5):
            meeting = Meeting.objects.create(
                calendar_event_id=f'concurrent-test-{i}',
                title=f'Concurrent Test Meeting {i}',
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1)
            )
            meetings.append(meeting)
            
            session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f'concurrent-bot-{i}',
                platform='meet',
                join_time=timezone.now(),
                connection_status='connected'
            )
            sessions.append(session)
        
        # Track concurrent calls
        metrics = self.service.track_concurrent_calls()
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.active_calls, 5)
    
    def test_concurrent_performance_simulation(self):
        """Test performance under concurrent load simulation"""
        def simulate_call_session(session_id):
            """Simulate a call session with performance tracking"""
            meeting = Meeting.objects.create(
                calendar_event_id=f'load-test-{session_id}',
                title=f'Load Test Meeting {session_id}',
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1)
            )
            
            call_bot_session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f'load-bot-{session_id}',
                platform='meet',
                join_time=timezone.now(),
                connection_status='connected'
            )
            
            # Simulate connection time
            connection_time = 2.0 + (session_id * 0.1)  # Increasing connection time
            
            # Track performance
            self.service.track_call_bot_performance(
                call_bot_session=call_bot_session,
                connection_time=connection_time,
                connection_success=True
            )
            
            # Simulate AI processing
            self.service.track_ai_processing(
                operation_type='transcription',
                operation_id=f'ai-op-{session_id}',
                processing_time=3.0 + (session_id * 0.2),
                input_size=1000,
                output_size=800,
                confidence_score=0.9
            )
        
        # Simulate 10 concurrent sessions
        threads = []
        for i in range(10):
            thread = threading.Thread(target=simulate_call_session, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all performance records were created
        call_performances = CallBotPerformance.objects.all()
        ai_performances = AIProcessingPerformance.objects.all()
        
        self.assertEqual(call_performances.count(), 10)
        self.assertEqual(ai_performances.count(), 10)
        
        # Check performance degradation with load
        connection_times = [p.connection_time for p in call_performances]
        self.assertGreater(max(connection_times), min(connection_times))  # Should show degradation


class PerformanceThresholdTest(BasePerformanceTestCase):
    """Test performance threshold monitoring"""
    
    def setUp(self):
        self.service = PerformanceMonitoringService()
        
        # Create a performance threshold
        self.threshold = PerformanceThreshold.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            warning_threshold=5.0,
            error_threshold=10.0,
            critical_threshold=15.0,
            comparison_operator='>',
            is_active=True
        )
    
    def test_threshold_violation_warning(self):
        """Test threshold violation creates warning alert"""
        # Record metric that exceeds warning threshold
        self.service.record_metric(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=7.0,  # Exceeds warning threshold of 5.0
            status='success'
        )
        
        # Check that warning alert was created
        alerts = SystemAlert.objects.filter(
            alert_type='performance_degradation',
            severity='warning'
        )
        self.assertEqual(alerts.count(), 1)
    
    def test_threshold_violation_critical(self):
        """Test threshold violation creates critical alert"""
        # Record metric that exceeds critical threshold
        self.service.record_metric(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=20.0,  # Exceeds critical threshold of 15.0
            status='success'
        )
        
        # Check that critical alert was created
        alerts = SystemAlert.objects.filter(
            alert_type='performance_degradation',
            severity='critical'
        )
        self.assertEqual(alerts.count(), 1)
    
    def test_no_threshold_violation(self):
        """Test that no alert is created when threshold is not exceeded"""
        # Record metric that doesn't exceed any threshold
        self.service.record_metric(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=3.0,  # Below warning threshold of 5.0
            status='success'
        )
        
        # Check that no alert was created
        alerts = SystemAlert.objects.filter(
            alert_type='performance_degradation'
        )
        self.assertEqual(alerts.count(), 0)