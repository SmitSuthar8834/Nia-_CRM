"""
Serializers for User Account and Authentication
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, TwoFactorAuth, CalendarIntegration, UserActivity, LoginAttempt


class UserSerializer(serializers.ModelSerializer):
    """
    Basic User serializer
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserProfileSerializer(serializers.ModelSerializer):
    """
    User Profile serializer with role and permissions
    """
    user = UserSerializer(read_only=True)
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'role', 'permissions', 'phone', 'department', 'title',
            'timezone', 'google_calendar_connected', 'outlook_calendar_connected',
            'calendar_sync_enabled', 'email_notifications', 'debriefing_reminders',
            'meeting_alerts', 'ai_coaching_enabled', 'auto_debriefing_scheduling',
            'created_at', 'updated_at', 'last_login_ip', 'full_name'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at', 'last_login_ip', 'full_name',
            'google_calendar_connected', 'outlook_calendar_connected'
        ]
    
    def validate_role(self, value):
        """
        Validate role assignment
        """
        # Only admins can assign admin role
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user_profile = getattr(request.user, 'profile', None)
            if value == 'admin' and user_profile and user_profile.role != 'admin':
                raise serializers.ValidationError("Only admins can assign admin role")
        return value


class TwoFactorAuthSerializer(serializers.ModelSerializer):
    """
    Two-Factor Authentication serializer
    """
    qr_code = serializers.ReadOnlyField()
    totp_uri = serializers.ReadOnlyField()
    
    class Meta:
        model = TwoFactorAuth
        fields = [
            'id', 'is_enabled', 'backup_codes', 'created_at', 'enabled_at',
            'last_used', 'qr_code', 'totp_uri'
        ]
        read_only_fields = [
            'id', 'backup_codes', 'created_at', 'enabled_at', 'last_used',
            'qr_code', 'totp_uri'
        ]


class CalendarIntegrationSerializer(serializers.ModelSerializer):
    """
    Calendar Integration serializer
    """
    is_token_expired = serializers.ReadOnlyField()
    
    class Meta:
        model = CalendarIntegration
        fields = [
            'id', 'provider', 'provider_user_id', 'provider_email', 'status',
            'last_sync', 'next_sync', 'sync_enabled', 'sync_interval_minutes',
            'error_message', 'error_count', 'created_at', 'updated_at',
            'is_token_expired'
        ]
        read_only_fields = [
            'id', 'provider_user_id', 'status', 'last_sync', 'next_sync',
            'error_message', 'error_count', 'created_at', 'updated_at',
            'is_token_expired'
        ]


class UserActivitySerializer(serializers.ModelSerializer):
    """
    User Activity serializer
    """
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = UserActivity
        fields = [
            'id', 'user_username', 'activity_type', 'description', 'entity_type',
            'entity_id', 'ip_address', 'user_agent', 'session_id', 'created_at'
        ]
        read_only_fields = ['id', 'user_username', 'created_at']


class LoginAttemptSerializer(serializers.ModelSerializer):
    """
    Login Attempt serializer for security monitoring
    """
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = LoginAttempt
        fields = [
            'id', 'user_username', 'username', 'attempt_type', 'status',
            'ip_address', 'user_agent', 'failure_reason', 'created_at'
        ]
        read_only_fields = ['id', 'user_username', 'created_at']


class LoginRequestSerializer(serializers.Serializer):
    """
    Login request serializer
    """
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    totp_token = serializers.CharField(max_length=6, required=False, allow_blank=True)
    backup_code = serializers.CharField(max_length=8, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """
        Validate login request
        """
        username = attrs.get('username')
        password = attrs.get('password')
        
        if not username or not password:
            raise serializers.ValidationError("Username and password are required")
        
        return attrs


class RefreshTokenSerializer(serializers.Serializer):
    """
    Refresh token request serializer
    """
    refresh_token = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    """
    Change password serializer
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """
        Validate password change
        """
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError("New passwords do not match")
        
        # Add password strength validation here if needed
        if len(new_password) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        
        return attrs


class UserRoleChangeSerializer(serializers.Serializer):
    """
    User role change serializer for admin use
    """
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    
    def validate_user_id(self, value):
        """
        Validate user exists
        """
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        return value


class TwoFactorSetupSerializer(serializers.Serializer):
    """
    Two-factor authentication setup serializer
    """
    token = serializers.CharField(max_length=6)
    
    def validate_token(self, value):
        """
        Validate TOTP token format
        """
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Token must be 6 digits")
        return value


class CalendarConnectionSerializer(serializers.Serializer):
    """
    Calendar connection request serializer
    """
    provider = serializers.ChoiceField(choices=CalendarIntegration.PROVIDER_CHOICES)
    provider_email = serializers.EmailField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField(required=False, allow_blank=True)
    token_expires_at = serializers.DateTimeField(required=False, allow_null=True)