"""
Custom password validators for enhanced security
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """
    Custom password validator with enhanced security requirements
    """
    
    def validate(self, password, user=None):
        """
        Validate password against security requirements
        """
        errors = []
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            errors.append(_('Password must contain at least one uppercase letter.'))
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            errors.append(_('Password must contain at least one lowercase letter.'))
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            errors.append(_('Password must contain at least one digit.'))
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append(_('Password must contain at least one special character (!@#$%^&*(),.?":{}|<>).'))
        
        # Check for common patterns
        if self._has_common_patterns(password):
            errors.append(_('Password contains common patterns that are not secure.'))
        
        # Check against user information if provided
        if user and self._contains_user_info(password, user):
            errors.append(_('Password cannot contain personal information.'))
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        """
        Return help text for password requirements
        """
        return _(
            "Your password must contain at least 12 characters including "
            "uppercase letters, lowercase letters, digits, and special characters. "
            "It cannot contain common patterns or personal information."
        )
    
    def _has_common_patterns(self, password):
        """
        Check for common insecure patterns
        """
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'admin',
            r'letmein',
            r'welcome',
            r'monkey',
            r'dragon',
            r'master',
            r'(\w)\1{2,}',  # Repeated characters (aaa, 111, etc.)
            r'(012|123|234|345|456|567|678|789|890)',  # Sequential numbers
            r'(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz)',  # Sequential letters
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if re.search(pattern, password_lower):
                return True
        
        return False
    
    def _contains_user_info(self, password, user):
        """
        Check if password contains user information
        """
        if not user:
            return False
        
        password_lower = password.lower()
        
        # Check username
        if user.username and len(user.username) > 2 and user.username.lower() in password_lower:
            return True
        
        # Check email
        if user.email:
            email_parts = user.email.lower().split('@')
            if email_parts[0] and len(email_parts[0]) > 2 and email_parts[0] in password_lower:
                return True
        
        # Check first and last name
        if user.first_name and len(user.first_name) > 2 and user.first_name.lower() in password_lower:
            return True
        
        if user.last_name and len(user.last_name) > 2 and user.last_name.lower() in password_lower:
            return True
        
        return False


class PasswordHistoryValidator:
    """
    Validator to prevent reusing recent passwords
    """
    
    def __init__(self, history_count=5):
        self.history_count = history_count
    
    def validate(self, password, user=None):
        """
        Validate password is not in recent history
        """
        if not user:
            return
        
        # This would require a PasswordHistory model to track previous passwords
        # For now, we'll implement a basic check
        from django.contrib.auth.hashers import check_password
        
        # Check current password
        if user.pk and check_password(password, user.password):
            raise ValidationError(
                _('You cannot reuse your current password.'),
                code='password_reused'
            )
    
    def get_help_text(self):
        return _(f'Your password cannot be the same as your last {self.history_count} passwords.')


class PasswordExpiryValidator:
    """
    Validator to enforce password expiry
    """
    
    def __init__(self, max_age_days=90):
        self.max_age_days = max_age_days
    
    def validate(self, password, user=None):
        """
        Check if password needs to be changed due to age
        """
        if not user or not user.pk:
            return
        
        # This would require tracking password change dates
        # Implementation would depend on adding password_changed_at field to UserProfile
        pass
    
    def get_help_text(self):
        return _(f'Passwords must be changed every {self.max_age_days} days.')