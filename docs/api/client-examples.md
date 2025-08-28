# API Client Examples

This document provides examples of how to integrate with the NIA Meeting Intelligence API using various programming languages and frameworks.

## Python Examples

### Basic Client Setup

```python
import requests
import json
from datetime import datetime, timedelta

class NIAClient:
    def __init__(self, base_url, username=None, password=None, access_token=None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.access_token = access_token
        
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}'
            })
        elif username and password:
            self.login(username, password)
    
    def login(self, username, password, totp_token=None):
        """Login and get access token"""
        data = {
            'username': username,
            'password': password
        }
        if totp_token:
            data['totp_token'] = totp_token
        
        response = self.session.post(
            f'{self.base_url}/api/v1/auth/login/',
            json=data
        )
        response.raise_for_status()
        
        result = response.json()
        self.access_token = result['access_token']
        self.refresh_token = result['refresh_token']
        
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}'
        })
        
        return result
    
    def refresh_access_token(self):
        """Refresh expired access token"""
        response = self.session.post(
            f'{self.base_url}/api/v1/auth/refresh/',
            json={'refresh_token': self.refresh_token}
        )
        response.raise_for_status()
        
        result = response.json()
        self.access_token = result['access_token']
        
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}'
        })
        
        return result
    
    def get(self, endpoint, params=None):
        """Make GET request"""
        response = self.session.get(
            f'{self.base_url}{endpoint}',
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint, data=None):
        """Make POST request"""
        response = self.session.post(
            f'{self.base_url}{endpoint}',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def patch(self, endpoint, data=None):
        """Make PATCH request"""
        response = self.session.patch(
            f'{self.base_url}{endpoint}',
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def delete(self, endpoint):
        """Make DELETE request"""
        response = self.session.delete(f'{self.base_url}{endpoint}')
        response.raise_for_status()
        return response.status_code == 204

# Usage example
client = NIAClient(
    base_url='http://localhost:8000',
    username='john.doe@company.com',
    password='securepassword123'
)
```

### Meeting Management

```python
class MeetingManager:
    def __init__(self, client):
        self.client = client
    
    def list_meetings(self, **filters):
        """List meetings with optional filters"""
        return self.client.get('/api/v1/meetings/', params=filters)
    
    def get_meeting(self, meeting_id):
        """Get meeting details"""
        return self.client.get(f'/api/v1/meetings/{meeting_id}/')
    
    def create_meeting(self, meeting_data):
        """Create new meeting"""
        return self.client.post('/api/v1/meetings/', data=meeting_data)
    
    def update_meeting(self, meeting_id, updates):
        """Update meeting"""
        return self.client.patch(f'/api/v1/meetings/{meeting_id}/', data=updates)
    
    def schedule_debriefing(self, meeting_id, scheduled_time=None):
        """Schedule debriefing for meeting"""
        if not scheduled_time:
            # Schedule 30 minutes after meeting end
            meeting = self.get_meeting(meeting_id)
            end_time = datetime.fromisoformat(meeting['end_time'].replace('Z', '+00:00'))
            scheduled_time = end_time + timedelta(minutes=30)
        
        return self.client.post(
            f'/api/v1/meetings/{meeting_id}/schedule_debriefing/',
            data={'scheduled_time': scheduled_time.isoformat()}
        )
    
    def get_meeting_stats(self, start_date=None, end_date=None):
        """Get meeting statistics"""
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self.client.get('/api/v1/meetings/stats/', params=params)

# Usage
meetings = MeetingManager(client)

# List recent sales meetings
recent_meetings = meetings.list_meetings(
    is_sales_meeting=True,
    start_date='2024-02-01'
)

# Create new meeting
new_meeting = meetings.create_meeting({
    'title': 'Product Demo - Acme Corp',
    'start_time': '2024-02-15T14:00:00Z',
    'end_time': '2024-02-15T15:00:00Z',
    'meeting_type': 'demo',
    'participants': [
        {
            'email': 'john.smith@acme.com',
            'name': 'John Smith',
            'company': 'Acme Corp'
        }
    ]
})

# Schedule debriefing
meetings.schedule_debriefing(new_meeting['id'])
```

