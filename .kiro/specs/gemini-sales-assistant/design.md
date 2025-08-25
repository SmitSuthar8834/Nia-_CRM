# Design Document: NIA CRM Meeting Intelligence System

## Overview

The NIA (AI Assistant) CRM Meeting Intelligence system is a specialized Django-based platform that automates meeting-related CRM workflows through intelligent calendar integration, automated debriefing, and smart data extraction. The system integrates Google's Gemini AI with Creatio CRM to provide bidirectional synchronization, intelligent meeting detection, automated post-meeting debriefing sessions, and structured data extraction from conversations. The architecture focuses on meeting intelligence, conversation parsing, and automated CRM updates while maintaining scalability and security.

### Key Design Principles
- **Meeting-Centric Architecture**: All workflows centered around meeting intelligence
- **AI-Powered Debriefing**: Gemini AI drives intelligent questioning and data extraction
- **Seamless CRM Integration**: Bidirectional sync with Creatio Freedom UI
- **Calendar Intelligence**: Smart meeting detection and participant matching
- **Context Continuity**: Multi-meeting relationship tracking and progression
- **Automated Workflows**: Proactive scheduling and conflict resolution
- **Security by Design**: End-to-end encryption and role-based access control

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Layer (React/Vue.js)                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │   Meeting   │ │  Debriefing │ │    Lead     │ │  Dashboard  ││
│  │  Calendar   │ │  Interface  │ │  Management │ │ & Analytics ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway (Django REST)                    │
├─────────────────────────────────────────────────────────────────┤
│  Authentication │ Rate Limiting │ Request Routing │ Validation  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Services Layer                        │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │   Gemini    │ │   Meeting   │ │ Debriefing  │ │    Lead     │ │
│ │ AI Engine   │ │ Intelligence│ │   Service   │ │  Matching   │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │  Calendar   │ │ Conversation│ │ CRM Sync    │ │ Scheduling  │ │
│ │Integration  │ │   Parser    │ │  Service    │ │  Service    │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Integration Layer                            │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │   Creatio   │ │   Google    │ │  Calendar   │ │   Google    │ │
│ │ CRM Adapter │ │   Gemini    │ │   Systems   │ │  Calendar   │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │  Outlook    │ │  Exchange   │ │   Email     │ │ Notification│ │
│ │  Calendar   │ │  Calendar   │ │ Integration │ │  Services   │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ PostgreSQL  │ │    Redis    │ │  Elasticsearch│ │   Object    │ │
│ │  Primary    │ │   Cache     │ │  Search &    │ │  Storage    │ │
│ │  Database   │ │             │ │  Analytics   │ │   (S3/GCS)  │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Microservices Architecture

The system is designed as a collection of focused microservices:

1. **Meeting Intelligence Service**: Calendar integration and meeting detection
2. **Debriefing Service**: AI-powered post-meeting conversations
3. **Conversation Parser Service**: Natural language processing and data extraction
4. **Lead Matching Service**: Multi-tier participant identification
5. **CRM Sync Service**: Bidirectional Creatio integration
6. **Scheduling Service**: Automated meeting coordination
7. **Analytics Service**: Performance metrics and insights
8. **Notification Service**: Real-time alerts and reminders
9. **User Management Service**: Authentication and authorization

## Components and Interfaces

### Core Components

#### 1. Meeting Intelligence Engine
```python
class MeetingIntelligenceEngine:
    """Core meeting detection and analysis engine"""
    
    def detect_sales_meetings(self, calendar_events: list) -> list:
        """Identify potential sales meetings from calendar events"""
        
    def classify_meeting_type(self, meeting: dict) -> str:
        """Classify meeting type (discovery, demo, negotiation, etc.)"""
        
    def match_participants(self, attendees: list) -> list:
        """Match meeting participants with CRM leads"""
        
    def analyze_meeting_patterns(self, meetings: list) -> dict:
        """Analyze meeting patterns and relationship progression"""
        
    def schedule_debriefing(self, meeting: dict) -> str:
        """Automatically schedule post-meeting debriefing"""
```

#### 2. AI-Powered Debriefing System
```python
class DebriefingSystem:
    """Handles intelligent debriefing conversations"""
    
    def generate_questions(self, meeting_context: dict) -> list:
        """Generate context-aware debriefing questions"""
        
    def process_response(self, question: str, response: str) -> dict:
        """Process user response and generate follow-up questions"""
        
    def extract_structured_data(self, conversation: str) -> dict:
        """Extract structured data from debriefing conversation"""
        
    def validate_extraction(self, data: dict) -> dict:
        """Validate extracted data and flag uncertainties"""
```

#### 3. Conversation Parser
```python
class ConversationParser:
    """Natural language processing for data extraction"""
    
    def parse_contact_info(self, text: str) -> dict:
        """Extract contact information from conversation"""
        
    def parse_deal_info(self, text: str) -> dict:
        """Extract deal-related information"""
        
    def parse_competitive_intel(self, text: str) -> dict:
        """Extract competitive intelligence"""
        
    def parse_action_items(self, text: str) -> list:
        """Extract action items and commitments"""
        
    def calculate_confidence(self, extraction: dict) -> float:
        """Calculate confidence score for extracted data"""
```

