# Meeting Intelligence API

The Meeting Intelligence API provides comprehensive meeting management with AI-powered sales meeting detection, participant matching, and automated debriefing scheduling.

## Features

- **Meeting Management**: Full CRUD operations for meetings with calendar integration
- **Sales Meeting Detection**: AI-powered detection of sales meetings with confidence scoring
- **Participant Matching**: Multi-tier matching of meeting participants with CRM leads
- **Meeting Intelligence**: Classification of meeting types and relationship tracking
- **Debriefing Scheduling**: Automated scheduling of post-meeting debriefing sessions
- **Search & Filtering**: Advanced search and filtering capabilities
- **Statistics & Analytics**: Meeting performance metrics and insights

## Models

### Meeting
Core meeting model with calendar integration and intelligence features.

**Key Fields:**
- `calendar_event_id`: Unique identifier from calendar system
- `title`, `description`: Meeting details
- `start_time`, `end_time`: Meeting schedule
- `meeting_type`: Classification (discovery, demo, negotiation, etc.)
- `is_sales_meeting`: AI-determined sales meeting flag
- `confidence_score`: AI confidence in sales meeting detection (0-1)
- `debriefing_scheduled`, `debriefing_completed`: Debriefing status

### MeetingParticipant
Meeting participants with lead matching capabilities.

**Key Fields:**
- `email`, `name`, `company`: Participant information
- `matched_lead`: Linked CRM lead record
- `match_confidence`: Confidence in lead matching (0-1)
- `match_method`: Method used for matching (email, name_company, etc.)
- `is_external`: Flag for external participants

### MeetingNote
Meeting notes and outcomes.

**Key Fields:**
- `content`: Note content
- `note_type`: Type of note (general, outcome, action_item)
- `ai_generated`: Flag for AI-generated notes
- `ai_confidence`: Confidence in AI-generated content

## API Endpoints

### Meetings

```
GET    /api/v1/meetings/                    # List meetings
POST   /api/v1/meetings/                    # Create meeting
GET    /api/v1/meetings/{id}/               # Get meeting details
PUT    /api/v1/meetings/{id}/               # Update meeting
DELETE /api/v1/meetings/{id}/               # Delete meeting

# Custom Actions
POST   /api/v1/meetings/{id}/schedule_debriefing/  # Schedule debriefing
POST   /api/v1/meetings/{id}/detect_intelligence/  # Run AI detection
GET    /api/v1/meetings/upcoming/                  # Get upcoming meetings
GET    /api/v1/meetings/recent/                    # Get recent meetings
GET    /api/v1/meetings/sales_meetings/            # Get sales meetings only
GET    /api/v1/meetings/pending_debriefings/       # Get pending debriefings
GET    /api/v1/meetings/statistics/                # Get meeting statistics
```

### Participants

```
GET    /api/v1/meetings/participants/              # List participants
POST   /api/v1/meetings/participants/              # Create participant
GET    /api/v1/meetings/participants/{id}/         # Get participant
PUT    /api/v1/meetings/participants/{id}/         # Update participant
DELETE /api/v1/meetings/participants/{id}/         # Delete participant

# Custom Actions
POST   /api/v1/meetings/participants/{id}/verify_match/  # Verify lead match
GET    /api/v1/meetings/participants/unmatched/          # Get unmatched participants
GET    /api/v1/meetings/participants/verification_required/  # Get verification required
```

### Notes

```
GET    /api/v1/meetings/notes/                     # List notes
POST   /api/v1/meetings/notes/                     # Create note
GET    /api/v1/meetings/notes/{id}/                # Get note
PUT    /api/v1/meetings/notes/{id}/                # Update note
DELETE /api/v1/meetings/notes/{id}/                # Delete note

# Custom Actions
GET    /api/v1/meetings/notes/by_meeting/          # Get notes by meeting
```

## Query Parameters

### Meeting Filtering
- `search`: Search in title, description, participant names
- `meeting_type`: Filter by meeting type
- `status`: Filter by meeting status
- `is_sales_meeting`: Filter sales meetings (true/false)
- `start_date`, `end_date`: Date range filtering
- `organizer`: Filter by organizer user ID
- `has_debriefing`: Filter by debriefing status
- `participant_email`: Filter by participant email
- `company`: Filter by participant company

### Participant Filtering
- `meeting`: Filter by meeting ID
- `external_only`: Show only external participants
- `min_confidence`: Minimum match confidence threshold

### Note Filtering
- `meeting`: Filter by meeting ID
- `note_type`: Filter by note type
- `ai_generated`: Filter AI-generated notes

## Usage Examples

### Create a Meeting
```python
import requests

data = {
    "calendar_event_id": "event-123",
    "title": "Sales Discovery Call",
    "start_time": "2024-01-15T10:00:00Z",
    "end_time": "2024-01-15T11:00:00Z",
    "meeting_type": "discovery",
    "is_sales_meeting": True
}

response = requests.post("/api/v1/meetings/", json=data)
```

### Search Meetings
```python
# Search for meetings with "demo" in title
response = requests.get("/api/v1/meetings/?search=demo")

# Get sales meetings from last week
response = requests.get("/api/v1/meetings/?is_sales_meeting=true&start_date=2024-01-08T00:00:00Z")
```

### Schedule Debriefing
```python
meeting_id = "123e4567-e89b-12d3-a456-426614174000"
response = requests.post(f"/api/v1/meetings/{meeting_id}/schedule_debriefing/")
```

### Verify Participant Match
```python
participant_id = "123e4567-e89b-12d3-a456-426614174000"
lead_id = "456e7890-e89b-12d3-a456-426614174000"

data = {
    "verified": True,
    "lead_id": lead_id
}

response = requests.post(f"/api/v1/meetings/participants/{participant_id}/verify_match/", json=data)
```

## Management Commands

### Sync Meetings
```bash
# Sync meetings for all users
python manage.py sync_meetings

# Sync for specific user
python manage.py sync_meetings --user-id 1

# Only run detection on existing meetings
python manage.py sync_meetings --detect-only

# Sync with custom date range
python manage.py sync_meetings --days-back 14 --days-forward 60
```

## Integration

The Meeting Intelligence API integrates with:

- **Calendar Integration**: Automatic meeting detection from Google Calendar, Outlook
- **Lead Management**: Participant matching with CRM leads
- **AI Engine**: Sales meeting detection and classification
- **Debriefing System**: Automated debriefing scheduling
- **Analytics**: Meeting performance tracking

## Testing

Run the comprehensive test suite:

```bash
python manage.py test apps.meetings
```

The test suite includes:
- Model functionality tests
- API endpoint tests
- Permission and security tests
- Integration tests with other apps
- Performance and edge case tests

## Performance

The API is optimized for performance with:
- Database indexes on frequently queried fields
- Efficient querysets with select_related and prefetch_related
- Pagination for large result sets
- Caching for statistics and frequently accessed data