# API Versioning Strategy

This document outlines the versioning strategy for the NIA Meeting Intelligence API, including version management, backward compatibility, deprecation policies, and migration guidelines.

## Versioning Approach

### URL-Based Versioning

The NIA API uses URL-based versioning with the version number included in the URL path:

```
https://api.nia-intelligence.com/api/v1/meetings/
https://api.nia-intelligence.com/api/v2/meetings/
```

**Benefits:**
- Clear and explicit version identification
- Easy to cache and route
- Simple for clients to understand and implement
- Allows different versions to coexist

### Version Format

- **Major Version**: `v1`, `v2`, `v3`, etc.
- **Minor versions and patches**: Handled transparently within major versions
- **Pre-release versions**: `v2-beta`, `v2-alpha` (for testing)

## Version Lifecycle

### Version States

1. **Development**: Internal development and testing
2. **Beta**: Public testing with selected partners
3. **Stable**: General availability and production use
4. **Deprecated**: Marked for removal, maintenance mode only
5. **Retired**: No longer available

### Version Timeline

```
v1.0 (Current Stable)
├── Released: 2024-01-01
├── Deprecation: 2025-01-01 (planned)
└── Retirement: 2026-01-01 (planned)

v2.0 (In Development)
├── Beta Release: 2024-06-01 (planned)
├── Stable Release: 2024-09-01 (planned)
└── Full Support: 2024-09-01 - 2026-09-01
```

## Backward Compatibility

### Compatibility Promise

**Non-Breaking Changes (within major version):**
- Adding new optional fields to requests
- Adding new fields to responses
- Adding new endpoints
- Adding new optional query parameters
- Adding new HTTP methods to existing endpoints
- Relaxing validation rules

**Breaking Changes (require new major version):**
- Removing fields from responses
- Changing field types or formats
- Making optional fields required
- Removing endpoints
- Changing HTTP status codes
- Changing authentication mechanisms
- Changing URL structures

### Example: Non-Breaking Change

```json
// v1.0 Response
{
  "id": 123,
  "title": "Meeting Title",
  "start_time": "2024-02-15T14:00:00Z"
}

// v1.1 Response (backward compatible)
{
  "id": 123,
  "title": "Meeting Title",
  "start_time": "2024-02-15T14:00:00Z",
  "meeting_type": "discovery",  // New field added
  "confidence_score": 0.95      // New field added
}
```

### Example: Breaking Change

```json
// v1.0 Response
{
  "id": 123,
  "title": "Meeting Title",
  "start_time": "2024-02-15T14:00:00Z",
  "participants": ["email1@example.com", "email2@example.com"]
}

// v2.0 Response (breaking change - requires new major version)
{
  "id": 123,
  "title": "Meeting Title",
  "start_time": "2024-02-15T14:00:00Z",
  "participants": [
    {
      "email": "email1@example.com",
      "name": "John Doe",
      "company": "Acme Corp"
    }
  ]
}
```

## Version Implementation

### Django URL Configuration

```python
# meeting_intelligence/urls.py
from django.urls import path, include

urlpatterns = [
    # Version 1 (current stable)
    path('api/v1/', include('meeting_intelligence.api.v1.urls')),
    
    # Version 2 (beta)
    path('api/v2/', include('meeting_intelligence.api.v2.urls')),
    
    # Default to latest stable version
    path('api/', include('meeting_intelligence.api.v1.urls')),
]
```

### Version-Specific URL Modules

```python
# meeting_intelligence/api/v1/urls.py
from django.urls import path, include

urlpatterns = [
    path('auth/', include('apps.accounts.api.v1.urls')),
    path('meetings/', include('apps.meetings.api.v1.urls')),
    path('debriefings/', include('apps.debriefings.api.v1.urls')),
    path('leads/', include('apps.leads.api.v1.urls')),
    path('calendar/', include('apps.calendar_integration.api.v1.urls')),
    path('crm/', include('apps.crm_sync.api.v1.urls')),
    path('ai/', include('apps.ai_engine.api.v1.urls')),
    path('analytics/', include('apps.analytics.api.v1.urls')),
]

# meeting_intelligence/api/v2/urls.py
from django.urls import path, include

urlpatterns = [
    path('auth/', include('apps.accounts.api.v2.urls')),
    path('meetings/', include('apps.meetings.api.v2.urls')),
    # ... other v2 endpoints
]
```

