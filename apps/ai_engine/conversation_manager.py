"""
Conversation History and Context Management
Handles conversation continuity and context preservation across debriefing sessions
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.cache import cache

from apps.debriefings.models import DebriefingSession
from .models import AIInteraction

logger = logging.getLogger(__name__)


class ConversationHistoryManager:
    """Manages conversation history and context continuity"""
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
    
    def get_conversation_context(
        self,
        debriefing_session_id: str,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """Get comprehensive conversation context for a debriefing session"""
        try:
            session = DebriefingSession.objects.select_related('meeting').get(
                id=debriefing_session_id
            )
            
            context = {
                'session_id': str(session.id),
                'meeting_id': str(session.meeting.id),
                'session_status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'current_conversation': session.conversation_data,
                'extracted_data': session.extracted_data,
                'confidence_scores': session.confidence_scores
            }
            
            if include_history:
                context.update(self._get_conversation_history(session))
                context.update(self._get_related_conversations(session))
            
            return context
            
        except DebriefingSession.DoesNotExist:
            logger.error(f"Debriefing session {debriefing_session_id} not found")
            return {'error': 'Session not found'}
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return {'error': str(e)}
    
    def _get_conversation_history(self, session: DebriefingSession) -> Dict[str, Any]:
        """Get conversation history for the current session"""
        conversation_data = session.conversation_data or {}
        
        # Extract conversation flow
        questions_asked = conversation_data.get('questions_asked', [])
        responses_given = conversation_data.get('responses', [])
        
        # Build conversation timeline
        conversation_timeline = []
        for i, question in enumerate(questions_asked):
            timeline_entry = {
                'sequence': i + 1,
                'timestamp': question.get('timestamp'),
                'question': question.get('question'),
                'question_type': question.get('type', 'unknown'),
                'response': responses_given[i] if i < len(responses_given) else None,
                'follow_up_generated': question.get('follow_up_generated', False)
            }
            conversation_timeline.append(timeline_entry)
        
        # Analyze conversation patterns
        patterns = self._analyze_conversation_patterns(conversation_timeline)
        
        return {
            'conversation_timeline': conversation_timeline,
            'total_questions': len(questions_asked),
            'total_responses': len(responses_given),
            'completion_rate': len(responses_given) / len(questions_asked) if questions_asked else 0,
            'conversation_patterns': patterns,
            'session_duration': self._calculate_session_duration(session)
        }
    
    def _get_related_conversations(self, session: DebriefingSession) -> Dict[str, Any]:
        """Get related conversations from previous meetings with same participants"""
        try:
            # Get participants from the current meeting
            meeting = session.meeting
            participant_emails = list(
                meeting.meetingparticipant_set.filter(is_external=True)
                .values_list('email', flat=True)
            )
            
            if not participant_emails:
                return {'related_conversations': []}
            
            # Find previous meetings with same participants
            from apps.meetings.models import Meeting
            related_meetings = Meeting.objects.filter(
                meetingparticipant__email__in=participant_emails,
                start_time__lt=meeting.start_time,
                is_sales_meeting=True
            ).distinct().order_by('-start_time')[:3]
            
            related_conversations = []
            for related_meeting in related_meetings:
                try:
                    related_session = related_meeting.debriefingsession
                    if related_session.completed_at and related_session.extracted_data:
                        conversation_summary = {
                            'meeting_date': related_meeting.start_time.strftime('%Y-%m-%d'),
                            'meeting_type': related_meeting.meeting_type,
                            'key_insights': self._extract_key_insights(related_session.extracted_data),
                            'action_items': related_session.extracted_data.get('action_items', []),
                            'meeting_outcome': related_session.extracted_data.get('meeting_outcome', ''),
                            'competitive_mentions': related_session.extracted_data.get('competitive_intelligence', [])
                        }
                        related_conversations.append(conversation_summary)
                except:
                    continue
            
            return {
                'related_conversations': related_conversations,
                'relationship_continuity': len(related_conversations) > 0
            }
            
        except Exception as e:
            logger.warning(f"Error getting related conversations: {str(e)}")
            return {'related_conversations': []}
    
    def _analyze_conversation_patterns(self, timeline: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns in the conversation"""
        if not timeline:
            return {}
        
        # Response length analysis
        response_lengths = []
        short_responses = 0
        detailed_responses = 0
        
        for entry in timeline:
            if entry['response']:
                length = len(entry['response'].split())
                response_lengths.append(length)
                
                if length < 10:
                    short_responses += 1
                elif length > 30:
                    detailed_responses += 1
        
        # Question type analysis
        question_types = {}
        for entry in timeline:
            q_type = entry.get('question_type', 'unknown')
            question_types[q_type] = question_types.get(q_type, 0) + 1
        
        # Follow-up pattern analysis
        follow_ups_generated = sum(1 for entry in timeline if entry.get('follow_up_generated'))
        
        return {
            'avg_response_length': sum(response_lengths) / len(response_lengths) if response_lengths else 0,
            'short_response_rate': short_responses / len(timeline) if timeline else 0,
            'detailed_response_rate': detailed_responses / len(timeline) if timeline else 0,
            'question_type_distribution': question_types,
            'follow_up_rate': follow_ups_generated / len(timeline) if timeline else 0,
            'engagement_level': self._calculate_engagement_level(response_lengths, follow_ups_generated)
        }
    
    def _calculate_engagement_level(self, response_lengths: List[int], follow_ups: int) -> str:
        """Calculate user engagement level based on response patterns"""
        if not response_lengths:
            return 'unknown'
        
        avg_length = sum(response_lengths) / len(response_lengths)
        
        if avg_length > 25 and follow_ups > len(response_lengths) * 0.3:
            return 'high'
        elif avg_length > 15 and follow_ups > len(response_lengths) * 0.2:
            return 'medium'
        elif avg_length > 5:
            return 'low'
        else:
            return 'very_low'
    
    def _extract_key_insights(self, extracted_data: Dict) -> List[str]:
        """Extract key insights from previous conversation data"""
        insights = []
        
        # Extract from different data categories
        if 'deal_information' in extracted_data:
            deal_info = extracted_data['deal_information']
            if isinstance(deal_info, dict):
                for key, value in deal_info.items():
                    if value and isinstance(value, str) and len(value) > 10:
                        insights.append(f"{key.replace('_', ' ').title()}: {value[:100]}")
        
        if 'competitive_intelligence' in extracted_data:
            comp_intel = extracted_data['competitive_intelligence']
            if isinstance(comp_intel, list):
                for item in comp_intel[:2]:  # Limit to 2 items
                    if isinstance(item, str):
                        insights.append(f"Competitive: {item[:100]}")
        
        return insights[:5]  # Limit to 5 key insights
    
    def _calculate_session_duration(self, session: DebriefingSession) -> Optional[str]:
        """Calculate session duration in human-readable format"""
        if not session.started_at:
            return None
        
        end_time = session.completed_at or timezone.now()
        duration = end_time - session.started_at
        
        total_minutes = int(duration.total_seconds() / 60)
        
        if total_minutes < 1:
            return "Less than 1 minute"
        elif total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m"
    
    def update_conversation_state(
        self,
        debriefing_session_id: str,
        question: Dict[str, Any],
        response: Optional[str] = None,
        follow_up_question: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update conversation state with new question/response"""
        try:
            session = DebriefingSession.objects.get(id=debriefing_session_id)
            
            # Initialize conversation data if needed
            if not session.conversation_data:
                session.conversation_data = {
                    'questions_asked': [],
                    'responses': [],
                    'conversation_flow': []
                }
            
            # Add question to conversation data
            question_entry = {
                'timestamp': timezone.now().isoformat(),
                'question': question.get('question', ''),
                'type': question.get('category', 'general'),
                'priority': question.get('priority', 'medium'),
                'follow_up_generated': follow_up_question is not None
            }
            
            session.conversation_data['questions_asked'].append(question_entry)
            
            # Add response if provided
            if response:
                response_entry = {
                    'timestamp': timezone.now().isoformat(),
                    'response': response,
                    'word_count': len(response.split()),
                    'question_index': len(session.conversation_data['questions_asked']) - 1
                }
                session.conversation_data['responses'].append(response_entry)
            
            # Add follow-up question if generated
            if follow_up_question:
                followup_entry = {
                    'timestamp': timezone.now().isoformat(),
                    'question': follow_up_question.get('question', ''),
                    'type': follow_up_question.get('category', 'follow_up'),
                    'reasoning': follow_up_question.get('reasoning', ''),
                    'parent_question_index': len(session.conversation_data['questions_asked']) - 1
                }
                session.conversation_data['questions_asked'].append(followup_entry)
            
            session.save()
            
            # Cache updated context
            cache_key = f"conversation_context_{debriefing_session_id}"
            cache.delete(cache_key)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating conversation state: {str(e)}")
            return False
    
    def get_conversation_summary(self, debriefing_session_id: str) -> Dict[str, Any]:
        """Get a summary of the conversation for context injection"""
        try:
            context = self.get_conversation_context(debriefing_session_id)
            
            if 'error' in context:
                return context
            
            timeline = context.get('conversation_timeline', [])
            patterns = context.get('conversation_patterns', {})
            
            # Build summary
            summary = {
                'total_interactions': len(timeline),
                'completion_status': 'completed' if context.get('completion_rate', 0) >= 0.8 else 'in_progress',
                'engagement_level': patterns.get('engagement_level', 'unknown'),
                'key_topics_covered': self._extract_topics_from_timeline(timeline),
                'response_quality': self._assess_response_quality(patterns),
                'conversation_duration': context.get('session_duration'),
                'follow_up_effectiveness': patterns.get('follow_up_rate', 0)
            }
            
            # Add relationship context if available
            if context.get('relationship_continuity'):
                summary['relationship_context'] = {
                    'has_history': True,
                    'previous_meetings': len(context.get('related_conversations', [])),
                    'key_historical_insights': self._summarize_historical_insights(
                        context.get('related_conversations', [])
                    )
                }
            else:
                summary['relationship_context'] = {'has_history': False}
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {str(e)}")
            return {'error': str(e)}
    
    def _extract_topics_from_timeline(self, timeline: List[Dict]) -> List[str]:
        """Extract main topics discussed from conversation timeline"""
        topics = set()
        
        for entry in timeline:
            question_type = entry.get('question_type', '')
            if question_type and question_type != 'unknown':
                topics.add(question_type.replace('_', ' ').title())
        
        return list(topics)[:10]  # Limit to 10 topics
    
    def _assess_response_quality(self, patterns: Dict) -> str:
        """Assess overall response quality"""
        detailed_rate = patterns.get('detailed_response_rate', 0)
        short_rate = patterns.get('short_response_rate', 0)
        avg_length = patterns.get('avg_response_length', 0)
        
        if detailed_rate > 0.5 and avg_length > 20:
            return 'high'
        elif detailed_rate > 0.3 and avg_length > 15:
            return 'good'
        elif short_rate < 0.7 and avg_length > 10:
            return 'adequate'
        else:
            return 'needs_improvement'
    
    def _summarize_historical_insights(self, related_conversations: List[Dict]) -> List[str]:
        """Summarize key insights from historical conversations"""
        insights = []
        
        for conversation in related_conversations[:2]:  # Limit to 2 most recent
            meeting_date = conversation.get('meeting_date', 'Unknown')
            outcome = conversation.get('meeting_outcome', '')
            
            if outcome:
                insights.append(f"{meeting_date}: {outcome[:100]}")
            
            # Add key action items if available
            action_items = conversation.get('action_items', [])
            if action_items:
                insights.append(f"{meeting_date}: {len(action_items)} action items discussed")
        
        return insights[:5]  # Limit to 5 insights


class ConversationContextInjector:
    """Injects conversation context into AI prompts"""
    
    def __init__(self):
        self.history_manager = ConversationHistoryManager()
    
    def inject_context_into_prompt(
        self,
        base_prompt: str,
        debriefing_session_id: str,
        context_type: str = 'full'
    ) -> str:
        """Inject conversation context into a prompt"""
        try:
            if context_type == 'summary':
                context = self.history_manager.get_conversation_summary(debriefing_session_id)
            else:
                context = self.history_manager.get_conversation_context(debriefing_session_id)
            
            if 'error' in context:
                return base_prompt
            
            # Build context injection
            context_injection = self._build_context_injection(context, context_type)
            
            # Inject context into prompt
            if context_injection:
                enhanced_prompt = f"{base_prompt}\n\nConversation Context:\n{context_injection}"
                return enhanced_prompt
            
            return base_prompt
            
        except Exception as e:
            logger.warning(f"Error injecting context into prompt: {str(e)}")
            return base_prompt
    
    def _build_context_injection(self, context: Dict, context_type: str) -> str:
        """Build context injection string"""
        if context_type == 'summary':
            return self._build_summary_injection(context)
        else:
            return self._build_full_context_injection(context)
    
    def _build_summary_injection(self, context: Dict) -> str:
        """Build summary context injection"""
        parts = []
        
        # Basic conversation info
        parts.append(f"Conversation Status: {context.get('completion_status', 'unknown')}")
        parts.append(f"Engagement Level: {context.get('engagement_level', 'unknown')}")
        
        # Topics covered
        topics = context.get('key_topics_covered', [])
        if topics:
            parts.append(f"Topics Covered: {', '.join(topics)}")
        
        # Relationship context
        rel_context = context.get('relationship_context', {})
        if rel_context.get('has_history'):
            parts.append(f"Previous Meetings: {rel_context.get('previous_meetings', 0)}")
            
            historical_insights = rel_context.get('key_historical_insights', [])
            if historical_insights:
                parts.append("Recent History:")
                for insight in historical_insights[:2]:
                    parts.append(f"  - {insight}")
        
        return '\n'.join(parts)
    
    def _build_full_context_injection(self, context: Dict) -> str:
        """Build full context injection"""
        parts = []
        
        # Current session info
        parts.append(f"Session Duration: {context.get('session_duration', 'Unknown')}")
        parts.append(f"Questions Asked: {context.get('total_questions', 0)}")
        parts.append(f"Responses Given: {context.get('total_responses', 0)}")
        
        # Conversation patterns
        patterns = context.get('conversation_patterns', {})
        if patterns:
            parts.append(f"Engagement Level: {patterns.get('engagement_level', 'unknown')}")
            parts.append(f"Average Response Length: {patterns.get('avg_response_length', 0):.1f} words")
        
        # Recent conversation flow (last 3 interactions)
        timeline = context.get('conversation_timeline', [])
        if timeline:
            parts.append("\nRecent Conversation Flow:")
            for entry in timeline[-3:]:
                parts.append(f"Q: {entry.get('question', '')[:100]}...")
                if entry.get('response'):
                    parts.append(f"A: {entry.get('response', '')[:100]}...")
        
        return '\n'.join(parts)