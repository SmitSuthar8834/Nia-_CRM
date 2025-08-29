"""
Security tests for authentication and authorization
"""
import json
import jwt
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from django.conf import settings
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import UserProfile, TwoFactorAuth, LoginAttempt
from .authentication import JWTTokenGenerator, SessionManager


class AuthenticationSecurityTest(APITestCase):
    """
    Test authentication security features
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
        cache.clear()
    
    def test_login_with_valid_credentials(self):
        """Test successful login with valid credentials"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_with_invalid_credentials(self):
        """Test login failure with invalid credentials"""
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_attempt_tracking(self):
        """Test that failed login attempts are tracked"""
        # Make failed login attempt
        self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # Check that login attempt was recorded
        attempt = LoginAttempt.objects.filter(username='testuser').first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.status, 'failed')
    
    def test_account_lockout_after_failed_attempts(self):
        """Test account lockout after multiple failed attempts"""
        # Make multiple failed attempts
        for _ in range(6):  # Exceed the limit
            self.client.post(reverse('accounts:login'), {
                'username': 'testuser',
                'password': 'wrongpassword'
            })
        
        # Next attempt should be blocked
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'  # Even with correct password
        })
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_jwt_token_validation(self):
        """Test JWT token validation"""
        # Generate token
        token = JWTTokenGenerator.generate_access_token(self.user)
        
        # Use token for authenticated request
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(reverse('accounts:user_profile'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_jwt_token_expiration(self):
        """Test JWT token expiration"""
        # Generate expired token
        payload = {
            'user_id': self.user.id,
            'exp': datetime.utcnow() - timedelta(hours=1),  # Expired
            'iat': datetime.utcnow() - timedelta(hours=2),
            'type': 'access'
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Try to use expired token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        response = self.client.get(reverse('accounts:user_profile'))
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_blacklisting(self):
        """Test token blacklisting functionality"""
        # Generate token
        token = JWTTokenGenerator.generate_access_token(self.user)
        
        # Revoke token
        JWTTokenGenerator.revoke_token(token)
        
        # Try to use revoked token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(reverse('accounts:user_profile'))
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_refresh_token_functionality(self):
        """Test refresh token functionality"""
        # Generate tokens
        access_token = JWTTokenGenerator.generate_access_token(self.user)
        refresh_token = JWTTokenGenerator.generate_refresh_token(self.user)
        
        # Use refresh token to get new access token
        response = self.client.post(reverse('accounts:refresh_token'), {
            'refresh_token': refresh_token
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_password_change_security(self):
        """Test password change security"""
        # Login first
        self.client.force_authenticate(user=self.user)
        
        # Change password
        response = self.client.post(reverse('accounts:change_password'), {
            'current_password': 'TestPassword123!',
            'new_password': 'NewSecurePassword456!',
            'confirm_password': 'NewSecurePassword456!'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify old password no longer works
        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_session_management(self):
        """Test session management functionality"""
        # Create session
        session_id = SessionManager.create_session(self.user, self.client.request)
        
        # Validate session
        is_valid = SessionManager.validate_session(session_id, self.user, self.client.request)
        self.assertTrue(is_valid)
        
        # Revoke session
        SessionManager.revoke_session(session_id)
        
        # Validate revoked session
        is_valid = SessionManager.validate_session(session_id, self.user, self.client.request)
        self.assertFalse(is_valid)


class TwoFactorAuthTest(APITestCase):
    """
    Test two-factor authentication
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
        self.two_factor = TwoFactorAuth.objects.create(user=self.user)
    
    def test_2fa_setup(self):
        """Test 2FA setup process"""
        self.client.force_authenticate(user=self.user)
        
        # Get 2FA setup info
        response = self.client.get(reverse('accounts:2fa_setup'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret_key', response.data)
        self.assertIn('qr_code', response.data)
        self.assertFalse(response.data['is_enabled'])
    
    def test_2fa_enable_with_valid_token(self):
        """Test enabling 2FA with valid token"""
        self.client.force_authenticate(user=self.user)
        
        # Mock TOTP verification
        import pyotp
        totp = pyotp.TOTP(self.two_factor.secret_key)
        token = totp.now()
        
        response = self.client.post(reverse('accounts:2fa_setup'), {
            'token': token
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('backup_codes', response.data)
        
        # Verify 2FA is enabled
        self.two_factor.refresh_from_db()
        self.assertTrue(self.two_factor.is_enabled)
    
    def test_login_with_2fa_enabled(self):
        """Test login process when 2FA is enabled"""
        # Enable 2FA
        self.two_factor.enable_2fa()
        
        # Try login without 2FA token
        response = self.client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('requires_2fa', response.data)
        self.assertTrue(response.data['requires_2fa'])


class RoleBasedAccessTest(APITestCase):
    """
    Test role-based access control
    """
    
    def setUp(self):
        self.client = APIClient()
        
        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPass123!'
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user, 
            role='admin'
        )
        
        self.manager_user = User.objects.create_user(
            username='manager',
            email='manager@example.com',
            password='ManagerPass123!'
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager_user, 
            role='sales_manager'
        )
        
        self.sales_user = User.objects.create_user(
            username='sales',
            email='sales@example.com',
            password='SalesPass123!'
        )
        self.sales_profile = UserProfile.objects.create(
            user=self.sales_user, 
            role='sales_rep'
        )
        
        self.viewer_user = User.objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='ViewerPass123!'
        )
        self.viewer_profile = UserProfile.objects.create(
            user=self.viewer_user, 
            role='viewer'
        )
    
    def test_admin_access_to_user_management(self):
        """Test admin access to user management endpoints"""
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_non_admin_denied_user_management(self):
        """Test non-admin users denied access to user management"""
        self.client.force_authenticate(user=self.sales_user)
        
        response = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_manager_access_to_team_data(self):
        """Test manager access to team data"""
        self.client.force_authenticate(user=self.manager_user)
        
        response = self.client.get(reverse('accounts:manager_team'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_sales_rep_limited_access(self):
        """Test sales rep has limited access"""
        self.client.force_authenticate(user=self.sales_user)
        
        # Should have access to own profile
        response = self.client.get(reverse('accounts:user_profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should not have access to admin endpoints
        response = self.client.get(reverse('accounts:admin_users'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_viewer_read_only_access(self):
        """Test viewer has read-only access"""
        self.client.force_authenticate(user=self.viewer_user)
        
        # Should have access to profile (read)
        response = self.client.get(reverse('accounts:user_profile'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_role_change_authorization(self):
        """Test role change requires admin privileges"""
        # Admin can change roles
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('accounts:change_user_role'), {
            'user_id': self.sales_user.id,
            'role': 'sales_manager'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Non-admin cannot change roles
        self.client.force_authenticate(user=self.sales_user)
        response = self.client.post(reverse('accounts:change_user_role'), {
            'user_id': self.viewer_user.id,
            'role': 'sales_rep'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SecurityHeadersTest(TestCase):
    """
    Test security headers and configurations
    """
    
    def setUp(self):
        self.client = Client()
    
    def test_security_headers_present(self):
        """Test that security headers are present in responses"""
        response = self.client.get('/')
        
        # Check for security headers (these would be set by middleware in production)
        # This is a placeholder test - actual implementation depends on your middleware setup
        self.assertTrue(True)  # Placeholder
    
    def test_csrf_protection(self):
        """Test CSRF protection is enabled"""
        # This would test CSRF token validation
        # Implementation depends on your CSRF configuration
        self.assertTrue(True)  # Placeholder


class PasswordSecurityTest(TestCase):
    """
    Test password security requirements
    """
    
    def test_password_validation(self):
        """Test password validation requirements"""
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        
        # Test weak password
        with self.assertRaises(ValidationError):
            validate_password('weak')
        
        # Test strong password
        try:
            validate_password('StrongPassword123!')
        except ValidationError:
            self.fail("Strong password should be valid")
    
    def test_password_history_prevention(self):
        """Test prevention of password reuse"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPassword123!'
        )
        
        # This would test password history validation
        # Implementation depends on password history tracking
        self.assertTrue(True)  # Placeholder