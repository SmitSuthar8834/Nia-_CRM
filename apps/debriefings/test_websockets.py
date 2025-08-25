"""
WebSocket integration tests for debriefing conversations
"""
import json
import asyncio
from datetime import datetime, timedelta
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from .models import DebriefingSession, DebriefingQuestion, DebriefingTemplate
from .consumers import DebriefingConsumer, DebriefingNotificationConsumer
from apps.meetings.models import Meeting, MeetingParticipant
from apps.accounts.models import UserProfile


class DebriefingWebSocketTestCase(TransactionTestCase):
    """
    Base test case for debriefing WebSocket tests
    """
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create user profile
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            role='sales_rep'
        )
        
        # Create test meeting
        self.meeting = Meeting.objects.create(
            title='Test Sales Meeting',
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            meeting_type='discovery',
            is_sales_meeting=True,
            organizer=self.user,
            duration_minutes=30
        )
        
        # Create meeting participant
        self.participant = MeetingParticipant.objects.create(
            meeting=self.meeting,
            email='prospect@example.com',
            name='John Prospect',
            company='Prospect Corp',
            is_external=True
        )
        
        # Create debriefing session
        self.session = DebriefingSession.objects.create(
            meeting=self.meeting,
            user=self.user,
            scheduled_time=timezone.now(),
            status='scheduled'
        )
        
        # Create test template
        self.template = DebriefingTemplate.objects.create(
            name='Test Template',
            template_type='discovery',
            created_by=self.user,
            question_templates=[
                {
                    'question_text': 'How did the meeting go overall?',
                    'question_type': 'outcome',
                    'question_order': 1
                },
                {
                    'question_text': 'What were the key topics discussed?',
                    'question_type': 'topics',
                    'question_order': 2
                }
            ]
        )


