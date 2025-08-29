"""
Integration tests for performance monitoring with existing services
"""
import time
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from .services import performance_monitor
from .models import PerformanceMetric, CallBotPerformance
from meetings.models import Meeting, CallBotSession
from meetings.call_bot_service import CallBotService


class PerformanceIntegrationTest(TestCase):
    """Integration tests for performance monitoring"""
    
    def setUp(self):
        self.meeting = Meeting.objects.create(
            calendar_event_id='integration-test-123',
            title='Integration Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
    
    @patch('meetings.call_bot_service.CallBotService._connect_to_platform')
    @patch('meetings.call_bot_service.CallBotService._start_audio_stream')
    def test_call_bot_performance_tracking(self, mock_audio, mock_connect):
        """Test that call bot performance is tracked correctly"""
        # Mock successful connection
        mock_connect.return_value = True
        mock_audio.return_value = MagicMock()
        
        # Create call bot service
        call_bot_service = CallBotService()
        
        # Start tracking performance
        start_time = time.time()
        
        # Simulate joining a meeting
        session = call_bot_service.join_meeting(
            meeting_url='https://meet.google.com/test-123',
            platform='meet'
        )
        
        connection_time = time.time() - start_time
        
        # Track performance manually (since we're mocking the actual service)
        performance = performance_monitor.track_call_bot_performance(
            call_bot_session=session,
            connection_time=connection_time,
            connection_success=True
        )
        
        # Verify performance was tracked
        self.assertIsNotNone(performance)
        self.assertEqual(performance.call_bot_session, session)
        self.assertTrue(performance.connection_success)
        self.assertGreater(performance.connection_time, 0)
        
        # Verify metric was recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='call_bot_session',
            metric_name='connection_time'
        )
        self.assertEqual(metrics.count(), 1)
    
    def test_performance_context_manager_integration(self):
        """Test performance tracking context manager with real operations"""
        
        # Test database operation performance
        with performance_monitor.track_performance(
            'database_query', 
            'meeting_creation',
            metadata={'operation': 'create_meeting'}
        ):
            # Simulate database operation
            meeting = Meeting.objects.create(
                calendar_event_id='perf-test-456',
                title='Performance Test Meeting',
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1)
            )
        
        # Verify metric was recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='database_query',
            metric_name='meeting_creation'
        )
        self.assertEqual(metrics.count(), 1)
        
        metric = metrics.first()
        self.assertEqual(metric.status, 'success')
        self.assertGreater(metric.value, 0)
        self.assertEqual(metric.metadata['operation'], 'create_meeting')
    
    def test_concurrent_performance_tracking(self):
        """Test performance tracking under concurrent load"""
        import threading
        
        def create_session(session_id):
            """Create a call bot session and track performance"""
            meeting = Meeting.objects.create(
                calendar_event_id=f'concurrent-{session_id}',
                title=f'Concurrent Test {session_id}',
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(hours=1)
            )
            
            session = CallBotSession.objects.create(
                meeting=meeting,
                bot_session_id=f'concurrent-bot-{session_id}',
                platform='meet',
                join_time=timezone.now(),
                connection_status='connected'
            )
            
            # Track performance
            performance_monitor.track_call_bot_performance(
                call_bot_session=session,
                connection_time=1.0 + (session_id * 0.1),
                connection_success=True
            )
        
        # Create 5 concurrent sessions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_session, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all performances were tracked
        performances = CallBotPerformance.objects.all()
        self.assertEqual(performances.count(), 5)
        
        # Verify metrics were recorded
        metrics = PerformanceMetric.objects.filter(
            metric_type='call_bot_session',
            metric_name='connection_time'
        )
        self.assertEqual(metrics.count(), 5)
    
    def test_system_metrics_collection(self):
        """Test system metrics collection"""
        with patch('performance_monitoring.services.psutil') as mock_psutil:
            # Mock system metrics
            mock_psutil.cpu_percent.return_value = 45.2
            mock_psutil.virtual_memory.return_value = MagicMock(
                percent=62.1,
                available=2048 * 1024 * 1024
            )
            mock_psutil.disk_usage.return_value = MagicMock(percent=78.5)
            mock_psutil.net_io_counters.return_value = MagicMock(
                bytes_sent=1024000,
                bytes_recv=2048000
            )
            
            # Collect metrics
            performance_monitor.collect_system_metrics()
            
            # Verify system metrics were recorded
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
    
    def test_performance_summary_generation(self):
        """Test performance summary generation"""
        # Create some test data
        for i in range(3):
            PerformanceMetric.objects.create(
                metric_type='call_bot_session',
                metric_name='connection_time',
                value=2.0 + i,
                status='success'
            )
        
        PerformanceMetric.objects.create(
            metric_type='call_bot_session',
            metric_name='connection_time',
            value=5.0,
            status='error'
        )
        
        # Generate summary
        summary = performance_monitor.get_performance_summary(hours=1)
        
        # Verify summary content
        self.assertIn('total_metrics', summary)
        self.assertIn('error_rate', summary)
        self.assertIn('call_bot_performance', summary)
        
        self.assertEqual(summary['total_metrics'], 4)
        self.assertEqual(summary['error_rate'], 25.0)  # 1 error out of 4 total
        
        call_bot_perf = summary['call_bot_performance']
        self.assertEqual(call_bot_perf['total_sessions'], 4)
        self.assertAlmostEqual(call_bot_perf['avg_connection_time'], 3.25, places=2)