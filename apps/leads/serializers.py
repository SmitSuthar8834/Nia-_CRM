"""
Serializers for Lead Management and Participant Matching
"""
from rest_framework import serializers
from .models import Lead, LeadNote, ActionItem, CompetitiveIntelligence
# from .verification import VerificationRequest
from apps.meetings.models import MeetingParticipant


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead model"""
    
    full_name = serializers.ReadOnlyField()
    days_since_last_meeting = serializers.ReadOnlyField()
    
    class Meta:
        model = Lead
        fields = [
            'id', 'creatio_id', 'external_id', 'first_name', 'last_name', 'full_name',
            'email', 'phone', 'mobile', 'company', 'title', 'department', 
            'company_size', 'industry', 'website', 'source', 'status', 
            'qualification_score', 'last_meeting_date', 'meeting_count',
            'relationship_stage', 'decision_authority', 'estimated_budget',
            'estimated_close_date', 'probability', 'assigned_to',
            'created_at', 'updated_at', 'last_contacted', 'days_since_last_meeting'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'meeting_count', 'last_meeting_date']


class LeadNoteSerializer(serializers.ModelSerializer):
    """Serializer for Lead Notes"""
    
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = LeadNote
        fields = [
            'id', 'lead', 'author', 'author_name', 'title', 'content', 
            'note_type', 'ai_generated', 'ai_confidence', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'author_name']


class ActionItemSerializer(serializers.ModelSerializer):
    """Serializer for Action Items"""
    
    is_overdue = serializers.ReadOnlyField()
    owner_user_name = serializers.CharField(source='owner_user.get_full_name', read_only=True)
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)
    
    class Meta:
        model = ActionItem
        fields = [
            'id', 'meeting', 'meeting_title', 'lead', 'lead_name', 'description',
            'owner', 'owner_user', 'owner_user_name', 'due_date', 'priority', 
            'status', 'is_commitment', 'is_internal', 'completed_at', 
            'completion_notes', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_overdue']


class CompetitiveIntelligenceSerializer(serializers.ModelSerializer):
    """Serializer for Competitive Intelligence"""
    
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    
    class Meta:
        model = CompetitiveIntelligence
        fields = [
            'id', 'lead', 'lead_name', 'meeting', 'meeting_title', 'competitor_name',
            'competitive_context', 'strengths_mentioned', 'weaknesses_mentioned',
            'pricing_intelligence', 'relationship_status', 'threat_level',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MeetingParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Meeting Participants"""
    
    display_name = serializers.ReadOnlyField()
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    matched_lead_name = serializers.CharField(source='matched_lead.full_name', read_only=True)
    
    class Meta:
        model = MeetingParticipant
        fields = [
            'id', 'meeting', 'meeting_title', 'email', 'name', 'display_name',
            'company', 'title', 'phone', 'participant_type', 'response_status',
            'is_external', 'matched_lead', 'matched_lead_name', 'match_confidence',
            'match_method', 'manual_verification_required', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'display_name']


# class VerificationRequestSerializer(serializers.ModelSerializer):
#     """Serializer for Verification Requests"""
#     
#     participant_name = serializers.CharField(source='meeting_participant.display_name', read_only=True)
#     participant_email = serializers.CharField(source='meeting_participant.email', read_only=True)
#     meeting_title = serializers.CharField(source='meeting_participant.meeting.title', read_only=True)
#     assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
#     reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
#     selected_match_name = serializers.CharField(source='selected_match.full_name', read_only=True)
#     is_overdue = serializers.ReadOnlyField()
#     
#     class Meta:
#         model = VerificationRequest
#         fields = [
#             'id', 'meeting_participant', 'participant_name', 'participant_email',
#             'meeting_title', 'verification_type', 'status', 'participant_data',
#             'potential_matches', 'confidence_scores', 'assigned_to', 'assigned_to_name',
#             'reviewed_by', 'reviewed_by_name', 'selected_match', 'selected_match_name',
#             'create_new_lead', 'reviewer_notes', 'created_at', 'due_date',
#             'reviewed_at', 'is_overdue'
#         ]
#         read_only_fields = [
#             'id', 'created_at', 'reviewed_at', 'is_overdue', 'participant_name',
#             'participant_email', 'meeting_title', 'assigned_to_name', 'reviewed_by_name',
#             'selected_match_name'
#         ]


class ParticipantMatchResultSerializer(serializers.Serializer):
    """Serializer for participant matching results"""
    
    participant = serializers.DictField()
    matched_lead = LeadSerializer(read_only=True)
    confidence_score = serializers.FloatField()
    match_method = serializers.CharField(allow_null=True)
    potential_matches = serializers.ListField(child=serializers.DictField())
    requires_manual_verification = serializers.BooleanField()
    should_create_new_lead = serializers.BooleanField()
    
    class Meta:
        fields = [
            'participant', 'matched_lead', 'confidence_score', 'match_method',
            'potential_matches', 'requires_manual_verification', 'should_create_new_lead'
        ]