### Debriefing Management

```python
class DebriefingManager:
    def __init__(self, client):
        self.client = client
    
    def create_debriefing(self, meeting_id, scheduled_time=None):
        """Create debriefing session"""
        data = {'meeting_id': meeting_id}
        if scheduled_time:
            data['scheduled_time'] = scheduled_time
        
        return self.client.post('/api/v1/debriefings/', data=data)
    
    def submit_response(self, debriefing_id, question, response):
        """Submit response to debriefing question"""
        return self.client.post(
            f'/api/v1/debriefings/{debriefing_id}/respond/',
            data={
                'question': question,
                'response': response
            }
        )
    
    def get_extracted_data(self, debriefing_id):
        """Get extracted data from debriefing"""
        return self.client.get(f'/api/v1/debriefings/{debriefing_id}/extracted_data/')
    
    def complete_debriefing(self, debriefing_id):
        """Mark debriefing as complete"""
        return self.client.post(f'/api/v1/debriefings/{debriefing_id}/complete/')
    
    def conduct_full_debriefing(self, meeting_id, responses):
        """Conduct complete debriefing session"""
        # Create debriefing
        debriefing = self.create_debriefing(meeting_id)
        debriefing_id = debriefing['id']
        
        # Submit all responses
        for question, response in responses.items():
            self.submit_response(debriefing_id, question, response)
        
        # Complete debriefing
        self.complete_debriefing(debriefing_id)
        
        # Get extracted data
        return self.get_extracted_data(debriefing_id)

# Usage
debriefings = DebriefingManager(client)

# Conduct full debriefing
extracted_data = debriefings.conduct_full_debriefing(
    meeting_id=123,
    responses={
        "How did the meeting go overall?": "Very positive! The client showed strong interest.",
        "What were the main topics discussed?": "Budget, timeline, and technical requirements.",
        "Were there any concerns raised?": "They were worried about data migration complexity.",
        "What are the next steps?": "Send technical proposal by Friday."
    }
)

print("Extracted data:", extracted_data)
```

### Lead Management

```python
class LeadManager:
    def __init__(self, client):
        self.client = client
    
    def list_leads(self, **filters):
        """List leads with filters"""
        return self.client.get('/api/v1/leads/', params=filters)
    
    def create_lead(self, lead_data):
        """Create new lead"""
        return self.client.post('/api/v1/leads/', data=lead_data)
    
    def update_lead(self, lead_id, updates):
        """Update lead"""
        return self.client.patch(f'/api/v1/leads/{lead_id}/', data=updates)
    
    def match_participants(self, participants):
        """Match meeting participants to leads"""
        return self.client.post('/api/v1/leads/match/', data={'participants': participants})
    
    def get_lead_meetings(self, lead_id):
        """Get meeting history for lead"""
        return self.client.get(f'/api/v1/leads/{lead_id}/meetings/')
    
    def create_lead_from_participant(self, participant_data):
        """Create lead from meeting participant"""
        lead_data = {
            'first_name': participant_data.get('name', '').split()[0] if participant_data.get('name') else '',
            'last_name': ' '.join(participant_data.get('name', '').split()[1:]) if participant_data.get('name') else '',
            'email': participant_data['email'],
            'company': participant_data.get('company', ''),
            'source': 'meeting'
        }
        return self.create_lead(lead_data)

# Usage
leads = LeadManager(client)

# Create lead from meeting participant
participant = {
    'email': 'jane.doe@example.com',
    'name': 'Jane Doe',
    'company': 'Example Corp'
}

new_lead = leads.create_lead_from_participant(participant)

# Update lead with meeting insights
leads.update_lead(new_lead['id'], {
    'status': 'qualified',
    'qualification_score': 85,
    'decision_authority': 'high'
})
```

