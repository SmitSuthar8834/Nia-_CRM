"""
Tests for CRM suggestion API endpoints
"""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from meetings.models import Meeting, CallBotSession, DraftSummary
from leads.models import Lead
from datetime import datetime, timedelta


class CRMSuggestionAPITest(TestCase):
    """Test cases for CRM suggestion API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id='TEST_LEAD_001',
            name='John Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='qualified'
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            calendar_event_id='test_event_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            attendees=['john.doe@example.com', 'sales@company.com'],
            status='completed'
        )
        
        # Create test bot session
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id='bot_session_123',
            platform='meet',
            join_time=datetime.now(),
            connection_status='connected',
            raw_transcript='Test transcript content'
        )
        
        # Create test draft summary
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary='Great meeting with John from Test Company. Discussed budget and timeline.',
            key_points=['Budget confirmed at $50k', 'Timeline: end of Q1', 'Decision maker identified'],
            extracted_action_items=[
                {'description': 'Send proposal by Friday', 'assignee': 'sales_rep', 'priority': 'high'},
                {'description': 'Schedule follow-up call', 'assignee': 'sales_rep', 'priority': 'medium'}
            ],
            suggested_next_steps=['Send detailed proposal', 'Schedule demo'],
            decisions_made=['Will send proposal by Friday', 'Schedule follow-up next week'],
            confidence_score=0.85
        )
    
    def test_generate_crm_suggestions_salesforce(self):
        """Test generating CRM suggestions for Salesforce"""
        url = reverse('generate-crm-suggestions', kwargs={'summary_id': self.draft_summary.id})
        data = {
            'crm_system': 'salesforce',
            'current_opportunity_stage': 'prospecting'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['crm_system'], 'salesforce')
        self.assertIn('field_updates', response.data)
        self.assertIn('field_mappings', response.data)
        self.assertIn('follow_up_tasks', response.data)
        self.assertIn('confidence_score', response.data)
        
        # Check that Salesforce-specific fields are present
        self.assertIn('Description', response.data['field_updates'])
    
    def test_generate_crm_suggestions_hubspot(self):
        """Test generating CRM suggestions for HubSpot"""
        url = reverse('generate-crm-suggestions', kwargs={'summary_id': self.draft_summary.id})
        data = {
            'crm_system': 'hubspot'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['crm_system'], 'hubspot')
        
        # Check that HubSpot-specific fields are present
        self.assertIn('hs_meeting_body', response.data['field_updates'])
    
    def test_generate_crm_suggestions_invalid_system(self):
        """Test generating CRM suggestions with invalid system"""
        url = reverse('generate-crm-suggestions', kwargs={'summary_id': self.draft_summary.id})
        data = {
            'crm_system': 'invalid_crm'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_get_crm_field_mappings_salesforce(self):
        """Test getting CRM field mappings for Salesforce"""
        url = reverse('get-crm-field-mappings', kwargs={'crm_system': 'salesforce'})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['crm_system'], 'salesforce')
        self.assertIn('field_mappings', response.data)
        self.assertGreater(response.data['total_fields'], 0)
        
        # Check specific Salesforce fields
        field_mappings = response.data['field_mappings']
        self.assertIn('notes', field_mappings)
        self.assertEqual(field_mappings['notes']['crm_field'], 'Description')
    
    def test_get_crm_field_mappings_invalid_system(self):
        """Test getting CRM field mappings for invalid system"""
        url = reverse('get-crm-field-mappings', kwargs={'crm_system': 'invalid_crm'})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_validate_crm_field_mapping_valid(self):
        """Test validating a valid CRM field mapping"""
        url = reverse('validate-crm-field-mapping')
        data = {
            'crm_system': 'salesforce',
            'field_name': 'Description',
            'field_value': 'Test meeting notes'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valid'])
        self.assertIn('field_type', response.data)
    
    def test_validate_crm_field_mapping_invalid_field(self):
        """Test validating an invalid CRM field mapping"""
        url = reverse('validate-crm-field-mapping')
        data = {
            'crm_system': 'salesforce',
            'field_name': 'NonExistentField',
            'field_value': 'Test value'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['valid'])
        self.assertIn('available_fields', response.data)
    
    def test_preview_crm_update(self):
        """Test previewing CRM update"""
        url = reverse('preview-crm-update', kwargs={'summary_id': self.draft_summary.id})
        data = {
            'crm_system': 'salesforce'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preview', response.data)
        self.assertIn('summary', response.data)
        
        preview = response.data['preview']
        self.assertEqual(preview['crm_system'], 'salesforce')
        self.assertIn('formatted_data', preview)
        self.assertIn('suggested_updates', preview)
        self.assertIn('confidence_score', preview)
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access endpoints"""
        self.client.force_authenticate(user=None)
        
        url = reverse('generate-crm-suggestions', kwargs={'summary_id': self.draft_summary.id})
        response = self.client.post(url, {'crm_system': 'salesforce'}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_nonexistent_summary(self):
        """Test handling of nonexistent summary ID"""
        url = reverse('generate-crm-suggestions', kwargs={'summary_id': 99999})
        data = {
            'crm_system': 'salesforce'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)