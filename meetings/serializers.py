from rest_framework import serializers
from .models import (
    Meeting, MeetingSession, ActionItem, CallBotSession, 
    DraftSummary, ValidationSession, CRMSyncRecord
)
from leads.serializers import LeadSerializer


class ActionItemSerializer(serializers.ModelSerializer):
    """
    Serializer for ActionItem model
    """
    
    class Meta:
        model = ActionItem
        fields = [
            'id', 'description', 'assignee', 'due_date', 'priority',
            'status', 'confidence', 'source_text', 'crm_task_id', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_description(self, value):
        """Validate description field"""
        if not value.strip():
            raise serializers.ValidationError("Description cannot be empty")
        return value.strip()
    
    def validate_confidence(self, value):
        """Validate confidence field"""
        if value < 0 or value > 1:
            raise serializers.ValidationError("Confidence must be between 0 and 1")
        return value


class MeetingSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for MeetingSession model
    """
    action_items = ActionItemSerializer(many=True, read_only=True, source='actionitem_set')
    is_active = serializers.ReadOnlyField()
    duration = serializers.ReadOnlyField()
    
    class Meta:
        model = MeetingSession
        fields = [
            'id', 'ai_session_id', 'notes', 'transcript', 
            'action_items', 'summary', 'started_at', 'ended_at',
            'is_active', 'duration'
        ]
        read_only_fields = ['id', 'started_at']


class MeetingSerializer(serializers.ModelSerializer):
    """
    Serializer for Meeting model
    """
    lead = LeadSerializer(read_only=True)
    lead_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    meeting_session = MeetingSessionSerializer(read_only=True, source='meetingsession')
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'calendar_event_id', 'lead', 'lead_id', 'title', 
            'start_time', 'end_time', 'attendees', 'match_confidence', 
            'status', 'created_at', 'updated_at', 'meeting_session'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate meeting data"""
        if data.get('end_time') and data.get('start_time'):
            if data['end_time'] <= data['start_time']:
                raise serializers.ValidationError("End time must be after start time")
        
        if data.get('match_confidence') is not None:
            if data['match_confidence'] < 0 or data['match_confidence'] > 1:
                raise serializers.ValidationError("Match confidence must be between 0 and 1")
        
        return data


class CallBotSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for CallBotSession model
    """
    is_active = serializers.ReadOnlyField()
    duration = serializers.ReadOnlyField()
    
    class Meta:
        model = CallBotSession
        fields = [
            'id', 'bot_session_id', 'platform', 'join_time', 'leave_time',
            'connection_status', 'raw_transcript', 'speaker_mapping',
            'audio_quality', 'error_count', 'is_active', 'duration'
        ]
        read_only_fields = ['id', 'join_time']


class DraftSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for DraftSummary model
    """
    
    class Meta:
        model = DraftSummary
        fields = [
            'id', 'ai_generated_summary', 'key_points', 'extracted_action_items',
            'suggested_next_steps', 'decisions_made', 'suggested_crm_updates',
            'confidence_score', 'processing_time', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_confidence_score(self, value):
        """Validate confidence score field"""
        if value < 0 or value > 1:
            raise serializers.ValidationError("Confidence score must be between 0 and 1")
        return value


class CRMFormattedSummarySerializer(serializers.Serializer):
    """
    Serializer for CRM-formatted summary data
    """
    crm_system = serializers.ChoiceField(choices=['salesforce', 'hubspot', 'creatio'])
    formatted_data = serializers.JSONField(read_only=True)


class MeetingMatchSerializer(serializers.Serializer):
    """
    Serializer for meeting-lead matching operations from n8n
    """
    calendar_event_id = serializers.CharField(max_length=200)
    title = serializers.CharField(max_length=300)
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    attendees = serializers.ListField(child=serializers.EmailField(), required=False, default=list)
    
    def validate(self, data):
        """Validate meeting match data"""
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError("End time must be after start time")
        return data


class ValidationSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for ValidationSession model
    """
    draft_summary = DraftSummarySerializer(read_only=True)
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = ValidationSession
        fields = [
            'id', 'draft_summary', 'sales_rep_email', 'validation_questions',
            'rep_responses', 'validated_summary', 'approved_crm_updates',
            'validation_status', 'changes_made', 'started_at', 'completed_at',
            'expires_at', 'is_expired', 'time_remaining'
        ]
        read_only_fields = [
            'id', 'validation_questions', 'changes_made', 'started_at', 
            'expires_at', 'is_expired', 'time_remaining'
        ]


class ValidationResponseSerializer(serializers.Serializer):
    """
    Serializer for validation question responses
    """
    question_id = serializers.CharField(max_length=100)
    response = serializers.JSONField()
    
    def validate_question_id(self, value):
        """Validate question ID format"""
        if not value.strip():
            raise serializers.ValidationError("Question ID cannot be empty")
        return value.strip()


class ValidationSessionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating validation sessions
    """
    draft_summary_id = serializers.IntegerField()
    sales_rep_email = serializers.EmailField()
    session_duration_hours = serializers.IntegerField(
        required=False, 
        default=24, 
        min_value=1, 
        max_value=168  # Max 1 week
    )


class CRMSyncRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for CRMSyncRecord model
    """
    
    class Meta:
        model = CRMSyncRecord
        fields = [
            'id', 'crm_system', 'sync_status', 'crm_record_id',
            'sync_payload', 'error_message', 'retry_count',
            'synced_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ValidationSessionDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for ValidationSession with related data
    """
    draft_summary = DraftSummarySerializer(read_only=True)
    crm_sync_records = CRMSyncRecordSerializer(many=True, read_only=True, source='crmsyncrecord_set')
    meeting_info = serializers.SerializerMethodField()
    is_expired = serializers.ReadOnlyField()
    time_remaining = serializers.ReadOnlyField()
    
    class Meta:
        model = ValidationSession
        fields = [
            'id', 'draft_summary', 'sales_rep_email', 'validation_questions',
            'rep_responses', 'validated_summary', 'approved_crm_updates',
            'validation_status', 'changes_made', 'started_at', 'completed_at',
            'expires_at', 'is_expired', 'time_remaining', 'crm_sync_records',
            'meeting_info'
        ]
        read_only_fields = [
            'id', 'validation_questions', 'changes_made', 'started_at', 
            'expires_at', 'is_expired', 'time_remaining', 'crm_sync_records',
            'meeting_info'
        ]
    
    def get_meeting_info(self, obj):
        """Get meeting information from the validation session"""
        meeting = obj.draft_summary.bot_session.meeting
        return {
            'id': meeting.id,
            'title': meeting.title,
            'start_time': meeting.start_time,
            'end_time': meeting.end_time,
            'attendees': meeting.attendees,
            'lead': {
                'id': meeting.lead.id if meeting.lead else None,
                'name': meeting.lead.name if meeting.lead else None,
                'company': meeting.lead.company if meeting.lead else None,
            } if meeting.lead else None
        }