## JavaScript/Node.js Examples

### Basic Client Setup

```javascript
const axios = require('axios');

class NIAClient {
    constructor(baseURL, options = {}) {
        this.baseURL = baseURL.replace(/\/$/, '');
        this.accessToken = options.accessToken;
        this.refreshToken = options.refreshToken;
        
        this.client = axios.create({
            baseURL: this.baseURL,
            headers: {
                'Content-Type': 'application/json',
                ...(this.accessToken && { 'Authorization': `Bearer ${this.accessToken}` })
            }
        });
        
        // Add response interceptor for token refresh
        this.client.interceptors.response.use(
            response => response,
            async error => {
                if (error.response?.status === 401 && this.refreshToken) {
                    try {
                        await this.refreshAccessToken();
                        // Retry original request
                        return this.client.request(error.config);
                    } catch (refreshError) {
                        throw refreshError;
                    }
                }
                throw error;
            }
        );
    }
    
    async login(username, password, totpToken = null) {
        const data = { username, password };
        if (totpToken) data.totp_token = totpToken;
        
        const response = await this.client.post('/api/v1/auth/login/', data);
        
        this.accessToken = response.data.access_token;
        this.refreshToken = response.data.refresh_token;
        
        this.client.defaults.headers['Authorization'] = `Bearer ${this.accessToken}`;
        
        return response.data;
    }
    
    async refreshAccessToken() {
        const response = await this.client.post('/api/v1/auth/refresh/', {
            refresh_token: this.refreshToken
        });
        
        this.accessToken = response.data.access_token;
        this.client.defaults.headers['Authorization'] = `Bearer ${this.accessToken}`;
        
        return response.data;
    }
    
    async get(endpoint, params = {}) {
        const response = await this.client.get(endpoint, { params });
        return response.data;
    }
    
    async post(endpoint, data = {}) {
        const response = await this.client.post(endpoint, data);
        return response.data;
    }
    
    async patch(endpoint, data = {}) {
        const response = await this.client.patch(endpoint, data);
        return response.data;
    }
    
    async delete(endpoint) {
        const response = await this.client.delete(endpoint);
        return response.status === 204;
    }
}

// Usage
const client = new NIAClient('http://localhost:8000');
await client.login('john.doe@company.com', 'securepassword123');
```

### Meeting Intelligence Workflow

