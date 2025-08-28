# Intelligent Questioning System

## Overview

The Intelligent Questioning System is a comprehensive AI-powered solution for generating context-aware questions, analyzing responses, and providing intelligent follow-up questions during meeting debriefings. It implements advanced sentiment analysis, competitive intelligence probing, technical requirement capture, and incomplete response handling.

## Key Components

### 1. SentimentAnalyzer
Analyzes sentiment and emotional indicators in user responses to adapt questioning strategy.

**Features:**
- Multi-tier sentiment analysis (positive, negative, neutral)
- Urgency level detection (low, medium, high)
- Competitive context identification
- Confidence scoring based on indicator density

**Usage:**
```python
from apps.ai_engine.intelligent_questioning import SentimentAnalyzer

analyzer = SentimentAnalyzer()
result = analyzer.analyze_sentiment("I'm excited about this solution!")
# Returns: {'primary_sentiment': 'positive', 'urgency_level': 'low', ...}
```

### 2. CompetitiveIntelligenceProber
Specialized probing for competitive intelligence gathering when competitors are mentioned.

**Features:**
- Detects competitive keywords and competitor names
- Generates targeted competitive intelligence questions
- Analyzes competitive intensity and aspects mentioned

**Usage:**
```python
from apps.ai_engine.intelligent_questioning import CompetitiveIntelligenceProber

prober = CompetitiveIntelligenceProber()
analysis = prober.detect_competitive_mentions("We're comparing with Salesforce")
probes = prober.generate_competitive_probes(analysis, meeting_context)
```

### 3. TechnicalRequirementCapture
Captures technical requirements from complex discussions.

**Features:**
- Detects technical keywords across multiple categories
- Assesses technical complexity (low/medium/high)
- Generates technical requirement questions
- Identifies integration, security, and performance focus areas

**Usage:**
```python
from apps.ai_engine.intelligent_questioning import TechnicalRequirementCapture

capture = TechnicalRequirementCapture()
analysis = capture.detect_technical_discussion("We need API integration and SSO")
probes = capture.generate_technical_probes(analysis, meeting_context)
```

### 4. IncompleteResponseHandler
Handles incomplete responses with guided prompts.

**Features:**
- Assesses response completeness using multiple criteria
- Detects vague responses and incomplete indicators
- Generates guided prompts for clarification
- Category-specific prompting strategies

**Usage:**
```python
from apps.ai_engine.intelligent_questioning import IncompleteResponseHandler

handler = IncompleteResponseHandler()
assessment = handler.assess_response_completeness("It's fine.", "budget")
prompt = handler.generate_guided_prompt(question, response, assessment, category)
```

### 5. IntelligentQuestioningSystem
Main orchestrating system that combines all components.

**Features:**
- Context-aware question generation based on meeting type
- Intelligent follow-up question logic
- AI-enhanced question alternatives
- Comprehensive logging and monitoring

**Usage:**
```python
from apps.ai_engine.intelligent_questioning import IntelligentQuestioningSystem

system = IntelligentQuestioningSystem()

# Generate context-aware questions
questions = system.generate_context_aware_questions(meeting_id, count=5)

# Process response and generate follow-up
result = system.process_response_and_generate_followup(
    original_question, user_response, meeting_context
)
```

## Convenience Functions

### Generate Meeting Questions
```python
from apps.ai_engine.intelligent_questioning import generate_meeting_questions

questions = generate_meeting_questions(meeting_id, count=5)
```

### Process Debriefing Response
```python
from apps.ai_engine.intelligent_questioning import process_debriefing_response

result = process_debriefing_response(question, response, meeting_id)
```

## Integration with Existing Systems

The Intelligent Questioning System integrates seamlessly with:

- **ContextInjectionService**: Provides meeting context and history
- **MeetingTypeStrategy**: Supplies meeting-specific questioning approaches
- **GeminiClient**: Powers AI-enhanced question generation
- **AIInteraction**: Logs interactions for monitoring and improvement
- **ConversationFlowManager**: Provides structured question generation

## Question Generation Strategies

### By Meeting Type
- **Discovery**: Focus on pain points, stakeholders, budget, timeline
- **Demo**: Emphasize feature interest, technical concerns, user feedback
- **Negotiation**: Probe pricing, terms, decision process, objections
- **Follow-up**: Track action items, progress updates, timeline changes

### By Response Analysis
- **Incomplete**: Guided prompts for clarification and expansion
- **Competitive**: Targeted competitive intelligence gathering
- **Technical**: Deep-dive into technical requirements and constraints
- **Sentiment-based**: Appropriate responses to positive/negative sentiment

## Monitoring and Analytics

The system provides comprehensive logging through:
- **AIInteraction**: Tracks all question generation and response analysis
- **Performance Metrics**: Response times, confidence scores, success rates
- **Usage Analytics**: Question effectiveness, follow-up success rates

## Error Handling

Robust error handling includes:
- Fallback questions when context-aware generation fails
- Graceful degradation when AI services are unavailable
- Comprehensive error logging for debugging and improvement

## Testing

The system includes comprehensive tests:
- Unit tests for individual components
- Integration tests for system workflows
- Performance tests for response times
- Accuracy tests for sentiment and competitive detection

Run tests with:
```bash
python test_simple_questioning.py  # Core logic tests
python test_task_requirements.py   # Requirements verification
```

## Requirements Satisfied

This implementation satisfies all Task 5.4 requirements:

✅ **Context-aware question generation based on meeting type**
- Implemented in `IntelligentQuestioningSystem.generate_context_aware_questions()`
- Uses meeting context to determine appropriate question strategy
- Different question sets for discovery, demo, negotiation, follow-up meetings

✅ **Follow-up question logic based on user responses**
- Implemented in `IntelligentQuestioningSystem.process_response_and_generate_followup()`
- Analyzes response completeness, sentiment, competitive mentions, technical content
- Generates appropriate follow-up strategy based on comprehensive analysis

✅ **Competitive intelligence probing when competitors are mentioned**
- Implemented in `CompetitiveIntelligenceProber` class
- Detects competitive keywords and extracts potential competitor names
- Generates targeted competitive intelligence questions and probes

✅ **Sentiment-based questioning for customer concerns**
- Implemented in `SentimentAnalyzer` class
- Analyzes positive, negative, neutral sentiment with confidence scoring
- Generates sentiment-appropriate follow-up questions and recommendations

✅ **Technical requirement capture for complex discussions**
- Implemented in `TechnicalRequirementCapture` class
- Detects technical complexity across integration, security, performance domains
- Generates technical requirement questions and identifies stakeholders

✅ **Incomplete response handling with guided prompts**
- Implemented in `IncompleteResponseHandler` class
- Assesses response completeness using multiple criteria and scoring
- Generates guided prompts for clarification, expansion, and completion

## Future Enhancements

Potential improvements include:
- Machine learning-based sentiment analysis
- Advanced NLP for competitor name extraction
- Dynamic question weighting based on success rates
- Real-time question effectiveness feedback
- Integration with CRM data for enhanced context