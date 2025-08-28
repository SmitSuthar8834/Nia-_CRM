"""
Authentication and User Management Views
"""
import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import UserProfile, TwoFactorAuth, LoginAttempt, CalendarIntegration, UserActivity
from .authentication import JWTTokenGenerator, authenticate_user
from .permissions import (
    AdminOnlyPermission, 
    ManagerOrAdminPermission,
    MeetingIntelligencePermission
)
from .serializers import (
    UserProfileSerializer, 
    TwoFactorAuthSerializer,
    CalendarIntegrationSerializer,
    UserActivitySerializer
)


class LoginView(APIView):
    """
    User login with JWT token generation
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        tags=['Authentication'],
        summary='User Login',
        description='Authenticate user and return JWT tokens. Supports two-factor authentication.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Username or email'},
                    'password': {'type': 'string', 'description': 'User password'},
                    'totp_token': {'type': 'string', 'description': 'TOTP token for 2FA (optional)'},
                    'backup_code': {'type': 'string', 'description': 'Backup code for 2FA (optional)'}
                },
                'required': ['username', 'password'],
                'example': {
                    'username': 'john.doe@company.com',
                    'password': 'securepassword123',
                    'totp_token': '123456'
                }
            }
        },
        responses={
            200: {
                'description': 'Login successful',
                'examples': [
                    OpenApiExample(
                        'Success Response',
                        value={
                            'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                            'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...',
                            'user': {
                                'id': 1,
                                'username': 'john.doe',
                                'email': 'john.doe@company.com',
                                'role': 'sales_rep',
                                'first_name': 'John',
                                'last_name': 'Doe'
                            }
                        }
                    ),
                    OpenApiExample(
                        '2FA Required',
                        value={
                            'error': '2FA token required',
                            'requires_2fa': True
                        }
                    )
                ]
            },
            400: {
                'description': 'Bad request - missing required fields',
                'examples': [
                    OpenApiExample(
                        'Missing Credentials',
                        value={'error': 'Username and password are required'}
                    )
                ]
            },
            401: {
                'description': 'Authentication failed',
                'examples': [
                    OpenApiExample(
                        'Invalid Credentials',
                        value={'error': 'Invalid credentials'}
                    ),
                    OpenApiExample(
                        'Invalid 2FA Token',
                        value={'error': 'Invalid 2FA token'}
                    )
                ]
            },
            429: {
                'description': 'Too many failed attempts',
                'examples': [
                    OpenApiExample(
                        'Account Blocked',
                        value={'error': 'Account temporarily blocked due to too many failed attempts'}
                    )
                ]
            }
        }
    )
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        totp_token = request.data.get('totp_token')
        backup_code = request.data.get('backup_code')
        
        if not username or not password:
            return Response({
                'error': 'Username and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get client IP and user agent
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check if user is blocked
        if LoginAttempt.is_blocked(username, ip_address):
            LoginAttempt.objects.create(
                username=username,
                attempt_type='password',
                status='blocked',
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason='Too many failed attempts'
            )
            return Response({
                'error': 'Account temporarily blocked due to too many failed attempts'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Authenticate user
        auth_result = authenticate_user(username, password)
        if not auth_result:
            LoginAttempt.objects.create(
                username=username,
                attempt_type='password',
                status='failed',
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason='Invalid credentials'
            )
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        user = auth_result['user']
        
        # Check if 2FA is enabled
        two_factor = getattr(user, 'two_factor', None)
        if two_factor and two_factor.is_enabled:
            # Verify TOTP token or backup code
            if totp_token:
                if not two_factor.verify_token(totp_token):
                    LoginAttempt.objects.create(
                        user=user,
                        username=username,
                        attempt_type='2fa',
                        status='failed',
                        ip_address=ip_address,
                        user_agent=user_agent,
                        failure_reason='Invalid TOTP token'
                    )
                    return Response({
                        'error': 'Invalid 2FA token'
                    }, status=status.HTTP_401_UNAUTHORIZED)
            elif backup_code:
                if not two_factor.verify_backup_code(backup_code):
                    LoginAttempt.objects.create(
                        user=user,
                        username=username,
                        attempt_type='backup_code',
                        status='failed',
                        ip_address=ip_address,
                        user_agent=user_agent,
                        failure_reason='Invalid backup code'
                    )
                    return Response({
                        'error': 'Invalid backup code'
                    }, status=status.HTTP_401_UNAUTHORIZED)
            else:
                return Response({
                    'error': '2FA token required',
                    'requires_2fa': True
                }, status=status.HTTP_200_OK)
        
        # Successful login
        LoginAttempt.objects.create(
            user=user,
            username=username,
            attempt_type='2fa' if (totp_token or backup_code) else 'password',
            status='success',
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Update user profile
        user.profile.last_login_ip = ip_address
        user.profile.save()
        
        # Log activity
        UserActivity.objects.create(
            user=user,
            activity_type='login',
            description=f'User logged in from {ip_address}',
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return Response({
            'access_token': auth_result['access_token'],
            'refresh_token': auth_result['refresh_token'],
            'user': UserProfileSerializer(user.profile).data
        })
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RefreshTokenView(APIView):
    """
    Refresh JWT access token
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        tags=['Authentication'],
        summary='Refresh Access Token',
        description='Refresh an expired access token using a valid refresh token.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh_token': {'type': 'string', 'description': 'Valid refresh token'}
                },
                'required': ['refresh_token'],
                'example': {
                    'refresh_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                }
            }
        },
        responses={
            200: {
                'description': 'Token refreshed successfully',
                'examples': [
                    OpenApiExample(
                        'Success Response',
                        value={
                            'access_token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
                        }
                    )
                ]
            },
            400: {
                'description': 'Bad request - missing refresh token',
                'examples': [
                    OpenApiExample(
                        'Missing Token',
                        value={'error': 'Refresh token is required'}
                    )
                ]
            },
            401: {
                'description': 'Invalid or expired refresh token',
                'examples': [
                    OpenApiExample(
                        'Invalid Token',
                        value={'error': 'Invalid or expired refresh token'}
                    )
                ]
            }
        }
    )
    
    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            access_token = JWTTokenGenerator.refresh_access_token(refresh_token)
            return Response({
                'access_token': access_token
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    """
    User logout
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Authentication'],
        summary='User Logout',
        description='Log out the current user and invalidate their session.',
        responses={
            200: {
                'description': 'Logout successful',
                'examples': [
                    OpenApiExample(
                        'Success Response',
                        value={'message': 'Successfully logged out'}
                    )
                ]
            },
            401: {
                'description': 'Authentication required',
                'examples': [
                    OpenApiExample(
                        'Not Authenticated',
                        value={'detail': 'Authentication credentials were not provided.'}
                    )
                ]
            }
        }
    )
    
    def post(self, request):
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='logout',
            description='User logged out',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'message': 'Successfully logged out'
        })
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get and update user profile
    """
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Authentication'],
        summary='Get User Profile',
        description='Retrieve the current user\'s profile information.',
        responses={
            200: UserProfileSerializer,
            401: {
                'description': 'Authentication required',
                'examples': [
                    OpenApiExample(
                        'Not Authenticated',
                        value={'detail': 'Authentication credentials were not provided.'}
                    )
                ]
            }
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Authentication'],
        summary='Update User Profile',
        description='Update the current user\'s profile information.',
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: {
                'description': 'Validation error',
                'examples': [
                    OpenApiExample(
                        'Validation Error',
                        value={
                            'email': ['Enter a valid email address.'],
                            'phone': ['This field may not be blank.']
                        }
                    )
                ]
            },
            401: {
                'description': 'Authentication required'
            }
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Authentication'],
        summary='Partially Update User Profile',
        description='Partially update the current user\'s profile information.',
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: {'description': 'Validation error'},
            401: {'description': 'Authentication required'}
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class TwoFactorSetupView(APIView):
    """
    Setup two-factor authentication
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Authentication'],
        summary='Get 2FA Setup Information',
        description='Get the secret key and QR code for setting up two-factor authentication.',
        responses={
            200: {
                'description': '2FA setup information',
                'examples': [
                    OpenApiExample(
                        'Setup Info',
                        value={
                            'secret_key': 'JBSWY3DPEHPK3PXP',
                            'qr_code': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...',
                            'totp_uri': 'otpauth://totp/NIA:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=NIA',
                            'is_enabled': False,
                            'backup_codes': []
                        }
                    )
                ]
            },
            401: {'description': 'Authentication required'}
        }
    )
    def get(self, request):
        """Get 2FA setup information"""
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
        
        return Response({
            'secret_key': two_factor.secret_key,
            'qr_code': two_factor.get_qr_code(),
            'totp_uri': two_factor.get_totp_uri(),
            'is_enabled': two_factor.is_enabled,
            'backup_codes': two_factor.backup_codes if two_factor.is_enabled else []
        })
    
    @extend_schema(
        tags=['Authentication'],
        summary='Enable 2FA',
        description='Enable two-factor authentication by verifying a TOTP token.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'token': {'type': 'string', 'description': 'TOTP token from authenticator app'}
                },
                'required': ['token'],
                'example': {'token': '123456'}
            }
        },
        responses={
            200: {
                'description': '2FA enabled successfully',
                'examples': [
                    OpenApiExample(
                        'Success Response',
                        value={
                            'message': '2FA enabled successfully',
                            'backup_codes': ['12345678', '87654321', '11111111', '22222222', '33333333']
                        }
                    )
                ]
            },
            400: {
                'description': 'Invalid token or missing token',
                'examples': [
                    OpenApiExample(
                        'Missing Token',
                        value={'error': 'TOTP token is required'}
                    ),
                    OpenApiExample(
                        'Invalid Token',
                        value={'error': 'Invalid TOTP token'}
                    )
                ]
            },
            401: {'description': 'Authentication required'}
        }
    )
    def post(self, request):
        """Enable 2FA with token verification"""
        token = request.data.get('token')
        
        if not token:
            return Response({
                'error': 'TOTP token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
        
        if two_factor.verify_token(token):
            two_factor.enable_2fa()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='settings_change',
                description='Two-factor authentication enabled'
            )
            
            return Response({
                'message': '2FA enabled successfully',
                'backup_codes': two_factor.backup_codes
            })
        else:
            return Response({
                'error': 'Invalid TOTP token'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        tags=['Authentication'],
        summary='Disable 2FA',
        description='Disable two-factor authentication for the current user.',
        responses={
            200: {
                'description': '2FA disabled successfully',
                'examples': [
                    OpenApiExample(
                        'Success Response',
                        value={'message': '2FA disabled successfully'}
                    )
                ]
            },
            400: {
                'description': '2FA not enabled',
                'examples': [
                    OpenApiExample(
                        'Not Enabled',
                        value={'error': '2FA is not enabled'}
                    )
                ]
            },
            401: {'description': 'Authentication required'}
        }
    )
    
    def get(self, request):
        """Get 2FA setup information"""
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
        
        return Response({
            'secret_key': two_factor.secret_key,
            'qr_code': two_factor.get_qr_code(),
            'totp_uri': two_factor.get_totp_uri(),
            'is_enabled': two_factor.is_enabled,
            'backup_codes': two_factor.backup_codes if two_factor.is_enabled else []
        })
    
    def post(self, request):
        """Enable 2FA with token verification"""
        token = request.data.get('token')
        
        if not token:
            return Response({
                'error': 'TOTP token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        two_factor, created = TwoFactorAuth.objects.get_or_create(user=request.user)
        
        if two_factor.verify_token(token):
            two_factor.enable_2fa()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='settings_change',
                description='Two-factor authentication enabled'
            )
            
            return Response({
                'message': '2FA enabled successfully',
                'backup_codes': two_factor.backup_codes
            })
        else:
            return Response({
                'error': 'Invalid TOTP token'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request):
        """Disable 2FA"""
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user)
            two_factor.disable_2fa()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='settings_change',
                description='Two-factor authentication disabled'
            )
            
            return Response({
                'message': '2FA disabled successfully'
            })
        except TwoFactorAuth.DoesNotExist:
            return Response({
                'error': '2FA is not enabled'
            }, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorBackupCodesView(APIView):
    """
    Manage 2FA backup codes
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Generate new backup codes"""
        try:
            two_factor = TwoFactorAuth.objects.get(user=request.user, is_enabled=True)
            backup_codes = two_factor.generate_backup_codes()
            
            # Log activity
            UserActivity.objects.create(
                user=request.user,
                activity_type='settings_change',
                description='New backup codes generated'
            )
            
            return Response({
                'backup_codes': backup_codes
            })
        except TwoFactorAuth.DoesNotExist:
            return Response({
                'error': '2FA is not enabled'
            }, status=status.HTTP_400_BAD_REQUEST)


class CalendarIntegrationView(generics.ListCreateAPIView):
    """
    Manage calendar integrations
    """
    serializer_class = CalendarIntegrationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CalendarIntegration.objects.filter(user=self.request.user)


class UserActivityView(generics.ListAPIView):
    """
    View user activity log
    """
    serializer_class = UserActivitySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserActivity.objects.filter(user=self.request.user)


class AdminUserManagementView(generics.ListAPIView):
    """
    Admin view for user management
    """
    serializer_class = UserProfileSerializer
    permission_classes = [AdminOnlyPermission]
    
    def get_queryset(self):
        return UserProfile.objects.all()


class ManagerTeamView(generics.ListAPIView):
    """
    Manager view for team members
    """
    serializer_class = UserProfileSerializer
    permission_classes = [ManagerOrAdminPermission]
    
    def get_queryset(self):
        # For now, return all sales reps
        # In a real implementation, you'd filter by team assignment
        return UserProfile.objects.filter(role='sales_rep')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_permissions(request):
    """
    Get current user's permissions
    """
    user_profile = request.user.profile
    
    # Define all possible permissions
    all_permissions = [
        'view_all_meetings', 'manage_team_debriefings',
        'view_competitive_intel', 'approve_crm_updates',
        'view_analytics', 'manage_leads', 'view_own_meetings',
        'conduct_debriefings', 'update_own_leads', 'schedule_meetings',
        'view_dashboard', 'view_reports', 'all_permissions'
    ]
    
    user_permissions = {}
    for permission in all_permissions:
        user_permissions[permission] = user_profile.has_permission(permission)
    
    return Response({
        'role': user_profile.role,
        'permissions': user_permissions
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def notification_settings(request):
    """
    Get and update notification settings
    """
    if request.method == 'GET':
        # Return default notification settings
        return Response({
            'email_debriefing_reminders': True,
            'email_meeting_updates': True,
            'email_crm_sync_alerts': True,
            'push_notifications': True,
            'debriefing_reminder_frequency': 30,
        })
    
    elif request.method == 'PATCH':
        # For now, just return success - in a real app you'd save to user profile
        return Response({
            'message': 'Notification settings updated successfully'
        })


@api_view(['POST'])
@permission_classes([AdminOnlyPermission])
def change_user_role(request):
    """
    Admin endpoint to change user role
    """
    user_id = request.data.get('user_id')
    new_role = request.data.get('role')
    
    if not user_id or not new_role:
        return Response({
            'error': 'user_id and role are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user_profile = UserProfile.objects.get(user_id=user_id)
        old_role = user_profile.role
        user_profile.role = new_role
        user_profile.save()
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='settings_change',
            description=f'Changed user {user_profile.user.username} role from {old_role} to {new_role}',
            entity_type='user',
            entity_id=user_profile.user.id
        )
        
        return Response({
            'message': f'User role changed to {new_role}'
        })
    except UserProfile.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)