class LinkedInProfileSerializer(serializers.Serializer):
    """Serializer for LinkedIn profile data"""
    
    profile_url = serializers.URLField(allow_null=True)
    name = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    company = serializers.CharField(allow_blank=True)
    industry = serializers.CharField(allow_blank=True)
    location = serializers.CharField(allow_blank=True)
    summary = serializers.CharField(allow_blank=True)
    confidence = serializers.FloatField()
    experience_years = serializers.IntegerField()
    skills = serializers.ListField(child=serializers.CharField())
    education = serializers.ListField(child=serializers.DictField())


class EnhancedParticipantSerializer(serializers.Serializer):
    """Serializer for LinkedIn-enhanced participant data"""
    
    email = serializers.EmailField()
    name = serializers.CharField()
    company = serializers.CharField(allow_blank=True)
    title = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_blank=True)
    
    # LinkedIn enhancement fields
    linkedin_profile = serializers.URLField(allow_null=True, required=False)
    linkedin_confidence = serializers.FloatField(allow_null=True, required=False)
    enhanced_title = serializers.CharField(allow_blank=True, required=False)
    enhanced_company = serializers.CharField(allow_blank=True, required=False)
    industry = serializers.CharField(allow_blank=True, required=False)
    location = serializers.CharField(allow_blank=True, required=False)
    profile_summary = serializers.CharField(allow_blank=True, required=False)
    experience_years = serializers.IntegerField(allow_null=True, required=False)
    skills = serializers.ListField(child=serializers.CharField(), required=False)
    education = serializers.ListField(child=serializers.DictField(), required=False)


class ParticipantAnalysisResultSerializer(serializers.Serializer):
    """Serializer for complete participant analysis results"""
    
    total_participants = serializers.IntegerField()
    matched_participants = serializers.IntegerField()
    new_leads_created = serializers.IntegerField()
    manual_verification_required = serializers.IntegerField()
    linkedin_enhanced = serializers.IntegerField()
    matching_results = ParticipantMatchResultSerializer(many=True)
    created_leads = LeadSerializer(many=True)
    verification_queue = serializers.ListField(child=serializers.DictField())


class VerificationStatisticsSerializer(serializers.Serializer):
    """Serializer for verification statistics"""
    
    total_requests = serializers.IntegerField()
    approved_requests = serializers.IntegerField()
    rejected_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    approval_rate = serializers.FloatField()
    avg_review_hours = serializers.FloatField()
    overdue_requests = serializers.IntegerField()


class MatchingConfidenceSerializer(serializers.Serializer):
    """Serializer for matching confidence thresholds"""
    
    high_confidence_threshold = serializers.FloatField()
    medium_confidence_threshold = serializers.FloatField()
    low_confidence_threshold = serializers.FloatField()
    
    def to_representation(self, instance):
        """Return confidence thresholds from ParticipantMatchingService"""
        from .services import ParticipantMatchingService
        return {
            'high_confidence_threshold': ParticipantMatchingService.HIGH_CONFIDENCE_THRESHOLD,
            'medium_confidence_threshold': ParticipantMatchingService.MEDIUM_CONFIDENCE_THRESHOLD,
            'low_confidence_threshold': ParticipantMatchingService.LOW_CONFIDENCE_THRESHOLD
        }


class BulkParticipantMatchSerializer(serializers.Serializer):
    """Serializer for bulk participant matching requests"""
    
    participants = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=100  # Reasonable limit for bulk operations
    )
    use_linkedin_enhancement = serializers.BooleanField(default=False)
    confidence_threshold = serializers.FloatField(default=0.65, min_value=0.0, max_value=1.0)
    auto_create_high_confidence = serializers.BooleanField(default=True)
    
    def validate_participants(self, value):
        """Validate participant data structure"""
        required_fields = ['email']
        
        for i, participant in enumerate(value):
            for field in required_fields:
                if field not in participant or not participant[field]:
                    raise serializers.ValidationError(
                        f"Participant {i+1} is missing required field: {field}"
                    )
            
            # Validate email format
            email = participant['email']
            if '@' not in email or '.' not in email.split('@')[-1]:
                raise serializers.ValidationError(
                    f"Participant {i+1} has invalid email format: {email}"
                )
        
        return value


class MeetingParticipantAnalysisSerializer(serializers.Serializer):
    """Serializer for meeting-specific participant analysis"""
    
    meeting_id = serializers.UUIDField()
    participants = serializers.ListField(child=serializers.DictField(), min_length=1)
    use_linkedin_enhancement = serializers.BooleanField(default=False)
    auto_approve_high_confidence = serializers.BooleanField(default=True)
    send_verification_notifications = serializers.BooleanField(default=True)
    
    def validate_meeting_id(self, value):
        """Validate that meeting exists"""
        from apps.meetings.models import Meeting
        
        try:
            Meeting.objects.get(id=value)
        except Meeting.DoesNotExist:
            raise serializers.ValidationError("Meeting not found")
        
        return value