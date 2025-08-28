"""
Tests for AI Engine functionality
"""
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from .models import AIPromptTemplate, AIInteraction, AICache
from .gemini_client import GeminiClient, GeminiResponse, GeminiRateLimiter, GeminiAPIKeyManager
from .services import QuestionGenerationService, DataExtractionService, AIServiceError


class GeminiClientTest(TestCase):
    """Test Gemini client functionality"""
    
    @override_settings(GEMINI_API_KEY='test-api-key')
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('apps.ai_engine.gemini_client.genai.configure')
    @patch('apps.ai_engine.gemini_client.genai.GenerativeModel')
    def test_client_initialization(self, mock_model, mock_configure):
        """Test Gemini client initialization"""
        with override_settings(GEMINI_API_KEY='test-api-key'):
            client = GeminiClient()
            
            mock_configure.assert_called_once_with(api_key='test-api-key')
            mock_model.assert_called_once_with('gemini-pro')
            self.assertIsNotNone(client._model)
    
    def test_api_key_manager_get_active_key(self):
        """Test API key manager functionality"""
        with override_settings(GEMINI_API_KEY='test-key'):
            manager = GeminiAPIKeyManager()
            self.assertEqual(manager.get_active_key(), 'test-key')
    
    def test_api_key_manager_no_key_configured(self):
        """Test API key manager with no key configured"""
        with override_settings(GEMINI_API_KEY=''):
            manager = GeminiAPIKeyManager()
            with self.assertRaises(ValueError):
                manager.get_active_key()
    
    def test_rate_limiter_can_make_request(self):
        """Test rate limiter functionality"""
        limiter = GeminiRateLimiter(requests_per_minute=2, requests_per_day=10)
        
        # Should allow initial requests
        can_request, message = limiter.can_make_request()
        self.assertTrue(can_request)
        self.assertEqual(message, "")
    
    @patch('apps.ai_engine.gemini_client.cache')
    def test_rate_limiter_exceeds_limit(self, mock_cache):
        """Test rate limiter when limit is exceeded"""
        mock_cache.get.return_value = 5  # Simulate exceeded limit
        
        limiter = GeminiRateLimiter(requests_per_minute=2, requests_per_day=10)
        can_request, message = limiter.can_make_request()
        
        self.assertFalse(can_request)
        self.assertIn("Rate limit exceeded", message)
    
    @patch('apps.ai_engine.gemini_client.genai.configure')
    @patch('apps.ai_engine.gemini_client.genai.GenerativeModel')
    def test_health_check_success(self, mock_model, mock_configure):
        """Test successful health check"""
        # Mock successful response
        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = "OK"
        mock_response.candidates[0].safety_ratings = []
        
        mock_model_instance = Mock()
        mock_model_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_model_instance
        
        with override_settings(GEMINI_API_KEY='test-key'):
            client = GeminiClient()
            health = client.health_check()
            
            self.assertEqual(health['status'], 'healthy')
            self.assertIn('response_time_ms', health)
            self.assertIn('timestamp', health)


