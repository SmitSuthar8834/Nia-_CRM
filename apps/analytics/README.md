# Analytics and Reporting System

The Analytics app provides comprehensive analytics, reporting, and performance monitoring for the Meeting Intelligence system. It tracks various metrics, generates automated reports, and provides real-time insights into system performance and user engagement.

## Features

### 📊 Performance Metrics
- **Debriefing Completion Rates**: Track meeting debriefing completion by user and time period
- **Data Extraction Accuracy**: Monitor AI-powered data extraction confidence and accuracy
- **Meeting Detection Accuracy**: Measure calendar meeting detection and classification performance
- **Participant Matching Accuracy**: Track lead matching and participant identification success
- **CRM Sync Success Rates**: Monitor bidirectional CRM synchronization performance
- **User Engagement Metrics**: Track user interactions and system usage patterns

### 📈 Real-Time Analytics
- **Live Dashboard**: Real-time metrics and system status
- **User Activity Tracking**: Track user engagement events as they happen
- **System Health Monitoring**: Monitor API response times, database performance, and resource usage
- **Alert System**: Automated alerts for critical system issues and performance degradation

### 📋 Automated Reporting
- **Daily Summary Reports**: Automated daily performance summaries
- **Weekly Performance Reports**: Comprehensive weekly analytics
- **Monthly Analytics Reports**: Detailed monthly insights with trends
- **User Activity Reports**: Individual user performance and engagement reports
- **Custom Report Generation**: On-demand report generation with flexible parameters

### 🚀 Advanced Features
- **Intelligent Caching**: Multi-tier caching system for optimal performance
- **Data Export**: Export analytics data in JSON and CSV formats
- **Batch Processing**: Efficient processing of large datasets
- **Anomaly Detection**: Automatic detection of unusual patterns in metrics
- **Trend Analysis**: Historical trend analysis and forecasting

## API Endpoints

### Dashboard Analytics
```
GET /api/v1/analytics/dashboard/
```
Get comprehensive dashboard analytics with configurable time periods.

**Query Parameters:**
- `days`: Number of days to include (default: 7)

### Performance Metrics
```
GET /api/v1/analytics/metrics/performance/
```
List performance metrics with filtering and pagination.

**Query Parameters:**
- `metric_type`: Filter by metric type
- `start_date`: Filter by start date
- `end_date`: Filter by end date

### User Engagement
```
GET /api/v1/analytics/metrics/engagement/
POST /api/v1/analytics/track-engagement/
```
Track and retrieve user engagement metrics.

### System Health
```
GET /api/v1/analytics/metrics/system-health/
GET /api/v1/analytics/system-health/status/
```
Monitor system health and get current status.

### Reports
```
GET /api/v1/analytics/reports/
GET /api/v1/analytics/reports/{id}/
POST /api/v1/analytics/reports/generate/
```
Generate and retrieve analytics reports.

### Data Export
```
GET /api/v1/analytics/export/
```
Export analytics data in various formats.

**Query Parameters:**
- `format`: Export format (json, csv)
- `metric_type`: Type of metrics to export
- `start_date`: Start date for export
- `end_date`: End date for export

## Models

### PerformanceMetric
Stores aggregated performance metrics with time-based aggregation.

**Key Fields:**
- `metric_type`: Type of metric (debriefing_completion, data_extraction_accuracy, etc.)
- `aggregation_period`: Time period (hourly, daily, weekly, monthly)
- `value`: Metric value
- `period_start/end`: Time period boundaries
- `user`: Associated user (for user-specific metrics)
- `metadata`: Additional metric data

### UserEngagementMetric
Tracks individual user engagement events.

**Key Fields:**
- `user`: User who performed the action
- `engagement_type`: Type of engagement (login, meeting_view, debriefing_start, etc.)
- `session_id`: Session identifier
- `duration_seconds`: Duration of engagement
- `entity_type/id`: Related entity information

### DataQualityMetric
Monitors data quality and extraction accuracy.

**Key Fields:**
- `quality_type`: Type of quality metric
- `entity_type`: Type of entity being measured
- `score`: Quality score (0-1)
- `confidence`: Confidence in the score
- `field_name`: Specific field being measured

