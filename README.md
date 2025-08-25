# NIA CRM Meeting Intelligence System

An AI-powered meeting intelligence platform that automates CRM workflows through intelligent calendar integration, automated debriefing, and smart data extraction.

## Features

- **Calendar Integration**: Smart meeting detection across Google Calendar, Outlook, and Exchange
- **AI-Powered Debriefing**: Automated post-meeting conversations with context-aware questioning
- **Participant Matching**: Multi-tier algorithms to match meeting attendees with CRM leads
- **Creatio CRM Sync**: Bidirectional synchronization with conflict resolution
- **Competitive Intelligence**: Systematic capture and analysis of competitor information
- **Follow-up Management**: Automated action item tracking and commitment management
- **Pipeline Intelligence**: Lead qualification and progression assessment
- **Analytics & Reporting**: Comprehensive performance and data quality metrics

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd meeting-intelligence
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

## Architecture

The system is built using:

- **Backend**: Django 4.2 with Django REST Framework
- **Database**: PostgreSQL with Redis for caching
- **Task Queue**: Celery with Redis broker
- **Real-time**: Django Channels with WebSocket support
- **AI Integration**: Google Gemini AI
- **Calendar APIs**: Google Calendar, Microsoft Graph

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

## API Documentation

Once the server is running, API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.