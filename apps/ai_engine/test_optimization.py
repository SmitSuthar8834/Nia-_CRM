"""
Tests for AI caching and optimization features
"""
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from .models import AICache, AIInteraction, AIPromptTemplate
from .caching_optimization import (
    IntelligentCacheManager, ConversationContextOptimizer, 
    BatchProcessor, AIUsageMonitor, FallbackManager, 
    AIOptimizationService, CacheStrategy
)
from .gemini_client import GeminiResponse


class IntelligentCacheManagerTest(TestCase):
    """Test intelligent cache management"""
    
    def setUp(self):
        self.cache_manager = IntelligentCacheManager()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
    
    def test_cache_key_generation(self):
        """Test cache key generation with context"""
        prompt = "Test prompt"
        context = {"meeting_id": "123", "type": "demo"}
        
        key1 = self.cache_manager.get_cache_key(prompt, context, "question_generation")
        key2 = self.cache_manager.get_cache_key(prompt, context, "question_generation")
        key3 = self.cache_manager.get_cache_key(prompt, None, "question_generation")
        
        # Same inputs should generate same key
        self.assertEqual(key1, key2)
        
        # Different context should generate different key
        self.assertNotEqual(key1, key3)
        
        # Key should include interaction type
        self.assertTrue(key1.startswith("question_generation_"))
    
    def test_cache_response(self):
        """Test caching AI responses"""
        prompt = "Test prompt"
        response = GeminiResponse(
            content="Test response",
            confidence_score=0.8,
            cached=False
        )
        
        # Cache the response
        success = self.cache_manager.cache_response(
            prompt, response, "test", {"meeting_id": "123"}
        )
        
        self.assertTrue(success)
        
        # Verify cache entry was created
        cache_entries = AICache.objects.filter(interaction_type="test")
        self.assertEqual(cache_entries.count(), 1)
        
        cache_entry = cache_entries.first()
        self.assertEqual(cache_entry.cached_response, "Test response")
        self.assertEqual(cache_entry.confidence_score, 0.8)
    
    def test_get_cached_response(self):
        """Test retrieving cached responses"""
        prompt = "Test prompt"
        context = {"meeting_id": "123"}
        
        # Create cache entry
        cache_key = self.cache_manager.get_cache_key(prompt, context, "test")
        AICache.objects.create(
            prompt_hash=cache_key,
            interaction_type="test",
            cached_response="Cached response",
            confidence_score=0.9,
            expires_at=timezone.now() + timedelta(hours=1),
            original_prompt=prompt
        )
        
        # Retrieve cached response
        cached_response = self.cache_manager.get_cached_response(prompt, "test", context)
        
        self.assertIsNotNone(cached_response)
        self.assertEqual(cached_response.content, "Cached response")
        self.assertEqual(cached_response.confidence_score, 0.9)
        self.assertTrue(cached_response.cached)
    
    def test_prompt_similarity_calculation(self):
        """Test prompt similarity calculation"""
        prompt1 = "What were the key outcomes of the meeting?"
        prompt2 = "What were the main outcomes of the meeting?"
        prompt3 = "How is the weather today?"
        
        similarity1 = self.cache_manager._calculate_prompt_similarity(prompt1, prompt2)
        similarity2 = self.cache_manager._calculate_prompt_similarity(prompt1, prompt3)
        
        # Similar prompts should have higher similarity
        self.assertGreater(similarity1, similarity2)
        self.assertGreater(similarity1, 0.5)
        self.assertLess(similarity2, 0.3)


