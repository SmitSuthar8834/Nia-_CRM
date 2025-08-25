"""
Advanced Prompt Engineering for Meeting Intelligence
Handles context injection, conversation flow, and meeting-specific strategies
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.models import User

from apps.meetings.models import Meeting, MeetingParticipant
from apps.leads.models import Lead
from apps.debriefings.models import DebriefingSession
from .models import AIPromptTemplate, AIInteraction
# Removed circular import - PromptTemplateService will be imported locally when needed

logger = logging.getLogger(__name__)


class ContextInjectionService:
    """Service for injecting contextual information into prompts"""
    
    def __init__(self):
        # Import locally to avoid circular import
        from .services import PromptTemplateService
        self.template_service = PromptTemplateService()
    
    def build_meeting_context(self, meeting_id: str) -> Dict[str, Any]:
        """Build comprehensive meeting context for prompt injection"""
        try:
            from apps.meetings.models import Meeting
            meeting = Meeting.objects.select_related().prefetch_related(
                'meetingparticipant_set__matched_lead'
            ).get(id=meeting_id)
            
            # Basic meeting information
            context = {
                'meeting_id': str(meeting.id),
                'meeting_type': meeting.meeting_type,
                'title': meeting.title,
                'start_time': meeting.start_time.isoformat(),
                'end_time': meeting.end_time.isoformat(),
                'duration': self._calculate_duration(meeting.start_time, meeting.end_time),
                'organizer': meeting.organizer.get_full_name() or meeting.organizer.username,
            }
            
            # Participant information
            participants = []
            external_participants = []
            matched_leads = []
            
            for participant in meeting.meetingparticipant_set.all():
                participant_info = {
                    'email': participant.email,
                    'name': participant.name or 'Unknown',
                    'company': participant.company or 'Unknown',
                    'is_external': participant.is_external,
                    'match_confidence': participant.match_confidence
                }
                
                participants.append(participant_info)
                
                if participant.is_external:
                    external_participants.append(participant_info)
                
                if participant.matched_lead:
                    matched_leads.append({
                        'id': str(participant.matched_lead.id),
                        'name': f"{participant.matched_lead.first_name} {participant.matched_lead.last_name}",
                        'company': participant.matched_lead.company,
                        'title': participant.matched_lead.title,
                        'status': participant.matched_lead.status,
                        'qualification_score': participant.matched_lead.qualification_score
                    })
            
            context.update({
                'participants': participants,
                'external_participants': external_participants,
                'matched_leads': matched_leads,
                'participant_count': len(participants),
                'external_count': len(external_participants)
            })
            
            # Historical context
            context.update(self._build_historical_context(meeting, matched_leads))
            
            # Relationship context
            context.update(self._build_relationship_context(matched_leads))
            
            return context
            
        except Exception as e:
            logger.error(f"Error building meeting context: {str(e)}")
            return {
                'meeting_id': meeting_id,
                'error': f"Could not load meeting context: {str(e)}"
            }
    
    def _calculate_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Calculate meeting duration in human-readable format"""
        duration = end_time - start_time
        total_minutes = int(duration.total_seconds() / 60)
        
        if total_minutes < 60:
            return f"{total_minutes} minutes"
        else:
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minutes"
    
    def _build_historical_context(self, meeting: 'Meeting', matched_leads: List[Dict]) -> Dict[str, Any]:
        """Build historical context from previous meetings"""
        try:
            # Get previous meetings with same participants
            lead_ids = [lead['id'] for lead in matched_leads]
            if not lead_ids:
                return {'previous_meetings': 0, 'relationship_stage': 'new'}
            
            from apps.meetings.models import Meeting as MeetingModel
            previous_meetings = MeetingModel.objects.filter(
                meetingparticipant__matched_lead__id__in=lead_ids,
                start_time__lt=meeting.start_time,
                is_sales_meeting=True
            ).distinct().order_by('-start_time')[:5]
            
            previous_count = previous_meetings.count()
            
            # Determine relationship stage based on meeting history
            if previous_count == 0:
                relationship_stage = 'new'
            elif previous_count <= 2:
                relationship_stage = 'early'
            elif previous_count <= 5:
                relationship_stage = 'developing'
            else:
                relationship_stage = 'established'
            
            # Get recent meeting outcomes
            recent_outcomes = []
            for prev_meeting in previous_meetings[:3]:
                try:
                    debriefing = prev_meeting.debriefingsession
                    if debriefing.completed_at and debriefing.extracted_data:
                        outcome = debriefing.extracted_data.get('meeting_outcome', '')
                        if outcome:
                            recent_outcomes.append({
                                'date': prev_meeting.start_time.strftime('%Y-%m-%d'),
                                'outcome': outcome[:200]  # Truncate for context
                            })
                except:
                    continue
            
            return {
                'previous_meetings': previous_count,
                'relationship_stage': relationship_stage,
                'recent_outcomes': recent_outcomes,
                'last_meeting_date': previous_meetings.first().start_time.strftime('%Y-%m-%d') if previous_meetings.exists() else None
            }
            
        except Exception as e:
            logger.warning(f"Error building historical context: {str(e)}")
            return {'previous_meetings': 0, 'relationship_stage': 'unknown'}
    
    def _build_relationship_context(self, matched_leads: List[Dict]) -> Dict[str, Any]:
        """Build relationship context from lead data"""
        if not matched_leads:
            return {'deal_stage': 'unknown', 'qualification_level': 'unqualified'}
        
        # Aggregate qualification scores
        total_score = sum(lead.get('qualification_score', 0) for lead in matched_leads)
        avg_score = total_score / len(matched_leads) if matched_leads else 0
        
        # Determine qualification level
        if avg_score >= 80:
            qualification_level = 'highly_qualified'
        elif avg_score >= 60:
            qualification_level = 'qualified'
        elif avg_score >= 40:
            qualification_level = 'partially_qualified'
        else:
            qualification_level = 'unqualified'
        
        # Determine deal stage based on lead status
        statuses = [lead.get('status', 'new') for lead in matched_leads]
        if 'negotiation' in statuses:
            deal_stage = 'negotiation'
        elif 'proposal' in statuses:
            deal_stage = 'proposal'
        elif 'qualified' in statuses:
            deal_stage = 'qualified'
        elif 'contacted' in statuses:
            deal_stage = 'contacted'
        else:
            deal_stage = 'new'
        
        return {
            'deal_stage': deal_stage,
            'qualification_level': qualification_level,
            'average_qualification_score': avg_score,
            'lead_count': len(matched_leads)
        }


