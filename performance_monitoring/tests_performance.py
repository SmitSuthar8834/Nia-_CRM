"""
Performance tests for concurrent call handling and system monitoring
"""
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.test.utils import override_settings
from django.db import transaction

from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, ConcurrentCallMetrics
)
from .services import PerformanceMonitoringService, AlertingService
from meetings.models import Meeting, CallBotSession, DraftSummary
from leads.models import Lead


class ConcurrentCallPerformanceTest(TransactionTestCase):
    """
    Test concurrent call handling performance and capacity
    """
    
    def setUp(self):
        self.performance_service = PerformanceMonitoringService()
        self.alerting_service = AlertingService()
        
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_001",
            name="Test Lead",
            email="test@example.com",
            company="Test Company"
        )
    
    def create_test_meeting(self, meeting_id: str):
        """Create a test meeting with call bot session"""
        meeting = Meeting.objects.create(
            calendar_event_id=f"meeting_{meeting_id}",
            lead=self.lead,
            title=f"Test Meeting {meeting_id}",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        
        call_bot_session = CallBotSession.objects.create(
            meeting=meeting,
            bot_session_id=f"bot_session_{meeting_id}",
            platform="meet",
            join_time=timezone.now(),
            connection_status="connected"
        )
        
        return meeting, call_bot_session
    
    def simulate_call_bot_session(self, session_id: str, duration: float = 2.0):
        """Simulate a call bot session with performance tracking"""
        try:
            # Simulate connection time
            connection_start = time.time()
            time.sleep(0.1)  # Simulate connection delay
            connection_time = time.time() - connection_start
            
            # Create meeting and session
            meeting, call_bot_session = self.create_test_meeting(session_id)
            
            # Track performance
            performance = self.performance_service.track_call_bot_performance(
                call_bot_session=call_bot_session,
                connection_time=connection_time,
                connection_success=True
            )
            
            # Simulate transcription processing
            processing_start = time.time()
            time.sleep(duration)  # Simulate processing time
            processing_time = time.time() - processing_start
            
            # Update audio metrics
            self.performance_service.update_call_bot_audio_metrics(
                call_bot_session=call_bot_session,
                audio_quality_score=0.95,
                audio_dropouts=0,
                audio_latency=50.0
            )
            
            # Track AI processing
            self.performance_service.track_ai_processing(
                operation_type='transcription',
                operation_id=f"transcription_{session_id}",
                processing_time=processing_time,
                input_size=1000,
                output_size=800,
                confidence_score=0.92
            )
            
            # End session
            call_bot_session.connection_status = 'disconnected'
            call_bot_session.leave_time = timezone.now()
            call_bot_session.save()
            
            return {
                'session_id': session_id,
                'connection_time': connection_time,
                'processing_time': processing_time,
                'success': True
            }
            
        except Exception as e:
            return {
                'session_id': session_id,
                'error': str(e),
                'success': False
            }
    
    def test_concurrent_call_capacity(self):
        """Test system capacity for handling 50 concurrent calls"""
        num_concurrent_calls = 50
        session_duration = 1.0  # Reduced for faster testing
        
        start_time = time.time()
        
        # Use ThreadPoolExecutor to simulate concurrent calls
        with ThreadPoolExecutor(max_workers=num_concurrent_calls) as executor:
            # Submit all call simulations
            futures = [
                executor.submit(self.simulate_call_bot_session, f"session_{i}", session_duration)
                for i in range(num_concurrent_calls)
            ]
            
            # Collect results
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        total_time = time.time() - start_time
        
        # Analyze results
        successful_calls = [r for r in results if r['success']]
        failed_calls = [r for r in results if not r['success']]
        
        avg_connection_time = sum(r['connection_time'] for r in successful_calls) / len(successful_calls)
        avg_processing_time = sum(r['processing_time'] for r in successful_calls) / len(successful_calls)
        
        # Assertions
        self.assertEqual(len(successful_calls), num_concurrent_calls, 
                        f"Expected {num_concurrent_calls} successful calls, got {len(successful_calls)}")
        self.assertEqual(len(failed_calls), 0, f"Unexpected failures: {failed_calls}")
        self.assertLess(avg_connection_time, 1.0, "Average connection time should be under 1 second")
        self.assertLess(total_time, 10.0, "Total test time should be under 10 seconds")
        
        # Verify performance metrics were recorded
        call_bot_metrics = PerformanceMetric.objects.filter(
            metric_type='call_bot_session',
            metric_name='connection_time'
        ).count()
        self.assertEqual(call_bot_metrics, num_concurrent_calls)
        
        ai_metrics = PerformanceMetric.objects.filter(
            metric_type='ai_processing'
        ).count()
        self.assertEqual(ai_metrics, num_concurrent_calls)
        
        print(f"\nConcurrent Call Performance Test Results:")
        print(f"- Concurrent calls: {num_concurrent_calls}")
        print(f"- Successful calls: {len(successful_calls)}")
        print(f"- Failed calls: {len(failed_calls)}")
        print(f"- Total time: {total_time:.2f}s")
        print(f"- Average connection time: {avg_connection_time:.3f}s")
        print(f"- Average processing time: {avg_processing_time:.3f}s")
    
    def test_performance_monitoring_under_load(self):
        """Test performance monitoring system under high load"""
        num_operations = 100
        
        start_time = time.time()
        
        # Simulate high-frequency metric recording
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            for i in range(num_operations):
                future = executor.submit(
                    self.performance_service.record_metric,
                    metric_type='test_load',
                    metric_name=f'operation_{i % 10}',
                    value=float(i),
                    unit='count',
                    metadata={'test_id': i}
                )
                futures.append(future)
            
            # Wait for all operations to complete
            for future in as_completed(futures):
                result = future.result()
                self.assertIsNotNone(result)
        
        total_time = time.time() - start_time
        
        # Verify all metrics were recorded
        recorded_metrics = PerformanceMetric.objects.filter(
            metric_type='test_load'
        ).count()
        
        self.assertEqual(recorded_metrics, num_operations)
        self.assertLess(total_time, 5.0, "High-load metric recording should complete quickly")
        
        print(f"\nPerformance Monitoring Load Test Results:")
        print(f"- Operations: {num_operations}")
        print(f"- Total time: {total_time:.2f}s")
        print(f"- Operations per second: {num_operations / total_time:.1f}")
    
    def test_concurrent_call_metrics_tracking(self):
        """Test concurrent call metrics collection"""
        # Create multiple active call bot sessions
        active_sessions = []
        for i in range(10):
            meeting, call_bot_session = self.create_test_meeting(f"concurrent_{i}")
            call_bot_session.connection_status = 'connected'
            call_bot_session.save()
            active_sessions.append(call_bot_session)
        
        # Track concurrent call metrics
        metrics = self.performance_service.track_concurrent_calls()
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.active_calls, 10)
        self.assertGreaterEqual(metrics.available_memory, 0)
        
        # Verify metric was recorded
        concurrent_metric = PerformanceMetric.objects.filter(
            metric_type='system_resource',
            metric_name='concurrent_calls'
        ).first()
        
        self.assertIsNotNone(concurrent_metric)
        self.assertEqual(concurrent_metric.value, 10)
    
    def test_ai_processing_performance_tracking(self):
        """Test AI processing performance under concurrent load"""
        num_operations = 20
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            
            for i in range(num_operations):
                future = executor.submit(
                    self.performance_service.track_ai_processing,
                    operation_type='summary_generation',
                    operation_id=f'summary_{i}',
                    processing_time=0.5 + (i * 0.1),  # Varying processing times
                    input_size=1000 + (i * 100),
                    output_size=500 + (i * 50),
                    confidence_score=0.8 + (i * 0.01),
                    tokens_used=100 + (i * 10)
                )
                futures.append(future)
            
            # Wait for completion
            results = [future.result() for future in as_completed(futures)]
        
        # Verify all operations were tracked
        successful_operations = [r for r in results if r is not None]
        self.assertEqual(len(successful_operations), num_operations)
        
        # Check database records
        ai_performance_records = AIProcessingPerformance.objects.filter(
            operation_type='summary_generation'
        ).count()
        self.assertEqual(ai_performance_records, num_operations)
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_system_resource_monitoring(self, mock_disk, mock_memory, mock_cpu):
        """Test system resource monitoring and alerting"""
        # Mock high resource usage
        mock_cpu.return_value = 95.0
        mock_memory.return_value = MagicMock(percent=90.0, available=1024*1024*1024)
        mock_disk.return_value = MagicMock(percent=85.0, free=10*1024*1024*1024)
        
        # Collect system metrics
        self.performance_service.collect_system_metrics()
        
        # Check system health (should create alerts)
        self.alerting_service.check_system_health()
        
        # Verify metrics were recorded
        cpu_metric = PerformanceMetric.objects.filter(
            metric_type='system_resource',
            metric_name='cpu_usage'
        ).first()
        self.assertIsNotNone(cpu_metric)
        self.assertEqual(cpu_metric.value, 95.0)
        
        memory_metric = PerformanceMetric.objects.filter(
            metric_type='system_resource',
            metric_name='memory_usage'
        ).first()
        self.assertIsNotNone(memory_metric)
        self.assertEqual(memory_metric.value, 90.0)
        
        # Verify alerts were created
        cpu_alert = SystemAlert.objects.filter(
            alert_type='resource_exhaustion',
            component='cpu'
        ).first()
        self.assertIsNotNone(cpu_alert)
        self.assertEqual(cpu_alert.severity, 'critical')
        
        memory_alert = SystemAlert.objects.filter(
            alert_type='resource_exhaustion',
            component='memory'
        ).first()
        self.assertIsNotNone(memory_alert)
        self.assertEqual(memory_alert.severity, 'error')


