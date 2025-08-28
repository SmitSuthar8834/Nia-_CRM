"""
Debriefing Session Models for AI-Powered Meeting Intelligence
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class DebriefingSession(models.Model):
    """
    AI-powered debriefing sessions for meetings
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.OneToOneField('meetings.Meeting', on_delete=models.CASCADE, related_name='debriefing')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Scheduling
    scheduled_time = models.DateTimeField()
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Conversation Data
    conversation_data = models.JSONField(default=dict, help_text="Complete conversation history")
    current_question_index = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    
    # AI Processing Results
    extracted_data = models.JSONField(default=dict, help_text="Structured data extracted from conversation")
    confidence_scores = models.JSONField(default=dict, help_text="Confidence scores for extracted data")
    ai_insights = models.JSONField(default=dict, help_text="AI-generated insights and recommendations")
    
    # User Approval
    user_approved = models.BooleanField(default=False)
    approval_timestamp = models.DateTimeField(blank=True, null=True)
    user_feedback = models.JSONField(default=dict, help_text="User feedback on AI suggestions")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'debriefing_sessions'
        indexes = [
            models.Index(fields=['meeting']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['scheduled_time']),
            models.Index(fields=['status', 'scheduled_time']),
        ]
        ordering = ['-scheduled_time']

    def __str__(self):
        return f"Debriefing for {self.meeting.title} - {self.status}"

    @property
    def duration_minutes(self):
        """Calculate debriefing duration in minutes"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        return 0

    @property
    def is_overdue(self):
        """Check if debriefing is overdue"""
        if self.status == 'scheduled':
            return timezone.now() > self.scheduled_time + timezone.timedelta(hours=24)
        return False

    def start_session(self):
        """Start the debriefing session"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()

    def complete_session(self):
        """Complete the debriefing session"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class DebriefingQuestion(models.Model):
    """
    AI-generated questions for debriefing sessions
    """
    QUESTION_TYPE_CHOICES = [
        ('opening', 'Opening Question'),
        ('outcome', 'Meeting Outcome'),
        ('participants', 'Participants'),
        ('competitive', 'Competitive Intelligence'),
        ('technical', 'Technical Requirements'),
        ('timeline', 'Timeline & Next Steps'),
        ('budget', 'Budget Discussion'),
        ('decision_process', 'Decision Process'),
        ('objections', 'Objections & Concerns'),
        ('follow_up', 'Follow-up Actions'),
        ('closing', 'Closing Question'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(DebriefingSession, on_delete=models.CASCADE, related_name='questions')
    
    # Question Details
    question_text = models.TextField()
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPE_CHOICES)
    question_order = models.IntegerField()
    is_follow_up = models.BooleanField(default=False)
    parent_question = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True)
    
    # AI Context
    ai_context = models.JSONField(default=dict, help_text="Context used to generate this question")
    ai_prompt = models.TextField(blank=True, null=True)
    
    # Response
    user_response = models.TextField(blank=True, null=True)
    response_timestamp = models.DateTimeField(blank=True, null=True)
    
    # Processing
    processed = models.BooleanField(default=False)
    extracted_entities = models.JSONField(default=dict, help_text="Entities extracted from response")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'debriefing_questions'
        indexes = [
            models.Index(fields=['session', 'question_order']),
            models.Index(fields=['question_type']),
            models.Index(fields=['processed']),
        ]
        ordering = ['question_order']

    def __str__(self):
        return f"Q{self.question_order}: {self.question_text[:50]}..."

    def record_response(self, response_text):
        """Record user response to question"""
        self.user_response = response_text
        self.response_timestamp = timezone.now()
        self.save()


class DebriefingInsight(models.Model):
    """
    AI-generated insights from debriefing sessions
    """
    INSIGHT_TYPE_CHOICES = [
        ('opportunity', 'Opportunity Identified'),
        ('risk', 'Risk Identified'),
        ('next_action', 'Recommended Next Action'),
        ('competitive_threat', 'Competitive Threat'),
        ('buying_signal', 'Buying Signal'),
        ('objection', 'Objection Identified'),
        ('requirement', 'Requirement Captured'),
        ('timeline_change', 'Timeline Change'),
        ('budget_info', 'Budget Information'),
        ('decision_maker', 'Decision Maker Identified'),
    ]
    
    CONFIDENCE_LEVEL_CHOICES = [
        ('low', 'Low Confidence'),
        ('medium', 'Medium Confidence'),
        ('high', 'High Confidence'),
        ('very_high', 'Very High Confidence'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(DebriefingSession, on_delete=models.CASCADE, related_name='insights')
    
    # Insight Details
    insight_type = models.CharField(max_length=50, choices=INSIGHT_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVEL_CHOICES)
    confidence_score = models.FloatField(help_text="Numerical confidence score (0-1)")
    
    # Source Information
    source_question = models.ForeignKey(DebriefingQuestion, on_delete=models.CASCADE, blank=True, null=True)
    source_text = models.TextField(blank=True, null=True, help_text="Text that generated this insight")
    
    # Action Items
    suggested_actions = models.JSONField(default=list, help_text="AI-suggested actions based on this insight")
    priority = models.CharField(max_length=20, default='medium')
    
    # User Feedback
    user_validated = models.BooleanField(default=False)
    user_feedback = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'debriefing_insights'
        indexes = [
            models.Index(fields=['session', 'insight_type']),
            models.Index(fields=['confidence_level']),
            models.Index(fields=['user_validated']),
        ]
        ordering = ['-confidence_score', '-created_at']

    def __str__(self):
        return f"{self.insight_type}: {self.title}"


class DebriefingTemplate(models.Model):
    """
    Templates for different types of debriefing sessions
    """
    TEMPLATE_TYPE_CHOICES = [
        ('discovery', 'Discovery Call'),
        ('demo', 'Product Demo'),
        ('negotiation', 'Negotiation'),
        ('follow_up', 'Follow-up'),
        ('closing', 'Closing Meeting'),
        ('general', 'General Meeting'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    
    # Template Configuration
    question_templates = models.JSONField(default=list, help_text="List of question templates")
    ai_prompts = models.JSONField(default=dict, help_text="AI prompts for different question types")
    extraction_rules = models.JSONField(default=dict, help_text="Rules for data extraction")
    
    # Usage
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'debriefing_templates'
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['created_by']),
        ]
        ordering = ['template_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.template_type})"

    def increment_usage(self):
        """Increment usage counter"""
        self.usage_count += 1
        self.save(update_fields=['usage_count'])