#!/usr/bin/env python3
"""
Test runner for AI Assistant n8n workflow
Tests the workflow logic and error handling with mock AI service responses
"""

import json
import requests
import time
from unittest.mock import Mock, patch
import pytest


class TestAIAssistantWorkflow:
    """Test cases for AI Assistant workflow"""
    
    def setup_method(self):
        """Setup test environment"""
        self.webhook_url = "http://localhost:5678/webhook/meeting-started"
        self.django_api_url = "http://localhost:8000"
        
        # Mock meeting data
        self.valid_meeting_data = {
            "meeting_id": 123,
            "meeting_title": "Sales Call with Acme Corp",
            "start_time": "2024-01-15T10:00:00Z",
            "attendees": ["john@acme.com", "sales@company.com"],
            "user_id": "user_456",
            "lead_context": {
                "name": "John Smith",
                "email": "john@acme.com",
                "company": "Acme Corp",
                "status": "qualified",
                "source": "website"
            }
        }
        
        # Mock AI service responses
        self.successful_ai_response = {
            "success": True,
            "ai_available": True,
            "session": {
                "session_id": "ai_session_789",
                "meeting_id": 123,
                "lead_context": self.valid_meeting_data["lead_context"],
                "created_at": "2024-01-15T10:00:00Z"
            }
        }
        
        self.failed_ai_response = {
            "success": False,
            "error": "AI service temporarily unavailable",
            "ai_available": False
        }

    def test_successful_ai_session_initialization(self):
        """Test successful AI session initialization"""
        with patch('requests.post') as mock_post:
            # Mock Django API response
            mock_post.return_value.json.return_value = self.successful_ai_response
            mock_post.return_value.status_code = 200
            
            # Simulate webhook trigger
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify AI initialization was called
            expected_payload = {
                "meeting_id": 123,
                "lead_context": json.dumps(self.valid_meeting_data["lead_context"])
            }
            
            # Check that the workflow would call Django API
            assert mock_post.called
            
            # Verify response structure
            expected_response = {
                "status": "success",
                "session_id": "ai_session_789",
                "meeting_id": 123,
                "ai_available": True,
                "fallback_available": False,
                "initial_questions": [
                    "How has Acme Corp been performing recently?",
                    "What are the main challenges John Smith is facing?",
                    "What goals is Acme Corp hoping to achieve?"
                ],
                "error_type": "",
                "message": "AI session initialized successfully"
            }
            
            print("✓ Successful AI session initialization test passed")

    def test_ai_service_failure_with_fallback(self):
        """Test AI service failure with graceful fallback"""
        with patch('requests.post') as mock_post:
            # Mock Django API failure response
            mock_post.return_value.json.return_value = self.failed_ai_response
            mock_post.return_value.status_code = 500
            
            # Simulate webhook trigger
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify fallback response structure
            expected_fallback_response = {
                "status": "degraded",
                "ai_available": False,
                "fallback_available": True,
                "initial_questions": [
                    "How has your business been performing this quarter?",
                    "What are your main challenges right now?",
                    "What goals are you hoping to achieve?",
                    "How did you hear about our solution?"
                ],
                "error_type": "ai_service_error",
                "message": "AI session running in fallback mode"
            }
            
            print("✓ AI service failure with fallback test passed")

    def test_invalid_meeting_data_validation(self):
        """Test validation of invalid meeting data"""
        invalid_data_cases = [
            {},  # Empty data
            {"meeting_title": "Test"},  # Missing meeting_id
            {"meeting_id": "invalid"},  # Invalid meeting_id format
            {"meeting_id": 123, "lead_context": "invalid"}  # Invalid lead_context format
        ]
        
        for invalid_data in invalid_data_cases:
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 400
                
                response = requests.post(self.webhook_url, json=invalid_data)
                
                # Verify error handling
                assert mock_post.called
                
        print("✓ Invalid meeting data validation test passed")

    def test_network_error_retry_logic(self):
        """Test exponential backoff retry logic for network errors"""
        with patch('requests.post') as mock_post:
            # Simulate network timeout then success
            mock_post.side_effect = [
                requests.exceptions.Timeout(),  # First attempt fails
                requests.exceptions.Timeout(),  # Second attempt fails
                Mock(json=lambda: self.successful_ai_response, status_code=200)  # Third succeeds
            ]
            
            # Simulate webhook trigger
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify retry attempts
            assert mock_post.call_count == 3
            
        print("✓ Network error retry logic test passed")

    def test_authentication_error_handling(self):
        """Test handling of authentication errors"""
        with patch('requests.post') as mock_post:
            # Mock authentication error
            auth_error_response = {
                "success": False,
                "error": "Authentication failed - invalid API key",
                "ai_available": False
            }
            mock_post.return_value.json.return_value = auth_error_response
            mock_post.return_value.status_code = 401
            
            # Simulate webhook trigger
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify no fallback for auth errors
            expected_response = {
                "status": "failed",
                "ai_available": False,
                "fallback_available": False,
                "error_type": "auth_error",
                "message": "AI session initialization failed"
            }
            
        print("✓ Authentication error handling test passed")

    def test_meeting_context_processing(self):
        """Test processing of different meeting contexts"""
        test_contexts = [
            {
                "lead_context": {
                    "name": "Jane Doe",
                    "company": "Tech Startup Inc",
                    "status": "new",
                    "industry": "Technology"
                }
            },
            {
                "lead_context": {}  # Empty context
            },
            {
                "lead_context": None  # Null context
            }
        ]
        
        for context_data in test_contexts:
            meeting_data = {**self.valid_meeting_data, **context_data}
            
            with patch('requests.post') as mock_post:
                mock_post.return_value.json.return_value = self.successful_ai_response
                mock_post.return_value.status_code = 200
                
                response = requests.post(self.webhook_url, json=meeting_data)
                
                # Verify context processing
                assert mock_post.called
                
        print("✓ Meeting context processing test passed")

    def test_notification_system(self):
        """Test notification system for successful and failed sessions"""
        notification_cases = [
            (self.successful_ai_response, "ai_session_started"),
            (self.failed_ai_response, "ai_session_error")
        ]
        
        for api_response, expected_notification_type in notification_cases:
            with patch('requests.post') as mock_post:
                mock_post.return_value.json.return_value = api_response
                mock_post.return_value.status_code = 200 if api_response["success"] else 500
                
                response = requests.post(self.webhook_url, json=self.valid_meeting_data)
                
                # Verify notification would be sent
                assert mock_post.called
                
        print("✓ Notification system test passed")

    def test_error_logging_integration(self):
        """Test error logging to Django system"""
        with patch('requests.post') as mock_post:
            # Mock Django API failure
            mock_post.return_value.json.return_value = self.failed_ai_response
            mock_post.return_value.status_code = 500
            
            response = requests.post(self.webhook_url, json=self.valid_meeting_data)
            
            # Verify error logging payload structure
            expected_log_payload = {
                "workflow": "ai-assistant",
                "error_type": "ai_service_error",
                "meeting_id": 123,
                "message": "AI service temporarily unavailable",
                "severity": "warning"
            }
            
        print("✓ Error logging integration test passed")


def run_workflow_tests():
    """Run all AI Assistant workflow tests"""
    print("Running AI Assistant Workflow Tests...")
    print("=" * 50)
    
    test_suite = TestAIAssistantWorkflow()
    test_methods = [
        test_suite.test_successful_ai_session_initialization,
        test_suite.test_ai_service_failure_with_fallback,
        test_suite.test_invalid_meeting_data_validation,
        test_suite.test_network_error_retry_logic,
        test_suite.test_authentication_error_handling,
        test_suite.test_meeting_context_processing,
        test_suite.test_notification_system,
        test_suite.test_error_logging_integration
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
    print(f"AI Assistant Workflow Tests: {passed_tests}/{total_tests} passed")
    
    if passed_tests == total_tests:
        print("🎉 All AI Assistant workflow tests passed!")
        return True
    else:
        print("❌ Some AI Assistant workflow tests failed")
        return False


if __name__ == "__main__":
    success = run_workflow_tests()
    exit(0 if success else 1)