class PerformanceMetricsTest(TestCase):
    """
    Test performance metrics collection and analysis
    """
    
    def setUp(self):
        self.performance_service = PerformanceMonitoringService()
    
    def test_performance_context_manager(self):
        """Test performance tracking context manager"""
        with self.performance_service.track_performance(
            metric_type='test',
            metric_name='context_manager_test',
            metadata={'test': True}
        ):
            time.sleep(0.1)  # Simulate work
        
        # Verify metric was recorded
        metric = PerformanceMetric.objects.filter(
            metric_type='test',
            metric_name='context_manager_test'
        ).first()
        
        self.assertIsNotNone(metric)
        self.assertGreaterEqual(metric.value, 0.1)
        self.assertEqual(metric.status, 'success')
        self.assertEqual(metric.metadata['test'], True)
    
    def test_performance_context_manager_with_error(self):
        """Test performance tracking context manager with error"""
        with self.assertRaises(ValueError):
            with self.performance_service.track_performance(
                metric_type='test',
                metric_name='error_test'
            ):
                raise ValueError("Test error")
        
        # Verify error metric was recorded
        metric = PerformanceMetric.objects.filter(
            metric_type='test',
            metric_name='error_test'
        ).first()
        
        self.assertIsNotNone(metric)
        self.assertEqual(metric.status, 'error')
        self.assertIn("Test error", metric.error_message)
    
    def test_performance_summary_generation(self):
        """Test performance summary generation"""
        # Create test metrics
        for i in range(10):
            self.performance_service.record_metric(
                metric_type='call_bot_session',
                metric_name='connection_time',
                value=1.0 + (i * 0.1),
                status='success' if i < 8 else 'error'
            )
        
        for i in range(5):
            self.performance_service.track_ai_processing(
                operation_type='transcription',
                operation_id=f'test_{i}',
                processing_time=2.0 + (i * 0.5),
                input_size=1000,
                output_size=800,
                confidence_score=0.9
            )
        
        # Generate summary
        summary = self.performance_service.get_performance_summary(hours=24)
        
        self.assertIsInstance(summary, dict)
        self.assertEqual(summary['period_hours'], 24)
        self.assertGreater(summary['total_metrics'], 0)
        self.assertGreaterEqual(summary['error_rate'], 0)
        self.assertIn('call_bot_performance', summary)
        self.assertIn('ai_performance', summary)
    
    def test_call_bot_performance_scoring(self):
        """Test call bot performance overall scoring"""
        # Create test meeting and session
        lead = Lead.objects.create(
            crm_id="TEST_LEAD_SCORE",
            name="Test Lead",
            email="test@example.com"
        )
        
        meeting = Meeting.objects.create(
            calendar_event_id="test_meeting_score",
            lead=lead,
            title="Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        
        call_bot_session = CallBotSession.objects.create(
            meeting=meeting,
            bot_session_id="test_bot_score",
            platform="meet",
            join_time=timezone.now(),
            connection_status="connected"
        )
        
        # Create performance record
        performance = CallBotPerformance.objects.create(
            call_bot_session=call_bot_session,
            connection_time=2.0,
            connection_success=True,
            audio_quality_score=0.9,
            transcription_accuracy=0.95,
            error_count=1
        )
        
        # Test overall score calculation
        score = performance.overall_score
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1)
        
        # Test with poor performance
        performance.connection_time = 25.0
        performance.audio_quality_score = 0.5
        performance.transcription_accuracy = 0.6
        performance.error_count = 5
        performance.save()
        
        poor_score = performance.overall_score
        self.assertLess(poor_score, score)


