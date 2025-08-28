from django.db import models
from django.utils import timezone


class AISession(models.Model):
    """
    AI session model for tracking AI assistant interactions
    """
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    meeting_id = models.IntegerField(db_index=True)
    lead_context = models.JSONField(default=dict)
    conversation_history = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['meeting_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"AI Session {self.session_id} - Meeting {self.meeting_id}"


class AIInteraction(models.Model):
    """
    AI interaction model for logging AI requests and responses
    """
    INTERACTION_TYPES = [
        ('question_suggestion', 'Question Suggestion'),
        ('note_processing', 'Note Processing'),
        ('action_extraction', 'Action Item Extraction'),
        ('summary_generation', 'Summary Generation'),
    ]
    
    session = models.ForeignKey(AISession, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPES)
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['interaction_type']),
            models.Index(fields=['success']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.interaction_type} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"