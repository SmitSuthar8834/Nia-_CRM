"""
Conversation flow management for AI-powered debriefing sessions
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from channels.db import database_sync_to_async

from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight, DebriefingTemplate
from .ai_integration import DebriefingAIService
from apps.meetings.models import Meeting, MeetingParticipant

logger = logging.getLogger(__name__)


class ConversationFlowManager:
    """
    Manages the flow of debriefing conversations with AI-powered question generation
    """
    
    def __init__(self, session: DebriefingSession):
        self.session = session
        self.ai_service = DebriefingAIService()
        self.meeting = session.meeting
        self.context_data = {}
        self._load_context()
    
    def _load_context(self):
        """Load meeting context for conversation flow"""
        self.context_data = {
            'meeting_id': str(self.meeting.id),
            'meeting_title': self.meeting.title,
            'meeting_type': self.meeting.meeting_type,
            'start_time': self.meeting.start_time.isoformat(),
            'end_time': self.meeting.end_time.isoformat(),
            'duration_minutes': self.meeting.duration_minutes,
            'participants': self._get_participant_context(),
            'previous_meetings': self._get_previous_meetings_context(),
            'lead_context': self._get_lead_context(),
            'conversation_history': self.session.conversation_data.get('history', [])
        }
    
    def _get_participant_context(self) -> List[Dict[str, Any]]:
        """Get context about meeting participants"""
        participants = []
        for participant in self.meeting.participants.all():
            participants.append({
                'email': participant.email,
                'name': participant.name,
                'company': participant.company,
                'is_external': participant.is_external,
                'matched_lead': str(participant.matched_lead.id) if participant.matched_lead else None,
                'match_confidence': participant.match_confidence
            })
        return participants
    
    def _get_previous_meetings_context(self) -> List[Dict[str, Any]]:
        """Get context from previous meetings with same participants"""
        # Find previous meetings with overlapping participants
        participant_emails = set(
            self.meeting.participants.values_list('email', flat=True)
        )
        
        previous_meetings = Meeting.objects.filter(
            organizer=self.meeting.organizer,
            start_time__lt=self.meeting.start_time,
            is_sales_meeting=True,
            participants__email__in=participant_emails
        ).distinct().order_by('-start_time')[:3]  # Last 3 meetings
        
        context = []
        for meeting in previous_meetings:
            if hasattr(meeting, 'debriefing') and meeting.debriefing.status == 'completed':
                context.append({
                    'meeting_id': str(meeting.id),
                    'title': meeting.title,
                    'date': meeting.start_time.isoformat(),
                    'type': meeting.meeting_type,
                    'key_outcomes': meeting.debriefing.extracted_data.get('key_outcomes', []),
                    'action_items': meeting.debriefing.extracted_data.get('action_items', []),
                    'next_steps': meeting.debriefing.extracted_data.get('next_steps', [])
                })
        
        return context
    
    def _get_lead_context(self) -> Dict[str, Any]:
        """Get context about leads involved in the meeting"""
        leads = []
        for participant in self.meeting.participants.filter(matched_lead__isnull=False):
            lead = participant.matched_lead
            leads.append({
                'lead_id': str(lead.id),
                'name': f"{lead.first_name} {lead.last_name}",
                'company': lead.company,
                'title': lead.title,
                'status': lead.status,
                'qualification_score': lead.qualification_score,
                'relationship_stage': lead.relationship_stage,
                'last_meeting_date': lead.last_meeting_date.isoformat() if lead.last_meeting_date else None,
                'meeting_count': lead.meeting_count
            })
        
        return {'leads': leads}
    
    async def initialize_conversation(self) -> DebriefingQuestion:
        """Initialize conversation flow and generate first question"""
        try:
            # Get appropriate template
            template = await self._get_conversation_template()
            
            # Generate initial questions based on meeting context
            questions = await self._generate_initial_questions(template)
            
            # Save questions to database
            await self._save_questions(questions)
            
            # Update session with total questions
            await self._update_session_totals(len(questions))
            
            # Return first question
            return questions[0] if questions else None
            
        except Exception as e:
            logger.error(f"Error initializing conversation: {str(e)}")
            raise
    
    @database_sync_to_async
    def _get_conversation_template(self) -> Optional[DebriefingTemplate]:
        """Get appropriate conversation template based on meeting type"""
        return DebriefingTemplate.objects.filter(
            template_type=self.meeting.meeting_type,
            is_active=True
        ).first() or DebriefingTemplate.objects.filter(
            template_type='general',
            is_active=True
        ).first()
    
    async def _generate_initial_questions(self, template: Optional[DebriefingTemplate]) -> List[Dict[str, Any]]:
        """Generate initial set of questions for the conversation"""
        try:
            # Prepare context for AI
            ai_context = {
                'meeting_context': self.context_data,
                'template': template.question_templates if template else None,
                'conversation_type': 'initial_questions'
            }
            
            # Generate questions using AI service
            response = await self.ai_service.generate_debriefing_questions(
                meeting_context=self.context_data,
                template_context=template.question_templates if template else None,
                question_count=8  # Generate 8 initial questions
            )
            
            if response.error:
                logger.error(f"AI error generating questions: {response.error}")
                return self._get_fallback_questions()
            
            return response.parsed_data.get('questions', [])
            
        except Exception as e:
            logger.error(f"Error generating initial questions: {str(e)}")
            return self._get_fallback_questions()
    
    def _get_fallback_questions(self) -> List[Dict[str, Any]]:
        """Get fallback questions if AI generation fails"""
        return [
            {
                'question_text': "How would you describe the overall outcome of this meeting?",
                'question_type': 'outcome',
                'question_order': 1,
                'ai_context': {'fallback': True}
            },
            {
                'question_text': "What were the key topics discussed during the meeting?",
                'question_type': 'topics',
                'question_order': 2,
                'ai_context': {'fallback': True}
            },
            {
                'question_text': "Were there any specific next steps or action items agreed upon?",
                'question_type': 'follow_up',
                'question_order': 3,
                'ai_context': {'fallback': True}
            },
            {
                'question_text': "Did any concerns or objections come up during the discussion?",
                'question_type': 'objections',
                'question_order': 4,
                'ai_context': {'fallback': True}
            }
        ]
    
    @database_sync_to_async
    def _save_questions(self, questions: List[Dict[str, Any]]):
        """Save generated questions to database"""
        with transaction.atomic():
            for question_data in questions:
                DebriefingQuestion.objects.create(
                    session=self.session,
                    question_text=question_data['question_text'],
                    question_type=question_data.get('question_type', 'general'),
                    question_order=question_data['question_order'],
                    ai_context=question_data.get('ai_context', {}),
                    ai_prompt=question_data.get('ai_prompt', '')
                )
    
    @database_sync_to_async
    def _update_session_totals(self, total_questions: int):
        """Update session with total question count"""
        self.session.total_questions = total_questions
        self.session.save()
    
    async def process_response(self, question: DebriefingQuestion, response_text: str) -> Dict[str, Any]:
        """Process user response and extract structured data"""
        try:
            # Extract entities and insights from response
            extraction_result = await self.ai_service.extract_response_data(
                question_text=question.question_text,
                response_text=response_text,
                question_type=question.question_type,
                meeting_context=self.context_data
            )
            
            if extraction_result.error:
                logger.error(f"AI error processing response: {extraction_result.error}")
                return {'error': extraction_result.error}
            
            # Save extracted entities to question
            await self._save_extracted_entities(question, extraction_result.parsed_data)
            
            # Generate insights if applicable
            insights = await self._generate_response_insights(
                question, response_text, extraction_result.parsed_data
            )
            
            # Update conversation history
            await self._update_conversation_history(question, response_text, extraction_result.parsed_data)
            
            return {
                'extracted_data': extraction_result.parsed_data,
                'insights': insights,
                'confidence_score': extraction_result.confidence_score
            }
            
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            return {'error': str(e)}
    
    @database_sync_to_async
    def _save_extracted_entities(self, question: DebriefingQuestion, extracted_data: Dict[str, Any]):
        """Save extracted entities to question"""
        question.extracted_entities = extracted_data
        question.processed = True
        question.save()
    
    async def _generate_response_insights(
        self, 
        question: DebriefingQuestion, 
        response_text: str, 
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate insights from response data"""
        try:
            insights_result = await self.ai_service.generate_response_insights(
                question_type=question.question_type,
                response_text=response_text,
                extracted_data=extracted_data,
                meeting_context=self.context_data
            )
            
            if insights_result.error:
                logger.error(f"AI error generating insights: {insights_result.error}")
                return []
            
            # Save insights to database
            insights = insights_result.parsed_data.get('insights', [])
            await self._save_insights(insights, question)
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return []
    
    @database_sync_to_async
    def _save_insights(self, insights: List[Dict[str, Any]], source_question: DebriefingQuestion):
        """Save insights to database"""
        with transaction.atomic():
            for insight_data in insights:
                DebriefingInsight.objects.create(
                    session=self.session,
                    source_question=source_question,
                    insight_type=insight_data.get('type', 'general'),
                    title=insight_data.get('title', ''),
                    description=insight_data.get('description', ''),
                    confidence_level=insight_data.get('confidence_level', 'medium'),
                    confidence_score=insight_data.get('confidence_score', 0.5),
                    source_text=insight_data.get('source_text', ''),
                    suggested_actions=insight_data.get('suggested_actions', []),
                    priority=insight_data.get('priority', 'medium')
                )
    
    @database_sync_to_async
    def _update_conversation_history(
        self, 
        question: DebriefingQuestion, 
        response_text: str, 
        extracted_data: Dict[str, Any]
    ):
        """Update conversation history in session"""
        if 'history' not in self.session.conversation_data:
            self.session.conversation_data['history'] = []
        
        self.session.conversation_data['history'].append({
            'question_id': str(question.id),
            'question_text': question.question_text,
            'question_type': question.question_type,
            'response_text': response_text,
            'extracted_data': extracted_data,
            'timestamp': timezone.now().isoformat()
        })
        
        self.session.save()
    
    async def generate_follow_up_questions(
        self, 
        question: DebriefingQuestion, 
        response_text: str, 
        processing_result: Dict[str, Any]
    ) -> List[DebriefingQuestion]:
        """Generate follow-up questions based on response"""
        try:
            # Determine if follow-up questions are needed
            if not self._needs_follow_up(question, response_text, processing_result):
                return []
            
            # Generate follow-up questions using AI
            follow_up_result = await self.ai_service.generate_follow_up_questions(
                original_question=question.question_text,
                response_text=response_text,
                extracted_data=processing_result.get('extracted_data', {}),
                meeting_context=self.context_data
            )
            
            if follow_up_result.error:
                logger.error(f"AI error generating follow-up questions: {follow_up_result.error}")
                return []
            
            # Create follow-up question objects
            follow_up_questions = []
            for i, question_data in enumerate(follow_up_result.parsed_data.get('questions', [])):
                follow_up_question = await self._create_follow_up_question(
                    question, question_data, i + 1
                )
                follow_up_questions.append(follow_up_question)
            
            return follow_up_questions
            
        except Exception as e:
            logger.error(f"Error generating follow-up questions: {str(e)}")
            return []
    
    def _needs_follow_up(
        self, 
        question: DebriefingQuestion, 
        response_text: str, 
        processing_result: Dict[str, Any]
    ) -> bool:
        """Determine if follow-up questions are needed"""
        # Check confidence score
        confidence = processing_result.get('confidence_score', 1.0)
        if confidence < 0.7:
            return True
        
        # Check for incomplete information based on question type
        extracted_data = processing_result.get('extracted_data', {})
        
        if question.question_type == 'competitive' and not extracted_data.get('competitors'):
            return True
        
        if question.question_type == 'budget' and not extracted_data.get('budget_info'):
            return True
        
        if question.question_type == 'timeline' and not extracted_data.get('timeline'):
            return True
        
        # Check response length (very short responses might need clarification)
        if len(response_text.strip()) < 20:
            return True
        
        return False
    
    @database_sync_to_async
    def _create_follow_up_question(
        self, 
        parent_question: DebriefingQuestion, 
        question_data: Dict[str, Any], 
        follow_up_index: int
    ) -> DebriefingQuestion:
        """Create a follow-up question in the database"""
        from django.db import models
        
        # Get next order number
        max_order = DebriefingQuestion.objects.filter(session=self.session).aggregate(
            max_order=models.Max('question_order')
        )['max_order'] or 0
        
        return DebriefingQuestion.objects.create(
            session=self.session,
            question_text=question_data['question_text'],
            question_type=question_data.get('question_type', parent_question.question_type),
            question_order=max_order + follow_up_index,
            is_follow_up=True,
            parent_question=parent_question,
            ai_context=question_data.get('ai_context', {}),
            ai_prompt=question_data.get('ai_prompt', '')
        )
    
    async def get_next_question(self, follow_up_questions: List[DebriefingQuestion] = None) -> Optional[DebriefingQuestion]:
        """Get the next question in the conversation flow"""
        try:
            # If we have follow-up questions, return the first one
            if follow_up_questions:
                return follow_up_questions[0]
            
            # Otherwise, get the next unanswered question
            next_question = await self._get_next_unanswered_question()
            
            return next_question
            
        except Exception as e:
            logger.error(f"Error getting next question: {str(e)}")
            return None
    
    @database_sync_to_async
    def _get_next_unanswered_question(self) -> Optional[DebriefingQuestion]:
        """Get the next unanswered question from the database"""
        return DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=True
        ).order_by('question_order').first()
    
    async def generate_clarification(self, question: DebriefingQuestion, clarification_type: str) -> str:
        """Generate clarification for a question"""
        try:
            clarification_result = await self.ai_service.generate_question_clarification(
                question_text=question.question_text,
                question_type=question.question_type,
                clarification_type=clarification_type,
                meeting_context=self.context_data
            )
            
            if clarification_result.error:
                logger.error(f"AI error generating clarification: {clarification_result.error}")
                return "I apologize, but I'm having trouble generating a clarification right now. Could you please provide any additional details you think might be relevant?"
            
            return clarification_result.parsed_data.get('clarification', 'Could you please provide more details?')
            
        except Exception as e:
            logger.error(f"Error generating clarification: {str(e)}")
            return "Could you please provide more details about your response?"
    
    async def extract_final_data(self) -> Dict[str, Any]:
        """Extract and consolidate final structured data from entire conversation"""
        try:
            # Get all answered questions
            answered_questions = await self._get_answered_questions()
            
            # Prepare conversation data for final extraction
            conversation_data = []
            for question in answered_questions:
                conversation_data.append({
                    'question': question.question_text,
                    'question_type': question.question_type,
                    'response': question.user_response,
                    'extracted_entities': question.extracted_entities
                })
            
            # Use AI to consolidate and extract final structured data
            final_extraction = await self.ai_service.extract_final_conversation_data(
                conversation_data=conversation_data,
                meeting_context=self.context_data
            )
            
            if final_extraction.error:
                logger.error(f"AI error in final extraction: {final_extraction.error}")
                return self._create_fallback_extraction(answered_questions)
            
            # Save final extracted data to session
            extracted_data = final_extraction.parsed_data
            await self._save_final_extracted_data(extracted_data)
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error in final data extraction: {str(e)}")
            return {}
    
    @database_sync_to_async
    def _get_answered_questions(self) -> List[DebriefingQuestion]:
        """Get all answered questions from the session"""
        return list(DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=False
        ).order_by('question_order'))
    
    def _create_fallback_extraction(self, answered_questions: List[DebriefingQuestion]) -> Dict[str, Any]:
        """Create fallback extraction if AI fails"""
        extraction = {
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
            'extraction_method': 'fallback',
            'confidence_score': 0.3
        }
        
        # Extract basic information from responses
        for question in answered_questions:
            if question.question_type == 'outcome':
                extraction['meeting_outcome'] = question.user_response[:200]
            elif question.question_type == 'follow_up':
                extraction['next_steps'].append(question.user_response)
            elif question.question_type == 'objections':
                extraction['concerns_objections'].append(question.user_response)
        
        return extraction
    
    @database_sync_to_async
    def _save_final_extracted_data(self, extracted_data: Dict[str, Any]):
        """Save final extracted data to session"""
        self.session.extracted_data = extracted_data
        self.session.save()
    
    async def generate_insights(self) -> List[Dict[str, Any]]:
        """Generate final insights from the complete conversation"""
        try:
            # Get all insights generated during conversation
            session_insights = await self._get_session_insights()
            
            # Generate additional insights from complete conversation
            final_insights_result = await self.ai_service.generate_final_insights(
                extracted_data=self.session.extracted_data,
                conversation_insights=session_insights,
                meeting_context=self.context_data
            )
            
            if final_insights_result.error:
                logger.error(f"AI error generating final insights: {final_insights_result.error}")
                return session_insights
            
            # Combine and deduplicate insights
            all_insights = session_insights + final_insights_result.parsed_data.get('insights', [])
            
            return self._deduplicate_insights(all_insights)
            
        except Exception as e:
            logger.error(f"Error generating final insights: {str(e)}")
            return []
    
    @database_sync_to_async
    def _get_session_insights(self) -> List[Dict[str, Any]]:
        """Get all insights generated during the session"""
        insights = []
        for insight in DebriefingInsight.objects.filter(session=self.session):
            insights.append({
                'type': insight.insight_type,
                'title': insight.title,
                'description': insight.description,
                'confidence_level': insight.confidence_level,
                'confidence_score': insight.confidence_score,
                'suggested_actions': insight.suggested_actions,
                'priority': insight.priority
            })
        return insights
    
    def _deduplicate_insights(self, insights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate insights based on title and type"""
        seen = set()
        deduplicated = []
        
        for insight in insights:
            key = (insight.get('type', ''), insight.get('title', ''))
            if key not in seen:
                seen.add(key)
                deduplicated.append(insight)
        
        return deduplicated


class ConversationRecoveryManager:
    """
    Manages recovery of interrupted debriefing conversations
    """
    
    def __init__(self, session: DebriefingSession):
        self.session = session
    
    async def can_recover(self) -> bool:
        """Check if session can be recovered"""
        # Session must be in progress and have some answered questions
        if self.session.status != 'in_progress':
            return False
        
        answered_count = await self._get_answered_questions_count()
        return answered_count > 0
    
    @database_sync_to_async
    def _get_answered_questions_count(self) -> int:
        """Get count of answered questions"""
        return DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=False
        ).count()
    
    async def get_recovery_state(self) -> Dict[str, Any]:
        """Get state information for recovery"""
        answered_questions = await self._get_answered_questions()
        next_question = await self._get_next_question()
        
        return {
            'session_id': str(self.session.id),
            'answered_questions_count': len(answered_questions),
            'total_questions': self.session.total_questions,
            'progress_percentage': (len(answered_questions) / self.session.total_questions) * 100,
            'next_question_id': str(next_question.id) if next_question else None,
            'last_activity': self.session.conversation_data.get('last_activity'),
            'can_continue': next_question is not None
        }
    
    @database_sync_to_async
    def _get_answered_questions(self) -> List[DebriefingQuestion]:
        """Get answered questions for recovery"""
        return list(DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=False
        ).order_by('question_order'))
    
    @database_sync_to_async
    def _get_next_question(self) -> Optional[DebriefingQuestion]:
        """Get next unanswered question for recovery"""
        return DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=True
        ).order_by('question_order').first()
    
    async def resume_conversation(self) -> Optional[DebriefingQuestion]:
        """Resume conversation from where it left off"""
        if not await self.can_recover():
            return None
        
        # Update session status if needed
        if self.session.status == 'scheduled':
            await self._update_session_status()
        
        # Get next question
        return await self._get_next_question()
    
    @database_sync_to_async
    def _update_session_status(self):
        """Update session status for recovery"""
        if not self.session.started_at:
            self.session.started_at = timezone.now()
        self.session.status = 'in_progress'
        self.session.save()