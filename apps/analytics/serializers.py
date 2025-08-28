"""
Analytics Serializers
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import PerformanceMetric, UserEngagementMetric, DataQualityMetric, SystemHealthMetric, Report


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for analytics"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """Serializer for performance metrics"""
    user = UserBasicSerializer(read_only=True)
    is_meeting_target = serializers.ReadOnlyField()
    
    class Meta:
        model = PerformanceMetric
        fields = [
            'id', 'metric_type', 'metric_name', 'aggregation_period',
            'period_start', 'period_end', 'value', 'count', 'target_value',
            'user', 'department', 'metadata', 'is_meeting_target',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserEngagementMetricSerializer(serializers.ModelSerializer):
    """Serializer for user engagement metrics"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = UserEngagementMetric
        fields = [
            'id', 'user', 'engagement_type', 'session_id', 'duration_seconds',
            'entity_type', 'entity_id', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DataQualityMetricSerializer(serializers.ModelSerializer):
    """Serializer for data quality metrics"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = DataQualityMetric
        fields = [
            'id', 'quality_type', 'entity_type', 'field_name', 'score',
            'confidence', 'entity_id', 'user', 'measurement_date',
            'details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SystemHealthMetricSerializer(serializers.ModelSerializer):
    """Serializer for system health metrics"""
    
    class Meta:
        model = SystemHealthMetric
        fields = [
            'id', 'health_type', 'component', 'value', 'unit', 'status',
            'warning_threshold', 'critical_threshold', 'details',
            'measured_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for reports"""
    created_by = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'report_type', 'title', 'description', 'period_start',
            'period_end', 'report_data', 'summary', 'status', 'generated_at',
            'generation_time_seconds', 'created_by', 'is_public', 'created_at'
        ]
        read_only_fields = [
            'id', 'report_data', 'summary', 'status', 'generated_at',
            'generation_time_seconds', 'created_at'
        ]


class AnalyticsSummarySerializer(serializers.Serializer):
    """Serializer for analytics summary data"""
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    total_meetings = serializers.IntegerField()
    sales_meetings = serializers.IntegerField()
    completed_debriefings = serializers.IntegerField()
    completion_rate = serializers.FloatField()
    extraction_accuracy = serializers.FloatField()
    matching_rate = serializers.FloatField()
    sync_success_rate = serializers.FloatField()
    total_engagements = serializers.IntegerField()
    unique_users = serializers.IntegerField()


class CompetitiveIntelligenceSerializer(serializers.Serializer):
    """Serializer for competitive intelligence insights"""
    total_competitive_mentions = serializers.IntegerField()
    unique_competitors = serializers.IntegerField()
    top_competitors = serializers.ListField(
        child=serializers.DictField()
    )
    threat_distribution = serializers.ListField(
        child=serializers.DictField()
    )


class DashboardAnalyticsSerializer(serializers.Serializer):
    """Serializer for dashboard analytics data"""
    period = serializers.DictField()
    debriefing_metrics = serializers.DictField()
    extraction_metrics = serializers.DictField()
    meeting_metrics = serializers.DictField()
    participant_metrics = serializers.DictField()
    crm_metrics = serializers.DictField()
    engagement_metrics = serializers.DictField()
    competitive_metrics = CompetitiveIntelligenceSerializer()


class SystemHealthStatusSerializer(serializers.Serializer):
    """Serializer for system health status"""
    overall_status = serializers.CharField()
    components = serializers.ListField(
        child=serializers.DictField()
    )
    alerts = serializers.ListField(
        child=serializers.DictField()
    )
    summary = serializers.DictField()
    last_updated = serializers.DateTimeField()


class AnalyticsExportSerializer(serializers.Serializer):
    """Serializer for analytics export requests"""
    format = serializers.ChoiceField(choices=['json', 'csv'], default='json')
    metric_type = serializers.ChoiceField(
        choices=['all', 'debriefing', 'extraction', 'meeting', 'participant', 'crm', 'engagement', 'competitive'],
        default='all'
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)


class ReportGenerationSerializer(serializers.Serializer):
    """Serializer for report generation requests"""
    report_type = serializers.ChoiceField(
        choices=['daily_summary', 'weekly_performance', 'user_activity', 'data_quality', 'system_health']
    )
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField(required=False)
    target_user_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        """Validate report generation request"""
        if data['report_type'] == 'user_activity' and not data.get('target_user_id'):
            raise serializers.ValidationError(
                "target_user_id is required for user_activity reports"
            )
        return data


class EngagementTrackingSerializer(serializers.Serializer):
    """Serializer for engagement tracking requests"""
    engagement_type = serializers.ChoiceField(
        choices=[
            'login', 'meeting_view', 'debriefing_start', 'debriefing_complete',
            'lead_update', 'calendar_sync', 'ai_interaction'
        ]
    )
    session_id = serializers.CharField(required=False, allow_blank=True)
    duration_seconds = serializers.IntegerField(required=False, min_value=0)
    entity_type = serializers.CharField(required=False, allow_blank=True)
    entity_id = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.DictField(required=False, default=dict)