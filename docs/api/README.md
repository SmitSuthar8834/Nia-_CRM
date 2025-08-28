# NIA Meeting Intelligence API Documentation

## Overview

The NIA (AI Assistant) CRM Meeting Intelligence API provides comprehensive endpoints for managing meeting intelligence, automated debriefing, lead management, CRM synchronization, and analytics. This RESTful API is built with Django REST Framework and follows OpenAPI 3.0 specifications.

## Base URL

- **Development**: `http://localhost:8000/api/v1/`
- **Production**: `https://api.nia-intelligence.com/api/v1/`

## Interactive Documentation

- **Swagger UI**: `/api/docs/` - Interactive API documentation with request/response examples
- **ReDoc**: `/api/redoc/` - Alternative documentation interface
- **OpenAPI Schema**: `/api/schema/` - Raw OpenAPI 3.0 schema

## Authentication

The API supports two authentication methods:

### 1. JWT Token Authentication (Recommended)

```bash
# Login to get tokens
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-username",
    "password": "your-password"
  }'

# Response
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "john.doe@company.com",
    "role": "sales_rep"
  }
}

# Use token in subsequent requests
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### 2. Session Authentication

```bash
# Login with session
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "username": "your-username",
    "password": "your-password"
  }'

# Use session in subsequent requests
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -b cookies.txt
```

## API Versioning

The API uses URL-based versioning:
- Current version: `v1`
- All endpoints are prefixed with `/api/v1/`

## Rate Limiting

- **Authenticated users**: 1000 requests per hour
- **Anonymous users**: 100 requests per hour
- Rate limit headers are included in responses:
  - `X-RateLimit-Limit`: Request limit per hour
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Time when limit resets

## Error Handling

The API uses standard HTTP status codes and returns consistent error responses:

```json
{
  "error": "Error message",
  "details": {
    "field_name": ["Specific field error"]
  },
  "code": "ERROR_CODE"
}
```

### Common Status Codes

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Permission denied
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Pagination

List endpoints use cursor-based pagination:

```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/meetings/?page=2",
  "previous": null,
  "results": [...]
}
```

Query parameters:
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

## Filtering and Search

Most list endpoints support filtering and search:

```bash
# Filter meetings by type
GET /api/v1/meetings/?meeting_type=discovery

# Search meetings
GET /api/v1/meetings/?search=quarterly+review

# Date range filtering
GET /api/v1/meetings/?start_date=2024-01-01&end_date=2024-01-31

# Multiple filters
GET /api/v1/meetings/?meeting_type=demo&is_sales_meeting=true&organizer=5
```

## Webhooks

The API supports webhooks for real-time notifications:

### Supported Events

- `meeting.created`: New meeting detected
- `meeting.updated`: Meeting information updated
- `debriefing.completed`: Debriefing session completed
- `lead.matched`: New lead matched to meeting participant
- `crm.sync.completed`: CRM synchronization completed
- `crm.sync.failed`: CRM synchronization failed

### Webhook Configuration

```bash
# Create webhook endpoint
POST /api/v1/webhooks/
{
  "url": "https://your-app.com/webhooks/nia",
  "events": ["meeting.created", "debriefing.completed"],
  "secret": "your-webhook-secret"
}
```

## SDK and Client Libraries

### Python SDK

```python
from nia_client import NIAClient

# Initialize client
client = NIAClient(
    base_url="http://localhost:8000/api/v1/",
    username="your-username",
    password="your-password"
)

# List meetings
meetings = client.meetings.list(meeting_type="discovery")

# Get meeting details
meeting = client.meetings.get(meeting_id)

# Start debriefing
debriefing = client.debriefings.create(meeting_id=meeting_id)
```

### JavaScript SDK

```javascript
import { NIAClient } from '@nia/client';

// Initialize client
const client = new NIAClient({
  baseURL: 'http://localhost:8000/api/v1/',
  username: 'your-username',
  password: 'your-password'
});

// List meetings
const meetings = await client.meetings.list({ meetingType: 'discovery' });

// Get meeting details
const meeting = await client.meetings.get(meetingId);

// Start debriefing
const debriefing = await client.debriefings.create({ meetingId });
```

## Common Use Cases

### 1. Meeting Intelligence Workflow

```bash
# 1. Detect new meetings from calendar
POST /api/v1/calendar/sync/

# 2. Get detected meetings
GET /api/v1/meetings/?is_sales_meeting=true&debriefing_scheduled=false

# 3. Schedule debriefing for a meeting
POST /api/v1/meetings/{id}/schedule_debriefing/

# 4. Conduct debriefing session
POST /api/v1/debriefings/
{
  "meeting_id": 123,
  "responses": [
    {
      "question": "How did the meeting go?",
      "response": "Very positive, they're interested in our solution"
    }
  ]
}

# 5. Get extracted data
GET /api/v1/debriefings/{id}/extracted_data/

# 6. Sync to CRM
POST /api/v1/crm/sync/
```

### 2. Lead Management

```bash
# 1. Get unmatched meeting participants
GET /api/v1/meetings/participants/?matched_lead__isnull=true

# 2. Match participants to leads
POST /api/v1/leads/match/
{
  "participants": [
    {
      "email": "prospect@company.com",
      "name": "John Smith",
      "company": "Acme Corp"
    }
  ]
}

# 3. Create new lead from participant
POST /api/v1/leads/
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "prospect@company.com",
  "company": "Acme Corp",
  "source": "meeting"
}
```

### 3. Analytics and Reporting

```bash
# Get meeting statistics
GET /api/v1/analytics/meetings/stats/

# Get debriefing completion rates
GET /api/v1/analytics/debriefings/completion_rate/

# Get lead conversion metrics
GET /api/v1/analytics/leads/conversion/

# Export analytics data
GET /api/v1/analytics/export/?format=csv&start_date=2024-01-01
```

## Testing

### Test Environment

- **Base URL**: `http://localhost:8000/api/v1/`
- **Test User**: `test@example.com` / `testpassword123`

### Postman Collection

Import the Postman collection for easy API testing:

```bash
curl -o nia-api.postman_collection.json \
  http://localhost:8000/api/postman_collection/
```

### cURL Examples

See the [cURL Examples](./curl-examples.md) file for comprehensive request examples.

## Support

- **Documentation**: [https://docs.nia-intelligence.com](https://docs.nia-intelligence.com)
- **API Support**: [api-support@nia-intelligence.com](mailto:api-support@nia-intelligence.com)
- **Status Page**: [https://status.nia-intelligence.com](https://status.nia-intelligence.com)

## Changelog

### v1.0.0 (Current)
- Initial API release
- Meeting intelligence endpoints
- Debriefing management
- Lead matching and management
- CRM synchronization
- Analytics and reporting
- Authentication and authorization
- Webhook support