from django.db import models
from django.utils import timezone
from leads.models import Lead


class Meeting(models.Model):
    """
    Meeting model representing calendar events matched to leads
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    calendar_event_id = models.CharField(max_length=200, unique=True, db_index=True)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=300)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    attendees = models.JSONField(default=list)
    match_confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='scheduled', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['match_confidence']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def clean(self):
        """Custom validation for Meeting model"""
        from django.core.exceptions import ValidationError
        
        if self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time'})
        
        if self.match_confidence is not None and (self.match_confidence < 0 or self.match_confidence > 1):
            raise ValidationError({'match_confidence': 'Match confidence must be between 0 and 1'})


class MeetingSession(models.Model):
    """
    Meeting session model for AI-powered meeting data
    """
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE)
    ai_session_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    notes_version = models.IntegerField(default=0)  # For conflict resolution
    transcript = models.TextField(blank=True)
    action_items = models.JSONField(default=list)
    summary = models.TextField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"Session for {self.meeting.title}"
    
    @property
    def is_active(self):
        """Check if meeting session is currently active"""
        return self.ended_at is None
    
    @property
    def duration(self):
        """Calculate session duration"""
        if self.ended_at:
            return self.ended_at - self.started_at
        return timezone.now() - self.started_at


class ActionItem(models.Model):
    """
    Action item model for tasks extracted from meetings
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    meeting_session = models.ForeignKey(MeetingSession, on_delete=models.CASCADE)
    description = models.TextField()
    assignee = models.CharField(max_length=200, blank=True)
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    confidence = models.FloatField(default=0.0)
    source_text = models.TextField(blank=True)
    crm_task_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['due_date', '-created_at']
        indexes = [
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"{self.description[:50]}... - {self.assignee or 'Unassigned'}"
    
    def clean(self):
        """Custom validation for ActionItem model"""
        from django.core.exceptions import ValidationError
        
        if not self.description.strip():
            raise ValidationError({'description': 'Description cannot be empty'})
        
        if self.confidence < 0 or self.confidence > 1:
            raise ValidationError({'confidence': 'Confidence must be between 0 and 1'})


class CallBotSession(models.Model):
    """
    Call bot session model for video call participation
    """
    STATUS_CHOICES = [
        ('connecting', 'Connecting'),
        ('connected', 'Connected'),
        ('transcribing', 'Transcribing'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
    ]
    
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE)
    bot_session_id = models.CharField(max_length=100, unique=True)
    platform = models.CharField(max_length=50)  # 'meet', 'teams', 'zoom'
    join_time = models.DateTimeField()
    leave_time = models.DateTimeField(null=True, blank=True)
    connection_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='connecting')
    raw_transcript = models.TextField(blank=True)
    speaker_mapping = models.JSONField(default=dict)
    audio_quality = models.CharField(max_length=20, default='good')
    error_count = models.IntegerField(default=0)
    
    class Meta:
        indexes = [
            models.Index(fields=['join_time']),
            models.Index(fields=['connection_status']),
            models.Index(fields=['platform']),
        ]
    
    def __str__(self):
        return f"Bot session for {self.meeting.title}"
    
    @property
    def is_active(self):
        """Check if bot session is currently active"""
        return self.connection_status in ['connecting', 'connected', 'transcribing']
    
    @property
    def duration(self):
        """Calculate session duration"""
        if self.leave_time:
            return self.leave_time - self.join_time
        return timezone.now() - self.join_time


class DraftSummary(models.Model):
    """
    AI-generated draft summary model
    """
    CRM_SYSTEM_CHOICES = [
        ('salesforce', 'Salesforce'),
        ('hubspot', 'HubSpot'),
        ('creatio', 'Creatio'),
        ('sap_c4c', 'SAP C4C'),
    ]
    
    bot_session = models.OneToOneField(CallBotSession, on_delete=models.CASCADE)
    ai_generated_summary = models.TextField()
    key_points = models.JSONField(default=list)
    extracted_action_items = models.JSONField(default=list)
    suggested_next_steps = models.JSONField(default=list)
    decisions_made = models.JSONField(default=list)
    suggested_crm_updates = models.JSONField(default=dict)
    confidence_score = models.FloatField()
    processing_time = models.FloatField(null=True, blank=True)  # seconds
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['confidence_score']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Draft summary for {self.bot_session.meeting.title}"
    
    def clean(self):
        """Custom validation for DraftSummary model"""
        from django.core.exceptions import ValidationError
        
        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValidationError({'confidence_score': 'Confidence score must be between 0 and 1'})
    
    def format_for_crm(self, crm_system: str) -> dict:
        """Format summary data for specific CRM system"""
        base_data = {
            'summary': self.ai_generated_summary,
            'key_points': self.key_points,
            'action_items': self.extracted_action_items,
            'next_steps': self.suggested_next_steps,
            'decisions': self.decisions_made
        }
        
        if crm_system == 'salesforce':
            return {
                'Description': self.ai_generated_summary,
                'Key_Points__c': '\n'.join(f"• {point}" for point in self.key_points),
                'Action_Items__c': '\n'.join(f"• {item.get('description', '')}" for item in self.extracted_action_items),
                'Next_Steps__c': '\n'.join(f"• {step}" for step in self.suggested_next_steps),
                'Decisions_Made__c': '\n'.join(f"• {decision}" for decision in self.decisions_made)
            }
        elif crm_system == 'hubspot':
            return {
                'hs_meeting_body': self.ai_generated_summary,
                'hs_meeting_outcome': 'COMPLETED',
                'hs_meeting_notes': '\n'.join(f"• {point}" for point in self.key_points),
                'hs_activity_type': 'MEETING',
                'custom_key_points': self.key_points,
                'custom_action_items': self.extracted_action_items,
                'custom_next_steps': self.suggested_next_steps,
                'custom_decisions': self.decisions_made
            }
        elif crm_system == 'creatio':
            return {
                'Notes': self.ai_generated_summary,
                'KeyPoints': self.key_points,
                'ActionItems': self.extracted_action_items,
                'NextSteps': self.suggested_next_steps,
                'Decisions': self.decisions_made
            }
        
        return base_data


