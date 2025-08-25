"""
AI integration for debriefing conversations
Simplified implementation for the conversation interface
"""
import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class DebriefingAIService:
    """
    Simplified AI service for debriefing conversations
    This is a mock implementation that will be replaced with actual Gemini integration
    """
    
    def __init__(self):
        self.fallback_questions = [
            {
                'question_text': 'How would you describe the overall outcome of this meeting?',
                'question_type': 'outcome',
                'question_order': 1,
                'ai_context': {'type': 'opening', 'priority': 'high'}
            },
            {
                'question_text': 'What were the key topics or agenda items discussed?',
                'question_type': 'topics',
                'question_order': 2,
                'ai_context': {'type': 'content', 'priority': 'high'}
            },
            {
                'question_text': 'Were there any specific next steps or action items agreed upon?',
                'question_type': 'follow_up',
                'question_order': 3,
                'ai_context': {'type': 'actions', 'priority': 'high'}
            },
            {
                'question_text': 'Did any concerns, objections, or challenges come up during the discussion?',
                'question_type': 'objections',
                'question_order': 4,
                'ai_context': {'type': 'challenges', 'priority': 'medium'}
            },
            {
                'question_text': 'What was the general sentiment or engagement level of the participants?',
                'question_type': 'sentiment',
                'question_order': 5,
                'ai_context': {'type': 'assessment', 'priority': 'medium'}
            },
            {
                'question_text': 'Were there any competitive products or solutions mentioned?',
                'question_type': 'competitive',
                'question_order': 6,
                'ai_context': {'type': 'intelligence', 'priority': 'medium'}
            },
            {
                'question_text': 'Was budget or pricing discussed in any capacity?',
                'question_type': 'budget',
                'question_order': 7,
                'ai_context': {'type': 'commercial', 'priority': 'low'}
            },
            {
                'question_text': 'What are the expected timelines for next steps or decisions?',
                'question_type': 'timeline',
                'question_order': 8,
                'ai_context': {'type': 'planning', 'priority': 'medium'}
            }
        ]
    
    async def generate_debriefing_questions(
        self, 
        meeting_context: Dict[str, Any],
        template_context: Optional[List[Dict]] = None,
        question_count: int = 8
    ) -> 'MockAIResponse':
        """
        Generate initial debriefing questions based on meeting context
        """
        try:
            # Use template questions if available, otherwise use fallback
            if template_context and isinstance(template_context, list):
                questions = template_context[:question_count]
            else:
                questions = self.fallback_questions[:question_count]
            
            # Customize questions based on meeting type
            meeting_type = meeting_context.get('meeting_type', 'general')
            customized_questions = self._customize_questions_for_meeting_type(questions, meeting_type)
            
            return MockAIResponse(
                content="Generated debriefing questions",
                parsed_data={'questions': customized_questions},
                confidence_score=0.8,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error generating debriefing questions: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'questions': self.fallback_questions[:4]},  # Minimal fallback
                confidence_score=0.3,
                error=str(e)
            )
    
    def _customize_questions_for_meeting_type(
        self, 
        questions: List[Dict[str, Any]], 
        meeting_type: str
    ) -> List[Dict[str, Any]]:
        """Customize questions based on meeting type"""
        customized = []
        
        for question in questions:
            customized_question = question.copy()
            
            # Customize based on meeting type
            if meeting_type == 'discovery':
                if question['question_type'] == 'outcome':
                    customized_question['question_text'] = 'How successful was this discovery call in understanding the prospect\'s needs?'
                elif question['question_type'] == 'topics':
                    customized_question['question_text'] = 'What specific pain points or challenges did the prospect share?'
            
            elif meeting_type == 'demo':
                if question['question_type'] == 'outcome':
                    customized_question['question_text'] = 'How engaged was the prospect during the product demonstration?'
                elif question['question_type'] == 'topics':
                    customized_question['question_text'] = 'Which features or capabilities generated the most interest?'
            
            elif meeting_type == 'negotiation':
                if question['question_type'] == 'outcome':
                    customized_question['question_text'] = 'What progress was made in the negotiation process?'
                elif question['question_type'] == 'budget':
                    customized_question['question_text'] = 'What specific pricing or contract terms were discussed?'
            
            customized.append(customized_question)
        
        return customized
    
    async def extract_response_data(
        self,
        question_text: str,
        response_text: str,
        question_type: str,
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Extract structured data from user response
        """
        try:
            # Simple extraction based on question type
            extracted_data = {}
            
            if question_type == 'outcome':
                extracted_data = {
                    'meeting_outcome': response_text[:200],
                    'sentiment': self._extract_sentiment(response_text),
                    'success_indicators': self._extract_success_indicators(response_text)
                }
            
            elif question_type == 'topics':
                extracted_data = {
                    'topics_discussed': self._extract_topics(response_text),
                    'key_points': self._extract_key_points(response_text)
                }
            
            elif question_type == 'follow_up':
                extracted_data = {
                    'action_items': self._extract_action_items(response_text),
                    'next_steps': self._extract_next_steps(response_text)
                }
            
            elif question_type == 'competitive':
                extracted_data = {
                    'competitors_mentioned': self._extract_competitors(response_text),
                    'competitive_context': response_text
                }
            
            elif question_type == 'budget':
                extracted_data = {
                    'budget_discussed': 'budget' in response_text.lower() or 'price' in response_text.lower(),
                    'budget_context': response_text if 'budget' in response_text.lower() else None
                }
            
            else:
                extracted_data = {
                    'response_summary': response_text[:100],
                    'response_length': len(response_text)
                }
            
            confidence = self._calculate_extraction_confidence(response_text, extracted_data)
            
            return MockAIResponse(
                content="Extracted structured data",
                parsed_data=extracted_data,
                confidence_score=confidence,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error extracting response data: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'error': 'extraction_failed'},
                confidence_score=0.1,
                error=str(e)
            )
    
    async def generate_response_insights(
        self,
        question_type: str,
        response_text: str,
        extracted_data: Dict[str, Any],
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Generate insights from response data
        """
        try:
            insights = []
            
            # Generate insights based on question type and response
            if question_type == 'outcome' and 'positive' in response_text.lower():
                insights.append({
                    'type': 'opportunity',
                    'title': 'Positive Meeting Outcome',
                    'description': 'The meeting outcome appears positive, indicating good engagement.',
                    'confidence_level': 'high',
                    'confidence_score': 0.8,
                    'suggested_actions': ['Schedule follow-up meeting', 'Send summary email'],
                    'priority': 'high'
                })
            
            if question_type == 'competitive' and extracted_data.get('competitors_mentioned'):
                insights.append({
                    'type': 'competitive_threat',
                    'title': 'Competitive Mention Detected',
                    'description': 'Competitors were mentioned during the meeting.',
                    'confidence_level': 'medium',
                    'confidence_score': 0.7,
                    'suggested_actions': ['Prepare competitive analysis', 'Address competitive concerns'],
                    'priority': 'medium'
                })
            
            if question_type == 'budget' and extracted_data.get('budget_discussed'):
                insights.append({
                    'type': 'buying_signal',
                    'title': 'Budget Discussion Indicates Interest',
                    'description': 'Budget or pricing discussion suggests serious consideration.',
                    'confidence_level': 'high',
                    'confidence_score': 0.85,
                    'suggested_actions': ['Prepare formal proposal', 'Discuss pricing options'],
                    'priority': 'high'
                })
            
            return MockAIResponse(
                content="Generated insights",
                parsed_data={'insights': insights},
                confidence_score=0.75,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'insights': []},
                confidence_score=0.1,
                error=str(e)
            )
    
    async def generate_follow_up_questions(
        self,
        original_question: str,
        response_text: str,
        extracted_data: Dict[str, Any],
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Generate follow-up questions based on response
        """
        try:
            follow_up_questions = []
            
            # Generate follow-ups based on response content
            if len(response_text.strip()) < 20:
                follow_up_questions.append({
                    'question_text': 'Could you provide more details about that?',
                    'question_type': 'clarification',
                    'ai_context': {'reason': 'short_response'}
                })
            
            if 'competitor' in response_text.lower() and not extracted_data.get('competitors_mentioned'):
                follow_up_questions.append({
                    'question_text': 'Which specific competitors were mentioned and in what context?',
                    'question_type': 'competitive',
                    'ai_context': {'reason': 'competitor_mentioned'}
                })
            
            if 'budget' in response_text.lower() or 'price' in response_text.lower():
                follow_up_questions.append({
                    'question_text': 'What specific budget or pricing information was discussed?',
                    'question_type': 'budget',
                    'ai_context': {'reason': 'budget_mentioned'}
                })
            
            return MockAIResponse(
                content="Generated follow-up questions",
                parsed_data={'questions': follow_up_questions},
                confidence_score=0.7,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'questions': []},
                confidence_score=0.1,
                error=str(e)
            )
    
    async def generate_question_clarification(
        self,
        question_text: str,
        question_type: str,
        clarification_type: str,
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Generate clarification for a question
        """
        try:
            clarifications = {
                'outcome': 'This question is asking about the overall result or success of the meeting. Consider factors like engagement level, progress made, and whether objectives were met.',
                'topics': 'Please list the main subjects, agenda items, or discussion points that were covered during the meeting.',
                'follow_up': 'Think about any commitments made, tasks assigned, or next steps that were agreed upon by any participants.',
                'competitive': 'Were any other companies, products, or solutions mentioned as alternatives or comparisons?',
                'budget': 'Was there any discussion about costs, pricing, budget constraints, or financial considerations?',
                'timeline': 'Were any dates, deadlines, or timeframes mentioned for decisions or next actions?'
            }
            
            clarification = clarifications.get(
                question_type, 
                'Please provide any relevant details or information related to this question.'
            )
            
            return MockAIResponse(
                content=clarification,
                parsed_data={'clarification': clarification},
                confidence_score=0.9,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error generating clarification: {str(e)}")
            return MockAIResponse(
                content="Could you please provide more details?",
                parsed_data={'clarification': "Could you please provide more details?"},
                confidence_score=0.3,
                error=str(e)
            )
    
    async def extract_final_conversation_data(
        self,
        conversation_data: List[Dict[str, Any]],
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Extract and consolidate final structured data from entire conversation
        """
        try:
            # Consolidate data from all responses
            final_data = {
                'meeting_outcome': 'Unknown',
                'key_topics': [],
                'action_items': [],
                'next_steps': [],
                'participants_mentioned': [],
                'competitive_intelligence': [],
                'budget_information': {},
                'timeline_information': {},
                'concerns_objections': [],
                'buying_signals': [],
                'extraction_method': 'ai_consolidation',
                'confidence_score': 0.7
            }
            
            # Process each conversation entry
            for entry in conversation_data:
                question_type = entry.get('question_type', '')
                response = entry.get('response', '')
                extracted = entry.get('extracted_entities', {})
                
                if question_type == 'outcome':
                    final_data['meeting_outcome'] = response[:200]
                elif question_type == 'topics':
                    final_data['key_topics'].extend(self._extract_topics(response))
                elif question_type == 'follow_up':
                    final_data['action_items'].extend(self._extract_action_items(response))
                    final_data['next_steps'].extend(self._extract_next_steps(response))
                elif question_type == 'competitive':
                    competitors = self._extract_competitors(response)
                    if competitors:
                        final_data['competitive_intelligence'].extend(competitors)
                elif question_type == 'budget':
                    if 'budget' in response.lower() or 'price' in response.lower():
                        final_data['budget_information']['discussed'] = True
                        final_data['budget_information']['context'] = response
                elif question_type == 'objections':
                    final_data['concerns_objections'].append(response)
            
            # Detect buying signals
            if final_data['budget_information'].get('discussed'):
                final_data['buying_signals'].append('Budget discussion indicates serious interest')
            
            if any('positive' in topic.lower() for topic in final_data['key_topics']):
                final_data['buying_signals'].append('Positive engagement during meeting')
            
            return MockAIResponse(
                content="Consolidated conversation data",
                parsed_data=final_data,
                confidence_score=0.75,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error extracting final conversation data: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'error': 'final_extraction_failed'},
                confidence_score=0.1,
                error=str(e)
            )
    
    async def generate_final_insights(
        self,
        extracted_data: Dict[str, Any],
        conversation_insights: List[Dict[str, Any]],
        meeting_context: Dict[str, Any]
    ) -> 'MockAIResponse':
        """
        Generate final insights from complete conversation
        """
        try:
            final_insights = []
            
            # Analyze overall conversation for additional insights
            if extracted_data.get('buying_signals'):
                final_insights.append({
                    'type': 'opportunity',
                    'title': 'Strong Buying Signals Detected',
                    'description': f"Multiple buying signals identified: {', '.join(extracted_data['buying_signals'])}",
                    'confidence_level': 'high',
                    'confidence_score': 0.85,
                    'suggested_actions': ['Prepare proposal', 'Schedule decision meeting'],
                    'priority': 'high'
                })
            
            if extracted_data.get('competitive_intelligence'):
                final_insights.append({
                    'type': 'competitive_threat',
                    'title': 'Competitive Landscape Analysis Needed',
                    'description': f"Competitors mentioned: {', '.join(extracted_data['competitive_intelligence'])}",
                    'confidence_level': 'medium',
                    'confidence_score': 0.7,
                    'suggested_actions': ['Prepare competitive analysis', 'Develop differentiation strategy'],
                    'priority': 'medium'
                })
            
            if len(extracted_data.get('action_items', [])) > 3:
                final_insights.append({
                    'type': 'next_action',
                    'title': 'Multiple Action Items Require Follow-up',
                    'description': f"Several action items identified requiring coordination and follow-up",
                    'confidence_level': 'high',
                    'confidence_score': 0.8,
                    'suggested_actions': ['Create action item tracker', 'Schedule follow-up meetings'],
                    'priority': 'medium'
                })
            
            return MockAIResponse(
                content="Generated final insights",
                parsed_data={'insights': final_insights},
                confidence_score=0.8,
                error=None
            )
            
        except Exception as e:
            logger.error(f"Error generating final insights: {str(e)}")
            return MockAIResponse(
                content="",
                parsed_data={'insights': []},
                confidence_score=0.1,
                error=str(e)
            )
    
    # Helper methods for data extraction
    
    def _extract_sentiment(self, text: str) -> str:
        """Extract sentiment from text"""
        positive_words = ['good', 'great', 'excellent', 'positive', 'successful', 'interested']
        negative_words = ['bad', 'poor', 'negative', 'concerned', 'disappointed', 'rejected']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def _extract_success_indicators(self, text: str) -> List[str]:
        """Extract success indicators from text"""
        indicators = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['engaged', 'interested', 'excited']):
            indicators.append('High engagement')
        if any(word in text_lower for word in ['questions', 'asked', 'curious']):
            indicators.append('Active participation')
        if any(word in text_lower for word in ['next', 'follow', 'continue']):
            indicators.append('Interest in next steps')
        
        return indicators
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text"""
        # Simple topic extraction - split by common delimiters
        topics = []
        for delimiter in [',', ';', '\n', ' and ', ' & ']:
            if delimiter in text:
                topics.extend([topic.strip() for topic in text.split(delimiter) if topic.strip()])
                break
        
        if not topics:
            topics = [text.strip()]
        
        return topics[:5]  # Limit to 5 topics
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from text"""
        # Look for bullet points or numbered lists
        lines = text.split('\n')
        key_points = []
        
        for line in lines:
            line = line.strip()
            if line.startswith(('-', '*', '•')) or (len(line) > 0 and line[0].isdigit()):
                key_points.append(line)
        
        if not key_points:
            # If no structured points, split by sentences
            sentences = text.split('.')
            key_points = [s.strip() for s in sentences if len(s.strip()) > 10][:3]
        
        return key_points
    
    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action items from text"""
        action_words = ['will', 'should', 'need to', 'must', 'action', 'task', 'todo']
        action_items = []
        
        sentences = text.split('.')
        for sentence in sentences:
            if any(word in sentence.lower() for word in action_words):
                action_items.append(sentence.strip())
        
        return action_items[:5]  # Limit to 5 action items
    
    def _extract_next_steps(self, text: str) -> List[str]:
        """Extract next steps from text"""
        next_step_indicators = ['next', 'follow up', 'schedule', 'send', 'prepare', 'review']
        next_steps = []
        
        sentences = text.split('.')
        for sentence in sentences:
            if any(indicator in sentence.lower() for indicator in next_step_indicators):
                next_steps.append(sentence.strip())
        
        return next_steps[:3]  # Limit to 3 next steps
    
    def _extract_competitors(self, text: str) -> List[str]:
        """Extract competitor mentions from text"""
        # Look for company names or competitor indicators
        competitor_indicators = ['competitor', 'alternative', 'other solution', 'vendor']
        competitors = []
        
        words = text.split()
        for i, word in enumerate(words):
            if any(indicator in word.lower() for indicator in competitor_indicators):
                # Look for capitalized words nearby (potential company names)
                for j in range(max(0, i-3), min(len(words), i+4)):
                    if words[j][0].isupper() and len(words[j]) > 2:
                        competitors.append(words[j])
        
        return list(set(competitors))[:3]  # Unique competitors, limit to 3
    
    def _calculate_extraction_confidence(self, response_text: str, extracted_data: Dict[str, Any]) -> float:
        """Calculate confidence score for extraction"""
        base_confidence = 0.5
        
        # Increase confidence based on response length
        if len(response_text) > 50:
            base_confidence += 0.2
        if len(response_text) > 100:
            base_confidence += 0.1
        
        # Increase confidence based on extracted data richness
        if extracted_data and len(extracted_data) > 2:
            base_confidence += 0.1
        
        # Decrease confidence for very short responses
        if len(response_text) < 20:
            base_confidence -= 0.3
        
        return max(0.1, min(1.0, base_confidence))


class MockAIResponse:
    """
    Mock AI response object to simulate Gemini API responses
    """
    
    def __init__(self, content: str, parsed_data: Dict[str, Any], confidence_score: float, error: Optional[str]):
        self.content = content
        self.parsed_data = parsed_data
        self.confidence_score = confidence_score
        self.error = error
        self.response_time_ms = 500  # Mock response time
        self.token_count = len(content.split()) if content else 0