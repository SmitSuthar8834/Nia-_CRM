"""
Data encryption utilities for sensitive information
"""
import base64
import hashlib
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from django.core.cache import cache


class DataEncryption:
    """
    Utility class for encrypting and decrypting sensitive data
    """
    
    @staticmethod
    def _get_encryption_key():
        """
        Get or generate encryption key from settings
        """
        # In production, this should come from environment variables or key management service
        secret_key = getattr(settings, 'DATA_ENCRYPTION_KEY', settings.SECRET_KEY)
        
        # Derive a proper encryption key from the secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'meeting_intelligence_salt',  # In production, use random salt per data
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return key
    
    @staticmethod
    def encrypt_text(plaintext):
        """
        Encrypt plaintext string
        """
        if not plaintext:
            return None
        
        try:
            key = DataEncryption._get_encryption_key()
            f = Fernet(key)
            encrypted_data = f.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            # Log error in production
            raise Exception(f"Encryption failed: {str(e)}")
    
    @staticmethod
    def decrypt_text(encrypted_text):
        """
        Decrypt encrypted string
        """
        if not encrypted_text:
            return None
        
        try:
            key = DataEncryption._get_encryption_key()
            f = Fernet(key)
            encrypted_data = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted_data = f.decrypt(encrypted_data)
            return decrypted_data.decode()
        except Exception as e:
            # Log error in production
            raise Exception(f"Decryption failed: {str(e)}")
    
    @staticmethod
    def encrypt_json(data):
        """
        Encrypt JSON-serializable data
        """
        import json
        if not data:
            return None
        
        json_string = json.dumps(data)
        return DataEncryption.encrypt_text(json_string)
    
    @staticmethod
    def decrypt_json(encrypted_data):
        """
        Decrypt JSON data
        """
        import json
        if not encrypted_data:
            return None
        
        json_string = DataEncryption.decrypt_text(encrypted_data)
        return json.loads(json_string) if json_string else None
    
    @staticmethod
    def hash_sensitive_data(data):
        """
        Create a hash of sensitive data for indexing/searching without storing plaintext
        """
        if not data:
            return None
        
        # Use SHA-256 with salt for hashing
        salt = getattr(settings, 'DATA_HASH_SALT', 'default_salt').encode()
        return hashlib.pbkdf2_hmac('sha256', data.encode(), salt, 100000).hex()


class FieldEncryption:
    """
    Django model field encryption utilities
    """
    
    @staticmethod
    def encrypt_field(instance, field_name, value):
        """
        Encrypt a model field value
        """
        if value is None:
            return None
        
        encrypted_value = DataEncryption.encrypt_text(str(value))
        
        # Store hash for searching if needed
        hash_field_name = f"{field_name}_hash"
        if hasattr(instance, hash_field_name):
            setattr(instance, hash_field_name, DataEncryption.hash_sensitive_data(str(value)))
        
        return encrypted_value
    
    @staticmethod
    def decrypt_field(encrypted_value):
        """
        Decrypt a model field value
        """
        if not encrypted_value:
            return None
        
        return DataEncryption.decrypt_text(encrypted_value)


class TranscriptEncryption:
    """
    Specialized encryption for meeting transcripts
    """
    
    @staticmethod
    def encrypt_transcript(transcript_text, meeting_id):
        """
        Encrypt meeting transcript with additional metadata
        """
        if not transcript_text:
            return None
        
        # Add metadata for audit trail
        transcript_data = {
            'content': transcript_text,
            'meeting_id': str(meeting_id),
            'encrypted_at': DataEncryption._get_current_timestamp(),
            'version': '1.0'
        }
        
        return DataEncryption.encrypt_json(transcript_data)
    
    @staticmethod
    def decrypt_transcript(encrypted_transcript):
        """
        Decrypt meeting transcript and return content
        """
        if not encrypted_transcript:
            return None
        
        transcript_data = DataEncryption.decrypt_json(encrypted_transcript)
        return transcript_data.get('content') if transcript_data else None
    
    @staticmethod
    def get_transcript_metadata(encrypted_transcript):
        """
        Get transcript metadata without decrypting content
        """
        if not encrypted_transcript:
            return None
        
        try:
            transcript_data = DataEncryption.decrypt_json(encrypted_transcript)
            if transcript_data:
                return {
                    'meeting_id': transcript_data.get('meeting_id'),
                    'encrypted_at': transcript_data.get('encrypted_at'),
                    'version': transcript_data.get('version'),
                    'has_content': bool(transcript_data.get('content'))
                }
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def _get_current_timestamp():
        """Get current timestamp"""
        from django.utils import timezone
        return timezone.now().isoformat()


