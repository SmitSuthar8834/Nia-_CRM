"""
Lead Management Models for Meeting Intelligence
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Lead(models.Model):
    """
    Enhanced Lead model with meeting intelligence features
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('opportunity', 'Opportunity'),
        ('customer', 'Customer'),
        ('lost', 'Lost'),
        ('disqualified', 'Disqualified'),
    ]
    
    SOURCE_CHOICES = [
        ('meeting', 'Meeting Detection'),
        ('calendar', 'Calendar Import'),
        ('manual', 'Manual Entry'),
        ('crm_sync', 'CRM Sync'),
        ('email', 'Email'),
        ('web', 'Website'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ]
    
    RELATIONSHIP_STAGE_CHOICES = [
        ('cold', 'Cold'),
        ('warm', 'Warm'),
        ('hot', 'Hot'),
        ('engaged', 'Engaged'),
        ('negotiating', 'Negotiating'),
        ('closing', 'Closing'),
    ]
    
    DECISION_AUTHORITY_CHOICES = [
        ('decision_maker', 'Decision Maker'),
        ('influencer', 'Influencer'),
        ('user', 'End User'),
        ('gatekeeper', 'Gatekeeper'),
        ('champion', 'Champion'),
        ('unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # CRM Integration
    creatio_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    external_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    
    # Company Information
    company = models.CharField(max_length=200)
    title = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.CharField(max_length=50, blank=True, null=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    
    # Lead Management
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES, default='meeting')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    qualification_score = models.IntegerField(default=0, help_text="Lead qualification score (0-100)")
    
    # Meeting Intelligence Fields
    last_meeting_date = models.DateTimeField(blank=True, null=True)
    meeting_count = models.IntegerField(default=0)
    relationship_stage = models.CharField(max_length=50, choices=RELATIONSHIP_STAGE_CHOICES, blank=True, null=True)
    decision_authority = models.CharField(max_length=50, choices=DECISION_AUTHORITY_CHOICES, default='unknown')
    
    # Sales Information
    estimated_budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    estimated_close_date = models.DateField(blank=True, null=True)
    probability = models.IntegerField(default=0, help_text="Win probability (0-100)")
    
    # Assignment
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='assigned_leads')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'leads'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company', 'last_name']),
            models.Index(fields=['status', 'assigned_to']),
            models.Index(fields=['last_meeting_date']),
            models.Index(fields=['qualification_score']),
            models.Index(fields=['creatio_id']),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.company}"

    @property
    def full_name(self):
        """Get full name of the lead"""
        return f"{self.first_name} {self.last_name}"

    @property
    def days_since_last_meeting(self):
        """Calculate days since last meeting"""
        if self.last_meeting_date:
            return (timezone.now() - self.last_meeting_date).days
        return None

    def update_meeting_stats(self):
        """Update meeting-related statistics"""
        from apps.meetings.models import MeetingParticipant
        
        participants = MeetingParticipant.objects.filter(matched_lead=self)
        self.meeting_count = participants.count()
        
        if participants.exists():
            latest_meeting = participants.select_related('meeting').order_by('-meeting__start_time').first()
            self.last_meeting_date = latest_meeting.meeting.start_time
        
        self.save()


class LeadNote(models.Model):
    """
    Notes and interactions for leads
    """
    NOTE_TYPE_CHOICES = [
        ('call', 'Phone Call'),
        ('email', 'Email'),
        ('meeting', 'Meeting'),
        ('general', 'General Note'),
        ('ai_insight', 'AI Insight'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Note Content
    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    note_type = models.CharField(max_length=20, choices=NOTE_TYPE_CHOICES, default='general')
    
    # AI Processing
    ai_generated = models.BooleanField(default=False)
    ai_confidence = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lead_notes'
        indexes = [
            models.Index(fields=['lead', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['note_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Note for {self.lead.full_name} by {self.author.username}"


class CompetitiveIntelligence(models.Model):
    """
    Competitive intelligence captured from meetings
    """
    THREAT_LEVEL_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    RELATIONSHIP_STATUS_CHOICES = [
        ('incumbent', 'Incumbent Vendor'),
        ('evaluating', 'Under Evaluation'),
        ('rejected', 'Rejected'),
        ('unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='competitive_intel')
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.CASCADE, blank=True, null=True)
    
    # Competitor Information
    competitor_name = models.CharField(max_length=200)
    competitive_context = models.TextField()
    strengths_mentioned = models.JSONField(default=list, blank=True)
    weaknesses_mentioned = models.JSONField(default=list, blank=True)
    pricing_intelligence = models.JSONField(default=dict, blank=True)
    
    # Relationship and Threat Assessment
    relationship_status = models.CharField(max_length=50, choices=RELATIONSHIP_STATUS_CHOICES, default='unknown')
    threat_level = models.CharField(max_length=20, choices=THREAT_LEVEL_CHOICES, default='medium')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'competitive_intelligence'
        indexes = [
            models.Index(fields=['lead', 'competitor_name']),
            models.Index(fields=['threat_level']),
            models.Index(fields=['relationship_status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.competitor_name} vs {self.lead.company}"


class ActionItem(models.Model):
    """
    Action items and commitments from meetings
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey('meetings.Meeting', on_delete=models.CASCADE, related_name='action_items')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='action_items', blank=True, null=True)
    
    # Action Item Details
    description = models.TextField()
    owner = models.CharField(max_length=200, help_text="Can be internal user or external contact")
    owner_user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Commitment Tracking
    is_commitment = models.BooleanField(default=False, help_text="True if this is a commitment made to customer")
    is_internal = models.BooleanField(default=True, help_text="True if owner is internal team member")
    
    # Completion Tracking
    completed_at = models.DateTimeField(blank=True, null=True)
    completion_notes = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'action_items'
        indexes = [
            models.Index(fields=['meeting', 'status']),
            models.Index(fields=['owner_user', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['priority', 'status']),
        ]
        ordering = ['due_date', '-priority']

    def __str__(self):
        return f"{self.description[:50]}... - {self.owner}"

    @property
    def is_overdue(self):
        """Check if action item is overdue"""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return self.due_date < timezone.now().date()
        return False

    def mark_completed(self, notes=None):
        """Mark action item as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if notes:
            self.completion_notes = notes
        self.save()