class ConversationFlowManager:
    """Manages conversation flow and dynamic follow-ups"""
    
    def __init__(self):
        self.context_service = ContextInjectionService()
    
    def generate_opening_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate opening questions based on meeting context"""
        meeting_type = meeting_context.get('meeting_type', 'general')
        relationship_stage = meeting_context.get('relationship_stage', 'new')
        
        # Select appropriate question strategy
        if meeting_type == 'discovery':
            return self._generate_discovery_questions(meeting_context, question_count)
        elif meeting_type == 'demo':
            return self._generate_demo_questions(meeting_context, question_count)
        elif meeting_type == 'negotiation':
            return self._generate_negotiation_questions(meeting_context, question_count)
        elif meeting_type == 'follow_up':
            return self._generate_followup_questions(meeting_context, question_count)
        else:
            return self._generate_general_questions(meeting_context, question_count)
    
    def _generate_discovery_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> List[Dict[str, Any]]:
        """Generate discovery-specific questions"""
        relationship_stage = meeting_context.get('relationship_stage', 'new')
        previous_meetings = meeting_context.get('previous_meetings', 0)
        
        questions = []
        
        if relationship_stage == 'new':
            questions.extend([
                {
                    'category': 'introduction',
                    'priority': 'high',
                    'question': 'How did the introductions go? What did you learn about the key stakeholders?',
                    'follow_up_triggers': ['stakeholder', 'decision maker', 'team']
                },
                {
                    'category': 'pain_points',
                    'priority': 'high',
                    'question': 'What specific challenges or pain points did they mention?',
                    'follow_up_triggers': ['challenge', 'problem', 'issue', 'difficulty']
                },
                {
                    'category': 'current_solution',
                    'priority': 'medium',
                    'question': 'What solutions are they currently using to address these challenges?',
                    'follow_up_triggers': ['competitor', 'vendor', 'tool', 'system']
                }
            ])
        else:
            questions.extend([
                {
                    'category': 'progress',
                    'priority': 'high',
                    'question': 'What progress has been made since our last meeting?',
                    'follow_up_triggers': ['progress', 'update', 'change']
                },
                {
                    'category': 'requirements',
                    'priority': 'high',
                    'question': 'Did any new requirements or considerations come up?',
                    'follow_up_triggers': ['requirement', 'need', 'must have']
                }
            ])
        
        # Add budget and timeline questions
        questions.extend([
            {
                'category': 'budget',
                'priority': 'high',
                'question': 'Was budget discussed? What did you learn about their financial parameters?',
                'follow_up_triggers': ['budget', 'cost', 'price', 'investment']
            },
            {
                'category': 'timeline',
                'priority': 'high',
                'question': 'What timeline or urgency did they express for implementing a solution?',
                'follow_up_triggers': ['timeline', 'deadline', 'urgent', 'when']
            }
        ])
        
        return questions[:question_count]
    
    def _generate_demo_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> List[Dict[str, Any]]:
        """Generate demo-specific questions"""
        return [
            {
                'category': 'feature_interest',
                'priority': 'high',
                'question': 'Which features or capabilities seemed to resonate most with the audience?',
                'follow_up_triggers': ['feature', 'capability', 'functionality']
            },
            {
                'category': 'technical_concerns',
                'priority': 'high',
                'question': 'Were there any technical questions or concerns raised during the demo?',
                'follow_up_triggers': ['technical', 'integration', 'security', 'performance']
            },
            {
                'category': 'user_feedback',
                'priority': 'medium',
                'question': 'How did the end users react to the interface and workflow?',
                'follow_up_triggers': ['user', 'interface', 'workflow', 'usability']
            },
            {
                'category': 'implementation',
                'priority': 'medium',
                'question': 'What questions came up about implementation and rollout?',
                'follow_up_triggers': ['implementation', 'rollout', 'deployment', 'training']
            },
            {
                'category': 'next_steps',
                'priority': 'high',
                'question': 'What next steps were agreed upon at the end of the demo?',
                'follow_up_triggers': ['next step', 'follow up', 'action item']
            }
        ][:question_count]
    
    def _generate_negotiation_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> List[Dict[str, Any]]:
        """Generate negotiation-specific questions"""
        return [
            {
                'category': 'pricing_discussion',
                'priority': 'high',
                'question': 'How did the pricing discussion go? What were their main concerns?',
                'follow_up_triggers': ['price', 'cost', 'budget', 'expensive']
            },
            {
                'category': 'terms_conditions',
                'priority': 'high',
                'question': 'Which contract terms or conditions were discussed or negotiated?',
                'follow_up_triggers': ['contract', 'terms', 'conditions', 'agreement']
            },
            {
                'category': 'decision_process',
                'priority': 'high',
                'question': 'What did you learn about their decision-making process and timeline?',
                'follow_up_triggers': ['decision', 'approval', 'timeline', 'process']
            },
            {
                'category': 'objections',
                'priority': 'medium',
                'question': 'What objections or concerns were raised, and how were they addressed?',
                'follow_up_triggers': ['objection', 'concern', 'worry', 'hesitation']
            },
            {
                'category': 'competitive_pressure',
                'priority': 'medium',
                'question': 'Was there any mention of competitive alternatives or pressure?',
                'follow_up_triggers': ['competitor', 'alternative', 'comparison']
            }
        ][:question_count]
    
    def _generate_followup_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> List[Dict[str, Any]]:
        """Generate follow-up meeting questions"""
        recent_outcomes = meeting_context.get('recent_outcomes', [])
        
        questions = [
            {
                'category': 'action_items',
                'priority': 'high',
                'question': 'Were the action items from the previous meeting completed? What was the outcome?',
                'follow_up_triggers': ['action item', 'task', 'deliverable', 'completed']
            },
            {
                'category': 'progress_update',
                'priority': 'high',
                'question': 'What progress has been made on their end since our last meeting?',
                'follow_up_triggers': ['progress', 'update', 'development', 'change']
            }
        ]
        
        if recent_outcomes:
            questions.append({
                'category': 'outcome_follow_up',
                'priority': 'high',
                'question': f'Following up on our last meeting outcome: {recent_outcomes[0]["outcome"][:100]}... - what has changed?',
                'follow_up_triggers': ['change', 'update', 'development']
            })
        
        questions.extend([
            {
                'category': 'new_requirements',
                'priority': 'medium',
                'question': 'Have any new requirements or stakeholders emerged?',
                'follow_up_triggers': ['new', 'requirement', 'stakeholder', 'change']
            },
            {
                'category': 'timeline_update',
                'priority': 'medium',
                'question': 'Has their timeline or urgency changed since we last spoke?',
                'follow_up_triggers': ['timeline', 'urgency', 'deadline', 'schedule']
            }
        ])
        
        return questions[:question_count]
    
    def _generate_general_questions(
        self,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> List[Dict[str, Any]]:
        """Generate general meeting questions"""
        return [
            {
                'category': 'meeting_outcome',
                'priority': 'high',
                'question': 'How would you summarize the overall outcome of this meeting?',
                'follow_up_triggers': ['outcome', 'result', 'summary']
            },
            {
                'category': 'key_insights',
                'priority': 'high',
                'question': 'What were the key insights or takeaways from the conversation?',
                'follow_up_triggers': ['insight', 'takeaway', 'learning']
            },
            {
                'category': 'participant_engagement',
                'priority': 'medium',
                'question': 'How engaged were the participants? Who seemed most interested?',
                'follow_up_triggers': ['engaged', 'interested', 'enthusiastic']
            },
            {
                'category': 'concerns_raised',
                'priority': 'medium',
                'question': 'Were there any concerns or objections raised during the meeting?',
                'follow_up_triggers': ['concern', 'objection', 'worry', 'issue']
            },
            {
                'category': 'next_steps',
                'priority': 'high',
                'question': 'What are the agreed-upon next steps and who is responsible for each?',
                'follow_up_triggers': ['next step', 'action', 'follow up', 'responsible']
            }
        ][:question_count]
    
    def generate_follow_up_question(
        self,
        original_question: Dict[str, Any],
        user_response: str,
        meeting_context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate intelligent follow-up question based on response"""
        try:
            # Analyze response for trigger words
            response_lower = user_response.lower()
            triggers = original_question.get('follow_up_triggers', [])
            
            triggered_topics = [trigger for trigger in triggers if trigger in response_lower]
            
            # Generate follow-up based on category and triggers
            category = original_question.get('category', 'general')
            
            if category == 'pain_points' and triggered_topics:
                return {
                    'category': 'pain_points_detail',
                    'question': f'You mentioned {triggered_topics[0]}. Can you elaborate on the specific impact this has on their business?',
                    'reasoning': f'Following up on {triggered_topics[0]} to understand business impact'
                }
            
            elif category == 'budget' and any(word in response_lower for word in ['budget', 'cost', 'price']):
                return {
                    'category': 'budget_detail',
                    'question': 'Did they give you a specific budget range or mention how they typically approach investment decisions?',
                    'reasoning': 'Drilling down on budget specifics'
                }
            
            elif category == 'technical_concerns' and triggered_topics:
                return {
                    'category': 'technical_detail',
                    'question': f'Regarding the {triggered_topics[0]} concerns - did they mention their current technical environment or constraints?',
                    'reasoning': f'Getting technical context for {triggered_topics[0]}'
                }
            
            elif len(user_response.split()) < 10:  # Short response
                return {
                    'category': f'{category}_expansion',
                    'question': 'Can you provide more details about that? What specific aspects stood out to you?',
                    'reasoning': 'Encouraging more detailed response'
                }
            
            elif 'competitor' in response_lower or 'alternative' in response_lower:
                return {
                    'category': 'competitive_intelligence',
                    'question': 'What did you learn about their current solution or other alternatives they\'re considering?',
                    'reasoning': 'Gathering competitive intelligence'
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error generating follow-up question: {str(e)}")
            return None


class MeetingTypeStrategy:
    """Strategy pattern for meeting-type-specific prompt engineering"""
    
    def __init__(self):
        self.context_service = ContextInjectionService()
        self.flow_manager = ConversationFlowManager()
    
    def get_strategy(self, meeting_type: str) -> 'BaseMeetingStrategy':
        """Get appropriate strategy for meeting type"""
        strategies = {
            'discovery': DiscoveryMeetingStrategy(),
            'demo': DemoMeetingStrategy(),
            'negotiation': NegotiationMeetingStrategy(),
            'follow_up': FollowUpMeetingStrategy(),
            'closing': ClosingMeetingStrategy()
        }
        
        return strategies.get(meeting_type, GeneralMeetingStrategy())


class BaseMeetingStrategy:
    """Base strategy for meeting-specific prompt engineering"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get system prompt for this meeting type"""
        raise NotImplementedError
    
    def get_question_priorities(self) -> List[str]:
        """Get question categories in priority order"""
        raise NotImplementedError
    
    def get_extraction_focus(self) -> List[str]:
        """Get data extraction focus areas"""
        raise NotImplementedError


class DiscoveryMeetingStrategy(BaseMeetingStrategy):
    """Strategy for discovery meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        relationship_stage = context.get('relationship_stage', 'new')
        
        if relationship_stage == 'new':
            return """You are an expert sales coach specializing in discovery meetings. Your role is to help sales representatives extract maximum value from initial customer conversations.

Focus on understanding:
- Customer pain points and business challenges
- Current solutions and their limitations
- Budget parameters and decision-making process
- Timeline and urgency factors
- Key stakeholders and their roles

Ask questions that encourage detailed responses and uncover both explicit and implicit needs. Be curious about the business impact of their challenges."""
        else:
            return """You are an expert sales coach helping with follow-up discovery. The relationship is already established, so focus on:

- Progress since the last interaction
- Evolving requirements and new challenges
- Changes in timeline or priorities
- New stakeholders or decision criteria
- Competitive developments

Build on previous conversations while exploring new developments and deeper insights."""
    
    def get_question_priorities(self) -> List[str]:
        return ['pain_points', 'stakeholders', 'budget', 'timeline', 'current_solution', 'decision_process']
    
    def get_extraction_focus(self) -> List[str]:
        return ['contacts', 'pain_points', 'budget_info', 'timeline', 'decision_makers', 'current_solutions']


class DemoMeetingStrategy(BaseMeetingStrategy):
    """Strategy for demo meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        return """You are an expert sales engineer coach specializing in product demonstrations. Your role is to help sales representatives capture valuable feedback and technical insights from product demos.

Focus on understanding:
- Feature interest and user reactions
- Technical requirements and constraints
- Integration considerations
- User adoption factors
- Implementation timeline and process

Ask questions that reveal both positive reactions and concerns, helping to identify the path forward and potential obstacles."""
    
    def get_question_priorities(self) -> List[str]:
        return ['feature_interest', 'technical_concerns', 'user_feedback', 'implementation', 'integration']
    
    def get_extraction_focus(self) -> List[str]:
        return ['feature_feedback', 'technical_requirements', 'implementation_timeline', 'user_concerns', 'integration_needs']


class NegotiationMeetingStrategy(BaseMeetingStrategy):
    """Strategy for negotiation meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        return """You are an expert sales negotiation coach. Your role is to help sales representatives capture critical information from pricing and contract discussions.

Focus on understanding:
- Pricing concerns and budget constraints
- Contract terms and conditions discussed
- Decision-making process and approval requirements
- Competitive pressure and alternatives
- Timeline for decision-making

Ask questions that reveal the customer's true position, constraints, and decision criteria."""
    
    def get_question_priorities(self) -> List[str]:
        return ['pricing_discussion', 'decision_process', 'terms_conditions', 'competitive_pressure', 'objections']
    
    def get_extraction_focus(self) -> List[str]:
        return ['pricing_feedback', 'contract_terms', 'decision_timeline', 'competitive_mentions', 'objections']


class FollowUpMeetingStrategy(BaseMeetingStrategy):
    """Strategy for follow-up meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        recent_outcomes = context.get('recent_outcomes', [])
        context_info = ""
        
        if recent_outcomes:
            context_info = f"\n\nPrevious meeting context: {recent_outcomes[0]['outcome']}"
        
        return f"""You are an expert sales coach specializing in follow-up meetings. Your role is to help sales representatives track progress and maintain momentum in ongoing opportunities.

Focus on understanding:
- Progress on previous action items and commitments
- Changes in requirements or priorities
- New stakeholders or decision criteria
- Timeline updates and urgency changes
- Competitive developments{context_info}

Ask questions that maintain continuity with previous conversations while exploring new developments."""
    
    def get_question_priorities(self) -> List[str]:
        return ['action_items', 'progress_update', 'timeline_update', 'new_requirements', 'stakeholder_changes']
    
    def get_extraction_focus(self) -> List[str]:
        return ['progress_updates', 'new_requirements', 'timeline_changes', 'action_items', 'stakeholder_updates']


class ClosingMeetingStrategy(BaseMeetingStrategy):
    """Strategy for closing meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        return """You are an expert sales closing coach. Your role is to help sales representatives capture critical information from final decision meetings.

Focus on understanding:
- Final objections and how they were addressed
- Decision outcome and reasoning
- Implementation timeline and next steps
- Contract details and approval process
- Success criteria and expectations

Ask questions that capture both the outcome and the path forward, whether positive or negative."""
    
    def get_question_priorities(self) -> List[str]:
        return ['decision_outcome', 'final_objections', 'implementation_plan', 'contract_details', 'success_criteria']
    
    def get_extraction_focus(self) -> List[str]:
        return ['decision_outcome', 'contract_details', 'implementation_timeline', 'success_criteria', 'final_objections']


class GeneralMeetingStrategy(BaseMeetingStrategy):
    """Default strategy for general meetings"""
    
    def get_system_prompt(self, context: Dict[str, Any]) -> str:
        return """You are an expert sales coach helping to debrief a business meeting. Your role is to help sales representatives extract valuable insights and actionable information.

Focus on understanding:
- Meeting outcome and key takeaways
- Participant engagement and reactions
- Action items and next steps
- Concerns or objections raised
- Opportunities for follow-up

Ask questions that encourage comprehensive responses and help identify both opportunities and potential challenges."""
    
    def get_question_priorities(self) -> List[str]:
        return ['meeting_outcome', 'key_insights', 'participant_engagement', 'concerns_raised', 'next_steps']
    
    def get_extraction_focus(self) -> List[str]:
        return ['meeting_outcome', 'key_insights', 'action_items', 'concerns', 'next_steps']