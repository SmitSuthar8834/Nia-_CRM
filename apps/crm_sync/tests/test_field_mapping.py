"""
Unit tests for CRM field mapping and data update functionality
"""
import uuid
from decimal import Decimal
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from apps.crm_sync.field_mapping import FieldMappingService, DataConflictDetector
from apps.crm_sync.update_service import CRMUpdateService, OpportunityProgressionTracker
from apps.crm_sync.models import CreatioSync, SyncConflict, CreatioConfiguration
from apps.leads.models import Lead, ActionItem, CompetitiveIntelligence, LeadNote
from apps.meetings.models import Meeting, MeetingParticipant
from apps.debriefings.models import DebriefingSession


class FieldMappingServiceTest(TestCase):
    """Test field mapping service functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new',
            qualification_score=50
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        self.service = FieldMappingService()
    
    def test_load_default_field_mappings(self):
        """Test loading default field mappings"""
        lead_mapping = self.service._get_default_lead_mapping()
        
        self.assertIn('first_name', lead_mapping)
        self.assertIn('email', lead_mapping)
        self.assertEqual(lead_mapping['first_name'], 'Name')
        self.assertEqual(lead_mapping['email'], 'Email')
    
    def test_parse_budget_amount(self):
        """Test budget amount parsing"""
        # Test various budget formats
        self.assertEqual(self.service._parse_budget_amount('50000'), Decimal('50000'))
        self.assertEqual(self.service._parse_budget_amount('$50,000'), Decimal('50000'))
        self.assertEqual(self.service._parse_budget_amount('50k'), Decimal('50000'))
        self.assertEqual(self.service._parse_budget_amount('1.5 million'), Decimal('1500000'))
        self.assertIsNone(self.service._parse_budget_amount('invalid'))
    
    def test_parse_date(self):
        """Test date parsing"""
        # Test various date formats
        self.assertEqual(self.service._parse_date('2024-12-31'), date(2024, 12, 31))
        self.assertEqual(self.service._parse_date('12/31/2024'), date(2024, 12, 31))
        self.assertEqual(self.service._parse_date('December 31, 2024'), date(2024, 12, 31))
        self.assertIsNone(self.service._parse_date('invalid date'))
    
    def test_map_extracted_data_to_lead_contact_info(self):
        """Test mapping contact information from extracted data"""
        extracted_data = {
            'contacts': [{
                'name': 'Jane Smith',
                'title': 'VP Sales',
                'company': 'New Company',
                'confidence': 0.9
            }],
            'overall_confidence': 0.8
        }
        
        result = self.service.map_extracted_data_to_lead(
            extracted_data, self.lead, self.meeting
        )
        
        self.assertIn('mapped_data', result)
        self.assertIn('changes_made', result)
        
        mapped_data = result['mapped_data']
        self.assertEqual(mapped_data.get('title'), 'VP Sales')
        self.assertEqual(mapped_data.get('company'), 'New Company')
        self.assertIn('title', result['changes_made'])
    
    def test_map_extracted_data_to_lead_deal_info(self):
        """Test mapping deal information from extracted data"""
        extracted_data = {
            'deal_information': {
                'budget': {
                    'amount': '$100,000',
                    'confidence': 0.8
                },
                'timeline': {
                    'decision_date': '2024-06-30',
                    'confidence': 0.9
                },
                'decision_makers': [{
                    'name': 'John CEO',
                    'role_in_decision': 'final_decision_maker'
                }]
            }
        }
        
        result = self.service.map_extracted_data_to_lead(
            extracted_data, self.lead, self.meeting
        )
        
        mapped_data = result['mapped_data']
        self.assertEqual(mapped_data.get('estimated_budget'), Decimal('100000'))
        self.assertEqual(mapped_data.get('estimated_close_date'), date(2024, 6, 30))
        self.assertEqual(mapped_data.get('decision_authority'), 'decision_maker')
    
    def test_calculate_qualification_updates(self):
        """Test qualification score calculation"""
        extracted_data = {
            'deal_information': {
                'budget': {'amount': '50000'},
                'timeline': {'decision_date': '2024-06-30'},
                'decision_makers': [{'role_in_decision': 'final_decision_maker'}],
                'requirements': ['Feature A', 'Feature B']
            },
            'meeting_outcome': {
                'overall_sentiment': 'positive',
                'customer_interest_level': 'high'
            }
        }
        
        score_update = self.service._calculate_qualification_updates(extracted_data, self.lead)
        
        # Should get points for budget (15) + timeline (10) + decision maker (20) + requirements (10) + sentiment (5) + interest (10)
        expected_score = 15 + 10 + 20 + 10 + 5 + 10
        self.assertEqual(score_update, expected_score)
    
    def test_create_opportunity_from_meeting(self):
        """Test opportunity creation from meeting data"""
        extracted_data = {
            'deal_information': {
                'budget': {'amount': '75000'},
                'timeline': {'decision_date': '2024-08-15'}
            },
            'meeting_outcome': {
                'customer_interest_level': 'high',
                'likelihood_to_proceed': 'high',
                'confidence_level': 0.85
            }
        }
        
        result = self.service.create_opportunity_from_meeting(
            self.lead, self.meeting, extracted_data
        )
        
        self.assertIsNotNone(result)
        self.assertIn('opportunity_data', result)
        self.assertIn('confidence', result)
        
        opp_data = result['opportunity_data']
        self.assertEqual(opp_data['Amount'], Decimal('75000'))
        self.assertEqual(opp_data['DueDate'], date(2024, 8, 15))
        self.assertGreater(opp_data['Probability'], 50)


class DataConflictDetectorTest(TestCase):
    """Test data conflict detection functionality"""
    
    def setUp(self):
        self.detector = DataConflictDetector()
        self.field_mapping = {
            'first_name': 'Name',
            'last_name': 'Surname',
            'email': 'Email',
            'company': 'AccountName'
        }
    
    def test_detect_conflicts_value_mismatch(self):
        """Test detection of value mismatches"""
        local_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'company': 'Local Company'
        }
        
        creatio_data = {
            'Name': 'John',
            'Surname': 'Doe',
            'Email': 'john.doe@example.com',
            'AccountName': 'Creatio Company'
        }
        
        conflicts = self.detector.detect_conflicts(
            local_data, creatio_data, self.field_mapping
        )
        
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict['field_name'], 'company')
        self.assertEqual(conflict['local_value'], 'Local Company')
        self.assertEqual(conflict['creatio_value'], 'Creatio Company')
        self.assertEqual(conflict['conflict_type'], 'value_mismatch')
    
    def test_detect_conflicts_missing_values(self):
        """Test detection of missing values"""
        local_data = {
            'first_name': 'John',
            'last_name': None,
            'email': 'john.doe@example.com'
        }
        
        creatio_data = {
            'Name': 'John',
            'Surname': 'Doe',
            'Email': 'john.doe@example.com'
        }
        
        conflicts = self.detector.detect_conflicts(
            local_data, creatio_data, self.field_mapping
        )
        
        self.assertEqual(len(conflicts), 1)
        conflict = conflicts[0]
        self.assertEqual(conflict['field_name'], 'last_name')
        self.assertEqual(conflict['conflict_type'], 'local_missing')
    
    def test_assess_conflict_severity(self):
        """Test conflict severity assessment"""
        # Critical field
        severity = self.detector._assess_conflict_severity('email', 'old@example.com', 'new@example.com')
        self.assertEqual(severity, 'high')
        
        # Important field
        severity = self.detector._assess_conflict_severity('phone', '123-456-7890', '098-765-4321')
        self.assertEqual(severity, 'medium')
        
        # Low priority field
        severity = self.detector._assess_conflict_severity('notes', 'old note', 'new note')
        self.assertEqual(severity, 'low')
    
    def test_create_conflict_resolution_workflow(self):
        """Test conflict resolution workflow creation"""
        conflicts = [
            {
                'field_name': 'company',
                'local_value': 'Local Co',
                'creatio_value': 'Creatio Co',
                'conflict_type': 'value_mismatch',
                'severity': 'medium'
            },
            {
                'field_name': 'notes',
                'local_value': 'Local note',
                'creatio_value': None,
                'conflict_type': 'creatio_missing',
                'severity': 'low'
            }
        ]
        
        workflow = self.detector.create_conflict_resolution_workflow(
            conflicts, 'lead', str(uuid.uuid4())
        )
        
        self.assertEqual(workflow['total_conflicts'], 2)
        self.assertEqual(len(workflow['auto_resolvable']), 1)  # Low severity conflict
        self.assertEqual(len(workflow['requires_review']), 1)  # Medium severity conflict


class CRMUpdateServiceTest(TestCase):
    """Test CRM update service functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new',
            qualification_score=50
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        self.participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='john.doe@example.com',
            name='John Doe',
            matched_lead=self.lead
        )
        
        self.debriefing = DebriefingSession.objects.create(
            meeting=self.meeting,
            scheduled_time=timezone.now(),
            status='completed',
            extracted_data={
                'contacts': [{
                    'name': 'John Doe',
                    'title': 'CTO',
                    'confidence': 0.9
                }],
                'deal_information': {
                    'budget': {'amount': '100000'},
                    'timeline': {'decision_date': '2024-12-31'}
                },
                'action_items': [{
                    'description': 'Send proposal',
                    'owner': 'internal',
                    'deadline': '2024-06-15',
                    'priority': 'high'
                }],
                'competitive_intelligence': [{
                    'competitor_name': 'Competitor A',
                    'context': 'Currently using their solution',
                    'threat_level': 'high'
                }]
            }
        )
        
        self.service = CRMUpdateService()
    
    @patch('apps.crm_sync.update_service.CRMUpdateService.detect_crm_conflicts')
    def test_update_lead_from_extracted_data(self, mock_detect_conflicts):
        """Test updating lead from extracted data"""
        mock_detect_conflicts.return_value = []
        
        result = self.service.update_lead_from_extracted_data(
            self.lead, self.meeting, self.debriefing.extracted_data, self.user
        )
        
        self.assertTrue(result['success'])
        self.assertIn('changes_made', result)
        
        # Verify lead was updated
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.title, 'CTO')
        self.assertEqual(self.lead.estimated_budget, Decimal('100000'))
    
    def test_create_competitive_intelligence(self):
        """Test creating competitive intelligence records"""
        result = self.service.create_competitive_intelligence(
            self.lead, self.meeting, self.debriefing.extracted_data, self.user
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['action'], 'created')
        self.assertEqual(result[0]['competitor'], 'Competitor A')
        
        # Verify record was created
        intel = CompetitiveIntelligence.objects.get(
            lead=self.lead,
            competitor_name='Competitor A'
        )
        self.assertEqual(intel.threat_level, 'high')
    
    def test_create_action_items(self):
        """Test creating action items from extracted data"""
        result = self.service.create_action_items(
            self.meeting, self.debriefing.extracted_data, self.user
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], 'Send proposal')
        self.assertEqual(result[0]['priority'], 'high')
        
        # Verify action item was created
        action_item = ActionItem.objects.get(meeting=self.meeting)
        self.assertEqual(action_item.description, 'Send proposal')
        self.assertEqual(action_item.priority, 'high')
        self.assertTrue(action_item.is_internal)
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_create_opportunity_if_warranted(self, mock_request):
        """Test opportunity creation when warranted"""
        # Mock successful opportunity creation
        mock_response = Mock()
        mock_response.json.return_value = {'Id': 'test-opportunity-id'}
        mock_request.return_value = mock_response
        
        extracted_data = {
            'deal_information': {
                'budget': {'amount': '75000'},
                'timeline': {'decision_date': '2024-08-15'}
            },
            'meeting_outcome': {
                'customer_interest_level': 'high',
                'likelihood_to_proceed': 'high',
                'confidence_level': 0.85
            }
        }
        
        result = self.service.create_opportunity_if_warranted(
            self.lead, self.meeting, extracted_data, self.user
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['opportunity_id'], 'test-opportunity-id')
        self.assertEqual(result['confidence'], 0.85)
        
        # Verify sync record was created
        sync_record = CreatioSync.objects.get(
            entity_type='opportunity',
            local_id=self.meeting.id
        )
        self.assertEqual(sync_record.creatio_id, 'test-opportunity-id')
    
    def test_process_debriefing_data(self):
        """Test processing complete debriefing data"""
        with patch('apps.crm_sync.update_service.CRMUpdateService.detect_crm_conflicts') as mock_conflicts:
            mock_conflicts.return_value = []
            
            result = self.service.process_debriefing_data(self.debriefing, self.user)
            
            self.assertTrue(result['success'])
            self.assertIn('results', result)
            
            results = result['results']
            self.assertEqual(len(results['lead_updates']), 1)
            self.assertEqual(len(results['competitive_intel']), 1)
            self.assertEqual(len(results['action_items']), 1)


