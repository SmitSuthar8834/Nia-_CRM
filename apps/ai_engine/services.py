"""
AI Engine Services for Meeting Intelligence
High-level services that use the Gemini client for specific business logic
"""
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User

from .models import AIInteraction, AIPromptTemplate, AIFeedback
from .gemini_client import get_gemini_client, GeminiResponse
from .prompt_engineering import ContextInjectionService, ConversationFlowManager, MeetingTypeStrategy
from .conversation_manager import ConversationHistoryManager, ConversationContextInjector
from .data_extraction import ComprehensiveDataExtractor
from .caching_optimization import get_optimization_service

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Custom exception for AI service errors"""
    pass


class BaseAIService:
    """Base class for AI services with common functionality"""
    
    def __init__(self):
        self.client = get_gemini_client()
    
    def _log_interaction(
        self,
        interaction_type: str,
        user: Optional[User],
        input_data: Dict[str, Any],
        formatted_prompt: str,
        template: Optional[AIPromptTemplate] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> AIInteraction:
        """Log AI interaction for monitoring and improvement"""
        return AIInteraction.objects.create(
            interaction_type=interaction_type,
            prompt_template=template,
            user=user,
            input_data=input_data,
            formatted_prompt=formatted_prompt,
            entity_type=entity_type,
            entity_id=entity_id
        )
    
    def _complete_interaction(
        self,
        interaction: AIInteraction,
        response: GeminiResponse,
        parsed_data: Optional[Dict] = None
    ):
        """Complete interaction logging with response data"""
        if response.error:
            interaction.mark_error(response.error)
        else:
            interaction.mark_success(
                response=response.content,
                parsed_data=parsed_data,
                confidence=response.confidence_score,
                tokens=response.token_count
            )
            
            # Update template usage statistics
            if interaction.prompt_template:
                interaction.prompt_template.increment_usage(
                    response_time=response.response_time_ms / 1000 if response.response_time_ms else None
                )


class PromptTemplateService(BaseAIService):
    """Service for managing and using AI prompt templates"""
    
    def get_template(
        self,
        template_type: str,
        context: str = 'general'
    ) -> Optional[AIPromptTemplate]:
        """Get the best template for given type and context"""
        try:
            return AIPromptTemplate.objects.filter(
                template_type=template_type,
                context=context,
                is_active=True
            ).order_by('-usage_count', '-created_at').first()
        except Exception as e:
            logger.error(f"Error retrieving template: {str(e)}")
            return None
    
    def format_prompt(
        self,
        template: AIPromptTemplate,
        variables: Dict[str, Any]
    ) -> str:
        """Format prompt template with variables"""
        try:
            return template.prompt_template.format(**variables)
        except KeyError as e:
            raise AIServiceError(f"Missing template variable: {str(e)}")
        except Exception as e:
            raise AIServiceError(f"Error formatting prompt: {str(e)}")
    
    def create_template(
        self,
        name: str,
        template_type: str,
        prompt_template: str,
        context: str = 'general',
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        user: Optional[User] = None
    ) -> AIPromptTemplate:
        """Create a new prompt template"""
        if not user:
            raise AIServiceError("User required to create template")
        
        return AIPromptTemplate.objects.create(
            name=name,
            template_type=template_type,
            context=context,
            prompt_template=prompt_template,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            created_by=user
        )


class QuestionGenerationService(BaseAIService):
    """Service for generating intelligent debriefing questions"""
    
    def __init__(self):
        super().__init__()
        self.context_service = ContextInjectionService()
        self.flow_manager = ConversationFlowManager()
        self.strategy_manager = MeetingTypeStrategy()
    
    def generate_questions(
        self,
        meeting_context: Dict[str, Any],
        user: Optional[User] = None,
        question_count: int = 5
    ) -> Dict[str, Any]:
        """
        Generate context-aware debriefing questions
        
        Args:
            meeting_context: Dictionary containing meeting information
            user: User requesting questions
            question_count: Number of questions to generate
            
        Returns:
            Dictionary with questions and metadata
        """
        try:
            # Build comprehensive meeting context
            meeting_id = meeting_context.get('meeting_id')
            if meeting_id:
                enhanced_context = self.context_service.build_meeting_context(meeting_id)
                meeting_context.update(enhanced_context)
            
            # Use conversation flow manager for intelligent question generation
            questions = self.flow_manager.generate_opening_questions(
                meeting_context, question_count
            )
            
            # If we have structured questions, use them directly
            if questions:
                result = {
                    'questions': questions,
                    'meeting_type': meeting_context.get('meeting_type', 'general'),
                    'confidence_score': 0.9,  # High confidence for structured questions
                    'method': 'structured_generation',
                    'context_enhanced': meeting_id is not None
                }
                return result
            
            # Fallback to template-based generation
            meeting_type = meeting_context.get('meeting_type', 'general')
            template = self._get_question_template(meeting_type)
            
            if not template:
                raise AIServiceError(f"No template found for meeting type: {meeting_type}")
            
            # Get meeting-specific strategy for enhanced prompting
            strategy = self.strategy_manager.get_strategy(meeting_type)
            enhanced_system_prompt = strategy.get_system_prompt(meeting_context)
            
            # Format prompt with meeting context
            formatted_prompt = self._format_question_prompt(template, meeting_context, question_count)
            
            # Log interaction
            interaction = self._log_interaction(
                interaction_type='question_generation',
                user=user,
                input_data=meeting_context,
                formatted_prompt=formatted_prompt,
                template=template,
                entity_type='meeting',
                entity_id=meeting_context.get('meeting_id')
            )
            
            # Generate questions using optimized AI service
            optimization_service = get_optimization_service()
            response = optimization_service.optimized_generate_response(
                prompt=formatted_prompt,
                system_prompt=enhanced_system_prompt or template.system_prompt,
                interaction_type='question_generation',
                context=meeting_context,
                use_cache=True,
                use_fallback=True
            )
            
            if response.error:
                self._complete_interaction(interaction, response)
                raise AIServiceError(f"Failed to generate questions: {response.error}")
            
            # Parse questions from response
            questions = self._parse_questions(response.content)
            
            result = {
                'questions': questions,
                'meeting_type': meeting_type,
                'confidence_score': response.confidence_score,
                'interaction_id': str(interaction.id),
                'cached': response.cached,
                'method': 'ai_generation',
                'context_enhanced': meeting_id is not None
            }
            
            # Complete interaction logging
            self._complete_interaction(interaction, response, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            raise AIServiceError(f"Question generation failed: {str(e)}")
    
    def generate_follow_up_question(
        self,
        original_question: str,
        user_response: str,
        meeting_context: Dict[str, Any],
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Generate intelligent follow-up question based on user response"""
        try:
            # Try structured follow-up generation first
            original_question_dict = {
                'question': original_question,
                'category': self._infer_question_category(original_question),
                'follow_up_triggers': self._extract_triggers_from_question(original_question)
            }
            
            structured_followup = self.flow_manager.generate_follow_up_question(
                original_question_dict, user_response, meeting_context
            )
            
            if structured_followup:
                return {
                    'follow_up_question': structured_followup['question'],
                    'confidence_score': 0.85,
                    'method': 'structured_generation',
                    'reasoning': structured_followup.get('reasoning', 'Structured follow-up based on response analysis'),
                    'category': structured_followup.get('category', 'follow_up')
                }
            
            # Fallback to template-based generation
            template = self._get_followup_template()
            
            if not template:
                raise AIServiceError("No follow-up template found")
            
            # Prepare context for follow-up
            followup_context = {
                'original_question': original_question,
                'user_response': user_response,
                'meeting_type': meeting_context.get('meeting_type', 'general'),
                'participants': meeting_context.get('participants', []),
                'meeting_title': meeting_context.get('title', 'Meeting')
            }
            
            formatted_prompt = self._format_followup_prompt(template, followup_context)
            
            # Log interaction
            interaction = self._log_interaction(
                interaction_type='question_generation',
                user=user,
                input_data=followup_context,
                formatted_prompt=formatted_prompt,
                template=template,
                entity_type='meeting',
                entity_id=meeting_context.get('meeting_id')
            )
            
            # Generate follow-up question using optimized service
            optimization_service = get_optimization_service()
            response = optimization_service.optimized_generate_response(
                prompt=formatted_prompt,
                system_prompt=template.system_prompt,
                interaction_type='question_generation',
                context=followup_context,
                use_cache=True,
                use_fallback=True
            )
            
            if response.error:
                self._complete_interaction(interaction, response)
                raise AIServiceError(f"Failed to generate follow-up: {response.error}")
            
            result = {
                'follow_up_question': response.content.strip(),
                'confidence_score': response.confidence_score,
                'interaction_id': str(interaction.id),
                'cached': response.cached
            }
            
            self._complete_interaction(interaction, response, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating follow-up question: {str(e)}")
            raise AIServiceError(f"Follow-up generation failed: {str(e)}")
    
    def _get_question_template(self, meeting_type: str) -> Optional[AIPromptTemplate]:
        """Get question generation template for meeting type"""
        template_service = PromptTemplateService()
        return template_service.get_template('debriefing_question', meeting_type)
    
    def _get_followup_template(self) -> Optional[AIPromptTemplate]:
        """Get follow-up question template"""
        template_service = PromptTemplateService()
        return template_service.get_template('debriefing_question', 'follow_up')
    
    def _format_question_prompt(
        self,
        template: AIPromptTemplate,
        meeting_context: Dict[str, Any],
        question_count: int
    ) -> str:
        """Format question generation prompt"""
        template_vars = {
            'meeting_type': meeting_context.get('meeting_type', 'general'),
            'meeting_title': meeting_context.get('title', 'Meeting'),
            'participants': ', '.join(meeting_context.get('participants', [])),
            'duration': meeting_context.get('duration', 'unknown'),
            'question_count': question_count,
            'previous_meetings': meeting_context.get('previous_meetings', 0)
        }
        
        template_service = PromptTemplateService()
        return template_service.format_prompt(template, template_vars)
    
    def _format_followup_prompt(
        self,
        template: AIPromptTemplate,
        context: Dict[str, Any]
    ) -> str:
        """Format follow-up question prompt"""
        template_service = PromptTemplateService()
        return template_service.format_prompt(template, context)
    
    def _parse_questions(self, response_content: str) -> List[Dict[str, Any]]:
        """Parse questions from AI response"""
        try:
            questions = []
            lines = response_content.strip().split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                if line and (line.startswith(f'{i+1}.') or line.startswith('-') or line.startswith('•')):
                    # Clean up the question
                    question = line.lstrip('0123456789.-• ').strip()
                    if question:
                        questions.append({
                            'id': i + 1,
                            'question': question,
                            'type': 'open_ended'  # Default type
                        })
            
            # If no numbered questions found, treat each non-empty line as a question
            if not questions:
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line and line.endswith('?'):
                        questions.append({
                            'id': i + 1,
                            'question': line,
                            'type': 'open_ended'
                        })
            
            return questions[:10]  # Limit to 10 questions max
            
        except Exception as e:
            logger.warning(f"Error parsing questions: {str(e)}")
            # Fallback: return the entire response as a single question
            return [{
                'id': 1,
                'question': response_content.strip(),
                'type': 'open_ended'
            }]
    
    def _infer_question_category(self, question: str) -> str:
        """Infer question category from question text"""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['budget', 'cost', 'price', 'investment']):
            return 'budget'
        elif any(word in question_lower for word in ['timeline', 'when', 'deadline', 'urgency']):
            return 'timeline'
        elif any(word in question_lower for word in ['stakeholder', 'decision', 'who', 'authority']):
            return 'stakeholders'
        elif any(word in question_lower for word in ['pain', 'challenge', 'problem', 'issue']):
            return 'pain_points'
        elif any(word in question_lower for word in ['competitor', 'alternative', 'current solution']):
            return 'competitive'
        elif any(word in question_lower for word in ['technical', 'integration', 'requirement']):
            return 'technical'
        elif any(word in question_lower for word in ['demo', 'feature', 'functionality']):
            return 'demo_feedback'
        else:
            return 'general'
    
    def _extract_triggers_from_question(self, question: str) -> List[str]:
        """Extract potential trigger words from question"""
        question_lower = question.lower()
        
        # Common trigger patterns
        triggers = []
        
        if 'budget' in question_lower:
            triggers.extend(['budget', 'cost', 'price', 'investment'])
        if 'timeline' in question_lower:
            triggers.extend(['timeline', 'deadline', 'urgent', 'when'])
        if 'stakeholder' in question_lower or 'decision' in question_lower:
            triggers.extend(['stakeholder', 'decision maker', 'authority'])
        if 'challenge' in question_lower or 'problem' in question_lower:
            triggers.extend(['challenge', 'problem', 'issue', 'difficulty'])
        if 'competitor' in question_lower:
            triggers.extend(['competitor', 'alternative', 'comparison'])
        if 'technical' in question_lower:
            triggers.extend(['technical', 'integration', 'security', 'performance'])
        
        return triggers[:5]  # Limit to 5 triggers