### SystemHealthMetric
Tracks system health and performance indicators.

**Key Fields:**
- `health_type`: Type of health metric
- `component`: System component being monitored
- `value`: Metric value
- `status`: Health status (healthy, warning, critical, down)
- `warning_threshold/critical_threshold`: Alert thresholds

### Report
Stores generated analytics reports.

**Key Fields:**
- `report_type`: Type of report
- `title`: Report title
- `period_start/end`: Report time period
- `report_data`: Generated report data (JSON)
- `status`: Generation status
- `created_by`: User who requested the report

## Services

### AnalyticsService
Core service for calculating analytics metrics.

**Key Methods:**
- `calculate_debriefing_completion_rate()`
- `calculate_data_extraction_accuracy()`
- `calculate_meeting_detection_accuracy()`
- `calculate_participant_matching_accuracy()`
- `calculate_crm_sync_success_rate()`
- `calculate_user_engagement_metrics()`
- `get_competitive_intelligence_insights()`

### ReportingService
Service for generating automated reports.

**Key Methods:**
- `generate_daily_summary_report()`
- `generate_weekly_performance_report()`
- `generate_user_activity_report()`

### RealTimeAnalyticsCollector
Service for real-time data collection.

**Key Methods:**
- `track_user_engagement()`
- `track_data_quality()`
- `track_system_health()`

## Caching System

### AnalyticsCache
Advanced caching system with multiple cache types and automatic invalidation.

**Features:**
- **Intelligent Key Generation**: Automatic cache key generation with collision avoidance
- **Tiered Timeouts**: Different cache timeouts for different data types
- **Pattern Invalidation**: Bulk cache invalidation by pattern
- **User-Specific Caching**: Per-user cache management

### RealTimeAnalyticsCache
Specialized caching for real-time metrics.

**Features:**
- **Counter Management**: Atomic counter increments
- **Active User Tracking**: Track currently active users
- **Metric Aggregation**: Real-time metric aggregation

## Background Tasks

### Celery Tasks
Automated background processing for analytics.

**Available Tasks:**
- `collect_performance_metrics`: Collect and aggregate performance metrics
- `generate_scheduled_report`: Generate reports on schedule
- `collect_system_health_metrics`: Monitor system health
- `cleanup_old_analytics_data`: Clean up old data
- `invalidate_analytics_cache`: Cache management
- `aggregate_real_time_metrics`: Aggregate real-time data
- `send_analytics_alerts`: Send performance alerts

## Management Commands

### collect_analytics
Collect and aggregate analytics data.

```bash
python manage.py collect_analytics --period daily --days-back 1
python manage.py collect_analytics --period weekly --system-health
```

**Options:**
- `--period`: Aggregation period (hourly, daily, weekly, monthly)
- `--date`: Specific date to collect for
- `--days-back`: Number of days back to collect
- `--force`: Force recalculation of existing metrics
- `--system-health`: Include system health metrics

### generate_reports
Generate analytics reports.

```bash
python manage.py generate_reports --report-type daily_summary
python manage.py generate_reports --auto-schedule
```

**Options:**
- `--report-type`: Type of report to generate
- `--date`: Specific date for report
- `--user-id`: User ID for user-specific reports
- `--email-recipients`: Email addresses to send report to
- `--auto-schedule`: Generate scheduled reports
- `--force`: Force regeneration of existing reports

## Configuration

### Settings
Add to Django settings:

```python
# Analytics configuration
ANALYTICS_CACHE_TIMEOUT = 300  # 5 minutes default
ANALYTICS_RETENTION_DAYS = 90  # Keep data for 90 days
ANALYTICS_ALERT_EMAILS = ['admin@example.com']

# Celery beat schedule for automated tasks
CELERY_BEAT_SCHEDULE = {
    'collect-hourly-metrics': {
        'task': 'apps.analytics.tasks.collect_performance_metrics',
        'schedule': crontab(minute=0),  # Every hour
        'args': ('hourly',)
    },
    'collect-daily-metrics': {
        'task': 'apps.analytics.tasks.collect_performance_metrics',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
        'args': ('daily',)
    },
    'generate-daily-reports': {
        'task': 'apps.analytics.tasks.generate_scheduled_report',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'args': ('daily_summary',)
    },
    'system-health-check': {
        'task': 'apps.analytics.tasks.collect_system_health_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'cleanup-old-data': {
        'task': 'apps.analytics.tasks.cleanup_old_analytics_data',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Weekly on Sunday
    },
}
```

