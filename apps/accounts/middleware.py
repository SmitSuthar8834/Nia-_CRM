"""
Security and Authentication Middleware
"""
import logging
from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserActivity, LoginAttempt

logger = logging.getLogger(__name__)


class UserActivityMiddleware:
    """
    Middleware to log user activities
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Log API activities for authenticated users
        if (request.user.is_authenticated and 
            request.path.startswith('/api/') and
            request.method in ['POST', 'PUT', 'PATCH', 'DELETE']):
            
            self._log_activity(request, response)
        
        return response
    
    def _log_activity(self, request, response):
        """Log user activity"""
        try:
            activity_type = self._determine_activity_type(request)
            if activity_type:
                UserActivity.objects.create(
                    user=request.user,
                    activity_type=activity_type,
                    description=self._get_activity_description(request, response),
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    session_id=request.session.session_key
                )
        except Exception as e:
            logger.error(f"Error logging user activity: {str(e)}")
    
    def _determine_activity_type(self, request):
        """Determine activity type based on request"""
        path = request.path.lower()
        method = request.method
        
        if '/meetings/' in path:
            if method == 'POST':
                return 'meeting_create'
            elif method in ['PUT', 'PATCH']:
                return 'meeting_update'
            elif method == 'DELETE':
                return 'meeting_delete'
        elif '/debriefings/' in path:
            if method == 'POST':
                return 'debriefing_start'
            elif method in ['PUT', 'PATCH']:
                return 'debriefing_update'
        elif '/leads/' in path:
            if method == 'POST':
                return 'lead_create'
            elif method in ['PUT', 'PATCH']:
                return 'lead_update'
        elif '/crm/' in path:
            return 'crm_sync'
        elif '/calendar/' in path:
            return 'calendar_sync'
        
        return None
    
    def _get_activity_description(self, request, response):
        """Generate activity description"""
        method = request.method
        path = request.path
        status_code = response.status_code
        
        return f"{method} {path} - Status: {status_code}"
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add CSP header for API endpoints
        if request.path.startswith('/api/'):
            response['Content-Security-Policy'] = "default-src 'self'"
        
        return response


class RateLimitMiddleware:
    """
    Simple rate limiting middleware for authentication endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limits = {
            '/api/v1/auth/login/': {'requests': 5, 'window': 300},  # 5 requests per 5 minutes
            '/api/v1/auth/refresh/': {'requests': 10, 'window': 300},  # 10 requests per 5 minutes
        }
    
    def __call__(self, request):
        # Check rate limits for specific endpoints
        if request.path in self.rate_limits:
            if self._is_rate_limited(request):
                from django.http import JsonResponse
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Please try again later.'},
                    status=429
                )
        
        response = self.get_response(request)
        return response
    
    def _is_rate_limited(self, request):
        """Check if request should be rate limited"""
        path = request.path
        ip_address = self._get_client_ip(request)
        
        if path not in self.rate_limits:
            return False
        
        limit_config = self.rate_limits[path]
        window_seconds = limit_config['window']
        max_requests = limit_config['requests']
        
        # Count recent requests from this IP for this endpoint
        from datetime import timedelta
        recent_time = timezone.now() - timedelta(seconds=window_seconds)
        
        # For login endpoint, count all login attempts
        if path == '/api/v1/auth/login/':
            recent_attempts = LoginAttempt.objects.filter(
                ip_address=ip_address,
                created_at__gte=recent_time
            ).count()
        else:
            # For other endpoints, we'd need a more sophisticated tracking system
            # For now, just allow all requests
            recent_attempts = 0
        
        return recent_attempts >= max_requests
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SessionSecurityMiddleware:
    """
    Middleware for session security enhancements
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Update last activity for authenticated users
        if request.user.is_authenticated:
            request.session['last_activity'] = timezone.now().isoformat()
            
            # Update user profile last login IP if it's different
            if hasattr(request.user, 'profile'):
                current_ip = self._get_client_ip(request)
                if request.user.profile.last_login_ip != current_ip:
                    request.user.profile.last_login_ip = current_ip
                    request.user.profile.save(update_fields=['last_login_ip'])
        
        response = self.get_response(request)
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip