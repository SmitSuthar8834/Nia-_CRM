# Lead Management and Participant Matching System

This module implements a comprehensive meeting participant matching and lead identification system for the NIA CRM Meeting Intelligence platform.

## Overview

The system automatically matches meeting participants with existing leads in the CRM using multi-tier matching algorithms, creates new leads for unmatched participants, and provides manual verification workflows for low-confidence matches.

## Key Features

### 1. Multi-Tier Matching Algorithms

The system uses a sophisticated matching approach with multiple tiers:

- **Tier 1: Exact Email Match** (100% confidence)
  - Direct email address matching with existing leads
  - Highest priority and confidence

- **Tier 2: Name + Company Match** (85%+ confidence)
  - Combines name similarity with company matching
  - Uses fuzzy string matching for variations

- **Tier 3: Domain Matching** (65%+ confidence)
  - Matches participants with leads from the same email domain
  - Excludes common email providers (gmail, yahoo, etc.)

- **Tier 4: Phone Number Match** (65%+ confidence)
  - Matches normalized phone numbers
  - Handles various phone number formats

- **Tier 5: Fuzzy Name Match** (40%+ confidence)
  - Uses string similarity algorithms within company context
  - Handles name variations and nicknames

### 2. LinkedIn Integration

Enhanced matching using LinkedIn profile data:

- **Profile Search**: Search LinkedIn for participant profiles
- **Data Enrichment**: Enhance participant data with LinkedIn information
- **Confidence Boosting**: Improve matching confidence with social profile data
- **Industry Validation**: Verify business relevance of profiles

### 3. Automatic Lead Creation

For unmatched participants:

- **Smart Data Extraction**: Parse names from email addresses when needed
- **Company Inference**: Derive company names from email domains
- **Default Values**: Set appropriate defaults for new leads
- **Meeting Source Tracking**: Track leads created from meetings

### 4. Manual Verification Workflows

For low-confidence matches:

- **Verification Requests**: Create structured review requests
- **Assignment Logic**: Assign to appropriate reviewers
- **Approval Workflows**: Support for match approval or new lead creation
- **Bulk Operations**: Batch approval for high-confidence matches
- **Analytics**: Track verification patterns and performance

### 5. Confidence Scoring

Sophisticated confidence calculation:

- **Multiple Factors**: Email, name, company, phone, domain matching
- **Weighted Scoring**: Different weights for different match types
- **Threshold-Based Actions**: Different actions based on confidence levels
- **Learning System**: Improve algorithms based on verification feedback

## API Endpoints

### Lead Management
```
GET    /api/leads/                     # List leads
POST   /api/leads/                     # Create lead
GET    /api/leads/{id}/                # Get lead details
PUT    /api/leads/{id}/                # Update lead
DELETE /api/leads/{id}/                # Delete lead
GET    /api/leads/{id}/meetings/       # Get lead meetings
GET    /api/leads/{id}/action_items/   # Get lead action items
```

### Participant Matching
```
POST   /api/matching/match_participants/           # Match participants
POST   /api/matching/analyze_meeting_participants/ # Analyze meeting participants
```

### Verification Management
```
GET    /api/verification/              # List verification requests
POST   /api/verification/{id}/approve_match/    # Approve specific match
POST   /api/verification/{id}/approve_new_lead/ # Approve new lead creation
POST   /api/verification/{id}/reject/           # Reject verification
GET    /api/verification/pending/              # Get pending requests
GET    /api/verification/overdue/              # Get overdue requests
```

## Usage Examples

### Basic Participant Matching

```python
from apps.leads.services import ParticipantMatchingService

participants = [
    {
        'email': 'john.doe@acme.com',
        'name': 'John Doe',
        'company': 'Acme Corp',
        'title': 'VP Sales'
    }
]

matching_service = ParticipantMatchingService()
results = matching_service.match_participants(participants)

for result in results:
    if result['matched_lead']:
        print(f"Matched: {result['participant']['email']} -> {result['matched_lead'].full_name}")
    elif result['should_create_new_lead']:
        print(f"Create new lead: {result['participant']['email']}")
```

### Meeting Participant Analysis