class OpportunityProgressionTrackerTest(TestCase):
    """Test opportunity progression tracking"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new',
            relationship_stage='warm'
        )
        
        self.meeting = Meeting.objects.create(
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True
        )
        
        self.tracker = OpportunityProgressionTracker()
    
    def test_track_progression_positive_indicators(self):
        """Test tracking progression with positive indicators"""
        extracted_data = {
            'deal_information': {
                'budget': {'amount': '100000'},
                'timeline': {'decision_date': '2024-12-31'},
                'decision_makers': [{'role_in_decision': 'final_decision_maker'}],
                'requirements': ['Feature A', 'Feature B']
            },
            'meeting_outcome': {
                'overall_sentiment': 'positive',
                'customer_interest_level': 'high'
            }
        }
        
        result = self.tracker.track_progression(self.lead, self.meeting, extracted_data)
        
        self.assertEqual(result['previous_stage'], 'warm')
        self.assertEqual(result['new_stage'], 'hot')
        self.assertGreater(len(result['progression_indicators']), 0)
        self.assertIn('budget_discussion', [i['type'] for i in result['progression_indicators']])
    
    def test_calculate_new_stage(self):
        """Test stage calculation logic"""
        # Test progression from cold to warm
        indicators = [{'impact': 'positive'}]
        new_stage = self.tracker._calculate_new_stage(self.lead, indicators)
        self.assertEqual(new_stage, 'warm')  # Lead is already warm, so stays warm
        
        # Test progression with multiple positive indicators
        indicators = [
            {'impact': 'positive'},
            {'impact': 'positive'},
            {'impact': 'positive'}
        ]
        new_stage = self.tracker._calculate_new_stage(self.lead, indicators)
        self.assertEqual(new_stage, 'hot')
    
    def test_generate_progression_recommendations(self):
        """Test recommendation generation"""
        indicators = [
            {'type': 'budget_discussion', 'impact': 'positive'},
            {'type': 'interest_level', 'value': 'medium', 'impact': 'positive'}
        ]
        
        recommendations = self.tracker._generate_progression_recommendations(self.lead, indicators)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        # Should recommend clarifying timeline since it's missing
        timeline_rec = any('timeline' in rec.lower() for rec in recommendations)
        self.assertTrue(timeline_rec)


class IntegrationTest(TestCase):
    """Integration tests for complete CRM update workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        
        self.lead = Lead.objects.create(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            company='Test Company',
            status='new',
            qualification_score=30,
            creatio_id='test-creatio-id'
        )
        
        self.meeting = Meeting.objects.create(
            title='Discovery Meeting',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            organizer=self.user,
            is_sales_meeting=True,
            meeting_type='discovery'
        )
        
        self.participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='john.doe@example.com',
            name='John Doe',
            matched_lead=self.lead
        )
        
        self.debriefing = DebriefingSession.objects.create(
            meeting=self.meeting,
            scheduled_time=timezone.now(),
            status='completed',
            extracted_data={
                'contacts': [{
                    'name': 'John Doe',
                    'title': 'VP Engineering',
                    'company': 'Updated Company Name',
                    'confidence': 0.95
                }],
                'deal_information': {
                    'budget': {
                        'amount': '$250,000',
                        'confidence': 0.8
                    },
                    'timeline': {
                        'decision_date': '2024-09-30',
                        'confidence': 0.9
                    },
                    'decision_makers': [{
                        'name': 'John Doe',
                        'role_in_decision': 'final_decision_maker'
                    }],
                    'requirements': [
                        'Scalable architecture',
                        'API integration',
                        'Real-time analytics'
                    ]
                },
                'meeting_outcome': {
                    'overall_sentiment': 'positive',
                    'customer_interest_level': 'high',
                    'likelihood_to_proceed': 'high',
                    'summary': 'Very interested in our solution, ready to move forward'
                },
                'action_items': [
                    {
                        'description': 'Send technical architecture document',
                        'owner': 'internal',
                        'deadline': '2024-06-20',
                        'priority': 'high',
                        'commitment_level': 'firm'
                    },
                    {
                        'description': 'Schedule demo with technical team',
                        'owner': 'John Doe',
                        'deadline': '2024-06-25',
                        'priority': 'medium'
                    }
                ],
                'competitive_intelligence': [{
                    'competitor_name': 'TechCorp Solutions',
                    'context': 'Currently evaluating their platform alongside ours',
                    'strengths': ['Lower price point', 'Existing relationship'],
                    'weaknesses': ['Limited scalability', 'Poor API support'],
                    'threat_level': 'medium',
                    'relationship': 'evaluating'
                }],
                'overall_confidence': 0.87
            }
        )
    
    @patch('apps.crm_sync.adapters.CreatioAdapter._make_request')
    def test_complete_crm_update_workflow(self, mock_request):
        """Test complete CRM update workflow from debriefing to sync"""
        # Mock Creatio API responses
        def mock_api_call(method, endpoint, data=None, params=None):
            mock_response = Mock()
            if 'Lead' in endpoint and method == 'GET':
                # Return current Creatio data for conflict detection
                mock_response.json.return_value = {
                    'Id': 'test-creatio-id',
                    'Name': 'John',
                    'Surname': 'Doe',
                    'Email': 'john.doe@example.com',
                    'AccountName': 'Test Company',  # Different from extracted data
                    'JobTitle': 'Engineer',  # Different from extracted data
                    'Score': 30
                }
            elif 'Opportunity' in endpoint and method == 'POST':
                # Return created opportunity
                mock_response.json.return_value = {'Id': 'new-opportunity-id'}
            else:
                mock_response.json.return_value = {'Id': 'success'}
            
            return mock_response
        
        mock_request.side_effect = mock_api_call
        
        # Process the debriefing data
        service = CRMUpdateService()
        result = service.process_debriefing_data(self.debriefing, self.user)
        
        # Verify successful processing
        self.assertTrue(result['success'])
        results = result['results']
        
        # Check lead updates
        self.assertEqual(len(results['lead_updates']), 1)
        lead_result = results['lead_updates'][0]
        self.assertTrue(lead_result['success'])
        self.assertGreater(len(lead_result['changes_made']), 0)
        
        # Verify lead was updated
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.title, 'VP Engineering')
        self.assertEqual(self.lead.estimated_budget, Decimal('250000'))
        self.assertEqual(self.lead.decision_authority, 'decision_maker')
        self.assertGreater(self.lead.qualification_score, 30)  # Should be increased
        
        # Check competitive intelligence
        self.assertEqual(len(results['competitive_intel']), 1)
        intel = CompetitiveIntelligence.objects.get(
            lead=self.lead,
            competitor_name='TechCorp Solutions'
        )
        self.assertEqual(intel.threat_level, 'medium')
        self.assertEqual(intel.strengths_mentioned, ['Lower price point', 'Existing relationship'])
        
        # Check action items
        self.assertEqual(len(results['action_items']), 2)
        action_items = ActionItem.objects.filter(meeting=self.meeting)
        self.assertEqual(action_items.count(), 2)
        
        internal_item = action_items.filter(is_internal=True).first()
        self.assertEqual(internal_item.description, 'Send technical architecture document')
        self.assertEqual(internal_item.priority, 'high')
        self.assertTrue(internal_item.is_commitment)
        
        # Check opportunity creation
        self.assertEqual(len(results['opportunities']), 1)
        opp_result = results['opportunities'][0]
        self.assertEqual(opp_result['opportunity_id'], 'new-opportunity-id')
        
        # Verify sync records were created
        lead_sync = CreatioSync.objects.get(
            entity_type='lead',
            local_id=self.lead.id
        )
        self.assertIn(lead_sync.sync_status, ['pending', 'conflict'])
        
        # Check that notes were created
        notes = LeadNote.objects.filter(lead=self.lead)
        self.assertGreater(notes.count(), 0)
        
        ai_note = notes.filter(note_type='ai_insight').first()
        self.assertIsNotNone(ai_note)
        self.assertTrue(ai_note.ai_generated)
        self.assertEqual(ai_note.ai_confidence, 0.87)
    
    def test_conflict_detection_and_resolution(self):
        """Test conflict detection and resolution workflow"""
        # Create a scenario where local and Creatio data conflict
        service = CRMUpdateService()
        
        # Mock conflicting Creatio data
        with patch('apps.crm_sync.adapters.CreatioAdapter._make_request') as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {
                'Id': 'test-creatio-id',
                'Name': 'John',
                'Surname': 'Doe',
                'Email': 'john.doe@example.com',
                'AccountName': 'Different Company',  # Conflicts with extracted data
                'JobTitle': 'Different Title',  # Conflicts with extracted data
                'Score': 30
            }
            mock_request.return_value = mock_response
            
            # Update lead with extracted data
            result = service.update_lead_from_extracted_data(
                self.lead, self.meeting, self.debriefing.extracted_data, self.user
            )
            
            # Should detect conflicts
            self.assertTrue(result['success'])
            self.assertGreater(result.get('conflicts_detected', 0), 0)
            
            # Check that conflict records were created
            sync_record = CreatioSync.objects.get(
                entity_type='lead',
                local_id=self.lead.id
            )
            
            conflicts = SyncConflict.objects.filter(sync_record=sync_record)
            self.assertGreater(conflicts.count(), 0)
            
            # Verify sync status is set to conflict
            self.assertEqual(sync_record.sync_status, 'conflict')