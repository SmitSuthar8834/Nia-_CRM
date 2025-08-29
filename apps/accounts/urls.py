"""
URL Configuration for Accounts App
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'accounts'

# API URLs
urlpatterns = [
    # Authentication
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('refresh/', views.RefreshTokenView.as_view(), name='refresh_token'),
    
    # User Profile
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('permissions/', views.user_permissions, name='user_permissions'),
    
    # Security Management
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('sessions/', views.ActiveSessionsView.as_view(), name='active_sessions'),
    path('security/', views.SecuritySettingsView.as_view(), name='security_settings'),
    path('revoke-all/', views.RevokeAllTokensView.as_view(), name='revoke_all_tokens'),
    
    # Two-Factor Authentication
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('2fa/backup-codes/', views.TwoFactorBackupCodesView.as_view(), name='2fa_backup_codes'),
    
    # Calendar Integration
    path('calendar/', views.CalendarIntegrationView.as_view(), name='calendar_integration'),
    
    # User Activity
    path('activity/', views.UserActivityView.as_view(), name='user_activity'),
    
    # Admin endpoints
    path('admin/users/', views.AdminUserManagementView.as_view(), name='admin_users'),
    path('admin/change-role/', views.change_user_role, name='change_user_role'),
    
    # Manager endpoints
    path('team/', views.ManagerTeamView.as_view(), name='manager_team'),
]

# Add settings URLs
urlpatterns += [
    path('settings/notifications/', views.notification_settings, name='notification_settings'),
]

# Privacy URLs
from . import privacy_views

urlpatterns += [
    path('privacy/consent/', privacy_views.ConsentManagementView.as_view(), name='consent_management'),
    path('privacy/settings/', privacy_views.PrivacySettingsView.as_view(), name='privacy_settings'),
    path('privacy/export/', privacy_views.DataExportView.as_view(), name='data_export'),
    path('privacy/deletion/', privacy_views.DataDeletionRequestView.as_view(), name='data_deletion'),
    path('privacy/dashboard/', privacy_views.privacy_dashboard, name='privacy_dashboard'),
    
    # Admin privacy endpoints
    path('admin/retention-policies/', privacy_views.AdminDataRetentionView.as_view(), name='admin_retention_policies'),
    path('admin/deletion-requests/<uuid:request_id>/process/', privacy_views.process_deletion_request, name='process_deletion_request'),
]