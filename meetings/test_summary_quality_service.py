"""
Unit tests for summary quality service
Tests quality assessment, confidence scoring, and validation
"""
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Meeting, CallBotSession, DraftSummary
from .summary_quality_service import (
    SummaryQualityService, QualityMetric, QualityScore, QualityAssessment,
    update_summary_confidence_score, validate_summary_for_crm_sync
)
from leads.models import Lead


class SummaryQualityServiceTest(TestCase):
    """Test cases for SummaryQualityService"""
    
    def setUp(self):
        """Set up test data"""
        # Create test lead
        self.lead = Lead.objects.create(
            crm_id="TEST_LEAD_QUALITY",
            name="Quality Test User",
            email="quality@example.com",
            company="Quality Corp",
            status="qualified"
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            calendar_event_id="quality_test_event",
            lead=self.lead,
            title="Quality Assessment Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            attendees=["quality@example.com", "test@company.com"],
            status="completed"
        )
        
        # Create test call bot session with good quality data
        self.good_bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="quality_bot_session_good",
            platform="meet",
            join_time=timezone.now(),
            connection_status="connected",
            raw_transcript=self._get_good_quality_transcript(),
            speaker_mapping=self._get_good_speaker_mapping(),
            audio_quality="excellent"
        )
        
        # Create draft summary with good quality
        self.good_draft_summary = DraftSummary.objects.create(
            bot_session=self.good_bot_session,
            ai_generated_summary=self._get_good_quality_summary(),
            key_points=self._get_good_key_points(),
            extracted_action_items=self._get_good_action_items(),
            suggested_next_steps=["Finalize requirements", "Schedule follow-up"],
            decisions_made=["Approved React framework", "Set March deadline"],
            confidence_score=0.85
        )
        
        # Create poor quality test data
        self.poor_bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="quality_bot_session_poor",
            platform="zoom",
            join_time=timezone.now(),
            connection_status="connected",
            raw_transcript="Short transcript.",
            speaker_mapping={},
            audio_quality="poor"
        )
        
        self.poor_draft_summary = DraftSummary.objects.create(
            bot_session=self.poor_bot_session,
            ai_generated_summary="Error in summary generation.",
            key_points=[],
            extracted_action_items=[],
            suggested_next_steps=[],
            decisions_made=[],
            confidence_score=0.2
        )
        
        self.quality_service = SummaryQualityService()
    
    def _get_good_quality_transcript(self):
        """Get a good quality transcript for testing"""
        return """
        Alice Johnson: Good morning everyone, thank you for joining today's project planning meeting.
        Bob Smith: Thanks Alice. I'm excited to discuss the new web application requirements.
        Alice Johnson: Great! Let's start with the project timeline. We need to deliver the MVP by March 15th, 2024.
        Bob Smith: That's a tight timeline, but achievable. I'll coordinate with the development team this week.
        Alice Johnson: Perfect. We've decided to use React for the frontend and Node.js for the backend.
        Bob Smith: Excellent choice. I'll set up the development environment and create the initial project structure.
        Alice Johnson: Bob, can you also prepare the technical requirements document by Friday?
        Bob Smith: Absolutely. I'll have the requirements ready for review by end of week.
        Alice Johnson: We also need to schedule weekly sprint reviews starting next Monday.
        Bob Smith: I'll send out calendar invites for the sprint reviews today.
        Alice Johnson: Any questions before we wrap up?
        Bob Smith: No questions. I think we have a clear path forward.
        Alice Johnson: Excellent. Let's reconvene next week to review progress.
        """
    
    def _get_good_speaker_mapping(self):
        """Get good speaker mapping for testing"""
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
    
    def _get_good_quality_summary(self):
        """Get a good quality summary for testing"""
        return """
        The team conducted a project planning meeting to discuss the new web application development.
        Key decisions were made regarding technology stack and timeline. The MVP delivery date was
        set for March 15th, 2024, with React chosen for frontend and Node.js for backend development.
        Weekly sprint reviews will begin next Monday to track progress.
        """
    
    def _get_good_key_points(self):
        """Get good quality key points for testing"""
        return [
            "MVP delivery deadline set for March 15th, 2024",
            "Technology stack decided: React frontend, Node.js backend",
            "Weekly sprint reviews scheduled starting next Monday",
            "Technical requirements document due by Friday",
            "Development environment setup assigned to Bob Smith"
        ]
    
    def _get_good_action_items(self):
        """Get good quality action items for testing"""
        return [
            {
                "description": "Prepare technical requirements document",
                "assignee": "Bob Smith",
                "due_date": "2024-03-08",
                "priority": "high",
                "confidence": 0.9,
                "source_text": "Bob, can you also prepare the technical requirements document by Friday?"
            },
            {
                "description": "Set up development environment and project structure",
                "assignee": "Bob Smith",
                "due_date": "2024-03-10",
                "priority": "medium",
                "confidence": 0.85,
                "source_text": "I'll set up the development environment and create the initial project structure"
            },
            {
                "description": "Send calendar invites for sprint reviews",
                "assignee": "Bob Smith",
                "due_date": "2024-03-05",
                "priority": "medium",
                "confidence": 0.88,
                "source_text": "I'll send out calendar invites for the sprint reviews today"
            }
        ]
    
    def test_assess_good_quality_summary(self):
        """Test quality assessment of a good quality summary"""
        # Execute
        assessment = self.quality_service.assess_summary_quality(self.good_draft_summary)
        
        # Verify
        self.assertIsInstance(assessment, QualityAssessment)
        self.assertGreater(assessment.overall_confidence, 0.7)
        self.assertEqual(len(assessment.quality_scores), len(QualityMetric))
        self.assertLess(len(assessment.validation_errors), 3)
        
        # Check that all metrics were assessed
        assessed_metrics = {score.metric for score in assessment.quality_scores}
        self.assertEqual(assessed_metrics, set(QualityMetric))
        
        # Verify high-scoring metrics
        transcript_score = next(s for s in assessment.quality_scores if s.metric == QualityMetric.TRANSCRIPT_LENGTH)
        self.assertGreater(transcript_score.score, 0.8)
        
        action_item_score = next(s for s in assessment.quality_scores if s.metric == QualityMetric.ACTION_ITEM_CLARITY)
        self.assertGreater(action_item_score.score, 0.7)
    
    def test_assess_poor_quality_summary(self):
        """Test quality assessment of a poor quality summary"""
        # Execute
        assessment = self.quality_service.assess_summary_quality(self.poor_draft_summary)
        
        # Verify
        self.assertIsInstance(assessment, QualityAssessment)
        self.assertLess(assessment.overall_confidence, 0.5)
        self.assertGreater(len(assessment.validation_errors), 0)
        self.assertGreater(len(assessment.recommendations), 0)
        
        # Check for specific validation errors
        error_messages = ' '.join(assessment.validation_errors)
        self.assertIn("error indicators", error_messages.lower())
        
        # Verify low-scoring metrics
        transcript_score = next(s for s in assessment.quality_scores if s.metric == QualityMetric.TRANSCRIPT_LENGTH)
        self.assertLess(transcript_score.score, 0.5)
    
    def test_transcript_length_assessment(self):
        """Test transcript length quality assessment"""
        # Test with different transcript lengths
        test_cases = [
            ("", 0.2),  # Empty transcript
            ("Short transcript with few words.", 0.2),  # Very short
            (" ".join(["word"] * 100), 0.6),  # Adequate length
            (" ".join(["word"] * 500), 1.0),  # Excellent length
        ]
        
        for transcript, expected_min_score in test_cases:
            with self.subTest(transcript_length=len(transcript.split())):
                # Update transcript
                self.good_bot_session.raw_transcript = transcript
                self.good_bot_session.save()
                
                # Assess
                score = self.quality_service._assess_transcript_length(
                    self.good_draft_summary, 0.15
                )
                
                # Verify
                self.assertGreaterEqual(score.score, expected_min_score - 0.1)
                self.assertEqual(score.metric, QualityMetric.TRANSCRIPT_LENGTH)
    
    def test_summary_coherence_assessment(self):
        """Test summary coherence assessment"""
        # Test coherent summary
        coherent_summary = "The team discussed project requirements and made key decisions about technology stack."
        self.good_draft_summary.ai_generated_summary = coherent_summary
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_summary_coherence(self.good_draft_summary, 0.2)
        self.assertGreater(score.score, 0.6)
        
        # Test incoherent summary
        incoherent_summary = "Error failed null undefined."
        self.good_draft_summary.ai_generated_summary = incoherent_summary
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_summary_coherence(self.good_draft_summary, 0.2)
        self.assertLess(score.score, 0.5)
    
    def test_action_item_clarity_assessment(self):
        """Test action item clarity assessment"""
        # Test clear action items
        clear_items = [
            {
                "description": "Complete technical requirements document by Friday",
                "assignee": "John Doe",
                "confidence": 0.9
            }
        ]
        self.good_draft_summary.extracted_action_items = clear_items
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_action_item_clarity(self.good_draft_summary, 0.2)
        self.assertGreater(score.score, 0.8)
        
        # Test unclear action items
        unclear_items = [
            {
                "description": "Do something",
                "assignee": "",
                "confidence": 0.3
            }
        ]
        self.good_draft_summary.extracted_action_items = unclear_items
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_action_item_clarity(self.good_draft_summary, 0.2)
        self.assertLess(score.score, 0.5)
    
    def test_key_points_relevance_assessment(self):
        """Test key points relevance assessment"""
        # Test relevant key points
        relevant_points = [
            "Project timeline established for March delivery",
            "Technology stack decision: React and Node.js",
            "Weekly sprint reviews scheduled"
        ]
        self.good_draft_summary.key_points = relevant_points
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_key_points_relevance(self.good_draft_summary, 0.15)
        self.assertGreater(score.score, 0.7)
        
        # Test irrelevant key points
        irrelevant_points = ["Point", "Another point", "Third point"]
        self.good_draft_summary.key_points = irrelevant_points
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_key_points_relevance(self.good_draft_summary, 0.15)
        self.assertLess(score.score, 0.5)
    
    def test_speaker_identification_assessment(self):
        """Test speaker identification assessment"""
        # Test good speaker identification
        good_mapping = {
            "speaker_1": {"name": "Alice Johnson", "confidence": 0.9},
            "speaker_2": {"name": "Bob Smith", "confidence": 0.85}
        }
        self.good_bot_session.speaker_mapping = good_mapping
        self.good_bot_session.save()
        
        score = self.quality_service._assess_speaker_identification(self.good_draft_summary, 0.1)
        self.assertGreater(score.score, 0.7)
        
        # Test poor speaker identification
        poor_mapping = {
            "speaker_1": {"name": "Unknown Speaker", "confidence": 0.3}
        }
        self.good_bot_session.speaker_mapping = poor_mapping
        self.good_bot_session.save()
        
        score = self.quality_service._assess_speaker_identification(self.good_draft_summary, 0.1)
        self.assertLess(score.score, 0.5)
    
    def test_content_coverage_assessment(self):
        """Test content coverage assessment"""
        # Test good coverage
        transcript = "The team discussed project requirements, timeline, and technology decisions."
        summary = "Team discussed project requirements and timeline decisions."
        
        self.good_bot_session.raw_transcript = transcript
        self.good_bot_session.save()
        self.good_draft_summary.ai_generated_summary = summary
        self.good_draft_summary.save()
        
        score = self.quality_service._assess_content_coverage(self.good_draft_summary, 0.1)
        self.assertGreater(score.score, 0.5)
    
    def test_validation_errors_detection(self):
        """Test validation error detection"""
        # Test summary with validation errors
        self.poor_draft_summary.ai_generated_summary = ""  # Empty summary
        self.poor_draft_summary.key_points = []  # No key points
        self.poor_draft_summary.confidence_score = 1.5  # Invalid confidence
        self.poor_draft_summary.save()
        
        errors = self.quality_service._validate_summary_content(self.poor_draft_summary)
        
        # Verify errors are detected
        self.assertGreater(len(errors), 0)
        error_text = ' '.join(errors).lower()
        self.assertIn("too short", error_text)
        self.assertIn("no key points", error_text)
        self.assertIn("invalid", error_text)
    
    def test_overall_confidence_calculation(self):
        """Test overall confidence score calculation"""
        # Create mock quality scores
        quality_scores = [
            QualityScore(QualityMetric.TRANSCRIPT_LENGTH, 0.8, 0.15),
            QualityScore(QualityMetric.SUMMARY_COHERENCE, 0.9, 0.20),
            QualityScore(QualityMetric.ACTION_ITEM_CLARITY, 0.7, 0.20),
        ]
        
        # Test with no validation errors
        confidence = self.quality_service._calculate_overall_confidence(quality_scores, [])
        self.assertGreater(confidence, 0.7)
        
        # Test with validation errors
        validation_errors = ["Error 1", "Error 2"]
        confidence_with_errors = self.quality_service._calculate_overall_confidence(
            quality_scores, validation_errors
        )
        self.assertLess(confidence_with_errors, confidence)
    
    def test_custom_weights(self):
        """Test quality service with custom metric weights"""
        custom_weights = {
            QualityMetric.TRANSCRIPT_LENGTH: 0.5,  # Higher weight
            QualityMetric.SUMMARY_COHERENCE: 0.3,
            QualityMetric.ACTION_ITEM_CLARITY: 0.2,
        }
        
        custom_service = SummaryQualityService(custom_weights)
        assessment = custom_service.assess_summary_quality(self.good_draft_summary)
        
        # Verify custom weights are used
        transcript_score = next(s for s in assessment.quality_scores if s.metric == QualityMetric.TRANSCRIPT_LENGTH)
        self.assertEqual(transcript_score.weight, 0.5)


