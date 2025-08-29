"""
Health check endpoints for deployment monitoring
"""
import json
import time
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Basic health check endpoint
    Returns 200 if the service is healthy
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'intelligent-meeting-workflow'
    })


@csrf_exempt
@require_http_methods(["GET"])
def health_detailed(request):
    """
    Detailed health check with component status
    """
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'intelligent-meeting-workflow',
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'components': {}
    }
    
    overall_healthy = True
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_data['components']['database'] = {
            'status': 'healthy',
            'response_time_ms': _measure_db_response_time()
        }
    except Exception as e:
        health_data['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Check cache connectivity
    try:
        cache_key = 'health_check_test'
        cache_value = str(time.time())
        cache.set(cache_key, cache_value, timeout=60)
        retrieved_value = cache.get(cache_key)
        
        if retrieved_value == cache_value:
            health_data['components']['cache'] = {
                'status': 'healthy',
                'response_time_ms': _measure_cache_response_time()
            }
        else:
            health_data['components']['cache'] = {
                'status': 'unhealthy',
                'error': 'Cache value mismatch'
            }
            overall_healthy = False
            
        cache.delete(cache_key)
    except Exception as e:
        health_data['components']['cache'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Check external service configurations
    health_data['components']['external_services'] = _check_external_services()
    
    # Set overall status
    if not overall_healthy:
        health_data['status'] = 'unhealthy'
    
    status_code = 200 if overall_healthy else 503
    return JsonResponse(health_data, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
def readiness_check(request):
    """
    Readiness check for Kubernetes/container orchestration
    """
    try:
        # Check if migrations are up to date
        from django.core.management import execute_from_command_line
        from django.core.management.base import CommandError
        
        # This is a simplified check - in production you might want more sophisticated logic
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        return JsonResponse({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
def liveness_check(request):
    """
    Liveness check for Kubernetes/container orchestration
    """
    return JsonResponse({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat()
    })


def _measure_db_response_time():
    """Measure database response time in milliseconds"""
    start_time = time.time()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return round((time.time() - start_time) * 1000, 2)
    except:
        return None


def _measure_cache_response_time():
    """Measure cache response time in milliseconds"""
    start_time = time.time()
    try:
        test_key = f'perf_test_{time.time()}'
        cache.set(test_key, 'test_value', timeout=10)
        cache.get(test_key)
        cache.delete(test_key)
        return round((time.time() - start_time) * 1000, 2)
    except:
        return None


def _check_external_services():
    """Check external service configurations"""
    services = {}
    
    # Check CRM configurations
    crm_configs = {
        'salesforce': ['SALESFORCE_CLIENT_ID', 'SALESFORCE_CLIENT_SECRET'],
        'hubspot': ['HUBSPOT_API_KEY'],
        'creatio': ['CREATIO_API_URL', 'CREATIO_USERNAME']
    }
    
    for crm, required_settings in crm_configs.items():
        configured = all(
            getattr(settings, setting, None) or 
            getattr(settings, setting.lower(), None)
            for setting in required_settings
        )
        services[f'crm_{crm}'] = {
            'status': 'configured' if configured else 'not_configured'
        }
    
    # Check AI service configuration
    ai_configured = bool(getattr(settings, 'GEMINI_API_KEY', None))
    services['ai_service'] = {
        'status': 'configured' if ai_configured else 'not_configured'
    }
    
    # Check video platform configurations
    video_platforms = {
        'google_meet': ['GOOGLE_MEET_CLIENT_ID', 'GOOGLE_MEET_CLIENT_SECRET'],
        'teams': ['TEAMS_CLIENT_ID', 'TEAMS_CLIENT_SECRET'],
        'zoom': ['ZOOM_CLIENT_ID', 'ZOOM_CLIENT_SECRET']
    }
    
    for platform, required_settings in video_platforms.items():
        configured = all(
            getattr(settings, setting, None)
            for setting in required_settings
        )
        services[f'video_{platform}'] = {
            'status': 'configured' if configured else 'not_configured'
        }
    
    return services