## Usage Examples

### Track User Engagement
```python
from apps.analytics.services import RealTimeAnalyticsCollector

# Track when user starts a debriefing
RealTimeAnalyticsCollector.track_user_engagement(
    user=request.user,
    engagement_type='debriefing_start',
    session_id='session-123',
    entity_type='meeting',
    entity_id=meeting.id,
    metadata={'meeting_type': 'discovery'}
)
```

### Generate Custom Report
```python
from apps.analytics.services import ReportingService

reporting_service = ReportingService()
report = reporting_service.generate_daily_summary_report(
    date=timezone.now(),
    user=request.user
)
```

### Check System Health
```python
from apps.analytics.services import RealTimeAnalyticsCollector

# Track API response time
RealTimeAnalyticsCollector.track_system_health(
    health_type='api_response_time',
    component='gemini_api',
    value=response_time_ms,
    unit='ms',
    warning_threshold=200.0,
    critical_threshold=500.0
)
```

### Use Caching
```python
from apps.analytics.cache import cache_analytics_result

@cache_analytics_result('dashboard', timeout=300)
def get_dashboard_data(user_id, days=7):
    # Expensive calculation
    return analytics_data
```

## Testing

Run analytics tests:
```bash
python manage.py test apps.analytics
```

The test suite includes:
- **Unit Tests**: Test individual components and functions
- **Integration Tests**: Test complete workflows
- **API Tests**: Test all API endpoints
- **Performance Tests**: Test caching and optimization
- **Real-time Tests**: Test real-time data collection

## Performance Considerations

### Optimization Strategies
1. **Caching**: Multi-tier caching system reduces database load
2. **Batch Processing**: Process large datasets in batches
3. **Indexing**: Optimized database indexes for analytics queries
4. **Aggregation**: Pre-aggregate metrics to reduce calculation time
5. **Background Processing**: Use Celery for heavy computations

### Monitoring
- Monitor cache hit rates
- Track query performance
- Monitor background task execution
- Set up alerts for performance degradation

## Security

### Access Control
- **Role-based Access**: Different access levels for different user roles
- **Data Isolation**: Users can only see their own data unless they have elevated permissions
- **API Authentication**: All endpoints require authentication
- **Audit Logging**: Track all analytics access and modifications

### Data Protection
- **Encryption**: Sensitive data encrypted at rest and in transit
- **Anonymization**: Personal data can be anonymized for analytics
- **Retention Policies**: Automatic cleanup of old data
- **Compliance**: GDPR and other privacy regulation compliance

## Troubleshooting

### Common Issues

**High Memory Usage**
- Check batch processing sizes
- Monitor cache usage
- Review data retention policies

**Slow Analytics Queries**
- Check database indexes
- Review query optimization
- Consider data archiving

**Cache Issues**
- Verify Redis configuration
- Check cache invalidation patterns
- Monitor cache hit rates

**Background Task Failures**
- Check Celery worker status
- Review task retry configuration
- Monitor task queue sizes

### Debugging
Enable debug logging:
```python
LOGGING = {
    'loggers': {
        'apps.analytics': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

## Future Enhancements

### Planned Features
- **Machine Learning**: Predictive analytics and anomaly detection
- **Advanced Visualizations**: Interactive charts and dashboards
- **Custom Metrics**: User-defined custom metrics
- **Data Warehouse Integration**: Integration with external data warehouses
- **Real-time Streaming**: Real-time data streaming and processing
- **Mobile Analytics**: Mobile app usage analytics
- **A/B Testing**: Built-in A/B testing framework