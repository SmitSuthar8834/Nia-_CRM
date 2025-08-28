"""
Unit tests for AI summary service
Tests transcription processing, summary generation, and action item extraction
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Meeting, CallBotSession, DraftSummary, ActionItem, MeetingSession
from .ai_summary_service import AISummaryService, extract_meeting_metrics, format_summary_for_export
from .transcription_service import (
    TranscriptionService, MeetingSummary, ActionItem as TranscriptActionItem,
    Speaker, SpeakerRole
)
from leads.models import Lead


class AISummaryServiceTest(TestCase):
    """Test cases for AISummaryService"""
    
    def setUp(self):
        """Set up test data"""
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_001",
            name="John Doe",
            email="john.doe@example.com",
            company="Test Company",
            status="qualified"
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_123",
            lead=self.lead,
            title="Test Sales Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            attendees=["john.doe@example.com", "sales@company.com"],
            status="completed"
        )
        
        # Create test call bot session
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="bot_session_123",
            platform="meet",
            join_time=timezone.now(),
            connection_status="connected",
            raw_transcript=self._get_sample_transcript(),
            speaker_mapping=self._get_sample_speaker_mapping(),
            audio_quality="good"
        )
        
        # Create AI summary service with mock transcription service
        self.mock_transcription_service = Mock(spec=TranscriptionService)
        self.ai_service = AISummaryService(self.mock_transcription_service)
    
    def _get_sample_transcript(self):
        """Get sample meeting transcript"""
        return """
        Alice Johnson: Good morning everyone, thank you for joining today's meeting.
        Bob Smith: Thanks for having me, Alice. I'm excited to discuss the project requirements.
        Alice Johnson: Great! Let's start with the timeline. We need to deliver this by March 15th.
        Bob Smith: That's a tight timeline, but I think we can make it work. I'll need to coordinate with the development team.
        Alice Johnson: Perfect. Bob, can you follow up with the technical requirements by Friday?
        Bob Smith: Absolutely, I'll have those ready for review by end of week.
        Alice Johnson: Excellent. We also decided to use React for the frontend development.
        Bob Smith: Good choice. I'll make sure the team is aligned on that decision.
        Alice Johnson: Any other questions before we wrap up?
        Bob Smith: No, I think we covered everything. I'll send out meeting notes later today.
        """
    
    def _get_sample_speaker_mapping(self):
        """Get sample speaker mapping"""
        return {
            "speaker_1": {
                "name": "Alice Johnson",
                "role": "host",
                "confidence": 0.95
            },
            "speaker_2": {
                "name": "Bob Smith",
                "role": "participant",
                "confidence": 0.88
            }
        }
    
    def _get_sample_meeting_summary(self):
        """Get sample MeetingSummary object"""
        action_items = [
            TranscriptActionItem(
                description="Follow up with technical requirements",
                assignee="Bob Smith",
                due_date="2024-03-15",
                priority="high",
                confidence=0.85,
                source_text="Bob, can you follow up with the technical requirements by Friday?"
            ),
            TranscriptActionItem(
                description="Send out meeting notes",
                assignee="Bob Smith",
                due_date=None,
                priority="medium",
                confidence=0.78,
                source_text="I'll send out meeting notes later today"
            )
        ]
        
        return MeetingSummary(
            summary_text="Team discussed project timeline and technical requirements. Decided on React for frontend development.",
            key_points=[
                "Project delivery deadline set for March 15th",
                "React chosen for frontend development",
                "Technical requirements review needed by Friday"
            ],
            action_items=action_items,
            next_steps=[
                "Coordinate with development team on timeline",
                "Finalize technical requirements document",
                "Begin React frontend setup"
            ],
            decisions_made=[
                "Approved React for frontend development",
                "Confirmed March 15th delivery deadline"
            ],
            confidence_score=0.87
        )
    
    @patch('meetings.ai_summary_service.settings')
    def test_initialize_success(self, mock_settings):
        """Test successful initialization of AI summary service"""
        # Setup
        mock_settings.GEMINI_API_KEY = "test_api_key"
        mock_settings.TRANSCRIPTION_ENGINE = "mock"
        self.mock_transcription_service.initialize = AsyncMock(return_value=True)
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service.initialize())
        loop.close()
        
        # Verify
        self.assertTrue(result)
        self.mock_transcription_service.initialize.assert_called_once()
    
    @patch('meetings.ai_summary_service.settings')
    def test_initialize_failure(self, mock_settings):
        """Test initialization failure"""
        # Setup
        mock_settings.GEMINI_API_KEY = None
        self.mock_transcription_service.initialize = AsyncMock(return_value=False)
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service.initialize())
        loop.close()
        
        # Verify
        self.assertFalse(result)
    
    def test_generate_draft_summary_success(self):
        """Test successful draft summary generation"""
        # Setup
        sample_summary = self._get_sample_meeting_summary()
        
        self.mock_transcription_service.start_transcription = AsyncMock()
        self.mock_transcription_service.stop_transcription = AsyncMock()
        self.mock_transcription_service.engine = Mock()
        self.mock_transcription_service.engine.generate_summary = AsyncMock(return_value=sample_summary)
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service.generate_draft_summary(self.bot_session))
        loop.close()
        
        # Verify
        self.assertIsNotNone(result)
        self.assertIsInstance(result, DraftSummary)
        self.assertEqual(result.bot_session, self.bot_session)
        self.assertEqual(result.ai_generated_summary, sample_summary.summary_text)
        self.assertEqual(result.key_points, sample_summary.key_points)
        self.assertEqual(len(result.extracted_action_items), 2)
        self.assertGreater(result.confidence_score, 0)
        
        # Verify action items were created
        action_items = ActionItem.objects.filter(meeting_session__meeting=self.meeting)
        self.assertEqual(action_items.count(), 2)
        
        # Verify CRM suggestions were generated
        self.assertIn('salesforce', result.suggested_crm_updates)
        self.assertIn('hubspot', result.suggested_crm_updates)
        self.assertIn('creatio', result.suggested_crm_updates)
    
    def test_generate_draft_summary_empty_transcript(self):
        """Test draft summary generation with empty transcript"""
        # Setup
        self.bot_session.raw_transcript = ""
        self.bot_session.save()
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service.generate_draft_summary(self.bot_session))
        loop.close()
        
        # Verify
        self.assertIsNone(result)
    
    def test_generate_draft_summary_existing_summary(self):
        """Test that existing draft summary is returned"""
        # Setup - create existing draft summary
        existing_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Existing summary",
            key_points=["Existing point"],
            extracted_action_items=[],
            suggested_next_steps=[],
            decisions_made=[],
            confidence_score=0.75
        )
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service.generate_draft_summary(self.bot_session))
        loop.close()
        
        # Verify
        self.assertEqual(result.id, existing_summary.id)
        self.assertEqual(result.ai_generated_summary, "Existing summary")
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation"""
        # Setup
        sample_summary = self._get_sample_meeting_summary()
        transcript_length = len(self._get_sample_transcript())
        
        # Execute
        confidence = self.ai_service.calculate_confidence_score(sample_summary, transcript_length)
        
        # Verify
        self.assertGreater(confidence, 0)
        self.assertLessEqual(confidence, 1.0)
        self.assertIsInstance(confidence, float)
    
    def test_suggest_opportunity_stages_closing(self):
        """Test opportunity stage suggestions for closing scenarios"""
        # Setup
        draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="The client signed the contract and approved the purchase order.",
            key_points=["Contract signed", "Purchase order approved"],
            extracted_action_items=[],
            suggested_next_steps=[],
            decisions_made=["Approved contract terms"],
            confidence_score=0.9
        )
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service._suggest_opportunity_stages(draft_summary))
        loop.close()
        
        # Verify
        self.assertEqual(result['salesforce'], 'Closed Won')
        self.assertEqual(result['hubspot'], 'closedwon')
        self.assertEqual(result['creatio'], 'Won')
    
    def test_suggest_opportunity_stages_proposal(self):
        """Test opportunity stage suggestions for proposal scenarios"""
        # Setup
        draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Discussed pricing options and prepared a detailed proposal for review.",
            key_points=["Pricing discussed", "Proposal prepared"],
            extracted_action_items=[],
            suggested_next_steps=[],
            decisions_made=[],
            confidence_score=0.8
        )
        
        # Execute
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.ai_service._suggest_opportunity_stages(draft_summary))
        loop.close()
        
        # Verify
        self.assertEqual(result['salesforce'], 'Proposal/Price Quote')
        self.assertEqual(result['hubspot'], 'presentationscheduled')
        self.assertEqual(result['creatio'], 'Proposal')


