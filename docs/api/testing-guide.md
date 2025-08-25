# API Testing and Integration Guide

This guide provides comprehensive information on testing the NIA Meeting Intelligence API, including unit tests, integration tests, and end-to-end testing strategies.

## Testing Environment Setup

### Local Development Environment

```bash
# Clone the repository
git clone https://github.com/your-org/nia-meeting-intelligence.git
cd nia-meeting-intelligence

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start services with Docker
docker-compose up -d

# Run migrations
python manage.py migrate

# Create test user
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Test Database Configuration

```python
# settings/test.py
from .base import *

# Use in-memory SQLite for faster tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True
    
    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

# Use dummy cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use console email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## Unit Testing

### Authentication Tests

```python
# tests/test_authentication.py
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import UserProfile, TwoFactorAuth

class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='sales_rep'
        )
    
    def test_login_success(self):
        """Test successful login"""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_with_2fa(self):
        """Test login with 2FA enabled"""
        # Enable 2FA for user
        two_factor = TwoFactorAuth.objects.create(user=self.user)
        two_factor.enable_2fa()
        
        # First login attempt without 2FA token
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('requires_2fa'))
        
        # Login with valid 2FA token
        valid_token = two_factor.generate_token()
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123',
            'totp_token': valid_token
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_token_refresh(self):
        """Test token refresh"""
        # Login to get tokens
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        
        refresh_token = login_response.data['refresh_token']
        
        # Refresh token
        response = self.client.post('/api/v1/auth/refresh/', {
            'refresh_token': refresh_token
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_protected_endpoint_without_auth(self):
        """Test accessing protected endpoint without authentication"""
        response = self.client.get('/api/v1/meetings/')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_protected_endpoint_with_auth(self):
        """Test accessing protected endpoint with authentication"""
        # Login and get token
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        
        access_token = login_response.data['access_token']
        
        # Access protected endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/v1/meetings/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
```

### Meeting Intelligence Tests

```python
# tests/test_meetings.py
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from apps.meetings.models import Meeting, MeetingParticipant
from apps.accounts.models import UserProfile

class MeetingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='sales_rep'
        )
        
        # Authenticate client
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        access_token = login_response.data['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    def test_create_meeting(self):
        """Test creating a new meeting"""
        meeting_data = {
            'title': 'Test Meeting',
            'start_time': (datetime.now() + timedelta(hours=1)).isoformat(),
            'end_time': (datetime.now() + timedelta(hours=2)).isoformat(),
            'meeting_type': 'discovery',
            'calendar_event_id': 'test_event_123',
            'participants': [
                {
                    'email': 'participant@example.com',
                    'name': 'John Participant',
                    'company': 'Example Corp'
                }
            ]
        }
        
        response = self.client.post('/api/v1/meetings/', meeting_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Test Meeting')
        self.assertEqual(response.data['meeting_type'], 'discovery')
        
        # Verify meeting was created in database
        meeting = Meeting.objects.get(id=response.data['id'])
        self.assertEqual(meeting.title, 'Test Meeting')
        self.assertEqual(meeting.organizer, self.user)
    
    def test_list_meetings(self):
        """Test listing meetings"""
        # Create test meetings
        Meeting.objects.create(
            title='Meeting 1',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            organizer=self.user,
            meeting_type='discovery'
        )
        Meeting.objects.create(
            title='Meeting 2',
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=1),
            organizer=self.user,
            meeting_type='demo'
        )
        
        response = self.client.get('/api/v1/meetings/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_filter_meetings_by_type(self):
        """Test filtering meetings by type"""
        Meeting.objects.create(
            title='Discovery Meeting',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            organizer=self.user,
            meeting_type='discovery'
        )
        Meeting.objects.create(
            title='Demo Meeting',
            start_time=datetime.now() + timedelta(days=1),
            end_time=datetime.now() + timedelta(days=1, hours=1),
            organizer=self.user,
            meeting_type='demo'
        )
        
        response = self.client.get('/api/v1/meetings/?meeting_type=discovery')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['meeting_type'], 'discovery')
    
    def test_schedule_debriefing(self):
        """Test scheduling debriefing for a meeting"""
        meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            organizer=self.user,
            meeting_type='discovery'
        )
        
        response = self.client.post(f'/api/v1/meetings/{meeting.id}/schedule_debriefing/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify debriefing was scheduled
        meeting.refresh_from_db()
        self.assertTrue(meeting.debriefing_scheduled)
    
    def test_meeting_statistics(self):
        """Test getting meeting statistics"""
        # Create test meetings
        Meeting.objects.create(
            title='Meeting 1',
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now() - timedelta(days=1) + timedelta(hours=1),
            organizer=self.user,
            meeting_type='discovery',
            is_sales_meeting=True
        )
        Meeting.objects.create(
            title='Meeting 2',
            start_time=datetime.now() - timedelta(days=2),
            end_time=datetime.now() - timedelta(days=2) + timedelta(hours=1),
            organizer=self.user,
            meeting_type='demo',
            is_sales_meeting=True
        )
        
        response = self.client.get('/api/v1/meetings/stats/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_meetings', response.data)
        self.assertIn('sales_meetings', response.data)
        self.assertIn('meeting_types', response.data)
```