class AIPromptTemplateTest(TestCase):
    """Test AI prompt template model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_template(self):
        """Test creating a prompt template"""
        template = AIPromptTemplate.objects.create(
            name='Test Template',
            template_type='debriefing_question',
            context='discovery',
            prompt_template='Test prompt with {variable}',
            system_prompt='System prompt',
            temperature=0.7,
            max_tokens=1000,
            created_by=self.user
        )
        
        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.template_type, 'debriefing_question')
        self.assertEqual(template.context, 'discovery')
        self.assertEqual(template.usage_count, 0)
        self.assertTrue(template.is_active)
    
    def test_increment_usage(self):
        """Test incrementing template usage"""
        template = AIPromptTemplate.objects.create(
            name='Test Template',
            template_type='debriefing_question',
            prompt_template='Test prompt',
            created_by=self.user
        )
        
        initial_count = template.usage_count
        template.increment_usage(response_time=1.5)
        
        self.assertEqual(template.usage_count, initial_count + 1)
        self.assertEqual(template.average_response_time, 1.5)


class QuestionGenerationServiceTest(TestCase):
    """Test question generation service"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test template
        self.template = AIPromptTemplate.objects.create(
            name='Test Questions',
            template_type='debriefing_question',
            context='discovery',
            prompt_template='Generate {question_count} questions for {meeting_type} meeting',
            system_prompt='You are a sales coach',
            created_by=self.user
        )
    
    @patch('apps.ai_engine.services.get_gemini_client')
    def test_generate_questions_success(self, mock_get_client):
        """Test successful question generation"""
        # Mock Gemini client response
        mock_client = Mock()
        mock_response = GeminiResponse(
            content="1. What are your main challenges?\n2. What's your budget?\n3. When do you need a solution?",
            confidence_score=0.9,
            response_time_ms=1500
        )
        mock_client.generate_response.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        service = QuestionGenerationService()
        
        meeting_context = {
            'meeting_id': 'test-123',
            'meeting_type': 'discovery',
            'title': 'Discovery Call',
            'participants': ['john@example.com'],
            'duration': '30 minutes'
        }
        
        result = service.generate_questions(meeting_context, self.user, 3)
        
        self.assertIn('questions', result)
        self.assertEqual(len(result['questions']), 3)
        self.assertEqual(result['meeting_type'], 'discovery')
        self.assertIsNotNone(result['confidence_score'])
    
    @patch('apps.ai_engine.services.get_gemini_client')
    def test_generate_questions_api_error(self, mock_get_client):
        """Test question generation with API error"""
        # Mock Gemini client error
        mock_client = Mock()
        mock_response = GeminiResponse(
            content="",
            error="API quota exceeded"
        )
        mock_client.generate_response.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        service = QuestionGenerationService()
        
        meeting_context = {
            'meeting_type': 'discovery',
            'title': 'Discovery Call',
            'participants': ['john@example.com']
        }
        
        with self.assertRaises(AIServiceError):
            service.generate_questions(meeting_context, self.user)


class DataExtractionServiceTest(TestCase):
    """Test data extraction service"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create extraction template
        self.template = AIPromptTemplate.objects.create(
            name='Data Extraction',
            template_type='data_extraction',
            context='general',
            prompt_template='Extract data from: {conversation_text}',
            created_by=self.user
        )
    
    @patch('apps.ai_engine.services.get_gemini_client')
    def test_extract_meeting_data_success(self, mock_get_client):
        """Test successful data extraction"""
        # Mock Gemini client response
        mock_client = Mock()
        mock_response = GeminiResponse(
            content="""Contacts:
- John Smith, CTO, Acme Corp, john@acme.com

Action Items:
- Send proposal by Friday (Owner: Sales Rep)
- Schedule technical demo (Owner: John Smith)

Competitive Intelligence:
- Currently using Competitor X
- Concerns about pricing