### Version-Specific Views

```python
# apps/meetings/api/v1/views.py
from rest_framework import viewsets
from apps.meetings.models import Meeting
from .serializers import MeetingSerializerV1

class MeetingViewSetV1(viewsets.ModelViewSet):
    """Meeting API v1"""
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializerV1

# apps/meetings/api/v2/views.py
from rest_framework import viewsets
from apps.meetings.models import Meeting
from .serializers import MeetingSerializerV2

class MeetingViewSetV2(viewsets.ModelViewSet):
    """Meeting API v2 with enhanced features"""
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializerV2
    
    def get_queryset(self):
        # v2 includes additional filtering capabilities
        queryset = super().get_queryset()
        # Add v2-specific filtering logic
        return queryset
```

### Version-Specific Serializers

```python
# apps/meetings/api/v1/serializers.py
from rest_framework import serializers
from apps.meetings.models import Meeting

class MeetingSerializerV1(serializers.ModelSerializer):
    """Meeting serializer for API v1"""
    participants = serializers.ListField(
        child=serializers.EmailField(),
        source='get_participant_emails'
    )
    
    class Meta:
        model = Meeting
        fields = ['id', 'title', 'start_time', 'end_time', 'participants']

# apps/meetings/api/v2/serializers.py
from rest_framework import serializers
from apps.meetings.models import Meeting, MeetingParticipant

class ParticipantSerializerV2(serializers.ModelSerializer):
    class Meta:
        model = MeetingParticipant
        fields = ['email', 'name', 'company', 'match_confidence']

class MeetingSerializerV2(serializers.ModelSerializer):
    """Meeting serializer for API v2 with enhanced participant data"""
    participants = ParticipantSerializerV2(many=True, read_only=True)
    meeting_intelligence = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'start_time', 'end_time', 'meeting_type',
            'confidence_score', 'participants', 'meeting_intelligence'
        ]
    
    def get_meeting_intelligence(self, obj):
        return {
            'is_sales_meeting': obj.is_sales_meeting,
            'debriefing_scheduled': obj.debriefing_scheduled,
            'debriefing_completed': obj.debriefing_completed
        }
```

## Version Detection and Headers

### Version Detection Middleware

```python
# meeting_intelligence/middleware/versioning.py
import re
from django.http import HttpResponseBadRequest

class APIVersionMiddleware:
    """Middleware to detect and validate API version"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.version_pattern = re.compile(r'/api/v(\d+)/')
    
    def __call__(self, request):
        # Extract version from URL
        if request.path.startswith('/api/'):
            match = self.version_pattern.search(request.path)
            if match:
                version = int(match.group(1))
                request.api_version = version
                
                # Validate supported versions
                if version not in [1, 2]:  # Supported versions
                    return HttpResponseBadRequest(
                        'Unsupported API version. Supported versions: v1, v2'
                    )
            else:
                # Default to v1 for /api/ without version
                request.api_version = 1
        
        response = self.get_response(request)
        
        # Add version headers to response
        if hasattr(request, 'api_version'):
            response['API-Version'] = f'v{request.api_version}'
            response['API-Supported-Versions'] = 'v1, v2'
            
            # Add deprecation warning for old versions
            if request.api_version == 1:
                response['API-Deprecation-Warning'] = (
                    'API v1 is deprecated and will be removed on 2026-01-01. '
                    'Please migrate to v2.'
                )
        
        return response
```

### Version-Aware Error Handling

```python
# meeting_intelligence/api/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    """Custom exception handler with version-aware responses"""
    response = exception_handler(exc, context)
    
    if response is not None:
        request = context.get('request')
        api_version = getattr(request, 'api_version', 1)
        
        if api_version == 1:
            # v1 error format (simple)
            custom_response_data = {
                'error': str(exc),
                'status_code': response.status_code
            }
        else:
            # v2 error format (detailed)
            custom_response_data = {
                'error': {
                    'message': str(exc),
                    'code': getattr(exc, 'default_code', 'error'),
                    'details': response.data if isinstance(response.data, dict) else {},
                    'timestamp': timezone.now().isoformat(),
                    'path': request.path
                },
                'status_code': response.status_code
            }
        
        response.data = custom_response_data
    
    return response
```

