"""
Privacy and GDPR compliance tests
"""
import json
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import (
    UserProfile, ConsentRecord, PrivacySettings, DataRetentionPolicy,
    DataDeletionRequest, EncryptedDataField
)
from .encryption import DataEncryption, PIIEncryption, TranscriptEncryption


class ConsentManagementTest(APITestCase):
    """
    Test consent management functionality
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
    
    def test_grant_consent(self):
        """Test granting consent for data processing"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(reverse('accounts:consent_management'), {
            'consent_type': 'call_recording',
            'status': 'granted'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify consent was recorded
        consent = ConsentRecord.objects.get(user=self.user, consent_type='call_recording')
        self.assertEqual(consent.status, 'granted')
        self.assertTrue(consent.is_active)
    
    def test_withdraw_consent(self):
        """Test withdrawing consent"""
        # First grant consent
        ConsentRecord.objects.create(
            user=self.user,
            consent_type='transcription',
            status='granted',
            purpose='Test consent'
        )
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(reverse('accounts:consent_management'), {
            'consent_type': 'transcription',
            'status': 'denied'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify consent was withdrawn
        consent = ConsentRecord.objects.get(user=self.user, consent_type='transcription')
        self.assertEqual(consent.status, 'denied')
        self.assertFalse(consent.is_active)
    
    def test_get_consent_status(self):
        """Test retrieving consent status"""
        # Create some consent records
        ConsentRecord.objects.create(
            user=self.user,
            consent_type='ai_analysis',
            status='granted',
            purpose='AI analysis consent'
        )
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:consent_management'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('consents', response.data)
        self.assertEqual(len(response.data['consents']), 1)
        self.assertEqual(response.data['consents'][0]['consent_type'], 'ai_analysis')
    
    def test_consent_expiration(self):
        """Test consent expiration functionality"""
        # Create expired consent
        expired_consent = ConsentRecord.objects.create(
            user=self.user,
            consent_type='marketing',
            status='granted',
            purpose='Marketing consent',
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        self.assertFalse(expired_consent.is_active)


class PrivacySettingsTest(APITestCase):
    """
    Test privacy settings functionality
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
    
    def test_get_privacy_settings(self):
        """Test retrieving privacy settings"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:privacy_settings'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Settings should be created automatically if they don't exist
        self.assertTrue(PrivacySettings.objects.filter(user=self.user).exists())
    
    def test_update_privacy_settings(self):
        """Test updating privacy settings"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.put(reverse('accounts:privacy_settings'), {
            'allow_ai_analysis': False,
            'allow_transcript_storage': True,
            'auto_delete_transcripts': True,
            'transcript_retention_days': 365
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify settings were updated
        settings = PrivacySettings.objects.get(user=self.user)
        self.assertFalse(settings.allow_ai_analysis)
        self.assertTrue(settings.allow_transcript_storage)
        self.assertTrue(settings.auto_delete_transcripts)
        self.assertEqual(settings.transcript_retention_days, 365)


class DataExportTest(APITestCase):
    """
    Test data export functionality (GDPR compliance)
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
        
        # Create some test data
        ConsentRecord.objects.create(
            user=self.user,
            consent_type='call_recording',
            status='granted',
            purpose='Test consent'
        )
        
        PrivacySettings.objects.create(
            user=self.user,
            allow_ai_analysis=True,
            transcript_retention_days=365
        )
    
    def test_export_user_data_json(self):
        """Test exporting user data as JSON"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:data_export'), {'format': 'json'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Parse response content
        data = json.loads(response.content)
        self.assertIn('export_info', data)
        self.assertIn('profile', data)
        self.assertIn('consent_records', data)
        self.assertIn('privacy_settings', data)
    
    def test_export_user_data_csv(self):
        """Test exporting user data as CSV"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:data_export'), {'format': 'csv'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_export_anonymized_data(self):
        """Test exporting anonymized user data"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:data_export'), {
            'format': 'json',
            'anonymize': 'true'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = json.loads(response.content)
        self.assertTrue(data['export_info']['anonymized'])
        # Email should be masked
        self.assertIn('***', data['profile']['email'])


class DataDeletionTest(APITestCase):
    """
    Test data deletion functionality (Right to be Forgotten)
    """
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(user=self.user, role='sales_rep')
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPass123!'
        )
        self.admin_profile = UserProfile.objects.create(user=self.admin_user, role='admin')
    
    def test_create_deletion_request(self):
        """Test creating a data deletion request"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post(reverse('accounts:data_deletion'), {
            'data_types': ['meeting_transcripts', 'activity_logs'],
            'include_backups': True,
            'reason': 'User requested data deletion'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('request_id', response.data)
        
        # Verify deletion request was created
        request_obj = DataDeletionRequest.objects.get(user=self.user)
        self.assertEqual(request_obj.status, 'pending')
        self.assertEqual(request_obj.data_types, ['meeting_transcripts', 'activity_logs'])
    
    def test_get_deletion_requests(self):
        """Test retrieving deletion requests"""
        # Create a deletion request
        DataDeletionRequest.objects.create(
            user=self.user,
            request_type='user_initiated',
            data_types=['meeting_transcripts'],
            requested_by=self.user
        )
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(reverse('accounts:data_deletion'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deletion_requests', response.data)
        self.assertEqual(len(response.data['deletion_requests']), 1)
    
    def test_process_deletion_request_admin(self):
        """Test admin processing of deletion request"""
        # Create a deletion request
        deletion_request = DataDeletionRequest.objects.create(
            user=self.user,
            request_type='user_initiated',
            data_types=['activity_logs'],
            requested_by=self.user
        )
        
        # Create some encrypted data to delete
        EncryptedDataField.objects.create(
            owner=self.user,
            field_type='transcript',
            encrypted_data='encrypted_test_data',
            sensitivity_level=2
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        response = self.client.post(
            reverse('accounts:process_deletion_request', args=[deletion_request.id])
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('deleted_counts', response.data)
        
        # Verify request was processed
        deletion_request.refresh_from_db()
        self.assertEqual(deletion_request.status, 'completed')


class DataEncryptionTest(TestCase):
    """
    Test data encryption functionality
    """
    
    def test_encrypt_decrypt_text(self):
        """Test basic text encryption and decryption"""
        original_text = "This is sensitive information"
        
        # Encrypt
        encrypted_text = DataEncryption.encrypt_text(original_text)
        self.assertIsNotNone(encrypted_text)
        self.assertNotEqual(encrypted_text, original_text)
        
        # Decrypt
        decrypted_text = DataEncryption.decrypt_text(encrypted_text)
        self.assertEqual(decrypted_text, original_text)
    
    def test_encrypt_decrypt_json(self):
        """Test JSON data encryption and decryption"""
        original_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '555-1234'
        }
        
        # Encrypt
        encrypted_data = DataEncryption.encrypt_json(original_data)
        self.assertIsNotNone(encrypted_data)
        
        # Decrypt
        decrypted_data = DataEncryption.decrypt_json(encrypted_data)
        self.assertEqual(decrypted_data, original_data)
    
    def test_hash_sensitive_data(self):
        """Test hashing sensitive data for indexing"""
        sensitive_data = "john.doe@example.com"
        
        hash1 = DataEncryption.hash_sensitive_data(sensitive_data)
        hash2 = DataEncryption.hash_sensitive_data(sensitive_data)
        
        # Same data should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different data should produce different hash
        hash3 = DataEncryption.hash_sensitive_data("jane.doe@example.com")
        self.assertNotEqual(hash1, hash3)
    
    def test_transcript_encryption(self):
        """Test transcript-specific encryption"""
        transcript_text = "This is a meeting transcript with sensitive information."
        meeting_id = "meeting-123"
        
        # Encrypt
        encrypted_transcript = TranscriptEncryption.encrypt_transcript(transcript_text, meeting_id)
        self.assertIsNotNone(encrypted_transcript)
        
        # Decrypt
        decrypted_transcript = TranscriptEncryption.decrypt_transcript(encrypted_transcript)
        self.assertEqual(decrypted_transcript, transcript_text)
        
        # Get metadata
        metadata = TranscriptEncryption.get_transcript_metadata(encrypted_transcript)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata['meeting_id'], meeting_id)
        self.assertTrue(metadata['has_content'])
    
    def test_pii_encryption_and_masking(self):
        """Test PII encryption and masking"""
        pii_data = {
            'email': 'john.doe@example.com',
            'phone': '555-123-4567',
            'ssn': '123-45-6789'
        }
        
        # Encrypt PII
        encrypted_pii = PIIEncryption.encrypt_pii_data(pii_data)
        self.assertIsNotNone(encrypted_pii)
        
        # Decrypt PII
        decrypted_pii = PIIEncryption.decrypt_pii_data(encrypted_pii)
        self.assertEqual(decrypted_pii, pii_data)
        
        # Test masking
        masked_email = PIIEncryption.mask_pii_for_display('john.doe@example.com', 'email')
        self.assertIn('***', masked_email)
        self.assertTrue(masked_email.endswith('@example.com'))
        
        masked_phone = PIIEncryption.mask_pii_for_display('555-123-4567', 'phone')
        self.assertIn('***', masked_phone)
        self.assertTrue(masked_phone.endswith('4567'))


class DataRetentionTest(TestCase):
    """
    Test data retention policies
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='AdminPass123!'
        )
    
    def test_retention_policy_creation(self):
        """Test creating data retention policies"""
        policy = DataRetentionPolicy.objects.create(
            data_type='meeting_transcripts',
            retention_period_days=365,
            auto_delete_enabled=True,
            legal_basis='Business requirement',
            created_by=self.admin_user
        )
        
        self.assertEqual(policy.data_type, 'meeting_transcripts')
        self.assertEqual(policy.retention_period_days, 365)
        self.assertTrue(policy.auto_delete_enabled)
    
    def test_data_expiration_check(self):
        """Test checking if data is expired based on retention policy"""
        policy = DataRetentionPolicy.objects.create(
            data_type='activity_logs',
            retention_period_days=30,
            created_by=self.admin_user
        )
        
        # Test with recent data (not expired)
        recent_date = timezone.now() - timedelta(days=15)
        self.assertFalse(policy.is_data_expired(recent_date))
        
        # Test with old data (expired)
        old_date = timezone.now() - timedelta(days=45)
        self.assertTrue(policy.is_data_expired(old_date))
    
    def test_privacy_settings_retention(self):
        """Test privacy settings retention calculations"""
        privacy_settings = PrivacySettings.objects.create(
            user=self.user,
            auto_delete_transcripts=True,
            transcript_retention_days=180
        )
        
        effective_days = privacy_settings.get_effective_retention_days()
        self.assertEqual(effective_days, 180)


class ComplianceTest(TestCase):
    """
    Test GDPR and privacy compliance features
    """
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )
    
    def test_consent_audit_trail(self):
        """Test that consent changes are properly tracked"""
        # Grant consent
        consent = ConsentRecord.objects.create(
            user=self.user,
            consent_type='call_recording',
            status='granted',
            purpose='Call recording consent',
            ip_address='192.168.1.100',
            user_agent='Test Browser'
        )
        
        # Verify audit trail
        self.assertIsNotNone(consent.granted_at)
        self.assertEqual(consent.ip_address, '192.168.1.100')
        self.assertEqual(consent.user_agent, 'Test Browser')
        
        # Withdraw consent
        consent.withdraw_consent()
        
        # Verify withdrawal is tracked
        self.assertEqual(consent.status, 'withdrawn')
        self.assertIsNotNone(consent.withdrawn_at)
    
    def test_encrypted_data_access_tracking(self):
        """Test that access to encrypted data is tracked"""
        encrypted_field = EncryptedDataField.objects.create(
            owner=self.user,
            field_type='pii',
            encrypted_data='encrypted_test_data',
            sensitivity_level=3
        )
        
        # Record access
        encrypted_field.record_access()
        
        # Verify access tracking
        self.assertEqual(encrypted_field.access_count, 1)
        self.assertIsNotNone(encrypted_field.last_accessed)
    
    def test_data_anonymization(self):
        """Test data anonymization functionality"""
        from .encryption import DataAnonymization
        
        # Test transcript anonymization
        transcript = "Contact John Doe at john.doe@example.com or call 555-123-4567"
        anonymized = DataAnonymization.anonymize_transcript(transcript)
        
        self.assertNotIn('john.doe@example.com', anonymized)
        self.assertNotIn('555-123-4567', anonymized)
        self.assertIn('[EMAIL_REDACTED]', anonymized)
        self.assertIn('[PHONE_REDACTED]', anonymized)
        
        # Test user data pseudonymization
        user_data = {'name': 'John Doe', 'email': 'john@example.com'}
        pseudonymized = DataAnonymization.pseudonymize_user_data(user_data)
        
        self.assertTrue(pseudonymized['anonymized'])
        self.assertIn('user_', pseudonymized['user_id'])