Deal Information:
- Budget: $50,000
- Timeline: Q1 implementation""",
            confidence_score=0.85,
            response_time_ms=2000
        )
        mock_client.generate_response.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        service = DataExtractionService()
        
        conversation_text = "We discussed budget of $50,000 and need implementation by Q1..."
        meeting_context = {
            'meeting_id': 'test-123',
            'meeting_type': 'discovery',
            'title': 'Discovery Call',
            'participants': ['john@acme.com']
        }
        
        result = service.extract_meeting_data(conversation_text, meeting_context, self.user)
        
        self.assertIn('extracted_data', result)
        self.assertIn('confidence_score', result)
        self.assertIsNotNone(result['interaction_id'])


class AIEngineAPITest(APITestCase):
    """Test AI Engine API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test template
        self.template = AIPromptTemplate.objects.create(
            name='Test Template',
            template_type='debriefing_question',
            context='discovery',
            prompt_template='Test prompt',
            created_by=self.user
        )
    
    @patch('apps.ai_engine.views.get_question_generation_service')
    def test_generate_questions_endpoint(self, mock_service):
        """Test question generation API endpoint"""
        # Mock service response
        mock_service_instance = Mock()
        mock_service_instance.generate_questions.return_value = {
            'questions': [
                {'id': 1, 'question': 'What are your main challenges?', 'type': 'open_ended'}
            ],
            'meeting_type': 'discovery',
            'confidence_score': 0.9
        }
        mock_service.return_value = mock_service_instance
        
        url = reverse('ai_engine:generate_questions')
        data = {
            'meeting_context': {
                'meeting_type': 'discovery',
                'title': 'Discovery Call',
                'participants': ['john@example.com']
            },
            'question_count': 5
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('questions', response.data)
        self.assertEqual(len(response.data['questions']), 1)
    
    def test_generate_questions_missing_context(self):
        """Test question generation with missing context"""
        url = reverse('ai_engine:generate_questions')
        data = {'question_count': 5}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    @patch('apps.ai_engine.views.get_ai_health_service')
    def test_health_status_endpoint(self, mock_service):
        """Test health status API endpoint"""
        # Mock health service response
        mock_service_instance = Mock()
        mock_service_instance.get_health_status.return_value = {
            'overall_status': 'healthy',
            'client_health': {'status': 'healthy'},
            'usage_stats': {'requests_today': 10}
        }
        mock_service.return_value = mock_service_instance
        
        url = reverse('ai_engine:health_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_status', response.data)
        self.assertEqual(response.data['overall_status'], 'healthy')
    
    def test_list_templates_endpoint(self):
        """Test template listing API endpoint"""
        url = reverse('ai_engine:list_templates')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('templates', response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['templates'][0]['name'], 'Test Template')
    
    def test_create_template_endpoint(self):
        """Test template creation API endpoint"""
        url = reverse('ai_engine:create_template')
        data = {
            'name': 'New Template',
            'template_type': 'data_extraction',
            'prompt_template': 'Extract data from {text}',
            'context': 'general',
            'temperature': 0.5,
            'max_tokens': 800
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['name'], 'New Template')
        
        # Verify template was created in database
        template = AIPromptTemplate.objects.get(id=response.data['id'])
        self.assertEqual(template.name, 'New Template')
        self.assertEqual(template.temperature, 0.5)
    
    def test_create_template_missing_fields(self):
        """Test template creation with missing required fields"""
        url = reverse('ai_engine:create_template')
        data = {
            'name': 'Incomplete Template'
            # Missing template_type and prompt_template
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_interaction_history_endpoint(self):
        """Test interaction history API endpoint"""
        # Create test interaction
        AIInteraction.objects.create(
            interaction_type='question_generation',
            user=self.user,
            input_data={'test': 'data'},
            formatted_prompt='Test prompt',
            status='success'
        )
        
        url = reverse('ai_engine:interaction_history')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('interactions', response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['interactions'][0]['interaction_type'], 'question_generation')


class AICacheTest(TestCase):
    """Test AI caching functionality"""
    
    def test_cache_creation(self):
        """Test creating cache entry"""
        cache_entry = AICache.objects.create(
            prompt_hash='test-hash-123',
            interaction_type='question_generation',
            cached_response='Test response',
            confidence_score=0.9,
            original_prompt='Test prompt'
        )
        
        self.assertEqual(cache_entry.prompt_hash, 'test-hash-123')
        self.assertEqual(cache_entry.hit_count, 0)
        self.assertFalse(cache_entry.is_expired)
    
    def test_cache_hit_increment(self):
        """Test incrementing cache hit count"""
        cache_entry = AICache.objects.create(
            prompt_hash='test-hash-123',
            interaction_type='question_generation',
            cached_response='Test response',
            original_prompt='Test prompt'
        )
        
        initial_hits = cache_entry.hit_count
        cache_entry.increment_hit()
        
        self.assertEqual(cache_entry.hit_count, initial_hits + 1)