### Debriefing Tests

```python
# tests/test_debriefings.py
import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from apps.meetings.models import Meeting
from apps.debriefings.models import DebriefingSession
from apps.accounts.models import UserProfile

class DebriefingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='sales_rep'
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(hours=1),
            organizer=self.user,
            meeting_type='discovery'
        )
        
        # Authenticate client
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        access_token = login_response.data['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    def test_create_debriefing_session(self):
        """Test creating a debriefing session"""
        debriefing_data = {
            'meeting_id': self.meeting.id,
            'scheduled_time': datetime.now().isoformat()
        }
        
        response = self.client.post('/api/v1/debriefings/', debriefing_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['meeting'], self.meeting.id)
        self.assertEqual(response.data['status'], 'scheduled')
    
    def test_submit_debriefing_response(self):
        """Test submitting a response to debriefing"""
        # Create debriefing session
        debriefing = DebriefingSession.objects.create(
            meeting=self.meeting,
            scheduled_time=datetime.now(),
            status='in_progress'
        )
        
        response_data = {
            'question': 'How did the meeting go?',
            'response': 'Very positive, client showed strong interest'
        }
        
        response = self.client.post(
            f'/api/v1/debriefings/{debriefing.id}/respond/',
            response_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify response was saved
        debriefing.refresh_from_db()
        self.assertIn('responses', debriefing.conversation_data)
    
    def test_complete_debriefing(self):
        """Test completing a debriefing session"""
        debriefing = DebriefingSession.objects.create(
            meeting=self.meeting,
            scheduled_time=datetime.now(),
            status='in_progress'
        )
        
        response = self.client.post(f'/api/v1/debriefings/{debriefing.id}/complete/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify debriefing was completed
        debriefing.refresh_from_db()
        self.assertEqual(debriefing.status, 'completed')
        self.assertIsNotNone(debriefing.completed_at)
    
    def test_get_extracted_data(self):
        """Test getting extracted data from debriefing"""
        debriefing = DebriefingSession.objects.create(
            meeting=self.meeting,
            scheduled_time=datetime.now(),
            status='completed',
            extracted_data={
                'budget': '$50,000',
                'timeline': 'Q2 2024',
                'decision_makers': ['John Smith']
            }
        )
        
        response = self.client.get(f'/api/v1/debriefings/{debriefing.id}/extracted_data/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('budget', response.data)
        self.assertIn('timeline', response.data)
        self.assertIn('decision_makers', response.data)
```

## Integration Testing

### API Integration Tests

