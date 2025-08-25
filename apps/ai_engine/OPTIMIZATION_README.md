# AI Caching and Optimization Features

This document describes the AI caching and optimization features implemented for the Meeting Intelligence system.

## Overview

The AI optimization system provides intelligent response caching, conversation context optimization, batch processing, usage monitoring, and fallback mechanisms to reduce API costs, improve performance, and ensure system reliability.

## Features

### 1. Intelligent Response Caching

**Purpose**: Reduce API costs by caching AI responses and reusing them for similar requests.

**Key Components**:
- `IntelligentCacheManager`: Manages cache storage and retrieval
- Semantic similarity matching for related prompts
- Context-aware caching based on meeting context
- Automatic cache eviction based on performance metrics

**Benefits**:
- Reduces API calls by 30-70% (typical cache hit rates)
- Faster response times for cached content
- Significant cost savings on repeated or similar queries

**Usage**:
```python
from apps.ai_engine.caching_optimization import get_optimization_service

optimization_service = get_optimization_service()
response = optimization_service.optimized_generate_response(
    prompt="What were the key outcomes?",
    interaction_type="question_generation",
    use_cache=True
)
```

### 2. Conversation Context Optimization

**Purpose**: Optimize conversation context to improve AI response quality while staying within token limits.

**Key Components**:
- `ConversationContextOptimizer`: Intelligently compresses conversation history
- Exchange importance scoring
- Key insights extraction
- Context summarization

**Benefits**:
- Better AI responses through optimized context
- Reduced token usage
- Maintains conversation continuity

**Features**:
- Smart truncation of conversation history
- Importance-based exchange selection
- Automatic context summarization
- Key insights extraction

### 3. Batch Processing

**Purpose**: Process multiple AI requests efficiently for non-real-time operations.

**Key Components**:
- `BatchProcessor`: Handles batch request processing
- Celery integration for asynchronous processing
- Progress tracking and error handling
- Rate limit management

**Benefits**:
- Efficient processing of large request volumes
- Better rate limit management
- Reduced system load during peak times

**Usage**:
```python
from apps.ai_engine.tasks import schedule_batch_ai_processing

requests = [
    {"id": "1", "prompt": "Analyze meeting 1"},
    {"id": "2", "prompt": "Analyze meeting 2"}
]

task_id = schedule_batch_ai_processing(requests, "analysis_job")
```

### 4. AI Usage Monitoring and Cost Optimization

**Purpose**: Monitor AI usage patterns and provide cost optimization insights.

**Key Components**:
- `AIUsageMonitor`: Tracks usage metrics and costs
- Performance analytics
- Cost estimation and savings tracking
- Optimization recommendations

**Metrics Tracked**:
- Total API interactions
- Success/error rates
- Response times
- Token usage and costs
- Cache performance
- Error patterns

**Reports Available**:
- Daily/weekly usage reports
- Cost analysis and savings
- Performance trends
- Optimization suggestions

### 5. Fallback Mechanisms

**Purpose**: Ensure system availability when AI services are unavailable.

**Key Components**:
- `FallbackManager`: Provides fallback responses
- Health monitoring
- Graceful degradation
- Service status tracking

**Fallback Strategies**:
- Pre-defined question templates
- Basic data extraction patterns
- Service health monitoring
- Automatic failover

## Configuration

### Settings

Add to your Django settings:

```python
# AI Optimization Settings
AI_CACHE_TTL_SECONDS = 3600  # 1 hour
AI_MAX_CACHE_SIZE = 10000
AI_SIMILARITY_THRESHOLD = 0.85
AI_ENABLE_SEMANTIC_CACHING = True
AI_ENABLE_CONTEXT_AWARE_CACHING = True

# Batch Processing
AI_BATCH_SIZE = 10
AI_BATCH_DELAY = 2  # seconds

# Cost Tracking
GEMINI_COST_PER_1K_TOKENS = 0.001
AI_ENABLE_COST_TRACKING = True

# Fallback Configuration
AI_ENABLE_FALLBACK = True
AI_FALLBACK_TIMEOUT = 5  # seconds
```

### Celery Tasks

Add to your Celery beat schedule:

```python
CELERY_BEAT_SCHEDULE = {
    'cleanup-ai-cache': {
        'task': 'apps.ai_engine.tasks.cleanup_ai_cache',
        'schedule': 3600.0,  # Every hour
    },
    'generate-daily-usage-report': {
        'task': 'apps.ai_engine.tasks.generate_usage_report',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'kwargs': {'days': 1},
    },
    'health-check-ai-services': {
        'task': 'apps.ai_engine.tasks.health_check_ai_services',
        'schedule': 300.0,  # Every 5 minutes
    },
}
```

## API Endpoints

### Optimization Status
```
GET /api/ai-engine/optimization/status/?days=7
```

### Cache Metrics
```
GET /api/ai-engine/optimization/cache/metrics/?days=7
```

### Trigger Cache Cleanup
```
POST /api/ai-engine/optimization/cache/cleanup/
```