class ConversationContextOptimizerTest(TestCase):
    """Test conversation context optimization"""
    
    def setUp(self):
        self.optimizer = ConversationContextOptimizer()
    
    def test_optimize_context(self):
        """Test context optimization"""
        conversation_history = [
            {"question": "What was discussed?", "response": "Budget and timeline"},
            {"question": "Any concerns?", "response": "Yes, about the competitor"},
            {"question": "Next steps?", "response": "Schedule demo"}
        ]
        
        current_prompt = "Generate follow-up questions"
        meeting_context = {"meeting_type": "discovery", "participants": ["John", "Jane"]}
        
        optimized = self.optimizer.optimize_context(
            conversation_history, current_prompt, meeting_context
        )
        
        self.assertIn('conversation_summary', optimized)
        self.assertIn('key_insights', optimized)
        self.assertIn('recent_exchanges', optimized)
        self.assertIn('meeting_context', optimized)
        self.assertIn('context_optimization', optimized)
        
        # Should have optimization metrics
        opt_metrics = optimized['context_optimization']
        self.assertEqual(opt_metrics['original_length'], 3)
        self.assertLessEqual(opt_metrics['optimized_length'], 3)
    
    def test_exchange_importance_calculation(self):
        """Test exchange importance scoring"""
        # Exchange with important keywords should score higher
        important_exchange = {
            "question": "What's your budget for this project?",
            "response": "We have $100k allocated and need to decide by next month"
        }
        
        simple_exchange = {
            "question": "How are you?",
            "response": "Fine, thanks"
        }
        
        important_score = self.optimizer._calculate_exchange_importance(
            important_exchange, 1, 3
        )
        simple_score = self.optimizer._calculate_exchange_importance(
            simple_exchange, 1, 3
        )
        
        self.assertGreater(important_score, simple_score)
    
    def test_key_insights_extraction(self):
        """Test key insights extraction"""
        conversation_history = [
            {"response": "We're comparing with competitor X and need to decide by Q1"},
            {"response": "Budget is around $50k but we have some concerns about security"},
            {"response": "The technical requirements include API integration"}
        ]
        
        insights = self.optimizer._extract_key_insights(conversation_history)
        
        # Should identify key topics
        insight_text = ' '.join(insights).lower()
        self.assertTrue(any('budget' in insight or 'competition' in insight for insight in insights))


class BatchProcessorTest(TestCase):
    """Test batch processing functionality"""
    
    def setUp(self):
        self.batch_processor = BatchProcessor()
    
    @patch('apps.ai_engine.caching_optimization.get_gemini_client')
    def test_process_batch_requests(self, mock_get_client):
        """Test batch request processing"""
        # Mock client
        mock_client = Mock()
        mock_client.batch_mode.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client.batch_mode.return_value.__exit__ = Mock(return_value=None)
        mock_get_client.return_value = mock_client
        
        # Mock response
        mock_response = GeminiResponse(
            content="Test response",
            confidence_score=0.8,
            error=None
        )
        mock_client.generate_response.return_value = mock_response
        
        # Test requests
        requests = [
            {"id": "1", "prompt": "Test prompt 1"},
            {"id": "2", "prompt": "Test prompt 2"}
        ]
        
        results = self.batch_processor.process_batch_requests(requests)
        
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r['success'] for r in results))
        self.assertEqual(results[0]['request_id'], "1")
        self.assertEqual(results[1]['request_id'], "2")


class AIUsageMonitorTest(TestCase):
    """Test AI usage monitoring"""
    
    def setUp(self):
        self.monitor = AIUsageMonitor()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
    
    def test_get_usage_metrics(self):
        """Test usage metrics calculation"""
        # Create test interactions
        AIInteraction.objects.create(
            interaction_type='question_generation',
            user=self.user,
            input_data={'test': 'data'},
            formatted_prompt='Test prompt',
            status='success',
            response_time_ms=500,
            token_count=100
        )
        
        AIInteraction.objects.create(
            interaction_type='data_extraction',
            user=self.user,
            input_data={'test': 'data'},
            formatted_prompt='Test prompt 2',
            status='error',
            error_message='Test error'
        )
        
        # Create cache entry
        AICache.objects.create(
            prompt_hash='test_hash',
            interaction_type='test',
            cached_response='Test response',
            hit_count=5,
            expires_at=timezone.now() + timedelta(hours=1),
            original_prompt='Test prompt'
        )
        
        metrics = self.monitor.get_usage_metrics(7)
        
        self.assertEqual(metrics['total_interactions'], 2)
        self.assertEqual(metrics['successful_interactions'], 1)
        self.assertEqual(metrics['success_rate'], 0.5)
        self.assertEqual(metrics['total_tokens_used'], 100)
        self.assertGreater(metrics['estimated_cost_usd'], 0)
        
        # Check cache metrics
        cache_metrics = metrics['cache_metrics']
        self.assertEqual(cache_metrics['total_cache_hits'], 5)
        self.assertGreater(cache_metrics['estimated_cost_savings'], 0)