#### 4. Creatio CRM Adapter
```python
class CreatioAdapter:
    """Handles all Creatio CRM API interactions"""
    
    def sync_leads_bidirectional(self) -> dict:
        """Bidirectional synchronization of lead data"""
        
    def update_lead_from_meeting(self, lead_id: str, meeting_data: dict) -> bool:
        """Update lead record with meeting insights"""
        
    def create_activities(self, activities: list) -> bool:
        """Create meeting activities in Creatio"""
        
    def handle_sync_conflicts(self, conflicts: list) -> dict:
        """Resolve synchronization conflicts"""
```

#### 5. Calendar Integration Hub
```python
class CalendarIntegrationHub:
    """Unified interface for multiple calendar systems"""
    
    def connect_google_calendar(self, credentials: dict) -> bool:
        """Connect to Google Calendar"""
        
    def connect_outlook_calendar(self, credentials: dict) -> bool:
        """Connect to Outlook/Exchange calendar"""
        
    def detect_meeting_changes(self) -> list:
        """Detect changes in calendar events"""
        
    def resolve_scheduling_conflicts(self, conflicts: list) -> dict:
        """Automatically resolve scheduling conflicts"""
```

### API Interfaces

#### REST API Endpoints

**Meeting Intelligence**
```
GET    /api/v1/meetings/                    # List meetings with intelligence
POST   /api/v1/meetings/detect/            # Trigger meeting detection
GET    /api/v1/meetings/{id}/participants/ # Get matched participants
POST   /api/v1/meetings/{id}/debriefing/   # Schedule debriefing
```

**Debriefing Management**
```
POST   /api/v1/debriefings/                # Start debriefing session
GET    /api/v1/debriefings/{id}/           # Get debriefing status
POST   /api/v1/debriefings/{id}/respond/   # Submit response
GET    /api/v1/debriefings/{id}/extract/   # Get extracted data
```

**Lead Management**
```
GET    /api/v1/leads/                      # List leads
POST   /api/v1/leads/match/               # Match meeting participants
PUT    /api/v1/leads/{id}/                # Update lead from meeting data
GET    /api/v1/leads/{id}/meetings/       # Get lead meeting history
```

**CRM Synchronization**
```
POST   /api/v1/crm/sync/                  # Trigger CRM sync
GET    /api/v1/crm/conflicts/             # Get sync conflicts
POST   /api/v1/crm/resolve/               # Resolve conflicts
GET    /api/v1/crm/status/                # Get sync status
```

#### WebSocket Interfaces

Real-time communication for:
- Live debriefing sessions
- Real-time notifications
- Calendar sync status updates
- Meeting conflict alerts

```python
class WebSocketHandler:
    async def handle_debriefing_session(self, websocket, path):
        """Handle real-time debriefing conversation"""
        
    async def handle_notifications(self, websocket, path):
        """Send real-time notifications"""
        
    async def handle_sync_updates(self, websocket, path):
        """Real-time CRM sync status updates"""
```

## Data Models

### Core Data Models

#### Meeting Model
```python
class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    calendar_event_id = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    meeting_type = models.CharField(max_length=50, choices=MEETING_TYPE_CHOICES)
    is_sales_meeting = models.BooleanField(default=False)
    confidence_score = models.FloatField(default=0.0)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    debriefing_scheduled = models.BooleanField(default=False)
    debriefing_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'meetings'
        indexes = [
            models.Index(fields=['start_time', 'organizer']),
            models.Index(fields=['is_sales_meeting', 'meeting_type']),
        ]
```

#### Meeting Participant Model
```python
class MeetingParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    email = models.EmailField()
    name = models.CharField(max_length=200, null=True)
    company = models.CharField(max_length=200, null=True)
    matched_lead = models.ForeignKey('Lead', on_delete=models.SET_NULL, null=True)
    match_confidence = models.FloatField(default=0.0)
    is_external = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'meeting_participants'
        unique_together = ['meeting', 'email']
```

#### Debriefing Session Model
```python
class DebriefingSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, choices=DEBRIEFING_STATUS_CHOICES)
    conversation_data = models.JSONField(default=dict)
    extracted_data = models.JSONField(default=dict)
    confidence_scores = models.JSONField(default=dict)
    user_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'debriefing_sessions'
```

#### Lead Model (Enhanced for Meeting Intelligence)
```python
class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    creatio_id = models.CharField(max_length=100, unique=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, null=True)
    company = models.CharField(max_length=200)
    title = models.CharField(max_length=100, null=True)
    source = models.CharField(max_length=50, default='meeting')
    status = models.CharField(max_length=20, choices=LEAD_STATUS_CHOICES)
    qualification_score = models.IntegerField(default=0)
    last_meeting_date = models.DateTimeField(null=True)
    meeting_count = models.IntegerField(default=0)
    relationship_stage = models.CharField(max_length=50, null=True)
    decision_authority = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'leads'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company', 'last_name']),
            models.Index(fields=['last_meeting_date']),
        ]
```