```python
# tests/test_integration.py
import pytest
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from apps.meetings.models import Meeting
from apps.debriefings.models import DebriefingSession
from apps.leads.models import Lead
from apps.accounts.models import UserProfile

class MeetingIntelligenceIntegrationTest(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='sales_rep'
        )
        
        # Authenticate client
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'testpassword123'
        })
        access_token = login_response.data['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    def test_complete_meeting_intelligence_workflow(self):
        """Test complete meeting intelligence workflow"""
        # 1. Create meeting
        meeting_data = {
            'title': 'Product Demo - Acme Corp',
            'start_time': (datetime.now() - timedelta(hours=2)).isoformat(),
            'end_time': (datetime.now() - timedelta(hours=1)).isoformat(),
            'meeting_type': 'demo',
            'calendar_event_id': 'cal_event_123',
            'participants': [
                {
                    'email': 'john.smith@acme.com',
                    'name': 'John Smith',
                    'company': 'Acme Corp'
                }
            ]
        }
        
        meeting_response = self.client.post('/api/v1/meetings/', meeting_data, format='json')
        self.assertEqual(meeting_response.status_code, status.HTTP_201_CREATED)
        meeting_id = meeting_response.data['id']
        
        # 2. Schedule debriefing
        debriefing_response = self.client.post(f'/api/v1/meetings/{meeting_id}/schedule_debriefing/')
        self.assertEqual(debriefing_response.status_code, status.HTTP_200_OK)
        
        # 3. Create debriefing session
        debriefing_data = {
            'meeting_id': meeting_id,
            'scheduled_time': datetime.now().isoformat()
        }
        
        session_response = self.client.post('/api/v1/debriefings/', debriefing_data, format='json')
        self.assertEqual(session_response.status_code, status.HTTP_201_CREATED)
        debriefing_id = session_response.data['id']
        
        # 4. Submit debriefing responses
        responses = [
            {
                'question': 'How did the meeting go overall?',
                'response': 'Very positive! Client showed strong interest in our solution.'
            },
            {
                'question': 'What was discussed about budget?',
                'response': 'They mentioned having a budget of around $100,000 for this project.'
            },
            {
                'question': 'What are the next steps?',
                'response': 'Send technical proposal by Friday and schedule follow-up demo.'
            }
        ]
        
        for response_data in responses:
            response = self.client.post(
                f'/api/v1/debriefings/{debriefing_id}/respond/',
                response_data,
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Complete debriefing
        complete_response = self.client.post(f'/api/v1/debriefings/{debriefing_id}/complete/')
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)
        
        # 6. Get extracted data
        extracted_response = self.client.get(f'/api/v1/debriefings/{debriefing_id}/extracted_data/')
        self.assertEqual(extracted_response.status_code, status.HTTP_200_OK)
        
        # Verify workflow completion
        meeting = Meeting.objects.get(id=meeting_id)
        self.assertTrue(meeting.debriefing_scheduled)
        self.assertTrue(meeting.debriefing_completed)
        
        debriefing = DebriefingSession.objects.get(id=debriefing_id)
        self.assertEqual(debriefing.status, 'completed')
        self.assertIsNotNone(debriefing.extracted_data)
    
    @patch('apps.crm_sync.adapters.CreatioAdapter.sync_lead')
    def test_crm_sync_integration(self, mock_sync_lead):
        """Test CRM synchronization integration"""
        mock_sync_lead.return_value = {'success': True, 'creatio_id': 'crm_123'}
        
        # Create lead
        lead_data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'jane.doe@example.com',
            'company': 'Example Corp',
            'source': 'meeting'
        }
        
        lead_response = self.client.post('/api/v1/leads/', lead_data, format='json')
        self.assertEqual(lead_response.status_code, status.HTTP_201_CREATED)
        lead_id = lead_response.data['id']
        
        # Trigger CRM sync
        sync_response = self.client.post('/api/v1/crm/sync/', {
            'sync_type': 'leads',
            'entity_ids': [lead_id]
        }, format='json')
        
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        
        # Verify sync was called
        mock_sync_lead.assert_called_once()
        
        # Verify lead was updated with CRM ID
        lead = Lead.objects.get(id=lead_id)
        self.assertEqual(lead.creatio_id, 'crm_123')
```

## Load Testing

### Using Locust for Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between
import json
import random

class NIAAPIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login and get access token"""
        response = self.client.post("/api/v1/auth/login/", json={
            "username": "testuser",
            "password": "testpassword123"
        })
        
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            self.client.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
    
    @task(3)
    def list_meetings(self):
        """List meetings - most common operation"""
        self.client.get("/api/v1/meetings/")
    
    @task(2)
    def get_meeting_details(self):
        """Get meeting details"""
        meeting_id = random.randint(1, 100)  # Assume meetings exist
        self.client.get(f"/api/v1/meetings/{meeting_id}/")
    
    @task(1)
    def create_meeting(self):
        """Create new meeting"""
        meeting_data = {
            "title": f"Test Meeting {random.randint(1, 1000)}",
            "start_time": "2024-02-15T14:00:00Z",
            "end_time": "2024-02-15T15:00:00Z",
            "meeting_type": random.choice(["discovery", "demo", "negotiation"]),
            "participants": [
                {
                    "email": f"test{random.randint(1, 1000)}@example.com",
                    "name": "Test Participant"
                }
            ]
        }
        
        self.client.post("/api/v1/meetings/", json=meeting_data)
    
    @task(1)
    def get_analytics(self):
        """Get analytics data"""
        self.client.get("/api/v1/analytics/dashboard/")
    
    @task(1)
    def list_leads(self):
        """List leads"""
        self.client.get("/api/v1/leads/")

# Run load test
# locust -f locustfile.py --host=http://localhost:8000
```

### Performance Test Script

```bash
#!/bin/bash
# performance_test.sh

echo "Starting NIA API Performance Tests"

# Test 1: Authentication endpoint
echo "Testing authentication endpoint..."
ab -n 1000 -c 10 -p login_data.json -T application/json http://localhost:8000/api/v1/auth/login/

# Test 2: Meeting list endpoint (with auth)
echo "Testing meeting list endpoint..."
# First get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpassword123"}' | \
  jq -r '.access_token')

# Test with auth header
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/meetings/

# Test 3: Meeting creation endpoint
echo "Testing meeting creation endpoint..."
ab -n 100 -c 5 -p meeting_data.json -T application/json \
  -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/meetings/

echo "Performance tests completed"
```

## Automated Testing Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/api-tests.yml
name: API Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_nia
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-django pytest-cov
    
    - name: Set up environment
      run: |
        cp .env.example .env
        echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_nia" >> .env
        echo "REDIS_URL=redis://localhost:6379/0" >> .env
    
    - name: Run migrations
      run: python manage.py migrate
    
    - name: Run unit tests
      run: |
        pytest tests/ -v --cov=apps --cov-report=xml --cov-report=html
    
    - name: Run API integration tests
      run: |
        python manage.py test tests.test_integration
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v1
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
    
    - name: Run security checks
      run: |
        pip install bandit safety
        bandit -r apps/
        safety check
    
    - name: Run API documentation tests
      run: |
        python manage.py spectacular --file schema.yml
        # Validate OpenAPI schema
        pip install openapi-spec-validator
        openapi-spec-validator schema.yml

  api-tests:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Start services
      run: |
        docker-compose up -d
        sleep 30  # Wait for services to start
    
    - name: Run API tests with Newman
      run: |
        npm install -g newman
        newman run postman/NIA_API_Tests.postman_collection.json \
          -e postman/test_environment.postman_environment.json \
          --reporters cli,junit --reporter-junit-export results.xml
    
    - name: Publish test results
      uses: EnricoMi/publish-unit-test-result-action@v1
      if: always()
      with:
        files: results.xml
```

### Test Data Management

```python
# tests/fixtures.py
import pytest
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.meetings.models import Meeting, MeetingParticipant
from apps.leads.models import Lead
from datetime import datetime, timedelta

@pytest.fixture
def test_user():
    """Create test user"""
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpassword123'
    )
    UserProfile.objects.create(user=user, role='sales_rep')
    return user

@pytest.fixture
def test_meeting(test_user):
    """Create test meeting"""
    return Meeting.objects.create(
        title='Test Meeting',
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=1),
        organizer=test_user,
        meeting_type='discovery'
    )

@pytest.fixture
def test_lead():
    """Create test lead"""
    return Lead.objects.create(
        first_name='John',
        last_name='Doe',
        email='john.doe@example.com',
        company='Example Corp',
        source='meeting'
    )

@pytest.fixture
def api_client(test_user):
    """Authenticated API client"""
    from rest_framework.test import APIClient
    
    client = APIClient()
    login_response = client.post('/api/v1/auth/login/', {
        'username': 'testuser',
        'password': 'testpassword123'
    })
    access_token = login_response.data['access_token']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    return client
```

### Test Configuration

```python
# pytest.ini
[tool:pytest]
DJANGO_SETTINGS_MODULE = meeting_intelligence.settings.test
python_files = tests.py test_*.py *_tests.py
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=apps
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=80
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    api: marks tests as API tests
```

## Continuous Integration Best Practices

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 21.9b0
    hooks:
      - id: black
        language_version: python3.9
  
  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]
  
  - repo: https://github.com/pycqa/isort
    rev: 5.9.3
    hooks:
      - id: isort
        args: ["--profile", "black"]
  
  - repo: local
    hooks:
      - id: django-check
        name: Django Check
        entry: python manage.py check
        language: system
        pass_filenames: false
      
      - id: django-test
        name: Django Tests
        entry: python manage.py test
        language: system
        pass_filenames: false
```

This comprehensive testing guide provides everything needed to thoroughly test the NIA Meeting Intelligence API, from unit tests to load testing and continuous integration.