class PIIEncryption:
    """
    Encryption for Personally Identifiable Information
    """
    
    PII_FIELDS = [
        'email', 'phone', 'address', 'ssn', 'credit_card',
        'full_name', 'date_of_birth', 'passport_number'
    ]
    
    @staticmethod
    def encrypt_pii_data(pii_data):
        """
        Encrypt PII data with special handling
        """
        if not pii_data:
            return None
        
        # Add PII-specific metadata
        pii_container = {
            'data': pii_data,
            'type': 'pii',
            'encrypted_at': TranscriptEncryption._get_current_timestamp(),
            'retention_policy': 'gdpr_compliant'
        }
        
        return DataEncryption.encrypt_json(pii_container)
    
    @staticmethod
    def decrypt_pii_data(encrypted_pii):
        """
        Decrypt PII data with audit logging
        """
        if not encrypted_pii:
            return None
        
        try:
            pii_container = DataEncryption.decrypt_json(encrypted_pii)
            
            # Log PII access (in production, send to audit system)
            PIIEncryption._log_pii_access(pii_container)
            
            return pii_container.get('data') if pii_container else None
        except Exception as e:
            # Log decryption failure
            PIIEncryption._log_pii_access_failure(str(e))
            return None
    
    @staticmethod
    def _log_pii_access(pii_container):
        """
        Log PII data access for audit trail
        """
        # In production, this would send to a secure audit log
        import logging
        logger = logging.getLogger('pii_access')
        logger.info(f"PII data accessed: type={pii_container.get('type')}, "
                   f"encrypted_at={pii_container.get('encrypted_at')}")
    
    @staticmethod
    def _log_pii_access_failure(error):
        """
        Log PII access failure
        """
        import logging
        logger = logging.getLogger('pii_access')
        logger.error(f"PII decryption failed: {error}")
    
    @staticmethod
    def mask_pii_for_display(pii_data, field_type):
        """
        Mask PII data for display purposes
        """
        if not pii_data:
            return None
        
        if field_type == 'email':
            parts = pii_data.split('@')
            if len(parts) == 2:
                return f"{parts[0][:2]}***@{parts[1]}"
        
        elif field_type == 'phone':
            if len(pii_data) >= 4:
                return f"***-***-{pii_data[-4:]}"
        
        elif field_type == 'credit_card':
            if len(pii_data) >= 4:
                return f"****-****-****-{pii_data[-4:]}"
        
        elif field_type in ['full_name', 'address']:
            words = pii_data.split()
            if words:
                return f"{words[0]} ***"
        
        # Default masking
        if len(pii_data) > 4:
            return f"{pii_data[:2]}***{pii_data[-2:]}"
        else:
            return "***"


class EncryptionKeyManager:
    """
    Manage encryption keys and rotation
    """
    
    @staticmethod
    def generate_new_key():
        """
        Generate a new encryption key
        """
        return Fernet.generate_key()
    
    @staticmethod
    def rotate_encryption_key():
        """
        Rotate encryption keys (for production use)
        """
        # This would implement key rotation logic
        # 1. Generate new key
        # 2. Re-encrypt data with new key
        # 3. Update key in secure storage
        # 4. Remove old key after grace period
        pass
    
    @staticmethod
    def backup_encryption_key():
        """
        Backup encryption keys securely
        """
        # This would implement secure key backup
        pass
    
    @staticmethod
    def validate_key_integrity():
        """
        Validate encryption key integrity
        """
        try:
            # Test encryption/decryption with current key
            test_data = "test_encryption_integrity"
            encrypted = DataEncryption.encrypt_text(test_data)
            decrypted = DataEncryption.decrypt_text(encrypted)
            return decrypted == test_data
        except Exception:
            return False


class DataAnonymization:
    """
    Utilities for data anonymization and pseudonymization
    """
    
    @staticmethod
    def anonymize_transcript(transcript_text):
        """
        Anonymize transcript by removing/replacing PII
        """
        import re
        
        if not transcript_text:
            return transcript_text
        
        # Replace email addresses
        transcript_text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            '[EMAIL_REDACTED]',
            transcript_text
        )
        
        # Replace phone numbers
        transcript_text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            '[PHONE_REDACTED]',
            transcript_text
        )
        
        # Replace potential SSNs
        transcript_text = re.sub(
            r'\b\d{3}-\d{2}-\d{4}\b',
            '[SSN_REDACTED]',
            transcript_text
        )
        
        # Replace credit card numbers
        transcript_text = re.sub(
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            '[CARD_REDACTED]',
            transcript_text
        )
        
        return transcript_text
    
    @staticmethod
    def pseudonymize_user_data(user_data):
        """
        Pseudonymize user data for analytics
        """
        if not user_data:
            return user_data
        
        # Generate consistent pseudonym based on original data
        pseudonym_seed = hashlib.sha256(str(user_data).encode()).hexdigest()[:8]
        
        return {
            'user_id': f"user_{pseudonym_seed}",
            'anonymized': True,
            'original_fields': list(user_data.keys()) if isinstance(user_data, dict) else ['data']
        }
    
    @staticmethod
    def create_data_export(user_data, anonymize=True):
        """
        Create data export for GDPR compliance
        """
        export_data = {
            'export_timestamp': TranscriptEncryption._get_current_timestamp(),
            'data_types': [],
            'anonymized': anonymize
        }
        
        if anonymize:
            export_data['data'] = DataAnonymization.pseudonymize_user_data(user_data)
        else:
            export_data['data'] = user_data
        
        return export_data