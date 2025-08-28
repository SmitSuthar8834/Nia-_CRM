"""
JWT Authentication for Meeting Intelligence System
"""
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import authentication, exceptions
from rest_framework.authentication import BaseAuthentication
from .models import UserProfile


class JWTAuthentication(BaseAuthentication):
    """
    Custom JWT Authentication class
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
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            
            user_id = payload.get('user_id')
            if not user_id:
                raise exceptions.AuthenticationFailed('Invalid token payload')
                
            user = User.objects.get(id=user_id)
            
            # Check if token is expired
            exp = payload.get('exp')
            if exp and datetime.utcnow().timestamp() > exp:
                raise exceptions.AuthenticationFailed('Token has expired')
                
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


class JWTTokenGenerator:
    """
    JWT Token generation and validation utilities
    """
    
    @staticmethod
    def generate_access_token(user):
        """
        Generate access token for user
        """
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.profile.role if hasattr(user, 'profile') else 'sales_rep',
            'exp': datetime.utcnow() + timedelta(hours=24),  # 24 hour expiry
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    
    @staticmethod
    def generate_refresh_token(user):
        """
        Generate refresh token for user
        """
        payload = {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=7),  # 7 day expiry
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        
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
    def refresh_access_token(refresh_token):
        """
        Generate new access token from refresh token
        """
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
            
            if payload.get('type') != 'refresh':
                raise exceptions.AuthenticationFailed('Invalid token type')
                
            user_id = payload.get('user_id')
            user = User.objects.get(id=user_id)
            
            return JWTTokenGenerator.generate_access_token(user)
            
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid refresh token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')


def authenticate_user(username, password):
    """
    Authenticate user and return tokens
    """
    user = authenticate(username=username, password=password)
    if not user:
        return None
        
    # Ensure user has a profile
    if not hasattr(user, 'profile'):
        UserProfile.objects.create(user=user)
    
    access_token = JWTTokenGenerator.generate_access_token(user)
    refresh_token = JWTTokenGenerator.generate_refresh_token(user)
    
    return {
        'user': user,
        'access_token': access_token,
        'refresh_token': refresh_token
    }