"""
Comprehensive tests for CRM suggestion service
"""
from django.test import TestCase
from datetime import datetime, timedelta
from meetings.crm_suggestion_service import CRMSuggestionService, CRMSystem, OpportunityStage


class TestCRMSuggestionService(TestCase):
    """Test cases for CRM suggestion service"""
    
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
    
    def test_generate_crm_suggestions_salesforce(self):
        """Test generating CRM suggestions for Salesforce"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        self.assertEqual(suggestions.crm_system, CRMSystem.SALESFORCE)
        self.assertGreater(suggestions.confidence_score, 0)
        self.assertGreater(len(suggestions.field_updates), 0)
        self.assertGreater(len(suggestions.follow_up_tasks), 0)
        self.assertGreater(len(suggestions.validation_notes), 0)
        
        # Check Salesforce-specific field mappings
        self.assertIn('Description', suggestions.field_updates)
    
    def test_generate_crm_suggestions_hubspot(self):
        """Test generating CRM suggestions for HubSpot"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.HUBSPOT
        )
        
        self.assertEqual(suggestions.crm_system, CRMSystem.HUBSPOT)
        
        # Check HubSpot-specific field mappings
        self.assertIn('hs_meeting_body', suggestions.field_updates)
    
    def test_generate_crm_suggestions_creatio(self):
        """Test generating CRM suggestions for Creatio"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.CREATIO
        )
        
        self.assertEqual(suggestions.crm_system, CRMSystem.CREATIO)
        
        # Check Creatio-specific field mappings
        self.assertIn('Notes', suggestions.field_updates)
    
    def test_opportunity_stage_suggestion_qualification(self):
        """Test opportunity stage suggestion for qualification stage"""
        summary_with_budget = """
        We discussed budget requirements and John confirmed they have $50k allocated.
        He mentioned he's the decision maker and we need to move quickly due to 
        their timeline constraints.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=summary_with_budget,
            action_items=[],
            key_points=["Budget confirmed", "Decision maker identified"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        if suggestions.opportunity_suggestion:
            self.assertEqual(suggestions.opportunity_suggestion.suggested_stage, OpportunityStage.QUALIFICATION)
            self.assertGreater(suggestions.opportunity_suggestion.confidence, 0.3)
            self.assertGreater(len(suggestions.opportunity_suggestion.supporting_evidence), 0)
    
    def test_opportunity_stage_suggestion_proposal(self):
        """Test opportunity stage suggestion for proposal stage"""
        summary_with_proposal = """
        Great meeting! We presented our solution and John was very interested.
        They want a detailed proposal with pricing options. We'll send the 
        proposal by end of week and schedule a demo.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=summary_with_proposal,
            action_items=[],
            key_points=["Interested in solution", "Requested proposal", "Want demo"],
            decisions_made=["Send proposal by Friday"],
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="qualification"
        )
        
        if suggestions.opportunity_suggestion:
            self.assertEqual(suggestions.opportunity_suggestion.suggested_stage, OpportunityStage.PROPOSAL)
    
    def test_follow_up_task_generation_from_action_items(self):
        """Test follow-up task generation from explicit action items"""
        action_items = [
            {
                "description": "Send proposal urgently by tomorrow",
                "assignee": "john.doe@company.com",
                "priority": "high"
            },
            {
                "description": "Schedule demo when possible",
                "assignee": "jane.smith@company.com",
                "priority": "low"
            }
        ]
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Brief meeting",
            action_items=action_items,
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Should have tasks from action items plus standard follow-up
        self.assertGreaterEqual(len(suggestions.follow_up_tasks), 2)
        
        # Check high priority task
        high_priority_tasks = [t for t in suggestions.follow_up_tasks if t.priority == 'high']
        self.assertGreaterEqual(len(high_priority_tasks), 1)
        
        # Check task with assignee
        assigned_tasks = [t for t in suggestions.follow_up_tasks if t.assignee]
        self.assertGreaterEqual(len(assigned_tasks), 1)
    
    def test_confidence_score_calculation(self):
        """Test confidence score calculation"""
        # High confidence scenario
        rich_suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        # Low confidence scenario
        minimal_suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Brief call",
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertGreaterEqual(rich_suggestions.confidence_score, minimal_suggestions.confidence_score)
        self.assertGreaterEqual(rich_suggestions.confidence_score, 0)
        self.assertLessEqual(rich_suggestions.confidence_score, 1)
        self.assertGreaterEqual(minimal_suggestions.confidence_score, 0)
        self.assertLessEqual(minimal_suggestions.confidence_score, 1)
    
    def test_validation_notes_generation(self):
        """Test validation notes generation"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        self.assertGreater(len(suggestions.validation_notes), 0)
        
        # Should always include review reminder
        review_notes = [note for note in suggestions.validation_notes 
                      if 'review' in note.lower()]
        self.assertGreater(len(review_notes), 0)
    
    def test_crm_system_enum_values(self):
        """Test CRM system enum values"""
        self.assertEqual(CRMSystem.SALESFORCE.value, "salesforce")
        self.assertEqual(CRMSystem.HUBSPOT.value, "hubspot")
        self.assertEqual(CRMSystem.CREATIO.value, "creatio")
    
    def test_opportunity_stage_enum_values(self):
        """Test opportunity stage enum values"""
        self.assertEqual(OpportunityStage.PROSPECTING.value, "prospecting")
        self.assertEqual(OpportunityStage.QUALIFICATION.value, "qualification")
        self.assertEqual(OpportunityStage.PROPOSAL.value, "proposal")
        self.assertEqual(OpportunityStage.CLOSED_WON.value, "closed_won") 
   
    def test_enhanced_field_mappings_salesforce(self):
        """Test enhanced field mappings for Salesforce"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        # Check field mappings structure
        self.assertGreater(len(suggestions.field_mappings), 0)
        
        # Verify field mapping properties
        for mapping in suggestions.field_mappings:
            self.assertIsInstance(mapping, CRMFieldMapping)
            self.assertIsInstance(mapping.field_name, str)
            self.assertIsInstance(mapping.confidence, float)
            self.assertGreaterEqual(mapping.confidence, 0)
            self.assertLessEqual(mapping.confidence, 1)
            self.assertIsInstance(mapping.source_evidence, list)
        
        # Check specific Salesforce fields
        field_names = [mapping.field_name for mapping in suggestions.field_mappings]
        self.assertIn('Description', field_names)
    
    def test_enhanced_field_mappings_hubspot(self):
        """Test enhanced field mappings for HubSpot"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.HUBSPOT
        )
        
        field_names = [mapping.field_name for mapping in suggestions.field_mappings]
        self.assertIn('hs_meeting_body', field_names)
    
    def test_enhanced_field_mappings_creatio(self):
        """Test enhanced field mappings for Creatio"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.CREATIO
        )
        
        field_names = [mapping.field_name for mapping in suggestions.field_mappings]
        self.assertIn('Notes', field_names)
    
    def test_opportunity_stage_suggestions_comprehensive(self):
        """Test comprehensive opportunity stage suggestions"""
        # Test prospecting stage
        prospecting_summary = """
        Initial call with new prospect. Introduced our company and services.
        They showed interest and want to learn more about our solutions.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=prospecting_summary,
            action_items=[],
            key_points=["First meeting", "Initial contact"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        if suggestions.opportunity_suggestion:
            self.assertEqual(suggestions.opportunity_suggestion.suggested_stage, OpportunityStage.PROSPECTING)
        
        # Test needs analysis stage
        needs_summary = """
        Conducted detailed requirements gathering session. Analyzed their current
        processes and identified key pain points. Need to do further assessment.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=needs_summary,
            action_items=[],
            key_points=["Requirements gathering", "Assessment needed"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        if suggestions.opportunity_suggestion:
            self.assertEqual(suggestions.opportunity_suggestion.suggested_stage, OpportunityStage.NEEDS_ANALYSIS)
    
    def test_follow_up_task_priority_detection(self):
        """Test follow-up task priority detection"""
        urgent_action_items = [
            {
                "description": "Send urgent proposal ASAP - client needs it immediately",
                "assignee": "sales_rep",
                "priority": "high"
            },
            {
                "description": "Schedule demo when possible next month",
                "assignee": "sales_rep",
                "priority": "low"
            }
        ]
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Meeting with urgent requirements",
            action_items=urgent_action_items,
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check that urgent task gets high priority
        urgent_tasks = [task for task in suggestions.follow_up_tasks 
                       if task.priority in [TaskPriority.URGENT, TaskPriority.HIGH]]
        self.assertGreater(len(urgent_tasks), 0)
        
        # Check task categorization
        sales_tasks = [task for task in suggestions.follow_up_tasks 
                      if task.crm_category == 'Sales']
        self.assertGreater(len(sales_tasks), 0)
    
    def test_reminder_suggestions_generation(self):
        """Test reminder suggestions generation"""
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
            key_points=["Contract needed"],
            decisions_made=["Send contract by tomorrow"],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check reminder suggestions exist
        self.assertGreater(len(suggestions.reminder_suggestions), 0)
        
        # Check reminder types
        reminder_types = [r.reminder_type for r in suggestions.reminder_suggestions]
        self.assertIn(ReminderType.EMAIL, reminder_types)
        
        # Check high priority reminders for urgent tasks
        high_priority_reminders = [r for r in suggestions.reminder_suggestions 
                                 if r.priority == TaskPriority.HIGH]
        self.assertGreater(len(high_priority_reminders), 0)
    
    def test_deal_value_extraction(self):
        """Test deal value extraction from meeting text"""
        value_summary = """
        Great meeting! They confirmed budget of $50,000 for this project.
        Also mentioned potential for additional 25k in next phase.
        """
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=value_summary,
            action_items=[],
            key_points=["Budget: $50k confirmed"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(suggestions.deal_value_estimate)
        self.assertEqual(suggestions.deal_value_estimate, 50000.0)
    
    def test_deal_value_extraction_k_format(self):
        """Test deal value extraction with 'k' format"""
        value_summary = "They have 75k budget allocated for this initiative."
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=value_summary,
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(suggestions.deal_value_estimate)
        self.assertEqual(suggestions.deal_value_estimate, 75000.0)
    
    def test_next_meeting_suggestion(self):
        """Test next meeting timing suggestions"""
        next_week_summary = "Great discussion. Let's schedule follow-up for next week."
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=next_week_summary,
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        self.assertIsNotNone(suggestions.suggested_next_meeting)
        
        # Should be approximately 7 days from now
        days_diff = (suggestions.suggested_next_meeting - datetime.now()).days
        self.assertGreaterEqual(days_diff, 6)
        self.assertLessEqual(days_diff, 8)
    
    def test_confidence_score_calculation(self):
        """Test confidence score calculation with different scenarios"""
        # High confidence scenario - rich data
        rich_suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting"
        )
        
        # Low confidence scenario - minimal data
        minimal_suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Brief call",
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Rich data should have higher confidence
        self.assertGreater(rich_suggestions.confidence_score, minimal_suggestions.confidence_score)
        
        # Both should be within valid range
        self.assertGreaterEqual(rich_suggestions.confidence_score, 0)
        self.assertLessEqual(rich_suggestions.confidence_score, 1)
        self.assertGreaterEqual(minimal_suggestions.confidence_score, 0)
        self.assertLessEqual(minimal_suggestions.confidence_score, 1)
    
    def test_validation_notes_comprehensive(self):
        """Test comprehensive validation notes generation"""
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE,
            current_opportunity_stage="prospecting",
            current_deal_value=25000.0
        )
        
        # Check validation notes exist and are informative
        self.assertGreater(len(suggestions.validation_notes), 0)
        
        # Should contain field mapping info
        field_notes = [note for note in suggestions.validation_notes 
                      if 'field' in note.lower()]
        self.assertGreater(len(field_notes), 0)
        
        # Should contain review reminder
        review_notes = [note for note in suggestions.validation_notes 
                       if 'review' in note.lower()]
        self.assertGreater(len(review_notes), 0)
    
    def test_task_categorization(self):
        """Test task categorization for CRM organization"""
        diverse_action_items = [
            {
                "description": "Send detailed proposal with pricing breakdown",
                "assignee": "sales_rep"
            },
            {
                "description": "Schedule technical demo with engineering team",
                "assignee": "sales_engineer"
            },
            {
                "description": "Review contract terms with legal department",
                "assignee": "legal_team"
            },
            {
                "description": "Set up integration meeting with IT team",
                "assignee": "technical_lead"
            }
        ]
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary="Comprehensive planning meeting",
            action_items=diverse_action_items,
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check that tasks are properly categorized
        categories = [task.crm_category for task in suggestions.follow_up_tasks if task.crm_category]
        
        self.assertIn('Sales', categories)
        self.assertIn('Meeting', categories)
        self.assertIn('Legal', categories)
        self.assertIn('Technical', categories)
    
    def test_meeting_outcome_determination(self):
        """Test meeting outcome determination"""
        # Test successful meeting
        successful_summary = "Very productive meeting with great progress made"
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=successful_summary,
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Check that outcome field is set
        outcome_mappings = [fm for fm in suggestions.field_mappings 
                           if 'outcome' in fm.field_name.lower() or 'Outcome' in fm.field_name]
        if outcome_mappings:
            self.assertEqual(outcome_mappings[0].field_value, 'COMPLETED')
    
    def test_standard_task_generation(self):
        """Test standard task generation based on meeting content"""
        proposal_summary = "Client requested detailed proposal with implementation timeline"
        
        suggestions = self.service.generate_crm_suggestions(
            meeting_summary=proposal_summary,
            action_items=[],
            key_points=["Proposal requested"],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Should generate proposal-related task
        proposal_tasks = [task for task in suggestions.follow_up_tasks 
                         if 'proposal' in task.description.lower()]
        self.assertGreater(len(proposal_tasks), 0)
        
        # Should have high priority for proposal task
        high_priority_tasks = [task for task in suggestions.follow_up_tasks 
                             if task.priority == TaskPriority.HIGH]
        self.assertGreater(len(high_priority_tasks), 0)
    
    def test_crm_system_specific_formatting(self):
        """Test CRM system specific field formatting"""
        suggestions_sf = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.SALESFORCE
        )
        
        suggestions_hs = self.service.generate_crm_suggestions(
            meeting_summary=self.sample_summary,
            action_items=self.sample_action_items,
            key_points=self.sample_key_points,
            decisions_made=self.sample_decisions,
            crm_system=CRMSystem.HUBSPOT
        )
        
        # Field names should be different for different CRMs
        sf_fields = set(suggestions_sf.field_updates.keys())
        hs_fields = set(suggestions_hs.field_updates.keys())
        
        # Should have different field names
        self.assertNotEqual(sf_fields, hs_fields)
        
        # But should have similar content structure
        self.assertEqual(len(sf_fields), len(hs_fields))
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        # Empty inputs
        empty_suggestions = self.service.generate_crm_suggestions(
            meeting_summary="",
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Should still return valid structure
        self.assertIsInstance(empty_suggestions.field_mappings, list)
        self.assertIsInstance(empty_suggestions.follow_up_tasks, list)
        self.assertIsInstance(empty_suggestions.confidence_score, float)
        
        # Very long inputs
        long_summary = "Very long meeting summary. " * 1000
        long_suggestions = self.service.generate_crm_suggestions(
            meeting_summary=long_summary,
            action_items=[],
            key_points=[],
            decisions_made=[],
            crm_system=CRMSystem.SALESFORCE
        )
        
        # Should handle gracefully
        self.assertIsNotNone(long_suggestions)
        self.assertGreater(len(long_suggestions.field_updates), 0)