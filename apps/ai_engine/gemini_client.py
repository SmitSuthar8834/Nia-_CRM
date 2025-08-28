"""
Google Gemini AI Client for Meeting Intelligence
Handles secure API communication, authentication, and error handling
"""
import os
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import contextmanager

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import AIInteraction, AICache, AIPromptTemplate

logger = logging.getLogger(__name__)


@dataclass
class GeminiResponse:
    """Structured response from Gemini API"""
    content: str
    confidence_score: Optional[float] = None
    token_count: Optional[int] = None
    response_time_ms: Optional[int] = None
    cached: bool = False
    error: Optional[str] = None


class GeminiRateLimiter:
    """Rate limiting for Gemini API calls"""
    
    def __init__(self, requests_per_minute: int = 60, requests_per_day: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_key = "gemini_rate_limit_minute"
        self.day_key = "gemini_rate_limit_day"
    
    def can_make_request(self) -> Tuple[bool, str]:
        """Check if request can be made within rate limits"""
        current_time = timezone.now()
        minute_key = f"{self.minute_key}_{current_time.strftime('%Y%m%d%H%M')}"
        day_key = f"{self.day_key}_{current_time.strftime('%Y%m%d')}"
        
        minute_count = cache.get(minute_key, 0)
        day_count = cache.get(day_key, 0)
        
        if minute_count >= self.requests_per_minute:
            return False, "Rate limit exceeded: too many requests per minute"
        
        if day_count >= self.requests_per_day:
            return False, "Rate limit exceeded: too many requests per day"
        
        return True, ""
    
    def record_request(self):
        """Record a successful request"""
        current_time = timezone.now()
        minute_key = f"{self.minute_key}_{current_time.strftime('%Y%m%d%H%M')}"
        day_key = f"{self.day_key}_{current_time.strftime('%Y%m%d')}"
        
        # Increment counters with expiration
        cache.set(minute_key, cache.get(minute_key, 0) + 1, 60)  # 1 minute
        cache.set(day_key, cache.get(day_key, 0) + 1, 86400)  # 24 hours


class GeminiAPIKeyManager:
    """Manages API key rotation and security"""
    
    def __init__(self):
        self.primary_key = settings.GEMINI_API_KEY
        self.backup_keys = getattr(settings, 'GEMINI_BACKUP_API_KEYS', [])
        self.current_key_index = 0
        self.key_failure_counts = {}
        self.max_failures_per_key = 5
    
    def get_active_key(self) -> str:
        """Get the currently active API key"""
        if not self.primary_key:
            raise ValueError("GEMINI_API_KEY not configured in settings")
        
        # Check if primary key has failed too many times
        if self.key_failure_counts.get('primary', 0) >= self.max_failures_per_key:
            return self._get_backup_key()
        
        return self.primary_key
    
    def _get_backup_key(self) -> str:
        """Get a backup API key if available"""
        if not self.backup_keys:
            logger.warning("Primary API key failed but no backup keys available")
            return self.primary_key
        
        # Find a backup key that hasn't failed too many times
        for i, key in enumerate(self.backup_keys):
            if self.key_failure_counts.get(f'backup_{i}', 0) < self.max_failures_per_key:
                self.current_key_index = i
                return key
        
        # If all keys have failed, reset counters and try again
        logger.warning("All API keys have failed, resetting failure counters")
        self.key_failure_counts.clear()
        return self.primary_key
    
    def record_key_failure(self, key: str):
        """Record a failure for the given key"""
        if key == self.primary_key:
            self.key_failure_counts['primary'] = self.key_failure_counts.get('primary', 0) + 1
        else:
            for i, backup_key in enumerate(self.backup_keys):
                if key == backup_key:
                    self.key_failure_counts[f'backup_{i}'] = self.key_failure_counts.get(f'backup_{i}', 0) + 1
                    break
    
    def record_key_success(self, key: str):
        """Record a success for the given key (reset failure count)"""
        if key == self.primary_key:
            self.key_failure_counts.pop('primary', None)
        else:
            for i, backup_key in enumerate(self.backup_keys):
                if key == backup_key:
                    self.key_failure_counts.pop(f'backup_{i}', None)
                    break


class GeminiClient:
    """
    Secure Google Gemini AI client with error handling, rate limiting, and caching
    """
    
    def __init__(self):
        self.key_manager = GeminiAPIKeyManager()
        self.rate_limiter = GeminiRateLimiter()
        self.model_name = getattr(settings, 'GEMINI_MODEL_NAME', 'gemini-pro')
        self.max_retries = getattr(settings, 'GEMINI_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'GEMINI_RETRY_DELAY', 1)  # seconds
        self.timeout = getattr(settings, 'GEMINI_TIMEOUT', 30)  # seconds
        
        # Safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
        
        self._model = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Gemini client with API key"""
        try:
            api_key = self.key_manager.get_active_key()
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(self.model_name)
            logger.info("Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Gemini API connection"""
        try:
            start_time = time.time()
            
            # Simple test prompt
            test_prompt = "Respond with 'OK' if you can process this message."
            response = self._make_request(test_prompt, max_tokens=10)
            
            response_time = (time.time() - start_time) * 1000
            
            if response and not response.error:
                return {
                    'status': 'healthy',
                    'response_time_ms': response_time,
                    'model': self.model_name,
                    'timestamp': timezone.now().isoformat()
                }
            else:
                return {
                    'status': 'unhealthy',
                    'error': response.error if response else 'No response received',
                    'timestamp': timezone.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        use_cache: bool = True,
        cache_ttl: int = 3600  # 1 hour
    ) -> GeminiResponse:
        """
        Generate response from Gemini API with caching and error handling
        """
        # Check cache first if enabled
        if use_cache:
            cached_response = self._get_cached_response(prompt, system_prompt)
            if cached_response:
                return cached_response
        
        # Check rate limits
        can_request, rate_limit_msg = self.rate_limiter.can_make_request()
        if not can_request:
            logger.warning(f"Rate limit exceeded: {rate_limit_msg}")
            return GeminiResponse(
                content="",
                error=f"Rate limit exceeded: {rate_limit_msg}"
            )
        
        # Make the API request
        response = self._make_request_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Cache successful responses
        if use_cache and response and not response.error:
            self._cache_response(prompt, system_prompt, response, cache_ttl)
        
        # Record successful request for rate limiting
        if response and not response.error:
            self.rate_limiter.record_request()
        
        return response
    
    def _make_request_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> GeminiResponse:
        """Make request with retry logic"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._make_request(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response and not response.error:
                    # Record success for current API key
                    current_key = self.key_manager.get_active_key()
                    self.key_manager.record_key_success(current_key)
                    return response
                
                last_error = response.error if response else "Unknown error"
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Gemini API request attempt {attempt + 1} failed: {last_error}")
                
                # Record failure for current API key
                current_key = self.key_manager.get_active_key()
                self.key_manager.record_key_failure(current_key)
                
                # Reinitialize client with potentially different API key
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    self._initialize_client()
        
        return GeminiResponse(
            content="",
            error=f"Failed after {self.max_retries} attempts. Last error: {last_error}"
        )
    
    def _make_request(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> GeminiResponse:
        """Make a single request to Gemini API"""
        start_time = time.time()
        
        try:
            # Prepare the full prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Configure generation parameters
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
            
            # Make the API call
            response = self._model.generate_content(
                full_prompt,
                generation_config=generation_config,
                safety_settings=self.safety_settings
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract response content
            if response.candidates and len(response.candidates) > 0:
                content = response.candidates[0].content.parts[0].text
                
                # Calculate confidence score (simplified)
                confidence_score = self._calculate_confidence_score(response)
                
                # Get token count if available
                token_count = None
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    token_count = getattr(response.usage_metadata, 'total_token_count', None)
                
                return GeminiResponse(
                    content=content,
                    confidence_score=confidence_score,
                    token_count=token_count,
                    response_time_ms=response_time_ms
                )
            else:
                return GeminiResponse(
                    content="",
                    error="No response candidates generated",
                    response_time_ms=response_time_ms
                )
        
        except google_exceptions.ResourceExhausted as e:
            logger.error(f"Gemini API quota exceeded: {str(e)}")
            return GeminiResponse(
                content="",
                error="API quota exceeded",
                response_time_ms=int((time.time() - start_time) * 1000)
            )
        
        except google_exceptions.InvalidArgument as e:
            logger.error(f"Invalid request to Gemini API: {str(e)}")
            return GeminiResponse(
                content="",
                error=f"Invalid request: {str(e)}",
                response_time_ms=int((time.time() - start_time) * 1000)
            )
        
        except Exception as e:
            logger.error(f"Unexpected error in Gemini API request: {str(e)}")
            return GeminiResponse(
                content="",
                error=f"Unexpected error: {str(e)}",
                response_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _calculate_confidence_score(self, response) -> float:
        """Calculate confidence score based on response metadata"""
        # This is a simplified confidence calculation
        # In a real implementation, you might use more sophisticated methods
        try:
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'safety_ratings'):
                    # Use safety ratings as a proxy for confidence
                    # Higher safety ratings generally indicate more confident responses
                    total_confidence = 0
                    rating_count = 0
                    
                    for rating in candidate.safety_ratings:
                        if hasattr(rating, 'probability'):
                            # Convert probability to confidence score
                            prob_value = rating.probability.value if hasattr(rating.probability, 'value') else 0
                            confidence = max(0, 1 - (prob_value / 4))  # Normalize to 0-1
                            total_confidence += confidence
                            rating_count += 1
                    
                    if rating_count > 0:
                        return total_confidence / rating_count
            
            # Default confidence score
            return 0.8
        
        except Exception as e:
            logger.warning(f"Could not calculate confidence score: {str(e)}")
            return 0.5
    
    def _get_cache_key(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate cache key for prompt"""
        full_prompt = f"{system_prompt or ''}\n{prompt}"
        return hashlib.sha256(full_prompt.encode()).hexdigest()
    
    def _get_cached_response(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[GeminiResponse]:
        """Get cached response if available"""
        try:
            cache_key = self._get_cache_key(prompt, system_prompt)
            cached_entry = AICache.objects.filter(
                prompt_hash=cache_key,
                expires_at__gt=timezone.now()
            ).first()
            
            if cached_entry:
                cached_entry.increment_hit()
                logger.info(f"Cache hit for prompt hash: {cache_key[:8]}...")
                
                return GeminiResponse(
                    content=cached_entry.cached_response,
                    confidence_score=cached_entry.confidence_score,
                    cached=True
                )
            
            return None
        
        except Exception as e:
            logger.warning(f"Error retrieving cached response: {str(e)}")
            return None
    
    def _cache_response(
        self,
        prompt: str,
        system_prompt: Optional[str],
        response: GeminiResponse,
        ttl: int
    ):
        """Cache the response"""
        try:
            cache_key = self._get_cache_key(prompt, system_prompt)
            expires_at = timezone.now() + timedelta(seconds=ttl)
            
            # Create or update cache entry
            AICache.objects.update_or_create(
                prompt_hash=cache_key,
                defaults={
                    'interaction_type': 'general',
                    'cached_response': response.content,
                    'confidence_score': response.confidence_score,
                    'expires_at': expires_at,
                    'original_prompt': f"{system_prompt or ''}\n{prompt}",
                }
            )
            
            logger.info(f"Cached response for prompt hash: {cache_key[:8]}...")
        
        except Exception as e:
            logger.warning(f"Error caching response: {str(e)}")
    
    @contextmanager
    def batch_mode(self):
        """Context manager for batch processing with optimized settings"""
        original_rate_limiter = self.rate_limiter
        
        # Use more conservative rate limiting for batch operations
        self.rate_limiter = GeminiRateLimiter(
            requests_per_minute=30,  # Reduced for batch operations
            requests_per_day=800
        )
        
        try:
            yield self
        finally:
            self.rate_limiter = original_rate_limiter
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for monitoring"""
        try:
            current_time = timezone.now()
            day_key = f"gemini_rate_limit_day_{current_time.strftime('%Y%m%d')}"
            minute_key = f"gemini_rate_limit_minute_{current_time.strftime('%Y%m%d%H%M')}"
            
            return {
                'requests_today': cache.get(day_key, 0),
                'requests_this_minute': cache.get(minute_key, 0),
                'rate_limit_per_minute': self.rate_limiter.requests_per_minute,
                'rate_limit_per_day': self.rate_limiter.requests_per_day,
                'model': self.model_name,
                'key_failures': dict(self.key_manager.key_failure_counts),
                'timestamp': current_time.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            return {'error': str(e)}


# Global client instance
_gemini_client = None


def get_gemini_client() -> GeminiClient:
    """Get singleton Gemini client instance"""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client