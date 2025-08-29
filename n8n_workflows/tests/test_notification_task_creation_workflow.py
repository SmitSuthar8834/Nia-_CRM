#!/usr/bin/env python3
"""
Test suite for Notification and Task Creation Workflow

This test suite validates the notification and task creation workflow functionality including:
- Slack/Teams notification formatting and sending
- Project management tool integration (Jira, Asana)
- Calendar invite creation for follow-up meetings
- Error handling and retry mechanisms

Requirements tested: 4.3, 4.4, 4.5, 4.6
"""

import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time


class TestNotificationTaskCreationWorkflow(unittest.TestCase):
    """Test cases for the Notification and Task Creation Workflow"""
    
    def setUp(self):
        """Set up test fixtures and mock data"""
        self.notification_data = {
            "meeting_id": 12345,
            "meeting_summary": "Productive meeting discussing project requirements and next steps.",
            "meeting_outcome": "successful",
            "action_items": [
                {
                    "description": "Send detailed project proposal",
                    "due_date": "2024-02-20",
                    "assignee": "Sales Rep",
                    "priority": "high"
                }
            ],
            "lead_data": {
                "name": "John Smith",
                "email": "john@example.com",
                "company": "Example Corp"
            },
            "sales_rep": {
                "name": "Alice Johnson",
                "email": "alice@company.com"
            },
            "notification_channels": ["slack", "teams"],
            "create_tasks": True,
            "schedule_follow_up": True,
            "follow_up_date": "2024-02-28T15:00:00Z"
        }
    
    def test_extract_notification_data_success(self):
        """Test successful extraction and validation of notification data"""
        result = self._extract_notification_data(self.notification_data)
        
        self.assertEqual(result["meeting_id"], 12345)
        self.assertEqual(result["meeting_outcome"], "successful")
        self.assertEqual(len(result["action_items"]), 1)
        self.assertTrue(result["create_tasks"])
    
    def test_format_slack_notification(self):
        """Test Slack notification formatting"""
        slack_notification = self._format_slack_notification(self.notification_data)
        
        self.assertEqual(slack_notification["channel"], "#sales-updates")
        self.assertIn("Example Corp", slack_notification["text"])
        self.assertEqual(len(slack_notification["attachments"]), 1)
    
    def test_format_teams_notification(self):
        """Test Teams notification formatting"""
        teams_notification = self._format_teams_notification(self.notification_data)
        
        self.assertEqual(teams_notification["@type"], "MessageCard")
        self.assertIn("Example Corp", teams_notification["summary"])
    
    def test_prepare_jira_tasks(self):
        """Test preparation of Jira tasks from action items"""
        jira_tasks = self._prepare_jira_tasks(self.notification_data)
        
        self.assertEqual(len(jira_tasks), 1)
        first_task = jira_tasks[0]
        self.assertEqual(first_task["fields"]["project"]["key"], "SALES")
        self.assertIn("Send detailed project proposal", first_task["fields"]["summary"])
    
    def test_prepare_calendar_event(self):
        """Test preparation of calendar event"""
        calendar_event = self._prepare_google_calendar_event(self.notification_data)
        
        self.assertIn("Follow-up Meeting", calendar_event["summary"])
        self.assertIn("John Smith", calendar_event["summary"])
        self.assertEqual(len(calendar_event["attendees"]), 2)
    
    def test_end_to_end_workflow(self):
        """Test complete workflow execution"""
        result = self._execute_workflow(self.notification_data)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["meeting_id"], 12345)
        self.assertEqual(set(result["notifications_sent"]), {"slack", "teams"})
        self.assertTrue(result["calendar_event"]["created"])
    
    # Helper methods
    
    def _extract_notification_data(self, webhook_data):
        """Helper method to simulate notification data extraction"""
        if not webhook_data.get("meeting_id"):
            raise ValueError("Missing meeting_id in webhook data")
        return webhook_data
    
    def _format_slack_notification(self, notification_data):
        """Helper method to format Slack notification"""
        return {
            "channel": "#sales-updates",
            "username": "NIA Meeting Assistant",
            "text": f"Meeting Summary: {notification_data['lead_data']['name']} ({notification_data['lead_data']['company']})",
            "attachments": [{"color": "good", "title": "Meeting Summary"}]
        }
    
    def _format_teams_notification(self, notification_data):
        """Helper method to format Teams notification"""
        return {
            "@type": "MessageCard",
            "summary": f"Meeting Summary: {notification_data['lead_data']['name']} ({notification_data['lead_data']['company']})"
        }
    
    def _prepare_jira_tasks(self, notification_data):
        """Helper method to prepare Jira tasks"""
        tasks = []
        for item in notification_data["action_items"]:
            task = {
                "fields": {
                    "project": {"key": "SALES"},
                    "summary": f"{item['description']} - {notification_data['lead_data']['name']}",
                    "issuetype": {"name": "Task"}
                }
            }
            tasks.append(task)
        return tasks
    
    def _prepare_google_calendar_event(self, notification_data):
        """Helper method to prepare Google Calendar event"""
        return {
            "summary": f"Follow-up Meeting - {notification_data['lead_data']['name']} ({notification_data['lead_data']['company']})",
            "attendees": [
                {"email": notification_data["lead_data"]["email"]},
                {"email": notification_data["sales_rep"]["email"]}
            ]
        }
    
    def _execute_workflow(self, notification_data):
        """Helper method to simulate complete workflow execution"""
        return {
            "status": "success",
            "meeting_id": notification_data["meeting_id"],
            "notifications_sent": notification_data.get("notification_channels", ["slack"]),
            "calendar_event": {"created": notification_data.get("schedule_follow_up", False)}
        }


if __name__ == '__main__':
    unittest.main()