class ValidationSession(models.Model):
    """
    Post-call validation session model for rep interaction
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]
    
    draft_summary = models.OneToOneField(DraftSummary, on_delete=models.CASCADE)
    sales_rep_email = models.EmailField()
    validation_questions = models.JSONField(default=list)
    rep_responses = models.JSONField(default=dict)
    validated_summary = models.TextField(blank=True)
    approved_crm_updates = models.JSONField(default=dict)
    validation_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    changes_made = models.JSONField(default=list)  # Audit trail
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()  # Auto-expire after 24 hours
    
    class Meta:
        indexes = [
            models.Index(fields=['validation_status']),
            models.Index(fields=['sales_rep_email']),
            models.Index(fields=['started_at']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Validation session for {self.draft_summary.bot_session.meeting.title}"
    
    @property
    def is_expired(self):
        """Check if validation session has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def time_remaining(self):
        """Calculate time remaining before expiration"""
        from django.utils import timezone
        if self.is_expired:
            return None
        return self.expires_at - timezone.now()
    
    def clean(self):
        """Custom validation for ValidationSession model"""
        from django.core.exceptions import ValidationError
        
        if self.completed_at and self.completed_at <= self.started_at:
            raise ValidationError({'completed_at': 'Completion time must be after start time'})
        
        if self.expires_at <= self.started_at:
            raise ValidationError({'expires_at': 'Expiration time must be after start time'})


class CRMSyncRecord(models.Model):
    """
    CRM synchronization record model
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    CRM_SYSTEM_CHOICES = [
        ('salesforce', 'Salesforce'),
        ('hubspot', 'HubSpot'),
        ('creatio', 'Creatio'),
        ('sap_c4c', 'SAP C4C'),
    ]
    
    validation_session = models.ForeignKey(ValidationSession, on_delete=models.CASCADE)
    crm_system = models.CharField(max_length=50, choices=CRM_SYSTEM_CHOICES)
    sync_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    crm_record_id = models.CharField(max_length=200, blank=True)
    sync_payload = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['crm_system', 'sync_status']),
            models.Index(fields=['sync_status']),
            models.Index(fields=['created_at']),
        ]
        unique_together = ['validation_session', 'crm_system']
    
    def __str__(self):
        return f"CRM sync to {self.crm_system} - {self.sync_status}"


class DraftEmail(models.Model):
    """
    Draft email model for follow-up emails after meetings
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    EMAIL_TYPE_CHOICES = [
        ('follow_up', 'Follow-up'),
        ('thank_you', 'Thank You'),
        ('next_steps', 'Next Steps'),
        ('meeting_summary', 'Meeting Summary'),
        ('action_items', 'Action Items'),
    ]
    
    validation_session = models.ForeignKey(ValidationSession, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=50, choices=EMAIL_TYPE_CHOICES, default='follow_up')
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=200, blank=True)
    cc_emails = models.JSONField(default=list)
    bcc_emails = models.JSONField(default=list)
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')
    approval_requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.EmailField(blank=True)
    rejection_reason = models.TextField(blank=True)
    scheduled_send_time = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['email_type']),
            models.Index(fields=['scheduled_send_time']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.email_type} email to {self.recipient_email} - {self.status}"
    
    @property
    def is_pending_approval(self):
        """Check if email is pending approval"""
        return self.status == 'pending_approval'
    
    @property
    def is_scheduled(self):
        """Check if email is scheduled for future sending"""
        return self.status == 'scheduled' and self.scheduled_send_time
    
    def clean(self):
        """Custom validation for DraftEmail model"""
        from django.core.exceptions import ValidationError
        
        if not self.subject.strip():
            raise ValidationError({'subject': 'Subject cannot be empty'})
        
        if not self.body_html.strip():
            raise ValidationError({'body_html': 'Email body cannot be empty'})
        
        if self.scheduled_send_time and self.scheduled_send_time <= timezone.now():
            raise ValidationError({'scheduled_send_time': 'Scheduled send time must be in the future'})


class EmailApproval(models.Model):
    """
    Email approval model for tracking approval workflow
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    draft_email = models.OneToOneField(DraftEmail, on_delete=models.CASCADE)
    approver_email = models.EmailField()
    approval_token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['approver_email']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Email approval for {self.draft_email.subject} - {self.status}"
    
    @property
    def is_expired(self):
        """Check if approval request has expired"""
        return timezone.now() > self.expires_at
    
    def clean(self):
        """Custom validation for EmailApproval model"""
        from django.core.exceptions import ValidationError
        
        if self.expires_at <= timezone.now():
            raise ValidationError({'expires_at': 'Expiration time must be in the future'})