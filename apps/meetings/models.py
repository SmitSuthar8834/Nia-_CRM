"""
Meeting Intelligence Models
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Meeting(models.Model):
    """
    Core meeting model with calendar integration and intelligence features
    """
    MEETING_TYPE_CHOICES = [
        ('discovery', 'Discovery Call'),
        ('demo', 'Product Demo'),
        ('negotiation', 'Negotiation'),
        ('follow_up', 'Follow-up'),
        ('closing', 'Closing Meeting'),
        ('internal', 'Internal Meeting'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    calendar_event_id = models.CharField(max_length=200, unique=True)
    calendar_provider = models.CharField(max_length=50, default='google')  # google, outlook, exchange
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    timezone = models.CharField(max_length=50, default='UTC')
    location = models.CharField(max_length=200, blank=True, null=True)
    meeting_url = models.URLField(blank=True, null=True)
    
    # Meeting Intelligence Fields
    meeting_type = models.CharField(max_length=50, choices=MEETING_TYPE_CHOICES, default='other')
    is_sales_meeting = models.BooleanField(default=False)
    confidence_score = models.FloatField(default=0.0, help_text="AI confidence that this is a sales meeting (0-1)")
    
    # Meeting Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_meetings')
    
    # Debriefing Status
    debriefing_scheduled = models.BooleanField(default=False)
    debriefing_completed = models.BooleanField(default=False)
    debriefing_due_at = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'meetings'
        indexes = [
            models.Index(fields=['start_time', 'organizer']),
            models.Index(fields=['is_sales_meeting', 'meeting_type']),
            models.Index(fields=['calendar_event_id']),
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['debriefing_scheduled', 'debriefing_completed']),
        ]
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    @property
    def duration_minutes(self):
        """Calculate meeting duration in minutes"""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return 0

    @property
    def is_past(self):
        """Check if meeting is in the past"""
        return self.end_time < timezone.now()

    def schedule_debriefing(self):
        """Schedule debriefing session 30 minutes after meeting ends"""
        if not self.debriefing_scheduled and self.is_sales_meeting:
            self.debriefing_due_at = self.end_time + timezone.timedelta(minutes=30)
            self.debriefing_scheduled = True
            self.save()


class MeetingParticipant(models.Model):
    """
    Meeting participants with lead matching capabilities
    """
    PARTICIPANT_TYPE_CHOICES = [
        ('organizer', 'Organizer'),
        ('required', 'Required Attendee'),
        ('optional', 'Optional Attendee'),
        ('resource', 'Resource'),
    ]
    
    RESPONSE_STATUS_CHOICES = [
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('tentative', 'Tentative'),
        ('no_response', 'No Response'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='participants')
    
    # Participant Information
    email = models.EmailField()
    name = models.CharField(max_length=200, blank=True, null=True)
    company = models.CharField(max_length=200, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Meeting Participation
    participant_type = models.CharField(max_length=20, choices=PARTICIPANT_TYPE_CHOICES, default='required')
    response_status = models.CharField(max_length=20, choices=RESPONSE_STATUS_CHOICES, default='no_response')
    is_external = models.BooleanField(default=True)
    
    # Lead Matching
    matched_lead = models.ForeignKey('leads.Lead', on_delete=models.SET_NULL, blank=True, null=True)
    match_confidence = models.FloatField(default=0.0, help_text="Confidence score for lead matching (0-1)")
    match_method = models.CharField(max_length=50, blank=True, null=True)  # email, name_company, domain, etc.
    manual_verification_required = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'meeting_participants'
        unique_together = ['meeting', 'email']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company', 'name']),
            models.Index(fields=['matched_lead']),
            models.Index(fields=['is_external', 'match_confidence']),
        ]

    def __str__(self):
        return f"{self.name or self.email} - {self.meeting.title}"

    @property
    def display_name(self):
        """Get display name for participant"""
        if self.name:
            return self.name
        return self.email.split('@')[0].replace('.', ' ').title()


class MeetingNote(models.Model):
    """
    Meeting notes and outcomes
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Note Content
    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    note_type = models.CharField(max_length=50, default='general')  # general, outcome, action_item, etc.
    
    # AI Processing
    ai_generated = models.BooleanField(default=False)
    ai_confidence = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'meeting_notes'
        indexes = [
            models.Index(fields=['meeting', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['note_type']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Note for {self.meeting.title} by {self.author.username}"