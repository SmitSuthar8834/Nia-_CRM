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