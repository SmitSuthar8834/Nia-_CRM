# Intelligent Meeting Workflow System (NIA CRM)

A comprehensive AI-powered meeting intelligence platform that automates the entire lead-to-meeting lifecycle, integrating Creatio CRM, Google Calendar, AI assistance, and n8n workflow automation.

## Features

- **Calendar Integration**: Smart meeting detection across Google Calendar, Outlook, and Exchange
- **AI-Powered Debriefing**: Automated post-meeting conversations with context-aware questioning
- **Lead Synchronization**: Automatic sync from Creatio CRM every 15 minutes
- **Meeting-Lead Matching**: AI-powered matching with >85% accuracy using multi-tier algorithms
- **Real-time AI Assistant**: Live meeting support with question suggestions and note-taking
- **CRM Integration**: Automated post-meeting updates and follow-up task creation
- **Competitive Intelligence**: Systematic capture and analysis of competitor information
- **Follow-up Management**: Automated action item tracking and commitment management
- **Pipeline Intelligence**: Lead qualification and progression assessment
- **Analytics & Reporting**: Comprehensive performance and data quality metrics
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
- **Calendar APIs**: Google Calendar, Microsoft Graph

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd intelligent_meeting_workflow
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Update the `.env` file with your API keys and configuration

4. Start the services:
```bash
docker-compose up -d
```

5. Run migrations:
```bash
docker-compose exec web python manage.py migrate
```

6. Create a superuser:
```bash
docker-compose exec web python manage.py createsuperuser
```

7. Access the application:
- Web interface: http://localhost:8000
- Admin interface: http://localhost:8000/admin

### Manual Setup

1. Install Python 3.11+ and PostgreSQL

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (copy .env.example to .env)

5. Run migrations:
```bash
python manage.py migrate
```

6. Start the development server:
```bash
python manage.py runserver
```

## Configuration

### Required Environment Variables

- `GEMINI_API_KEY`: Google Gemini AI API key
- `CREATIO_API_URL`: Your Creatio CRM instance URL
- `CREATIO_CLIENT_ID`: Creatio OAuth client ID
- `CREATIO_CLIENT_SECRET`: Creatio OAuth client secret
- `GOOGLE_CALENDAR_CREDENTIALS_FILE`: Path to Google Calendar credentials JSON

### Optional Configuration

- `DEBUG`: Enable debug mode (default: True)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed CORS origins

## API Documentation

Once the server is running, API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

## Development

### Running Tests

```bash
python manage.py test
```

### Code Quality

```bash
# Format code
black .

# Check linting
flake8 .

# Type checking
mypy .
```

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is proprietary software for internal use.
