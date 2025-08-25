"""
AI Engine Models for Gemini Integration
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AIPromptTemplate(models.Model):
    """
    Templates for AI prompts used in different contexts
    """
    TEMPLATE_TYPE_CHOICES = [
        ('debriefing_question', 'Debriefing Question'),
        ('data_extraction', 'Data Extraction'),
        ('insight_generation', 'Insight Generation'),
        ('meeting_classification', 'Meeting Classification'),
        ('participant_matching', 'Participant Matching'),
        ('competitive_analysis', 'Competitive Analysis'),
    ]
    
    CONTEXT_CHOICES = [
        ('discovery', 'Discovery Call'),
        ('demo', 'Product Demo'),
        ('negotiation', 'Negotiation'),
        ('follow_up', 'Follow-up'),
        ('closing', 'Closing Meeting'),
        ('general', 'General'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Template Information
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES)
    context = models.CharField(max_length=50, choices=CONTEXT_CHOICES, default='general')
    
    # Prompt Content
    prompt_template = models.TextField(help_text="Template with placeholders like {meeting_type}, {participants}")
    system_prompt = models.TextField(blank=True, null=True, help_text="System prompt for AI context")
    
    # Configuration
    temperature = models.FloatField(default=0.7, help_text="AI temperature setting (0-1)")
    max_tokens = models.IntegerField(default=1000, help_text="Maximum tokens for response")
    
    # Usage and Performance
    usage_count = models.IntegerField(default=0)
    average_response_time = models.FloatField(default=0.0, help_text="Average response time in seconds")
    success_rate = models.FloatField(default=0.0, help_text="Success rate (0-1)")
    
    # Status
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=20, default='1.0')
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_prompt_templates'
        indexes = [
            models.Index(fields=['template_type', 'context', 'is_active']),
            models.Index(fields=['usage_count']),
        ]
        ordering = ['template_type', 'context', 'name']

    def __str__(self):
        return f"{self.name} ({self.template_type})"

    def increment_usage(self, response_time=None):
        """Increment usage counter and update performance metrics"""
        self.usage_count += 1
        if response_time:
            # Update average response time
            if self.average_response_time == 0:
                self.average_response_time = response_time
            else:
                self.average_response_time = (self.average_response_time + response_time) / 2
        self.save(update_fields=['usage_count', 'average_response_time'])


class AIInteraction(models.Model):
    """
    Log all AI interactions for monitoring and improvement
    """
    INTERACTION_TYPE_CHOICES = [
        ('question_generation', 'Question Generation'),
        ('data_extraction', 'Data Extraction'),
        ('insight_generation', 'Insight Generation'),
        ('classification', 'Classification'),
        ('analysis', 'Analysis'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Interaction Details
    interaction_type = models.CharField(max_length=50, choices=INTERACTION_TYPE_CHOICES)
    prompt_template = models.ForeignKey(AIPromptTemplate, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Request Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)
    input_data = models.JSONField(help_text="Input data sent to AI")
    formatted_prompt = models.TextField(help_text="Final formatted prompt sent to AI")
    
    # Response Information
    ai_response = models.TextField(blank=True, null=True)
    parsed_response = models.JSONField(blank=True, null=True, help_text="Structured response data")
    confidence_score = models.FloatField(blank=True, null=True, help_text="AI confidence score (0-1)")
    
    # Performance Metrics
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    response_time_ms = models.IntegerField(blank=True, null=True)
    token_count = models.IntegerField(blank=True, null=True)
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    
    # Error Handling
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Context
    entity_type = models.CharField(max_length=50, blank=True, null=True)
    entity_id = models.UUIDField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'ai_interactions'
        indexes = [
            models.Index(fields=['interaction_type', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.interaction_type} - {self.status} - {self.created_at}"

    def mark_success(self, response, parsed_data=None, confidence=None, tokens=None):
        """Mark interaction as successful"""
        self.status = 'success'
        self.ai_response = response
        self.parsed_response = parsed_data
        self.confidence_score = confidence
        self.token_count = tokens
        self.completed_at = timezone.now()
        
        if self.created_at:
            self.response_time_ms = int((self.completed_at - self.created_at).total_seconds() * 1000)
        
        self.save()

    def mark_error(self, error_message):
        """Mark interaction as failed"""
        self.status = 'error'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()


class AICache(models.Model):
    """
    Cache AI responses to reduce API calls and costs
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Cache Key
    prompt_hash = models.CharField(max_length=64, unique=True, help_text="SHA-256 hash of the prompt")
    interaction_type = models.CharField(max_length=50)
    
    # Cached Data
    cached_response = models.TextField()
    cached_parsed_data = models.JSONField(blank=True, null=True)
    confidence_score = models.FloatField(blank=True, null=True)
    
    # Cache Metadata
    hit_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Original Request Info
    original_prompt = models.TextField()
    template_used = models.ForeignKey(AIPromptTemplate, on_delete=models.SET_NULL, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_cache'
        indexes = [
            models.Index(fields=['prompt_hash']),
            models.Index(fields=['interaction_type']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['last_accessed']),
        ]

    def __str__(self):
        return f"Cache: {self.interaction_type} - {self.hit_count} hits"

    def increment_hit(self):
        """Increment cache hit counter"""
        self.hit_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['hit_count', 'last_accessed'])

    @property
    def is_expired(self):
        """Check if cache entry is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class AIFeedback(models.Model):
    """
    User feedback on AI responses for continuous improvement
    """
    FEEDBACK_TYPE_CHOICES = [
        ('accuracy', 'Accuracy'),
        ('relevance', 'Relevance'),
        ('completeness', 'Completeness'),
        ('usefulness', 'Usefulness'),
    ]
    
    RATING_CHOICES = [
        (1, 'Very Poor'),
        (2, 'Poor'),
        (3, 'Average'),
        (4, 'Good'),
        (5, 'Excellent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interaction = models.ForeignKey(AIInteraction, on_delete=models.CASCADE, related_name='feedback')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Feedback Details
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPE_CHOICES)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comments = models.TextField(blank=True, null=True)
    
    # Improvement Suggestions
    suggested_response = models.TextField(blank=True, null=True)
    improvement_notes = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_feedback'
        unique_together = ['interaction', 'user', 'feedback_type']
        indexes = [
            models.Index(fields=['interaction']),
            models.Index(fields=['feedback_type', 'rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.feedback_type}: {self.rating}/5 - {self.interaction.interaction_type}"