### Schedule Batch Processing
```
POST /api/ai-engine/optimization/batch/schedule/
{
    "requests": [
        {"id": "1", "prompt": "Test prompt 1"},
        {"id": "2", "prompt": "Test prompt 2"}
    ],
    "job_name": "test_batch",
    "priority": "normal"
}
```

### Service Health
```
GET /api/ai-engine/optimization/service/health/
```

### Generate Usage Report
```
POST /api/ai-engine/optimization/report/generate/
{
    "days": 7,
    "email_recipients": ["admin@example.com"]
}
```

### Optimization Suggestions
```
GET /api/ai-engine/optimization/suggestions/?days=7
```

## Management Commands

### Cache Maintenance
```bash
# Clean up expired cache entries
python manage.py ai_cache_maintenance --cleanup

# Show cache statistics
python manage.py ai_cache_maintenance --stats --days=7

# Optimize cache performance
python manage.py ai_cache_maintenance --optimize
```

### Usage Reports
```bash
# Generate text report
python manage.py ai_usage_report --days=7

# Generate JSON report
python manage.py ai_usage_report --days=7 --format=json

# Save to file
python manage.py ai_usage_report --days=7 --output=usage_report.txt
```

## Monitoring and Alerts

### Performance Thresholds

The system monitors the following metrics:

- **Cache Hit Rate**: Target >60%, Excellent >80%
- **Error Rate**: Target <5%, Excellent <1%
- **Response Time**: Target <2s, Excellent <1s
- **Cost per Interaction**: Target <$0.01, Excellent <$0.001

### Optimization Suggestions

The system automatically generates optimization suggestions based on usage patterns:

- Low cache hit rate → Review caching strategy
- High error rate → Improve error handling
- Rate limit errors → Implement better request spacing
- High usage volume → Consider more aggressive caching

## Integration Examples

### Using Optimized AI Service

```python
from apps.ai_engine.caching_optimization import get_optimization_service

# Get optimization service
optimization_service = get_optimization_service()

# Generate optimized response with full features
response = optimization_service.optimized_generate_response(
    prompt="What were the key outcomes of this meeting?",
    system_prompt="You are a meeting analysis assistant.",
    interaction_type="question_generation",
    context={"meeting_id": "123", "meeting_type": "discovery"},
    conversation_history=[
        {"question": "Previous question", "response": "Previous response"}
    ],
    use_cache=True,
    use_fallback=True
)

print(f"Response: {response.content}")
print(f"Cached: {response.cached}")
print(f"Confidence: {response.confidence_score}")
```

### Batch Processing Example

```python
from apps.ai_engine.tasks import schedule_batch_ai_processing

# Prepare batch requests
requests = []
for meeting_id in meeting_ids:
    requests.append({
        "id": meeting_id,
        "prompt": f"Analyze meeting {meeting_id}",
        "system_prompt": "You are a meeting analyzer.",
        "interaction_type": "data_extraction",
        "context": {"meeting_id": meeting_id}
    })

# Schedule batch processing
task_id = schedule_batch_ai_processing(
    requests=requests,
    job_name="meeting_analysis_batch",
    priority="normal"
)

print(f"Batch job scheduled: {task_id}")
```

### Monitoring Integration

```python
from apps.ai_engine.caching_optimization import get_optimization_service

# Get optimization report
optimization_service = get_optimization_service()
report = optimization_service.get_optimization_report(days=7)

# Check key metrics
usage_metrics = report['usage_metrics']
cache_metrics = usage_metrics['cache_metrics']

print(f"Cache hit rate: {cache_metrics['estimated_hit_rate']:.2%}")
print(f"Cost savings: ${cache_metrics['estimated_cost_savings']:.4f}")
print(f"API calls saved: {cache_metrics['estimated_api_calls_saved']}")

# Get optimization suggestions
suggestions = usage_metrics['optimization_suggestions']
for suggestion in suggestions:
    print(f"• {suggestion}")
```

## Performance Impact

### Expected Improvements

- **Cost Reduction**: 30-70% reduction in API costs through intelligent caching
- **Response Time**: 50-90% faster responses for cached content
- **System Reliability**: 99.9% uptime through fallback mechanisms
- **Resource Efficiency**: 40-60% reduction in API calls through optimization

### Monitoring Results

The system tracks and reports on:
- Cache hit rates and performance
- Cost savings and API call reduction
- Error rates and system reliability
- Response times and user experience

## Troubleshooting

### Common Issues

1. **Low Cache Hit Rate**
   - Check similarity threshold settings
   - Review prompt patterns for consistency
   - Consider enabling semantic caching

2. **High Error Rates**
   - Check API key configuration
   - Review rate limiting settings
   - Verify network connectivity

3. **Performance Issues**
   - Monitor cache size and eviction
   - Check batch processing configuration
   - Review context optimization settings

### Debug Commands

```bash
# Check cache status
python manage.py ai_cache_maintenance --stats

# Test optimization features
curl -X POST /api/ai-engine/optimization/test/ \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test prompt", "use_cache": true}'

# Check service health
curl /api/ai-engine/optimization/service/health/
```

## Future Enhancements

- Advanced semantic similarity using embeddings
- Machine learning-based cache optimization
- Predictive batch processing
- Advanced cost optimization algorithms
- Real-time performance tuning