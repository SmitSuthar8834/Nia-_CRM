# cURL API Examples

This document provides comprehensive cURL examples for all NIA Meeting Intelligence API endpoints.

## Authentication

### Login

```bash
# Basic login
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe@company.com",
    "password": "securepassword123"
  }'

# Login with 2FA
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john.doe@company.com",
    "password": "securepassword123",
    "totp_token": "123456"
  }'
```

### Refresh Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }'
```

### Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## User Profile

### Get Profile

```bash
curl -X GET http://localhost:8000/api/v1/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Update Profile

```bash
curl -X PATCH http://localhost:8000/api/v1/auth/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "phone": "+1-555-123-4567",
    "timezone": "America/New_York"
  }'
```

## Two-Factor Authentication

### Get 2FA Setup Info

```bash
curl -X GET http://localhost:8000/api/v1/auth/2fa/setup/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Enable 2FA

```bash
curl -X POST http://localhost:8000/api/v1/auth/2fa/setup/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "123456"
  }'
```

### Generate Backup Codes

```bash
curl -X POST http://localhost:8000/api/v1/auth/2fa/backup-codes/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Meetings

### List Meetings

```bash
# Basic list
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# With filters
curl -X GET "http://localhost:8000/api/v1/meetings/?meeting_type=discovery&is_sales_meeting=true&page_size=50" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Search meetings
curl -X GET "http://localhost:8000/api/v1/meetings/?search=quarterly+review" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Date range filter
curl -X GET "http://localhost:8000/api/v1/meetings/?start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Meeting Details

```bash
curl -X GET http://localhost:8000/api/v1/meetings/123/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Create Meeting

```bash
curl -X POST http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Demo - Acme Corp",
    "start_time": "2024-02-15T14:00:00Z",
    "end_time": "2024-02-15T15:00:00Z",
    "meeting_type": "demo",
    "calendar_event_id": "cal_event_123",
    "participants": [
      {
        "email": "john.smith@acme.com",
        "name": "John Smith",
        "company": "Acme Corp"
      }
    ]
  }'
```

### Update Meeting

```bash
curl -X PATCH http://localhost:8000/api/v1/meetings/123/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_type": "negotiation",
    "confidence_score": 0.95
  }'
```

### Schedule Debriefing

```bash
curl -X POST http://localhost:8000/api/v1/meetings/123/schedule_debriefing/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_time": "2024-02-15T15:30:00Z"
  }'
```

### Get Meeting Statistics

```bash
curl -X GET http://localhost:8000/api/v1/meetings/stats/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Detect Sales Meetings

```bash
curl -X POST http://localhost:8000/api/v1/meetings/detect/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "calendar_events": [
      {
        "id": "cal_event_456",
        "title": "Client Meeting - ABC Corp",
        "start_time": "2024-02-16T10:00:00Z",
        "end_time": "2024-02-16T11:00:00Z",
        "attendees": ["client@abc.com", "sales@company.com"]
      }
    ]
  }'
```

## Meeting Participants

### List Participants

```bash
curl -X GET http://localhost:8000/api/v1/meetings/123/participants/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Match Participants

```bash
curl -X POST http://localhost:8000/api/v1/meetings/123/match_participants/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Debriefings

### List Debriefing Sessions

```bash
curl -X GET http://localhost:8000/api/v1/debriefings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Create Debriefing Session

```bash
curl -X POST http://localhost:8000/api/v1/debriefings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 123,
    "scheduled_time": "2024-02-15T15:30:00Z"
  }'
```

### Get Debriefing Details

```bash
curl -X GET http://localhost:8000/api/v1/debriefings/456/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Submit Debriefing Response

```bash
curl -X POST http://localhost:8000/api/v1/debriefings/456/respond/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How did the meeting go overall?",
    "response": "Very positive! The client showed strong interest in our solution and asked detailed technical questions."
  }'
```

### Get Extracted Data

```bash
curl -X GET http://localhost:8000/api/v1/debriefings/456/extracted_data/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Complete Debriefing

```bash
curl -X POST http://localhost:8000/api/v1/debriefings/456/complete/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Leads

### List Leads

```bash
# Basic list
curl -X GET http://localhost:8000/api/v1/leads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# With filters
curl -X GET "http://localhost:8000/api/v1/leads/?status=qualified&company=Acme+Corp" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Search leads
curl -X GET "http://localhost:8000/api/v1/leads/?search=john+smith" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Lead Details

```bash
curl -X GET http://localhost:8000/api/v1/leads/789/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Create Lead

```bash
curl -X POST http://localhost:8000/api/v1/leads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "phone": "+1-555-987-6543",
    "company": "Example Corp",
    "title": "VP of Sales",
    "source": "meeting"
  }'
```

### Update Lead

```bash
curl -X PATCH http://localhost:8000/api/v1/leads/789/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "opportunity",
    "qualification_score": 85,
    "decision_authority": "high"
  }'
```

### Match Meeting Participants

```bash
curl -X POST http://localhost:8000/api/v1/leads/match/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "participants": [
      {
        "email": "prospect@company.com",
        "name": "John Smith",
        "company": "Acme Corp"
      }
    ]
  }'
