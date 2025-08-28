"""
AI Caching and Optimization Service
Implements intelligent response caching, conversation context optimization,
batch processing, usage monitoring, and fallback mechanisms.
"""
import logging
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from contextlib import contextmanager

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.db import transaction

from .models import AIInteraction, AICache, AIPromptTemplate
from .gemini_client import GeminiClient, GeminiResponse, get_gemini_client

logger = logging.getLogger(__name__)


@dataclass
class CacheStrategy:
    """Configuration for caching strategy"""
    ttl_seconds: int = 3600  # 1 hour default
    max_cache_size: int = 10000  # Maximum cached entries
    cache_hit_threshold: float = 0.1  # Minimum hit rate to keep cache
    similarity_threshold: float = 0.85  # Similarity threshold for cache matching
    enable_semantic_caching: bool = True
    enable_context_aware_caching: bool = True


@dataclass
class OptimizationMetrics:
    """Metrics for optimization tracking"""
    cache_hit_rate: float
    average_response_time: float
    cost_savings: float
    api_calls_saved: int
    batch_efficiency: float
    fallback_usage_rate: float


class IntelligentCacheManager:
    """Manages intelligent caching with semantic similarity and context awareness"""
    
    def __init__(self, strategy: Optional[CacheStrategy] = None):
        self.strategy = strategy or CacheStrategy()
        self.client = get_gemini_client()
        
    def get_cache_key(self, prompt: str, context: Optional[Dict] = None, interaction_type: str = 'general') -> str:
        """Generate intelligent cache key considering context and interaction type"""
        # Create base hash from prompt
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        
        # Add context if available
        if context:
            # Sort context keys for consistent hashing
            context_str = json.dumps(context, sort_keys=True, default=str)
            context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
            prompt_hash = f"{prompt_hash}_{context_hash}"
        
        # Add interaction type
        return f"{interaction_type}_{prompt_hash}"
    
    def find_similar_cached_response(
        self, 
        prompt: str, 
        interaction_type: str = 'general',
        context: Optional[Dict] = None
    ) -> Optional[Tuple[AICache, float]]:
        """Find semantically similar cached responses"""
        if not self.strategy.enable_semantic_caching:
            return None
        
        try:
            # Get recent cache entries of the same type
            recent_entries = AICache.objects.filter(
                interaction_type=interaction_type,
                expires_at__gt=timezone.now(),
                created_at__gte=timezone.now() - timedelta(days=7)
            ).order_by('-hit_count', '-created_at')[:50]  # Limit search scope
            
            # Calculate similarity scores
            best_match = None
            best_score = 0.0
            
            for entry in recent_entries:
                similarity = self._calculate_prompt_similarity(prompt, entry.original_prompt)
                
                # Consider context similarity if available
                if context and self.strategy.enable_context_aware_caching:
                    # This is a simplified context similarity - could be enhanced
                    context_similarity = 0.8  # Default context match
                    similarity = (similarity * 0.7) + (context_similarity * 0.3)
                
                if similarity > best_score and similarity >= self.strategy.similarity_threshold:
                    best_score = similarity
                    best_match = entry
            
            if best_match:
                logger.info(f"Found similar cached response with {best_score:.2f} similarity")
                return best_match, best_score
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding similar cached response: {str(e)}")
            return None
    
    def _calculate_prompt_similarity(self, prompt1: str, prompt2: str) -> float:
        """Calculate similarity between two prompts (simplified implementation)"""
        # This is a basic implementation - could be enhanced with embeddings
        words1 = set(prompt1.lower().split())
        words2 = set(prompt2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        jaccard_similarity = len(intersection) / len(union) if union else 0.0
        
        # Boost similarity for exact substring matches
        if prompt1.lower() in prompt2.lower() or prompt2.lower() in prompt1.lower():
            jaccard_similarity = min(1.0, jaccard_similarity + 0.2)
        
        return jaccard_similarity
    
    def cache_response(
        self,
        prompt: str,
        response: GeminiResponse,
        interaction_type: str = 'general',
        context: Optional[Dict] = None,
        template: Optional[AIPromptTemplate] = None
    ) -> bool:
        """Cache response with intelligent strategy"""
        try:
            cache_key = self.get_cache_key(prompt, context, interaction_type)
            expires_at = timezone.now() + timedelta(seconds=self.strategy.ttl_seconds)
            
            # Check cache size limits
            if self._should_evict_cache():
                self._evict_old_entries()
            
            # Create cache entry
            AICache.objects.update_or_create(
                prompt_hash=cache_key,
                defaults={
                    'interaction_type': interaction_type,
                    'cached_response': response.content,
                    'cached_parsed_data': getattr(response, 'parsed_data', None),
                    'confidence_score': response.confidence_score,
                    'expires_at': expires_at,
                    'original_prompt': prompt,
                    'template_used': template,
                }
            )
            
            logger.debug(f"Cached response for {interaction_type}: {cache_key[:16]}...")
            return True
            
        except Exception as e:
            logger.error(f"Error caching response: {str(e)}")
            return False
    
    def get_cached_response(
        self,
        prompt: str,
        interaction_type: str = 'general',
        context: Optional[Dict] = None
    ) -> Optional[GeminiResponse]:
        """Get cached response with fallback to similar responses"""
        try:
            # Try exact match first
            cache_key = self.get_cache_key(prompt, context, interaction_type)
            cached_entry = AICache.objects.filter(
                prompt_hash=cache_key,
                expires_at__gt=timezone.now()
            ).first()
            
            if cached_entry:
                cached_entry.increment_hit()
                logger.debug(f"Cache hit for {interaction_type}: {cache_key[:16]}...")
                
                return GeminiResponse(
                    content=cached_entry.cached_response,
                    confidence_score=cached_entry.confidence_score,
                    cached=True
                )
            
            # Try semantic similarity matching
            similar_match = self.find_similar_cached_response(prompt, interaction_type, context)
            if similar_match:
                entry, similarity = similar_match
                entry.increment_hit()
                
                logger.info(f"Using similar cached response ({similarity:.2f} similarity)")
                
                return GeminiResponse(
                    content=entry.cached_response,
                    confidence_score=entry.confidence_score * similarity,  # Adjust confidence
                    cached=True
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Error retrieving cached response: {str(e)}")
            return None
    
    def _should_evict_cache(self) -> bool:
        """Check if cache eviction is needed"""
        try:
            cache_count = AICache.objects.count()
            return cache_count >= self.strategy.max_cache_size
        except Exception:
            return False
    
    def _evict_old_entries(self):
        """Evict old or low-performing cache entries"""
        try:
            # Remove expired entries first
            AICache.objects.filter(expires_at__lte=timezone.now()).delete()
            
            # Remove entries with low hit rates
            cutoff_date = timezone.now() - timedelta(days=7)
            low_performance_entries = AICache.objects.filter(
                created_at__lt=cutoff_date,
                hit_count__lt=2
            )
            
            deleted_count = low_performance_entries.count()
            low_performance_entries.delete()
            
            logger.info(f"Evicted {deleted_count} low-performance cache entries")
            
        except Exception as e:
            logger.error(f"Error evicting cache entries: {str(e)}")


class ConversationContextOptimizer:
    """Optimizes conversation context for better AI responses"""
    
    def __init__(self):
        self.max_context_length = getattr(settings, 'AI_MAX_CONTEXT_LENGTH', 4000)
        self.context_compression_ratio = 0.7
        
    def optimize_context(
        self,
        conversation_history: List[Dict],
        current_prompt: str,
        meeting_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Optimize conversation context for better responses"""
        try:
            # Calculate current context size
            context_size = len(current_prompt)
            if meeting_context:
                context_size += len(json.dumps(meeting_context, default=str))
            
            # Add conversation history with smart truncation
            optimized_history = self._optimize_conversation_history(
                conversation_history, 
                self.max_context_length - context_size
            )
            
            # Extract key insights from conversation
            key_insights = self._extract_key_insights(optimized_history)
            
            # Build optimized context
            optimized_context = {
                'conversation_summary': self._summarize_conversation(optimized_history),
                'key_insights': key_insights,
                'recent_exchanges': optimized_history[-3:] if optimized_history else [],
                'meeting_context': meeting_context or {},
                'context_optimization': {
                    'original_length': len(conversation_history),
                    'optimized_length': len(optimized_history),
                    'compression_ratio': len(optimized_history) / max(1, len(conversation_history))
                }
            }
            
            return optimized_context
            
        except Exception as e:
            logger.error(f"Error optimizing conversation context: {str(e)}")
            return {
                'conversation_summary': 'Context optimization failed',
                'key_insights': [],
                'recent_exchanges': conversation_history[-3:] if conversation_history else [],
                'meeting_context': meeting_context or {}
            }
    
    def _optimize_conversation_history(
        self, 
        history: List[Dict], 
        max_length: int
    ) -> List[Dict]:
        """Optimize conversation history by keeping most relevant exchanges"""
        if not history:
            return []
        
        # Calculate importance scores for each exchange
        scored_exchanges = []
        for i, exchange in enumerate(history):
            score = self._calculate_exchange_importance(exchange, i, len(history))
            scored_exchanges.append((score, exchange))
        
        # Sort by importance and select top exchanges within length limit
        scored_exchanges.sort(key=lambda x: x[0], reverse=True)
        
        selected_exchanges = []
        current_length = 0
        
        for score, exchange in scored_exchanges:
            exchange_length = len(json.dumps(exchange, default=str))
            if current_length + exchange_length <= max_length:
                selected_exchanges.append(exchange)
                current_length += exchange_length
            else:
                break
        
        # Sort selected exchanges back to chronological order
        selected_exchanges.sort(key=lambda x: history.index(x))
        
        return selected_exchanges
    
    def _calculate_exchange_importance(
        self, 
        exchange: Dict, 
        position: int, 
        total_exchanges: int
    ) -> float:
        """Calculate importance score for a conversation exchange"""
        score = 0.0
        
        # Recent exchanges are more important
        recency_score = position / max(1, total_exchanges - 1)
        score += recency_score * 0.3
        
        # Exchanges with questions are important
        if 'question' in exchange or '?' in str(exchange):
            score += 0.2
        
        # Exchanges with specific keywords are important
        important_keywords = [
            'budget', 'timeline', 'decision', 'competitor', 'requirement',
            'concern', 'problem', 'solution', 'next steps', 'commitment'
        ]
        
        exchange_text = json.dumps(exchange, default=str).lower()
        keyword_matches = sum(1 for keyword in important_keywords if keyword in exchange_text)
        score += min(0.3, keyword_matches * 0.1)
        
        # Longer exchanges might be more detailed
        exchange_length = len(exchange_text)
        if exchange_length > 100:
            score += 0.1
        
        # Exchanges with structured data are important
        if isinstance(exchange, dict) and len(exchange) > 2:
            score += 0.1
        
        return score
    
    def _extract_key_insights(self, conversation_history: List[Dict]) -> List[str]:
        """Extract key insights from conversation history"""
        insights = []
        
        try:
            # Look for patterns and important information
            all_text = ' '.join([json.dumps(exchange, default=str) for exchange in conversation_history])
            
            # Extract mentions of key topics
            key_topics = {
                'budget': ['budget', 'cost', 'price', 'investment'],
                'timeline': ['timeline', 'deadline', 'when', 'schedule'],
                'stakeholders': ['decision maker', 'stakeholder', 'authority', 'approval'],
                'competition': ['competitor', 'alternative', 'comparison'],
                'concerns': ['concern', 'worry', 'problem', 'issue'],
                'requirements': ['requirement', 'need', 'must have', 'feature']
            }
            
            for topic, keywords in key_topics.items():
                if any(keyword in all_text.lower() for keyword in keywords):
                    insights.append(f"Discussion included {topic} considerations")
            
            # Limit insights
            return insights[:5]
            
        except Exception as e:
            logger.warning(f"Error extracting key insights: {str(e)}")
            return []
    
    def _summarize_conversation(self, conversation_history: List[Dict]) -> str:
        """Create a brief summary of the conversation"""
        if not conversation_history:
            return "No previous conversation"
        
        try:
            # Simple summarization based on exchange count and key topics
            exchange_count = len(conversation_history)
            
            # Extract key topics mentioned
            all_text = ' '.join([json.dumps(exchange, default=str) for exchange in conversation_history])
            
            summary_parts = [f"Previous conversation with {exchange_count} exchanges"]
            
            # Add topic mentions
            if 'budget' in all_text.lower():
                summary_parts.append("discussed budget/pricing")
            if 'timeline' in all_text.lower():
                summary_parts.append("covered timeline requirements")
            if 'competitor' in all_text.lower():
                summary_parts.append("mentioned competitive alternatives")
            
            return "; ".join(summary_parts)
            
        except Exception as e:
            logger.warning(f"Error summarizing conversation: {str(e)}")
            return f"Previous conversation with {len(conversation_history)} exchanges"


class BatchProcessor:
    """Handles batch processing for non-real-time AI operations"""
    
    def __init__(self):
        self.client = get_gemini_client()
        self.batch_size = getattr(settings, 'AI_BATCH_SIZE', 10)
        self.batch_delay = getattr(settings, 'AI_BATCH_DELAY', 2)  # seconds between batches
        
    @contextmanager
    def batch_context(self):
        """Context manager for batch processing with optimized settings"""
        with self.client.batch_mode():
            yield self
    
    def process_batch_requests(
        self,
        requests: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """Process multiple AI requests in batches"""
        results = []
        total_requests = len(requests)
        
        try:
            with self.batch_context():
                for i in range(0, total_requests, self.batch_size):
                    batch = requests[i:i + self.batch_size]
                    batch_results = self._process_single_batch(batch)
                    results.extend(batch_results)
                    
                    # Progress callback
                    if progress_callback:
                        progress = (i + len(batch)) / total_requests
                        progress_callback(progress, len(results))
                    
                    # Delay between batches to respect rate limits
                    if i + self.batch_size < total_requests:
                        time.sleep(self.batch_delay)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing batch requests: {str(e)}")
            return results  # Return partial results
    
    def _process_single_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a single batch of requests"""
        batch_results = []
        
        for request in batch:
            try:
                # Extract request parameters
                prompt = request.get('prompt', '')
                system_prompt = request.get('system_prompt')
                temperature = request.get('temperature', 0.7)
                max_tokens = request.get('max_tokens', 1000)
                use_cache = request.get('use_cache', True)
                
                # Make request
                response = self.client.generate_response(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_cache=use_cache
                )
                
                # Add request metadata to result
                result = {
                    'request_id': request.get('id'),
                    'response': response,
                    'success': not bool(response.error),
                    'error': response.error
                }
                
                batch_results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing batch request: {str(e)}")
                batch_results.append({
                    'request_id': request.get('id'),
                    'response': None,
                    'success': False,
                    'error': str(e)
                })
        
        return batch_results
    
    def schedule_batch_job(
        self,
        requests: List[Dict[str, Any]],
        job_name: str,
        priority: str = 'normal'
    ) -> str:
        """Schedule a batch job for later processing"""
        # This would integrate with Celery or similar task queue
        # For now, we'll use Django cache as a simple queue
        
        job_id = f"batch_job_{int(time.time())}_{hash(job_name)}"
        
        job_data = {
            'id': job_id,
            'name': job_name,
            'requests': requests,
            'priority': priority,
            'created_at': timezone.now().isoformat(),
            'status': 'queued'
        }
        
        # Store in cache with 24-hour expiration
        cache.set(f"batch_job_{job_id}", job_data, 86400)
        
        logger.info(f"Scheduled batch job {job_id} with {len(requests)} requests")
        return job_id


class AIUsageMonitor:
    """Monitors AI usage and provides cost optimization insights"""
    
    def __init__(self):
        self.cost_per_1k_tokens = getattr(settings, 'GEMINI_COST_PER_1K_TOKENS', 0.001)
        
    def get_usage_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive usage metrics"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Query interactions
            interactions = AIInteraction.objects.filter(created_at__gte=cutoff_date)
            
            # Basic metrics
            total_interactions = interactions.count()
            successful_interactions = interactions.filter(status='success').count()
            
            # Performance metrics
            avg_response_time = interactions.filter(
                response_time_ms__isnull=False
            ).aggregate(avg_time=Avg('response_time_ms'))['avg_time'] or 0
            
            # Token usage
            total_tokens = interactions.filter(
                token_count__isnull=False
            ).aggregate(total=Sum('token_count'))['total'] or 0
            
            # Cost estimation
            estimated_cost = (total_tokens / 1000) * self.cost_per_1k_tokens
            
            # Cache metrics
            cache_metrics = self._get_cache_metrics(cutoff_date)
            
            # Error analysis
            error_breakdown = self._get_error_breakdown(interactions)
            
            return {
                'period_days': days,
                'total_interactions': total_interactions,
                'successful_interactions': successful_interactions,
                'success_rate': successful_interactions / max(1, total_interactions),
                'average_response_time_ms': avg_response_time,
                'total_tokens_used': total_tokens,
                'estimated_cost_usd': estimated_cost,
                'cache_metrics': cache_metrics,
                'error_breakdown': error_breakdown,
                'optimization_suggestions': self._get_optimization_suggestions(
                    total_interactions, cache_metrics, error_breakdown
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {str(e)}")
            return {'error': str(e)}
    
    def _get_cache_metrics(self, cutoff_date: datetime) -> Dict[str, Any]:
        """Get cache performance metrics"""
        try:
            # Cache entries created in period
            cache_entries = AICache.objects.filter(created_at__gte=cutoff_date)
            total_cache_entries = cache_entries.count()
            
            # Cache hits
            total_hits = cache_entries.aggregate(total_hits=Sum('hit_count'))['total_hits'] or 0
            
            # Active cache entries
            active_entries = AICache.objects.filter(expires_at__gt=timezone.now()).count()
            
            # Cache hit rate estimation
            recent_interactions = AIInteraction.objects.filter(
                created_at__gte=cutoff_date
            ).count()
            
            cache_hit_rate = total_hits / max(1, recent_interactions + total_hits)
            
            return {
                'total_cache_entries': total_cache_entries,
                'active_cache_entries': active_entries,
                'total_cache_hits': total_hits,
                'estimated_hit_rate': cache_hit_rate,
                'estimated_api_calls_saved': total_hits,
                'estimated_cost_savings': (total_hits * 100 * self.cost_per_1k_tokens) / 1000
            }
            
        except Exception as e:
            logger.warning(f"Error getting cache metrics: {str(e)}")
            return {}
    
    def _get_error_breakdown(self, interactions) -> Dict[str, Any]:
        """Analyze error patterns"""
        try:
            error_interactions = interactions.filter(status='error')
            total_errors = error_interactions.count()
            
            if total_errors == 0:
                return {'total_errors': 0}
            
            # Group by error type (simplified)
            error_types = defaultdict(int)
            for interaction in error_interactions:
                error_msg = interaction.error_message or 'Unknown error'
                if 'rate limit' in error_msg.lower():
                    error_types['rate_limit'] += 1
                elif 'quota' in error_msg.lower():
                    error_types['quota_exceeded'] += 1
                elif 'timeout' in error_msg.lower():
                    error_types['timeout'] += 1
                elif 'invalid' in error_msg.lower():
                    error_types['invalid_request'] += 1
                else:
                    error_types['other'] += 1
            
            return {
                'total_errors': total_errors,
                'error_types': dict(error_types),
                'error_rate': total_errors / max(1, interactions.count())
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing error breakdown: {str(e)}")
            return {'total_errors': 0}
    
    def _get_optimization_suggestions(
        self,
        total_interactions: int,
        cache_metrics: Dict,
        error_breakdown: Dict
    ) -> List[str]:
        """Generate optimization suggestions based on metrics"""
        suggestions = []
        
        try:
            # Cache optimization
            hit_rate = cache_metrics.get('estimated_hit_rate', 0)
            if hit_rate < 0.2:
                suggestions.append("Consider improving cache strategy - low hit rate detected")
            elif hit_rate > 0.8:
                suggestions.append("Excellent cache performance - consider extending TTL")
            
            # Error rate optimization
            error_rate = error_breakdown.get('error_rate', 0)
            if error_rate > 0.1:
                suggestions.append("High error rate detected - review error handling and retry logic")
            
            # Rate limiting
            rate_limit_errors = error_breakdown.get('error_types', {}).get('rate_limit', 0)
            if rate_limit_errors > 0:
                suggestions.append("Rate limit errors detected - consider implementing better request spacing")
            
            # Usage volume
            if total_interactions > 1000:
                suggestions.append("High usage volume - consider implementing more aggressive caching")
            elif total_interactions < 10:
                suggestions.append("Low usage volume - consider reducing cache TTL to save storage")
            
            return suggestions
            
        except Exception as e:
            logger.warning(f"Error generating optimization suggestions: {str(e)}")
            return ["Unable to generate optimization suggestions"]


class FallbackManager:
    """Manages fallback mechanisms when AI services are unavailable"""
    
    def __init__(self):
        self.fallback_responses = {
            'question_generation': [
                "How would you summarize the key outcomes of this meeting?",
                "What were the main topics discussed?",
                "Were there any action items or next steps identified?",
                "What concerns or questions were raised?",
                "How would you rate the overall meeting effectiveness?"
            ],
            'data_extraction': {
                'contacts': [],
                'action_items': [],
                'competitive_intelligence': [],
                'deal_information': {},
                'meeting_outcome': 'Unable to analyze - AI service unavailable'
            },
            'follow_up_question': "Could you provide more details about that topic?"
        }
        
    def get_fallback_response(
        self,
        interaction_type: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Get fallback response when AI service is unavailable"""
        try:
            if interaction_type == 'question_generation':
                return {
                    'questions': [
                        {'id': i+1, 'question': q, 'type': 'fallback'}
                        for i, q in enumerate(self.fallback_responses['question_generation'])
                    ],
                    'confidence_score': 0.3,
                    'method': 'fallback',
                    'fallback_reason': 'AI service unavailable'
                }
            
            elif interaction_type == 'data_extraction':
                return {
                    'extracted_data': self.fallback_responses['data_extraction'].copy(),
                    'confidence_score': 0.0,
                    'method': 'fallback',
                    'fallback_reason': 'AI service unavailable'
                }
            
            elif interaction_type == 'follow_up_question':
                return {
                    'follow_up_question': self.fallback_responses['follow_up_question'],
                    'confidence_score': 0.2,
                    'method': 'fallback',
                    'fallback_reason': 'AI service unavailable'
                }
            
            else:
                return {
                    'content': 'Service temporarily unavailable. Please try again later.',
                    'confidence_score': 0.0,
                    'method': 'fallback',
                    'fallback_reason': 'AI service unavailable'
                }
                
        except Exception as e:
            logger.error(f"Error generating fallback response: {str(e)}")
            return {
                'content': 'Service temporarily unavailable.',
                'error': str(e),
                'method': 'fallback'
            }
    
    def is_ai_service_healthy(self) -> bool:
        """Check if AI service is healthy"""
        try:
            client = get_gemini_client()
            health_status = client.health_check()
            return health_status.get('status') == 'healthy'
        except Exception:
            return False
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status"""
        try:
            client = get_gemini_client()
            health_status = client.health_check()
            usage_stats = client.get_usage_stats()
            
            return {
                'ai_service_healthy': health_status.get('status') == 'healthy',
                'health_details': health_status,
                'usage_stats': usage_stats,
                'fallback_available': True,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'ai_service_healthy': False,
                'error': str(e),
                'fallback_available': True,
                'timestamp': timezone.now().isoformat()
            }


# Main optimization service that combines all components
class AIOptimizationService:
    """Main service that combines all optimization components"""
    
    def __init__(self):
        self.cache_manager = IntelligentCacheManager()
        self.context_optimizer = ConversationContextOptimizer()
        self.batch_processor = BatchProcessor()
        self.usage_monitor = AIUsageMonitor()
        self.fallback_manager = FallbackManager()
        
    def optimized_generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        interaction_type: str = 'general',
        context: Optional[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        use_cache: bool = True,
        use_fallback: bool = True
    ) -> GeminiResponse:
        """Generate response with full optimization pipeline"""
        try:
            # Check if AI service is healthy
            if use_fallback and not self.fallback_manager.is_ai_service_healthy():
                logger.warning("AI service unhealthy, using fallback")
                fallback_response = self.fallback_manager.get_fallback_response(
                    interaction_type, context
                )
                return GeminiResponse(
                    content=json.dumps(fallback_response),
                    confidence_score=fallback_response.get('confidence_score', 0.0),
                    cached=False,
                    error=None
                )
            
            # Optimize conversation context
            if conversation_history:
                optimized_context = self.context_optimizer.optimize_context(
                    conversation_history, prompt, context
                )
                # Enhance system prompt with optimized context
                if system_prompt:
                    system_prompt = f"{system_prompt}\n\nContext: {json.dumps(optimized_context, default=str)}"
                else:
                    system_prompt = f"Context: {json.dumps(optimized_context, default=str)}"
            
            # Try cache first
            if use_cache:
                cached_response = self.cache_manager.get_cached_response(
                    prompt, interaction_type, context
                )
                if cached_response:
                    return cached_response
            
            # Generate new response
            client = get_gemini_client()
            response = client.generate_response(
                prompt=prompt,
                system_prompt=system_prompt,
                use_cache=False  # We handle caching ourselves
            )
            
            # Cache successful responses
            if use_cache and response and not response.error:
                self.cache_manager.cache_response(
                    prompt, response, interaction_type, context
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in optimized response generation: {str(e)}")
            
            # Use fallback if enabled
            if use_fallback:
                fallback_response = self.fallback_manager.get_fallback_response(
                    interaction_type, context
                )
                return GeminiResponse(
                    content=json.dumps(fallback_response),
                    confidence_score=0.0,
                    cached=False,
                    error=f"Service error, using fallback: {str(e)}"
                )
            
            return GeminiResponse(
                content="",
                error=str(e)
            )
    
    def get_optimization_report(self, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive optimization report"""
        try:
            usage_metrics = self.usage_monitor.get_usage_metrics(days)
            service_status = self.fallback_manager.get_service_status()
            
            return {
                'report_period_days': days,
                'usage_metrics': usage_metrics,
                'service_status': service_status,
                'optimization_components': {
                    'intelligent_caching': True,
                    'context_optimization': True,
                    'batch_processing': True,
                    'usage_monitoring': True,
                    'fallback_mechanisms': True
                },
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating optimization report: {str(e)}")
            return {
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }


# Global optimization service instance
_optimization_service = None


def get_optimization_service() -> AIOptimizationService:
    """Get singleton optimization service instance"""
    global _optimization_service
    if _optimization_service is None:
        _optimization_service = AIOptimizationService()
    return _optimization_service