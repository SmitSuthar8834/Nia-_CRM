"""
User Account Models with Role-Based Access Control
"""
import uuid
import pyotp
import qrcode
from io import BytesIO
import base64
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings


class UserProfile(models.Model):
    """
    Extended user profile for meeting intelligence system
    """
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('sales_manager', 'Sales Manager'),
        ('sales_rep', 'Sales Representative'),
        ('viewer', 'Viewer'),
    ]
    
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('US/Eastern', 'Eastern Time'),
        ('US/Central', 'Central Time'),
        ('US/Mountain', 'Mountain Time'),
        ('US/Pacific', 'Pacific Time'),
        ('Europe/London', 'London'),
        ('Europe/Paris', 'Paris'),
        ('Asia/Tokyo', 'Tokyo'),
        ('Asia/Shanghai', 'Shanghai'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Role and Permissions
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales_rep')
    permissions = models.JSONField(default=dict, help_text="Custom permissions for this user")
    
    # Profile Information
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC')
    
    # Calendar Integration
    google_calendar_connected = models.BooleanField(default=False)
    outlook_calendar_connected = models.BooleanField(default=False)
    calendar_sync_enabled = models.BooleanField(default=True)
    
    # Notification Preferences
    email_notifications = models.BooleanField(default=True)
    debriefing_reminders = models.BooleanField(default=True)
    meeting_alerts = models.BooleanField(default=True)
    
    # AI Preferences
    ai_coaching_enabled = models.BooleanField(default=True)
    auto_debriefing_scheduling = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)
    
    class Meta:
        db_table = 'user_profiles'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    @property
    def full_name(self):
        """Get user's full name"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    def has_permission(self, permission):
        """Check if user has specific permission"""
        role_permissions = {
            'admin': ['all_permissions'],
            'sales_manager': [
                'view_all_meetings', 'manage_team_debriefings',
                'view_competitive_intel', 'approve_crm_updates',
                'view_analytics', 'manage_leads'
            ],
            'sales_rep': [
                'view_own_meetings', 'conduct_debriefings',
                'update_own_leads', 'schedule_meetings'
            ],
            'viewer': [
                'view_dashboard', 'view_reports'
            ]
        }
        
        user_permissions = role_permissions.get(self.role, [])
        return permission in user_permissions or 'all_permissions' in user_permissions


class CalendarIntegration(models.Model):
    """
    Calendar integration settings for users
    """
    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Outlook Calendar'),
        ('exchange', 'Exchange Server'),
    ]
    
    STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
        ('expired', 'Token Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_integrations')
    
    # Provider Information
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=200, blank=True, null=True)
    provider_email = models.EmailField()
    
    # Connection Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    last_sync = models.DateTimeField(blank=True, null=True)
    next_sync = models.DateTimeField(blank=True, null=True)
    
    # Authentication
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    
    # Settings
    sync_enabled = models.BooleanField(default=True)
    sync_interval_minutes = models.IntegerField(default=15)
    
    # Error Handling
    error_message = models.TextField(blank=True, null=True)
    error_count = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'calendar_integrations'
        unique_together = ['user', 'provider', 'provider_email']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['next_sync']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.provider} ({self.status})"

    @property
    def is_token_expired(self):
        """Check if access token is expired"""
        if self.token_expires_at:
            return timezone.now() >= self.token_expires_at
        return False

    def mark_error(self, error_message):
        """Mark integration as having an error"""
        self.status = 'error'
        self.error_message = error_message
        self.error_count += 1
        self.save()

    def mark_connected(self):
        """Mark integration as successfully connected"""
        self.status = 'connected'
        self.error_message = None
        self.error_count = 0
        self.last_sync = timezone.now()
        self.save()


class UserActivity(models.Model):
    """
    Track user activities for audit and analytics
    """
    ACTIVITY_TYPE_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('meeting_view', 'Meeting Viewed'),
        ('debriefing_start', 'Debriefing Started'),
        ('debriefing_complete', 'Debriefing Completed'),
        ('lead_update', 'Lead Updated'),
        ('crm_sync', 'CRM Sync'),
        ('calendar_sync', 'Calendar Sync'),
        ('settings_change', 'Settings Changed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    
    # Activity Details
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    
    # Context
    entity_type = models.CharField(max_length=50, blank=True, null=True)
    entity_id = models.UUIDField(blank=True, null=True)
    
    # Technical Details
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_activities'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['activity_type', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.created_at}"


class TwoFactorAuth(models.Model):
    """
    Two-Factor Authentication (TOTP) for users
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='two_factor')
    
    # TOTP Configuration
    secret_key = models.CharField(max_length=32, unique=True)
    is_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, help_text="List of backup codes")
    
    # Recovery
    recovery_codes_used = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    enabled_at = models.DateTimeField(blank=True, null=True)
    last_used = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'two_factor_auth'
        
    def __str__(self):
        return f"{self.user.username} - 2FA {'Enabled' if self.is_enabled else 'Disabled'}"
    
    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = pyotp.random_base32()
        super().save(*args, **kwargs)
    
    def get_totp_uri(self):
        """Get TOTP URI for QR code generation"""
        totp = pyotp.TOTP(self.secret_key)
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name="NIA Meeting Intelligence"
        )
    
    def get_qr_code(self):
        """Generate QR code for TOTP setup"""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(self.get_totp_uri())
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_token(self, token):
        """Verify TOTP token"""
        if not self.is_enabled:
            return False
            
        totp = pyotp.TOTP(self.secret_key)
        is_valid = totp.verify(token, valid_window=1)  # Allow 30 second window
        
        if is_valid:
            self.last_used = timezone.now()
            self.save()
            
        return is_valid
    
    def verify_backup_code(self, code):
        """Verify backup recovery code"""
        if code in self.backup_codes and code not in self.recovery_codes_used:
            self.recovery_codes_used.append(code)
            self.save()
            return True
        return False
    
    def generate_backup_codes(self, count=10):
        """Generate new backup codes"""
        import secrets
        import string
        
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            codes.append(code)
        
        self.backup_codes = codes
        self.recovery_codes_used = []
        self.save()
        return codes
    
    def enable_2fa(self):
        """Enable two-factor authentication"""
        self.is_enabled = True
        self.enabled_at = timezone.now()
        if not self.backup_codes:
            self.generate_backup_codes()
        self.save()
    
    def disable_2fa(self):
        """Disable two-factor authentication"""
        self.is_enabled = False
        self.enabled_at = None
        self.backup_codes = []
        self.recovery_codes_used = []
        self.save()


