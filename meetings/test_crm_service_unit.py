"""
Unit tests for CRM suggestion service (no database required)
"""
import unittest
from datetime import datetime, timedelta
from meetings.crm_suggestion_service import (
    CRMSuggestionService,
    CRMSystem,
    OpportunityStage,
    TaskPriority,
    ReminderType
)


class TestCRMSuggestionServiceUnit(unittest.TestCase):
    """Unit tests for CRM suggestion service"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.service = CRMSuggestionService()
        
        # Sample meeting data
        self.sample_summary = """
        Great meeting with John from Acme Corp. We discussed their current challenges 
        with inventory management and how our solution could help. They have a budget 
        of $50k and need to make a decision by end of Q1. John will check with his 
        team and get back to us next week. We agreed to send a detailed proposal.
        """
        
        self.sample_key_points = [
            "Budget confirmed at $50k",
            "Decision timeline: end of Q1",
            "Current pain point: inventory management",
            "Need proposal with detailed pricing"
        ]
        
        self.sample_decisions = [
            "Will send detailed proposal by Friday",
            "Schedule follow-up call for next week",
            "Include implementation timeline in proposal"
        ]
        
        self.sample_action_items = [
            {
                "description": "Send detailed proposal with pricing",
                "assignee": "sales_rep",
                "priority": "high"
            },
            {
                "description": "Schedule follow-up call",
                "assignee": "sales_rep",
                "priority": "medium"
            }
        ]
    
    def test_service_initialization(self):
        """Test service initialization"""
        self.assertIsInstance(self.service, CRMSuggestionService)
        self.assertIn(CRMSystem.SALESFORCE, self.service.field_mappings)
        self.assertIn(CRMSystem.HUBSPOT, self.service.field_mappings)
        self.assertIn(CRMSystem.CREATIO, self.service.field_mappings)
    
    def test_generate_crm_suggestions_basic(self):
        """Test basic CRM suggestion generation"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Basic structure checks
        self.assertEqual(suggestions.crm_system, CRMSystem.SALESFORCE)
        self.assertIsInstance(suggestions.field_updates, dict)
        self.assertIsInstance(suggestions.field_mappings, list)
        self.assertIsInstance(suggestions.follow_up_tasks, list)
        self.assertIsInstance(suggestions.reminder_suggestions, list)
        self.assertIsInstance(suggestions.confidence_score, float)
        self.assertIsInstance(suggestions.validation_notes, list)
        
        # Content checks
        self.assertGreater(len(suggestions.field_updates), 0)
        self.assertGreater(len(suggestions.follow_up_tasks), 0)
        self.assertGreaterEqual(suggestions.confidence_score, 0)
        self.assertLessEqual(suggestions.confidence_score, 1)
    
    def test_field_mappings_salesforce(self):
        """Test Salesforce field mappings"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check Salesforce-specific fields
        self.assertIn('Description', suggestions.field_updates)
        
        # Check field mappings structure
        for mapping in suggestions.field_mappings:
            self.assertIsInstance(mapping.field_name, str)
            self.assertIsInstance(mapping.confidence, float)
            self.assertGreaterEqual(mapping.confidence, 0)
            self.assertLessEqual(mapping.confidence, 1)
    
    def test_opportunity_stage_detection(self):
        """Test opportunity stage detection"""
        # Test qualification stage detection
        qualification_summary = """
        We discussed budget requirements and John confirmed they have $50k allocated.
        He mentioned he's the decision maker and we need to move quickly due to 
        their timeline constraints.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=qualification_summary,
            action_items=[],
            key_points=["Budget confirmed", "Decision maker identified"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        if suggestions.opportunity_suggestion:
            self.assertEqual(suggestions.opportunity_suggestion.suggested_stage, OpportunityStage.QUALIFICATION)
            self.assertGreater(suggestions.opportunity_suggestion.confidence, 0)
    
    def test_deal_value_extraction(self):
        """Test deal value extraction"""
        value_summary = "They confirmed budget of $75,000 for this project."
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=value_summary,
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(suggestions.deal_value_estimate)
        self.assertEqual(suggestions.deal_value_estimate, 75000.0)
    
    def test_task_priority_detection(self):
        """Test task priority detection"""
        urgent_items = [
            {
                "description": "Send urgent proposal ASAP - client needs it immediately",
                "assignee": "sales_rep"
            }
        ]
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Urgent meeting with tight deadline",
            action_items=urgent_items,
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check that urgent tasks are created
        high_priority_tasks = [
            task for task in suggestions.follow_up_tasks 
            if task.priority in [TaskPriority.HIGH, TaskPriority.URGENT]
        ]
        self.assertGreater(len(high_priority_tasks), 0)
    
    def test_reminder_generation(self):
        """Test reminder generation"""
        high_priority_items = [
            {
                "description": "Send contract urgently",
                "assignee": "john.doe@company.com",
                "priority": "high"
            }
        ]
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Important contract discussion",
            action_items=high_priority_items,
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check reminders are generated
        self.assertGreater(len(suggestions.reminder_suggestions), 0)
        
        # Check for email reminders for high priority items
        email_reminders = [
            r for r in suggestions.reminder_suggestions 
            if r.reminder_type == ReminderType.EMAIL
        ]
        self.assertGreater(len(email_reminders), 0)
    
    def test_different_crm_systems(self):
        """Test different CRM system handling"""
        systems = [CRMSystem.SALESFORCE, CRMSystem.HUBSPOT, CRMSystem.CREATIO]
        
        for crm_system in systems:
            suggestions = self.service.generate_crm_suggestions(
                meeting_summary=self.sample_summary,
                action_items=self.sample_action_items,
                key_points=self.sample_key_points,
                decisions_made=self.sample_decisions,
                crm_system=crm_system
            )
            
            self.assertEqual(suggestions.crm_system, crm_system)
            self.assertGreater(len(suggestions.field_updates), 0)
    
    def test_confidence_score_calculation(self):
        """Test confidence score calculation"""
        # Rich data scenario
        rich_suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Minimal data scenario
        minimal_suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Brief call",
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Rich data should have higher confidence
        self.assertGreater(rich_suggestions.confidence_score, minimal_suggestions.confidence_score)
    
    def test_validation_notes(self):
        """Test validation notes generation"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertGreater(len(suggestions.validation_notes), 0)
        
        # Should contain review reminder
        review_notes = [
            note for note in suggestions.validation_notes 
            if 'review' in note.lower()
        ]
        self.assertGreater(len(review_notes), 0)


if __name__ == '__main__':
    unittest.main()