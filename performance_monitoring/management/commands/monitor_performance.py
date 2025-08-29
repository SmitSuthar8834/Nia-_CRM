"""
Management command for continuous performance monitoring
"""
import time
import signal
import sys
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from performance_monitoring.services import PerformanceMonitoringService, AlertingService


class Command(BaseCommand):
    help = 'Run continuous performance monitoring and alerting'
    
    def __init__(self):
        super().__init__()
        self.performance_service = PerformanceMonitoringService()
        self.alerting_service = AlertingService()
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Monitoring interval in seconds (default: 60)'
        )
        parser.add_argument(
            '--system-metrics',
            action='store_true',
            help='Collect system resource metrics'
        )
        parser.add_argument(
            '--concurrent-calls',
            action='store_true',
            help='Track concurrent call metrics'
        )
        parser.add_argument(
            '--health-checks',
            action='store_true',
            help='Perform system health checks'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Enable all monitoring features'
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Run as daemon (continuous monitoring)'
        )
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.stdout.write(
            self.style.WARNING(f'Received signal {signum}, shutting down gracefully...')
        )
        self.running = False
    
    def handle(self, *args, **options):
        interval = options['interval']
        collect_system_metrics = options['system_metrics'] or options['all']
        track_concurrent_calls = options['concurrent_calls'] or options['all']
        perform_health_checks = options['health_checks'] or options['all']
        daemon_mode = options['daemon']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting performance monitoring (interval: {interval}s)')
        )
        
        if collect_system_metrics:
            self.stdout.write('- System resource metrics: ENABLED')
        if track_concurrent_calls:
            self.stdout.write('- Concurrent call tracking: ENABLED')
        if perform_health_checks:
            self.stdout.write('- Health checks: ENABLED')
        
        try:
            if daemon_mode:
                self.run_daemon_mode(
                    interval, collect_system_metrics, 
                    track_concurrent_calls, perform_health_checks
                )
            else:
                self.run_single_cycle(
                    collect_system_metrics, track_concurrent_calls, perform_health_checks
                )
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Monitoring stopped by user'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Monitoring error: {str(e)}')
            )
            raise
    
    def run_daemon_mode(self, interval, system_metrics, concurrent_calls, health_checks):
        """Run continuous monitoring in daemon mode"""
        cycle_count = 0
        
        while self.running:
            try:
                cycle_start = time.time()
                cycle_count += 1
                
                self.stdout.write(
                    f'Monitoring cycle {cycle_count} at {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
                )
                
                self.run_single_cycle(system_metrics, concurrent_calls, health_checks)
                
                cycle_duration = time.time() - cycle_start
                self.stdout.write(f'Cycle completed in {cycle_duration:.2f}s')
                
                # Sleep for remaining interval time
                sleep_time = max(0, interval - cycle_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error in monitoring cycle {cycle_count}: {str(e)}')
                )
                time.sleep(interval)  # Wait before retrying
        
        self.stdout.write(self.style.SUCCESS('Performance monitoring stopped'))
    
    def run_single_cycle(self, system_metrics, concurrent_calls, health_checks):
        """Run a single monitoring cycle"""
        try:
            if system_metrics:
                self.stdout.write('Collecting system metrics...')
                self.performance_service.collect_system_metrics()
            
            if concurrent_calls:
                self.stdout.write('Tracking concurrent calls...')
                metrics = self.performance_service.track_concurrent_calls()
                if metrics:
                    self.stdout.write(f'Active calls: {metrics.active_calls}')
            
            if health_checks:
                self.stdout.write('Performing health checks...')
                self.alerting_service.check_system_health()
                
                # Report active alerts
                from performance_monitoring.models import SystemAlert
                active_alerts = SystemAlert.objects.filter(is_active=True).count()
                if active_alerts > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Active alerts: {active_alerts}')
                    )
                else:
                    self.stdout.write('No active alerts')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error in monitoring cycle: {str(e)}')
            )
            raise
    
    def get_monitoring_summary(self):
        """Get current monitoring summary"""
        try:
            summary = self.performance_service.get_performance_summary(hours=1)
            
            self.stdout.write('\n=== Performance Summary (Last Hour) ===')
            self.stdout.write(f'Total metrics: {summary.get("total_metrics", 0)}')
            self.stdout.write(f'Error rate: {summary.get("error_rate", 0)}%')
            self.stdout.write(f'Active alerts: {summary.get("active_alerts", 0)}')
            self.stdout.write(f'Critical alerts: {summary.get("critical_alerts", 0)}')
            self.stdout.write(f'Max concurrent calls: {summary.get("max_concurrent_calls", 0)}')
            
            call_bot_perf = summary.get('call_bot_performance', {})
            if call_bot_perf.get('total_sessions', 0) > 0:
                self.stdout.write(f'Avg connection time: {call_bot_perf.get("avg_connection_time", 0):.2f}s')
            
            ai_perf = summary.get('ai_performance', {})
            if ai_perf.get('total_operations', 0) > 0:
                self.stdout.write(f'Avg AI processing time: {ai_perf.get("avg_processing_time", 0):.2f}s')
            
            self.stdout.write('=' * 40)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error generating summary: {str(e)}')
            )