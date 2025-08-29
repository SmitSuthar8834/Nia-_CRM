"""
Serializers for User Account and Authentication
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    UserProfile, TwoFactorAuth, CalendarIntegration, UserActivity, LoginAttempt,
    ConsentRecord, PrivacySettings, DataRetentionPolicy, DataDeletionRequest, EncryptedDataField
)


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


class ConsentRecordSerializer(serializers.ModelSerializer):
    """
    Consent record serializer
    """
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = ConsentRecord
        fields = [
            'id', 'consent_type', 'status', 'purpose', 'granted_at',
            'withdrawn_at', 'expires_at', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'granted_at', 'withdrawn_at', 'created_at', 'is_active']


class PrivacySettingsSerializer(serializers.ModelSerializer):
    """
    Privacy settings serializer
    """
    effective_retention_days = serializers.ReadOnlyField(source='get_effective_retention_days')
    
    class Meta:
        model = PrivacySettings
        fields = [
            'id', 'allow_ai_analysis', 'allow_transcript_storage',
            'allow_analytics_processing', 'allow_third_party_integrations',
            'share_anonymized_data', 'share_with_team_members',
            'share_with_managers', 'auto_delete_transcripts',
            'transcript_retention_days', 'privacy_policy_updates',
            'data_breach_notifications', 'consent_renewal_reminders',
            'effective_retention_days', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'effective_retention_days', 'created_at', 'updated_at']


class DataRetentionPolicySerializer(serializers.ModelSerializer):
    """
    Data retention policy serializer
    """
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = DataRetentionPolicy
        fields = [
            'id', 'data_type', 'retention_period_days', 'auto_delete_enabled',
            'archive_before_delete', 'require_user_consent', 'legal_basis',
            'regulatory_requirement', 'created_at', 'updated_at', 'created_by_username'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_username']


class DataDeletionRequestSerializer(serializers.ModelSerializer):
    """
    Data deletion request serializer
    """
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    processed_by_username = serializers.CharField(source='processed_by.username', read_only=True)
    
    class Meta:
        model = DataDeletionRequest
        fields = [
            'id', 'request_type', 'status', 'data_types', 'include_backups',
            'include_logs', 'requested_at', 'started_at', 'completed_at',
            'deleted_records_count', 'error_message', 'legal_basis',
            'retention_override', 'requested_by_username', 'processed_by_username'
        ]
        read_only_fields = [
            'id', 'requested_at', 'started_at', 'completed_at',
            'deleted_records_count', 'error_message', 'requested_by_username',
            'processed_by_username'
        ]


class EncryptedDataFieldSerializer(serializers.ModelSerializer):
    """
    Encrypted data field serializer (metadata only)
    """
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    is_high_sensitivity = serializers.ReadOnlyField()
    
    class Meta:
        model = EncryptedDataField
        fields = [
            'id', 'field_type', 'sensitivity_level', 'encryption_algorithm',
            'key_version', 'encrypted_at', 'owner_username', 'access_level',
            'created_at', 'last_accessed', 'access_count', 'is_high_sensitivity'
        ]
        read_only_fields = [
            'id', 'encrypted_at', 'owner_username', 'created_at',
            'last_accessed', 'access_count', 'is_high_sensitivity'
        ]
        # Note: encrypted_data is intentionally excluded for security