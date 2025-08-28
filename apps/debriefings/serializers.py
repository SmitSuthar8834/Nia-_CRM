"""
Serializers for debriefing models
"""
from rest_framework import serializers
from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight, DebriefingTemplate


class DebriefingSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for DebriefingSession model
    """
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    meeting_date = serializers.DateTimeField(source='meeting.start_time', read_only=True)
    meeting_type = serializers.CharField(source='meeting.meeting_type', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = DebriefingSession
        fields = [
            'id', 'meeting', 'meeting_title', 'meeting_date', 'meeting_type',
            'user', 'scheduled_time', 'started_at', 'completed_at', 'status',
            'conversation_data', 'current_question_index', 'total_questions',
            'extracted_data', 'confidence_scores', 'ai_insights',
            'user_approved', 'approval_timestamp', 'user_feedback',
            'duration_minutes', 'is_overdue', 'progress_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'started_at', 'completed_at', 'duration_minutes',
            'is_overdue', 'created_at', 'updated_at'
        ]
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage"""
        if obj.total_questions and obj.total_questions > 0:
            answered = obj.questions.filter(user_response__isnull=False).count()
            return round((answered / obj.total_questions) * 100, 2)
        return 0.0


class DebriefingQuestionSerializer(serializers.ModelSerializer):
    """
    Serializer for DebriefingQuestion model
    """
    has_response = serializers.SerializerMethodField()
    parent_question_text = serializers.CharField(
        source='parent_question.question_text', 
        read_only=True
    )
    
    class Meta:
        model = DebriefingQuestion
        fields = [
            'id', 'session', 'question_text', 'question_type', 'question_order',
            'is_follow_up', 'parent_question', 'parent_question_text',
            'ai_context', 'ai_prompt', 'user_response', 'response_timestamp',
            'processed', 'extracted_entities', 'has_response',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'response_timestamp', 'processed', 'extracted_entities',
            'created_at', 'updated_at'
        ]
    
    def get_has_response(self, obj):
        """Check if question has a response"""
        return obj.user_response is not None and obj.user_response.strip() != ''


class DebriefingInsightSerializer(serializers.ModelSerializer):
    """
    Serializer for DebriefingInsight model
    """
    source_question_text = serializers.CharField(
        source='source_question.question_text',
        read_only=True
    )
    confidence_level_display = serializers.CharField(
        source='get_confidence_level_display',
        read_only=True
    )
    
    class Meta:
        model = DebriefingInsight
        fields = [
            'id', 'session', 'insight_type', 'title', 'description',
            'confidence_level', 'confidence_level_display', 'confidence_score',
            'source_question', 'source_question_text', 'source_text',
            'suggested_actions', 'priority', 'user_validated', 'user_feedback',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'confidence_score', 'created_at', 'updated_at'
        ]


class DebriefingTemplateSerializer(serializers.ModelSerializer):
    """
    Serializer for DebriefingTemplate model
    """
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )
    question_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DebriefingTemplate
        fields = [
            'id', 'name', 'template_type', 'description',
            'question_templates', 'ai_prompts', 'extraction_rules',
            'is_active', 'usage_count', 'question_count',
            'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'usage_count', 'created_by', 'created_at', 'updated_at'
        ]
    
    def get_question_count(self, obj):
        """Get number of questions in template"""
        return len(obj.question_templates) if obj.question_templates else 0


class DebriefingSessionSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for debriefing session summary with related data
    """
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    meeting_date = serializers.DateTimeField(source='meeting.start_time', read_only=True)
    meeting_type = serializers.CharField(source='meeting.meeting_type', read_only=True)
    organizer_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    questions = DebriefingQuestionSerializer(many=True, read_only=True)
    insights = DebriefingInsightSerializer(many=True, read_only=True)
    
    duration_minutes = serializers.ReadOnlyField()
    progress_percentage = serializers.SerializerMethodField()
    insights_count = serializers.SerializerMethodField()
    answered_questions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DebriefingSession
        fields = [
            'id', 'meeting_title', 'meeting_date', 'meeting_type',
            'organizer_name', 'scheduled_time', 'started_at', 'completed_at',
            'status', 'duration_minutes', 'progress_percentage',
            'questions', 'insights', 'insights_count', 'answered_questions_count',
            'extracted_data', 'confidence_scores', 'user_approved',
            'created_at', 'updated_at'
        ]
    
    def get_progress_percentage(self, obj):
        """Calculate progress percentage"""
        if obj.total_questions and obj.total_questions > 0:
            answered = obj.questions.filter(user_response__isnull=False).count()
            return round((answered / obj.total_questions) * 100, 2)
        return 0.0
    
    def get_insights_count(self, obj):
        """Get count of insights"""
        return obj.insights.count()
    
    def get_answered_questions_count(self, obj):
        """Get count of answered questions"""
        return obj.questions.filter(user_response__isnull=False).count()


class DebriefingAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for debriefing analytics data
    """
    period_days = serializers.IntegerField()
    total_sessions = serializers.IntegerField()
    
    completion_metrics = serializers.DictField()
    timing_metrics = serializers.DictField()
    quality_metrics = serializers.DictField()
    trends = serializers.ListField()
    
    class Meta:
        fields = [
            'period_days', 'total_sessions', 'completion_metrics',
            'timing_metrics', 'quality_metrics', 'trends'
        ]


class UserPerformanceSerializer(serializers.Serializer):
    """
    Serializer for user performance metrics
    """
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    period_days = serializers.IntegerField()
    
    basic_metrics = serializers.DictField()
    meeting_type_breakdown = serializers.DictField()
    team_comparison = serializers.DictField()
    recent_activity = serializers.ListField()
    improvement_suggestions = serializers.ListField()
    
    class Meta:
        fields = [
            'user_id', 'username', 'period_days', 'basic_metrics',
            'meeting_type_breakdown', 'team_comparison', 'recent_activity',
            'improvement_suggestions'
        ]


class SessionExportSerializer(serializers.Serializer):
    """
    Serializer for session export data
    """
    session_info = serializers.DictField()
    conversation = serializers.DictField()
    insights = serializers.ListField()
    extracted_data = serializers.DictField()
    export_timestamp = serializers.DateTimeField()
    
    class Meta:
        fields = [
            'session_info', 'conversation', 'insights',
            'extracted_data', 'export_timestamp'
        ]