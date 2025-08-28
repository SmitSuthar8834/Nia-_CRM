"""
Tests for WebSocket functionality in meetings app
"""
import json
import pytest
from datetime import datetime
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from meetings.consumers import MeetingConsumer
from meetings.models import Meeting, MeetingSession, ActionItem
from leads.models import Lead


class WebSocketTestCase(TransactionTestCase):
    """
    Test case for WebSocket connections and messaging
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.lead = Lead.objects.create(
            crm_id='TEST_001',
            name='Test Lead',
            email='lead@example.com',
            company='Test Company',
            status='new'
        )
        
        from django.utils import timezone
        
        self.meeting = Meeting.objects.create(
            calendar_event_id='test_event_123',
            lead=self.lead,
            title='Test Meeting',
            start_time=timezone.now(),
            end_time=timezone.now(),
            status='scheduled'
        )
    
    def get_communicator(self, user=None):
        """Helper method to create WebSocket communicator"""
        from meetings.routing import websocket_urlpatterns
        from channels.routing import URLRouter
        
        application = URLRouter(websocket_urlpatterns)
        communicator = WebsocketCommunicator(
            application,
            f"/ws/meetings/{self.meeting.id}/"
        )
        communicator.scope["user"] = user or self.user
        return communicator
    
    @pytest.mark.asyncio
    async def test_websocket_connection_authenticated(self):
        """Test WebSocket connection with authenticated user"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Should receive connection confirmation
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['meeting_id'], str(self.meeting.id))
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_websocket_connection_unauthenticated(self):
        """Test WebSocket connection rejection for unauthenticated user"""
        from django.contrib.auth.models import AnonymousUser
        
        communicator = self.get_communicator(user=AnonymousUser())
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
    
    @pytest.mark.asyncio
    async def test_note_update_message(self):
        """Test note update message handling"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send note update
        test_notes = "These are test meeting notes"
        await communicator.send_json_to({
            'type': 'note_update',
            'notes': test_notes
        })
        
        # Should receive the note update back
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'note_update')
        self.assertEqual(response['notes'], test_notes)
        self.assertEqual(response['user_id'], self.user.id)
        
        # Verify notes were saved to database
        session = await database_sync_to_async(MeetingSession.objects.get)(
            meeting=self.meeting
        )
        self.assertEqual(session.notes, test_notes)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_action_item_message(self):
        """Test action item message handling"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send action item
        action_item_data = {
            'description': 'Follow up with client',
            'assignee': 'John Doe',
            'due_date': '2024-01-15'
        }
        
        await communicator.send_json_to({
            'type': 'action_item',
            'action_item': action_item_data
        })
        
        # Should receive the action item back
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'action_item')
        self.assertEqual(response['action_item'], action_item_data)
        self.assertEqual(response['user_id'], self.user.id)
        
        # Verify action item was saved to database
        action_items = await database_sync_to_async(list)(
            ActionItem.objects.filter(meeting_session__meeting=self.meeting)
        )
        self.assertEqual(len(action_items), 1)
        self.assertEqual(action_items[0].description, action_item_data['description'])
        self.assertEqual(action_items[0].assignee, action_item_data['assignee'])
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_ai_suggestion_request(self):
        """Test AI suggestion request handling"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send AI suggestion request
        await communicator.send_json_to({
            'type': 'ai_suggestion_request',
            'context': 'We are discussing pricing options'
        })
        
        # Should receive AI suggestion
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'ai_suggestion')
        self.assertIn('suggestions', response)
        self.assertIsInstance(response['suggestions'], list)
        self.assertEqual(response['user_id'], self.user.id)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Test ping/pong for connection health check"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send ping
        await communicator.send_json_to({
            'type': 'ping'
        })
        
        # Should receive pong
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'pong')
        self.assertIn('timestamp', response)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_invalid_message_handling(self):
        """Test handling of invalid messages"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send invalid JSON
        await communicator.send_to(text_data="invalid json")
        
        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('Invalid JSON', response['message'])
        
        # Send message without type
        await communicator.send_json_to({
            'data': 'some data'
        })
        
        # Should receive error message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('Message type is required', response['message'])
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_clients_same_meeting(self):
        """Test multiple clients connected to the same meeting"""
        # Create second user
        user2 = await database_sync_to_async(User.objects.create_user)(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Connect first client
        communicator1 = self.get_communicator(user=self.user)
        
        # Connect second client
        communicator2 = self.get_communicator(user=user2)
        
        # Both should connect successfully
        connected1, _ = await communicator1.connect()
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        
        # Skip connection confirmations
        await communicator1.receive_json_from()
        await communicator2.receive_json_from()
        
        # Send note update from first client
        test_notes = "Shared meeting notes"
        await communicator1.send_json_to({
            'type': 'note_update',
            'notes': test_notes
        })
        
        # Both clients should receive the update
        response1 = await communicator1.receive_json_from()
        response2 = await communicator2.receive_json_from()
        
        self.assertEqual(response1['type'], 'note_update')
        self.assertEqual(response2['type'], 'note_update')
        self.assertEqual(response1['notes'], test_notes)
        self.assertEqual(response2['notes'], test_notes)
        
        await communicator1.disconnect()
        await communicator2.disconnect()


    @pytest.mark.asyncio
    async def test_enhanced_ai_suggestion_request(self):
        """Test enhanced AI suggestion request with meeting stage and context"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send enhanced AI suggestion request
        await communicator.send_json_to({
            'type': 'ai_suggestion_request',
            'context': 'We are discussing the client\'s current sales process and they mentioned challenges with lead tracking',
            'meeting_stage': 'discovery'
        })
        
        # Should receive enhanced AI suggestions
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'ai_suggestion')
        self.assertIn('suggestions', response)
        self.assertIsInstance(response['suggestions'], list)
        self.assertEqual(response['meeting_stage'], 'discovery')
        self.assertEqual(response['user_id'], self.user.id)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_note_update_with_conflict_resolution(self):
        """Test note update with version conflict resolution"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Send first note update
        await communicator.send_json_to({
            'type': 'note_update',
            'notes': 'Initial meeting notes',
            'version': 0
        })
        
        # Should receive successful update
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'note_update')
        self.assertEqual(response['notes'], 'Initial meeting notes')
        self.assertIn('version', response)
        
        # Send conflicting update with old version
        await communicator.send_json_to({
            'type': 'note_update',
            'notes': 'Conflicting notes',
            'version': 0  # Old version
        })
        
        # Should receive conflict notification
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'note_conflict')
        self.assertIn('server_notes', response)
        self.assertIn('client_notes', response)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_connection_resilience_features(self):
        """Test connection resilience features like heartbeat and reconnection"""
        communicator = self.get_communicator()
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Skip connection confirmation
        await communicator.receive_json_from()
        
        # Test connection status check
        await communicator.send_json_to({
            'type': 'connection_status',
            'status': 'healthy'
        })
        
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'connection_status_response')
        self.assertEqual(response['server_status'], 'healthy')
        self.assertEqual(response['client_status'], 'healthy')
        
        # Test reconnection
        await communicator.send_json_to({
            'type': 'reconnect'
        })
        
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'reconnect_success')
        self.assertIn('meeting_state', response)
        
        await communicator.disconnect()
    
    @pytest.mark.asyncio
    async def test_real_time_note_synchronization(self):
        """Test real-time note synchronization between multiple clients"""
        # Create second user
        user2 = await database_sync_to_async(User.objects.create_user)(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        # Connect both clients
        communicator1 = self.get_communicator(user=self.user)
        communicator2 = self.get_communicator(user=user2)
        
        connected1, _ = await communicator1.connect()
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected1)
        self.assertTrue(connected2)
        
        # Skip connection confirmations
        await communicator1.receive_json_from()
        await communicator2.receive_json_from()
        
        # Client 1 sends note update with cursor position
        await communicator1.send_json_to({
            'type': 'note_update',
            'notes': 'Real-time synchronized notes',
            'version': 0,
            'cursor_position': 25
        })
        
        # Both clients should receive the update
        response1 = await communicator1.receive_json_from()
        response2 = await communicator2.receive_json_from()
        
        # Verify both received the same update
        self.assertEqual(response1['type'], 'note_update')
        self.assertEqual(response2['type'], 'note_update')
        self.assertEqual(response1['notes'], 'Real-time synchronized notes')
        self.assertEqual(response2['notes'], 'Real-time synchronized notes')
        self.assertEqual(response1['cursor_position'], 25)
        self.assertEqual(response2['cursor_position'], 25)
        
        await communicator1.disconnect()
        await communicator2.disconnect()


@pytest.mark.asyncio
async def test_websocket_connection_with_nonexistent_meeting():
    """Test WebSocket connection with non-existent meeting"""
    user = await database_sync_to_async(User.objects.create_user)(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    
    from meetings.routing import websocket_urlpatterns
    from channels.routing import URLRouter
    
    application = URLRouter(websocket_urlpatterns)
    communicator = WebsocketCommunicator(
        application,
        "/ws/meetings/999999/"
    )
    communicator.scope["user"] = user
    
    connected, subprotocol = await communicator.connect()
    # Should reject connection due to non-existent meeting
    assert not connected