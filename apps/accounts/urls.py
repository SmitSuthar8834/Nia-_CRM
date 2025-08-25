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