"""
Intelligent Questioning System for Meeting Intelligence
Implements context-aware question generation, follow-up logic, competitive intelligence probing,
sentiment-based questioning, technical requirement capture, and incomplete response handling.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzes sentiment in user responses to adapt questioning strategy"""
    
    def __init__(self):
        self.positive_indicators = [
            'excited', 'great', 'perfect', 'excellent', 'love', 'like', 'impressed',
            'interested', 'fantastic', 'amazing', 'wonderful', 'good', 'pleased',
            'happy', 'satisfied', 'thrilled', 'delighted', 'positive', 'optimistic'
        ]
        
        self.negative_indicators = [
            'concerned', 'worried', 'disappointed', 'frustrated', 'upset', 'angry',
            'dissatisfied', 'unhappy', 'skeptical', 'doubtful', 'hesitant', 'reluctant',
            'problem', 'issue', 'challenge', 'difficulty', 'obstacle', 'barrier'
        ]
        
        self.urgency_indicators = [
            'urgent', 'asap', 'immediately', 'quickly', 'soon', 'deadline', 'rush',
            'critical', 'important', 'priority', 'time-sensitive'
        ]
        
        self.competitive_indicators = [
            'competitor', 'alternative', 'other vendor', 'comparing', 'evaluation',
            'shortlist', 'rfp', 'proposal', 'bidding', 'selection process'
        ]
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment and emotional indicators in text"""
        text_lower = text.lower()
        
        positive_count = sum(1 for indicator in self.positive_indicators if indicator in text_lower)
        negative_count = sum(1 for indicator in self.negative_indicators if indicator in text_lower)
        
        total_indicators = positive_count + negative_count
        if total_indicators == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (positive_count - negative_count) / total_indicators
        
        if sentiment_score > 0.3:
            primary_sentiment = 'positive'
        elif sentiment_score < -0.3:
            primary_sentiment = 'negative'
        else:
            primary_sentiment = 'neutral'
        
        urgency_count = sum(1 for indicator in self.urgency_indicators if indicator in text_lower)
        urgency_level = 'high' if urgency_count >= 2 else 'medium' if urgency_count == 1 else 'low'
        
        competitive_count = sum(1 for indicator in self.competitive_indicators if indicator in text_lower)
        competitive_context = competitive_count > 0
        
        return {
            'sentiment_score': sentiment_score,
            'primary_sentiment': primary_sentiment,
            'positive_indicators': positive_count,
            'negative_indicators': negative_count,
            'urgency_level': urgency_level,
            'competitive_context': competitive_context,
            'confidence': min(1.0, total_indicators / 5.0)
        }


class CompetitiveIntelligenceProber:
    """Specialized probing for competitive intelligence gathering"""
    
    def __init__(self):
        self.competitive_keywords = [
            'competitor', 'alternative', 'other vendor', 'comparing', 'evaluation',
            'shortlist', 'rfp', 'proposal', 'bidding', 'selection process'
        ]
    
    def detect_competitive_mentions(self, text: str) -> Dict[str, Any]:
        """Detect and analyze competitive mentions in text"""
        text_lower = text.lower()
        mentioned_keywords = [kw for kw in self.competitive_keywords if kw in text_lower]
        
        return {
            'has_competitive_mentions': len(mentioned_keywords) > 0,
            'competitive_keywords': mentioned_keywords,
            'competitive_intensity': len(mentioned_keywords)
        }


class TechnicalRequirementCapture:
    """Captures technical requirements from complex discussions"""
    
    def __init__(self):
        self.technical_keywords = [
            'integration', 'api', 'database', 'security', 'authentication',
            'scalability', 'performance', 'latency', 'cloud', 'deployment'
        ]
    
    def detect_technical_discussion(self, text: str) -> Dict[str, Any]:
        """Detect technical requirements and concerns in text"""
        text_lower = text.lower()
        technical_count = sum(1 for kw in self.technical_keywords if kw in text_lower)
        
        if technical_count >= 3:
            complexity = 'high'
        elif technical_count >= 1:
            complexity = 'medium'
        else:
            complexity = 'low'
        
        return {
            'has_technical_content': technical_count > 0,
            'complexity': complexity,
            'technical_intensity': technical_count
        }


class IncompleteResponseHandler:
    """Handles incomplete responses with guided prompts"""
    
    def __init__(self):
        self.vague_responses = ['fine', 'okay', 'good', 'yes', 'no', 'maybe', 'sure']
    
    def assess_response_completeness(self, response: str, question_category: str) -> Dict[str, Any]:
        """Assess if a response is complete and informative"""
        response_clean = response.strip().lower()
        word_count = len(response.split())
        
        is_vague = any(vague in response_clean for vague in self.vague_responses)
        is_too_short = word_count < 5
        
        completeness_score = 0.2 if is_vague else (0.4 if is_too_short else min(1.0, word_count / 15.0))
        
        return {
            'is_complete': completeness_score >= 0.7 and not is_too_short and not is_vague,
            'completeness_score': completeness_score,
            'is_vague': is_vague,
            'is_too_short': is_too_short,
            'word_count': word_count,
            'needs_follow_up': completeness_score < 0.7 or is_vague
        }
    
    def generate_guided_prompt(self, original_question: str, response: str, assessment: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Generate guided prompt to elicit more complete response"""
        if assessment['is_vague']:
            return {
                'type': 'clarification',
                'prompt': 'I would love to get more specific details. Can you walk me through that in more depth?',
                'reasoning': 'Response was too vague'
            }
        elif assessment['is_too_short']:
            return {
                'type': 'expansion',
                'prompt': 'That is a good start. Can you elaborate on that? What specific aspects can you share?',
                'reasoning': 'Response was too brief'
            }
        else:
            return {
                'type': 'category_specific',
                'prompt': 'Can you provide more context around that?',
                'reasoning': f'Seeking more depth in {category} discussion'
            }