class DebriefingConsumerTests(DebriefingWebSocketTestCase):
    """
    Tests for DebriefingConsumer WebSocket functionality
    """
    
    async def test_websocket_connection_success(self):
        """Test successful WebSocket connection"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive session state
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'session_state')
        self.assertIn('session_id', response['state'])
        
        await communicator.disconnect()
    
    async def test_websocket_connection_unauthorized(self):
        """Test WebSocket connection with unauthorized user"""
        from django.contrib.auth.models import AnonymousUser
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = AnonymousUser()
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_websocket_connection_invalid_session(self):
        """Test WebSocket connection with invalid session ID"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            "/ws/debriefing/invalid-session-id/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_session_initialization(self):
        """Test session initialization and first question"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip session state message
        await communicator.receive_json_from()
        
        # Should receive first question
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'question')
        self.assertIn('question_text', response)
        self.assertIn('question_id', response)
        
        # Verify session status changed to in_progress
        await database_sync_to_async(self.session.refresh_from_db)()
        self.assertEqual(self.session.status, 'in_progress')
        
        await communicator.disconnect()
    
    async def test_user_response_processing(self):
        """Test processing user response to question"""
        # Create a question first
        question = await database_sync_to_async(DebriefingQuestion.objects.create)(
            session=self.session,
            question_text='How did the meeting go?',
            question_type='outcome',
            question_order=1
        )
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send user response
        await communicator.send_json_to({
            'type': 'response',
            'question_id': str(question.id),
            'response': 'The meeting went very well. We discussed their requirements and they seem interested.'
        })
        
        # Should receive processing message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'processing')
        
        # Should receive next question or completion
        response = await communicator.receive_json_from()
        self.assertIn(response['type'], ['question', 'conversation_complete'])
        
        # Verify response was saved
        await database_sync_to_async(question.refresh_from_db)()
        self.assertIsNotNone(question.user_response)
        self.assertTrue(question.processed)
        
        await communicator.disconnect()
    
    async def test_skip_question(self):
        """Test skipping a question"""
        question = await database_sync_to_async(DebriefingQuestion.objects.create)(
            session=self.session,
            question_text='What was discussed about budget?',
            question_type='budget',
            question_order=1
        )
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send skip request
        await communicator.send_json_to({
            'type': 'skip_question',
            'question_id': str(question.id),
            'reason': 'not_applicable'
        })
        
        # Should receive next question or completion
        response = await communicator.receive_json_from()
        self.assertIn(response['type'], ['question', 'conversation_complete'])
        
        # Verify question was marked as skipped
        await database_sync_to_async(question.refresh_from_db)()
        self.assertTrue(question.user_response.startswith('[SKIPPED:'))
        
        await communicator.disconnect()
    
    async def test_clarification_request(self):
        """Test requesting clarification for a question"""
        question = await database_sync_to_async(DebriefingQuestion.objects.create)(
            session=self.session,
            question_text='What was the customer sentiment?',
            question_type='sentiment',
            question_order=1
        )
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send clarification request
        await communicator.send_json_to({
            'type': 'request_clarification',
            'question_id': str(question.id),
            'clarification_type': 'general'
        })
        
        # Should receive clarification
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'clarification')
        self.assertEqual(response['question_id'], str(question.id))
        self.assertIn('clarification', response)
        
        await communicator.disconnect()
    
    async def test_session_completion(self):
        """Test manual session completion"""
        # Set session to in_progress
        await database_sync_to_async(lambda: setattr(self.session, 'status', 'in_progress'))()
        await database_sync_to_async(self.session.save)()
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send completion request
        await communicator.send_json_to({
            'type': 'complete_session'
        })
        
        # Should receive completion confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'session_completed')
        
        # Verify session status
        await database_sync_to_async(self.session.refresh_from_db)()
        self.assertEqual(self.session.status, 'completed')
        
        await communicator.disconnect()
    
    async def test_heartbeat_mechanism(self):
        """Test WebSocket heartbeat mechanism"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send heartbeat
        await communicator.send_json_to({
            'type': 'heartbeat'
        })
        
        # Should receive heartbeat acknowledgment
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'heartbeat_ack')
        self.assertIn('timestamp', response)
        
        await communicator.disconnect()
    
    async def test_session_timeout_handling(self):
        """Test session timeout handling"""
        # This test would require mocking time or using a shorter timeout
        # For now, we'll test the timeout detection logic
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Simulate timeout by waiting for heartbeat
        try:
            # Wait for heartbeat (should come within 30 seconds)
            response = await asyncio.wait_for(
                communicator.receive_json_from(), 
                timeout=35
            )
            self.assertEqual(response['type'], 'heartbeat')
        except asyncio.TimeoutError:
            self.fail("Heartbeat not received within expected time")
        
        await communicator.disconnect()
    
    async def test_error_handling(self):
        """Test error handling in WebSocket communication"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send invalid message
        await communicator.send_json_to({
            'type': 'invalid_message_type'
        })
        
        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('error', response)
        
        await communicator.disconnect()
    
    async def test_concurrent_connections(self):
        """Test multiple concurrent connections to same session"""
        # Create two communicators for the same session
        communicator1 = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator1.scope['user'] = self.user
        
        communicator2 = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator2.scope['user'] = self.user
        
        # Connect both
        connected1, _ = await communicator1.connect()
        connected2, _ = await communicator2.connect()
        
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        
        # Both should receive session state
        await communicator1.receive_json_from()
        await communicator2.receive_json_from()
        
        # Disconnect both
        await communicator1.disconnect()
        await communicator2.disconnect()


class DebriefingNotificationConsumerTests(DebriefingWebSocketTestCase):
    """
    Tests for DebriefingNotificationConsumer
    """
    
    async def test_notification_connection(self):
        """Test notification WebSocket connection"""
        communicator = WebsocketCommunicator(
            DebriefingNotificationConsumer.as_asgi(),
            "/ws/debriefing/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()
    
    async def test_notification_unauthorized(self):
        """Test notification connection with unauthorized user"""
        from django.contrib.auth.models import AnonymousUser
        
        communicator = WebsocketCommunicator(
            DebriefingNotificationConsumer.as_asgi(),
            "/ws/debriefing/notifications/"
        )
        communicator.scope['user'] = AnonymousUser()
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    async def test_debriefing_reminder_notification(self):
        """Test debriefing reminder notification"""
        communicator = WebsocketCommunicator(
            DebriefingNotificationConsumer.as_asgi(),
            "/ws/debriefing/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Simulate sending a reminder notification
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        await channel_layer.group_send(
            f"debriefing_notifications_{self.user.id}",
            {
                'type': 'debriefing_reminder',
                'session_id': str(self.session.id),
                'meeting_title': self.meeting.title,
                'scheduled_time': self.session.scheduled_time.isoformat(),
                'message': 'Your debriefing is ready'
            }
        )
        
        # Should receive the notification
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'debriefing_reminder')
        self.assertEqual(response['session_id'], str(self.session.id))
        self.assertEqual(response['meeting_title'], self.meeting.title)
        
        await communicator.disconnect()


class WebSocketIntegrationTests(DebriefingWebSocketTestCase):
    """
    Integration tests for complete WebSocket workflows
    """
    
    async def test_complete_debriefing_workflow(self):
        """Test complete debriefing workflow through WebSocket"""
        # Create questions
        questions = [
            await database_sync_to_async(DebriefingQuestion.objects.create)(
                session=self.session,
                question_text='How did the meeting go overall?',
                question_type='outcome',
                question_order=1
            ),
            await database_sync_to_async(DebriefingQuestion.objects.create)(
                session=self.session,
                question_text='What were the main topics discussed?',
                question_type='topics',
                question_order=2
            )
        ]
        
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip session state
        await communicator.receive_json_from()
        
        # Answer first question
        first_question = await communicator.receive_json_from()
        self.assertEqual(first_question['type'], 'question')
        
        await communicator.send_json_to({
            'type': 'response',
            'question_id': first_question['question_id'],
            'response': 'The meeting went very well. Good engagement from the prospect.'
        })
        
        # Skip processing message
        await communicator.receive_json_from()
        
        # Should get second question
        second_question = await communicator.receive_json_from()
        self.assertEqual(second_question['type'], 'question')
        
        await communicator.send_json_to({
            'type': 'response',
            'question_id': second_question['question_id'],
            'response': 'We discussed their current challenges and our solution capabilities.'
        })
        
        # Skip processing message
        await communicator.receive_json_from()
        
        # Should get conversation complete
        completion = await communicator.receive_json_from()
        self.assertEqual(completion['type'], 'conversation_complete')
        self.assertIn('extracted_data', completion)
        self.assertIn('insights', completion)
        
        # Verify session is completed
        await database_sync_to_async(self.session.refresh_from_db)()
        self.assertEqual(self.session.status, 'completed')
        
        await communicator.disconnect()
    
    async def test_session_recovery_workflow(self):
        """Test session recovery after timeout"""
        # Set session to expired with some answered questions
        await database_sync_to_async(lambda: setattr(self.session, 'status', 'expired'))()
        await database_sync_to_async(self.session.save)()
        
        question1 = await database_sync_to_async(DebriefingQuestion.objects.create)(
            session=self.session,
            question_text='How did the meeting go?',
            question_type='outcome',
            question_order=1,
            user_response='It went well',
            processed=True
        )
        
        question2 = await database_sync_to_async(DebriefingQuestion.objects.create)(
            session=self.session,
            question_text='What were the next steps?',
            question_type='follow_up',
            question_order=2
        )
        
        # Try to reconnect (this would normally trigger recovery)
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        
        # Connection might be rejected for expired session
        # In a real implementation, we'd have a recovery endpoint
        if connected:
            await communicator.disconnect()
        
        # This test demonstrates the recovery workflow structure
        # Actual recovery would be handled by the session manager
    
    async def test_real_time_notifications_integration(self):
        """Test integration between debriefing and notification WebSockets"""
        # Connect to both debriefing and notification WebSockets
        debriefing_communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        debriefing_communicator.scope['user'] = self.user
        
        notification_communicator = WebsocketCommunicator(
            DebriefingNotificationConsumer.as_asgi(),
            "/ws/debriefing/notifications/"
        )
        notification_communicator.scope['user'] = self.user
        
        # Connect both
        debriefing_connected, _ = await debriefing_communicator.connect()
        notification_connected, _ = await notification_communicator.connect()
        
        self.assertTrue(debriefing_connected)
        self.assertTrue(notification_connected)
        
        # Skip initial messages
        await debriefing_communicator.receive_json_from()  # session_state
        
        # Complete a debriefing session (this would trigger notifications)
        await debriefing_communicator.send_json_to({
            'type': 'complete_session'
        })
        
        # Should receive completion message
        completion_response = await debriefing_communicator.receive_json_from()
        self.assertEqual(completion_response['type'], 'session_completed')
        
        # In a real implementation, this would trigger a notification
        # to the notification WebSocket about the completion
        
        await debriefing_communicator.disconnect()
        await notification_communicator.disconnect()


class WebSocketPerformanceTests(DebriefingWebSocketTestCase):
    """
    Performance tests for WebSocket functionality
    """
    
    async def test_multiple_concurrent_sessions(self):
        """Test handling multiple concurrent debriefing sessions"""
        # Create multiple sessions
        sessions = []
        for i in range(5):
            meeting = await database_sync_to_async(Meeting.objects.create)(
                title=f'Test Meeting {i}',
                start_time=timezone.now() - timedelta(hours=1),
                end_time=timezone.now() - timedelta(minutes=30),
                meeting_type='discovery',
                is_sales_meeting=True,
                organizer=self.user,
                duration_minutes=30
            )
            
            session = await database_sync_to_async(DebriefingSession.objects.create)(
                meeting=meeting,
                user=self.user,
                scheduled_time=timezone.now(),
                status='scheduled'
            )
            sessions.append(session)
        
        # Connect to all sessions
        communicators = []
        for session in sessions:
            communicator = WebsocketCommunicator(
                DebriefingConsumer.as_asgi(),
                f"/ws/debriefing/{session.id}/"
            )
            communicator.scope['user'] = self.user
            communicators.append(communicator)
        
        # Connect all
        for communicator in communicators:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
        
        # Verify all received session state
        for communicator in communicators:
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'session_state')
        
        # Disconnect all
        for communicator in communicators:
            await communicator.disconnect()
    
    async def test_message_throughput(self):
        """Test WebSocket message throughput"""
        communicator = WebsocketCommunicator(
            DebriefingConsumer.as_asgi(),
            f"/ws/debriefing/{self.session.id}/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip initial messages
        await communicator.receive_json_from()  # session_state
        
        # Send multiple heartbeat messages rapidly
        start_time = asyncio.get_event_loop().time()
        message_count = 10
        
        for i in range(message_count):
            await communicator.send_json_to({
                'type': 'heartbeat'
            })
            
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'heartbeat_ack')
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        # Should handle messages reasonably quickly
        self.assertLess(duration, 5.0)  # Less than 5 seconds for 10 messages
        
        await communicator.disconnect()