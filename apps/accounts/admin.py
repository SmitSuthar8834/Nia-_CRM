"""
Admin configuration for Accounts app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, TwoFactorAuth, CalendarIntegration, UserActivity, LoginAttempt


class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile
    """
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = [
        'role', 'phone', 'department', 'title', 'timezone',
        'calendar_sync_enabled', 'email_notifications', 'debriefing_reminders',
        'meeting_alerts', 'ai_coaching_enabled', 'auto_debriefing_scheduling'
    ]


class UserAdmin(BaseUserAdmin):
    """
    Extended User admin with profile
    """
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'is_active', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'profile__role', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    def get_role(self, obj):
        """Get user role from profile"""
        return obj.profile.role if hasattr(obj, 'profile') else 'No Profile'
    get_role.short_description = 'Role'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin for UserProfile
    """
    list_display = [
        'user', 'role', 'department', 'title', 'timezone',
        'calendar_sync_enabled', 'created_at'
    ]
    list_filter = ['role', 'department', 'timezone', 'calendar_sync_enabled', 'created_at']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login_ip']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'role', 'permissions')
        }),
        ('Profile Details', {
            'fields': ('phone', 'department', 'title', 'timezone')
        }),
        ('Calendar Integration', {
            'fields': ('google_calendar_connected', 'outlook_calendar_connected', 'calendar_sync_enabled')
        }),
        ('Notification Preferences', {
            'fields': ('email_notifications', 'debriefing_reminders', 'meeting_alerts')
        }),
        ('AI Preferences', {
            'fields': ('ai_coaching_enabled', 'auto_debriefing_scheduling')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'last_login_ip'),
            'classes': ('collapse',)
        })
    )


@admin.register(TwoFactorAuth)
class TwoFactorAuthAdmin(admin.ModelAdmin):
    """
    Admin for Two-Factor Authentication
    """
    list_display = ['user', 'is_enabled', 'created_at', 'enabled_at', 'last_used']
    list_filter = ['is_enabled', 'created_at', 'enabled_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['id', 'secret_key', 'created_at', 'enabled_at', 'last_used']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('2FA Configuration', {
            'fields': ('secret_key', 'is_enabled', 'backup_codes', 'recovery_codes_used')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'enabled_at', 'last_used'),
            'classes': ('collapse',)
        })
    )
    
    def has_change_permission(self, request, obj=None):
        """Limit 2FA changes to admins only"""
        return request.user.is_superuser


@admin.register(CalendarIntegration)
class CalendarIntegrationAdmin(admin.ModelAdmin):
    """
    Admin for Calendar Integration
    """
    list_display = [
        'user', 'provider', 'provider_email', 'status',
        'sync_enabled', 'last_sync', 'error_count'
    ]
    list_filter = ['provider', 'status', 'sync_enabled', 'created_at']
    search_fields = ['user__username', 'provider_email']
    readonly_fields = [
        'id', 'provider_user_id', 'access_token', 'refresh_token',
        'token_expires_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('User & Provider', {
            'fields': ('user', 'provider', 'provider_user_id', 'provider_email')
        }),
        ('Connection Status', {
            'fields': ('status', 'last_sync', 'next_sync', 'error_message', 'error_count')
        }),
        ('Settings', {
            'fields': ('sync_enabled', 'sync_interval_minutes')
        }),
        ('Authentication (Sensitive)', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """
    Admin for User Activity
    """
    list_display = [
        'user', 'activity_type', 'description', 'entity_type',
        'ip_address', 'created_at'
    ]
    list_filter = ['activity_type', 'entity_type', 'created_at']
    search_fields = ['user__username', 'description', 'ip_address']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Activity', {
            'fields': ('user', 'activity_type', 'description')
        }),
        ('Context', {
            'fields': ('entity_type', 'entity_id')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'session_id')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of activity logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make activity logs read-only"""
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """
    Admin for Login Attempts
    """
    list_display = [
        'username', 'attempt_type', 'status', 'ip_address',
        'failure_reason', 'created_at'
    ]
    list_filter = ['attempt_type', 'status', 'created_at']
    search_fields = ['username', 'ip_address', 'failure_reason']
    readonly_fields = ['id', 'created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Attempt Details', {
            'fields': ('user', 'username', 'attempt_type', 'status')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Security', {
            'fields': ('failure_reason',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation of login attempts"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make login attempts read-only"""
        return False


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)