class MeetingMetricsTest(TestCase):
    """Test cases for meeting metrics extraction"""
    
    def setUp(self):
        """Set up test data"""
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_002",
            name="Jane Smith",
            email="jane.smith@example.com",
            company="Test Corp"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_456",
            lead=self.lead,
            title="Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="bot_session_456",
            platform="teams",
            join_time=timezone.now(),
            raw_transcript="This is a test transcript with multiple words for testing purposes.",
            speaker_mapping={}
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Test summary",
            key_points=["Point 1", "Point 2", "Point 3"],
            extracted_action_items=[
                {"description": "Task 1", "assignee": "John"},
                {"description": "Task 2", "assignee": "Jane"}
            ],
            suggested_next_steps=["Step 1", "Step 2"],
            decisions_made=["Decision 1"],
            confidence_score=0.85,
            processing_time=2.5
        )
    
    def test_extract_meeting_metrics(self):
        """Test meeting metrics extraction"""
        # Execute
        metrics = extract_meeting_metrics(self.draft_summary)
        
        # Verify
        self.assertIn('transcript_length', metrics)
        self.assertIn('word_count', metrics)
        self.assertIn('summary_length', metrics)
        self.assertIn('key_points_count', metrics)
        self.assertIn('action_items_count', metrics)
        self.assertIn('next_steps_count', metrics)
        self.assertIn('decisions_count', metrics)
        self.assertIn('confidence_score', metrics)
        self.assertIn('processing_time', metrics)
        self.assertIn('compression_ratio', metrics)
        
        # Verify values
        self.assertEqual(metrics['key_points_count'], 3)
        self.assertEqual(metrics['action_items_count'], 2)
        self.assertEqual(metrics['next_steps_count'], 2)
        self.assertEqual(metrics['decisions_count'], 1)
        self.assertEqual(metrics['confidence_score'], 0.85)
        self.assertEqual(metrics['processing_time'], 2.5)
        self.assertGreater(metrics['word_count'], 0)
        self.assertGreater(metrics['compression_ratio'], 0)


