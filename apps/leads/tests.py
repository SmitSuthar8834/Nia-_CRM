"""
Comprehensive Unit Tests for Meeting Participant Matching and Lead Identification
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Lead, ActionItem, CompetitiveIntelligence
from .services import (
    ParticipantMatchingService, 
    LeadCreationService, 
    ParticipantAnalysisService
)
# from .verification import ManualVerificationService, VerificationRequest
from .linkedin_integration import LinkedInProfileService, SocialProfileMatcher
from apps.meetings.models import Meeting, MeetingParticipant


class ParticipantMatchingServiceTest(TestCase):
    """Test cases for ParticipantMatchingService"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test leads
        self.lead1 = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@acme.com',
            phone='555-123-4567',
            company='Acme Corp',
            title='VP Sales',
            source='meeting'
        )
        
        self.lead2 = Lead.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@techcorp.com',
            phone='555-987-6543',
            company='TechCorp Inc',
            title='CTO',
            source='meeting'
        )
        
        self.lead3 = Lead.objects.create(
            first_name='Bob',
            last_name='Johnson',
            email='bob@acme.com',
            company='Acme Corp',
            title='Director',
            source='meeting'
        )
        
        self.matching_service = ParticipantMatchingService()
    
    def test_exact_email_match(self):
        """Test exact email matching (highest confidence)"""
        participants = [
            {
                'email': 'john.doe@acme.com',
                'name': 'John Doe',
                'company': 'Acme Corp'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        self.assertEqual(result['matched_lead'], self.lead1)
        self.assertEqual(result['confidence_score'], 1.0)
        self.assertEqual(result['match_method'], 'exact_email')
        self.assertFalse(result['requires_manual_verification'])
        self.assertFalse(result['should_create_new_lead'])
    
    def test_name_company_match(self):
        """Test name and company combination matching"""
        participants = [
            {
                'email': 'j.doe@acme.com',  # Different email
                'name': 'John Doe',
                'company': 'Acme Corp'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Should find potential matches
        self.assertTrue(len(result['potential_matches']) > 0)
        
        # Check if high confidence match was found
        if result['matched_lead']:
            self.assertGreaterEqual(result['confidence_score'], 
                                  self.matching_service.HIGH_CONFIDENCE_THRESHOLD)
    
    def test_domain_matching(self):
        """Test email domain matching"""
        participants = [
            {
                'email': 'new.person@acme.com',
                'name': 'New Person',
                'company': 'Acme Corp'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Should find domain matches (lead1 and lead3 are from acme.com)
        self.assertTrue(len(result['potential_matches']) >= 2)
        
        # Check domain matches
        domain_matches = [m for m in result['potential_matches'] if m['match_type'] == 'domain']
        self.assertTrue(len(domain_matches) >= 2)
    
    def test_phone_matching(self):
        """Test phone number matching"""
        participants = [
            {
                'email': 'unknown@example.com',
                'name': 'Unknown Person',
                'phone': '555-123-4567'  # Same as lead1
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Should find phone match
        phone_matches = [m for m in result['potential_matches'] if m['match_type'] == 'phone']
        self.assertTrue(len(phone_matches) > 0)
    
    def test_fuzzy_name_matching(self):
        """Test fuzzy name matching within company context"""
        participants = [
            {
                'email': 'johnathan.doe@acme.com',
                'name': 'Johnathan Doe',  # Similar to John Doe
                'company': 'Acme Corp'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Should find fuzzy name matches
        fuzzy_matches = [m for m in result['potential_matches'] if m['match_type'] == 'fuzzy_name']
        self.assertTrue(len(fuzzy_matches) > 0)
    
    def test_no_match_should_create_new_lead(self):
        """Test that unmatched participants are flagged for new lead creation"""
        participants = [
            {
                'email': 'completely.new@newcompany.com',
                'name': 'Completely New',
                'company': 'New Company'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        self.assertIsNone(result['matched_lead'])
        self.assertTrue(result['should_create_new_lead'])
        self.assertEqual(len(result['potential_matches']), 0)
    
    def test_low_confidence_requires_verification(self):
        """Test that low confidence matches require manual verification"""
        # Create a lead with similar but not exact information
        similar_lead = Lead.objects.create(
            first_name='Jon',  # Similar to John
            last_name='Doe',
            email='jon.doe@different.com',
            company='Different Corp',
            source='meeting'
        )
        
        participants = [
            {
                'email': 'john@somewhere.com',
                'name': 'John Doe',
                'company': 'Some Company'
            }
        ]
        
        results = self.matching_service.match_participants(participants)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        
        # Should have potential matches but require verification
        if result['potential_matches']:
            # Check if any low confidence matches require verification
            low_confidence_matches = [
                m for m in result['potential_matches'] 
                if m['confidence'] < self.matching_service.MEDIUM_CONFIDENCE_THRESHOLD
            ]
            if low_confidence_matches and not result['matched_lead']:
                self.assertTrue(result['requires_manual_verification'])
    
    def test_normalize_phone_numbers(self):
        """Test phone number normalization"""
        test_cases = [
            ('(555) 123-4567', '5551234567'),
            ('+1-555-123-4567', '5551234567'),
            ('555.123.4567', '5551234567'),
            ('15551234567', '5551234567'),  # Remove country code
            ('555 123 4567', '5551234567'),
        ]
        
        for input_phone, expected in test_cases:
            normalized = self.matching_service._normalize_phone(input_phone)
            self.assertEqual(normalized, expected, f"Failed for input: {input_phone}")
    
    def test_name_parsing(self):
        """Test name parsing functionality"""
        test_cases = [
            ('John Doe', ('John', 'Doe')),
            ('Mary Jane Smith', ('Mary', 'Jane Smith')),
            ('John', None),  # Single name should return None
            ('', None),  # Empty name should return None
        ]
        
        for input_name, expected in test_cases:
            result = self.matching_service._parse_name(input_name)
            self.assertEqual(result, expected, f"Failed for input: {input_name}")
    
    def test_string_similarity_calculation(self):
        """Test string similarity calculation"""
        test_cases = [
            ('Acme Corp', 'Acme Corporation', 0.8),  # Should be high similarity
            ('TechCorp', 'Tech Corp', 0.8),  # Should be high similarity
            ('Apple', 'Microsoft', 0.2),  # Should be low similarity
            ('Same', 'Same', 1.0),  # Exact match
        ]
        
        for str1, str2, min_expected in test_cases:
            similarity = self.matching_service._calculate_string_similarity(str1, str2)
            self.assertGreaterEqual(similarity, min_expected, 
                                  f"Similarity too low for '{str1}' vs '{str2}': {similarity}")


class LeadCreationServiceTest(TestCase):
    """Test cases for LeadCreationService"""
    
    def setUp(self):
        self.creation_service = LeadCreationService()
    
    def test_create_lead_from_participant(self):
        """Test creating a new lead from participant data"""
        participant = {
            'email': 'new.lead@company.com',
            'name': 'New Lead',
            'company': 'New Company',
            'title': 'Manager',
            'phone': '555-999-8888'
        }
        
        lead = self.creation_service.create_lead_from_participant(participant)
        
        self.assertEqual(lead.first_name, 'New')
        self.assertEqual(lead.last_name, 'Lead')
        self.assertEqual(lead.email, 'new.lead@company.com')
        self.assertEqual(lead.company, 'New Company')
        self.assertEqual(lead.title, 'Manager')
        self.assertEqual(lead.phone, '555-999-8888')
        self.assertEqual(lead.source, 'meeting')
        self.assertEqual(lead.status, 'new')
    
    def test_infer_company_from_email(self):
        """Test company inference from email domain"""
        test_cases = [
            ('user@acme.com', 'Acme'),
            ('john@tech-corp.com', 'Tech Corp'),
            ('jane@gmail.com', 'Unknown'),  # Common domain
            ('bob@my_company.org', 'My Company'),
        ]
        
        for email, expected_company in test_cases:
            company = self.creation_service._infer_company_from_email(email)
            self.assertEqual(company, expected_company, f"Failed for email: {email}")
    
    def test_parse_participant_name_from_email(self):
        """Test name parsing from email when name is not provided"""
        test_cases = [
            ('', 'john.doe@company.com', ('John', 'Doe')),
            ('', 'jane_smith@company.com', ('Jane', 'Smith')),
            ('', 'singlename@company.com', ('Singlename', '')),
            ('Provided Name', 'email@company.com', ('Provided', 'Name')),
        ]
        
        for name, email, expected in test_cases:
            first, last = self.creation_service._parse_participant_name(name, email)
            self.assertEqual((first, last), expected, 
                           f"Failed for name='{name}', email='{email}'")


class ParticipantAnalysisServiceTest(TestCase):
    """Test cases for ParticipantAnalysisService"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        self.lead = Lead.objects.create(
            first_name='Existing',
            last_name='Lead',
            email='existing@company.com',
            company='Existing Company',
            source='meeting'
        )
        
        self.analysis_service = ParticipantAnalysisService()
    
    def test_analyze_meeting_participants_with_matches(self):
        """Test participant analysis with existing lead matches"""
        participants = [
            {
                'email': 'existing@company.com',
                'name': 'Existing Lead',
                'company': 'Existing Company'
            },
            {
                'email': 'new@newcompany.com',
                'name': 'New Person',
                'company': 'New Company'
            }
        ]
        
        results = self.analysis_service.analyze_meeting_participants(
            str(self.meeting.id), participants, use_linkedin_enhancement=False
        )
        
        self.assertEqual(results['total_participants'], 2)
        self.assertEqual(results['matched_participants'], 1)
        self.assertEqual(results['new_leads_created'], 1)
        
        # Check that meeting participants were created
        meeting_participants = MeetingParticipant.objects.filter(meeting=self.meeting)
        self.assertEqual(meeting_participants.count(), 2)
    
    @patch('apps.leads.services.LinkedInProfileService')
    def test_linkedin_enhancement(self, mock_linkedin_service):
        """Test LinkedIn enhancement of participant data"""
        # Mock LinkedIn service
        mock_service_instance = MagicMock()
        mock_linkedin_service.return_value = mock_service_instance
        
        mock_service_instance.enrich_participant_data.return_value = {
            'email': 'test@company.com',
            'name': 'Test Person',
            'company': 'Test Company',
            'linkedin_profile': 'https://linkedin.com/in/testperson',
            'enhanced_title': 'Senior Manager',
            'industry': 'Technology'
        }
        
        participants = [
            {
                'email': 'test@company.com',
                'name': 'Test Person',
                'company': 'Test Company'
            }
        ]
        
        results = self.analysis_service.analyze_meeting_participants(
            str(self.meeting.id), participants, use_linkedin_enhancement=True
        )
        
        # Should have attempted LinkedIn enhancement
        mock_service_instance.enrich_participant_data.assert_called_once()
    
    def test_meeting_stats_update(self):
        """Test that lead meeting statistics are updated"""
        participants = [
            {
                'email': 'existing@company.com',
                'name': 'Existing Lead',
                'company': 'Existing Company'
            }
        ]
        
        # Initial meeting count should be 0
        self.assertEqual(self.lead.meeting_count, 0)
        
        self.analysis_service.analyze_meeting_participants(
            str(self.meeting.id), participants, use_linkedin_enhancement=False
        )
        
        # Refresh lead from database
        self.lead.refresh_from_db()
        
        # Meeting count should be updated
        self.assertEqual(self.lead.meeting_count, 1)
        self.assertIsNotNone(self.lead.last_meeting_date)


# class ManualVerificationServiceTest(TestCase):
    """Test cases for ManualVerificationService"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test-event-123',
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        self.meeting_participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='test@company.com',
            name='Test Person',
            company='Test Company',
            manual_verification_required=True
        )
        
        self.lead = Lead.objects.create(
            first_name='Potential',
            last_name='Match',
            email='potential@company.com',
            company='Test Company',
            source='meeting'
        )
        
        self.verification_service = ManualVerificationService()
    
    def test_create_verification_request(self):
        """Test creating a verification request"""
        participant_data = {
            'email': 'test@company.com',
            'name': 'Test Person',
            'company': 'Test Company'
        }
        
        potential_matches = [
            {
                'lead': self.lead,
                'confidence': 0.6,
                'match_type': 'name_company'
            }
        ]
        
        verification_request = self.verification_service.create_verification_request(
            self.meeting_participant, participant_data, potential_matches
        )
        
        self.assertIsNotNone(verification_request)
        self.assertEqual(verification_request.meeting_participant, self.meeting_participant)
        self.assertEqual(verification_request.status, 'pending')
        self.assertEqual(verification_request.assigned_to, self.user)  # Meeting organizer
        self.assertTrue(len(verification_request.potential_matches) > 0)
    
    def test_approve_match(self):
        """Test approving a verification request with a specific match"""
        verification_request = VerificationRequest.objects.create(
            meeting_participant=self.meeting_participant,
            verification_type='participant_match',
            participant_data={'email': 'test@company.com'},
            potential_matches=[],
            assigned_to=self.user,
            due_date=timezone.now() + timezone.timedelta(hours=24)
        )
        
        verification_request.approve_match(self.lead, self.user, "Good match")
        
        self.assertEqual(verification_request.status, 'approved')
        self.assertEqual(verification_request.selected_match, self.lead)
        self.assertIsNotNone(verification_request.reviewed_at)
        
        # Check that meeting participant was updated
        self.meeting_participant.refresh_from_db()
        self.assertEqual(self.meeting_participant.matched_lead, self.lead)
        self.assertFalse(self.meeting_participant.manual_verification_required)
    
    def test_approve_new_lead_creation(self):
        """Test approving new lead creation"""
        verification_request = VerificationRequest.objects.create(
            meeting_participant=self.meeting_participant,
            verification_type='participant_match',
            participant_data={
                'email': 'test@company.com',
                'name': 'Test Person',
                'company': 'Test Company'
            },
            potential_matches=[],
            assigned_to=self.user,
            due_date=timezone.now() + timezone.timedelta(hours=24)
        )
        
        initial_lead_count = Lead.objects.count()
        
        verification_request.approve_new_lead_creation(self.user, "Create new lead")
        
        self.assertEqual(verification_request.status, 'approved')
        self.assertTrue(verification_request.create_new_lead)
        
        # Check that new lead was created
        self.assertEqual(Lead.objects.count(), initial_lead_count + 1)
        
        # Check that meeting participant was updated
        self.meeting_participant.refresh_from_db()
        self.assertIsNotNone(self.meeting_participant.matched_lead)
        self.assertFalse(self.meeting_participant.manual_verification_required)
    
    def test_get_overdue_verifications(self):
        """Test getting overdue verification requests"""
        # Create overdue verification request
        overdue_request = VerificationRequest.objects.create(
            meeting_participant=self.meeting_participant,
            verification_type='participant_match',
            participant_data={'email': 'test@company.com'},
            potential_matches=[],
            assigned_to=self.user,
            due_date=timezone.now() - timezone.timedelta(hours=1)  # 1 hour overdue
        )
        
        overdue_requests = self.verification_service.get_overdue_verifications()
        
        self.assertEqual(len(overdue_requests), 1)
        self.assertEqual(overdue_requests[0], overdue_request)
    
    def test_bulk_approve_high_confidence_matches(self):
        """Test bulk approval of high confidence matches"""
        # Create verification request with high confidence match
        verification_request = VerificationRequest.objects.create(
            meeting_participant=self.meeting_participant,
            verification_type='participant_match',
            participant_data={'email': 'test@company.com'},
            potential_matches=[{
                'lead_id': str(self.lead.id),
                'confidence': 0.85,
                'match_type': 'name_company'
            }],
            assigned_to=self.user,
            due_date=timezone.now() + timezone.timedelta(hours=24)
        )
        
        approved_count = self.verification_service.bulk_approve_high_confidence_matches(0.8)
        
        self.assertEqual(approved_count, 1)
        
        verification_request.refresh_from_db()
        self.assertEqual(verification_request.status, 'approved')


class LinkedInIntegrationTest(TestCase):
    """Test cases for LinkedIn integration"""
    
    def setUp(self):
        self.linkedin_service = LinkedInProfileService()
        self.social_matcher = SocialProfileMatcher()
    
    @patch('apps.leads.linkedin_integration.requests.get')
    def test_search_profiles_with_mock(self, mock_get):
        """Test LinkedIn profile search with mocked API response"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'elements': [
                {
                    'formattedName': 'John Doe',
                    'headline': 'VP of Sales',
                    'publicProfileUrl': 'https://linkedin.com/in/johndoe',
                    'positions': {
                        'values': [
                            {
                                'company': {'name': 'Acme Corp'},
                                'title': 'VP Sales'
                            }
                        ]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response
        
        # Mock credentials check
        with patch.object(self.linkedin_service, '_has_linkedin_credentials', return_value=True):
            profiles = self.linkedin_service.search_profiles('John Doe', 'Acme Corp')
            
            self.assertTrue(len(profiles) > 0)
            profile = profiles[0]
            self.assertEqual(profile['name'], 'John Doe')
            self.assertIn('confidence', profile)
    
    def test_enrich_participant_data_without_credentials(self):
        """Test participant enrichment when LinkedIn credentials are not available"""
        participant = {
            'email': 'test@company.com',
            'name': 'Test Person',
            'company': 'Test Company'
        }
        
        # Should return original participant data when no credentials
        enriched = self.linkedin_service.enrich_participant_data(participant)
        self.assertEqual(enriched, participant)
    
    def test_calculate_experience_years(self):
        """Test experience calculation from LinkedIn profile data"""
        profile_data = {
            'positions': {
                'values': [
                    {
                        'startDate': {'year': 2020, 'month': 1},
                        'endDate': {'year': 2022, 'month': 12}
                    },
                    {
                        'startDate': {'year': 2018, 'month': 6},
                        'endDate': {'year': 2020, 'month': 1}
                    }
                ]
            }
        }
        
        years = self.linkedin_service._calculate_experience_years(profile_data)
        self.assertGreaterEqual(years, 4)  # Should be around 4-5 years
    
    def test_is_business_relevant_industry(self):
        """Test business industry relevance check"""
        relevant_industries = [
            'Technology',
            'Software Development',
            'Financial Services',
            'Healthcare Technology'
        ]
        
        irrelevant_industries = [
            'Entertainment',
            'Sports',
            'Personal Care'
        ]
        
        for industry in relevant_industries:
            self.assertTrue(
                self.linkedin_service._is_business_relevant_industry(industry),
                f"Should be relevant: {industry}"
            )
        
        for industry in irrelevant_industries:
            self.assertFalse(
                self.linkedin_service._is_business_relevant_industry(industry),
                f"Should not be relevant: {industry}"
            )


class IntegrationTest(TestCase):
    """Integration tests for the complete participant matching workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='integration-test-123',
            title='Integration Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        # Create some existing leads
        self.existing_leads = [
            Lead.objects.create(
                first_name='Alice',
                last_name='Johnson',
                email='alice@techcorp.com',
                company='TechCorp',
                title='CEO',
                source='meeting'
            ),
            Lead.objects.create(
                first_name='Bob',
                last_name='Smith',
                email='bob@acme.com',
                company='Acme Inc',
                title='CTO',
                source='meeting'
            )
        ]
    
    def test_complete_participant_analysis_workflow(self):
        """Test the complete workflow from participant data to lead matching"""
        participants = [
            # Exact match
            {
                'email': 'alice@techcorp.com',
                'name': 'Alice Johnson',
                'company': 'TechCorp'
            },
            # Domain match with similar name
            {
                'email': 'robert.smith@acme.com',
                'name': 'Robert Smith',
                'company': 'Acme Inc'
            },
            # New participant - should create new lead
            {
                'email': 'charlie@newcompany.com',
                'name': 'Charlie Brown',
                'company': 'New Company',
                'title': 'Manager'
            },
            # Ambiguous match - should require verification
            {
                'email': 'similar@somewhere.com',
                'name': 'Alice Smith',  # Similar to existing leads
                'company': 'Some Company'
            }
        ]
        
        analysis_service = ParticipantAnalysisService()
        results = analysis_service.analyze_meeting_participants(
            str(self.meeting.id), participants, use_linkedin_enhancement=False
        )
        
        # Verify results
        self.assertEqual(results['total_participants'], 4)
        self.assertGreaterEqual(results['matched_participants'], 1)  # At least exact match
        self.assertGreaterEqual(results['new_leads_created'], 1)  # At least Charlie
        
        # Verify meeting participants were created
        meeting_participants = MeetingParticipant.objects.filter(meeting=self.meeting)
        self.assertEqual(meeting_participants.count(), 4)
        
        # Verify exact match
        alice_participant = meeting_participants.get(email='alice@techcorp.com')
        self.assertEqual(alice_participant.matched_lead, self.existing_leads[0])
        self.assertEqual(alice_participant.match_confidence, 1.0)
        
        # Verify new lead was created
        charlie_participant = meeting_participants.get(email='charlie@newcompany.com')
        self.assertIsNotNone(charlie_participant.matched_lead)
        self.assertEqual(charlie_participant.matched_lead.first_name, 'Charlie')
        self.assertEqual(charlie_participant.matched_lead.last_name, 'Brown')
        
        # Verify lead statistics were updated
        self.existing_leads[0].refresh_from_db()
        self.assertEqual(self.existing_leads[0].meeting_count, 1)
        self.assertIsNotNone(self.existing_leads[0].last_meeting_date)
    
    def test_verification_workflow_integration(self):
        """Test integration with verification workflow"""
        # Create a participant that should require verification
        participants = [
            {
                'email': 'ambiguous@company.com',
                'name': 'Alice Smith',  # Similar to existing leads but different email/company
                'company': 'Different Company'
            }
        ]
        
        analysis_service = ParticipantAnalysisService()
        results = analysis_service.analyze_meeting_participants(
            str(self.meeting.id), participants, use_linkedin_enhancement=False
        )
        
        # Should have created verification requests if confidence is low
        if results['manual_verification_required'] > 0:
            verification_requests = VerificationRequest.objects.filter(
                meeting_participant__meeting=self.meeting
            )
            self.assertGreater(verification_requests.count(), 0)
            
            # Test verification approval
            verification_request = verification_requests.first()
            verification_request.approve_new_lead_creation(
                self.user, "Approved new lead creation"
            )
            
            # Verify new lead was created
            meeting_participant = verification_request.meeting_participant
            meeting_participant.refresh_from_db()
            self.assertIsNotNone(meeting_participant.matched_lead)
            self.assertFalse(meeting_participant.manual_verification_required)