class AlertingSystemTest(TestCase):
    """
    Test alerting system functionality
    """
    
    def setUp(self):
        self.alerting_service = AlertingService()
        self.performance_service = PerformanceMonitoringService()
    
    def test_alert_creation(self):
        """Test basic alert creation"""
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
        self.assertTrue(alert.is_active)
        self.assertFalse(alert.acknowledged)
        self.assertFalse(alert.resolved)
    
    def test_alert_acknowledgment_and_resolution(self):
        """Test alert acknowledgment and resolution workflow"""
        alert = self.alerting_service.create_alert(
            alert_type='system_failure',
            severity='critical',
            title='Critical Test Alert',
            description='Critical test alert description'
        )
        
        # Acknowledge alert
        alert.acknowledge('test_user@example.com')
        alert.refresh_from_db()
        
        self.assertTrue(alert.acknowledged)
        self.assertEqual(alert.acknowledged_by, 'test_user@example.com')
        self.assertIsNotNone(alert.acknowledged_at)
        
        # Resolve alert
        alert.resolve('test_user@example.com', 'Issue resolved by testing')
        alert.refresh_from_db()
        
        self.assertTrue(alert.resolved)
        self.assertEqual(alert.resolved_by, 'test_user@example.com')
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(alert.resolution_notes, 'Issue resolved by testing')
        self.assertFalse(alert.is_active)
    
    @patch('performance_monitoring.services.CallBotSession.objects.filter')
    def test_concurrent_capacity_alerting(self, mock_filter):
        """Test alerting for high concurrent call load"""
        # Mock 45 active call sessions
        mock_filter.return_value.count.return_value = 45
        
        self.alerting_service._check_concurrent_capacity()
        
        # Check if alert was created
        alert = SystemAlert.objects.filter(
            alert_type='resource_exhaustion',
            component='call_bot'
        ).first()
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'error')
        self.assertIn('45 active calls', alert.title)
    
    def test_error_rate_alerting(self):
        """Test alerting for high error rates"""
        # Create metrics with high error rate
        for i in range(20):
            status = 'error' if i < 15 else 'success'  # 75% error rate
            self.performance_service.record_metric(
                metric_type='test',
                metric_name='error_rate_test',
                value=1.0,
                status=status
            )
        
        self.alerting_service._check_error_rates()
        
        # Check if alert was created
        alert = SystemAlert.objects.filter(
            alert_type='high_error_rate'
        ).first()
        
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'critical')
        self.assertIn('75.0%', alert.title)


