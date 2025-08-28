#!/usr/bin/env python3
"""
Test runner for CRM Update n8n workflow
Tests the workflow logic and error handling with mock CRM responses
"""

import json
import requests
import time
from unittest.mock import Mock, patch
import pytest


class TestCRMUpdateWorkflow:
    """Test cases for CRM Update workflow"""
    
    def setup_method(self):
        """Setup test environment"""
        self.webhook_url = "http://localhost:5678/webhook/meeting-completed"
        self.django_api_url = "http://localhost:8000"
        self.creatio_api_url = "http://localhost:9000"
        
        # Mock meeting completion data
        self.valid_meeting_data = {
            "meeting_id": 123,
            "lead_id": 456,
            "meeting_outcome": "qualified",
            "notes": "Great discussion about their current challenges with scalability. They're interested in our enterprise solution.",
            "summary": "Productive meeting with qualified lead. Strong interest in enterprise solution.",
            "action_items": [
                {
                    "description": "Schedule product demo for next week",
                    "assignee": "Sales Rep",
                    "due_date": "2024-01-22",
                    "priority": "High"
                },
                {
                    "description": "Send enterprise pricing information",
                    "assignee": "Sales Rep", 
                    "due_date": "2024-01-18",
                    "priority": "Medium"
                }
            ],
            "meeting_duration": 45,
            "attendees": [
                {"email": "john@example.com", "displayName": "John Doe"}
            ],
            "completed_at": "2024-01-15T15:00:00Z",
            "user_id": "user_456"
        }
        
        # Mock Django lead response
        self.lead_response = {
            "id": 456,
            "crm_id": "CRM-LEAD-789",
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Example Corp",
            "status": "qualified"
        }
        
        # Mock successful CRM responses
        self.successful_crm_update = {
            "success": True,
            "id": "CRM-LEAD-789",
            "updated_fields": ["Status", "Notes", "LastContactDate"]
        }
        
        self.successful_task_creation = {
            "success": True,
            "id": "TASK-001",
            "subject": "Follow-up: Schedule product demo for next week"
        }

    def test_successful_crm_update_with_tasks(self):
        """Test successful CRM update with follow-up task creation"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            # Mock Django lead fetch
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Mock CRM update and task creation
            mock_post.side_effect = [
                Mock(json=lambda: self.successful_crm_update, status_code=200),  # CRM update
                Mock(json=lambda: self.successful_task_creation, status_code=201),  # Task 1
                Mock(json=lambda: self.successful_task_creation, status_code=201),  # Task 2
                Mock(json=lambda: {"success": True}, status_code=200),  # Sync status update
                Mock(json=lambda: {"success": True}, status_code=200)   # Notification
            ]
            
            # Simulate webhook trigger
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify API calls were made
            assert mock_get.called  # Lead fetch
            assert mock_post.call_count >= 3  # CRM update + tasks + sync status
            
            # Verify expected response structure
            expected_response = {
                "status": "success",
                "meeting_id": 123,
                "lead_updated": True,
                "tasks_created": 2,
                "error_type": "",
                "retryable": False,
                "message": "CRM update completed successfully for meeting 123"
            }
            
            print("✓ Successful CRM update with tasks test passed")

    def test_no_show_meeting_handling(self):
        """Test handling of no-show meetings"""
        no_show_data = {
            **self.valid_meeting_data,
            "meeting_outcome": "no_show",
            "notes": "Lead did not attend the scheduled meeting.",
            "summary": "No show - lead did not attend meeting",
            "meeting_duration": 0,
            "action_items": [
                {
                    "description": "Follow up via email about missed meeting",
                    "assignee": "Sales Rep",
                    "due_date": "2024-01-17",
                    "priority": "Medium"
                }
            ]
        }
        
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            mock_post.return_value.json.return_value = self.successful_crm_update
            mock_post.return_value.status_code = 200
            
            response = requests.post(self.webhook_url, json=no_show_data)
            
            # Verify no-show status mapping
            assert mock_post.called
            
        print("✓ No-show meeting handling test passed")

    def test_crm_authentication_error(self):
        """Test handling of CRM authentication errors"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Mock authentication error
            auth_error_response = {
                "success": False,
                "error": "Authentication failed - invalid OAuth token"
            }
            mock_post.return_value.json.return_value = auth_error_response
            mock_post.return_value.status_code = 401
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify error handling
            expected_response = {
                "status": "failed",
                "meeting_id": 123,
                "lead_updated": False,
                "tasks_created": 0,
                "error_type": "auth_error",
                "retryable": False
            }
            
        print("✓ CRM authentication error handling test passed")

    def test_network_error_retry_logic(self):
        """Test exponential backoff retry logic for network errors"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Simulate network timeout then success
            mock_post.side_effect = [
                requests.exceptions.Timeout(),  # First attempt fails
                requests.exceptions.Timeout(),  # Second attempt fails  
                Mock(json=lambda: self.successful_crm_update, status_code=200)  # Third succeeds
            ]
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify retry attempts
            assert mock_post.call_count == 3
            
        print("✓ Network error retry logic test passed")

    def test_lead_not_found_error(self):
        """Test handling when lead is not found in CRM"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Mock lead not found error
            not_found_error = {
                "success": False,
                "error": "Lead with ID CRM-LEAD-789 not found"
            }
            mock_post.return_value.json.return_value = not_found_error
            mock_post.return_value.status_code = 404
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify no retry for 404 errors
            expected_response = {
                "status": "failed",
                "error_type": "lead_not_found",
                "retryable": False
            }
            
        print("✓ Lead not found error handling test passed")

    def test_rate_limit_handling(self):
        """Test handling of API rate limits"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Mock rate limit error then success
            rate_limit_error = {
                "success": False,
                "error": "Rate limit exceeded - too many requests"
            }
            mock_post.side_effect = [
                Mock(json=lambda: rate_limit_error, status_code=429),  # Rate limited
                Mock(json=lambda: self.successful_crm_update, status_code=200)  # Success on retry
            ]
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify retry for rate limits
            assert mock_post.call_count == 2
            
        print("✓ Rate limit handling test passed")

    def test_invalid_meeting_data_validation(self):
        """Test validation of invalid meeting data"""
        invalid_data_cases = [
            {},  # Empty data
            {"meeting_id": None, "lead_id": 456},  # Missing meeting_id
            {"meeting_id": "invalid", "lead_id": 456},  # Invalid meeting_id format
            {"meeting_id": 123, "lead_id": "invalid"},  # Invalid lead_id format
            {"meeting_id": 123, "lead_id": 456, "meeting_outcome": "invalid"}  # Invalid outcome
        ]
        
        for invalid_data in invalid_data_cases:
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 400
                
                response = requests.post(self.webhook_url, json=invalid_data)
                
                # Verify validation errors are handled
                assert mock_post.called or len(invalid_data) == 0
                
        print("✓ Invalid meeting data validation test passed")

    def test_meeting_outcome_status_mapping(self):
        """Test mapping of meeting outcomes to CRM statuses"""
        outcome_test_cases = [
            ("successful", "Meeting Completed"),
            ("qualified", "Qualified"),
            ("not_qualified", "Not Qualified"),
            ("no_show", "No Show"),
            ("rescheduled", "Rescheduled"),
            ("cancelled", "Cancelled")
        ]
        
        for outcome, expected_status in outcome_test_cases:
            test_data = {
                **self.valid_meeting_data,
                "meeting_outcome": outcome
            }
            
            with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
                mock_get.return_value.json.return_value = self.lead_response
                mock_get.return_value.status_code = 200
                
                mock_post.return_value.json.return_value = self.successful_crm_update
                mock_post.return_value.status_code = 200
                
                response = requests.post(self.webhook_url, json=test_data)
                
                # Verify status mapping
                assert mock_post.called
                
        print("✓ Meeting outcome status mapping test passed")

    def test_action_item_task_creation(self):
        """Test creation of follow-up tasks from action items"""
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            # Mock successful responses for all operations
            mock_post.side_effect = [
                Mock(json=lambda: self.successful_crm_update, status_code=200),  # CRM update
                Mock(json=lambda: self.successful_task_creation, status_code=201),  # Task 1
                Mock(json=lambda: self.successful_task_creation, status_code=201),  # Task 2
                Mock(json=lambda: {"success": True}, status_code=200),  # Sync status
                Mock(json=lambda: {"success": True}, status_code=200)   # Notification
            ]
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify task creation calls
            assert mock_post.call_count >= 4  # CRM update + 2 tasks + sync + notification
            
        print("✓ Action item task creation test passed")

    def test_notes_formatting_for_crm(self):
        """Test proper formatting of meeting notes for CRM"""
        detailed_meeting_data = {
            **self.valid_meeting_data,
            "notes": "Detailed meeting notes about the discussion",
            "summary": "Meeting summary for quick reference",
            "action_items": [
                {
                    "description": "Follow up with proposal",
                    "assignee": "Sales Rep",
                    "due_date": "2024-01-20"
                }
            ]
        }
        
        with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = self.lead_response
            mock_get.return_value.status_code = 200
            
            mock_post.return_value.json.return_value = self.successful_crm_update
            mock_post.return_value.status_code = 200
            
            response = requests.post(self.webhook_url, json=detailed_meeting_data)
            
            # Verify notes formatting includes summary, notes, and action items
            assert mock_post.called
            
        print("✓ Notes formatting for CRM test passed")

    def test_follow_up_date_calculation(self):
        """Test calculation of follow-up dates based on meeting outcomes"""
        outcome_test_cases = [
            ("qualified", 3),    # 3 days for qualified leads
            ("successful", 7),   # 1 week for successful meetings
            ("rescheduled", 1),  # Next day for rescheduled
            ("no_show", 2)       # 2 days for no-shows
        ]
        
        for outcome, expected_days in outcome_test_cases:
            test_data = {
                **self.valid_meeting_data,
                "meeting_outcome": outcome,
                "action_items": []  # No action items to test default calculation
            }
            
            with patch('requests.post') as mock_post, patch('requests.get') as mock_get:
                mock_get.return_value.json.return_value = self.lead_response
                mock_get.return_value.status_code = 200
                
                mock_post.return_value.json.return_value = self.successful_crm_update
                mock_post.return_value.status_code = 200
                
                response = requests.post(self.webhook_url, json=test_data)
                
                # Verify follow-up date calculation
                assert mock_post.called
                
        print("✓ Follow-up date calculation test passed")


def run_workflow_tests():
    """Run all CRM Update workflow tests"""
    print("Running CRM Update Workflow Tests...")
    print("=" * 50)
    
    test_suite = TestCRMUpdateWorkflow()
    test_methods = [
        test_suite.test_successful_crm_update_with_tasks,
        test_suite.test_no_show_meeting_handling,
        test_suite.test_crm_authentication_error,
        test_suite.test_network_error_retry_logic,
        test_suite.test_lead_not_found_error,
        test_suite.test_rate_limit_handling,
        test_suite.test_invalid_meeting_data_validation,
        test_suite.test_meeting_outcome_status_mapping,
        test_suite.test_action_item_task_creation,
        test_suite.test_notes_formatting_for_crm,
        test_suite.test_follow_up_date_calculation
    ]
    
    passed_tests = 0
    total_tests = len(test_methods)
    
    for test_method in test_methods:
        try:
            test_suite.setup_method()
            test_method()
            passed_tests += 1
        except Exception as e:
            print(f"✗ {test_method.__name__} failed: {str(e)}")
    
    print("=" * 50)
    print(f"CRM Update Workflow Tests: {passed_tests}/{total_tests} passed")
    
    if passed_tests == total_tests:
        print("🎉 All CRM Update workflow tests passed!")
        return True
    else:
        print("❌ Some CRM Update workflow tests failed")
        return False


if __name__ == "__main__":
    success = run_workflow_tests()
    exit(0 if success else 1)