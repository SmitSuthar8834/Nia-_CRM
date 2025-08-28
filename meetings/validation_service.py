"""
Validation service for post-call validation sessions with sales reps
"""
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import (
    DraftSummary, ValidationSession, CRMSyncRecord, 
    Meeting, CallBotSession
)


class ValidationService:
    """
    Service class for managing post-call validation sessions with sales reps
    """
    
    # Default validation session duration (24 hours)
    DEFAULT_SESSION_DURATION = timedelta(hours=24)
    
    def create_validation_session(
        self, 
        draft_summary_id: int, 
        sales_rep_email: str,
        session_duration: Optional[timedelta] = None
    ) -> ValidationSession:
        """
        Create a new validation session for a draft summary
        
        Args:
            draft_summary_id: ID of the draft summary to validate
            sales_rep_email: Email of the sales rep who will validate
            session_duration: Optional custom session duration
            
        Returns:
            ValidationSession: Created validation session
            
        Raises:
            ValidationError: If draft summary doesn't exist or validation already exists
        """
        try:
            draft_summary = DraftSummary.objects.get(id=draft_summary_id)
        except DraftSummary.DoesNotExist:
            raise ValidationError(f"Draft summary with ID {draft_summary_id} not found")
        
        # Check if validation session already exists
        if hasattr(draft_summary, 'validationsession'):
            raise ValidationError("Validation session already exists for this draft summary")
        
        # Generate validation questions based on draft summary
        validation_questions = self._generate_validation_questions(draft_summary)
        
        # Set session timing
        now = timezone.now()
        duration = session_duration or self.DEFAULT_SESSION_DURATION
        expires_at = now + duration
        
        with transaction.atomic():
            validation_session = ValidationSession.objects.create(
                draft_summary=draft_summary,
                sales_rep_email=sales_rep_email,
                validation_questions=validation_questions,
                started_at=now,
                expires_at=expires_at,
                validation_status='pending'
            )
        
        return validation_session
    
    def _generate_validation_questions(self, draft_summary: DraftSummary) -> List[Dict]:
        """
        Generate validation questions based on draft summary content
        
        Args:
            draft_summary: DraftSummary instance
            
        Returns:
            List of validation questions with metadata
        """
        questions = []
        
        # Summary accuracy question
        questions.append({
            'id': 'summary_accuracy',
            'type': 'confirmation',
            'question': 'Is this meeting summary accurate and complete?',
            'context': draft_summary.ai_generated_summary,
            'required': True,
            'confidence_threshold': 0.8
        })
        
        # Key points validation
        if draft_summary.key_points:
            questions.append({
                'id': 'key_points_validation',
                'type': 'multi_select',
                'question': 'Which key points are accurate? (Select all that apply)',
                'options': draft_summary.key_points,
                'required': True
            })
        
        # Action items validation
        if draft_summary.extracted_action_items:
            questions.append({
                'id': 'action_items_validation',
                'type': 'action_items_review',
                'question': 'Please review and confirm these action items:',
                'items': draft_summary.extracted_action_items,
                'required': True
            })
        
        # Next steps confirmation
        if draft_summary.suggested_next_steps:
            questions.append({
                'id': 'next_steps_confirmation',
                'type': 'text_edit',
                'question': 'What are the confirmed next steps and timeline?',
                'suggested_text': '\n'.join(draft_summary.suggested_next_steps),
                'required': True
            })
        
        # CRM updates approval
        if draft_summary.suggested_crm_updates:
            questions.append({
                'id': 'crm_updates_approval',
                'type': 'crm_approval',
                'question': 'Should I update the CRM with these changes?',
                'suggested_updates': draft_summary.suggested_crm_updates,
                'required': True
            })
        
        # Deal stage update (if applicable)
        meeting = draft_summary.bot_session.meeting
        if meeting.lead:
            questions.append({
                'id': 'deal_stage_update',
                'type': 'stage_selection',
                'question': f'Should I update the deal stage for {meeting.lead.company}?',
                'current_stage': getattr(meeting.lead, 'stage', 'Unknown'),
                'suggested_stage': self._suggest_deal_stage(draft_summary),
                'required': False
            })
        
        # Additional notes
        questions.append({
            'id': 'additional_notes',
            'type': 'text_area',
            'question': 'Any additional notes or corrections?',
            'placeholder': 'Add any missing information or corrections...',
            'required': False
        })
        
        return questions
    
    def _suggest_deal_stage(self, draft_summary: DraftSummary) -> str:
        """
        Suggest deal stage based on meeting content
        
        Args:
            draft_summary: DraftSummary instance
            
        Returns:
            Suggested deal stage
        """
        summary_text = draft_summary.ai_generated_summary.lower()
        decisions = [d.lower() for d in draft_summary.decisions_made]
        
        # Simple keyword-based stage suggestion
        if any(keyword in summary_text for keyword in ['signed', 'contract', 'agreement', 'closed']):
            return 'Closed Won'
        elif any(keyword in summary_text for keyword in ['proposal', 'quote', 'pricing']):
            return 'Proposal'
        elif any(keyword in summary_text for keyword in ['demo', 'presentation', 'showcase']):
            return 'Demo Scheduled'
        elif any(keyword in summary_text for keyword in ['qualified', 'budget', 'timeline']):
            return 'Qualified'
        elif any(keyword in summary_text for keyword in ['not interested', 'no budget', 'postpone']):
            return 'Closed Lost'
        else:
            return 'In Progress'
    
    def get_validation_session(self, session_id: int) -> ValidationSession:
        """
        Get validation session by ID with expiration check
        
        Args:
            session_id: ValidationSession ID
            
        Returns:
            ValidationSession instance
            
        Raises:
            ValidationError: If session doesn't exist or has expired
        """
        try:
            session = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting__lead'
            ).get(id=session_id)
        except ValidationSession.DoesNotExist:
            raise ValidationError(f"Validation session with ID {session_id} not found")
        
        # Check if session has expired
        if session.is_expired and session.validation_status == 'pending':
            session.validation_status = 'expired'
            session.save()
            raise ValidationError("Validation session has expired")
        
        return session
    
    def submit_validation_response(
        self, 
        session_id: int, 
        question_id: str, 
        response: Dict
    ) -> ValidationSession:
        """
        Submit a response to a validation question
        
        Args:
            session_id: ValidationSession ID
            question_id: ID of the question being answered
            response: Response data
            
        Returns:
            Updated ValidationSession instance
            
        Raises:
            ValidationError: If session is invalid or response is malformed
        """
        session = self.get_validation_session(session_id)
        
        if session.validation_status not in ['pending', 'in_progress']:
            raise ValidationError("Cannot submit responses to completed or expired session")
        
        # Validate question exists
        question = next((q for q in session.validation_questions if q['id'] == question_id), None)
        if not question:
            raise ValidationError(f"Question with ID {question_id} not found")
        
        # Validate response format based on question type
        self._validate_response_format(question, response)
        
        # Update session status to in_progress if first response
        if session.validation_status == 'pending':
            session.validation_status = 'in_progress'
        
        # Store response
        if not session.rep_responses:
            session.rep_responses = {}
        
        session.rep_responses[question_id] = {
            'response': response,
            'timestamp': timezone.now().isoformat(),
            'question_type': question['type']
        }
        
        # Track changes for audit trail
        if not session.changes_made:
            session.changes_made = []
        
        session.changes_made.append({
            'action': 'response_submitted',
            'question_id': question_id,
            'timestamp': timezone.now().isoformat(),
            'response_summary': self._summarize_response(question, response)
        })
        
        session.save()
        return session
    
    def _validate_response_format(self, question: Dict, response: Dict) -> None:
        """
        Validate response format based on question type
        
        Args:
            question: Question configuration
            response: Response data
            
        Raises:
            ValidationError: If response format is invalid
        """
        question_type = question['type']
        
        if question_type == 'confirmation':
            if 'confirmed' not in response or not isinstance(response['confirmed'], bool):
                raise ValidationError("Confirmation response must include 'confirmed' boolean field")
        
        elif question_type == 'multi_select':
            if 'selected_options' not in response or not isinstance(response['selected_options'], list):
                raise ValidationError("Multi-select response must include 'selected_options' list")
        
        elif question_type == 'action_items_review':
            if 'approved_items' not in response:
                raise ValidationError("Action items response must include 'approved_items'")
        
        elif question_type == 'text_edit':
            if 'text' not in response or not isinstance(response['text'], str):
                raise ValidationError("Text edit response must include 'text' string field")
        
        elif question_type == 'crm_approval':
            if 'approved' not in response or not isinstance(response['approved'], bool):
                raise ValidationError("CRM approval response must include 'approved' boolean field")
        
        elif question_type == 'stage_selection':
            if 'selected_stage' not in response:
                raise ValidationError("Stage selection response must include 'selected_stage'")
    
    def _summarize_response(self, question: Dict, response: Dict) -> str:
        """
        Create a summary of the response for audit trail
        
        Args:
            question: Question configuration
            response: Response data
            
        Returns:
            Human-readable response summary
        """
        question_type = question['type']
        
        if question_type == 'confirmation':
            return f"Confirmed: {response['confirmed']}"
        elif question_type == 'multi_select':
            return f"Selected {len(response['selected_options'])} options"
        elif question_type == 'action_items_review':
            approved_count = len(response.get('approved_items', []))
            return f"Approved {approved_count} action items"
        elif question_type == 'text_edit':
            return f"Text updated ({len(response['text'])} characters)"
        elif question_type == 'crm_approval':
            return f"CRM updates {'approved' if response['approved'] else 'rejected'}"
        elif question_type == 'stage_selection':
            return f"Stage selected: {response['selected_stage']}"
        else:
            return "Response submitted"
    
    def complete_validation_session(self, session_id: int) -> Tuple[ValidationSession, str]:
        """
        Complete validation session and generate final summary
        
        Args:
            session_id: ValidationSession ID
            
        Returns:
            Tuple of (ValidationSession, final_summary)
            
        Raises:
            ValidationError: If session cannot be completed
        """
        session = self.get_validation_session(session_id)
        
        if session.validation_status != 'in_progress':
            raise ValidationError("Can only complete sessions that are in progress")
        
        # Check if all required questions have been answered
        required_questions = [q for q in session.validation_questions if q.get('required', False)]
        answered_questions = set(session.rep_responses.keys())
        
        missing_required = [q['id'] for q in required_questions if q['id'] not in answered_questions]
        if missing_required:
            raise ValidationError(f"Required questions not answered: {', '.join(missing_required)}")
        
        # Generate final validated summary
        final_summary = self._generate_final_summary(session)
        
        # Generate approved CRM updates
        approved_crm_updates = self._generate_approved_crm_updates(session)
        
        with transaction.atomic():
            # Update session
            session.validation_status = 'completed'
            session.completed_at = timezone.now()
            session.validated_summary = final_summary
            session.approved_crm_updates = approved_crm_updates
            
            # Add completion to audit trail
            session.changes_made.append({
                'action': 'session_completed',
                'timestamp': timezone.now().isoformat(),
                'final_summary_length': len(final_summary)
            })
            
            session.save()
        
        return session, final_summary
    
    def _generate_final_summary(self, session: ValidationSession) -> str:
        """
        Generate final validated summary from session responses
        
        Args:
            session: ValidationSession instance
            
        Returns:
            Final validated summary text
        """
        draft_summary = session.draft_summary
        responses = session.rep_responses
        
        # Start with original summary if confirmed, otherwise use edited version
        summary_response = responses.get('summary_accuracy', {}).get('response', {})
        if summary_response.get('confirmed', False):
            final_summary = draft_summary.ai_generated_summary
        else:
            final_summary = summary_response.get('edited_text', draft_summary.ai_generated_summary)
        
        # Add validated key points
        key_points_response = responses.get('key_points_validation', {}).get('response', {})
        validated_key_points = key_points_response.get('selected_options', draft_summary.key_points)
        
        if validated_key_points:
            final_summary += "\n\nKey Points:\n"
            final_summary += "\n".join(f"• {point}" for point in validated_key_points)
        
        # Add validated action items
        action_items_response = responses.get('action_items_validation', {}).get('response', {})
        approved_items = action_items_response.get('approved_items', draft_summary.extracted_action_items)
        
        if approved_items:
            final_summary += "\n\nAction Items:\n"
            for item in approved_items:
                if isinstance(item, dict):
                    final_summary += f"• {item.get('description', str(item))}\n"
                else:
                    final_summary += f"• {item}\n"
        
        # Add confirmed next steps
        next_steps_response = responses.get('next_steps_confirmation', {}).get('response', {})
        next_steps_text = next_steps_response.get('text', '')
        
        if next_steps_text:
            final_summary += f"\n\nNext Steps:\n{next_steps_text}"
        
        # Add additional notes
        additional_notes_response = responses.get('additional_notes', {}).get('response', {})
        additional_notes = additional_notes_response.get('text', '')
        
        if additional_notes:
            final_summary += f"\n\nAdditional Notes:\n{additional_notes}"
        
        return final_summary.strip()
    
    def _generate_approved_crm_updates(self, session: ValidationSession) -> Dict:
        """
        Generate approved CRM updates from session responses
        
        Args:
            session: ValidationSession instance
            
        Returns:
            Dictionary of approved CRM updates
        """
        responses = session.rep_responses
        approved_updates = {}
        
        # Check CRM approval response
        crm_approval_response = responses.get('crm_updates_approval', {}).get('response', {})
        if crm_approval_response.get('approved', False):
            # Use original suggested updates as base
            approved_updates = session.draft_summary.suggested_crm_updates.copy()
            
            # Apply any modifications from the approval response
            if 'modifications' in crm_approval_response:
                approved_updates.update(crm_approval_response['modifications'])
        
        # Add deal stage update if approved
        stage_response = responses.get('deal_stage_update', {}).get('response', {})
        if 'selected_stage' in stage_response:
            approved_updates['deal_stage'] = stage_response['selected_stage']
        
        # Add final summary to updates
        approved_updates['meeting_summary'] = session.validated_summary
        
        return approved_updates
    
    def get_sessions_for_rep(self, sales_rep_email: str, status: Optional[str] = None) -> List[ValidationSession]:
        """
        Get validation sessions for a specific sales rep
        
        Args:
            sales_rep_email: Sales rep email address
            status: Optional status filter
            
        Returns:
            List of ValidationSession instances
        """
        queryset = ValidationSession.objects.filter(
            sales_rep_email=sales_rep_email
        ).select_related(
            'draft_summary__bot_session__meeting__lead'
        ).order_by('-started_at')
        
        if status:
            queryset = queryset.filter(validation_status=status)
        
        return list(queryset)
    
    def expire_old_sessions(self) -> int:
        """
        Mark expired validation sessions as expired
        
        Returns:
            Number of sessions marked as expired
        """
        now = timezone.now()
        expired_count = ValidationSession.objects.filter(
            expires_at__lt=now,
            validation_status='pending'
        ).update(validation_status='expired')
        
        return expired_count