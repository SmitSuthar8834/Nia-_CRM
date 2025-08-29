"""
Serializers for performance monitoring models
"""
from rest_framework import serializers
from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold, ConcurrentCallMetrics
)


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """
    Serializer for PerformanceMetric model
    """
    duration = serializers.ReadOnlyField()
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'metric_type', 'metric_name', 'value', 'unit', 'status',
            'content_type', 'object_id', 'metadata', 'error_message',
            'timestamp', 'start_time', 'end_time', 'duration'
        ]
        read_only_fields = ['id', 'timestamp', 'duration']


class CallBotPerformanceSerializer(serializers.ModelSerializer):
    """
    Serializer for CallBotPerformance model
    """
    overall_score = serializers.ReadOnlyField()
    meeting_title = serializers.CharField(source='call_bot_session.meeting.title', read_only=True)
    platform = serializers.CharField(source='call_bot_session.platform', read_only=True)
    session_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = CallBotPerformance
        fields = [
            'id', 'call_bot_session', 'meeting_title', 'platform',
            'connection_time', 'connection_attempts', 'connection_success',
            'audio_quality_score', 'audio_dropouts', 'audio_latency',
            'transcription_accuracy', 'transcription_latency', 'words_per_minute',
            'error_count', 'reconnection_count',
            'cpu_usage_avg', 'memory_usage_avg',
            'overall_score', 'session_duration',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'overall_score', 'meeting_title', 'platform', 
            'session_duration', 'created_at', 'updated_at'
        ]
    
    def get_session_duration(self, obj):
        """Get call bot session duration in seconds"""
        if hasattr(obj.call_bot_session, 'duration'):
            duration = obj.call_bot_session.duration
            return duration.total_seconds() if duration else None
        return None


class AIProcessingPerformanceSerializer(serializers.ModelSerializer):
    """
    Serializer for AIProcessingPerformance model
    """
    processing_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = AIProcessingPerformance
        fields = [
            'id', 'operation_type', 'operation_id',
            'processing_time', 'input_size', 'output_size',
            'confidence_score', 'accuracy_score',
            'tokens_used', 'api_cost',
            'error_occurred', 'error_type', 'retry_count',
            'model_version', 'parameters',
            'processing_rate', 'timestamp'
        ]
        read_only_fields = ['id', 'processing_rate', 'timestamp']


class SystemAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for SystemAlert model
    """
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemAlert
        fields = [
            'id', 'alert_type', 'severity', 'title', 'description',
            'component', 'metric_threshold', 'current_value',
            'is_active', 'acknowledged', 'acknowledged_by', 'acknowledged_at',
            'resolved', 'resolved_by', 'resolved_at', 'resolution_notes',
            'first_occurred', 'last_occurred', 'occurrence_count',
            'is_expired', 'time_remaining', 'duration',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_expired', 'time_remaining', 'duration',
            'created_at', 'updated_at'
        ]
    
    def get_time_remaining(self, obj):
        """Get time remaining until alert expires (if applicable)"""
        # This is a placeholder - alerts don't have expiration in current model
        return None
    
    def get_duration(self, obj):
        """Get duration since alert first occurred"""
        from django.utils import timezone
        if obj.first_occurred:
            duration = timezone.now() - obj.first_occurred
            return duration.total_seconds()
        return None


class PerformanceThresholdSerializer(serializers.ModelSerializer):
    """
    Serializer for PerformanceThreshold model
    """
    
    class Meta:
        model = PerformanceThreshold
        fields = [
            'id', 'metric_type', 'metric_name',
            'warning_threshold', 'error_threshold', 'critical_threshold',
            'comparison_operator', 'time_window', 'min_occurrences',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate threshold values"""
        warning = data.get('warning_threshold')
        error = data.get('error_threshold')
        critical = data.get('critical_threshold')
        operator = data.get('comparison_operator', '>')
        
        # Ensure thresholds are in logical order
        if operator == '>':
            if warning and error and warning >= error:
                raise serializers.ValidationError(
                    "Warning threshold must be less than error threshold for '>' operator"
                )
            if error and critical and error >= critical:
                raise serializers.ValidationError(
                    "Error threshold must be less than critical threshold for '>' operator"
                )
        elif operator == '<':
            if warning and error and warning <= error:
                raise serializers.ValidationError(
                    "Warning threshold must be greater than error threshold for '<' operator"
                )
            if error and critical and error <= critical:
                raise serializers.ValidationError(
                    "Error threshold must be greater than critical threshold for '<' operator"
                )
        
        return data