class DataExtractionService(BaseAIService):
    """Service for extracting structured data from conversations"""
    
    def __init__(self):
        super().__init__()
        self.comprehensive_extractor = ComprehensiveDataExtractor()
    
    def extract_meeting_data(
        self,
        conversation_text: str,
        meeting_context: Dict[str, Any],
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Extract structured data from meeting conversation"""
        try:
            # Use comprehensive data extractor
            extracted_data = self.comprehensive_extractor.extract_all_data(
                conversation_text=conversation_text,
                meeting_context=meeting_context,
                use_ai=True  # Use AI-enhanced extraction by default
            )
            
            # Log interaction
            interaction = self._log_interaction(
                interaction_type='data_extraction',
                user=user,
                input_data={
                    'conversation_length': len(conversation_text),
                    'meeting_context': meeting_context,
                    'extraction_method': extracted_data.get('extraction_method', 'comprehensive')
                },
                formatted_prompt=f"Comprehensive extraction from {len(conversation_text)} character conversation",
                entity_type='meeting',
                entity_id=meeting_context.get('meeting_id')
            )
            
            # Check for extraction errors
            if 'error' in extracted_data:
                interaction.mark_error(extracted_data['error'])
                raise AIServiceError(f"Failed to extract data: {extracted_data['error']}")
            
            # Prepare result
            result = {
                'extracted_data': extracted_data,
                'confidence_score': extracted_data.get('overall_confidence', 0.5),
                'interaction_id': str(interaction.id),
                'extraction_method': extracted_data.get('extraction_method', 'comprehensive'),
                'data_categories': {
                    'contacts': len(extracted_data.get('contacts', [])),
                    'action_items': len(extracted_data.get('action_items', [])),
                    'competitive_intelligence': len(extracted_data.get('competitive_intelligence', [])),
                    'deal_information': bool(extracted_data.get('deal_information')),
                    'meeting_outcome': bool(extracted_data.get('meeting_outcome'))
                }
            }
            
            # Mark interaction as successful
            interaction.mark_success(
                response=f"Extracted {sum(result['data_categories'].values())} data points",
                parsed_data=result,
                confidence=result['confidence_score']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting meeting data: {str(e)}")
            raise AIServiceError(f"Data extraction failed: {str(e)}")
    
    def extract_specific_data_type(
        self,
        conversation_text: str,
        data_type: str,
        meeting_context: Dict[str, Any],
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Extract specific type of data (contacts, action_items, etc.)"""
        try:
            if data_type == 'contacts':
                data = self.comprehensive_extractor.contact_extractor.extract_with_ai(
                    conversation_text, self.comprehensive_extractor.client
                )
            elif data_type == 'deal_information':
                data = self.comprehensive_extractor.deal_extractor.extract_with_ai(
                    conversation_text, self.comprehensive_extractor.client
                )
            elif data_type == 'competitive_intelligence':
                data = self.comprehensive_extractor.competitive_extractor.extract_with_ai(
                    conversation_text, self.comprehensive_extractor.client
                )
            elif data_type == 'action_items':
                data = self.comprehensive_extractor.action_extractor.extract_with_ai(
                    conversation_text, self.comprehensive_extractor.client
                )
            elif data_type == 'meeting_outcome':
                data = self.comprehensive_extractor.outcome_classifier.classify_with_ai(
                    conversation_text, self.comprehensive_extractor.client
                )
            else:
                raise AIServiceError(f"Unknown data type: {data_type}")
            
            # Log interaction
            interaction = self._log_interaction(
                interaction_type='data_extraction',
                user=user,
                input_data={
                    'conversation_length': len(conversation_text),
                    'data_type': data_type,
                    'meeting_context': meeting_context
                },
                formatted_prompt=f"Extract {data_type} from conversation",
                entity_type='meeting',
                entity_id=meeting_context.get('meeting_id')
            )
            
            result = {
                'data_type': data_type,
                'extracted_data': data,
                'confidence_score': data.get('extraction_confidence', 0.5) if isinstance(data, dict) else 0.5,
                'interaction_id': str(interaction.id)
            }
            
            # Mark interaction as successful
            interaction.mark_success(
                response=f"Extracted {data_type}",
                parsed_data=result,
                confidence=result['confidence_score']
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting {data_type}: {str(e)}")
            raise AIServiceError(f"{data_type} extraction failed: {str(e)}")
    
    def _get_extraction_template(self) -> Optional[AIPromptTemplate]:
        """Get data extraction template"""
        template_service = PromptTemplateService()
        return template_service.get_template('data_extraction', 'general')
    
    def _format_extraction_prompt(
        self,
        template: AIPromptTemplate,
        conversation_text: str,
        meeting_context: Dict[str, Any]
    ) -> str:
        """Format data extraction prompt"""
        template_vars = {
            'conversation_text': conversation_text,
            'meeting_type': meeting_context.get('meeting_type', 'general'),
            'meeting_title': meeting_context.get('title', 'Meeting'),
            'participants': ', '.join(meeting_context.get('participants', []))
        }
        
        template_service = PromptTemplateService()
        return template_service.format_prompt(template, template_vars)
    
    def _parse_extracted_data(self, response_content: str) -> Dict[str, Any]:
        """Parse structured data from AI response"""
        # This is a simplified parser - in production you might want to use
        # more sophisticated parsing or ask the AI to return JSON
        try:
            extracted = {
                'contacts': [],
                'action_items': [],
                'competitive_intelligence': [],
                'deal_information': {},
                'meeting_outcome': '',
                'next_steps': []
            }
            
            # Simple parsing logic - this would be more sophisticated in production
            lines = response_content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Identify sections
                if 'contact' in line.lower() and ':' in line:
                    current_section = 'contacts'
                elif 'action' in line.lower() and ':' in line:
                    current_section = 'action_items'
                elif 'competitive' in line.lower() and ':' in line:
                    current_section = 'competitive_intelligence'
                elif 'deal' in line.lower() and ':' in line:
                    current_section = 'deal_information'
                elif 'outcome' in line.lower() and ':' in line:
                    current_section = 'meeting_outcome'
                elif 'next' in line.lower() and ':' in line:
                    current_section = 'next_steps'
                elif current_section and line.startswith('-'):
                    # Add item to current section
                    item = line.lstrip('- ').strip()
                    if current_section in ['contacts', 'action_items', 'competitive_intelligence', 'next_steps']:
                        extracted[current_section].append(item)
            
            return extracted
            
        except Exception as e:
            logger.warning(f"Error parsing extracted data: {str(e)}")
            return {
                'raw_response': response_content,
                'parsing_error': str(e)
            }


class AIHealthService:
    """Service for monitoring AI system health and performance"""
    
    def __init__(self):
        self.client = get_gemini_client()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of AI services"""
        try:
            # Get client health
            client_health = self.client.health_check()
            
            # Get usage statistics
            usage_stats = self.client.get_usage_stats()
            
            # Get recent interaction statistics
            interaction_stats = self._get_interaction_stats()
            
            # Get template performance
            template_stats = self._get_template_stats()
            
            return {
                'overall_status': client_health.get('status', 'unknown'),
                'client_health': client_health,
                'usage_stats': usage_stats,
                'interaction_stats': interaction_stats,
                'template_stats': template_stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting AI health status: {str(e)}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _get_interaction_stats(self) -> Dict[str, Any]:
        """Get recent interaction statistics"""
        try:
            from django.db.models import Count, Avg, Q
            from datetime import timedelta
            
            last_24h = timezone.now() - timedelta(hours=24)
            
            stats = AIInteraction.objects.filter(created_at__gte=last_24h).aggregate(
                total_interactions=Count('id'),
                successful_interactions=Count('id', filter=Q(status='success')),
                avg_response_time=Avg('response_time_ms'),
                avg_confidence=Avg('confidence_score')
            )
            
            return {
                'last_24h': stats,
                'success_rate': (
                    stats['successful_interactions'] / stats['total_interactions']
                    if stats['total_interactions'] > 0 else 0
                )
            }
            
        except Exception as e:
            logger.warning(f"Error getting interaction stats: {str(e)}")
            return {'error': str(e)}
    
    def _get_template_stats(self) -> Dict[str, Any]:
        """Get template performance statistics"""
        try:
            templates = AIPromptTemplate.objects.filter(is_active=True)
            
            stats = {
                'total_active_templates': templates.count(),
                'most_used_templates': list(
                    templates.order_by('-usage_count')[:5].values(
                        'name', 'template_type', 'usage_count', 'success_rate'
                    )
                ),
                'avg_success_rate': templates.aggregate(
                    avg_success=Avg('success_rate')
                )['avg_success'] or 0
            }
            
            return stats
            
        except Exception as e:
            logger.warning(f"Error getting template stats: {str(e)}")
            return {'error': str(e)}


# Service instances - lazy loaded
def get_prompt_template_service():
    return PromptTemplateService()

def get_question_generation_service():
    return QuestionGenerationService()

def get_data_extraction_service():
    return DataExtractionService()

def get_ai_health_service():
    return AIHealthService()