class ConfidenceUpdateTest(TestCase):
    """Test cases for confidence score updates"""
    
    def setUp(self):
        """Set up test data"""
        self.lead = Lead.objects.create(
            crm_id="CONF_TEST_LEAD",
            name="Confidence Test",
            email="conf@example.com",
            company="Conf Corp"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="conf_test_event",
            lead=self.lead,
            title="Confidence Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="conf_bot_session",
            platform="teams",
            join_time=timezone.now(),
            raw_transcript="Good quality transcript with sufficient content for testing confidence scoring.",
            speaker_mapping={"speaker_1": {"name": "Test Speaker", "confidence": 0.9}}
        )
        
        self.draft_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Test summary for confidence scoring validation.",
            key_points=["Test point 1", "Test point 2"],
            extracted_action_items=[
                {"description": "Test action", "assignee": "Test User", "confidence": 0.8}
            ],
            suggested_next_steps=["Test next step"],
            decisions_made=["Test decision"],
            confidence_score=0.5  # Initial score
        )
    
    def test_update_summary_confidence_score(self):
        """Test updating summary confidence score"""
        # Get initial confidence
        initial_confidence = self.draft_summary.confidence_score
        
        # Update confidence score
        new_confidence = update_summary_confidence_score(self.draft_summary)
        
        # Verify update
        self.assertIsInstance(new_confidence, float)
        self.assertGreaterEqual(new_confidence, 0.0)
        self.assertLessEqual(new_confidence, 1.0)
        
        # Verify database was updated
        self.draft_summary.refresh_from_db()
        self.assertEqual(self.draft_summary.confidence_score, new_confidence)