class FallbackManagerTest(TestCase):
    """Test fallback mechanisms"""
    
    def setUp(self):
        self.fallback_manager = FallbackManager()
    
    def test_get_fallback_response_question_generation(self):
        """Test fallback response for question generation"""
        response = self.fallback_manager.get_fallback_response('question_generation')
        
        self.assertIn('questions', response)
        self.assertIsInstance(response['questions'], list)
        self.assertGreater(len(response['questions']), 0)
        self.assertEqual(response['method'], 'fallback')
        self.assertIn('fallback_reason', response)
    
    def test_get_fallback_response_data_extraction(self):
        """Test fallback response for data extraction"""
        response = self.fallback_manager.get_fallback_response('data_extraction')
        
        self.assertIn('extracted_data', response)
        self.assertEqual(response['confidence_score'], 0.0)
        self.assertEqual(response['method'], 'fallback')
    
    @patch('apps.ai_engine.caching_optimization.get_gemini_client')
    def test_is_ai_service_healthy(self, mock_get_client):
        """Test AI service health check"""
        # Mock healthy service
        mock_client = Mock()
        mock_client.health_check.return_value = {'status': 'healthy'}
        mock_get_client.return_value = mock_client
        
        self.assertTrue(self.fallback_manager.is_ai_service_healthy())
        
        # Mock unhealthy service
        mock_client.health_check.return_value = {'status': 'unhealthy'}
        self.assertFalse(self.fallback_manager.is_ai_service_healthy())
        
        # Mock exception
        mock_client.health_check.side_effect = Exception("Connection error")
        self.assertFalse(self.fallback_manager.is_ai_service_healthy())


class AIOptimizationServiceTest(TestCase):
    """Test main optimization service"""
    
    def setUp(self):
        self.optimization_service = AIOptimizationService()
    
    @patch('apps.ai_engine.caching_optimization.get_gemini_client')
    def test_optimized_generate_response_with_cache(self, mock_get_client):
        """Test optimized response generation with caching"""
        # Mock client
        mock_client = Mock()
        mock_response = GeminiResponse(
            content="Test response",
            confidence_score=0.8,
            error=None
        )
        mock_client.generate_response.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        # First call should hit AI service
        response1 = self.optimization_service.optimized_generate_response(
            prompt="Test prompt",
            interaction_type="test",
            use_cache=True
        )
        
        self.assertEqual(response1.content, "Test response")
        self.assertFalse(response1.cached)
        
        # Second call should hit cache
        response2 = self.optimization_service.optimized_generate_response(
            prompt="Test prompt",
            interaction_type="test",
            use_cache=True
        )
        
        self.assertEqual(response2.content, "Test response")
        self.assertTrue(response2.cached)
    
    @patch('apps.ai_engine.caching_optimization.get_gemini_client')
    def test_optimized_generate_response_with_fallback(self, mock_get_client):
        """Test optimized response generation with fallback"""
        # Mock unhealthy service
        mock_client = Mock()
        mock_client.health_check.return_value = {'status': 'unhealthy'}
        mock_get_client.return_value = mock_client
        
        response = self.optimization_service.optimized_generate_response(
            prompt="Test prompt",
            interaction_type="question_generation",
            use_fallback=True
        )
        
        # Should get fallback response
        self.assertIsNotNone(response.content)
        self.assertFalse(response.cached)
        
        # Content should be JSON with fallback data
        fallback_data = json.loads(response.content)
        self.assertEqual(fallback_data['method'], 'fallback')
    
    def test_get_optimization_report(self):
        """Test optimization report generation"""
        report = self.optimization_service.get_optimization_report(7)
        
        self.assertIn('report_period_days', report)
        self.assertIn('usage_metrics', report)
        self.assertIn('service_status', report)
        self.assertIn('optimization_components', report)
        self.assertIn('generated_at', report)
        
        # Check optimization components
        components = report['optimization_components']
        self.assertTrue(components['intelligent_caching'])
        self.assertTrue(components['context_optimization'])
        self.assertTrue(components['batch_processing'])
        self.assertTrue(components['usage_monitoring'])
        self.assertTrue(components['fallback_mechanisms'])