```

### Get Lead Meeting History

```bash
curl -X GET http://localhost:8000/api/v1/leads/789/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Calendar Integration

### List Calendar Integrations

```bash
curl -X GET http://localhost:8000/api/v1/calendar/integrations/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Create Calendar Integration

```bash
curl -X POST http://localhost:8000/api/v1/calendar/integrations/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "google",
    "credentials": {
      "access_token": "ya29.a0AfH6SMC...",
      "refresh_token": "1//04...",
      "token_uri": "https://oauth2.googleapis.com/token",
      "client_id": "your-client-id.apps.googleusercontent.com",
      "client_secret": "your-client-secret"
    }
  }'
```

### Sync Calendar

```bash
curl -X POST http://localhost:8000/api/v1/calendar/sync/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "google",
    "start_date": "2024-02-01",
    "end_date": "2024-02-29"
  }'
```

### Get Sync Status

```bash
curl -X GET http://localhost:8000/api/v1/calendar/sync/status/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## CRM Synchronization

### Trigger CRM Sync

```bash
curl -X POST http://localhost:8000/api/v1/crm/sync/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sync_type": "bidirectional",
    "entities": ["leads", "activities", "opportunities"]
  }'
```

### Get Sync Status

```bash
curl -X GET http://localhost:8000/api/v1/crm/sync/status/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Sync Conflicts

```bash
curl -X GET http://localhost:8000/api/v1/crm/conflicts/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Resolve Conflict

```bash
curl -X POST http://localhost:8000/api/v1/crm/conflicts/123/resolve/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "use_local",
    "comment": "Local data is more recent"
  }'
```

### Update Lead from Meeting Data

```bash
curl -X POST http://localhost:8000/api/v1/crm/leads/789/update_from_meeting/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_id": 123,
    "extracted_data": {
      "budget": "$50,000",
      "timeline": "Q2 2024",
      "decision_makers": ["John Smith", "Jane Doe"],
      "requirements": ["API integration", "Custom reporting"]
    }
  }'
```

## AI Engine

### Generate Questions

```bash
curl -X POST http://localhost:8000/api/v1/ai/questions/generate/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_context": {
      "meeting_type": "discovery",
      "participants": ["prospect@company.com"],
      "company": "Acme Corp",
      "previous_meetings": []
    }
  }'
```

### Extract Data from Conversation

```bash
curl -X POST http://localhost:8000/api/v1/ai/extract/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation": "The meeting went very well. John mentioned they have a budget of $100k and need to make a decision by end of Q2. They are currently using Salesforce but are looking for better reporting capabilities.",
    "extraction_types": ["budget", "timeline", "requirements", "competitive_intel"]
  }'
```

### Process Response

```bash
curl -X POST http://localhost:8000/api/v1/ai/process_response/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was the client'\''s main concern?",
    "response": "They were worried about data migration and integration complexity",
    "context": {
      "meeting_type": "demo",
      "company": "Acme Corp"
    }
  }'
```

## Analytics

### Get Dashboard Metrics

```bash
curl -X GET http://localhost:8000/api/v1/analytics/dashboard/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Meeting Statistics

```bash
curl -X GET "http://localhost:8000/api/v1/analytics/meetings/stats/?start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Debriefing Completion Rate

```bash
curl -X GET http://localhost:8000/api/v1/analytics/debriefings/completion_rate/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Lead Conversion Metrics

```bash
curl -X GET http://localhost:8000/api/v1/analytics/leads/conversion/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get User Engagement Analytics

```bash
curl -X GET http://localhost:8000/api/v1/analytics/users/engagement/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Export Analytics Data

```bash
# CSV export
curl -X GET "http://localhost:8000/api/v1/analytics/export/?format=csv&start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o analytics_data.csv

# JSON export
curl -X GET "http://localhost:8000/api/v1/analytics/export/?format=json&metrics=meetings,debriefings,leads" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o analytics_data.json
```

## Error Handling Examples

### Validation Error (400)

```bash
curl -X POST http://localhost:8000/api/v1/leads/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "",
    "email": "invalid-email"
  }'

# Response:
# {
#   "first_name": ["This field may not be blank."],
#   "last_name": ["This field is required."],
#   "email": ["Enter a valid email address."]
# }
```

### Authentication Error (401)

```bash
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer invalid_token"

# Response:
# {
#   "detail": "Given token not valid for any token type",
#   "code": "token_not_valid",
#   "messages": [
#     {
#       "token_class": "AccessToken",
#       "token_type": "access",
#       "message": "Token is invalid or expired"
#     }
#   ]
# }
```

### Permission Error (403)

```bash
curl -X DELETE http://localhost:8000/api/v1/meetings/123/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Response (if user doesn't have permission):
# {
#   "detail": "You do not have permission to perform this action."
# }
```

### Not Found Error (404)

```bash
curl -X GET http://localhost:8000/api/v1/meetings/99999/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Response:
# {
#   "detail": "Not found."
# }
```

### Rate Limit Error (429)

```bash
# After exceeding rate limit
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Response:
# {
#   "detail": "Request was throttled. Expected available in 3600 seconds."
# }
```