class SummaryFormattingTest(TestCase):
    """Test cases for summary formatting and export"""
    
    def setUp(self):
        """Set up test data"""
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_003",
            name="Test User",
            email="test@example.com",
            company="Test Inc"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_789",
            lead=self.lead,
            title="Formatting Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="bot_session_789",
            platform="zoom",
            join_time=timezone.now(),
            raw_transcript="Test transcript for formatting",
            speaker_mapping={}
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="This is a test summary for formatting validation.",
            key_points=["Key point 1", "Key point 2"],
            extracted_action_items=[
                {
                    "description": "Complete task A",
                    "assignee": "John Doe",
                    "due_date": "2024-03-15",
                    "priority": "high"
                },
                {
                    "description": "Review document B",
                    "assignee": "Jane Smith",
                    "due_date": None,
                    "priority": "medium"
                }
            ],
            suggested_next_steps=["Next step 1", "Next step 2"],
            decisions_made=["Decision A", "Decision B"],
            confidence_score=0.92
        )
    
    def test_format_summary_markdown(self):
        """Test Markdown formatting"""
        # Execute
        result = format_summary_for_export(self.draft_summary, 'markdown')
        
        # Verify
        self.assertIn('# Meeting Summary:', result)
        self.assertIn('## Summary', result)
        self.assertIn('## Key Points', result)
        self.assertIn('## Action Items', result)
        self.assertIn('## Next Steps', result)
        self.assertIn('## Decisions Made', result)
        self.assertIn('- Key point 1', result)
        self.assertIn('- Complete task A (John Doe) - Due: 2024-03-15', result)
        self.assertIn('- Review document B (Jane Smith)', result)
    
    def test_format_summary_html(self):
        """Test HTML formatting"""
        # Execute
        result = format_summary_for_export(self.draft_summary, 'html')
        
        # Verify
        self.assertIn('<h1>Meeting Summary:', result)
        self.assertIn('<h2>Summary</h2>', result)
        self.assertIn('<h2>Key Points</h2>', result)
        self.assertIn('<h2>Action Items</h2>', result)
        self.assertIn('<ul>', result)
        self.assertIn('<li>Key point 1</li>', result)
        self.assertIn('<li>Complete task A (John Doe) - Due: 2024-03-15</li>', result)
    
    def test_format_summary_text(self):
        """Test plain text formatting"""
        # Execute
        result = format_summary_for_export(self.draft_summary, 'text')
        
        # Verify
        self.assertIn('Meeting Summary:', result)
        self.assertIn('SUMMARY:', result)
        self.assertIn('KEY POINTS:', result)
        self.assertIn('ACTION ITEMS:', result)
        self.assertIn('1. Key point 1', result)
        self.assertIn('1. Complete task A (John Doe) - Due: 2024-03-15', result)
        self.assertIn('2. Review document B (Jane Smith)', result)
    
    def test_format_summary_invalid_format(self):
        """Test handling of invalid format type"""
        # Execute
        result = format_summary_for_export(self.draft_summary, 'invalid')
        
        # Verify - should fallback to text format (not just the summary text)
        self.assertIn('Meeting Summary:', result)
        self.assertIn('SUMMARY:', result)
        self.assertIn(self.draft_summary.ai_generated_summary, result)