class LoadTestRunner:
    """
    Utility class for running load tests
    """
    
    @staticmethod
    def run_concurrent_call_load_test(num_calls: int = 50, duration: float = 30.0):
        """
        Run a load test with specified number of concurrent calls
        
        Args:
            num_calls: Number of concurrent calls to simulate
            duration: Duration of each call in seconds
        """
        print(f"\nStarting load test: {num_calls} concurrent calls for {duration}s each")
        
        performance_service = PerformanceMonitoringService()
        start_time = time.time()
        
        def simulate_call(call_id):
            try:
                # Simulate call bot connection
                connection_start = time.time()
                time.sleep(0.1)  # Connection delay
                connection_time = time.time() - connection_start
                
                # Simulate processing
                time.sleep(duration)
                
                # Record metrics
                performance_service.record_metric(
                    metric_type='load_test',
                    metric_name='call_duration',
                    value=duration,
                    metadata={'call_id': call_id}
                )
                
                return {'call_id': call_id, 'success': True, 'duration': duration}
                
            except Exception as e:
                return {'call_id': call_id, 'success': False, 'error': str(e)}
        
        # Run concurrent calls
        with ThreadPoolExecutor(max_workers=num_calls) as executor:
            futures = [executor.submit(simulate_call, i) for i in range(num_calls)]
            results = [future.result() for future in as_completed(futures)]
        
        total_time = time.time() - start_time
        successful_calls = [r for r in results if r['success']]
        failed_calls = [r for r in results if not r['success']]
        
        print(f"Load test completed in {total_time:.2f}s")
        print(f"Successful calls: {len(successful_calls)}/{num_calls}")
        print(f"Failed calls: {len(failed_calls)}")
        print(f"Success rate: {len(successful_calls)/num_calls*100:.1f}%")
        
        return {
            'total_time': total_time,
            'successful_calls': len(successful_calls),
            'failed_calls': len(failed_calls),
            'success_rate': len(successful_calls) / num_calls * 100
        }


if __name__ == '__main__':
    # Run load test if executed directly
    LoadTestRunner.run_concurrent_call_load_test(50, 2.0)