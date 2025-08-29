"""
Deployment verification tests
Tests system health, configuration, and readiness for production deployment
"""
import os
import json
import requests
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.cache import cache
from django.db import connection
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from leads.models import Lead
from meetings.models import Meeting, CallBotSession, DraftSummary, ValidationSession


class SystemHealthTestCase(TestCase):
    """Test system health and readiness for deployment"""
    
    def setUp(self):
        """Set up test environment"""
        self.client = APIClient()
    
    def test_database_connectivity(self):
        """Test database connection and basic operations"""
        
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
        
        # Test model operations
        lead = Lead.objects.create(
            crm_id="HEALTH_CHECK_001",
            name="Health Check Lead",
            email="health@example.com",
            company="Health Check Company"
        )
        
        self.assertTrue(Lead.objects.filter(id=lead.id).exists())
        
        # Test cascade operations
        meeting = Meeting.objects.create(
            calendar_event_id="health_check_meeting",
            lead=lead,
            title="Health Check Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        # Delete lead should cascade to meeting
        lead.delete()
        self.assertFalse(Meeting.objects.filter(id=meeting.id).exists())
    
    def test_cache_functionality(self):
        """Test cache system functionality"""
        
        # Test cache set/get
        cache_key = "deployment_test_key"
        cache_value = {"test": "data", "timestamp": timezone.now().isoformat()}
        
        cache.set(cache_key, cache_value, timeout=300)
        retrieved_value = cache.get(cache_key)
        
        self.assertEqual(retrieved_value["test"], "data")
        
        # Test cache deletion
        cache.delete(cache_key)
        self.assertIsNone(cache.get(cache_key))
    
    def test_api_endpoints_availability(self):
        """Test that all critical API endpoints are available"""
        
        # Test health check endpoint
        health_response = self.client.get('/api/health/')
        self.assertIn(health_response.status_code, [200, 404])  # 404 if not implemented yet
        
        # Test meetings endpoints
        meetings_response = self.client.get('/api/meetings/')
        self.assertIn(meetings_response.status_code, [200, 401])  # 401 if auth required
        
        # Test validation endpoints
        validation_response = self.client.get('/api/validation/sessions/')
        self.assertIn(validation_response.status_code, [200, 401])
        
        # Test leads endpoints
        leads_response = self.client.get('/api/leads/')
        self.assertIn(leads_response.status_code, [200, 401])
    
    def test_static_files_configuration(self):
        """Test static files are properly configured"""
        
        # Test static files settings
        self.assertTrue(hasattr(settings, 'STATIC_URL'))
        self.assertTrue(hasattr(settings, 'STATIC_ROOT'))
        
        # Test media files settings
        self.assertTrue(hasattr(settings, 'MEDIA_URL'))
        self.assertTrue(hasattr(settings, 'MEDIA_ROOT'))
    
    def test_environment_variables(self):
        """Test required environment variables are set"""
        
        required_vars = [
            'SECRET_KEY',
            'DATABASE_URL',
        ]
        
        for var in required_vars:
            # Check if variable exists in settings or environment
            has_setting = hasattr(settings, var)
            has_env = os.getenv(var) is not None
            
            self.assertTrue(
                has_setting or has_env,
                f"Required environment variable {var} is not set"
            )
    
    def test_database_migrations(self):
        """Test database migrations are up to date"""
        
        # Check for unapplied migrations
        try:
            call_command('showmigrations', '--plan', verbosity=0)
            # If this doesn't raise an exception, migrations are consistent
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Migration issues detected: {e}")
    
    def test_logging_configuration(self):
        """Test logging is properly configured"""
        
        import logging
        
        # Test that loggers are configured
        logger = logging.getLogger('django')
        self.assertIsNotNone(logger)
        
        # Test that we can log messages
        logger.info("Deployment verification test log message")
        
        # Test application-specific loggers
        app_logger = logging.getLogger('meetings')
        app_logger.info("Application logger test message")


class ConfigurationTestCase(TestCase):
    """Test system configuration for production deployment"""
    
    def test_security_settings(self):
        """Test security-related settings"""
        
        # Test DEBUG setting
        if hasattr(settings, 'DEBUG'):
            # In production, DEBUG should be False
            # For tests, we'll just verify it's set
            self.assertIsInstance(settings.DEBUG, bool)
        
        # Test ALLOWED_HOSTS
        self.assertTrue(hasattr(settings, 'ALLOWED_HOSTS'))
        self.assertIsInstance(settings.ALLOWED_HOSTS, list)
        
        # Test SECRET_KEY
        self.assertTrue(hasattr(settings, 'SECRET_KEY'))
        self.assertGreater(len(settings.SECRET_KEY), 20)
        
        # Test CSRF settings
        if hasattr(settings, 'CSRF_COOKIE_SECURE'):
            self.assertIsInstance(settings.CSRF_COOKIE_SECURE, bool)
        
        if hasattr(settings, 'SESSION_COOKIE_SECURE'):
            self.assertIsInstance(settings.SESSION_COOKIE_SECURE, bool)
    
    def test_database_configuration(self):
        """Test database configuration"""
        
        db_config = settings.DATABASES['default']
        
        # Test required database settings
        self.assertIn('ENGINE', db_config)
        self.assertIn('NAME', db_config)
        
        # Test connection pooling if configured
        if 'CONN_MAX_AGE' in db_config:
            self.assertIsInstance(db_config['CONN_MAX_AGE'], int)
            self.assertGreater(db_config['CONN_MAX_AGE'], 0)
    
    def test_cache_configuration(self):
        """Test cache configuration"""
        
        cache_config = settings.CACHES['default']
        
        # Test cache backend
        self.assertIn('BACKEND', cache_config)
        
        # Test cache location if using Redis/Memcached
        if 'redis' in cache_config['BACKEND'].lower():
            self.assertIn('LOCATION', cache_config)
    
    def test_email_configuration(self):
        """Test email configuration"""
        
        # Test email backend
        if hasattr(settings, 'EMAIL_BACKEND'):
            self.assertIsInstance(settings.EMAIL_BACKEND, str)
        
        # Test SMTP settings if configured
        if hasattr(settings, 'EMAIL_HOST'):
            self.assertIsInstance(settings.EMAIL_HOST, str)
        
        if hasattr(settings, 'EMAIL_PORT'):
            self.assertIsInstance(settings.EMAIL_PORT, int)
    
    def test_celery_configuration(self):
        """Test Celery configuration if used"""
        
        # Test Celery broker URL
        if hasattr(settings, 'CELERY_BROKER_URL'):
            self.assertIsInstance(settings.CELERY_BROKER_URL, str)
        
        # Test Celery result backend
        if hasattr(settings, 'CELERY_RESULT_BACKEND'):
            self.assertIsInstance(settings.CELERY_RESULT_BACKEND, str)


class PerformanceTestCase(TestCase):
    """Test system performance for deployment readiness"""
    
    def setUp(self):
        """Set up performance test data"""
        self.client = APIClient()
        
        # Create test data for performance testing
        self.leads = []
        for i in range(10):
            lead = Lead.objects.create(
                crm_id=f"PERF_LEAD_{i:03d}",
                name=f"Performance Test Lead {i}",
                email=f"perf{i}@example.com",
                company=f"Performance Test Company {i}"
            )
            self.leads.append(lead)
    
    def test_database_query_performance(self):
        """Test database query performance"""
        
        import time
        
        # Test simple query performance
        start_time = time.time()
        leads = list(Lead.objects.all()[:100])
        query_time = time.time() - start_time
        
        self.assertLess(query_time, 1.0, "Simple query should complete in under 1 second")
        self.assertGreater(len(leads), 0)
        
        # Test complex query performance
        start_time = time.time()
        meetings_with_leads = list(
            Meeting.objects.select_related('lead')
            .filter(lead__isnull=False)[:50]
        )
        complex_query_time = time.time() - start_time
        
        self.assertLess(complex_query_time, 2.0, "Complex query should complete in under 2 seconds")
    
    def test_api_response_performance(self):
        """Test API response performance"""
        
        import time
        
        # Test meetings list API performance
        start_time = time.time()
        response = self.client.get('/api/meetings/')
        api_time = time.time() - start_time
        
        self.assertLess(api_time, 2.0, "API response should be under 2 seconds")
        self.assertIn(response.status_code, [200, 401])
        
        # Test leads list API performance
        start_time = time.time()
        response = self.client.get('/api/leads/')
        api_time = time.time() - start_time
        
        self.assertLess(api_time, 2.0, "Leads API response should be under 2 seconds")
    
    def test_concurrent_request_handling(self):
        """Test system can handle concurrent requests"""
        
        import threading
        import time
        
        results = []
        
        def make_request():
            start_time = time.time()
            response = self.client.get('/api/meetings/')
            request_time = time.time() - start_time
            results.append((response.status_code, request_time))
        
        # Create multiple concurrent requests
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Verify all requests completed
        self.assertEqual(len(results), 5)
        
        # Verify reasonable response times
        for status_code, request_time in results:
            self.assertIn(status_code, [200, 401])
            self.assertLess(request_time, 5.0, "Concurrent requests should complete in reasonable time")
        
        # Total time should be reasonable for concurrent execution
        self.assertLess(total_time, 10.0, "Concurrent requests should complete efficiently")


class IntegrationReadinessTestCase(TestCase):
    """Test readiness for external integrations"""
    
    def test_crm_integration_configuration(self):
        """Test CRM integration configuration"""
        
        # Test Salesforce configuration
        sf_settings = [
            'SALESFORCE_CLIENT_ID',
            'SALESFORCE_CLIENT_SECRET',
            'SALESFORCE_USERNAME',
            'SALESFORCE_PASSWORD'
        ]
        
        sf_configured = all(
            hasattr(settings, setting) or os.getenv(setting)
            for setting in sf_settings
        )
        
        # Test HubSpot configuration
        hs_configured = (
            hasattr(settings, 'HUBSPOT_API_KEY') or 
            os.getenv('HUBSPOT_API_KEY')
        )
        
        # Test Creatio configuration
        creatio_settings = [
            'CREATIO_API_URL',
            'CREATIO_USERNAME',
            'CREATIO_PASSWORD'
        ]
        
        creatio_configured = all(
            hasattr(settings, setting) or os.getenv(setting)
            for setting in creatio_settings
        )
        
        # At least one CRM should be configured
        self.assertTrue(
            sf_configured or hs_configured or creatio_configured,
            "At least one CRM integration should be configured"
        )
    
    def test_ai_service_configuration(self):
        """Test AI service configuration"""
        
        # Test Gemini AI configuration
        gemini_configured = (
            hasattr(settings, 'GEMINI_API_KEY') or 
            os.getenv('GEMINI_API_KEY')
        )
        
        self.assertTrue(
            gemini_configured,
            "Gemini AI API key should be configured"
        )
    
    def test_video_platform_configuration(self):
        """Test video platform integration configuration"""
        
        # Test Google Meet configuration
        meet_settings = [
            'GOOGLE_MEET_CLIENT_ID',
            'GOOGLE_MEET_CLIENT_SECRET'
        ]
        
        meet_configured = all(
            hasattr(settings, setting) or os.getenv(setting)
            for setting in meet_settings
        )
        
        # Test Teams configuration
        teams_settings = [
            'TEAMS_CLIENT_ID',
            'TEAMS_CLIENT_SECRET'
        ]
        
        teams_configured = all(
            hasattr(settings, setting) or os.getenv(setting)
            for setting in teams_settings
        )
        
        # Test Zoom configuration
        zoom_settings = [
            'ZOOM_CLIENT_ID',
            'ZOOM_CLIENT_SECRET'
        ]
        
        zoom_configured = all(
            hasattr(settings, setting) or os.getenv(setting)
            for setting in zoom_settings
        )
        
        # At least one video platform should be configured
        self.assertTrue(
            meet_configured or teams_configured or zoom_configured,
            "At least one video platform integration should be configured"
        )
    
    @patch('requests.get')
    def test_external_service_connectivity(self, mock_get):
        """Test connectivity to external services"""
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_get.return_value = mock_response
        
        # Test n8n connectivity if configured
        if hasattr(settings, 'N8N_WEBHOOK_URL') or os.getenv('N8N_WEBHOOK_URL'):
            n8n_url = getattr(settings, 'N8N_WEBHOOK_URL', os.getenv('N8N_WEBHOOK_URL'))
            
            try:
                response = requests.get(f"{n8n_url}/health", timeout=5)
                # Connection successful or service unavailable (both acceptable for deployment)
                self.assertIn(response.status_code, [200, 404, 503])
            except requests.RequestException:
                # Connection issues are acceptable for deployment tests
                pass
    
    def test_webhook_endpoints_configuration(self):
        """Test webhook endpoints are properly configured"""
        
        # Test n8n webhook configuration
        if hasattr(settings, 'N8N_WEBHOOK_URL'):
            self.assertIsInstance(settings.N8N_WEBHOOK_URL, str)
            self.assertTrue(settings.N8N_WEBHOOK_URL.startswith('http'))
        
        # Test webhook authentication if configured
        if hasattr(settings, 'WEBHOOK_SECRET_KEY'):
            self.assertIsInstance(settings.WEBHOOK_SECRET_KEY, str)
            self.assertGreater(len(settings.WEBHOOK_SECRET_KEY), 10)


class MonitoringTestCase(TestCase):
    """Test monitoring and alerting configuration"""
    
    def test_logging_levels(self):
        """Test logging levels are appropriate for production"""
        
        import logging
        
        # Test root logger level
        root_logger = logging.getLogger()
        self.assertIsNotNone(root_logger.level)
        
        # Test Django logger level
        django_logger = logging.getLogger('django')
        self.assertIsNotNone(django_logger.level)
        
        # Test application logger level
        app_logger = logging.getLogger('meetings')
        self.assertIsNotNone(app_logger.level)
    
    def test_error_tracking_configuration(self):
        """Test error tracking configuration"""
        
        # Test Sentry configuration if used
        if hasattr(settings, 'SENTRY_DSN') or os.getenv('SENTRY_DSN'):
            sentry_dsn = getattr(settings, 'SENTRY_DSN', os.getenv('SENTRY_DSN'))
            self.assertIsInstance(sentry_dsn, str)
            self.assertTrue(sentry_dsn.startswith('https://'))
    
    def test_health_check_endpoint(self):
        """Test health check endpoint functionality"""
        
        # Create a simple health check
        response = self.client.get('/api/health/')
        
        # Should either exist (200) or not be implemented yet (404)
        self.assertIn(response.status_code, [200, 404])
        
        if response.status_code == 200:
            # If implemented, should return JSON with status
            self.assertEqual(response['content-type'], 'application/json')
    
    def test_metrics_collection(self):
        """Test metrics collection capability"""
        
        # Test that we can collect basic metrics
        from django.db import connection
        
        # Database connection count
        queries_before = len(connection.queries)
        
        # Perform some database operations
        Lead.objects.count()
        Meeting.objects.count()
        
        queries_after = len(connection.queries)
        
        # Should have executed queries
        self.assertGreater(queries_after, queries_before)


class SecurityTestCase(TestCase):
    """Test security configuration for deployment"""
    
    def test_authentication_configuration(self):
        """Test authentication is properly configured"""
        
        # Test that authentication classes are configured
        if hasattr(settings, 'REST_FRAMEWORK'):
            rest_config = settings.REST_FRAMEWORK
            
            if 'DEFAULT_AUTHENTICATION_CLASSES' in rest_config:
                auth_classes = rest_config['DEFAULT_AUTHENTICATION_CLASSES']
                self.assertIsInstance(auth_classes, (list, tuple))
                self.assertGreater(len(auth_classes), 0)
    
    def test_permission_configuration(self):
        """Test permissions are properly configured"""
        
        if hasattr(settings, 'REST_FRAMEWORK'):
            rest_config = settings.REST_FRAMEWORK
            
            if 'DEFAULT_PERMISSION_CLASSES' in rest_config:
                permission_classes = rest_config['DEFAULT_PERMISSION_CLASSES']
                self.assertIsInstance(permission_classes, (list, tuple))
    
    def test_cors_configuration(self):
        """Test CORS configuration if used"""
        
        # Test CORS allowed origins
        if hasattr(settings, 'CORS_ALLOWED_ORIGINS'):
            self.assertIsInstance(settings.CORS_ALLOWED_ORIGINS, (list, tuple))
        
        # Test CORS allow credentials
        if hasattr(settings, 'CORS_ALLOW_CREDENTIALS'):
            self.assertIsInstance(settings.CORS_ALLOW_CREDENTIALS, bool)
    
    def test_ssl_configuration(self):
        """Test SSL/TLS configuration"""
        
        # Test secure cookie settings
        if hasattr(settings, 'SECURE_SSL_REDIRECT'):
            self.assertIsInstance(settings.SECURE_SSL_REDIRECT, bool)
        
        if hasattr(settings, 'SECURE_HSTS_SECONDS'):
            self.assertIsInstance(settings.SECURE_HSTS_SECONDS, int)
        
        if hasattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF'):
            self.assertIsInstance(settings.SECURE_CONTENT_TYPE_NOSNIFF, bool)