class IntelligentQuestioningSystem:
    """Main system orchestrating intelligent questioning capabilities"""
    
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.competitive_prober = CompetitiveIntelligenceProber()
        self.technical_capture = TechnicalRequirementCapture()
        self.response_handler = IncompleteResponseHandler()
    
    def generate_context_aware_questions(self, meeting_id: str, question_count: int = 5) -> List[Dict[str, Any]]:
        """Generate context-aware questions based on meeting type and context"""
        # Fallback questions for now
        fallback_questions = [
            {
                'category': 'meeting_outcome',
                'priority': 'high',
                'question': 'How would you summarize the overall outcome of this meeting?'
            },
            {
                'category': 'key_insights',
                'priority': 'high',
                'question': 'What were the key insights or takeaways from the conversation?'
            },
            {
                'category': 'next_steps',
                'priority': 'high',
                'question': 'What are the agreed-upon next steps and who is responsible for each?'
            },
            {
                'category': 'concerns',
                'priority': 'medium',
                'question': 'Were there any concerns or objections raised during the meeting?'
            },
            {
                'category': 'timeline',
                'priority': 'medium',
                'question': 'What timeline did they express for moving forward?'
            }
        ]
        return fallback_questions[:question_count]
    
    def process_response_and_generate_followup(self, original_question: Dict[str, Any], user_response: str, meeting_context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user response and generate intelligent follow-up"""
        try:
            # Analyze response
            completeness = self.response_handler.assess_response_completeness(user_response, original_question.get('category', 'general'))
            sentiment = self.sentiment_analyzer.analyze_sentiment(user_response)
            competitive = self.competitive_prober.detect_competitive_mentions(user_response)
            technical = self.technical_capture.detect_technical_discussion(user_response)
            
            # Generate follow-up
            follow_up_question = None
            strategy = 'none'
            
            if not completeness['is_complete']:
                follow_up_question = self.response_handler.generate_guided_prompt(
                    original_question['question'], user_response, completeness, original_question.get('category', 'general')
                )
                strategy = 'clarification'
            elif competitive['has_competitive_mentions']:
                follow_up_question = {
                    'type': 'competitive_intelligence',
                    'prompt': 'You mentioned competitive alternatives. How are you approaching the comparison process?',
                    'reasoning': 'Competitive situation detected'
                }
                strategy = 'competitive_intelligence'
            elif sentiment['primary_sentiment'] == 'negative':
                follow_up_question = {
                    'type': 'concern_exploration',
                    'prompt': 'I am sensing some concerns. What specific aspects are causing hesitation?',
                    'reasoning': 'Negative sentiment detected'
                }
                strategy = 'concern_exploration'
            elif technical['has_technical_content'] and technical['complexity'] == 'high':
                follow_up_question = {
                    'type': 'technical_deep_dive',
                    'prompt': 'You mentioned several technical requirements. Can you describe your current technical environment?',
                    'reasoning': 'High technical complexity detected'
                }
                strategy = 'technical_deep_dive'
            
            return {
                'analysis': {
                    'completeness': completeness,
                    'sentiment': sentiment,
                    'competitive': competitive,
                    'technical': technical
                },
                'follow_up_question': follow_up_question,
                'strategy': strategy
            }
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return {
                'analysis': {},
                'follow_up_question': None,
                'strategy': 'error',
                'error': str(e)
            }


# Convenience functions
def generate_meeting_questions(meeting_id: str, count: int = 5) -> List[Dict[str, Any]]:
    """Convenience function to generate questions for a meeting"""
    system = IntelligentQuestioningSystem()
    return system.generate_context_aware_questions(meeting_id, count)


def process_debriefing_response(question: Dict[str, Any], response: str, meeting_id: str) -> Dict[str, Any]:
    """Convenience function to process a debriefing response"""
    system = IntelligentQuestioningSystem()
    meeting_context = {'meeting_id': meeting_id}
    return system.process_response_and_generate_followup(question, response, meeting_context)