class CRMValidationTest(TestCase):
    """Test cases for CRM sync validation"""
    
    def setUp(self):
        """Set up test data"""
        self.lead = Lead.objects.create(
            crm_id="CRM_TEST_LEAD",
            name="CRM Test",
            email="crm@example.com",
            company="CRM Corp"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="crm_test_event",
            lead=self.lead,
            title="CRM Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1)
        )
        
        self.bot_session = CallBotSession.objects.create(
            meeting=self.meeting,
            bot_session_id="crm_bot_session",
            platform="zoom",
            join_time=timezone.now(),
            raw_transcript="CRM validation test transcript with adequate content.",
            speaker_mapping={}
        )
        
        # Good quality summary for CRM sync
        self.good_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="High quality summary suitable for CRM synchronization with detailed meeting outcomes.",
            key_points=["CRM point 1", "CRM point 2", "CRM point 3"],
            extracted_action_items=[
                {"description": "CRM action item", "assignee": "CRM User"}
            ],
            suggested_next_steps=["CRM next step"],
            decisions_made=["CRM decision"],
            confidence_score=0.85
        )
        
        # Poor quality summary
        self.poor_summary = DraftSummary.objects.create(
            bot_session=self.bot_session,
            ai_generated_summary="Short summary.",
            key_points=[],
            extracted_action_items=[],
            suggested_next_steps=[],
            decisions_made=[],
            confidence_score=0.3
        )
    
    def test_validate_good_summary_for_crm_sync(self):
        """Test validation of good quality summary for CRM sync"""
        # Test Salesforce validation
        is_ready, errors = validate_summary_for_crm_sync(self.good_summary, 'salesforce')
        self.assertTrue(is_ready)
        self.assertEqual(len(errors), 0)
        
        # Test HubSpot validation
        is_ready, errors = validate_summary_for_crm_sync(self.good_summary, 'hubspot')
        self.assertTrue(is_ready)
        self.assertEqual(len(errors), 0)
        
        # Test Creatio validation
        is_ready, errors = validate_summary_for_crm_sync(self.good_summary, 'creatio')
        self.assertTrue(is_ready)
        self.assertEqual(len(errors), 0)
    
    def test_validate_poor_summary_for_crm_sync(self):
        """Test validation of poor quality summary for CRM sync"""
        # Test with poor quality summary
        is_ready, errors = validate_summary_for_crm_sync(self.poor_summary, 'salesforce')
        self.assertFalse(is_ready)
        self.assertGreater(len(errors), 0)
        
        # Check for specific error types
        error_text = ' '.join(errors).lower()
        self.assertIn("confidence", error_text)
        self.assertIn("short", error_text)
    
    def test_validate_unknown_crm_system(self):
        """Test validation with unknown CRM system"""
        # This should still work as format_for_crm handles unknown systems
        is_ready, errors = validate_summary_for_crm_sync(self.good_summary, 'unknown_crm')
        # Should be ready since the summary is good quality
        self.assertTrue(is_ready)


if __name__ == '__main__':
    import unittest
    unittest.main()