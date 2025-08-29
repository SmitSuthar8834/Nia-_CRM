"""
Demo script to show performance monitoring functionality
"""
import os
import sys
import django
import time
from datetime import timedelta

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelligent_meeting_workflow.settings')
django.setup()

from django.utils import timezone
from performance_monitoring.services import performance_monitor, alerting_service
from performance_monitoring.models import PerformanceMetric, SystemAlert, PerformanceThreshold
from meetings.models import Meeting, CallBotSession


def demo_performance_monitoring():
    """Demonstrate performance monitoring features"""
    print("=" * 60)
    print("NIA PERFORMANCE MONITORING DEMO")
    print("=" * 60)
    
    # 1. Create a test meeting and call bot session
    print("\n1. Creating test meeting and call bot session...")
    meeting = Meeting.objects.create(
        calendar_event_id='demo-meeting-123',
        title='Performance Demo Meeting',
        start_time=timezone.now(),
        end_time=timezone.now() + timedelta(hours=1)
    )
    
    call_bot_session = CallBotSession.objects.create(
        meeting=meeting,
        bot_session_id='demo-bot-123',
        platform='meet',
        join_time=timezone.now(),
        connection_status='connected'
    )
    print(f"✓ Created meeting: {meeting.title}")
    print(f"✓ Created call bot session: {call_bot_session.bot_session_id}")
    
    # 2. Track call bot performance
    print("\n2. Tracking call bot performance...")
    performance = performance_monitor.track_call_bot_performance(
        call_bot_session=call_bot_session,
        connection_time=2.5,
        connection_attempts=1,
        connection_success=True
    )
    print(f"✓ Tracked connection time: {performance.connection_time}s")
    print(f"✓ Connection success: {performance.connection_success}")
    
    # 3. Update audio metrics
    print("\n3. Updating audio quality metrics...")
    performance_monitor.update_call_bot_audio_metrics(
        call_bot_session=call_bot_session,
        audio_quality_score=0.92,
        audio_dropouts=2,
        audio_latency=150.0
    )
    performance.refresh_from_db()
    print(f"✓ Audio quality score: {performance.audio_quality_score}")
    print(f"✓ Audio dropouts: {performance.audio_dropouts}")
    print(f"✓ Audio latency: {performance.audio_latency}ms")
    
    # 4. Track AI processing
    print("\n4. Tracking AI processing performance...")
    ai_performance = performance_monitor.track_ai_processing(
        operation_type='transcription',
        operation_id='demo-transcription-123',
        processing_time=4.2,
        input_size=1500,
        output_size=1200,
        confidence_score=0.88,
        tokens_used=200
    )
    print(f"✓ AI processing time: {ai_performance.processing_time}s")
    print(f"✓ Confidence score: {ai_performance.confidence_score}")
    print(f"✓ Processing rate: {ai_performance.processing_rate:.1f} chars/sec")
    
    # 5. Use performance tracking context manager
    print("\n5. Using performance tracking context manager...")
    with performance_monitor.track_performance('demo', 'database_operation'):
        # Simulate some work
        time.sleep(0.1)
        # Create another meeting
        Meeting.objects.create(
            calendar_event_id='demo-meeting-456',
            title='Context Manager Demo',
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
    print("✓ Tracked database operation performance")
    
    # 6. Record custom metrics
    print("\n6. Recording custom metrics...")
    performance_monitor.record_metric(
        metric_type='custom',
        metric_name='demo_metric',
        value=15.7,
        unit='milliseconds',
        status='success',
        metadata={'demo': True, 'version': '1.0'}
    )
    print("✓ Recorded custom metric")
    
    # 7. Create performance threshold
    print("\n7. Creating performance threshold...")
    threshold = PerformanceThreshold.objects.create(
        metric_type='call_bot_session',
        metric_name='connection_time',
        warning_threshold=5.0,
        error_threshold=10.0,
        critical_threshold=15.0,
        comparison_operator='>',
        is_active=True
    )
    print(f"✓ Created threshold: {threshold.metric_name}")
    
    # 8. Trigger threshold violation
    print("\n8. Triggering threshold violation...")
    performance_monitor.record_metric(
        metric_type='call_bot_session',
        metric_name='connection_time',
        value=12.0,  # Exceeds error threshold
        status='success'
    )
    print("✓ Recorded metric that exceeds threshold")
    
    # 9. Check for alerts
    print("\n9. Checking system alerts...")
    alerts = SystemAlert.objects.filter(is_active=True)
    print(f"✓ Found {alerts.count()} active alerts")
    for alert in alerts:
        print(f"  - {alert.severity.upper()}: {alert.title}")
    
    # 10. Generate performance summary
    print("\n10. Generating performance summary...")
    summary = performance_monitor.get_performance_summary(hours=1)
    print(f"✓ Total metrics collected: {summary.get('total_metrics', 0)}")
    print(f"✓ Error rate: {summary.get('error_rate', 0)}%")
    print(f"✓ Active alerts: {summary.get('active_alerts', 0)}")
    
    call_bot_perf = summary.get('call_bot_performance', {})
    if call_bot_perf.get('total_sessions'):
        print(f"✓ Call bot sessions: {call_bot_perf['total_sessions']}")
        if call_bot_perf.get('avg_connection_time'):
            print(f"✓ Avg connection time: {call_bot_perf['avg_connection_time']:.2f}s")
    
    ai_perf = summary.get('ai_performance', {})
    if ai_perf.get('total_operations'):
        print(f"✓ AI operations: {ai_perf['total_operations']}")
        if ai_perf.get('avg_processing_time'):
            print(f"✓ Avg AI processing time: {ai_perf['avg_processing_time']:.2f}s")
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    # Show some statistics
    print(f"\nDatabase Records Created:")
    print(f"- Performance Metrics: {PerformanceMetric.objects.count()}")
    print(f"- System Alerts: {SystemAlert.objects.count()}")
    print(f"- Performance Thresholds: {PerformanceThreshold.objects.count()}")
    print(f"- Meetings: {Meeting.objects.count()}")
    print(f"- Call Bot Sessions: {CallBotSession.objects.count()}")


if __name__ == '__main__':
    demo_performance_monitoring()