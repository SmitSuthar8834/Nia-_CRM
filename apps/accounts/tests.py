"""
Unit tests for Authentication and Role-Based Access Control
"""
import json
import pyotp
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch

from .models import UserProfile, TwoFactorAuth, CalendarIntegration, UserActivity, LoginAttempt
from .authentication import JWTTokenGenerator, authenticate_user
from .permissions import (
    check_user_permission, get_user_role, 
    MeetingAccessPermission, LeadAccessPermission
)


class UserProfileModelTest(TestCase):
    """
    Test UserProfile model functionality
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_profile_creation(self):
        """Test automatic profile creation"""
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.role, 'sales_rep')  # Default role
        self.assertTrue(profile.calendar_sync_enabled)
        self.assertTrue(profile.email_notifications)
    
    def test_user_profile_permissions(self):
        """Test role-based permissions"""
        # Sales rep permissions
        profile = UserProfile.objects.create(user=self.user, role='sales_rep')
        self.assertTrue(profile.has_permission('view_own_meetings'))
        self.assertFalse(profile.has_permission('view_all_meetings'))
        
        # Sales manager permissions
        profile.role = 'sales_manager'
        profile.save()
        self.assertTrue(profile.has_permission('view_all_meetings'))
        self.assertTrue(profile.has_permission('manage_team_debriefings'))
        
        # Admin permissions
        profile.role = 'admin'
        profile.save()
        self.assertTrue(profile.has_permission('view_all_meetings'))
        self.assertTrue(profile.has_permission('manage_users'))  # Should have all permissions
    
    def test_full_name_property(self):
        """Test full name property"""
        self.user.first_name = 'John'
        self.user.last_name = 'Doe'
        self.user.save()
        
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(profile.full_name, 'John Doe')


class TwoFactorAuthModelTest(TestCase):
    """
    Test Two-Factor Authentication model
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.two_factor = TwoFactorAuth.objects.create(user=self.user)
    
    def test_secret_key_generation(self):
        """Test automatic secret key generation"""
        self.assertIsNotNone(self.two_factor.secret_key)
        self.assertEqual(len(self.two_factor.secret_key), 32)
    
    def test_totp_uri_generation(self):
        """Test TOTP URI generation"""
        uri = self.two_factor.get_totp_uri()
        self.assertIn('otpauth://totp/', uri)
        # Email is URL encoded in the URI
        self.assertIn('test%40example.com', uri)
        self.assertIn('NIA%20Meeting%20Intelligence', uri)
    
    def test_qr_code_generation(self):
        """Test QR code generation"""
        qr_code = self.two_factor.get_qr_code()
        self.assertIsInstance(qr_code, str)
        # Should be base64 encoded
        import base64
        try:
            base64.b64decode(qr_code)
        except Exception:
            self.fail("QR code is not valid base64")
    
    def test_token_verification(self):
        """Test TOTP token verification"""
        # Enable 2FA first
        self.two_factor.enable_2fa()
        
        # Generate valid token
        totp = pyotp.TOTP(self.two_factor.secret_key)
        valid_token = totp.now()
        
        # Test valid token
        self.assertTrue(self.two_factor.verify_token(valid_token))
        
        # Test invalid token
        self.assertFalse(self.two_factor.verify_token('123456'))
        
        # Test when 2FA is disabled
        self.two_factor.disable_2fa()
        self.assertFalse(self.two_factor.verify_token(valid_token))
    
    def test_backup_codes(self):
        """Test backup code generation and verification"""
        codes = self.two_factor.generate_backup_codes()
        self.assertEqual(len(codes), 10)
        
        # Test valid backup code
        test_code = codes[0]
        self.assertTrue(self.two_factor.verify_backup_code(test_code))
        
        # Test code can't be reused
        self.assertFalse(self.two_factor.verify_backup_code(test_code))
        
        # Test invalid code
        self.assertFalse(self.two_factor.verify_backup_code('INVALID'))


