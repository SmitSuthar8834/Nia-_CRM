"""
Management command to perform comprehensive system health checks
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta
import logging
import time
import requests
from apps.analytics.models import SystemHealthMetric

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Perform comprehensive system health checks and record metrics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--component',
            type=str,
            choices=['database', 'cache', 'ai', 'crm', 'calendar', 'all'],
            default='all',
            help='Specific component to check (default: all)'
        )
        parser.add_argument(
            '--record-metrics',
            action='store_true',
            help='Record health metrics to database'
        )
        parser.add_argument(
            '--alert-threshold',
            type=float,
            default=5.0,
            help='Response time threshold for alerts in seconds (default: 5.0)'
        )
    
    def handle(self, *args, **options):
        component = options['component']
        record_metrics = options['record_metrics']
        alert_threshold = options['alert_threshold']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting system health check at {timezone.now()}'
            )
        )
        
        health_results = {}
        
        if component in ['database', 'all']:
            health_results['database'] = self.check_database_health()
        
        if component in ['cache', 'all']:
            health_results['cache'] = self.check_cache_health()
        
        if component in ['ai', 'all']:
            health_results['ai'] = self.check_ai_engine_health()
        
        if component in ['crm', 'all']:
            health_results['crm'] = self.check_crm_integration_health()
        
        if component in ['calendar', 'all']:
            health_results['calendar'] = self.check_calendar_integration_health()
        
        # Display results
        self.display_health_results(health_results, alert_threshold)
        
        # Record metrics if requested
        if record_metrics:
            self.record_health_metrics(health_results)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'System health check completed at {timezone.now()}'
            )
        )
    
    def check_database_health(self):
        """Check database connectivity and performance"""
        self.stdout.write('Checking database health...')
        
        try:
            start_time = time.time()
            
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Test query performance
            cursor.execute("""
                SELECT COUNT(*) FROM django_migrations
            """)
            migration_count = cursor.fetchone()[0]
            
            response_time = time.time() - start_time
            
            # Check database size (PostgreSQL specific)
            try:
                cursor.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                db_size = cursor.fetchone()[0]
            except:
                db_size = 'Unknown'
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'migration_count': migration_count,
                'database_size': db_size,
                'details': f'Database responsive in {response_time:.3f}s'
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': None,
                'error': str(e),
                'details': f'Database connection failed: {str(e)}'
            }
    
    def check_cache_health(self):
        """Check cache system health"""
        self.stdout.write('Checking cache health...')
        
        try:
            start_time = time.time()
            
            # Test cache write/read
            test_key = f'health_check_{int(time.time())}'
            test_value = 'health_check_value'
            
            cache.set(test_key, test_value, 60)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            response_time = time.time() - start_time
            
            if retrieved_value == test_value:
                return {
                    'status': 'healthy',
                    'response_time': response_time,
                    'details': f'Cache responsive in {response_time:.3f}s'
                }
            else:
                return {
                    'status': 'warning',
                    'response_time': response_time,
                    'details': 'Cache read/write test failed'
                }
                
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': None,
                'error': str(e),
                'details': f'Cache system failed: {str(e)}'
            }
    
    def check_ai_engine_health(self):
        """Check AI engine connectivity"""
        self.stdout.write('Checking AI engine health...')
        
        try:
            from apps.ai_engine.gemini_client import GeminiClient
            
            start_time = time.time()
            
            # Test AI client initialization
            client = GeminiClient()
            
            # Simple test prompt
            test_response = client.generate_response(
                "Respond with 'OK' if you can process this message.",
                max_tokens=10
            )
            
            response_time = time.time() - start_time
            
            if 'OK' in test_response.get('content', '').upper():
                return {
                    'status': 'healthy',
                    'response_time': response_time,
                    'details': f'AI engine responsive in {response_time:.3f}s'
                }
            else:
                return {
                    'status': 'warning',
                    'response_time': response_time,
                    'details': 'AI engine responded but test failed'
                }
                
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': None,
                'error': str(e),
                'details': f'AI engine failed: {str(e)}'
            }
    
    def check_crm_integration_health(self):
        """Check CRM integration health"""
        self.stdout.write('Checking CRM integration health...')
        
        try:
            from apps.crm_sync.adapters import CreatioAdapter
            
            start_time = time.time()
            
            # Test CRM adapter initialization
            adapter = CreatioAdapter()
            
            # Test authentication (without making actual API calls)
            auth_status = adapter.test_connection()
            
            response_time = time.time() - start_time
            
            if auth_status:
                return {
                    'status': 'healthy',
                    'response_time': response_time,
                    'details': f'CRM integration healthy in {response_time:.3f}s'
                }
            else:
                return {
                    'status': 'warning',
                    'response_time': response_time,
                    'details': 'CRM authentication test failed'
                }
                
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': None,
                'error': str(e),
                'details': f'CRM integration failed: {str(e)}'
            }
    
    def check_calendar_integration_health(self):
        """Check calendar integration health"""
        self.stdout.write('Checking calendar integration health...')
        
        try:
            from apps.calendar_integration.services import CalendarIntegrationHub
            
            start_time = time.time()
            
            # Test calendar service initialization
            hub = CalendarIntegrationHub()
            
            # Check active integrations
            active_integrations = hub.get_active_integrations_count()
            
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'active_integrations': active_integrations,
                'details': f'Calendar integration healthy in {response_time:.3f}s, {active_integrations} active'
            }
            
        except Exception as e:
            return {
                'status': 'critical',
                'response_time': None,
                'error': str(e),
                'details': f'Calendar integration failed: {str(e)}'
            }
    
    def display_health_results(self, results, alert_threshold):
        """Display health check results"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('SYSTEM HEALTH CHECK RESULTS')
        self.stdout.write('='*60)
        
        overall_status = 'healthy'
        
        for component, result in results.items():
            status = result['status']
            response_time = result.get('response_time')
            details = result.get('details', '')
            
            # Determine color based on status
            if status == 'healthy':
                color = self.style.SUCCESS
            elif status == 'warning':
                color = self.style.WARNING
                if overall_status == 'healthy':
                    overall_status = 'warning'
            else:
                color = self.style.ERROR
                overall_status = 'critical'
            
            # Check response time threshold
            if response_time and response_time > alert_threshold:
                color = self.style.WARNING
                details += f' (SLOW: {response_time:.3f}s > {alert_threshold}s)'
                if overall_status == 'healthy':
                    overall_status = 'warning'
            
            self.stdout.write(
                f'{component.upper()}: {color(status.upper())} - {details}'
            )
        
        self.stdout.write('='*60)
        
        if overall_status == 'healthy':
            self.stdout.write(self.style.SUCCESS('OVERALL STATUS: HEALTHY'))
        elif overall_status == 'warning':
            self.stdout.write(self.style.WARNING('OVERALL STATUS: WARNING'))
        else:
            self.stdout.write(self.style.ERROR('OVERALL STATUS: CRITICAL'))
    
    def record_health_metrics(self, results):
        """Record health metrics to database"""
        self.stdout.write('Recording health metrics...')
        
        try:
            for component, result in results.items():
                SystemHealthMetric.objects.create(
                    component=component,
                    health_type='response_time',
                    value=result.get('response_time', 0) * 1000,  # Convert to ms
                    unit='ms',
                    status=result['status'],
                    details=result.get('details', ''),
                    measured_at=timezone.now()
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Recorded {len(results)} health metrics'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to record metrics: {str(e)}')
            )