class LoginAttempt(models.Model):
    """
    Track login attempts for security monitoring
    """
    ATTEMPT_TYPE_CHOICES = [
        ('password', 'Password Login'),
        ('2fa', 'Two-Factor Authentication'),
        ('backup_code', 'Backup Code'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts', null=True, blank=True)
    
    # Attempt Details
    username = models.CharField(max_length=150)  # Store even if user doesn't exist
    attempt_type = models.CharField(max_length=20, choices=ATTEMPT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Technical Details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    
    # Security
    failure_reason = models.CharField(max_length=200, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'login_attempts'
        indexes = [
            models.Index(fields=['username', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.attempt_type} - {self.status}"
    
    @classmethod
    def is_blocked(cls, username, ip_address):
        """Check if user/IP is temporarily blocked due to failed attempts"""
        from datetime import timedelta
        
        # Check failed attempts in last 15 minutes
        recent_failures = cls.objects.filter(
            username=username,
            status='failed',
            created_at__gte=timezone.now() - timedelta(minutes=15)
        ).count()
        
        # Block after 5 failed attempts
        return recent_failures >= 5


class ConsentRecord(models.Model):
    """
    Track user consent for data processing and recording
    """
    CONSENT_TYPE_CHOICES = [
        ('call_recording', 'Call Recording'),
        ('transcription', 'Transcription Processing'),
        ('ai_analysis', 'AI Analysis'),
        ('data_storage', 'Data Storage'),
        ('analytics', 'Analytics Processing'),
        ('marketing', 'Marketing Communications'),
        ('third_party_sharing', 'Third Party Data Sharing'),
    ]
    
    STATUS_CHOICES = [
        ('granted', 'Granted'),
        ('denied', 'Denied'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consent_records')
    
    # Consent Details
    consent_type = models.CharField(max_length=50, choices=CONSENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='granted')
    
    # Legal Basis
    legal_basis = models.CharField(max_length=100, blank=True, null=True)
    purpose = models.TextField(help_text="Purpose for which consent is granted")
    
    # Consent Metadata
    granted_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Technical Details
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    consent_method = models.CharField(max_length=50, default='web_form')
    
    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'consent_records'
        unique_together = ['user', 'consent_type']
        indexes = [
            models.Index(fields=['user', 'consent_type']),
            models.Index(fields=['status', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.consent_type} - {self.status}"

    @property
    def is_active(self):
        """Check if consent is currently active"""
        if self.status != 'granted':
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        return True

    def withdraw_consent(self):
        """Withdraw consent"""
        self.status = 'withdrawn'
        self.withdrawn_at = timezone.now()
        self.save()

    def renew_consent(self, expires_at=None):
        """Renew consent"""
        self.status = 'granted'
        self.withdrawn_at = None
        self.expires_at = expires_at
        self.save()


class DataRetentionPolicy(models.Model):
    """
    Define data retention policies for different data types
    """
    DATA_TYPE_CHOICES = [
        ('meeting_transcripts', 'Meeting Transcripts'),
        ('call_recordings', 'Call Recordings'),
        ('user_profiles', 'User Profiles'),
        ('login_attempts', 'Login Attempts'),
        ('activity_logs', 'Activity Logs'),
        ('consent_records', 'Consent Records'),
        ('crm_sync_data', 'CRM Sync Data'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Policy Details
    data_type = models.CharField(max_length=50, choices=DATA_TYPE_CHOICES, unique=True)
    retention_period_days = models.IntegerField(help_text="Number of days to retain data")
    
    # Policy Rules
    auto_delete_enabled = models.BooleanField(default=True)
    archive_before_delete = models.BooleanField(default=True)
    require_user_consent = models.BooleanField(default=False)
    
    # Legal Requirements
    legal_basis = models.CharField(max_length=200, blank=True, null=True)
    regulatory_requirement = models.CharField(max_length=200, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'data_retention_policies'
        indexes = [
            models.Index(fields=['data_type']),
            models.Index(fields=['auto_delete_enabled']),
        ]

    def __str__(self):
        return f"{self.data_type} - {self.retention_period_days} days"

    @property
    def retention_period_timedelta(self):
        """Get retention period as timedelta"""
        return timedelta(days=self.retention_period_days)

    def is_data_expired(self, data_created_at):
        """Check if data is expired based on this policy"""
        if not data_created_at:
            return False
        
        expiry_date = data_created_at + self.retention_period_timedelta
        return timezone.now() > expiry_date


class DataDeletionRequest(models.Model):
    """
    Track data deletion requests (GDPR Right to be Forgotten)
    """
    REQUEST_TYPE_CHOICES = [
        ('user_initiated', 'User Initiated'),
        ('admin_initiated', 'Admin Initiated'),
        ('automated', 'Automated Retention Policy'),
        ('legal_request', 'Legal Request'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Request Details
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deletion_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Scope of Deletion
    data_types = models.JSONField(default=list, help_text="List of data types to delete")
    include_backups = models.BooleanField(default=True)
    include_logs = models.BooleanField(default=False)
    
    # Processing Details
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Results
    deleted_records_count = models.JSONField(default=dict, help_text="Count of deleted records by type")
    error_message = models.TextField(blank=True, null=True)
    
    # Legal/Audit
    legal_basis = models.CharField(max_length=200, blank=True, null=True)
    retention_override = models.BooleanField(default=False, help_text="Override retention policies")
    
    # Metadata
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='initiated_deletions')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_deletions')
    
    class Meta:
        db_table = 'data_deletion_requests'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['request_type', 'status']),
            models.Index(fields=['requested_at']),
        ]

    def __str__(self):
        return f"Deletion request for {self.user.username} - {self.status}"

    def start_processing(self, processor_user):
        """Start processing the deletion request"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.processed_by = processor_user
        self.save()

    def mark_completed(self, deleted_counts):
        """Mark deletion request as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.deleted_records_count = deleted_counts
        self.save()

    def mark_failed(self, error_message):
        """Mark deletion request as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()


class EncryptedDataField(models.Model):
    """
    Store encrypted sensitive data with metadata
    """
    FIELD_TYPE_CHOICES = [
        ('transcript', 'Meeting Transcript'),
        ('pii', 'Personally Identifiable Information'),
        ('financial', 'Financial Information'),
        ('health', 'Health Information'),
        ('biometric', 'Biometric Data'),
        ('other', 'Other Sensitive Data'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Data Classification
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    sensitivity_level = models.IntegerField(default=1, help_text="1=Low, 2=Medium, 3=High, 4=Critical")
    
    # Encrypted Data
    encrypted_data = models.TextField()
    data_hash = models.CharField(max_length=64, blank=True, null=True, help_text="Hash for searching")
    
    # Encryption Metadata
    encryption_algorithm = models.CharField(max_length=50, default='Fernet')
    key_version = models.CharField(max_length=10, default='1.0')
    encrypted_at = models.DateTimeField(auto_now_add=True)
    
    # Access Control
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='encrypted_data')
    access_level = models.CharField(max_length=20, default='owner_only')
    
    # Audit Trail
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(blank=True, null=True)
    access_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'encrypted_data_fields'
        indexes = [
            models.Index(fields=['owner', 'field_type']),
            models.Index(fields=['sensitivity_level']),
            models.Index(fields=['data_hash']),
        ]

    def __str__(self):
        return f"{self.field_type} data for {self.owner.username}"

    def record_access(self):
        """Record data access for audit trail"""
        self.last_accessed = timezone.now()
        self.access_count += 1
        self.save(update_fields=['last_accessed', 'access_count'])

    @property
    def is_high_sensitivity(self):
        """Check if data is high sensitivity"""
        return self.sensitivity_level >= 3


class PrivacySettings(models.Model):
    """
    User privacy settings and preferences
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='privacy_settings')
    
    # Data Processing Preferences
    allow_ai_analysis = models.BooleanField(default=True)
    allow_transcript_storage = models.BooleanField(default=True)
    allow_analytics_processing = models.BooleanField(default=True)
    allow_third_party_integrations = models.BooleanField(default=True)
    
    # Data Sharing Preferences
    share_anonymized_data = models.BooleanField(default=False)
    share_with_team_members = models.BooleanField(default=True)
    share_with_managers = models.BooleanField(default=True)
    
    # Retention Preferences
    auto_delete_transcripts = models.BooleanField(default=False)
    transcript_retention_days = models.IntegerField(default=2555, help_text="Days to keep transcripts")
    
    # Communication Preferences
    privacy_policy_updates = models.BooleanField(default=True)
    data_breach_notifications = models.BooleanField(default=True)
    consent_renewal_reminders = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'privacy_settings'

    def __str__(self):
        return f"Privacy settings for {self.user.username}"

    def get_effective_retention_days(self):
        """Get effective retention period considering user preferences and policies"""
        if self.auto_delete_transcripts:
            return min(self.transcript_retention_days, 
                      getattr(settings, 'MAX_USER_RETENTION_DAYS', 2555))
        return getattr(settings, 'DEFAULT_RETENTION_DAYS', 2555)