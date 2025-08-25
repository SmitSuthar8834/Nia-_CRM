"""
CRM Synchronization Serializers
"""
from rest_framework import serializers
from .models import CreatioSync, SyncConflict, SyncLog, CreatioConfiguration


class CreatioSyncSerializer(serializers.ModelSerializer):
    """
    Serializer for CreatioSync model
    """
    needs_retry = serializers.ReadOnlyField()
    
    class Meta:
        model = CreatioSync
        fields = [
            'id', 'entity_type', 'local_id', 'creatio_id',
            'sync_status', 'sync_direction', 'last_sync', 'next_sync',
            'error_message', 'retry_count', 'max_retries', 'needs_retry',
            'local_data_hash', 'creatio_data_hash',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'needs_retry'
        ]


class SyncConflictSerializer(serializers.ModelSerializer):
    """
    Serializer for SyncConflict model
    """
    sync_record = CreatioSyncSerializer(read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True)
    
    class Meta:
        model = SyncConflict
        fields = [
            'id', 'sync_record', 'conflict_type', 'field_name',
            'local_value', 'creatio_value', 'resolution_status',
            'resolved_value', 'resolved_by', 'resolved_by_username',
            'resolved_at', 'resolution_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'sync_record', 'resolved_by', 'resolved_by_username',
            'resolved_at', 'created_at', 'updated_at'
        ]


class SyncLogSerializer(serializers.ModelSerializer):
    """
    Serializer for SyncLog model
    """
    sync_record = CreatioSyncSerializer(read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = SyncLog
        fields = [
            'id', 'sync_record', 'log_level', 'operation_type', 'message',
            'entity_type', 'entity_id', 'user', 'user_username',
            'request_data', 'response_data', 'execution_time_ms', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'user_username']


class CreatioConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for CreatioConfiguration model
    """
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = CreatioConfiguration
        fields = [
            'id', 'config_type', 'config_key', 'config_value', 'description',
            'is_active', 'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_username', 'created_at', 'updated_at'
        ]


class SyncRequestSerializer(serializers.Serializer):
    """
    Serializer for sync request parameters
    """
    force = serializers.BooleanField(default=False, help_text="Force sync even if no changes detected")
    async_execution = serializers.BooleanField(default=True, help_text="Execute synchronization asynchronously")
    
    def validate(self, data):
        return data


class LeadSyncRequestSerializer(serializers.Serializer):
    """
    Serializer for lead sync request
    """
    lead_id = serializers.UUIDField(required=True)
    direction = serializers.ChoiceField(
        choices=['to_creatio', 'from_creatio', 'bidirectional'],
        default='bidirectional'
    )
    async_execution = serializers.BooleanField(default=True)
    
    def validate(self, data):
        return data


class ConflictResolutionSerializer(serializers.Serializer):
    """
    Serializer for conflict resolution
    """
    RESOLUTION_CHOICES = [
        ('local_wins', 'Use Local Value'),
        ('creatio_wins', 'Use Creatio Value'),
        ('manual', 'Manual Resolution'),
        ('ignore', 'Ignore Conflict')
    ]
    
    conflict_id = serializers.UUIDField(required=True)
    resolution = serializers.ChoiceField(choices=RESOLUTION_CHOICES, required=True)
    resolved_value = serializers.JSONField(required=False, allow_null=True)
    resolution_notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        if data['resolution'] == 'manual' and 'resolved_value' not in data:
            raise serializers.ValidationError(
                "resolved_value is required for manual resolution"
            )
        return data


class MeetingActivityRequestSerializer(serializers.Serializer):
    """
    Serializer for creating meeting activity in Creatio
    """
    meeting_id = serializers.UUIDField(required=True)
    
    def validate(self, data):
        return data


class UpdateLeadFromMeetingSerializer(serializers.Serializer):
    """
    Serializer for updating lead with meeting data
    """
    lead_id = serializers.UUIDField(required=True)
    meeting_data = serializers.JSONField(required=True)
    
    def validate_meeting_data(self, value):
        """
        Validate meeting data structure
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("meeting_data must be a dictionary")
        
        # Optional validation for expected fields
        allowed_fields = [
            'qualification_insights', 'meeting_type', 'estimated_close_date',
            'estimated_budget', 'relationship_stage', 'decision_authority'
        ]
        
        for key in value.keys():
            if key not in allowed_fields:
                raise serializers.ValidationError(f"Unexpected field in meeting_data: {key}")
        
        return value


class SyncStatusSerializer(serializers.Serializer):
    """
    Serializer for sync status response
    """
    sync_status = serializers.DictField(child=serializers.IntegerField())
    conflicts = serializers.DictField(child=serializers.IntegerField())
    last_sync = CreatioSyncSerializer(allow_null=True)
    
    def to_representation(self, instance):
        return instance


class BulkSyncRequestSerializer(serializers.Serializer):
    """
    Serializer for bulk sync operations
    """
    entity_type = serializers.ChoiceField(
        choices=['lead', 'contact', 'activity', 'opportunity'],
        required=True
    )
    entity_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=100,
        required=True
    )
    direction = serializers.ChoiceField(
        choices=['to_creatio', 'from_creatio', 'bidirectional'],
        default='bidirectional'
    )
    async_execution = serializers.BooleanField(default=True)
    
    def validate(self, data):
        return data


class FieldMappingSerializer(serializers.Serializer):
    """
    Serializer for field mapping configuration
    """
    local_field = serializers.CharField(max_length=100)
    creatio_field = serializers.CharField(max_length=100)
    field_type = serializers.ChoiceField(
        choices=['string', 'integer', 'float', 'boolean', 'date', 'datetime'],
        default='string'
    )
    is_required = serializers.BooleanField(default=False)
    default_value = serializers.JSONField(required=False, allow_null=True)
    
    def validate(self, data):
        return data


class SyncScheduleSerializer(serializers.Serializer):
    """
    Serializer for sync schedule configuration
    """
    entity_type = serializers.ChoiceField(
        choices=['lead', 'contact', 'activity', 'opportunity'],
        required=True
    )
    sync_interval_minutes = serializers.IntegerField(min_value=1, max_value=1440)  # 1 minute to 24 hours
    is_active = serializers.BooleanField(default=True)
    sync_direction = serializers.ChoiceField(
        choices=['to_creatio', 'from_creatio', 'bidirectional'],
        default='bidirectional'
    )
    
    def validate(self, data):
        return data