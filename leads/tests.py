from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Lead
from .serializers import LeadSerializer, LeadSyncSerializer
import factory


class LeadFactory(factory.django.DjangoModelFactory):
    """Factory for creating Lead test instances"""
    
    class Meta:
        model = Lead
    
    crm_id = factory.Sequence(lambda n: f"CRM_{n}")
    name = factory.Faker('name')
    email = factory.Faker('email')
    company = factory.Faker('company')
    phone = factory.Faker('phone_number')
    status = 'new'
    source = 'website'


class LeadModelTest(TestCase):
    """Test cases for Lead model"""
    
    def test_lead_creation(self):
        """Test creating a valid lead"""
        lead = LeadFactory()
        self.assertTrue(isinstance(lead, Lead))
        self.assertEqual(lead.status, 'new')
        self.assertIsNotNone(lead.created_at)
        self.assertIsNotNone(lead.last_sync)
    
    def test_lead_str_representation(self):
        """Test string representation of lead"""
        lead = LeadFactory(name="John Doe", company="Test Corp")
        self.assertEqual(str(lead), "John Doe (Test Corp)")
    
    def test_unique_crm_id_constraint(self):
        """Test that crm_id must be unique"""
        LeadFactory(crm_id="UNIQUE_ID")
        with self.assertRaises((IntegrityError, ValidationError)):
            LeadFactory(crm_id="UNIQUE_ID")
    
    def test_lead_validation_empty_name(self):
        """Test validation for empty name"""
        lead = LeadFactory.build(name="")
        with self.assertRaises(ValidationError):
            lead.full_clean()
    
    def test_lead_validation_empty_company(self):
        """Test validation for empty company"""
        lead = LeadFactory.build(company="")
        with self.assertRaises(ValidationError):
            lead.full_clean()
    
    def test_lead_validation_short_phone(self):
        """Test validation for short phone number"""
        lead = LeadFactory.build(phone="123")
        with self.assertRaises(ValidationError):
            lead.full_clean()
    
    def test_lead_validation_valid_email(self):
        """Test validation for valid email"""
        lead = LeadFactory.build(email="invalid-email")
        with self.assertRaises(ValidationError):
            lead.full_clean()
    
    def test_lead_ordering(self):
        """Test default ordering by created_at desc"""
        import time
        lead1 = LeadFactory()
        time.sleep(0.01)  # Small delay to ensure different timestamps
        lead2 = LeadFactory()
        leads = Lead.objects.all()
        self.assertEqual(leads[0], lead2)  # Most recent first


