from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User
from django.core.cache import cache
from unittest.mock import Mock, patch, MagicMock
from .models import AISession, AIInteraction
from .services import AIAssistantService
from meetings.tests import MeetingFactory
import factory
import json


class AISessionFactory(factory.django.DjangoModelFactory):
    """Factory for creating AISession test instances"""
    
    class Meta:
        model = AISession
    
    session_id = factory.Faker('uuid4')
    meeting_id = factory.Faker('random_int', min=1, max=1000)
    lead_context = factory.LazyFunction(lambda: {'name': 'Test Lead', 'company': 'Test Corp'})
    is_active = True


class AIInteractionFactory(factory.django.DjangoModelFactory):
    """Factory for creating AIInteraction test instances"""
    
    class Meta:
        model = AIInteraction
    
    session = factory.SubFactory(AISessionFactory)
    interaction_type = 'question_suggestion'
    input_data = factory.LazyFunction(lambda: {'context': 'test context'})
    output_data = factory.LazyFunction(lambda: {'questions': ['Test question?']})
    processing_time = 0.5
    success = True


class AISessionModelTest(TestCase):
    """Test cases for AISession model"""
    
    def test_ai_session_creation(self):
        """Test creating a valid AI session"""
        session = AISessionFactory()
        self.assertTrue(isinstance(session, AISession))
        self.assertTrue(session.is_active)
        self.assertIsNotNone(session.created_at)
    
    def test_ai_session_str_representation(self):
        """Test string representation of AI session"""
        session = AISessionFactory(session_id='test-123', meeting_id=456)
        expected = "AI Session test-123 - Meeting 456"
        self.assertEqual(str(session), expected)
    
    def test_ai_session_default_values(self):
        """Test default values for AI session"""
        session = AISession.objects.create(
            session_id='test-session',
            meeting_id=1
        )
        self.assertEqual(session.lead_context, {})
        self.assertEqual(session.conversation_history, [])
        self.assertTrue(session.is_active)


class AIInteractionModelTest(TestCase):
    """Test cases for AIInteraction model"""
    
    def test_ai_interaction_creation(self):
        """Test creating a valid AI interaction"""
        interaction = AIInteractionFactory()
        self.assertTrue(isinstance(interaction, AIInteraction))
        self.assertTrue(interaction.success)
        self.assertIsNotNone(interaction.created_at)
    
    def test_ai_interaction_str_representation(self):
        """Test string representation of AI interaction"""
        interaction = AIInteractionFactory(interaction_type='question_suggestion')
        self.assertIn('question_suggestion', str(interaction))
    
    def test_ai_interaction_types(self):
        """Test different interaction types"""
        types = ['question_suggestion', 'note_processing', 'action_extraction', 'summary_generation']
        for interaction_type in types:
            interaction = AIInteractionFactory(interaction_type=interaction_type)
            self.assertEqual(interaction.interaction_type, interaction_type)