## Deprecation Policy

### Deprecation Timeline

1. **Announcement**: 12 months before deprecation
2. **Deprecation Warning**: 6 months before removal
3. **Deprecation**: Version marked as deprecated
4. **Retirement**: Version removed from service

### Deprecation Communication

#### 1. API Response Headers

```http
HTTP/1.1 200 OK
API-Version: v1
API-Deprecation-Warning: API v1 is deprecated and will be removed on 2026-01-01. Please migrate to v2.
API-Sunset: 2026-01-01T00:00:00Z
Link: <https://docs.nia-intelligence.com/api/v2/migration>; rel="successor-version"
```

#### 2. Email Notifications

```python
# management/commands/send_deprecation_notices.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.contrib.auth.models import User
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Send API deprecation notices to users'
    
    def handle(self, *args, **options):
        # Get users who have used v1 API in the last 30 days
        cutoff_date = datetime.now() - timedelta(days=30)
        users = User.objects.filter(
            useractivity__activity_type='api_request',
            useractivity__description__contains='v1',
            useractivity__timestamp__gte=cutoff_date
        ).distinct()
        
        for user in users:
            send_mail(
                subject='Important: NIA API v1 Deprecation Notice',
                message=self.get_deprecation_message(),
                from_email='api-support@nia-intelligence.com',
                recipient_list=[user.email],
                fail_silently=False,
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Sent deprecation notices to {users.count()} users')
        )
    
    def get_deprecation_message(self):
        return """
        Dear NIA API User,
        
        This is an important notice regarding the deprecation of NIA API v1.
        
        What's happening:
        - API v1 will be deprecated on January 1, 2025
        - API v1 will be retired on January 1, 2026
        - All applications must migrate to API v2 before the retirement date
        
        What you need to do:
        1. Review the migration guide: https://docs.nia-intelligence.com/api/v2/migration
        2. Test your application with API v2
        3. Update your application to use API v2
        4. Monitor for any issues and contact support if needed
        
        Resources:
        - Migration Guide: https://docs.nia-intelligence.com/api/v2/migration
        - API v2 Documentation: https://docs.nia-intelligence.com/api/v2/
        - Support: api-support@nia-intelligence.com
        
        Thank you for using NIA Meeting Intelligence.
        
        Best regards,
        The NIA Development Team
        """
```

#### 3. Dashboard Notifications

```python
# apps/accounts/api/v1/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def api_status(request):
    """Get API status and deprecation information"""
    return Response({
        'version': 'v1',
        'status': 'deprecated',
        'deprecation_date': '2025-01-01',
        'retirement_date': '2026-01-01',
        'migration_guide': 'https://docs.nia-intelligence.com/api/v2/migration',
        'successor_version': 'v2',
        'message': (
            'API v1 is deprecated and will be removed on 2026-01-01. '
            'Please migrate to v2 as soon as possible.'
        )
    })
```

## Migration Guide

### v1 to v2 Migration

#### Key Changes in v2

1. **Enhanced Participant Data**
   ```python
   # v1: Simple email list
   "participants": ["email1@example.com", "email2@example.com"]
   
   # v2: Rich participant objects
   "participants": [
       {
           "email": "email1@example.com",
           "name": "John Doe",
           "company": "Acme Corp",
           "match_confidence": 0.95
       }
   ]
   ```

2. **Meeting Intelligence Fields**
   ```python
   # v2 adds intelligence fields
   "meeting_intelligence": {
       "is_sales_meeting": true,
       "debriefing_scheduled": true,
       "debriefing_completed": false,
       "confidence_score": 0.87
   }
   ```

3. **Enhanced Error Responses**
   ```python
   # v1: Simple error
   {
       "error": "Validation failed",
       "status_code": 400
   }
   
   # v2: Detailed error
   {
       "error": {
           "message": "Validation failed",
           "code": "validation_error",
           "details": {
               "email": ["This field is required."]
           },
           "timestamp": "2024-02-15T14:30:00Z",
           "path": "/api/v2/meetings/"
       },
       "status_code": 400
   }
   ```