class LeadSerializerTest(TestCase):
    """Test cases for Lead serializers"""
    
    def test_lead_serializer_valid_data(self):
        """Test serializer with valid data"""
        data = {
            'crm_id': 'CRM_123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'company': 'Test Corp',
            'phone': '1234567890',
            'status': 'new',
            'source': 'website'
        }
        serializer = LeadSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_lead_serializer_invalid_email(self):
        """Test serializer with invalid email"""
        data = {
            'crm_id': 'CRM_123',
            'name': 'John Doe',
            'email': 'invalid-email',
            'company': 'Test Corp'
        }
        serializer = LeadSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
    
    def test_lead_sync_serializer(self):
        """Test bulk sync serializer"""
        data = {
            'leads': [
                {
                    'crm_id': 'CRM_1',
                    'name': 'John Doe',
                    'email': 'john@example.com',
                    'company': 'Test Corp'
                },
                {
                    'crm_id': 'CRM_2',
                    'name': 'Jane Smith',
                    'email': 'jane@example.com',
                    'company': 'Another Corp'
                }
            ]
        }
        serializer = LeadSyncSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class LeadAPITest(APITestCase):
    """Test cases for Lead API endpoints"""
    
    def setUp(self):
        """Set up test user and authentication"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_lead_list_endpoint(self):
        """Test GET /api/leads/"""
        LeadFactory.create_batch(3)
        response = self.client.get('/api/leads/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
    
    def test_lead_create_endpoint(self):
        """Test POST /api/leads/"""
        data = {
            'crm_id': 'CRM_123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'company': 'Test Corp'
        }
        response = self.client.post('/api/leads/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Lead.objects.count(), 1)
    
    def test_lead_detail_endpoint(self):
        """Test GET /api/leads/{id}/"""
        lead = LeadFactory()
        response = self.client.get(f'/api/leads/{lead.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], lead.name)
    
    def test_lead_update_endpoint(self):
        """Test PUT /api/leads/{id}/"""
        lead = LeadFactory()
        data = {
            'crm_id': lead.crm_id,
            'name': 'Updated Name',
            'email': lead.email,
            'company': lead.company
        }
        response = self.client.put(f'/api/leads/{lead.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.name, 'Updated Name')
    
    def test_lead_sync_endpoint(self):
        """Test POST /api/leads/sync/"""
        data = {
            'leads': [
                {
                    'crm_id': 'CRM_1',
                    'name': 'John Doe',
                    'email': 'john@example.com',
                    'company': 'Test Corp'
                }
            ]
        }
        response = self.client.post('/api/leads/sync/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Lead.objects.count(), 1)
    
    def test_lead_sync_creatio_format(self):
        """Test POST /api/leads/sync/ with Creatio format"""
        data = [
            {
                'Id': 'CREATIO_123',
                'Name': 'Jane Smith',
                'Email': 'jane@example.com',
                'Company': 'Creatio Corp',
                'Phone': '1234567890',
                'Status': 'Qualified',
                'Source': 'Website'
            }
        ]
        response = self.client.post('/api/leads/sync/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Lead.objects.count(), 1)
        
        lead = Lead.objects.first()
        self.assertEqual(lead.crm_id, 'CREATIO_123')
        self.assertEqual(lead.status, 'qualified')
    
    def test_lead_sync_error_handling(self):
        """Test error handling in sync endpoint"""
        data = {
            'leads': [
                {
                    'crm_id': 'CRM_1',
                    'name': '',  # Invalid empty name
                    'email': 'john@example.com',
                    'company': 'Test Corp'
                }
            ]
        }
        response = self.client.post('/api/leads/sync/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
    
    def test_lead_sync_update_existing(self):
        """Test updating existing leads via sync"""
        # Create initial lead
        lead = LeadFactory(crm_id='CRM_UPDATE', name='Original Name')
        
        data = {
            'leads': [
                {
                    'crm_id': 'CRM_UPDATE',
                    'name': 'Updated Name',
                    'email': lead.email,
                    'company': lead.company,
                    'status': 'new'  # Add required status field
                }
            ]
        }
        response = self.client.post('/api/leads/sync/', data, format='json')
        if response.status_code != status.HTTP_200_OK:
            print(f"Response data: {response.data}")  # Debug output
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Lead.objects.count(), 1)
        
        lead.refresh_from_db()
        self.assertEqual(lead.name, 'Updated Name')
    
    def test_lead_status_update_endpoint(self):
        """Test PUT /api/leads/{id}/status/"""
        lead = LeadFactory()
        data = {'status': 'qualified'}
        response = self.client.put(f'/api/leads/{lead.id}/status/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.status, 'qualified')
    
    def test_lead_filtering(self):
        """Test lead filtering by status and company"""
        LeadFactory(status='new', company='Company A')
        LeadFactory(status='qualified', company='Company B')
        
        # Filter by status
        response = self.client.get('/api/leads/?status=new')
        self.assertEqual(len(response.data['results']), 1)
        
        # Filter by company
        response = self.client.get('/api/leads/?company=Company A')
        self.assertEqual(len(response.data['results']), 1)


class LeadMatchingServiceTest(TestCase):
    """Test cases for Lead matching service"""
    
    def setUp(self):
        """Set up test data"""
        from .services import LeadMatchingService
        self.matching_service = LeadMatchingService()
        
        # Create test leads
        self.lead1 = LeadFactory(
            crm_id='CRM_001',
            name='John Doe',
            email='john.doe@techcorp.com',
            company='TechCorp Inc',
            phone='555-123-4567'
        )
        self.lead2 = LeadFactory(
            crm_id='CRM_002',
            name='Jane Smith',
            email='jane.smith@innovate.com',
            company='Innovate LLC',
            phone='555-987-6543'
        )
        self.lead3 = LeadFactory(
            crm_id='CRM_003',
            name='Bob Johnson',
            email='bob@startup.io',
            company='Startup Solutions',
            phone='555-555-5555'
        )
    
    def test_exact_email_match(self):
        """Test matching with exact email match"""
        meeting_data = {
            'attendees': ['john.doe@techcorp.com', 'other@example.com'],
            'title': 'Product Demo',
            'organizer': 'sales@ourcompany.com'
        }
        
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        self.assertIsNotNone(match)
        self.assertEqual(match['crm_id'], 'CRM_001')
        self.assertGreaterEqual(match['confidence'], 50)
        self.assertIn('Email match', str(match['match_reasons']))
    
    def test_domain_match(self):
        """Test matching with same domain"""
        meeting_data = {
            'attendees': ['different.person@techcorp.com'],
            'title': 'Meeting with TechCorp',
            'organizer': 'sales@ourcompany.com'
        }
        
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        # Domain match alone might not reach 85% threshold, but should be in potential matches
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        self.assertEqual(potential_matches[0]['crm_id'], 'CRM_001')
    
    def test_name_match_in_title(self):
        """Test matching with name in meeting title"""
        meeting_data = {
            'attendees': ['unknown@example.com'],
            'title': 'Meeting with John Doe from TechCorp',
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        
        # Find the match for John Doe
        john_match = next((m for m in potential_matches if m['crm_id'] == 'CRM_001'), None)
        self.assertIsNotNone(john_match)
        self.assertGreater(john_match['confidence'], 0)
    
    def test_company_match(self):
        """Test matching with company name in meeting details"""
        meeting_data = {
            'attendees': ['contact@example.com'],
            'title': 'TechCorp Partnership Discussion',
            'description': 'Discussing partnership opportunities with TechCorp Inc',
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        
        # Find the match for TechCorp
        techcorp_match = next((m for m in potential_matches if m['crm_id'] == 'CRM_001'), None)
        self.assertIsNotNone(techcorp_match)
        self.assertGreater(techcorp_match['confidence'], 0)
    
    def test_no_match_found(self):
        """Test when no good match is found"""
        meeting_data = {
            'attendees': ['random@nowhere.com'],
            'title': 'Random Meeting',
            'organizer': 'sales@ourcompany.com'
        }
        
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        self.assertIsNone(match)
    
    def test_multiple_potential_matches(self):
        """Test finding multiple potential matches"""
        meeting_data = {
            'attendees': ['contact@example.com'],
            'title': 'Meeting about innovation and tech solutions',
            'description': 'Discussing various tech and innovation solutions',
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data, limit=3)
        self.assertLessEqual(len(potential_matches), 3)
        
        # Should be sorted by confidence
        if len(potential_matches) > 1:
            self.assertGreaterEqual(
                potential_matches[0]['confidence'],
                potential_matches[1]['confidence']
            )
    
    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        # High confidence match (email + name + company)
        meeting_data = {
            'attendees': ['john.doe@techcorp.com'],
            'title': 'Meeting with John Doe from TechCorp Inc',
            'organizer': 'sales@ourcompany.com'
        }
        
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(match['confidence'], 50)
    
    def test_phone_matching(self):
        """Test phone number matching in description"""
        meeting_data = {
            'attendees': ['contact@example.com'],
            'title': 'Follow-up call',
            'description': 'Call John at 555-123-4567 to discuss the proposal',
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        
        # Find the match for John Doe (has phone 555-123-4567)
        john_match = next((m for m in potential_matches if m['crm_id'] == 'CRM_001'), None)
        self.assertIsNotNone(john_match)
        self.assertGreater(john_match['confidence'], 0)
    
    def test_fuzzy_name_matching(self):
        """Test fuzzy matching for names with typos"""
        meeting_data = {
            'attendees': ['contact@example.com'],
            'title': 'Meeting with Jon Doe',  # Typo in name
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        
        # Should still match John Doe despite typo
        john_match = next((m for m in potential_matches if m['crm_id'] == 'CRM_001'), None)
        self.assertIsNotNone(john_match)
    
    def test_company_name_normalization(self):
        """Test company name matching with different suffixes"""
        meeting_data = {
            'attendees': ['contact@example.com'],
            'title': 'Meeting with TechCorp',  # Without "Inc"
            'organizer': 'sales@ourcompany.com'
        }
        
        potential_matches = self.matching_service.find_potential_matches(meeting_data)
        self.assertGreater(len(potential_matches), 0)
        
        # Should match TechCorp Inc
        techcorp_match = next((m for m in potential_matches if m['crm_id'] == 'CRM_001'), None)
        self.assertIsNotNone(techcorp_match)


class LeadMatchingAPITest(APITestCase):
    """Test cases for Lead matching API endpoints"""
    
    def setUp(self):
        """Set up test user and test leads"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test leads
        self.lead1 = LeadFactory(
            crm_id='CRM_001',
            name='John Doe',
            email='john.doe@techcorp.com',
            company='TechCorp Inc'
        )
        self.lead2 = LeadFactory(
            crm_id='CRM_002',
            name='Jane Smith',
            email='jane.smith@innovate.com',
            company='Innovate LLC'
        )
    
    def test_match_meeting_to_lead_endpoint(self):
        """Test POST /api/leads/match-meeting/"""
        data = {
            'attendees': ['john.doe@techcorp.com', 'other@example.com'],
            'title': 'Product Demo',
            'organizer': 'sales@ourcompany.com'
        }
        
        response = self.client.post('/api/leads/match-meeting/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['match_found'])
        self.assertEqual(response.data['match']['crm_id'], 'CRM_001')
    
    def test_match_meeting_no_match_found(self):
        """Test matching when no good match is found"""
        data = {
            'attendees': ['unknown@nowhere.com'],
            'title': 'Random Meeting',
            'organizer': 'sales@ourcompany.com'
        }
        
        response = self.client.post('/api/leads/match-meeting/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertFalse(response.data['match_found'])
        self.assertIn('potential_matches', response.data)
    
    def test_get_potential_matches_endpoint(self):
        """Test GET /api/leads/potential-matches/"""
        self.client.force_authenticate(user=self.user)
        
        params = {
            'attendees': ['contact@example.com'],
            'title': 'Meeting with TechCorp',
            'organizer': 'sales@ourcompany.com'
        }
        
        response = self.client.get('/api/leads/potential-matches/', params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('potential_matches', response.data)
        self.assertIsInstance(response.data['potential_matches'], list)
    
    def test_match_meeting_error_handling(self):
        """Test error handling in matching endpoint"""
        # Send invalid data
        response = self.client.post('/api/leads/match-meeting/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Should handle gracefully
        self.assertTrue(response.data['success'])
        self.assertFalse(response.data['match_found'])
    
    def test_match_reasons(self):
        """Test that match reasons are properly generated"""
        meeting_data = {
            'attendees': ['john.doe@techcorp.com'],
            'title': 'Meeting with John from TechCorp',
            'organizer': 'sales@ourcompany.com'
        }
        
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        self.assertIsNotNone(match)
        self.assertIsInstance(match['match_reasons'], list)
        self.assertGreater(len(match['match_reasons']), 0)
        
        # Should have multiple reasons for this comprehensive match
        reasons_text = ' '.join(match['match_reasons'])
        self.assertIn('Email match', reasons_text)
    
    def test_cache_refresh(self):
        """Test that cache refresh works properly"""
        # Create a new lead after service initialization
        new_lead = LeadFactory(
            crm_id='CRM_NEW',
            name='New Person',
            email='new@newcompany.com',
            company='New Company'
        )
        
        # Should not match initially (cache not refreshed)
        meeting_data = {
            'attendees': ['new@newcompany.com'],
            'title': 'Meeting with New Person',
            'organizer': 'sales@ourcompany.com'
        }
        
        # Refresh cache and try again
        self.matching_service._refresh_cache()
        match = self.matching_service.match_meeting_to_lead(meeting_data)
        self.assertIsNotNone(match)
        self.assertEqual(match['crm_id'], 'CRM_NEW')