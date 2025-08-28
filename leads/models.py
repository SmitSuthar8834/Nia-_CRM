from django.db import models
from django.core.validators import EmailValidator
from django.utils import timezone


class Lead(models.Model):
    """
    Lead model representing prospects from Creatio CRM
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal'),
        ('negotiation', 'Negotiation'),
        ('closed_won', 'Closed Won'),
        ('closed_lost', 'Closed Lost'),
    ]
    
    crm_id = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(validators=[EmailValidator()], db_index=True)
    company = models.CharField(max_length=200, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new', db_index=True)
    source = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company']),
            models.Index(fields=['status']),
            models.Index(fields=['last_sync']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.company})"
    
    def clean(self):
        """Custom validation for Lead model"""
        from django.core.exceptions import ValidationError
        
        if not self.name.strip():
            raise ValidationError({'name': 'Name cannot be empty'})
        
        if not self.company.strip():
            raise ValidationError({'company': 'Company cannot be empty'})
        
        if self.phone and len(self.phone.strip()) < 10:
            raise ValidationError({'phone': 'Phone number must be at least 10 characters'})
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)