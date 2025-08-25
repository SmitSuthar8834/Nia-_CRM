# Authentication and Role-Based Access Control

This module implements comprehensive authentication and role-based access control for the NIA Meeting Intelligence system.

## Features

### 1. JWT Authentication
- Custom JWT authentication with access and refresh tokens
- 24-hour access token lifetime
- 7-day refresh token lifetime
- Secure token generation and validation

### 2. Role-Based Access Control (RBAC)
- **Admin**: Full system access and user management
- **Sales Manager**: Team oversight, analytics, and competitive intelligence
- **Sales Rep**: Personal meetings, debriefings, and lead management
- **Viewer**: Read-only access to dashboards and reports

### 3. Two-Factor Authentication (2FA)
- TOTP-based 2FA using Google Authenticator or similar apps
- QR code generation for easy setup
- Backup codes for account recovery
- Configurable TOTP settings

### 4. Security Features
- Login attempt tracking and rate limiting
- User activity logging
- IP address tracking
- Session security enhancements
- Security headers middleware

### 5. User Profile Management
- Extended user profiles with role assignments
- Calendar integration preferences
- Notification settings
- AI coaching preferences

## API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - User login with optional 2FA
- `POST /api/v1/auth/logout/` - User logout
- `POST /api/v1/auth/refresh/` - Refresh access token

### User Profile
- `GET /api/v1/auth/profile/` - Get user profile
- `PUT /api/v1/auth/profile/` - Update user profile
- `GET /api/v1/auth/permissions/` - Get user permissions

### Two-Factor Authentication
- `GET /api/v1/auth/2fa/setup/` - Get 2FA setup information
- `POST /api/v1/auth/2fa/setup/` - Enable 2FA
- `DELETE /api/v1/auth/2fa/setup/` - Disable 2FA
- `POST /api/v1/auth/2fa/backup-codes/` - Generate new backup codes

### Calendar Integration
- `GET /api/v1/auth/calendar/` - List calendar integrations
- `POST /api/v1/auth/calendar/` - Add calendar integration

### User Activity
- `GET /api/v1/auth/activity/` - View user activity log

### Admin Endpoints
- `GET /api/v1/auth/admin/users/` - List all users (admin only)
- `POST /api/v1/auth/admin/change-role/` - Change user role (admin only)

### Manager Endpoints
- `GET /api/v1/auth/team/` - View team members (manager only)

## Usage Examples

### Login
```python
import requests

# Basic login
response = requests.post('/api/v1/auth/login/', {
    'username': 'user@example.com',
    'password': 'password123'
})

# Login with 2FA
response = requests.post('/api/v1/auth/login/', {
    'username': 'user@example.com',
    'password': 'password123',
    'totp_token': '123456'
})
```

### Using JWT Tokens
```python
# Include token in headers
headers = {
    'Authorization': f'Bearer {access_token}'
}
response = requests.get('/api/v1/auth/profile/', headers=headers)
```

### Setting up 2FA
```python
# Get setup information
response = requests.get('/api/v1/auth/2fa/setup/', headers=headers)
qr_code = response.json()['qr_code']

# Enable 2FA
response = requests.post('/api/v1/auth/2fa/setup/', {
    'token': '123456'  # From authenticator app
}, headers=headers)
```

## Permission System

### Role Permissions
```python
ROLE_PERMISSIONS = {
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
```

### Using Permissions in Views
```python
from apps.accounts.permissions import RoleBasedPermission

class MyView(APIView):
    permission_classes = [RoleBasedPermission]
    required_roles = ['admin', 'sales_manager']
    required_permissions = ['view_all_meetings']
```

### Using Permission Decorators
```python
from apps.accounts.permissions import require_role, require_permission

@require_role(['admin', 'sales_manager'])
def admin_view(request):
    pass

@require_permission('view_all_meetings')
def meetings_view(request):
    pass
```

## Security Features

### Login Attempt Tracking
- Tracks all login attempts (success/failure)
- Blocks users after 5 failed attempts in 15 minutes
- Logs IP addresses and user agents

### User Activity Logging
- Logs all significant user actions
- Tracks API calls and data modifications
- Includes IP address and session information

### Security Middleware
- Rate limiting for authentication endpoints
- Security headers (XSS protection, content type sniffing, etc.)
- Session security enhancements

## Management Commands

### Create Admin User
```bash
python manage.py create_admin --email admin@example.com --username admin
```

## Testing

Run the authentication tests:
```bash
python manage.py test apps.accounts
```

## Models

### UserProfile
Extended user profile with role and preferences.

### TwoFactorAuth
TOTP-based two-factor authentication settings.

### CalendarIntegration
Calendar system integration settings.

### UserActivity
User activity and audit logging.

### LoginAttempt
Login attempt tracking for security.

## Configuration

### Settings
```python
# JWT settings
JWT_ACCESS_TOKEN_LIFETIME = 24 * 60 * 60  # 24 hours
JWT_REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60  # 7 days

# 2FA settings
TOTP_ISSUER_NAME = 'NIA Meeting Intelligence'
TOTP_VALID_WINDOW = 1

# Security settings
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_TIMEOUT = 15 * 60  # 15 minutes
```

### Middleware
Add to `MIDDLEWARE` in settings:
```python
MIDDLEWARE = [
    # ... other middleware
    'apps.accounts.middleware.UserActivityMiddleware',
    'apps.accounts.middleware.SecurityHeadersMiddleware',
    'apps.accounts.middleware.RateLimitMiddleware',
    'apps.accounts.middleware.SessionSecurityMiddleware',
]
```