class CacheStrategyTest(TestCase):
    """Test cache strategy configuration"""
    
    def test_cache_strategy_defaults(self):
        """Test default cache strategy values"""
        strategy = CacheStrategy()
        
        self.assertEqual(strategy.ttl_seconds, 3600)
        self.assertEqual(strategy.max_cache_size, 10000)
        self.assertEqual(strategy.cache_hit_threshold, 0.1)
        self.assertEqual(strategy.similarity_threshold, 0.85)
        self.assertTrue(strategy.enable_semantic_caching)
        self.assertTrue(strategy.enable_context_aware_caching)
    
    def test_cache_strategy_custom(self):
        """Test custom cache strategy configuration"""
        strategy = CacheStrategy(
            ttl_seconds=7200,
            max_cache_size=5000,
            similarity_threshold=0.9,
            enable_semantic_caching=False
        )
        
        self.assertEqual(strategy.ttl_seconds, 7200)
        self.assertEqual(strategy.max_cache_size, 5000)
        self.assertEqual(strategy.similarity_threshold, 0.9)
        self.assertFalse(strategy.enable_semantic_caching)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OptimizationTasksTest(TestCase):
    """Test optimization-related Celery tasks"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
    
    def test_cleanup_ai_cache_task(self):
        """Test cache cleanup task"""
        from .tasks import cleanup_ai_cache
        
        # Create expired cache entry
        AICache.objects.create(
            prompt_hash='expired_hash',
            interaction_type='test',
            cached_response='Expired response',
            expires_at=timezone.now() - timedelta(hours=1),
            original_prompt='Test prompt'
        )
        
        # Create low-performance entry
        AICache.objects.create(
            prompt_hash='low_perf_hash',
            interaction_type='test',
            cached_response='Low performance response',
            hit_count=1,
            expires_at=timezone.now() + timedelta(hours=1),
            created_at=timezone.now() - timedelta(days=8),
            original_prompt='Test prompt'
        )
        
        # Run cleanup task
        result = cleanup_ai_cache.delay().get()
        
        self.assertIn('expired_removed', result)
        self.assertIn('low_performance_removed', result)
        self.assertGreater(result['expired_removed'], 0)
    
    @patch('apps.ai_engine.tasks.get_optimization_service')
    def test_generate_usage_report_task(self, mock_get_service):
        """Test usage report generation task"""
        from .tasks import generate_usage_report
        
        # Mock optimization service
        mock_service = Mock()
        mock_service.get_optimization_report.return_value = {
            'usage_metrics': {
                'total_interactions': 100,
                'success_rate': 0.95,
                'cache_metrics': {'estimated_hit_rate': 0.7}
            },
            'generated_at': timezone.now().isoformat()
        }
        mock_get_service.return_value = mock_service
        
        # Run report generation task
        result = generate_usage_report.delay(7, []).get()
        
        self.assertTrue(result['report_generated'])
        self.assertEqual(result['report_period_days'], 7)
        self.assertFalse(result['email_sent'])
        self.assertEqual(result['email_recipients_count'], 0)