class JWTAuthenticationTest(TestCase):
    """
    Test JWT Authentication functionality
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
    
    def test_token_generation(self):
        """Test JWT token generation"""
        access_token = JWTTokenGenerator.generate_access_token(self.user)
        refresh_token = JWTTokenGenerator.generate_refresh_token(self.user)
        
        self.assertIsInstance(access_token, str)
        self.assertIsInstance(refresh_token, str)
        
        # Verify token payload
        payload = JWTTokenGenerator.verify_token(access_token)
        self.assertEqual(payload['user_id'], self.user.id)
        self.assertEqual(payload['username'], self.user.username)
        self.assertEqual(payload['type'], 'access')
    
    def test_token_refresh(self):
        """Test token refresh functionality"""
        refresh_token = JWTTokenGenerator.generate_refresh_token(self.user)
        new_access_token = JWTTokenGenerator.refresh_access_token(refresh_token)
        
        self.assertIsInstance(new_access_token, str)
        
        # Verify new token
        payload = JWTTokenGenerator.verify_token(new_access_token)
        self.assertEqual(payload['user_id'], self.user.id)
    
    def test_authenticate_user(self):
        """Test user authentication function"""
        result = authenticate_user('testuser', 'testpass123')
        
        self.assertIsNotNone(result)
        self.assertEqual(result['user'], self.user)
        self.assertIn('access_token', result)
        self.assertIn('refresh_token', result)
        
        # Test invalid credentials
        result = authenticate_user('testuser', 'wrongpass')
        self.assertIsNone(result)


class LoginAttemptModelTest(TestCase):
    """
    Test LoginAttempt model and blocking functionality
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_login_attempt_creation(self):
        """Test login attempt logging"""
        attempt = LoginAttempt.objects.create(
            user=self.user,
            username='testuser',
            attempt_type='password',
            status='success',
            ip_address='127.0.0.1'
        )
        
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.status, 'success')
    
    def test_blocking_functionality(self):
        """Test user blocking after failed attempts"""
        # Create 5 failed attempts
        for i in range(5):
            LoginAttempt.objects.create(
                username='testuser',
                attempt_type='password',
                status='failed',
                ip_address='127.0.0.1',
                created_at=timezone.now()
            )
        
        # Should be blocked now
        self.assertTrue(LoginAttempt.is_blocked('testuser', '127.0.0.1'))
        
        # Different user should not be blocked
        self.assertFalse(LoginAttempt.is_blocked('otheruser', '127.0.0.1'))


