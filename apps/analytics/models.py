"""
Analytics and Reporting Models
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PerformanceMetric(models.Model):
    """
    Track various performance metrics for the system
    """
    METRIC_TYPE_CHOICES = [
        ('debriefing_completion', 'Debriefing Completion Rate'),
        ('data_extraction_accuracy', 'Data Extraction Accuracy'),
        ('meeting_detection_accuracy', 'Meeting Detection Accuracy'),
        ('participant_matching_accuracy', 'Participant Matching Accuracy'),
        ('crm_sync_success', 'CRM Sync Success Rate'),
        ('ai_response_time', 'AI Response Time'),
        ('user_engagement', 'User Engagement'),
        ('lead_conversion', 'Lead Conversion Rate'),
    ]
    
    AGGREGATION_PERIOD_CHOICES = [
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metric Information
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPE_CHOICES)
    metric_name = models.CharField(max_length=200)
    aggregation_period = models.CharField(max_length=20, choices=AGGREGATION_PERIOD_CHOICES)
    
    # Time Period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Metric Values
    value = models.FloatField()
    count = models.IntegerField(default=0)
    target_value = models.FloatField(blank=True, null=True)
    
    # Context
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    
    # Additional Data
    metadata = models.JSONField(default=dict, help_text="Additional metric data")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'performance_metrics'
        unique_together = ['metric_type', 'aggregation_period', 'period_start', 'user']
        indexes = [
            models.Index(fields=['metric_type', 'period_start']),
            models.Index(fields=['user', 'metric_type']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        ordering = ['-period_start']

    def __str__(self):
        return f"{self.metric_name}: {self.value} ({self.period_start.date()})"

    @property
    def is_meeting_target(self):
        """Check if metric is meeting its target"""
        if self.target_value:
            return self.value >= self.target_value
        return None


class UserEngagementMetric(models.Model):
    """
    Track user engagement with the meeting intelligence system
    """
    ENGAGEMENT_TYPE_CHOICES = [
        ('login', 'Login'),
        ('meeting_view', 'Meeting Viewed'),
        ('debriefing_start', 'Debriefing Started'),
        ('debriefing_complete', 'Debriefing Completed'),
        ('lead_update', 'Lead Updated'),
        ('calendar_sync', 'Calendar Synced'),
        ('ai_interaction', 'AI Interaction'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='engagement_metrics')
    
    # Engagement Details
    engagement_type = models.CharField(max_length=50, choices=ENGAGEMENT_TYPE_CHOICES)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    
    # Context
    entity_type = models.CharField(max_length=50, blank=True, null=True)
    entity_id = models.UUIDField(blank=True, null=True)
    
    # Additional Data
    metadata = models.JSONField(default=dict)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_engagement_metrics'
        indexes = [
            models.Index(fields=['user', 'engagement_type', 'created_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.engagement_type} - {self.created_at}"


class DataQualityMetric(models.Model):
    """
    Track data quality metrics for extracted information
    """
    QUALITY_TYPE_CHOICES = [
        ('extraction_confidence', 'Extraction Confidence'),
        ('field_completeness', 'Field Completeness'),
        ('data_accuracy', 'Data Accuracy'),
        ('user_corrections', 'User Corrections'),
        ('validation_errors', 'Validation Errors'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Quality Metric
    quality_type = models.CharField(max_length=50, choices=QUALITY_TYPE_CHOICES)
    entity_type = models.CharField(max_length=50)  # meeting, lead, debriefing, etc.
    field_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Quality Scores
    score = models.FloatField(help_text="Quality score (0-1)")
    confidence = models.FloatField(blank=True, null=True, help_text="Confidence in the score")
    
    # Context
    entity_id = models.UUIDField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    
    # Time Period
    measurement_date = models.DateField(default=timezone.now)
    
    # Additional Data
    details = models.JSONField(default=dict)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'data_quality_metrics'
        indexes = [
            models.Index(fields=['quality_type', 'entity_type']),
            models.Index(fields=['entity_id']),
            models.Index(fields=['measurement_date']),
            models.Index(fields=['score']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quality_type} - {self.entity_type}: {self.score}"


class SystemHealthMetric(models.Model):
    """
    Track system health and performance metrics
    """
    HEALTH_TYPE_CHOICES = [
        ('api_response_time', 'API Response Time'),
        ('database_performance', 'Database Performance'),
        ('ai_service_availability', 'AI Service Availability'),
        ('calendar_sync_success', 'Calendar Sync Success'),
        ('crm_sync_success', 'CRM Sync Success'),
        ('error_rate', 'Error Rate'),
        ('memory_usage', 'Memory Usage'),
        ('cpu_usage', 'CPU Usage'),
    ]
    
    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('down', 'Down'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Health Metric
    health_type = models.CharField(max_length=50, choices=HEALTH_TYPE_CHOICES)
    component = models.CharField(max_length=100, help_text="System component being measured")
    
    # Metric Values
    value = models.FloatField()
    unit = models.CharField(max_length=20, blank=True, null=True)  # ms, %, MB, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='healthy')
    
    # Thresholds
    warning_threshold = models.FloatField(blank=True, null=True)
    critical_threshold = models.FloatField(blank=True, null=True)
    
    # Additional Data
    details = models.JSONField(default=dict)
    
    # Metadata
    measured_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'system_health_metrics'
        indexes = [
            models.Index(fields=['health_type', 'component']),
            models.Index(fields=['status', 'measured_at']),
            models.Index(fields=['measured_at']),
        ]
        ordering = ['-measured_at']

    def __str__(self):
        return f"{self.component} - {self.health_type}: {self.value} ({self.status})"

    def update_status(self):
        """Update status based on thresholds"""
        if self.critical_threshold and self.value >= self.critical_threshold:
            self.status = 'critical'
        elif self.warning_threshold and self.value >= self.warning_threshold:
            self.status = 'warning'
        else:
            self.status = 'healthy'
        self.save(update_fields=['status'])


class Report(models.Model):
    """
    Generated reports for analytics and insights
    """
    REPORT_TYPE_CHOICES = [
        ('daily_summary', 'Daily Summary'),
        ('weekly_performance', 'Weekly Performance'),
        ('monthly_analytics', 'Monthly Analytics'),
        ('user_activity', 'User Activity Report'),
        ('data_quality', 'Data Quality Report'),
        ('system_health', 'System Health Report'),
        ('competitive_intelligence', 'Competitive Intelligence'),
        ('pipeline_analysis', 'Pipeline Analysis'),
    ]
    
    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Report Information
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Time Period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Report Data
    report_data = models.JSONField(default=dict, help_text="Generated report data")
    summary = models.TextField(blank=True, null=True)
    
    # Generation Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    generated_at = models.DateTimeField(blank=True, null=True)
    generation_time_seconds = models.IntegerField(blank=True, null=True)
    
    # Access Control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reports'
        indexes = [
            models.Index(fields=['report_type', 'period_start']),
            models.Index(fields=['created_by', 'created_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.period_start.date()} to {self.period_end.date()}"

    def mark_completed(self, report_data, summary=None):
        """Mark report as completed"""
        self.status = 'completed'
        self.report_data = report_data
        self.summary = summary
        self.generated_at = timezone.now()
        
        if self.created_at:
            self.generation_time_seconds = int((self.generated_at - self.created_at).total_seconds())
        
        self.save()

    def mark_failed(self, error_message):
        """Mark report generation as failed"""
        self.status = 'failed'
        self.summary = f"Generation failed: {error_message}"
        self.save()