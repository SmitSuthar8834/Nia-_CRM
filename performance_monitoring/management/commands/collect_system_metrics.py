"""
Management command to collect system performance metrics
"""
import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from performance_monitoring.services import performance_monitor, alerting_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Collect system performance metrics and check for alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=60,
            help='Collection interval in seconds (default: 60)'
        )
        
        parser.add_argument(
            '--duration',
            type=int,
            default=0,
            help='Duration to run in seconds (0 = run indefinitely)'
        )
        
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run once and exit'
        )
    
    def handle(self, *args, **options):
        interval = options['interval']
        duration = options['duration']
        run_once = options['once']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting system metrics collection (interval: {interval}s)'
            )
        )
        
        start_time = time.time()
        
        try:
            while True:
                collection_start = time.time()
                
                # Collect system metrics
                try:
                    performance_monitor.collect_system_metrics()
                    self.stdout.write(
                        f'[{timezone.now()}] Collected system metrics'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error collecting system metrics: {str(e)}'
                        )
                    )
                
                # Track concurrent calls
                try:
                    performance_monitor.track_concurrent_calls()
                    self.stdout.write(
                        f'[{timezone.now()}] Tracked concurrent calls'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error tracking concurrent calls: {str(e)}'
                        )
                    )
                
                # Check system health and create alerts
                try:
                    alerting_service.check_system_health()
                    self.stdout.write(
                        f'[{timezone.now()}] Checked system health'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error checking system health: {str(e)}'
                        )
                    )
                
                # Exit if running once
                if run_once:
                    break
                
                # Check duration limit
                if duration > 0 and (time.time() - start_time) >= duration:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Completed {duration}s collection period'
                        )
                    )
                    break
                
                # Calculate sleep time
                collection_time = time.time() - collection_start
                sleep_time = max(0, interval - collection_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('Metrics collection interrupted by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {str(e)}')
            )
            raise
        
        self.stdout.write(
            self.style.SUCCESS('System metrics collection completed')
        )