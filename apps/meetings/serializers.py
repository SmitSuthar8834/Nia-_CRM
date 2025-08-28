"""
Serializers for Meeting Intelligence API
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Meeting, MeetingParticipant, MeetingNote


class MeetingParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Meeting Participants"""
    
    display_name = serializers.ReadOnlyField()
    matched_lead_name = serializers.CharField(source='matched_lead.full_name', read_only=True)
    matched_lead_company = serializers.CharField(source='matched_lead.company', read_only=True)
    
    class Meta:
        model = MeetingParticipant
        fields = [
            'id', 'email', 'name', 'company', 'title', 'phone',
            'participant_type', 'response_status', 'is_external',
            'matched_lead', 'matched_lead_name', 'matched_lead_company',
            'match_confidence', 'match_method', 'manual_verification_required',
            'display_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'display_name']


class MeetingNoteSerializer(serializers.ModelSerializer):
    """Serializer for Meeting Notes"""
    
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = MeetingNote
        fields = [
            'id', 'title', 'content', 'note_type', 'author', 'author_name',
            'ai_generated', 'ai_confidence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'author_name']


class MeetingSerializer(serializers.ModelSerializer):
    """Serializer for Meeting model"""
    
    participants = MeetingParticipantSerializer(many=True, read_only=True)
    notes = MeetingNoteSerializer(many=True, read_only=True)
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    participant_count = serializers.SerializerMethodField()
    external_participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'calendar_event_id', 'calendar_provider', 'title', 'description',
            'start_time', 'end_time', 'timezone', 'location', 'meeting_url',
            'meeting_type', 'is_sales_meeting', 'confidence_score', 'status',
            'organizer', 'organizer_name', 'debriefing_scheduled', 'debriefing_completed',
            'debriefing_due_at', 'duration_minutes', 'is_past', 'participant_count',
            'external_participant_count', 'participants', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'duration_minutes', 'is_past',
            'participant_count', 'external_participant_count', 'organizer_name', 'organizer'
        ]
    
    def get_participant_count(self, obj):
        """Get total participant count"""
        return obj.participants.count()
    
    def get_external_participant_count(self, obj):
        """Get external participant count"""
        return obj.participants.filter(is_external=True).count()


class MeetingListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for meeting lists"""
    
    organizer_name = serializers.CharField(source='organizer.get_full_name', read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    participant_count = serializers.SerializerMethodField()
    external_participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'title', 'start_time', 'end_time', 'meeting_type',
            'is_sales_meeting', 'confidence_score', 'status', 'organizer_name',
            'debriefing_scheduled', 'debriefing_completed', 'duration_minutes',
            'is_past', 'participant_count', 'external_participant_count'
        ]
    
    def get_participant_count(self, obj):
        """Get total participant count"""
        return obj.participants.count()
    
    def get_external_participant_count(self, obj):
        """Get external participant count"""
        return obj.participants.filter(is_external=True).count()


class MeetingStatsSerializer(serializers.Serializer):
    """Serializer for meeting statistics"""
    
    total_meetings = serializers.IntegerField()
    sales_meetings = serializers.IntegerField()
    completed_meetings = serializers.IntegerField()
    upcoming_meetings = serializers.IntegerField()
    debriefings_pending = serializers.IntegerField()
    debriefings_completed = serializers.IntegerField()
    average_duration = serializers.FloatField()
    meeting_types = serializers.DictField()
    monthly_trend = serializers.ListField()


class MeetingIntelligenceSerializer(serializers.Serializer):
    """Serializer for meeting intelligence detection results"""
    
    meeting_id = serializers.UUIDField()
    is_sales_meeting = serializers.BooleanField()
    confidence_score = serializers.FloatField()
    meeting_type = serializers.CharField()
    detected_participants = serializers.ListField()
    matched_leads = serializers.ListField()
    intelligence_summary = serializers.DictField()


class MeetingSearchSerializer(serializers.Serializer):
    """Serializer for meeting search parameters"""
    
    search = serializers.CharField(required=False, allow_blank=True, help_text="Search in title, description, or participant names")
    meeting_type = serializers.ChoiceField(choices=Meeting.MEETING_TYPE_CHOICES, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Meeting.STATUS_CHOICES, required=False, allow_blank=True)
    is_sales_meeting = serializers.BooleanField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    organizer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    has_debriefing = serializers.BooleanField(required=False, allow_null=True)
    participant_email = serializers.EmailField(required=False, allow_blank=True)
    company = serializers.CharField(required=False, allow_blank=True)