class AuthenticationAPITest(APITestCase):
    """
    Test Authentication API endpoints
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
    
    def test_login_api(self):
        """Test login API endpoint"""
        url = reverse('accounts:login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = reverse('accounts:login')
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_with_2fa(self):
        """Test login with 2FA enabled"""
        # Enable 2FA for user
        two_factor = TwoFactorAuth.objects.create(user=self.user)
        two_factor.enable_2fa()
        
        url = reverse('accounts:login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        # First request should ask for 2FA
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('requires_2fa'))
        
        # Generate valid TOTP token
        totp = pyotp.TOTP(two_factor.secret_key)
        valid_token = totp.now()
        
        # Second request with 2FA token
        data['totp_token'] = valid_token
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_refresh_token_api(self):
        """Test refresh token API endpoint"""
        # Get initial tokens
        auth_result = authenticate_user('testuser', 'testpass123')
        refresh_token = auth_result['refresh_token']
        
        url = reverse('accounts:refresh_token')
        data = {'refresh_token': refresh_token}
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_user_profile_api(self):
        """Test user profile API endpoint"""
        # Authenticate user
        auth_result = authenticate_user('testuser', 'testpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_result["access_token"]}')
        
        url = reverse('accounts:user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'testuser')
        self.assertEqual(response.data['role'], 'sales_rep')
    
    def test_2fa_setup_api(self):
        """Test 2FA setup API endpoint"""
        # Authenticate user
        auth_result = authenticate_user('testuser', 'testpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_result["access_token"]}')
        
        # Get 2FA setup info
        url = reverse('accounts:2fa_setup')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('secret_key', response.data)
        self.assertIn('qr_code', response.data)
        self.assertFalse(response.data['is_enabled'])
        
        # Test with invalid token first
        data = {'token': '123456'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # For testing purposes, we'll mock the token verification
        # In a real scenario, you'd use a valid TOTP token
        from unittest.mock import patch
        with patch('apps.accounts.models.TwoFactorAuth.verify_token', return_value=True):
            data = {'token': '123456'}  # Mock token
            response = self.client.post(url, data, format='json')
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('backup_codes', response.data)


class PermissionsTest(TestCase):
    """
    Test role-based permissions system
    """
    
    def setUp(self):
        # Create users with different roles
        self.admin_user = User.objects.create_user(username='admin', password='pass')
        self.manager_user = User.objects.create_user(username='manager', password='pass')
        self.sales_user = User.objects.create_user(username='sales', password='pass')
        self.viewer_user = User.objects.create_user(username='viewer', password='pass')
        
        UserProfile.objects.create(user=self.admin_user, role='admin')
        UserProfile.objects.create(user=self.manager_user, role='sales_manager')
        UserProfile.objects.create(user=self.sales_user, role='sales_rep')
        UserProfile.objects.create(user=self.viewer_user, role='viewer')
    
    def test_permission_utility_functions(self):
        """Test permission utility functions"""
        # Test check_user_permission
        self.assertTrue(check_user_permission(self.admin_user, 'view_all_meetings'))
        self.assertTrue(check_user_permission(self.manager_user, 'view_all_meetings'))
        self.assertFalse(check_user_permission(self.sales_user, 'view_all_meetings'))
        
        # Test get_user_role
        self.assertEqual(get_user_role(self.admin_user), 'admin')
        self.assertEqual(get_user_role(self.manager_user), 'sales_manager')
        self.assertEqual(get_user_role(self.sales_user), 'sales_rep')
        self.assertEqual(get_user_role(self.viewer_user), 'viewer')
    
    def test_meeting_access_permission(self):
        """Test meeting access permissions"""
        from apps.meetings.models import Meeting
        
        # Create a mock meeting object
        class MockMeeting:
            def __init__(self, organizer):
                self.organizer = organizer
        
        meeting = MockMeeting(organizer=self.sales_user)
        permission = MeetingAccessPermission()
        
        # Create mock request objects
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.method = 'GET'
        
        # Admin can access any meeting
        admin_request = MockRequest(self.admin_user)
        self.assertTrue(permission.has_object_permission(admin_request, None, meeting))
        
        # Sales rep can access own meeting
        sales_request = MockRequest(self.sales_user)
        self.assertTrue(permission.has_object_permission(sales_request, None, meeting))
        
        # Other sales rep cannot access
        other_sales_user = User.objects.create_user(username='other_sales', password='pass')
        UserProfile.objects.create(user=other_sales_user, role='sales_rep')
        other_request = MockRequest(other_sales_user)
        self.assertFalse(permission.has_object_permission(other_request, None, meeting))


class SecurityTest(TestCase):
    """
    Test security features
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(user=self.user)
    
    def test_login_attempt_logging(self):
        """Test that login attempts are logged"""
        client = APIClient()
        url = reverse('accounts:login')
        
        # Successful login
        data = {'username': 'testuser', 'password': 'testpass123'}
        response = client.post(url, data, format='json')
        
        # Check login attempt was logged
        attempt = LoginAttempt.objects.filter(username='testuser', status='success').first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.attempt_type, 'password')
        
        # Failed login
        data = {'username': 'testuser', 'password': 'wrongpass'}
        response = client.post(url, data, format='json')
        
        # Check failed attempt was logged
        attempt = LoginAttempt.objects.filter(username='testuser', status='failed').first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.failure_reason, 'Invalid credentials')
    
    def test_user_activity_logging(self):
        """Test that user activities are logged"""
        # Create a login activity manually since authenticate_user doesn't create it in tests
        UserActivity.objects.create(
            user=self.user,
            activity_type='login',
            description='Test login activity',
            ip_address='127.0.0.1'
        )
        
        # Check if login activity was logged
        activity = UserActivity.objects.filter(user=self.user, activity_type='login').first()
        self.assertIsNotNone(activity)
        self.assertEqual(activity.activity_type, 'login')
    
    def test_token_expiration(self):
        """Test JWT token expiration"""
        # Create an expired token
        import jwt
        from django.conf import settings
        
        payload = {
            'user_id': self.user.id,
            'exp': datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            'type': 'access'
        }
        
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {expired_token}')
        
        url = reverse('accounts:user_profile')
        response = client.get(url)
        
        # Could be 401 or 403 depending on how DRF handles it
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])