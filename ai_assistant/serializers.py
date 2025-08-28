from rest_framework import serializers
from .models import AISession, AIInteraction


class AISessionSerializer(serializers.ModelSerializer):
    """
    Serializer for AISession model
    """
    
    class Meta:
        model = AISession
        fields = [
            'id', 'session_id', 'meeting_id', 'lead_context',
            'conversation_history', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AIInteractionSerializer(serializers.ModelSerializer):
    """
    Serializer for AIInteraction model
    """
    
    class Meta:
        model = AIInteraction
        fields = [
            'id', 'interaction_type', 'input_data', 'output_data',
            'processing_time', 'success', 'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class AIInitializeSerializer(serializers.Serializer):
    """
    Serializer for AI session initialization
    """
    meeting_id = serializers.IntegerField()
    lead_context = serializers.JSONField(required=False, default=dict)


class AIQuestionSerializer(serializers.Serializer):
    """
    Serializer for AI question generation
    """
    session_id = serializers.CharField(max_length=100)
    conversation_context = serializers.CharField(max_length=5000)
    meeting_stage = serializers.CharField(max_length=50, required=False, default='general')


class AINotesSerializer(serializers.Serializer):
    """
    Serializer for AI note processing
    """
    session_id = serializers.CharField(max_length=100)
    meeting_notes = serializers.CharField(max_length=10000)
    extract_action_items = serializers.BooleanField(default=True)


class AISummarySerializer(serializers.Serializer):
    """
    Serializer for AI summary generation
    """
    session_id = serializers.CharField(max_length=100)
    meeting_transcript = serializers.CharField(max_length=20000)
    meeting_notes = serializers.CharField(max_length=10000, required=False, default='')