class CRMFormattingTest(TestCase):
    """Test cases for CRM-specific formatting"""
    
    def setUp(self):
        """Set up test data"""
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_004",
            name="CRM Test User",
            email="crm@example.com",
            company="CRM Corp"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_crm",
            lead=self.lead,
            title="CRM Integration Test",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="bot_session_crm",
            platform="meet",
            join_time=timezone.now(),
            raw_transcript="CRM test transcript",
            speaker_mapping={}
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="CRM integration test summary",
            key_points=["CRM point 1", "CRM point 2"],
            extracted_action_items=[
                {"description": "CRM task", "assignee": "CRM User"}
            ],
            suggested_next_steps=["CRM next step"],
            decisions_made=["CRM decision"],
            confidence_score=0.88
        )
    
    def test_format_for_salesforce(self):
        """Test Salesforce formatting"""
        # Execute
        result = self.draft_summary.format_for_crm('salesforce')
        
        # Verify
        self.assertIn('Description', result)
        self.assertIn('Key_Points__c', result)
        self.assertIn('Action_Items__c', result)
        self.assertIn('Next_Steps__c', result)
        self.assertIn('Decisions_Made__c', result)
        self.assertIn('• CRM point 1', result['Key_Points__c'])
        self.assertIn('• CRM task', result['Action_Items__c'])
    
    def test_format_for_hubspot(self):
        """Test HubSpot formatting"""
        # Execute
        result = self.draft_summary.format_for_crm('hubspot')
        
        # Verify
        self.assertIn('hs_meeting_body', result)
        self.assertIn('hs_meeting_outcome', result)
        self.assertIn('custom_key_points', result)
        self.assertIn('custom_action_items', result)
        self.assertEqual(result['hs_meeting_outcome'], 'COMPLETED')
    
    def test_format_for_creatio(self):
        """Test Creatio formatting"""
        # Execute
        result = self.draft_summary.format_for_crm('creatio')
        
        # Verify
        self.assertIn('Notes', result)
        self.assertIn('KeyPoints', result)
        self.assertIn('ActionItems', result)
        self.assertIn('NextSteps', result)
        self.assertIn('Decisions', result)
        self.assertEqual(result['Notes'], self.draft_summary.ai_generated_summary)
    
    def test_format_for_unknown_crm(self):
        """Test formatting for unknown CRM system"""
        # Execute
        result = self.draft_summary.format_for_crm('unknown')
        
        # Verify - should return base data
        self.assertIn('summary', result)
        self.assertIn('key_points', result)
        self.assertIn('action_items', result)
        self.assertIn('next_steps', result)
        self.assertIn('decisions', result)


if __name__ == '__main__':
    # Run tests with pytest for async support
    pytest.main([__file__, '-v'])