```javascript
class MeetingIntelligenceWorkflow {
    constructor(client) {
        this.client = client;
    }
    
    async processNewMeeting(calendarEvent) {
        try {
            // 1. Create meeting from calendar event
            const meeting = await this.client.post('/api/v1/meetings/', {
                title: calendarEvent.title,
                start_time: calendarEvent.start_time,
                end_time: calendarEvent.end_time,
                calendar_event_id: calendarEvent.id,
                participants: calendarEvent.attendees.map(email => ({ email }))
            });
            
            console.log(`Created meeting: ${meeting.id}`);
            
            // 2. Match participants to leads
            const matchResults = await this.client.post('/api/v1/leads/match/', {
                participants: meeting.participants
            });
            
            console.log(`Matched ${matchResults.matched_count} participants`);
            
            // 3. Schedule debriefing
            const debriefingTime = new Date(meeting.end_time);
            debriefingTime.setMinutes(debriefingTime.getMinutes() + 30);
            
            const debriefing = await this.client.post('/api/v1/debriefings/', {
                meeting_id: meeting.id,
                scheduled_time: debriefingTime.toISOString()
            });
            
            console.log(`Scheduled debriefing: ${debriefing.id}`);
            
            return {
                meeting,
                matchResults,
                debriefing
            };
            
        } catch (error) {
            console.error('Error processing meeting:', error.response?.data || error.message);
            throw error;
        }
    }
    
    async conductDebriefing(debriefingId, responses) {
        try {
            // Submit all responses
            for (const [question, response] of Object.entries(responses)) {
                await this.client.post(`/api/v1/debriefings/${debriefingId}/respond/`, {
                    question,
                    response
                });
            }
            
            // Complete debriefing
            await this.client.post(`/api/v1/debriefings/${debriefingId}/complete/`);
            
            // Get extracted data
            const extractedData = await this.client.get(
                `/api/v1/debriefings/${debriefingId}/extracted_data/`
            );
            
            console.log('Debriefing completed, extracted data:', extractedData);
            
            return extractedData;
            
        } catch (error) {
            console.error('Error conducting debriefing:', error.response?.data || error.message);
            throw error;
        }
    }
    
    async syncToCRM(extractedData) {
        try {
            // Trigger CRM sync with extracted data
            const syncResult = await this.client.post('/api/v1/crm/sync/', {
                sync_type: 'meeting_data',
                data: extractedData
            });
            
            console.log('CRM sync initiated:', syncResult.sync_id);
            
            // Poll for sync completion
            let syncStatus;
            do {
                await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
                syncStatus = await this.client.get('/api/v1/crm/sync/status/');
            } while (syncStatus.status === 'in_progress');
            
            console.log('CRM sync completed:', syncStatus);
            
            return syncStatus;
            
        } catch (error) {
            console.error('Error syncing to CRM:', error.response?.data || error.message);
            throw error;
        }
    }
}

// Usage
const workflow = new MeetingIntelligenceWorkflow(client);

// Process new meeting
const calendarEvent = {
    id: 'cal_event_123',
    title: 'Product Demo - Acme Corp',
    start_time: '2024-02-15T14:00:00Z',
    end_time: '2024-02-15T15:00:00Z',
    attendees: ['john.smith@acme.com', 'sales@company.com']
};

const result = await workflow.processNewMeeting(calendarEvent);

// Conduct debriefing
const responses = {
    "How did the meeting go overall?": "Very positive! Strong interest shown.",
    "What were the main topics discussed?": "Budget, timeline, technical requirements.",
    "Were there any concerns raised?": "Data migration complexity concerns.",
    "What are the next steps?": "Send technical proposal by Friday."
};

const extractedData = await workflow.conductDebriefing(result.debriefing.id, responses);

// Sync to CRM
await workflow.syncToCRM(extractedData);
```

## React Frontend Example

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