#### Migration Steps

1. **Update Base URLs**
   ```python
   # Before
   BASE_URL = "https://api.nia-intelligence.com/api/v1/"
   
   # After
   BASE_URL = "https://api.nia-intelligence.com/api/v2/"
   ```

2. **Update Response Parsing**
   ```python
   # Before (v1)
   def parse_meeting_participants(meeting_data):
       return meeting_data['participants']  # List of emails
   
   # After (v2)
   def parse_meeting_participants(meeting_data):
       participants = []
       for p in meeting_data['participants']:
           participants.append({
               'email': p['email'],
               'name': p.get('name', ''),
               'company': p.get('company', '')
           })
       return participants
   ```

3. **Update Error Handling**
   ```python
   # Before (v1)
   def handle_api_error(response):
       if response.status_code != 200:
           error_msg = response.json().get('error', 'Unknown error')
           raise APIError(error_msg)
   
   # After (v2)
   def handle_api_error(response):
       if response.status_code != 200:
           error_data = response.json().get('error', {})
           error_msg = error_data.get('message', 'Unknown error')
           error_code = error_data.get('code', 'unknown')
           error_details = error_data.get('details', {})
           raise APIError(error_msg, error_code, error_details)
   ```

#### Compatibility Layer

```python
# utils/api_compatibility.py
class APICompatibilityLayer:
    """Compatibility layer to ease v1 to v2 migration"""
    
    @staticmethod
    def normalize_meeting_response(response_data, api_version):
        """Normalize meeting response across versions"""
        if api_version == 1:
            return response_data
        
        # Convert v2 response to v1 format for backward compatibility
        if api_version == 2:
            normalized = response_data.copy()
            
            # Convert rich participants to simple email list
            if 'participants' in normalized:
                normalized['participants'] = [
                    p['email'] for p in normalized['participants']
                ]
            
            # Remove v2-specific fields
            normalized.pop('meeting_intelligence', None)
            
            return normalized
    
    @staticmethod
    def normalize_error_response(error_data, api_version):
        """Normalize error response across versions"""
        if api_version == 1:
            return error_data
        
        if api_version == 2:
            # Convert v2 error to v1 format
            if 'error' in error_data and isinstance(error_data['error'], dict):
                return {
                    'error': error_data['error']['message'],
                    'status_code': error_data['status_code']
                }
        
        return error_data
```

## Version Monitoring

### Usage Analytics

```python
# apps/analytics/api_usage.py
from django.db import models
from django.contrib.auth.models import User

class APIUsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    api_version = models.CharField(max_length=10)
    endpoint = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    response_time = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True)

class APIVersionUsageMiddleware:
    """Middleware to log API version usage"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        end_time = time.time()
        
        # Log API usage
        if request.path.startswith('/api/') and hasattr(request, 'api_version'):
            APIUsageLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                api_version=f'v{request.api_version}',
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time=end_time - start_time,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self.get_client_ip(request)
            )
        
        return response
```

### Version Usage Dashboard

```python
# apps/analytics/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Avg
from .models import APIUsageLog

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_version_usage_stats(request):
    """Get API version usage statistics"""
    
    # Version usage over time
    version_usage = APIUsageLog.objects.values('api_version').annotate(
        request_count=Count('id'),
        avg_response_time=Avg('response_time'),
        unique_users=Count('user', distinct=True)
    ).order_by('-request_count')
    
    # Daily usage by version
    daily_usage = APIUsageLog.objects.extra(
        select={'day': 'date(timestamp)'}
    ).values('day', 'api_version').annotate(
        request_count=Count('id')
    ).order_by('-day')
    
    # Top endpoints by version
    top_endpoints = APIUsageLog.objects.values(
        'api_version', 'endpoint'
    ).annotate(
        request_count=Count('id')
    ).order_by('-request_count')[:20]
    
    return Response({
        'version_usage': list(version_usage),
        'daily_usage': list(daily_usage),
        'top_endpoints': list(top_endpoints)
    })
```

This comprehensive versioning strategy ensures smooth API evolution while maintaining backward compatibility and providing clear migration paths for clients.