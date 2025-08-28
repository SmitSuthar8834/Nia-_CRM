"""
AI-powered summary generation service
Handles draft summary creation, action item extraction, and CRM formatting
"""
import logging
import time
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.utils import timezone
from .models import CallBotSession, DraftSummary, ActionItem, MeetingSession
from .transcription_service import TranscriptionService, MeetingSummary, ActionItem as TranscriptActionItem

logger = logging.getLogger(__name__)


class AISummaryService:
    """
    Service for AI-powered meeting summary generation and processing
    """
    
    def __init__(self, transcription_service: Optional[TranscriptionService] = None):
        self.transcription_service = transcription_service or TranscriptionService()
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the AI summary service"""
        try:
            # Initialize transcription service if not already done
            if not hasattr(self.transcription_service, 'engine') or not self.transcription_service.engine:
                default_config = {
                    'gemini_api_key': getattr(settings, 'GEMINI_API_KEY', None),
                    'engine_type': getattr(settings, 'TRANSCRIPTION_ENGINE', 'mock')
                }
                if config:
                    default_config.update(config)
                
                success = await self.transcription_service.initialize(default_config)
                if not success:
                    self.logger.error("Failed to initialize transcription service")
                    return False
            
            self.logger.info("AI summary service initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize AI summary service: {e}")
            return False
    
    async def generate_draft_summary(self, bot_session: CallBotSession) -> Optional[DraftSummary]:
        """
        Generate AI-powered draft summary from call bot session
        
        Args:
            bot_session: CallBotSession instance with transcript data
            
        Returns:
            DraftSummary instance or None if generation fails
        """
        try:
            from django.db import transaction
            from asgiref.sync import sync_to_async
            
            start_time = time.time()
            
            # Validate input
            if not bot_session.raw_transcript.strip():
                self.logger.warning(f"No transcript available for bot session {bot_session.id}")
                return None
            
            # Check if draft summary already exists (async-safe)
            existing_summary = await sync_to_async(
                lambda: DraftSummary.objects.filter(bot_session=bot_session).first()
            )()
            if existing_summary:
                self.logger.info(f"Draft summary already exists for bot session {bot_session.id}")
                return existing_summary
            
            # Generate summary using transcription service
            session_id = f"summary_gen_{bot_session.id}"
            
            # Create temporary transcription session for processing
            await self.transcription_service.start_transcription(session_id, bot_session.bot_session_id)
            
            # Process the existing transcript
            # In a real implementation, we would reconstruct the transcript chunks
            # For now, we'll work with the raw transcript directly
            summary = await self._generate_summary_from_transcript(
                bot_session.raw_transcript,
                bot_session.speaker_mapping
            )
            
            if not summary:
                self.logger.error(f"Failed to generate summary for bot session {bot_session.id}")
                return None
            
            # Create DraftSummary instance (async-safe)
            processing_time = time.time() - start_time
            
            @sync_to_async
            @transaction.atomic
            def create_draft_summary():
                return DraftSummary.objects.create(
                    bot_session=bot_session,
                    ai_generated_summary=summary.summary_text,
                    key_points=summary.key_points,
                    extracted_action_items=[item.to_dict() for item in summary.action_items],
                    suggested_next_steps=summary.next_steps,
                    decisions_made=summary.decisions_made,
                    confidence_score=summary.confidence_score,
                    processing_time=processing_time
                )
            
            draft_summary = await create_draft_summary()
            
            # Create ActionItem instances
            await self._create_action_items(draft_summary, summary.action_items)
            
            # Generate CRM update suggestions
            await self._generate_crm_suggestions(draft_summary)
            
            # Cleanup temporary session
            await self.transcription_service.stop_transcription(session_id)
            
            self.logger.info(f"Generated draft summary for bot session {bot_session.id} in {processing_time:.2f}s")
            return draft_summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate draft summary: {e}")
            return None
    
    async def _generate_summary_from_transcript(self, transcript: str, speaker_mapping: Dict) -> Optional[MeetingSummary]:
        """Generate summary from raw transcript and speaker mapping"""
        try:
            # Convert speaker mapping to Speaker objects for the engine
            from .transcription_service import Speaker, SpeakerRole
            
            speakers = {}
            for speaker_id, speaker_data in speaker_mapping.items():
                speakers[speaker_id] = Speaker(
                    speaker_id=speaker_id,
                    name=speaker_data.get('name'),
                    role=SpeakerRole(speaker_data.get('role', 'unknown')),
                    confidence=speaker_data.get('confidence', 0.0)
                )
            
            # Generate summary using the transcription engine
            summary = await self.transcription_service.engine.generate_summary(transcript, speakers)
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate summary from transcript: {e}")
            return None
    
    async def _create_action_items(self, draft_summary: DraftSummary, action_items: List[TranscriptActionItem]):
        """Create ActionItem model instances from extracted action items"""
        try:
            from asgiref.sync import sync_to_async
            from django.db import transaction
            
            @sync_to_async
            @transaction.atomic
            def create_action_items_sync():
                # Get or create meeting session
                meeting_session, created = MeetingSession.objects.get_or_create(
                    meeting=draft_summary.bot_session.meeting,
                    defaults={
                        'ai_session_id': draft_summary.bot_session.bot_session_id,
                        'transcript': draft_summary.bot_session.raw_transcript,
                        'summary': draft_summary.ai_generated_summary
                    }
                )
                
                # Create ActionItem instances
                created_items = []
                for item in action_items:
                    action_item = ActionItem.objects.create(
                        meeting_session=meeting_session,
                        description=item.description,
                        assignee=item.assignee or '',
                        due_date=item.due_date,
                        priority=item.priority,
                        confidence=item.confidence,
                        source_text=item.source_text
                    )
                    created_items.append(action_item)
                
                return created_items
            
            created_items = await create_action_items_sync()
            self.logger.info(f"Created {len(created_items)} action items for draft summary {draft_summary.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to create action items: {e}")
    
    async def _generate_crm_suggestions(self, draft_summary: DraftSummary):
        """Generate CRM-specific update suggestions"""
        try:
            from asgiref.sync import sync_to_async
            
            # Generate suggestions for each supported CRM (sync operation)
            @sync_to_async
            def generate_crm_suggestions_sync():
                crm_suggestions = {}
                
                # Generate suggestions for each supported CRM
                for crm_system in ['salesforce', 'hubspot', 'creatio']:
                    crm_suggestions[crm_system] = draft_summary.format_for_crm(crm_system)
                
                return crm_suggestions
            
            crm_suggestions = await generate_crm_suggestions_sync()
            
            # Add opportunity stage suggestions based on meeting content
            stage_suggestions = await self._suggest_opportunity_stages(draft_summary)
            for crm_system in crm_suggestions:
                crm_suggestions[crm_system]['suggested_stage'] = stage_suggestions.get(crm_system)
            
            # Update the draft summary (async-safe)
            @sync_to_async
            def update_draft_summary():
                draft_summary.suggested_crm_updates = crm_suggestions
                draft_summary.save(update_fields=['suggested_crm_updates'])
            
            await update_draft_summary()
            
            self.logger.info(f"Generated CRM suggestions for draft summary {draft_summary.id}")
            
        except Exception as e:
            self.logger.error(f"Failed to generate CRM suggestions: {e}")
    
    async def _suggest_opportunity_stages(self, draft_summary: DraftSummary) -> Dict[str, str]:
        """Suggest opportunity stage changes based on meeting content"""
        try:
            summary_text = draft_summary.ai_generated_summary.lower()
            decisions = [d.lower() for d in draft_summary.decisions_made]
            
            # Simple rule-based stage suggestions
            stage_suggestions = {}
            
            # Check for closing indicators
            closing_indicators = ['signed', 'approved', 'contract', 'deal closed', 'purchase order']
            if any(indicator in summary_text for indicator in closing_indicators):
                stage_suggestions = {
                    'salesforce': 'Closed Won',
                    'hubspot': 'closedwon',
                    'creatio': 'Won'
                }
            
            # Check for proposal indicators
            elif any(word in summary_text for word in ['proposal', 'quote', 'pricing', 'contract review']):
                stage_suggestions = {
                    'salesforce': 'Proposal/Price Quote',
                    'hubspot': 'presentationscheduled',
                    'creatio': 'Proposal'
                }
            
            # Check for negotiation indicators
            elif any(word in summary_text for word in ['negotiate', 'terms', 'conditions', 'discount']):
                stage_suggestions = {
                    'salesforce': 'Negotiation/Review',
                    'hubspot': 'decisionmakerboughtin',
                    'creatio': 'Negotiation'
                }
            
            # Check for qualification indicators
            elif any(word in summary_text for word in ['requirements', 'needs', 'budget', 'timeline']):
                stage_suggestions = {
                    'salesforce': 'Needs Analysis',
                    'hubspot': 'qualifiedtobuy',
                    'creatio': 'Qualification'
                }
            
            # Default to prospecting if no specific indicators
            else:
                stage_suggestions = {
                    'salesforce': 'Prospecting',
                    'hubspot': 'appointmentscheduled',
                    'creatio': 'Prospecting'
                }
            
            return stage_suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to suggest opportunity stages: {e}")
            return {}
    
    def calculate_confidence_score(self, summary: MeetingSummary, transcript_length: int) -> float:
        """
        Calculate overall confidence score for the generated summary
        
        Args:
            summary: Generated MeetingSummary
            transcript_length: Length of original transcript
            
        Returns:
            Confidence score between 0 and 1
        """
        try:
            # Base confidence from AI model
            base_confidence = summary.confidence_score
            
            # Adjust based on transcript quality indicators
            quality_factors = []
            
            # Transcript length factor (longer transcripts generally more reliable)
            if transcript_length > 1000:
                quality_factors.append(0.1)
            elif transcript_length > 500:
                quality_factors.append(0.05)
            
            # Action items extraction success
            if len(summary.action_items) > 0:
                avg_action_confidence = sum(item.confidence for item in summary.action_items) / len(summary.action_items)
                quality_factors.append(avg_action_confidence * 0.1)
            
            # Key points extraction
            if len(summary.key_points) >= 3:
                quality_factors.append(0.05)
            
            # Decisions identified
            if len(summary.decisions_made) > 0:
                quality_factors.append(0.05)
            
            # Calculate final confidence
            adjustment = sum(quality_factors)
            final_confidence = min(1.0, base_confidence + adjustment)
            
            return round(final_confidence, 3)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate confidence score: {e}")
            return 0.5  # Default moderate confidence
    
    async def update_summary_confidence(self, draft_summary: DraftSummary):
        """Update the confidence score of an existing draft summary"""
        try:
            # Reconstruct summary object for confidence calculation
            from .transcription_service import ActionItem as TranscriptActionItem
            
            action_items = []
            for item_data in draft_summary.extracted_action_items:
                action_items.append(TranscriptActionItem(
                    description=item_data.get('description', ''),
                    confidence=item_data.get('confidence', 0.0)
                ))
            
            summary = MeetingSummary(
                summary_text=draft_summary.ai_generated_summary,
                key_points=draft_summary.key_points,
                action_items=action_items,
                next_steps=draft_summary.suggested_next_steps,
                decisions_made=draft_summary.decisions_made,
                confidence_score=draft_summary.confidence_score
            )
            
            # Calculate new confidence score
            transcript_length = len(draft_summary.bot_session.raw_transcript)
            new_confidence = self.calculate_confidence_score(summary, transcript_length)
            
            # Update if significantly different
            if abs(new_confidence - draft_summary.confidence_score) > 0.05:
                draft_summary.confidence_score = new_confidence
                draft_summary.save(update_fields=['confidence_score'])
                self.logger.info(f"Updated confidence score for draft summary {draft_summary.id}: {new_confidence}")
            
        except Exception as e:
            self.logger.error(f"Failed to update summary confidence: {e}")
    
    async def cleanup(self):
        """Cleanup AI summary service resources"""
        try:
            if self.transcription_service:
                await self.transcription_service.cleanup()
            
            self.logger.info("AI summary service cleaned up")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Utility functions for summary processing
def extract_meeting_metrics(draft_summary: DraftSummary) -> Dict[str, Any]:
    """
    Extract metrics from a draft summary for analysis
    
    Args:
        draft_summary: DraftSummary instance
        
    Returns:
        Dictionary with meeting metrics
    """
    try:
        transcript_length = len(draft_summary.bot_session.raw_transcript)
        word_count = len(draft_summary.bot_session.raw_transcript.split())
        
        metrics = {
            'transcript_length': transcript_length,
            'word_count': word_count,
            'summary_length': len(draft_summary.ai_generated_summary),
            'key_points_count': len(draft_summary.key_points),
            'action_items_count': len(draft_summary.extracted_action_items),
            'next_steps_count': len(draft_summary.suggested_next_steps),
            'decisions_count': len(draft_summary.decisions_made),
            'confidence_score': draft_summary.confidence_score,
            'processing_time': draft_summary.processing_time,
            'compression_ratio': len(draft_summary.ai_generated_summary) / transcript_length if transcript_length > 0 else 0
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to extract meeting metrics: {e}")
        return {}


def format_summary_for_export(draft_summary: DraftSummary, format_type: str = 'markdown') -> str:
    """
    Format draft summary for export in various formats
    
    Args:
        draft_summary: DraftSummary instance
        format_type: Export format ('markdown', 'text', 'html')
        
    Returns:
        Formatted summary string
    """
    try:
        if format_type == 'markdown':
            return _format_markdown_summary(draft_summary)
        elif format_type == 'html':
            return _format_html_summary(draft_summary)
        else:  # text
            return _format_text_summary(draft_summary)
            
    except Exception as e:
        logger.error(f"Failed to format summary for export: {e}")
        return draft_summary.ai_generated_summary


def _format_markdown_summary(draft_summary: DraftSummary) -> str:
    """Format summary as Markdown"""
    lines = [
        f"# Meeting Summary: {draft_summary.bot_session.meeting.title}",
        f"**Date:** {draft_summary.bot_session.join_time.strftime('%Y-%m-%d %H:%M')}",
        f"**Confidence Score:** {draft_summary.confidence_score:.2%}",
        "",
        "## Summary",
        draft_summary.ai_generated_summary,
        "",
        "## Key Points"
    ]
    
    for point in draft_summary.key_points:
        lines.append(f"- {point}")
    
    if draft_summary.extracted_action_items:
        lines.extend(["", "## Action Items"])
        for item in draft_summary.extracted_action_items:
            assignee = f" ({item.get('assignee')})" if item.get('assignee') else ""
            due_date = f" - Due: {item.get('due_date')}" if item.get('due_date') else ""
            lines.append(f"- {item.get('description')}{assignee}{due_date}")
    
    if draft_summary.suggested_next_steps:
        lines.extend(["", "## Next Steps"])
        for step in draft_summary.suggested_next_steps:
            lines.append(f"- {step}")
    
    if draft_summary.decisions_made:
        lines.extend(["", "## Decisions Made"])
        for decision in draft_summary.decisions_made:
            lines.append(f"- {decision}")
    
    return "\n".join(lines)


def _format_html_summary(draft_summary: DraftSummary) -> str:
    """Format summary as HTML"""
    html_parts = [
        f"<h1>Meeting Summary: {draft_summary.bot_session.meeting.title}</h1>",
        f"<p><strong>Date:</strong> {draft_summary.bot_session.join_time.strftime('%Y-%m-%d %H:%M')}</p>",
        f"<p><strong>Confidence Score:</strong> {draft_summary.confidence_score:.2%}</p>",
        "<h2>Summary</h2>",
        f"<p>{draft_summary.ai_generated_summary}</p>",
        "<h2>Key Points</h2>",
        "<ul>"
    ]
    
    for point in draft_summary.key_points:
        html_parts.append(f"<li>{point}</li>")
    
    html_parts.append("</ul>")
    
    if draft_summary.extracted_action_items:
        html_parts.extend(["<h2>Action Items</h2>", "<ul>"])
        for item in draft_summary.extracted_action_items:
            assignee = f" ({item.get('assignee')})" if item.get('assignee') else ""
            due_date = f" - Due: {item.get('due_date')}" if item.get('due_date') else ""
            html_parts.append(f"<li>{item.get('description')}{assignee}{due_date}</li>")
        html_parts.append("</ul>")
    
    return "\n".join(html_parts)


def _format_text_summary(draft_summary: DraftSummary) -> str:
    """Format summary as plain text"""
    lines = [
        f"Meeting Summary: {draft_summary.bot_session.meeting.title}",
        f"Date: {draft_summary.bot_session.join_time.strftime('%Y-%m-%d %H:%M')}",
        f"Confidence Score: {draft_summary.confidence_score:.2%}",
        "",
        "SUMMARY:",
        draft_summary.ai_generated_summary,
        "",
        "KEY POINTS:"
    ]
    
    for i, point in enumerate(draft_summary.key_points, 1):
        lines.append(f"{i}. {point}")
    
    if draft_summary.extracted_action_items:
        lines.extend(["", "ACTION ITEMS:"])
        for i, item in enumerate(draft_summary.extracted_action_items, 1):
            assignee = f" ({item.get('assignee')})" if item.get('assignee') else ""
            due_date = f" - Due: {item.get('due_date')}" if item.get('due_date') else ""
            lines.append(f"{i}. {item.get('description')}{assignee}{due_date}")
    
    return "\n".join(lines)