// API Client Hook
const useNIAClient = () => {
    const [client, setClient] = useState(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    
    useEffect(() => {
        const token = localStorage.getItem('nia_access_token');
        if (token) {
            const apiClient = axios.create({
                baseURL: 'http://localhost:8000/api/v1',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            setClient(apiClient);
            setIsAuthenticated(true);
        }
    }, []);
    
    const login = async (username, password, totpToken = null) => {
        try {
            const response = await axios.post('http://localhost:8000/api/v1/auth/login/', {
                username,
                password,
                ...(totpToken && { totp_token: totpToken })
            });
            
            const { access_token, refresh_token } = response.data;
            
            localStorage.setItem('nia_access_token', access_token);
            localStorage.setItem('nia_refresh_token', refresh_token);
            
            const apiClient = axios.create({
                baseURL: 'http://localhost:8000/api/v1',
                headers: {
                    'Authorization': `Bearer ${access_token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            setClient(apiClient);
            setIsAuthenticated(true);
            
            return response.data;
        } catch (error) {
            throw error;
        }
    };
    
    const logout = () => {
        localStorage.removeItem('nia_access_token');
        localStorage.removeItem('nia_refresh_token');
        setClient(null);
        setIsAuthenticated(false);
    };
    
    return { client, isAuthenticated, login, logout };
};

// Meeting List Component
const MeetingList = () => {
    const { client } = useNIAClient();
    const [meetings, setMeetings] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        meeting_type: '',
        is_sales_meeting: '',
        search: ''
    });
    
    useEffect(() => {
        if (client) {
            fetchMeetings();
        }
    }, [client, filters]);
    
    const fetchMeetings = async () => {
        try {
            setLoading(true);
            const params = Object.fromEntries(
                Object.entries(filters).filter(([_, value]) => value !== '')
            );
            
            const response = await client.get('/meetings/', { params });
            setMeetings(response.data.results);
        } catch (error) {
            console.error('Error fetching meetings:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const scheduleDebriefing = async (meetingId) => {
        try {
            await client.post(`/meetings/${meetingId}/schedule_debriefing/`);
            fetchMeetings(); // Refresh list
        } catch (error) {
            console.error('Error scheduling debriefing:', error);
        }
    };
    
    if (loading) return <div>Loading meetings...</div>;
    
    return (
        <div>
            <h2>Meetings</h2>
            
            {/* Filters */}
            <div className="filters">
                <select
                    value={filters.meeting_type}
                    onChange={(e) => setFilters({...filters, meeting_type: e.target.value})}
                >
                    <option value="">All Types</option>
                    <option value="discovery">Discovery</option>
                    <option value="demo">Demo</option>
                    <option value="negotiation">Negotiation</option>
                    <option value="follow_up">Follow Up</option>
                </select>
                
                <select
                    value={filters.is_sales_meeting}
                    onChange={(e) => setFilters({...filters, is_sales_meeting: e.target.value})}
                >
                    <option value="">All Meetings</option>
                    <option value="true">Sales Meetings</option>
                    <option value="false">Non-Sales Meetings</option>
                </select>
                
                <input
                    type="text"
                    placeholder="Search meetings..."
                    value={filters.search}
                    onChange={(e) => setFilters({...filters, search: e.target.value})}
                />
            </div>
            
            {/* Meeting List */}
            <div className="meeting-list">
                {meetings.map(meeting => (
                    <div key={meeting.id} className="meeting-card">
                        <h3>{meeting.title}</h3>
                        <p>Type: {meeting.meeting_type}</p>
                        <p>Date: {new Date(meeting.start_time).toLocaleDateString()}</p>
                        <p>Participants: {meeting.participant_count}</p>
                        
                        {!meeting.debriefing_scheduled && (
                            <button onClick={() => scheduleDebriefing(meeting.id)}>
                                Schedule Debriefing
                            </button>
                        )}
                        
                        {meeting.debriefing_completed && (
                            <span className="badge">Debriefing Complete</span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
};

// Login Component
const Login = () => {
    const { login } = useNIAClient();
    const [credentials, setCredentials] = useState({
        username: '',
        password: '',
        totpToken: ''
    });
    const [requires2FA, setRequires2FA] = useState(false);
    const [error, setError] = useState('');
    
    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const result = await login(
                credentials.username,
                credentials.password,
                credentials.totpToken || null
            );
            
            if (result.requires_2fa) {
                setRequires2FA(true);
            }
        } catch (error) {
            setError(error.response?.data?.error || 'Login failed');
        }
    };
    
    return (
        <form onSubmit={handleSubmit}>
            <h2>Login to NIA</h2>
            
            {error && <div className="error">{error}</div>}
            
            <input
                type="text"
                placeholder="Username or Email"
                value={credentials.username}
                onChange={(e) => setCredentials({...credentials, username: e.target.value})}
                required
            />
            
            <input
                type="password"
                placeholder="Password"
                value={credentials.password}
                onChange={(e) => setCredentials({...credentials, password: e.target.value})}
                required
            />
            
            {requires2FA && (
                <input
                    type="text"
                    placeholder="2FA Token"
                    value={credentials.totpToken}
                    onChange={(e) => setCredentials({...credentials, totpToken: e.target.value})}
                    required
                />
            )}
            
            <button type="submit">Login</button>
        </form>
    );
};

// Main App Component
const App = () => {
    const { isAuthenticated } = useNIAClient();
    
    return (
        <div className="app">
            {isAuthenticated ? <MeetingList /> : <Login />}
        </div>
    );
};

export default App;
```

## Error Handling Best Practices

### Python Error Handling

```python
import requests
from requests.exceptions import RequestException, HTTPError, Timeout

class NIAAPIError(Exception):
    """Base exception for NIA API errors"""
    pass

class NIAAuthenticationError(NIAAPIError):
    """Authentication related errors"""
    pass

class NIAValidationError(NIAAPIError):
    """Validation errors"""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or {}

class NIARateLimitError(NIAAPIError):
    """Rate limit exceeded"""
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after

def handle_api_response(response):
    """Handle API response and raise appropriate exceptions"""
    try:
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        if response.status_code == 400:
            error_data = response.json()
            raise NIAValidationError("Validation error", error_data)
        elif response.status_code == 401:
            raise NIAAuthenticationError("Authentication failed")
        elif response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            raise NIARateLimitError("Rate limit exceeded", retry_after)
        else:
            raise NIAAPIError(f"API error: {response.status_code}")
    except RequestException as e:
        raise NIAAPIError(f"Request failed: {str(e)}")

# Usage with error handling
try:
    meetings = client.get('/api/v1/meetings/')
except NIAAuthenticationError:
    # Handle authentication error - maybe refresh token
    client.refresh_access_token()
    meetings = client.get('/api/v1/meetings/')
except NIAValidationError as e:
    # Handle validation errors
    print("Validation errors:", e.errors)
except NIARateLimitError as e:
    # Handle rate limiting
    print(f"Rate limited, retry after {e.retry_after} seconds")
    time.sleep(int(e.retry_after))
except NIAAPIError as e:
    # Handle other API errors
    print(f"API error: {e}")
```

### JavaScript Error Handling

```javascript
class NIAAPIError extends Error {
    constructor(message, status, data) {
        super(message);
        this.name = 'NIAAPIError';
        this.status = status;
        this.data = data;
    }
}

class NIAClient {
    // ... previous code ...
    
    async handleResponse(response) {
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            
            switch (response.status) {
                case 400:
                    throw new NIAAPIError('Validation error', 400, errorData);
                case 401:
                    throw new NIAAPIError('Authentication failed', 401, errorData);
                case 403:
                    throw new NIAAPIError('Permission denied', 403, errorData);
                case 404:
                    throw new NIAAPIError('Resource not found', 404, errorData);
                case 429:
                    const retryAfter = response.headers.get('Retry-After');
                    throw new NIAAPIError('Rate limit exceeded', 429, { retryAfter });
                default:
                    throw new NIAAPIError('API error', response.status, errorData);
            }
        }
        
        return response.json();
    }
    
    async withRetry(operation, maxRetries = 3) {
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return await operation();
            } catch (error) {
                if (error.status === 429 && attempt < maxRetries) {
                    const retryAfter = error.data?.retryAfter || Math.pow(2, attempt);
                    console.log(`Rate limited, retrying in ${retryAfter} seconds...`);
                    await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
                    continue;
                }
                
                if (error.status === 401 && this.refreshToken && attempt < maxRetries) {
                    try {
                        await this.refreshAccessToken();
                        continue;
                    } catch (refreshError) {
                        throw error;
                    }
                }
                
                throw error;
            }
        }
    }
}

// Usage with error handling
try {
    const meetings = await client.withRetry(() => client.get('/meetings/'));
    console.log('Meetings:', meetings);
} catch (error) {
    if (error instanceof NIAAPIError) {
        switch (error.status) {
            case 400:
                console.error('Validation errors:', error.data);
                break;
            case 401:
                console.error('Authentication failed, please login again');
                // Redirect to login
                break;
            case 403:
                console.error('Permission denied');
                break;
            case 429:
                console.error('Rate limited, please try again later');
                break;
            default:
                console.error('API error:', error.message);
        }
    } else {
        console.error('Unexpected error:', error);
    }
}
```

These examples provide comprehensive guidance for integrating with the NIA Meeting Intelligence API across different programming languages and scenarios.