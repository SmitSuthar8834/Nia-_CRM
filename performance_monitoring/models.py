"""
Performance monitoring models for tracking system metrics and performance
"""
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json


class PerformanceMetric(models.Model):
    """
    Base model for tracking performance metrics across the system
    """
    METRIC_TYPES = [
        ('call_bot_session', 'Call Bot Session'),
        ('ai_processing', 'AI Processing'),
        ('crm_sync', 'CRM Sync'),
        ('validation_session', 'Validation Session'),
        ('database_query', 'Database Query'),
        ('api_request', 'API Request'),
        ('system_resource', 'System Resource'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ]
    
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES, db_index=True)
    metric_name = models.CharField(max_length=200, db_index=True)
    value = models.FloatField()
    unit = models.CharField(max_length=50, default='seconds')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    
    # Generic foreign key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional context data
    metadata = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    
    # Timing information
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['metric_type', 'timestamp']),
            models.Index(fields=['metric_name', 'timestamp']),
            models.Index(fields=['status', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.metric_name}: {self.value} {self.unit} ({self.status})"
    
    @property
    def duration(self):
        """Calculate duration if start and end times are available"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class CallBotPerformance(models.Model):
    """
    Specific performance tracking for call bot sessions
    """
    call_bot_session = models.OneToOneField(
        'meetings.CallBotSession', 
        on_delete=models.CASCADE,
        related_name='performance_metrics'
    )
    
    # Connection metrics
    connection_time = models.FloatField(help_text="Time to connect to call in seconds")
    connection_attempts = models.IntegerField(default=1)
    connection_success = models.BooleanField(default=True)
    
    # Audio quality metrics
    audio_quality_score = models.FloatField(null=True, blank=True, help_text="Audio quality score 0-1")
    audio_dropouts = models.IntegerField(default=0)
    audio_latency = models.FloatField(null=True, blank=True, help_text="Audio latency in ms")
    
    # Transcription metrics
    transcription_accuracy = models.FloatField(null=True, blank=True, help_text="Transcription accuracy 0-1")
    transcription_latency = models.FloatField(null=True, blank=True, help_text="Transcription latency in seconds")
    words_per_minute = models.FloatField(null=True, blank=True)
    
    # Error tracking
    error_count = models.IntegerField(default=0)
    reconnection_count = models.IntegerField(default=0)
    
    # Resource usage
    cpu_usage_avg = models.FloatField(null=True, blank=True, help_text="Average CPU usage percentage")
    memory_usage_avg = models.FloatField(null=True, blank=True, help_text="Average memory usage in MB")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['connection_success', 'created_at']),
            models.Index(fields=['transcription_accuracy']),
            models.Index(fields=['error_count']),
        ]
    
    def __str__(self):
        return f"Performance for {self.call_bot_session}"
    
    @property
    def overall_score(self):
        """Calculate overall performance score"""
        scores = []
        
        # Connection score
        if self.connection_success:
            connection_score = max(0, 1 - (self.connection_time / 30))  # 30s baseline
            scores.append(connection_score)
        
        # Audio quality score
        if self.audio_quality_score is not None:
            scores.append(self.audio_quality_score)
        
        # Transcription accuracy score
        if self.transcription_accuracy is not None:
            scores.append(self.transcription_accuracy)
        
        # Error penalty
        error_penalty = max(0, 1 - (self.error_count * 0.1))
        scores.append(error_penalty)
        
        return sum(scores) / len(scores) if scores else 0


class AIProcessingPerformance(models.Model):
    """
    Performance tracking for AI processing operations
    """
    OPERATION_TYPES = [
        ('transcription', 'Transcription'),
        ('summary_generation', 'Summary Generation'),
        ('action_item_extraction', 'Action Item Extraction'),
        ('crm_suggestion', 'CRM Suggestion'),
        ('validation_questions', 'Validation Questions'),
    ]
    
    operation_type = models.CharField(max_length=50, choices=OPERATION_TYPES, db_index=True)
    operation_id = models.CharField(max_length=200, db_index=True)
    
    # Performance metrics
    processing_time = models.FloatField(help_text="Processing time in seconds")
    input_size = models.IntegerField(help_text="Input size in characters/tokens")
    output_size = models.IntegerField(help_text="Output size in characters/tokens")
    
    # Quality metrics
    confidence_score = models.FloatField(null=True, blank=True, help_text="AI confidence score 0-1")
    accuracy_score = models.FloatField(null=True, blank=True, help_text="Measured accuracy 0-1")
    
    # Resource usage
    tokens_used = models.IntegerField(null=True, blank=True)
    api_cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    
    # Error tracking
    error_occurred = models.BooleanField(default=False)
    error_type = models.CharField(max_length=100, blank=True)
    retry_count = models.IntegerField(default=0)
    
    # Context
    model_version = models.CharField(max_length=100, blank=True)
    parameters = models.JSONField(default=dict)
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['operation_type', 'timestamp']),
            models.Index(fields=['processing_time']),
            models.Index(fields=['confidence_score']),
            models.Index(fields=['error_occurred', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.operation_type} - {self.processing_time}s"
    
    @property
    def processing_rate(self):
        """Calculate processing rate (characters/tokens per second)"""
        if self.processing_time > 0:
            return self.input_size / self.processing_time
        return 0


class SystemAlert(models.Model):
    """
    System alerts for performance issues and failures
    """
    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    ALERT_TYPES = [
        ('performance_degradation', 'Performance Degradation'),
        ('high_error_rate', 'High Error Rate'),
        ('system_failure', 'System Failure'),
        ('resource_exhaustion', 'Resource Exhaustion'),
        ('api_rate_limit', 'API Rate Limit'),
        ('connection_failure', 'Connection Failure'),
    ]
    
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Alert context
    component = models.CharField(max_length=100, db_index=True)
    metric_threshold = models.FloatField(null=True, blank=True)
    current_value = models.FloatField(null=True, blank=True)
    
    # Status tracking
    is_active = models.BooleanField(default=True, db_index=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.CharField(max_length=200, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution tracking
    resolved = models.BooleanField(default=False)
    resolved_by = models.CharField(max_length=200, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Timing
    first_occurred = models.DateTimeField(default=timezone.now)
    last_occurred = models.DateTimeField(default=timezone.now)
    occurrence_count = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['alert_type', 'is_active']),
            models.Index(fields=['severity', 'is_active']),
            models.Index(fields=['component', 'is_active']),
            models.Index(fields=['first_occurred']),
        ]
        ordering = ['-severity', '-first_occurred']
    
    def __str__(self):
        return f"{self.severity.upper()}: {self.title}"
    
    def acknowledge(self, user: str):
        """Acknowledge the alert"""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['acknowledged', 'acknowledged_by', 'acknowledged_at'])
    
    def resolve(self, user: str, notes: str = ""):
        """Resolve the alert"""
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.is_active = False
        self.save(update_fields=[
            'resolved', 'resolved_by', 'resolved_at', 
            'resolution_notes', 'is_active'
        ])


class PerformanceThreshold(models.Model):
    """
    Configurable performance thresholds for alerting
    """
    metric_type = models.CharField(max_length=50, db_index=True)
    metric_name = models.CharField(max_length=200, db_index=True)
    
    # Threshold values
    warning_threshold = models.FloatField(null=True, blank=True)
    error_threshold = models.FloatField(null=True, blank=True)
    critical_threshold = models.FloatField(null=True, blank=True)
    
    # Threshold configuration
    comparison_operator = models.CharField(
        max_length=10, 
        choices=[('>', 'Greater than'), ('<', 'Less than'), ('=', 'Equal to')],
        default='>'
    )
    time_window = models.IntegerField(default=300, help_text="Time window in seconds")
    min_occurrences = models.IntegerField(default=1, help_text="Minimum occurrences to trigger alert")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['metric_type', 'metric_name']
        indexes = [
            models.Index(fields=['metric_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.metric_type}.{self.metric_name} thresholds"


class ConcurrentCallMetrics(models.Model):
    """
    Metrics for tracking concurrent call handling performance
    """
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Call metrics
    active_calls = models.IntegerField(default=0)
    max_concurrent_calls = models.IntegerField(default=0)
    successful_connections = models.IntegerField(default=0)
    failed_connections = models.IntegerField(default=0)
    
    # Performance metrics
    avg_connection_time = models.FloatField(null=True, blank=True)
    avg_processing_time = models.FloatField(null=True, blank=True)
    avg_memory_usage = models.FloatField(null=True, blank=True)
    avg_cpu_usage = models.FloatField(null=True, blank=True)
    
    # System health
    system_load = models.FloatField(null=True, blank=True)
    available_memory = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['active_calls']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Concurrent calls: {self.active_calls} at {self.timestamp}"