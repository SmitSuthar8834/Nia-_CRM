# NIA Meeting Intelligence API Documentation

Welcome to the comprehensive documentation for the NIA (AI Assistant) CRM Meeting Intelligence API. This documentation provides everything you need to integrate with and use the NIA API effectively.

## 📚 Documentation Overview

### Getting Started
- **[API Overview](./README.md)** - Introduction, authentication, and basic concepts
- **[Quick Start Guide](#quick-start)** - Get up and running in 5 minutes
- **[Authentication Guide](#authentication)** - Detailed authentication setup

### API Reference
- **[Interactive Documentation](http://localhost:8000/api/docs/)** - Swagger UI (when server is running)
- **[Alternative Documentation](http://localhost:8000/api/redoc/)** - ReDoc interface
- **[OpenAPI Schema](http://localhost:8000/api/schema/)** - Raw OpenAPI 3.0 schema

### Integration Guides
- **[Client Examples](./client-examples.md)** - Code examples in Python, JavaScript, and more
- **[cURL Examples](./curl-examples.md)** - Complete cURL command reference
- **[Testing Guide](./testing-guide.md)** - Testing strategies and examples

### Advanced Topics
- **[Versioning Strategy](./versioning-strategy.md)** - API versioning and migration
- **[Rate Limiting](#rate-limiting)** - Usage limits and best practices
- **[Error Handling](#error-handling)** - Error codes and troubleshooting

## 🚀 Quick Start

### 1. Get Your API Credentials

```bash
# Create a user account (if using local development)
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-username",
    "email": "your-email@example.com",
    "password": "your-secure-password"
  }'
```

### 2. Authenticate and Get Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-username",
    "password": "your-secure-password"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "your-username",
    "email": "your-email@example.com",
    "role": "sales_rep"
  }
}
```

### 3. Make Your First API Call

```bash
curl -X GET http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Create a Meeting

```bash
curl -X POST http://localhost:8000/api/v1/meetings/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Demo - Acme Corp",
    "start_time": "2024-02-15T14:00:00Z",
    "end_time": "2024-02-15T15:00:00Z",
    "meeting_type": "demo",
    "participants": [
      {
        "email": "john.smith@acme.com",
        "name": "John Smith",
        "company": "Acme Corp"
      }
    ]
  }'
```

## 🔐 Authentication

The NIA API supports two authentication methods:

### JWT Token Authentication (Recommended)

1. **Login** to get access and refresh tokens
2. **Include** the access token in the `Authorization` header
3. **Refresh** the token when it expires

```python
import requests

# Login
response = requests.post('http://localhost:8000/api/v1/auth/login/', json={
    'username': 'your-username',
    'password': 'your-password'
})
tokens = response.json()

# Use token for API calls
headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
meetings = requests.get('http://localhost:8000/api/v1/meetings/', headers=headers)
```

### Session Authentication

Use Django's built-in session authentication for web applications:

```javascript
// Login with session
fetch('/api/v1/auth/login/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  credentials: 'include',
  body: JSON.stringify({
    username: 'your-username',
    password: 'your-password'
  })
});

// Subsequent requests automatically include session cookie
fetch('/api/v1/meetings/', {
  credentials: 'include'
});
```

## 📊 API Endpoints Overview

### Authentication Endpoints
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/refresh/` - Refresh access token
- `POST /api/v1/auth/logout/` - User logout
- `GET /api/v1/auth/profile/` - Get user profile
- `PATCH /api/v1/auth/profile/` - Update user profile

### Meeting Intelligence Endpoints
- `GET /api/v1/meetings/` - List meetings
- `POST /api/v1/meetings/` - Create meeting
- `GET /api/v1/meetings/{id}/` - Get meeting details
- `PATCH /api/v1/meetings/{id}/` - Update meeting
- `POST /api/v1/meetings/{id}/schedule_debriefing/` - Schedule debriefing
- `GET /api/v1/meetings/stats/` - Get meeting statistics

### Debriefing Endpoints
- `GET /api/v1/debriefings/` - List debriefing sessions
- `POST /api/v1/debriefings/` - Create debriefing session
- `GET /api/v1/debriefings/{id}/` - Get debriefing details
- `POST /api/v1/debriefings/{id}/respond/` - Submit response
- `POST /api/v1/debriefings/{id}/complete/` - Complete debriefing
- `GET /api/v1/debriefings/{id}/extracted_data/` - Get extracted data

### Lead Management Endpoints
- `GET /api/v1/leads/` - List leads
- `POST /api/v1/leads/` - Create lead
- `GET /api/v1/leads/{id}/` - Get lead details
- `PATCH /api/v1/leads/{id}/` - Update lead
- `POST /api/v1/leads/match/` - Match meeting participants
- `GET /api/v1/leads/{id}/meetings/` - Get lead meeting history

### CRM Synchronization Endpoints
- `POST /api/v1/crm/sync/` - Trigger CRM sync
- `GET /api/v1/crm/sync/status/` - Get sync status
- `GET /api/v1/crm/conflicts/` - Get sync conflicts
- `POST /api/v1/crm/conflicts/{id}/resolve/` - Resolve conflict

### Analytics Endpoints
- `GET /api/v1/analytics/dashboard/` - Get dashboard metrics
- `GET /api/v1/analytics/meetings/stats/` - Get meeting statistics
- `GET /api/v1/analytics/debriefings/completion_rate/` - Get completion rates
- `GET /api/v1/analytics/export/` - Export analytics data

## 🚦 Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Authenticated users**: 1,000 requests per hour
- **Anonymous users**: 100 requests per hour

Rate limit information is included in response headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

### Best Practices
- **Cache responses** when possible
- **Use pagination** for large datasets
- **Implement exponential backoff** for retries
- **Monitor rate limit headers**

## ❌ Error Handling

The API uses standard HTTP status codes and returns consistent error responses:

### Common Status Codes
- `200 OK` - Request successful
- `201 Created` - Resource created
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Error Response Format
```json
{
  "error": "Validation failed",
  "details": {
    "email": ["Enter a valid email address."],
    "password": ["This field may not be blank."]
  },
  "code": "validation_error",
  "timestamp": "2024-02-15T14:30:00Z"
}
```

### Error Handling Example
```python
import requests

try:
    response = requests.post('/api/v1/meetings/', json=meeting_data)
    response.raise_for_status()
    meeting = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 400:
        errors = e.response.json()
        print(f"Validation errors: {errors['details']}")
    elif e.response.status_code == 401:
        print("Authentication required")
    elif e.response.status_code == 429:
        print("Rate limit exceeded")
    else:
        print(f"API error: {e.response.status_code}")
```

## 🔄 Webhooks

The API supports webhooks for real-time notifications:

### Supported Events
- `meeting.created` - New meeting detected
- `meeting.updated` - Meeting information updated
- `debriefing.completed` - Debriefing session completed
- `lead.matched` - New lead matched to participant
- `crm.sync.completed` - CRM synchronization completed

### Webhook Setup
```bash
curl -X POST http://localhost:8000/api/v1/webhooks/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhooks/nia",
    "events": ["meeting.created", "debriefing.completed"],
    "secret": "your-webhook-secret"
  }'
```

## 📱 SDKs and Libraries

### Official SDKs
- **Python SDK**: `pip install nia-client`
- **JavaScript SDK**: `npm install @nia/client`
- **PHP SDK**: `composer require nia/client`

### Community Libraries
- **Ruby Gem**: `gem install nia-ruby`
- **Go Module**: `go get github.com/nia/go-client`

## 🛠️ Development Tools

### Postman Collection
Import our comprehensive Postman collection:
```bash
curl -o nia-api.postman_collection.json \
  http://localhost:8000/api/postman_collection/
```

### OpenAPI Generator
Generate client libraries using OpenAPI Generator:
```bash
# Generate Python client
openapi-generator generate \
  -i http://localhost:8000/api/schema/ \
  -g python \
  -o ./nia-python-client

# Generate JavaScript client
openapi-generator generate \
  -i http://localhost:8000/api/schema/ \
  -g javascript \
  -o ./nia-js-client
```

## 📞 Support and Resources

### Documentation
- **API Reference**: [https://docs.nia-intelligence.com/api/](https://docs.nia-intelligence.com/api/)
- **User Guide**: [https://docs.nia-intelligence.com/guide/](https://docs.nia-intelligence.com/guide/)
- **FAQ**: [https://docs.nia-intelligence.com/faq/](https://docs.nia-intelligence.com/faq/)

### Support Channels
- **Email**: [api-support@nia-intelligence.com](mailto:api-support@nia-intelligence.com)
- **Community Forum**: [https://community.nia-intelligence.com](https://community.nia-intelligence.com)
- **GitHub Issues**: [https://github.com/nia/api-issues](https://github.com/nia/api-issues)

### Status and Updates
- **Status Page**: [https://status.nia-intelligence.com](https://status.nia-intelligence.com)
- **Changelog**: [https://docs.nia-intelligence.com/changelog/](https://docs.nia-intelligence.com/changelog/)
- **API Updates**: Subscribe to our newsletter for API updates

## 🎯 Next Steps

1. **Explore the Interactive Documentation** at `/api/docs/`
2. **Try the cURL Examples** in our [cURL guide](./curl-examples.md)
3. **Build Your First Integration** using our [client examples](./client-examples.md)
4. **Set Up Testing** with our [testing guide](./testing-guide.md)
5. **Plan for Production** with our [versioning strategy](./versioning-strategy.md)

---

**Happy coding!** 🚀

If you have any questions or need assistance, don't hesitate to reach out to our support team.