#### Competitive Intelligence Model
```python
class CompetitiveIntelligence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    competitor_name = models.CharField(max_length=200)
    competitive_context = models.TextField()
    strengths_mentioned = models.JSONField(default=list)
    weaknesses_mentioned = models.JSONField(default=list)
    pricing_intelligence = models.JSONField(default=dict)
    relationship_status = models.CharField(max_length=50, null=True)
    threat_level = models.CharField(max_length=20, choices=THREAT_LEVEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'competitive_intelligence'
```

#### Action Item Model
```python
class ActionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    debriefing_session = models.ForeignKey(DebriefingSession, on_delete=models.CASCADE)
    description = models.TextField()
    owner = models.CharField(max_length=200)  # Can be internal or external
    due_date = models.DateField(null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    status = models.CharField(max_length=20, choices=ACTION_STATUS_CHOICES)
    is_commitment = models.BooleanField(default=False)  # True if it's a commitment made
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    
    class Meta:
        db_table = 'action_items'
```

## Data Flow Architecture

### Meeting Intelligence Workflow

```
1. Calendar Event Detection
   ↓
2. Sales Meeting Classification
   ↓
3. Participant Matching with CRM
   ↓
4. Automatic Debriefing Scheduling
   ↓
5. AI-Powered Debriefing Conversation
   ↓
6. Structured Data Extraction
   ↓
7. CRM Update with User Approval
   ↓
8. Follow-up Action Creation
```

### Data Synchronization Flow

```
Calendar Systems → Meeting Detection → Participant Analysis
                                           ↓
Lead Matching ← CRM Data ← Bidirectional Sync → Creatio CRM
     ↓                                              ↑
Debriefing Session → Data Extraction → User Review → CRM Updates
     ↓                                              ↑
Action Items → Task Creation → Follow-up Management
```

## Security Architecture

### Authentication and Authorization

#### Role-Based Access Control
```python
class MeetingIntelligenceRoles:
    """Role definitions for meeting intelligence system"""
    
    ROLES = {
        'admin': [
            'manage_all_meetings', 'configure_integrations', 
            'view_all_analytics', 'manage_users'
        ],
        'sales_manager': [
            'view_team_meetings', 'manage_team_debriefings',
            'view_competitive_intel', 'approve_crm_updates'
        ],
        'sales_rep': [
            'view_own_meetings', 'conduct_debriefings',
            'update_own_leads', 'schedule_meetings'
        ],
        'viewer': [
            'view_dashboard', 'view_reports'
        ]
    }
```

### Data Protection

#### Encryption and Privacy
- **Data at Rest**: AES-256 encryption for sensitive meeting data
- **Data in Transit**: TLS 1.3 for all API communications
- **PII Protection**: Automatic detection and encryption of personal information
- **Meeting Confidentiality**: Role-based access to meeting content

## Performance and Scalability

### Performance Optimization

#### Caching Strategy
```python
class MeetingIntelligenceCache:
    """Caching system for meeting intelligence"""
    
    def cache_meeting_analysis(self, meeting_id: str, analysis: dict):
        """Cache meeting analysis results"""
        
    def cache_participant_matches(self, participants: list, matches: dict):
        """Cache participant matching results"""
        
    def cache_ai_responses(self, prompt_hash: str, response: str):
        """Cache AI responses to reduce API calls"""
```

#### Database Optimization
- **Indexing**: Optimized indexes for meeting queries and participant matching
- **Partitioning**: Time-based partitioning for meeting and debriefing data
- **Connection Pooling**: Efficient database connection management

### Scalability Architecture

#### Horizontal Scaling
- **Microservices**: Independent scaling of meeting intelligence components
- **Load Balancing**: Distribute meeting processing across instances
- **Queue Management**: Asynchronous processing of debriefing sessions

## Deployment Architecture

### Infrastructure Components

#### Application Tier
```yaml
# docker-compose.yml for Meeting Intelligence
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/meeting_intelligence
      - REDIS_URL=redis://redis:6379
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - CREATIO_API_URL=${CREATIO_API_URL}
    depends_on:
      - db
      - redis
      
  meeting_processor:
    build: .
    command: celery -A meeting_intelligence worker -Q meetings
    depends_on:
      - db
      - redis
      
  debriefing_processor:
    build: .
    command: celery -A meeting_intelligence worker -Q debriefings
    depends_on:
      - db
      - redis
      
  scheduler:
    build: .
    command: celery -A meeting_intelligence beat
    depends_on:
      - db
      - redis
```

This comprehensive design document provides the foundation for implementing the NIA CRM Meeting Intelligence system with all the features specified in the updated requirements. The architecture supports meeting-centric workflows, AI-powered debriefing, and seamless CRM integration while maintaining scalability and security.