class AIAssistantServiceTest(TestCase):
    """Test cases for AIAssistantService"""
    
    def setUp(self):
        """Set up test data"""
        self.service = AIAssistantService()
        self.meeting_id = 1
        self.lead_context = {
            'name': 'John Doe',
            'company': 'Test Corp',
            'email': 'john@testcorp.com',
            'status': 'qualified',
            'source': 'website'
        }
    
    def tearDown(self):
        """Clean up cache after each test"""
        cache.clear()
    
    def test_service_initialization(self):
        """Test AIAssistantService initialization"""
        service = AIAssistantService()
        self.assertIsNotNone(service)
        self.assertEqual(service.model_name, 'gemini-pro')
    
    @override_settings(GEMINI_API_KEY='')
    def test_service_without_api_key(self):
        """Test service behavior without API key"""
        service = AIAssistantService()
        self.assertFalse(service.is_available())
    
    @override_settings(GEMINI_API_KEY='test-key')
    @patch('ai_assistant.services.genai')
    def test_service_with_api_key(self, mock_genai):
        """Test service behavior with API key"""
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = AIAssistantService()
        service._initialize_client()
        
        mock_genai.configure.assert_called_with(api_key='test-key')
        mock_genai.GenerativeModel.assert_called_with('gemini-pro')
    
    def test_initialize_session(self):
        """Test AI session initialization"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        self.assertIsInstance(session, AISession)
        self.assertEqual(session.meeting_id, self.meeting_id)
        self.assertEqual(session.lead_context, self.lead_context)
        self.assertTrue(session.is_active)
        
        # Check cache
        cache_key = f"ai_session_{session.session_id}"
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data['meeting_id'], self.meeting_id)
    
    def test_generate_fallback_questions(self):
        """Test fallback question generation"""
        questions = self.service._generate_fallback_questions('opening')
        
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
        self.assertIn('How has your business been performing', questions[0])
    
    def test_generate_questions_without_ai(self):
        """Test question generation without AI"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        questions = self.service.generate_questions(
            session.session_id, 
            'We are discussing business challenges',
            'discovery'
        )
        
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
        
        # Check interaction logging
        interactions = AIInteraction.objects.filter(session=session)
        self.assertEqual(interactions.count(), 1)
        self.assertEqual(interactions.first().interaction_type, 'question_suggestion')
    
    @override_settings(GEMINI_API_KEY='test-key')
    @patch('ai_assistant.services.genai')
    def test_generate_questions_with_ai(self, mock_genai):
        """Test question generation with AI"""
        # Mock AI response
        mock_response = Mock()
        mock_response.text = "What are your main challenges?\nHow can we help you?\nWhat's your timeline?"
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = AIAssistantService()
        session = service.initialize_session(self.meeting_id, self.lead_context)
        
        questions = service.generate_questions(
            session.session_id,
            'We are discussing business challenges',
            'discovery'
        )
        
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), 3)
        self.assertIn('What are your main challenges?', questions)
    
    def test_extract_fallback_action_items(self):
        """Test fallback action item extraction"""
        meeting_notes = "We need to follow up with the proposal and send documentation"
        
        action_items = self.service._extract_fallback_action_items(meeting_notes)
        
        self.assertIsInstance(action_items, list)
        self.assertGreater(len(action_items), 0)
        self.assertIn('follow up', action_items[0]['description'].lower())
    
    def test_extract_action_items_without_ai(self):
        """Test action item extraction without AI"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        meeting_notes = "We discussed the project and need to follow up next week"
        
        action_items = self.service.extract_action_items(session.session_id, meeting_notes)
        
        self.assertIsInstance(action_items, list)
        
        # Check interaction logging
        interactions = AIInteraction.objects.filter(
            session=session, 
            interaction_type='action_extraction'
        )
        self.assertEqual(interactions.count(), 1)
    
    @override_settings(GEMINI_API_KEY='test-key')
    @patch('ai_assistant.services.genai')
    def test_extract_action_items_with_ai(self, mock_genai):
        """Test action item extraction with AI"""
        # Mock AI response
        mock_response = Mock()
        mock_response.text = json.dumps([
            {
                'description': 'Send proposal by Friday',
                'assignee': 'Sales Rep',
                'due_date': '2024-01-15'
            }
        ])
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = AIAssistantService()
        session = service.initialize_session(self.meeting_id, self.lead_context)
        
        action_items = service.extract_action_items(
            session.session_id,
            "We discussed the proposal and I need to send it by Friday"
        )
        
        self.assertIsInstance(action_items, list)
        self.assertEqual(len(action_items), 1)
        self.assertEqual(action_items[0]['description'], 'Send proposal by Friday')
    
    def test_generate_fallback_summary(self):
        """Test fallback summary generation"""
        transcript = "This is a test meeting transcript"
        notes = "Additional notes"
        
        summary = self.service._generate_fallback_summary(transcript, notes)
        
        self.assertIsInstance(summary, str)
        self.assertIn('Meeting Summary', summary)
        self.assertIn('characters', summary)
    
    def test_generate_summary_without_ai(self):
        """Test summary generation without AI"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        summary = self.service.generate_summary(
            session.session_id,
            "This is a test meeting transcript",
            "Additional notes"
        )
        
        self.assertIsInstance(summary, str)
        self.assertIn('Meeting Summary', summary)
        
        # Check interaction logging
        interactions = AIInteraction.objects.filter(
            session=session,
            interaction_type='summary_generation'
        )
        self.assertEqual(interactions.count(), 1)
    
    @override_settings(GEMINI_API_KEY='test-key')
    @patch('ai_assistant.services.genai')
    def test_generate_summary_with_ai(self, mock_genai):
        """Test summary generation with AI"""
        # Mock AI response
        mock_response = Mock()
        mock_response.text = "Meeting Summary: Discussed project requirements and timeline."
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = AIAssistantService()
        session = service.initialize_session(self.meeting_id, self.lead_context)
        
        summary = service.generate_summary(
            session.session_id,
            "This is a test meeting transcript",
            "Additional notes"
        )
        
        self.assertEqual(summary, "Meeting Summary: Discussed project requirements and timeline.")
    
    def test_format_lead_context(self):
        """Test lead context formatting"""
        formatted = self.service._format_lead_context(self.lead_context)
        
        self.assertIn('Contact: John Doe', formatted)
        self.assertIn('Company: Test Corp', formatted)
        self.assertIn('Email: john@testcorp.com', formatted)
    
    def test_format_empty_lead_context(self):
        """Test formatting empty lead context"""
        formatted = self.service._format_lead_context({})
        self.assertEqual(formatted, "No lead information available")
    
    def test_get_session_data_from_cache(self):
        """Test getting session data from cache"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        # Data should be in cache
        session_data = self.service._get_session_data(session.session_id)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data['meeting_id'], self.meeting_id)
    
    def test_get_session_data_from_database(self):
        """Test getting session data from database when not in cache"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        # Clear cache
        cache.clear()
        
        # Should fallback to database
        session_data = self.service._get_session_data(session.session_id)
        self.assertIsNotNone(session_data)
        self.assertEqual(session_data['meeting_id'], self.meeting_id)
    
    def test_get_nonexistent_session_data(self):
        """Test getting data for nonexistent session"""
        session_data = self.service._get_session_data('nonexistent-session')
        self.assertIsNone(session_data)
    
    def test_end_session(self):
        """Test ending AI session"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        # End session
        self.service.end_session(session.session_id)
        
        # Check database
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        
        # Check cache cleared
        cache_key = f"ai_session_{session.session_id}"
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)
    
    def test_log_interaction(self):
        """Test interaction logging"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        self.service._log_interaction(
            session.session_id,
            'test_interaction',
            {'input': 'test'},
            {'output': 'test'},
            1.5,
            True,
            ''
        )
        
        interactions = AIInteraction.objects.filter(session=session)
        self.assertEqual(interactions.count(), 1)
        
        interaction = interactions.first()
        self.assertEqual(interaction.interaction_type, 'test_interaction')
        self.assertEqual(interaction.processing_time, 1.5)
        self.assertTrue(interaction.success)
    
    def test_error_handling_in_questions(self):
        """Test error handling in question generation"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        # Test with invalid session
        questions = self.service.generate_questions(
            'invalid-session',
            'test context',
            'general'
        )
        
        # Should return fallback questions
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
    
    def test_analyze_conversation_context(self):
        """Test conversation context analysis"""
        conversation = "We've been struggling with our sales process and revenue growth. What tools do you recommend?"
        
        analysis = self.service.analyze_conversation_context(conversation)
        
        self.assertIn('topics', analysis)
        self.assertIn('pain_points', analysis)
        self.assertIn('questions_asked', analysis)
        self.assertIn('sales', analysis['topics'])
        self.assertIn('revenue', analysis['topics'])
        self.assertIn('struggle', analysis['pain_points'])
        self.assertEqual(analysis['questions_asked'], 1)
    
    def test_determine_meeting_stage(self):
        """Test meeting stage determination"""
        # Opening stage conversation
        opening_context = "Hi, nice to meet you. Can you tell me about your background?"
        stage = self.service.determine_meeting_stage(opening_context)
        self.assertEqual(stage, 'opening')
        
        # Discovery stage conversation
        discovery_context = "Tell me about your current process. How do you handle sales? What tools are you using? What challenges do you face?"
        stage = self.service.determine_meeting_stage(discovery_context)
        self.assertEqual(stage, 'discovery')
        
        # Closing stage conversation
        closing_context = "This sounds great. What are the next steps? What's the timeline for implementation?"
        stage = self.service.determine_meeting_stage(closing_context)
        self.assertEqual(stage, 'closing')
    
    def test_enhanced_fallback_questions_with_context(self):
        """Test enhanced fallback questions with context analysis"""
        context_analysis = {
            'topics': ['revenue', 'team'],
            'pain_points': ['struggling'],
            'interests': ['interested'],
            'questions_asked': 2
        }
        
        questions = self.service._generate_fallback_questions('discovery', context_analysis)
        
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 4)  # Should have enhanced questions
        
        # Check for context-specific questions
        questions_text = ' '.join(questions).lower()
        self.assertTrue(any('revenue' in q.lower() or 'team' in q.lower() for q in questions))
    
    def test_conversation_analysis_empty_context(self):
        """Test conversation analysis with empty context"""
        analysis = self.service.analyze_conversation_context("")
        
        self.assertEqual(analysis['topics'], [])
        self.assertEqual(analysis['questions_asked'], 0)
        self.assertEqual(analysis['pain_points'], [])
        self.assertEqual(analysis['interests'], [])
    
    def test_process_meeting_transcript(self):
        """Test meeting transcript processing with speaker identification"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        transcript = """
        John: Hello everyone, thanks for joining today's meeting.
        Sarah: Hi John, happy to be here. What's on the agenda?
        John: We need to discuss the new project timeline and deliverables.
        Sarah: That sounds important. I have some concerns about the current schedule.
        """
        
        result = self.service.process_meeting_transcript(session.session_id, transcript, True)
        
        self.assertIn('speakers', result)
        self.assertIn('structured_notes', result)
        self.assertIn('key_points', result)
        self.assertIn('decisions', result)
        
        # Check speakers were identified
        speakers = result['speakers']
        self.assertGreater(len(speakers), 0)
        speaker_names = [s['name'] for s in speakers]
        self.assertIn('John', speaker_names)
        self.assertIn('Sarah', speaker_names)
        
        # Check structured notes
        structured_notes = result['structured_notes']
        self.assertGreater(len(structured_notes), 0)
        self.assertTrue(any('John' in note['speaker'] for note in structured_notes))
    
    def test_identify_speakers(self):
        """Test speaker identification from transcript"""
        transcript = """
        John Smith: Welcome to the meeting.
        SARAH: Thank you for having me.
        [Mike Johnson]: I have some questions.
        """
        
        speakers = self.service._identify_speakers(transcript)
        
        self.assertGreater(len(speakers), 0)
        speaker_names = [s['name'] for s in speakers]
        self.assertIn('John Smith', speaker_names)
        self.assertIn('SARAH', speaker_names)
        self.assertIn('Mike Johnson', speaker_names)
    
    def test_extract_key_points(self):
        """Test key point extraction from transcript"""
        transcript = """
        This is an important decision we need to make.
        The key issue is our budget constraints.
        Our main goal is to increase revenue by 20%.
        We also discussed some minor details.
        """
        
        key_points = self.service._extract_key_points(transcript)
        
        self.assertIsInstance(key_points, list)
        self.assertGreater(len(key_points), 0)
        
        # Should contain lines with importance indicators
        key_points_text = ' '.join(key_points).lower()
        self.assertTrue(any(word in key_points_text for word in ['important', 'key', 'main']))
    
    def test_extract_decisions(self):
        """Test decision extraction from transcript"""
        transcript = """
        We decided to move forward with the project.
        The team agreed on the new timeline.
        Let's schedule a follow-up meeting next week.
        We also discussed some other topics.
        """
        
        decisions = self.service._extract_decisions(transcript)
        
        self.assertIsInstance(decisions, list)
        self.assertGreater(len(decisions), 0)
        
        # Should contain lines with decision indicators
        decisions_text = ' '.join(decisions).lower()
        self.assertTrue(any(word in decisions_text for word in ['decided', 'agreed', 'let\'s']))
    
    def test_extract_questions_from_transcript(self):
        """Test question extraction from transcript"""
        transcript = """
        What is our budget for this project?
        How long will the implementation take?
        This is a statement.
        Who will be responsible for testing?
        """
        
        questions = self.service._extract_questions_from_transcript(transcript)
        
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), 3)  # Should find 3 questions
        
        for question in questions:
            self.assertTrue(question.endswith('?'))
    
    def test_extract_action_items_from_transcript(self):
        """Test enhanced action item extraction from transcript"""
        session = self.service.initialize_session(self.meeting_id, self.lead_context)
        
        transcript = """
        John: I will send the proposal by Friday.
        Sarah: Can you please review the documents?
        John: Let's schedule a follow-up meeting next week.
        """
        
        action_items = self.service.extract_action_items_from_transcript(session.session_id, transcript)
        
        self.assertIsInstance(action_items, list)
        self.assertGreater(len(action_items), 0)
        
        # Check action item structure
        for item in action_items:
            self.assertIn('description', item)
            self.assertIn('assignee', item)
            self.assertIn('priority', item)
    
    def test_structure_notes_by_speaker(self):
        """Test structuring notes by speaker"""
        transcript = """
        John: Hello everyone.
        Sarah: Hi John, how are you?
        John: I'm doing well, thanks for asking.
        """
        
        speakers = [
            {'id': 'speaker_1', 'name': 'John', 'role': 'host'},
            {'id': 'speaker_2', 'name': 'Sarah', 'role': 'participant'}
        ]
        
        structured_notes = self.service._structure_notes_by_speaker(transcript, speakers)
        
        self.assertIsInstance(structured_notes, list)
        self.assertGreater(len(structured_notes), 0)
        
        # Check that speakers are correctly identified
        speakers_in_notes = [note['speaker'] for note in structured_notes]
        self.assertIn('John', speakers_in_notes)
        self.assertIn('Sarah', speakers_in_notes)


class AIAssistantAPITest(APITestCase):
    """Test cases for AI Assistant API endpoints"""
    
    def setUp(self):
        """Set up test user and authentication"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
    
    def test_initialize_ai_session_endpoint(self):
        """Test POST /api/ai/initialize/"""
        meeting = MeetingFactory()
        data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        response = self.client.post('/api/ai/initialize/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(AISession.objects.count(), 1)
    
    def test_initialize_ai_session_invalid_meeting(self):
        """Test initialize with invalid meeting ID"""
        data = {
            'meeting_id': 99999,
            'lead_context': {}
        }
        response = self.client.post('/api/ai/initialize/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_generate_questions_endpoint(self):
        """Test POST /api/ai/questions/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        data = {
            'session_id': session_id,
            'conversation_context': 'We are discussing business challenges',
            'meeting_stage': 'discovery'
        }
        response = self.client.post('/api/ai/questions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('questions', response.data)
        self.assertIsInstance(response.data['questions'], list)
    
    def test_generate_questions_invalid_data(self):
        """Test generate questions with invalid data"""
        data = {}  # Missing required fields
        response = self.client.post('/api/ai/questions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
    
    def test_process_notes_endpoint(self):
        """Test POST /api/ai/notes/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        data = {
            'session_id': session_id,
            'meeting_notes': 'We discussed the project timeline and need to follow up next week',
            'extract_action_items': True
        }
        response = self.client.post('/api/ai/notes/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('processed_notes', response.data)
        self.assertIn('action_items', response.data)
    
    def test_generate_summary_endpoint(self):
        """Test POST /api/ai/summary/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        data = {
            'session_id': session_id,
            'meeting_transcript': 'This is a sample meeting transcript with discussion points',
            'meeting_notes': 'Additional notes from the meeting'
        }
        response = self.client.post('/api/ai/summary/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('summary', response.data)
        self.assertIn('word_count', response.data)
    
    def test_ai_endpoints_require_authentication(self):
        """Test that AI endpoints require authentication"""
        self.client.force_authenticate(user=None)
        
        endpoints = [
            '/api/ai/initialize/',
            '/api/ai/questions/',
            '/api/ai/notes/',
            '/api/ai/summary/'
        ]
        
        for endpoint in endpoints:
            response = self.client.post(endpoint, {})
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_end_ai_session_endpoint(self):
        """Test POST /api/ai/end-session/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        # End the session
        data = {'session_id': session_id}
        response = self.client.post('/api/ai/end-session/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify session is inactive
        session = AISession.objects.get(session_id=session_id)
        self.assertFalse(session.is_active)
    
    def test_end_ai_session_missing_session_id(self):
        """Test end session without session_id"""
        response = self.client.post('/api/ai/end-session/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
    
    def test_analyze_conversation_endpoint(self):
        """Test POST /api/ai/analyze/"""
        data = {
            'conversation_context': 'We are struggling with our sales process and need better tools'
        }
        response = self.client.post('/api/ai/analyze/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('analysis', response.data)
        
        analysis = response.data['analysis']
        self.assertIn('topics', analysis)
        self.assertIn('pain_points', analysis)
        self.assertIn('sales', analysis['topics'])
    
    def test_analyze_conversation_missing_context(self):
        """Test analyze conversation without context"""
        response = self.client.post('/api/ai/analyze/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
    
    def test_stream_questions_endpoint(self):
        """Test POST /api/ai/questions/stream/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        data = {
            'session_id': session_id,
            'conversation_context': 'We are discussing business challenges',
            'meeting_stage': 'discovery'
        }
        response = self.client.post('/api/ai/questions/stream/', data, format='json')
        
        # For streaming response, we expect 200 status and event-stream content type
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
    
    def test_enhanced_question_generation_with_context(self):
        """Test enhanced question generation with conversation context"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        # Test with rich conversation context
        data = {
            'session_id': session_id,
            'conversation_context': 'We have been struggling with our revenue growth and our sales team is having challenges with the current process. We are interested in automation solutions.',
            'meeting_stage': 'discovery'
        }
        response = self.client.post('/api/ai/questions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        questions = response.data['questions']
        self.assertIsInstance(questions, list)
        self.assertGreater(len(questions), 0)
        
        # Questions should be contextually relevant
        questions_text = ' '.join(questions).lower()
        # Should contain context-relevant terms
        self.assertTrue(any(term in questions_text for term in ['revenue', 'sales', 'process', 'team', 'automation']))
    
    def test_process_transcript_endpoint(self):
        """Test POST /api/ai/transcript/process/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        transcript = """
        John: Welcome to our meeting today.
        Sarah: Thank you, I'm excited to discuss the project.
        John: Let's start with the requirements.
        """
        
        data = {
            'session_id': session_id,
            'transcript': transcript,
            'identify_speakers': True
        }
        response = self.client.post('/api/ai/transcript/process/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        result = response.data['result']
        self.assertIn('speakers', result)
        self.assertIn('structured_notes', result)
        self.assertIn('key_points', result)
        self.assertIn('decisions', result)
    
    def test_extract_action_items_from_transcript_endpoint(self):
        """Test POST /api/ai/transcript/actions/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        transcript = """
        John: I will send the proposal by Friday.
        Sarah: Please review the documents and provide feedback.
        John: Let's schedule a follow-up meeting next week.
        """
        
        data = {
            'session_id': session_id,
            'transcript': transcript
        }
        response = self.client.post('/api/ai/transcript/actions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        action_items = response.data['action_items']
        self.assertIsInstance(action_items, list)
        self.assertGreater(len(action_items), 0)
        
        # Check action item structure
        for item in action_items:
            self.assertIn('description', item)
            self.assertIn('assignee', item)
    
    def test_generate_comprehensive_summary_endpoint(self):
        """Test POST /api/ai/summary/comprehensive/"""
        # First create a session
        meeting = MeetingFactory()
        session_data = {
            'meeting_id': meeting.id,
            'lead_context': {'name': 'Test Lead', 'company': 'Test Corp'}
        }
        session_response = self.client.post('/api/ai/initialize/', session_data, format='json')
        session_id = session_response.data['session']['session_id']
        
        transcript = """
        John: Welcome to our important meeting today.
        Sarah: Thank you. What are the key objectives?
        John: We decided to move forward with the project.
        Sarah: I will prepare the documentation by next week.
        """
        
        data = {
            'session_id': session_id,
            'transcript': transcript,
            'include_action_items': True,
            'include_decisions': True,
            'include_key_points': True
        }
        response = self.client.post('/api/ai/summary/comprehensive/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        summary = response.data['comprehensive_summary']
        self.assertIn('summary', summary)
        self.assertIn('speakers', summary)
        self.assertIn('key_points', summary)
        self.assertIn('decisions', summary)
        self.assertIn('action_items', summary)
        self.assertIn('questions_raised', summary)
    
    def test_transcript_endpoints_missing_session_id(self):
        """Test transcript endpoints without session_id"""
        endpoints = [
            '/api/ai/transcript/process/',
            '/api/ai/transcript/actions/',
            '/api/ai/summary/comprehensive/'
        ]
        
        for endpoint in endpoints:
            data = {'transcript': 'Test transcript'}
            response = self.client.post(endpoint, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(response.data['success'])
    
    def test_transcript_endpoints_missing_transcript(self):
        """Test transcript endpoints without transcript"""
        endpoints = [
            '/api/ai/transcript/process/',
            '/api/ai/transcript/actions/',
            '/api/ai/summary/comprehensive/'
        ]
        
        for endpoint in endpoints:
            data = {'session_id': 'test-session'}
            response = self.client.post(endpoint, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(response.data['success'])