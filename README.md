# Intelligent Meeting Workflow System

A comprehensive meeting intelligence platform that automates the entire lead-to-meeting lifecycle, integrating Creatio CRM, Google Calendar, AI assistance, and n8n workflow automation.

## Features

- **Lead Synchronization**: Automatic sync from Creatio CRM every 15 minutes
- **Meeting-Lead Matching**: AI-powered matching with >85% accuracy
- **Real-time AI Assistant**: Live meeting support with question suggestions and note-taking
- **CRM Integration**: Automated post-meeting updates and follow-up task creation
- **WebSocket Support**: Real-time updates during meetings
- **RESTful API**: Comprehensive API for all operations

## Technology Stack

- **Backend**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL 14+ with Redis for caching
- **Real-time**: WebSocket with Django Channels
- **Task Queue**: Celery with Redis broker
- **AI Integration**: Google Gemini API
- **Workflow Engine**: n8n for automation
- **Authentication**: JWT with OAuth2 for external APIs

## Project Structure

```
intelligent_meeting_workflow/
├── intelligent_meeting_workflow/    # Main Django project
├── leads/                          # Lead management app
├── meetings/                       # Meeting management app
├── ai_assistant/                   # AI assistant app
├── requirements.txt                # Python dependencies
├── manage.py                       # Django management script
└── README.md                       # This file
```

## Setup Instructions

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Create PostgreSQL database
createdb intelligent_meeting_workflow

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### 3. Redis Setup

Make sure Redis is running on localhost:6379 or update the REDIS_URL in settings.

### 4. Environment Variables

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5. Run the Development Server

```bash
# Start Django development server
python manage.py runserver

# In another terminal, start Celery worker
celery -A intelligent_meeting_workflow worker -l info

# In another terminal, start Celery beat (for scheduled tasks)
celery -A intelligent_meeting_workflow beat -l info
```

## API Endpoints

### Authentication
- `POST /api/auth/token/` - Obtain JWT token
- `POST /api/auth/token/refresh/` - Refresh JWT token

### Leads
- `GET /api/leads/` - List leads
- `POST /api/leads/` - Create lead
- `GET /api/leads/{id}/` - Get lead details
- `PUT /api/leads/{id}/` - Update lead
- `POST /api/leads/sync/` - Sync leads from CRM (webhook)
- `PUT /api/leads/{id}/status/` - Update lead status

### Meetings
- `GET /api/meetings/` - List meetings
- `POST /api/meetings/` - Create meeting
- `GET /api/meetings/{id}/` - Get meeting details
- `POST /api/meetings/match-lead/` - Match meeting to lead (webhook)
- `POST /api/meetings/{id}/start/` - Start meeting session
- `POST /api/meetings/{id}/end/` - End meeting session

### AI Assistant
- `POST /api/ai/initialize/` - Initialize AI session
- `POST /api/ai/questions/` - Generate question suggestions
- `POST /api/ai/notes/` - Process meeting notes
- `POST /api/ai/summary/` - Generate meeting summary

## Testing

Run the test suite:

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test leads
python manage.py test meetings
python manage.py test ai_assistant

# Run with pytest (if installed)
pytest

# Run tests with coverage
python run_tests.py
```

## WebSocket Endpoints

- `ws://localhost:8000/ws/meetings/{meeting_id}/` - Real-time meeting updates

## Models

### Lead Model
- Stores lead information from Creatio CRM
- Includes validation for required fields
- Indexed for performance on email, company, status

### Meeting Model
- Represents calendar events matched to leads
- Tracks match confidence scores
- Supports various meeting statuses

### MeetingSession Model
- Manages AI-powered meeting sessions
- Stores notes, transcripts, and action items
- Tracks session duration and status

### ActionItem Model
- Extracted action items from meetings
- Assignee and due date tracking
- CRM task integration

## Development Guidelines

1. **Code Style**: Follow PEP 8 and Django best practices
2. **Testing**: Write tests for all new features
3. **Documentation**: Update README and docstrings
4. **Security**: Use proper authentication and validation
5. **Performance**: Optimize database queries and use caching

## Deployment

The application is designed to be deployed with:
- Docker containers for scalability
- PostgreSQL for production database
- Redis for caching and message broker
- nginx for reverse proxy
- SSL/TLS for security

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is proprietary software for internal use.