```python
from apps.leads.services import ParticipantAnalysisService

analysis_service = ParticipantAnalysisService()
results = analysis_service.analyze_meeting_participants(
    meeting_id='uuid-here',
    participants=participants,
    use_linkedin_enhancement=True
)

print(f"Processed {results['total_participants']} participants")
print(f"Matched: {results['matched_participants']}")
print(f"New leads: {results['new_leads_created']}")
print(f"Need verification: {results['manual_verification_required']}")
```

### Manual Verification

```python
from apps.leads.verification import ManualVerificationService

verification_service = ManualVerificationService()

# Get pending verifications
pending = verification_service.get_pending_verifications(user)

# Approve a match
verification_request = pending[0]
verification_request.approve_match(selected_lead, reviewer, "Good match")

# Bulk approve high confidence matches
approved_count = verification_service.bulk_approve_high_confidence_matches(0.8)
```

## Management Commands

### Match Participants Command

```bash
# Process all meetings from last 7 days
python manage.py match_participants

# Process specific meeting
python manage.py match_participants --meeting-id uuid-here

# Use LinkedIn enhancement
python manage.py match_participants --use-linkedin

# Dry run to see what would happen
python manage.py match_participants --dry-run

# Auto-approve high confidence matches
python manage.py match_participants --auto-approve-threshold 0.85
```

## Configuration

### Confidence Thresholds

```python
# In services.py
class ParticipantMatchingService:
    HIGH_CONFIDENCE_THRESHOLD = 0.85    # Auto-match
    MEDIUM_CONFIDENCE_THRESHOLD = 0.65  # Consider for matching
    LOW_CONFIDENCE_THRESHOLD = 0.40     # Minimum for consideration
```

### LinkedIn Integration

```python
# In settings.py
LINKEDIN_CLIENT_ID = 'your-client-id'
LINKEDIN_CLIENT_SECRET = 'your-client-secret'
LINKEDIN_ACCESS_TOKEN = 'your-access-token'
```

## Testing

Comprehensive test suite covering:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Mock Tests**: LinkedIn API integration testing
- **Performance Tests**: Large dataset handling

```bash
# Run all tests
python manage.py test apps.leads

# Run specific test class
python manage.py test apps.leads.tests.ParticipantMatchingServiceTest

# Run with coverage
coverage run --source='.' manage.py test apps.leads
coverage report
```

## Performance Considerations

### Database Optimization

- **Indexes**: Optimized indexes for email, company, and name searches
- **Query Optimization**: Efficient database queries for matching
- **Bulk Operations**: Batch processing for large datasets

### Caching

- **LinkedIn Profiles**: Cache profile search results
- **Matching Results**: Cache frequent matching patterns
- **Company Domains**: Cache domain-to-company mappings

### Rate Limiting

- **LinkedIn API**: Respect API rate limits
- **Bulk Processing**: Process in batches to avoid timeouts

## Security

### Data Protection

- **PII Handling**: Secure handling of personal information
- **Access Control**: Role-based access to verification workflows
- **Audit Logging**: Track all matching and verification activities

### API Security

- **Authentication**: Required for all endpoints
- **Authorization**: Role-based access control
- **Input Validation**: Comprehensive input validation and sanitization

## Monitoring and Analytics

### Metrics Tracked

- **Matching Accuracy**: Confidence scores and verification outcomes
- **Processing Time**: Performance metrics for matching algorithms
- **Verification Patterns**: Analysis of manual verification trends
- **LinkedIn Enhancement**: Usage and effectiveness of LinkedIn data

### Alerts

- **Overdue Verifications**: Notifications for pending reviews
- **Low Confidence Trends**: Alerts for declining matching accuracy
- **API Failures**: Monitoring for LinkedIn API issues

## Future Enhancements

### Planned Features

- **Machine Learning**: ML-based matching improvement
- **Additional Social Platforms**: Twitter, Facebook integration
- **Advanced Analytics**: Predictive matching confidence
- **Real-time Processing**: WebSocket-based real-time matching

### Optimization Opportunities

- **Fuzzy Matching**: Advanced fuzzy string matching algorithms
- **Company Normalization**: Better company name standardization
- **Phone Normalization**: International phone number handling
- **Name Parsing**: Improved name parsing for various cultures