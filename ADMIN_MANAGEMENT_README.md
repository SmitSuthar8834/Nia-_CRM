# NIA Meeting Intelligence - Admin & Management Commands

This document provides comprehensive information about the Django admin interfaces and management commands available in the NIA Meeting Intelligence system.

## Admin Interfaces

### Overview
All Django apps in the system have comprehensive admin interfaces with the following features:
- Custom list displays with relevant fields
- Advanced filtering and search capabilities
- Bulk actions for common operations
- Read-only fields for system-generated data
- Color-coded status indicators
- Inline editing where appropriate

### Available Admin Interfaces

#### 1. Accounts Admin (`/admin/accounts/`)
- **UserProfile**: User profile management with role-based access
- **TwoFactorAuth**: 2FA configuration and status
- **CalendarIntegration**: Calendar connection management
- **UserActivity**: Activity logging (read-only)
- **LoginAttempt**: Login attempt tracking (read-only)

#### 2. Meetings Admin (`/admin/meetings/`)
- **Meeting**: Meeting management with intelligence features
- **MeetingParticipant**: Participant matching and verification
- **MeetingNote**: Meeting notes and AI-generated content

#### 3. Debriefings Admin (`/admin/debriefings/`)
- **DebriefingSession**: Session management and progress tracking
- **DebriefingQuestion**: Question flow and responses
- **DebriefingInsight**: AI-generated insights and validation
- **DebriefingTemplate**: Template management for different meeting types

#### 4. Leads Admin (`/admin/leads/`)
- **Lead**: Lead management with meeting history
- **LeadNote**: Lead notes and relationship tracking
- **CompetitiveIntelligence**: Competitor information capture
- **ActionItem**: Follow-up task management

#### 5. CRM Sync Admin (`/admin/crm_sync/`)
- **CreatioSync**: Bidirectional sync status and management
- **SyncConflict**: Conflict resolution workflows
- **SyncLog**: Detailed sync operation logging
- **CreatioConfiguration**: CRM integration settings

#### 6. Calendar Integration Admin (`/admin/calendar_integration/`)
- **CalendarEvent**: Calendar event management and meeting detection
- **CalendarSyncStatus**: Sync status monitoring per user/provider

#### 7. AI Engine Admin (`/admin/ai_engine/`)
- **AIPromptTemplate**: Prompt template management and performance
- **AIInteraction**: AI interaction logging and monitoring
- **AICache**: Response caching and optimization
- **AIFeedback**: User feedback on AI responses

#### 8. Analytics Admin (`/admin/analytics/`)
- **PerformanceMetric**: System performance tracking
- **UserEngagementMetric**: User engagement analytics
- **DataQualityMetric**: Data quality monitoring
- **SystemHealthMetric**: System health monitoring
- **Report**: Automated report generation

### Admin Dashboard

#### System Dashboard (`/admin/dashboard/`)
Comprehensive system overview with:
- Real-time system health status
- Performance metrics summary
- User engagement statistics
- Data quality indicators
- Recent system alerts

#### Health Monitor (`/admin/health/`)
Detailed system health monitoring:
- Component-by-component health status
- Response time monitoring
- Historical health trends
- Auto-refresh capabilities

#### Performance Metrics (`/admin/performance/`)
Performance analytics dashboard:
- Metric trends and comparisons
- Top performing users/departments
- Performance target tracking

## Management Commands

### System Maintenance Commands

#### User Management
```bash
# Clean up inactive users
python manage.py cleanup_inactive_users --days 365 --dry-run

# Reset failed login attempts
python manage.py reset_failed_logins --hours 24 --ip 192.168.1.100
```

#### Data Cleanup
```bash
# Clean up old meetings (preserve sales meetings and debriefings)
python manage.py cleanup_old_meetings --days 365 --keep-sales-meetings --keep-with-debriefings

# Clean up old debriefing sessions
python manage.py cleanup_old_sessions --days 180 --keep-completed

# Clean up CRM sync logs
python manage.py cleanup_sync_logs --days 90 --keep-errors
```

#### AI Engine Maintenance
```bash
# Optimize AI cache
python manage.py optimize_ai_cache --min-hits 2 --max-age-days 30

# AI usage report
python manage.py ai_usage_report --days 30

# Test Gemini connection
python manage.py test_gemini_connection

# AI cache maintenance
python manage.py ai_cache_maintenance
```

#### Data Migration and Validation
```bash
# Fix participant matching issues
python manage.py migrate_meeting_data --operation fix_participant_matching

# Update meeting type classifications
python manage.py migrate_meeting_data --operation update_meeting_types

# Fix timezone issues
python manage.py migrate_meeting_data --operation fix_timezone_issues

# Consolidate duplicate meetings
python manage.py migrate_meeting_data --operation consolidate_duplicates

# Validate data integrity
python manage.py migrate_meeting_data --operation validate_data
```

#### System Health and Monitoring
```bash
# Comprehensive system health check
python manage.py system_health_check --component all --record-metrics

# Check specific components
python manage.py system_health_check --component database
python manage.py system_health_check --component ai --alert-threshold 3.0
```

#### Analytics and Reporting
```bash
# Collect analytics data
python manage.py collect_analytics

# Generate system reports
python manage.py generate_reports --report-type system_health
```

#### Calendar and CRM Sync
```bash
# Sync calendars
python manage.py sync_calendars --provider google

# Sync with Creatio CRM
python manage.py sync_creatio --full-sync

# Match meeting participants
python manage.py match_participants --confidence-threshold 0.8
```

#### Debriefing Management
```bash
# Schedule pending debriefings
python manage.py schedule_debriefings

# Process overdue debriefings
python manage.py process_overdue_debriefings --days 7
```

### System Management Script

#### Comprehensive System Manager (`python manage_system.py`)

The system includes a comprehensive management script that combines multiple operations:

```bash
# System health check
python manage_system.py health --alert-threshold 5.0

# System cleanup (with dry-run)
python manage_system.py cleanup --days 90 --dry-run

# System maintenance
python manage_system.py maintenance

# Database backup
python manage_system.py backup

# Run migrations
python manage_system.py migrate

# System status overview
python manage_system.py status
```

### Command Options

#### Common Options
- `--dry-run`: Show what would be done without executing
- `--force`: Skip confirmation prompts
- `--batch-size N`: Process records in batches of N
- `--days N`: Specify time period in days
- `--hours N`: Specify time period in hours

#### Logging and Output
All management commands include:
- Detailed progress reporting
- Error handling and logging
- Batch processing for large datasets
- Confirmation prompts for destructive operations
- Comprehensive statistics and summaries

### Scheduling Commands

#### Cron Job Examples
```bash
# Daily system health check (6 AM)
0 6 * * * cd /path/to/project && python manage.py system_health_check --record-metrics

# Weekly cleanup (Sunday 2 AM)
0 2 * * 0 cd /path/to/project && python manage.py cleanup_old_meetings --days 365 --keep-sales-meetings

# Monthly AI cache optimization (1st of month, 3 AM)
0 3 1 * * cd /path/to/project && python manage.py optimize_ai_cache --min-hits 2

# Daily CRM sync (every 4 hours)
0 */4 * * * cd /path/to/project && python manage.py sync_creatio
```

### Monitoring and Alerts

#### Health Check Integration
The system health check command can be integrated with monitoring systems:
- Exit codes indicate system status
- JSON output available for parsing
- Metrics recorded to database for trending
- Alert thresholds configurable

#### Performance Monitoring
- Response time tracking for all components
- Database query performance monitoring
- AI engine response time tracking
- CRM sync performance metrics

### Security Considerations

#### Admin Access
- Role-based access control for admin interfaces
- Audit logging for all admin actions
- Two-factor authentication support
- IP-based access restrictions available

#### Command Security
- Confirmation prompts for destructive operations
- Dry-run mode for testing
- Comprehensive logging of all operations
- Database transaction safety

### Troubleshooting

#### Common Issues
1. **Permission Errors**: Ensure proper database permissions
2. **Memory Issues**: Use batch processing for large datasets
3. **Timeout Issues**: Adjust command timeouts for large operations
4. **Lock Conflicts**: Avoid running multiple cleanup commands simultaneously

#### Debug Mode
Enable debug logging by setting:
```bash
export DJANGO_LOG_LEVEL=DEBUG
```

### Best Practices

#### Regular Maintenance Schedule
1. **Daily**: Health checks, failed login resets
2. **Weekly**: Data cleanup, cache optimization
3. **Monthly**: Comprehensive system maintenance, data migration validation
4. **Quarterly**: Full system backup, performance review

#### Monitoring Recommendations
1. Set up automated health checks
2. Monitor disk space before cleanup operations
3. Review admin audit logs regularly
4. Track performance metrics trends

This comprehensive admin and management system ensures the NIA Meeting Intelligence platform remains performant, secure, and well-maintained.