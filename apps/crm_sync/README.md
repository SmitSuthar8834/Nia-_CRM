# Creatio CRM Integration

This app provides comprehensive bidirectional synchronization between the NIA Meeting Intelligence system and Creatio CRM.

## Features

### Core Functionality
- **OAuth 2.0 Authentication**: Secure authentication with Creatio using client credentials flow
- **Bidirectional Synchronization**: Sync leads, contacts, and activities between systems
- **Conflict Resolution**: Intelligent conflict detection and resolution workflows
- **Retry Logic**: Exponential backoff retry mechanism for failed operations
- **Real-time Updates**: Immediate sync of meeting-derived data to CRM
- **Activity Creation**: Automatic creation of meeting activities in Creatio

### Data Synchronization
- **Lead Management**: Full CRUD operations for leads with field mapping
- **Meeting Activities**: Convert meetings to Creatio activities
- **Contact Information**: Sync participant data and contact details
- **Competitive Intelligence**: Track competitor mentions and analysis
- **Action Items**: Create tasks and follow-ups in CRM

### Monitoring & Management
- **Sync Status Tracking**: Comprehensive logging and status monitoring
- **Conflict Management**: User-friendly conflict resolution interface
- **Performance Metrics**: Sync success rates and timing analytics
- **Admin Interface**: Django admin integration for management
- **Management Commands**: CLI tools for sync operations

## Configuration

### Environment Variables
```bash
# Creatio CRM Configuration
CREATIO_API_URL=https://your-creatio-instance.com
CREATIO_CLIENT_ID=your-client-id
CREATIO_CLIENT_SECRET=your-client-secret
```

### Field Mapping Configuration
Field mappings can be configured through the `CreatioConfiguration` model:

```python
# Example lead field mapping
{
    "first_name": "Name",
    "last_name": "Surname", 
    "email": "Email",
    "phone": "MobilePhone",
    "company": "AccountName",
    "title": "JobTitle",
    "status": "QualifyStatus"
}
```

## API Endpoints

### Synchronization
- `POST /api/v1/crm/sync/sync_all/` - Trigger bidirectional sync
- `POST /api/v1/crm/sync/sync-lead/` - Sync specific lead
- `GET /api/v1/crm/sync/status/` - Get sync status overview

### Conflict Resolution
- `GET /api/v1/crm/conflicts/` - List pending conflicts
- `POST /api/v1/crm/sync/resolve-conflict/` - Resolve specific conflict

### Activity Management
- `POST /api/v1/crm/sync/create-activity/` - Create meeting activity
- `POST /api/v1/crm/sync/update-lead-from-meeting/` - Update lead with meeting data

## Usage Examples

### Programmatic Sync
```python
from apps.crm_sync.services import CRMSyncService

service = CRMSyncService()

# Sync all leads
result = service.sync_all_leads()

# Sync specific lead
result = service.sync_single_lead(lead_id, direction='to_creatio')

# Update lead with meeting data
meeting_data = {
    'qualification_insights': {
        'budget_discussed': True,
        'decision_maker_identified': True
    },
    'meeting_type': 'demo',
    'estimated_budget': 50000
}
result = service.update_lead_from_meeting_data(lead_id, meeting_data)
```

### Management Commands
```bash
# Sync all leads
python manage.py sync_creatio sync-all

# Sync specific lead
python manage.py sync_creatio sync-lead --lead-id=<uuid>

# Check sync status
python manage.py sync_creatio status

# View conflicts
python manage.py sync_creatio conflicts

# Retry failed syncs
python manage.py sync_creatio retry-failed

# Test connection
python manage.py sync_creatio test-connection

# Dry run (preview changes)
python manage.py sync_creatio sync-all --dry-run
```

### Async Processing
```python
from apps.crm_sync.services import sync_all_leads_task, sync_lead_to_creatio

# Trigger async sync
task = sync_all_leads_task.delay(force=False)
print(f"Task ID: {task.id}")

# Sync single lead async
task = sync_lead_to_creatio.delay(lead_id)
```

## Models

### CreatioSync
Tracks synchronization status for each entity:
- Entity type and IDs (local and Creatio)
- Sync status and direction
- Error handling and retry logic
- Data hashes for change detection

### SyncConflict
Manages data conflicts during synchronization:
- Conflict type and affected field
- Local and Creatio values
- Resolution status and user decisions
- Audit trail for conflict resolution

### SyncLog
Comprehensive logging for all sync operations:
- Operation type and log level
- Request/response data
- Execution timing
- User context and entity information

### CreatioConfiguration
Flexible configuration management:
- Field mappings between systems
- API endpoint configurations
- Business rules and sync schedules
- Feature flags and settings

## Error Handling

### Retry Logic
- Exponential backoff for failed operations
- Configurable retry limits per sync record
- Automatic retry scheduling for transient failures

### Conflict Resolution
- Automatic conflict detection during sync
- User approval workflows for data conflicts
- Multiple resolution strategies (local wins, Creatio wins, manual merge)

### Monitoring
- Real-time sync status tracking
- Performance metrics and analytics
- Alert system for critical failures

## Security

### Authentication
- OAuth 2.0 client credentials flow
- Secure token caching with expiration
- Automatic token refresh handling

### Data Protection
- Field-level access controls
- Audit logging for all operations
- Secure credential management

### API Security
- Rate limiting and request throttling
- Input validation and sanitization
- Error message sanitization

## Performance

### Optimization Features
- Intelligent change detection using data hashes
- Batch processing for bulk operations
- Connection pooling and request optimization
- Caching for frequently accessed data

### Scalability
- Async processing with Celery
- Database query optimization
- Configurable batch sizes
- Load balancing support

## Testing

### Test Coverage
- Unit tests for all adapters and services
- Integration tests with mock Creatio API
- API endpoint testing
- Error scenario testing

### Running Tests
```bash
# Run all CRM sync tests
python manage.py test apps.crm_sync

# Run specific test class
python manage.py test apps.crm_sync.tests.CreatioAdapterTestCase

# Run with coverage
coverage run --source='.' manage.py test apps.crm_sync
coverage report
```

## Troubleshooting

### Common Issues

#### Authentication Failures
- Verify Creatio credentials in environment variables
- Check Creatio instance URL and accessibility
- Ensure OAuth 2.0 is properly configured in Creatio

#### Sync Failures
- Check sync logs for detailed error messages
- Verify field mappings are correct
- Ensure required fields are populated

#### Performance Issues
- Monitor sync batch sizes
- Check database query performance
- Review Celery worker configuration

### Debug Mode
Enable detailed logging by setting:
```python
LOGGING = {
    'loggers': {
        'apps.crm_sync': {
            'level': 'DEBUG',
        }
    }
}
```

## Contributing

### Development Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables
3. Run migrations: `python manage.py migrate`
4. Create test data: `python manage.py loaddata crm_sync_fixtures.json`

### Code Style
- Follow PEP 8 guidelines
- Use type hints for all functions
- Add docstrings for all classes and methods
- Write comprehensive tests for new features

### Pull Request Process
1. Create feature branch from main
2. Implement changes with tests
3. Update documentation
4. Submit pull request with detailed description