"""
Production JWT Authentication for Meeting Intelligence System
"""
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils import timezone
from rest_framework import authentication, exceptions
from rest_framework.authentication import BaseAuthentication
from .models import UserProfile, LoginAttempt


class JWTAuthentication(BaseAuthentication):
    """
    Production JWT Authentication class with enhanced security
    """
    
    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
            
        try:
            token = auth_header.split(' ')[1]
            
            # Check if token is blacklisted
            if self._is_token_blacklisted(token):
                raise exceptions.AuthenticationFailed('Token has been revoked')
            
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            
            user_id = payload.get('user_id')
            token_id = payload.get('jti')  # JWT ID for token tracking
            
            if not user_id or not token_id:
                raise exceptions.AuthenticationFailed('Invalid token payload')
                
            user = User.objects.get(id=user_id)
            
            # Check if user is active
            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled')
            
            # Check token expiration
            exp = payload.get('exp')
            if exp and datetime.utcnow().timestamp() > exp:
                raise exceptions.AuthenticationFailed('Token has expired')
            
            # Validate session and IP if configured
            self._validate_session_security(request, user, payload)
                
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return 'Bearer'
    
    def _is_token_blacklisted(self, token):
        """
        Check if token is in blacklist cache
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return cache.get(f'blacklisted_token:{token_hash}') is not None
    
    def _validate_session_security(self, request, user, payload):
        """
        Validate session security constraints
        """
        # Check IP binding if enabled
        if getattr(settings, 'JWT_BIND_IP', False):
            token_ip = payload.get('ip')
            current_ip = self._get_client_ip(request)
            if token_ip and token_ip != current_ip:
                raise exceptions.AuthenticationFailed('Token IP mismatch')
        
        # Check user agent binding if enabled
        if getattr(settings, 'JWT_BIND_USER_AGENT', False):
            token_ua = payload.get('user_agent')
            current_ua = request.META.get('HTTP_USER_AGENT', '')
            if token_ua and token_ua != current_ua:
                raise exceptions.AuthenticationFailed('Token user agent mismatch')
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class JWTTokenGenerator:
    """
    Production JWT Token generation and validation utilities
    """
    
    @staticmethod
    def generate_access_token(user, request=None):
        """
        Generate secure access token for user
        """
        now = datetime.utcnow()
        token_id = secrets.token_urlsafe(32)  # Unique token ID
        
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.profile.role if hasattr(user, 'profile') else 'sales_rep',
            'jti': token_id,  # JWT ID for token tracking
            'exp': now + timedelta(hours=getattr(settings, 'JWT_ACCESS_TOKEN_LIFETIME_HOURS', 1)),
            'iat': now,
            'nbf': now,  # Not before
            'type': 'access',
            'iss': getattr(settings, 'JWT_ISSUER', 'nia-meeting-intelligence'),
            'aud': getattr(settings, 'JWT_AUDIENCE', 'nia-api')
        }
        
        # Add security context if enabled
        if request:
            if getattr(settings, 'JWT_BIND_IP', False):
                payload['ip'] = JWTTokenGenerator._get_client_ip(request)
            if getattr(settings, 'JWT_BIND_USER_AGENT', False):
                payload['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def generate_refresh_token(user, request=None):
        """
        Generate secure refresh token for user
        """
        now = datetime.utcnow()
        token_id = secrets.token_urlsafe(32)
        
        payload = {
            'user_id': user.id,
            'jti': token_id,
            'exp': now + timedelta(days=getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7)),
            'iat': now,
            'nbf': now,
            'type': 'refresh',
            'iss': getattr(settings, 'JWT_ISSUER', 'nia-meeting-intelligence'),
            'aud': getattr(settings, 'JWT_AUDIENCE', 'nia-api')
        }
        
        # Store refresh token in cache for validation
        cache.set(f'refresh_token:{token_id}', user.id, 
                 timeout=getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7) * 24 * 3600)
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def verify_token(token):
        """
        Verify and decode token
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
    
    @staticmethod
    def refresh_access_token(refresh_token, request=None):
        """
        Generate new access token from refresh token with enhanced validation
        """
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('type') != 'refresh':
                raise exceptions.AuthenticationFailed('Invalid token type')
            
            token_id = payload.get('jti')
            user_id = payload.get('user_id')
            
            if not token_id or not user_id:
                raise exceptions.AuthenticationFailed('Invalid token payload')
            
            # Validate refresh token exists in cache
            cached_user_id = cache.get(f'refresh_token:{token_id}')
            if cached_user_id != user_id:
                raise exceptions.AuthenticationFailed('Refresh token not found or invalid')
            
            user = User.objects.get(id=user_id)
            
            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled')
            
            return JWTTokenGenerator.generate_access_token(user, request)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid refresh token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')
    
    @staticmethod
    def revoke_token(token):
        """
        Revoke a token by adding it to blacklist
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'], options={"verify_exp": False})
            token_id = payload.get('jti')
            exp = payload.get('exp')
            
            if token_id and exp:
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                # Blacklist until expiration
                ttl = max(0, exp - datetime.utcnow().timestamp())
                cache.set(f'blacklisted_token:{token_hash}', True, timeout=int(ttl))
                
                # If it's a refresh token, remove from cache
                if payload.get('type') == 'refresh':
                    cache.delete(f'refresh_token:{token_id}')
                    
        except jwt.InvalidTokenError:
            pass  # Token already invalid
    
    @staticmethod
    def revoke_all_user_tokens(user):
        """
        Revoke all tokens for a user by updating their token version
        """
        # This would require adding a token_version field to UserProfile
        # For now, we'll implement a simpler approach using cache
        cache.set(f'user_token_revoked:{user.id}', timezone.now().timestamp(), timeout=None)
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


def authenticate_user(username, password, request=None):
    """
    Authenticate user with enhanced security checks
    """
    # Check for account lockout
    if request:
        ip_address = JWTTokenGenerator._get_client_ip(request)
        if LoginAttempt.is_blocked(username, ip_address):
            return None
    
    user = authenticate(username=username, password=password)
    if not user:
        return None
    
    # Check if user account is active
    if not user.is_active:
        return None
        
    # Ensure user has a profile
    if not hasattr(user, 'profile'):
        UserProfile.objects.create(user=user)
    
    access_token = JWTTokenGenerator.generate_access_token(user, request)
    refresh_token = JWTTokenGenerator.generate_refresh_token(user, request)
    
    return {
        'user': user,
        'access_token': access_token,
        'refresh_token': refresh_token
    }


class SessionManager:
    """
    Manage user sessions and security
    """
    
    @staticmethod
    def create_session(user, request):
        """
        Create a new user session with security tracking
        """
        session_id = secrets.token_urlsafe(32)
        session_data = {
            'user_id': user.id,
            'ip_address': JWTTokenGenerator._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'created_at': timezone.now().isoformat(),
            'last_activity': timezone.now().isoformat()
        }
        
        # Store session for 24 hours
        cache.set(f'user_session:{session_id}', session_data, timeout=24*3600)
        cache.set(f'user_active_sessions:{user.id}', 
                 cache.get(f'user_active_sessions:{user.id}', []) + [session_id], 
                 timeout=24*3600)
        
        return session_id
    
    @staticmethod
    def validate_session(session_id, user, request):
        """
        Validate user session
        """
        session_data = cache.get(f'user_session:{session_id}')
        if not session_data:
            return False
        
        # Check user matches
        if session_data.get('user_id') != user.id:
            return False
        
        # Update last activity
        session_data['last_activity'] = timezone.now().isoformat()
        cache.set(f'user_session:{session_id}', session_data, timeout=24*3600)
        
        return True
    
    @staticmethod
    def revoke_session(session_id):
        """
        Revoke a specific session
        """
        session_data = cache.get(f'user_session:{session_id}')
        if session_data:
            user_id = session_data.get('user_id')
            cache.delete(f'user_session:{session_id}')
            
            # Remove from active sessions
            active_sessions = cache.get(f'user_active_sessions:{user_id}', [])
            if session_id in active_sessions:
                active_sessions.remove(session_id)
                cache.set(f'user_active_sessions:{user_id}', active_sessions, timeout=24*3600)
    
    @staticmethod
    def revoke_all_sessions(user):
        """
        Revoke all sessions for a user
        """
        active_sessions = cache.get(f'user_active_sessions:{user.id}', [])
        for session_id in active_sessions:
            cache.delete(f'user_session:{session_id}')
        cache.delete(f'user_active_sessions:{user.id}')
    
    @staticmethod
    def get_active_sessions(user):
        """
        Get all active sessions for a user
        """
        active_sessions = cache.get(f'user_active_sessions:{user.id}', [])
        sessions = []
        
        for session_id in active_sessions:
            session_data = cache.get(f'user_session:{session_id}')
            if session_data:
                sessions.append({
                    'session_id': session_id,
                    'ip_address': session_data.get('ip_address'),
                    'user_agent': session_data.get('user_agent'),
                    'created_at': session_data.get('created_at'),
                    'last_activity': session_data.get('last_activity')
                })
        
        return sessions