class ConcurrentCallMetricsSerializer(serializers.ModelSerializer):
    """
    Serializer for ConcurrentCallMetrics model
    """
    capacity_utilization = serializers.SerializerMethodField()
    system_health_score = serializers.SerializerMethodField()
    
    class Meta:
        model = ConcurrentCallMetrics
        fields = [
            'id', 'timestamp',
            'active_calls', 'max_concurrent_calls',
            'successful_connections', 'failed_connections',
            'avg_connection_time', 'avg_processing_time',
            'avg_memory_usage', 'avg_cpu_usage',
            'system_load', 'available_memory', 'disk_usage',
            'capacity_utilization', 'system_health_score'
        ]
        read_only_fields = [
            'id', 'timestamp', 'capacity_utilization', 'system_health_score'
        ]
    
    def get_capacity_utilization(self, obj):
        """Calculate capacity utilization percentage (assuming 50 call limit)"""
        max_capacity = 50
        if obj.active_calls:
            return (obj.active_calls / max_capacity) * 100
        return 0
    
    def get_system_health_score(self, obj):
        """Calculate overall system health score (0-100)"""
        score = 100
        
        # Penalize high CPU usage
        if obj.avg_cpu_usage and obj.avg_cpu_usage > 80:
            score -= (obj.avg_cpu_usage - 80) * 2
        
        # Penalize high memory usage
        if obj.avg_memory_usage and obj.avg_memory_usage > 80:
            score -= (obj.avg_memory_usage - 80) * 2
        
        # Penalize high system load
        if obj.system_load and obj.system_load > 1.0:
            score -= (obj.system_load - 1.0) * 20
        
        # Penalize low available memory (less than 2GB)
        if obj.available_memory and obj.available_memory < 2048:
            score -= (2048 - obj.available_memory) / 20
        
        # Penalize high disk usage
        if obj.disk_usage and obj.disk_usage > 90:
            score -= (obj.disk_usage - 90) * 5
        
        return max(0, min(100, score))


class PerformanceSummarySerializer(serializers.Serializer):
    """
    Serializer for performance summary data
    """
    period_hours = serializers.IntegerField()
    total_metrics = serializers.IntegerField()
    error_rate = serializers.FloatField()
    
    # Call bot performance
    call_bot_performance = serializers.DictField(required=False)
    
    # AI performance
    ai_performance = serializers.DictField(required=False)
    
    # Alert information
    active_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    
    # System metrics
    max_concurrent_calls = serializers.IntegerField()
    
    generated_at = serializers.DateTimeField()


class AlertDashboardSerializer(serializers.Serializer):
    """
    Serializer for alert dashboard data
    """
    active_alerts = serializers.IntegerField()
    severity_breakdown = serializers.DictField()
    recent_alerts_24h = serializers.IntegerField()
    alert_trends = serializers.ListField(
        child=serializers.DictField()
    )
    critical_alerts = serializers.IntegerField()
    unacknowledged_alerts = serializers.IntegerField()


class SystemStatusSerializer(serializers.Serializer):
    """
    Serializer for system status data
    """
    system_resources = serializers.DictField()
    active_calls = serializers.IntegerField()
    recent_metrics = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


class CapacityAnalysisSerializer(serializers.Serializer):
    """
    Serializer for capacity analysis data
    """
    max_concurrent_calls = serializers.IntegerField(allow_null=True)
    avg_concurrent_calls = serializers.FloatField(allow_null=True)
    peak_system_load = serializers.FloatField(allow_null=True)
    avg_system_load = serializers.FloatField(allow_null=True)
    min_available_memory = serializers.FloatField(allow_null=True)
    avg_available_memory = serializers.FloatField(allow_null=True)
    max_disk_usage = serializers.FloatField(allow_null=True)
    avg_disk_usage = serializers.FloatField(allow_null=True)
    capacity_utilization = serializers.FloatField()
    assessment = serializers.DictField()


class MetricTimelineSerializer(serializers.Serializer):
    """
    Serializer for metric timeline data
    """
    timestamp = serializers.DateTimeField()
    value = serializers.FloatField()
    status = serializers.CharField()


class OperationStatsSerializer(serializers.Serializer):
    """
    Serializer for operation statistics
    """
    count = serializers.IntegerField()
    avg_processing_time = serializers.FloatField(allow_null=True)
    max_processing_time = serializers.FloatField(allow_null=True)
    avg_confidence = serializers.FloatField(allow_null=True)
    error_count = serializers.IntegerField()
    error_rate = serializers.FloatField()
    total_tokens = serializers.IntegerField(allow_null=True)


class EfficiencyTrendSerializer(serializers.Serializer):
    """
    Serializer for efficiency trend data
    """
    timestamp = serializers.DateTimeField()
    count = serializers.IntegerField()
    avg_processing_time = serializers.FloatField(allow_null=True)
    avg_confidence = serializers.FloatField(allow_null=True)
    error_count = serializers.IntegerField()
    error_rate = serializers.FloatField()


class HealthCheckSerializer(serializers.Serializer):
    """
    Serializer for health check response
    """
    health_status = serializers.ChoiceField(
        choices=['healthy', 'warning', 'critical']
    )
    active_alerts = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    checked_at = serializers.DateTimeField()


class MetricsCollectionSerializer(serializers.Serializer):
    """
    Serializer for metrics collection response
    """
    message = serializers.CharField()
    concurrent_calls = serializers.IntegerField()
    timestamp = serializers.DateTimeField()