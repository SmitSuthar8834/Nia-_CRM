"""
Unit tests for CallBotService and platform-specific bots
"""
import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from django.test import TestCase

from .call_bot_service import (
    CallBotService, 
    Platform, 
    ConnectionStatus, 
    BotSession,
    TranscriptionStream,
    GoogleMeetBot,
    MicrosoftTeamsBot,
    ZoomBot
)


class TestPlatformDetection(TestCase):
    """Test platform detection from meeting URLs"""
    
    def setUp(self):
        self.service = CallBotService()
    
    def test_detect_google_meet(self):
        """Test Google Meet URL detection"""
        urls = [
            "https://meet.google.com/abc-defg-hij",
            "https://meet.google.com/lookup/abc123",
            "http://meet.google.com/test"
        ]
        
        for url in urls:
            platform = self.service._detect_platform(url)
            self.assertEqual(platform, Platform.GOOGLE_MEET)
    
    def test_detect_microsoft_teams(self):
        """Test Microsoft Teams URL detection"""
        urls = [
            "https://teams.microsoft.com/l/meetup-join/abc123",
            "https://teams.live.com/meet/abc123",
            "https://teams.microsoft.com/dl/launcher"
        ]
        
        for url in urls:
            platform = self.service._detect_platform(url)
            self.assertEqual(platform, Platform.MICROSOFT_TEAMS)
    
    def test_detect_zoom(self):
        """Test Zoom URL detection"""
        urls = [
            "https://zoom.us/j/1234567890",
            "https://us02web.zoom.us/j/1234567890",
            "https://zoom.com/j/meeting123"
        ]
        
        for url in urls:
            platform = self.service._detect_platform(url)
            self.assertEqual(platform, Platform.ZOOM)
    
    def test_unsupported_platform(self):
        """Test unsupported platform raises ValueError"""
        with self.assertRaises(ValueError):
            self.service._detect_platform("https://webex.com/meeting/123")


class TestBotSession(TestCase):
    """Test BotSession data structure"""
    
    def test_bot_session_creation(self):
        """Test BotSession creation and serialization"""
        session = BotSession(
            session_id="test_123",
            meeting_url="https://meet.google.com/test",
            platform=Platform.GOOGLE_MEET,
            status=ConnectionStatus.CONNECTED,
            join_time=1234567890.0
        )
        
        self.assertEqual(session.session_id, "test_123")
        self.assertEqual(session.platform, Platform.GOOGLE_MEET)
        self.assertEqual(session.status, ConnectionStatus.CONNECTED)
        
        # Test serialization
        data = session.to_dict()
        self.assertEqual(data['session_id'], "test_123")
        self.assertEqual(data['platform'], "meet")
        self.assertEqual(data['status'], "connected")
        self.assertEqual(data['join_time'], 1234567890.0)


class TestTranscriptionStream(TestCase):
    """Test TranscriptionStream data structure"""
    
    def test_transcription_stream_creation(self):
        """Test TranscriptionStream creation and serialization"""
        stream = TranscriptionStream(
            session_id="test_123",
            stream_id="stream_456",
            is_active=True,
            audio_quality="good",
            speaker_count=3
        )
        
        self.assertEqual(stream.session_id, "test_123")
        self.assertEqual(stream.stream_id, "stream_456")
        self.assertTrue(stream.is_active)
        self.assertEqual(stream.speaker_count, 3)
        
        # Test serialization
        data = stream.to_dict()
        self.assertEqual(data['session_id'], "test_123")
        self.assertEqual(data['stream_id'], "stream_456")
        self.assertTrue(data['is_active'])
        self.assertEqual(data['audio_quality'], "good")


class AsyncTestCase(TestCase):
    """Base class for async test cases"""
    
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
    
    def tearDown(self):
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)


class TestGoogleMeetBot(AsyncTestCase):
    """Test Google Meet bot implementation"""
    
    def setUp(self):
        super().setUp()
        self.bot = GoogleMeetBot()
    
    def test_authentication(self):
        """Test Google Meet authentication"""
        async def test():
            result = await self.bot.authenticate({})
            self.assertTrue(result)
        
        self.async_test(test())
    
    def test_join_meeting(self):
        """Test joining Google Meet"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://meet.google.com/test"
            
            result = await self.bot.join_meeting(meeting_url, session_id)
            self.assertTrue(result)
            
            # Check session was created
            self.assertIn(session_id, self.bot.sessions)
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['url'], meeting_url)
            self.assertEqual(session_data['status'], ConnectionStatus.CONNECTED)
        
        self.async_test(test())
    
    def test_start_transcription(self):
        """Test starting transcription"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://meet.google.com/test"
            
            # First join meeting
            await self.bot.join_meeting(meeting_url, session_id)
            
            # Then start transcription
            stream_id = await self.bot.start_transcription(session_id)
            
            self.assertIsNotNone(stream_id)
            self.assertTrue(stream_id.startswith("gmeet_stream_"))
            
            # Check session status updated
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['status'], ConnectionStatus.TRANSCRIBING)
        
        self.async_test(test())
    
    def test_start_transcription_invalid_session(self):
        """Test starting transcription with invalid session"""
        async def test():
            with self.assertRaises(ValueError):
                await self.bot.start_transcription("invalid_session")
        
        self.async_test(test())
    
    def test_leave_meeting(self):
        """Test leaving meeting"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://meet.google.com/test"
            
            # Join meeting first
            await self.bot.join_meeting(meeting_url, session_id)
            
            # Leave meeting
            result = await self.bot.leave_meeting(session_id)
            self.assertTrue(result)
            
            # Check session status
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['status'], ConnectionStatus.DISCONNECTED)
            self.assertIsNotNone(session_data['leave_time'])
        
        self.async_test(test())
    
    def test_get_connection_status(self):
        """Test getting connection status"""
        async def test():
            session_id = "test_session_123"
            
            # Test non-existent session
            status = await self.bot.get_connection_status(session_id)
            self.assertEqual(status, ConnectionStatus.DISCONNECTED)
            
            # Join meeting and test status
            await self.bot.join_meeting("https://meet.google.com/test", session_id)
            status = await self.bot.get_connection_status(session_id)
            self.assertEqual(status, ConnectionStatus.CONNECTED)
        
        self.async_test(test())


class TestMicrosoftTeamsBot(AsyncTestCase):
    """Test Microsoft Teams bot implementation"""
    
    def setUp(self):
        super().setUp()
        self.bot = MicrosoftTeamsBot()
    
    def test_authentication(self):
        """Test Teams authentication"""
        async def test():
            result = await self.bot.authenticate({})
            self.assertTrue(result)
        
        self.async_test(test())
    
    def test_join_meeting(self):
        """Test joining Teams meeting"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://teams.microsoft.com/l/meetup-join/test"
            
            result = await self.bot.join_meeting(meeting_url, session_id)
            self.assertTrue(result)
            
            # Check session was created
            self.assertIn(session_id, self.bot.sessions)
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['url'], meeting_url)
            self.assertEqual(session_data['status'], ConnectionStatus.CONNECTED)
        
        self.async_test(test())
    
    def test_start_transcription(self):
        """Test starting Teams transcription"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://teams.microsoft.com/l/meetup-join/test"
            
            # First join meeting
            await self.bot.join_meeting(meeting_url, session_id)
            
            # Then start transcription
            stream_id = await self.bot.start_transcription(session_id)
            
            self.assertIsNotNone(stream_id)
            self.assertTrue(stream_id.startswith("teams_stream_"))
            
            # Check session status updated
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['status'], ConnectionStatus.TRANSCRIBING)
        
        self.async_test(test())


class TestZoomBot(AsyncTestCase):
    """Test Zoom bot implementation"""
    
    def setUp(self):
        super().setUp()
        self.bot = ZoomBot()
    
    def test_authentication(self):
        """Test Zoom authentication"""
        async def test():
            result = await self.bot.authenticate({})
            self.assertTrue(result)
        
        self.async_test(test())
    
    def test_join_meeting(self):
        """Test joining Zoom meeting"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://zoom.us/j/1234567890"
            
            result = await self.bot.join_meeting(meeting_url, session_id)
            self.assertTrue(result)
            
            # Check session was created
            self.assertIn(session_id, self.bot.sessions)
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['url'], meeting_url)
            self.assertEqual(session_data['status'], ConnectionStatus.CONNECTED)
        
        self.async_test(test())
    
    def test_start_transcription(self):
        """Test starting Zoom transcription"""
        async def test():
            session_id = "test_session_123"
            meeting_url = "https://zoom.us/j/1234567890"
            
            # First join meeting
            await self.bot.join_meeting(meeting_url, session_id)
            
            # Then start transcription
            stream_id = await self.bot.start_transcription(session_id)
            
            self.assertIsNotNone(stream_id)
            self.assertTrue(stream_id.startswith("zoom_stream_"))
            
            # Check session status updated
            session_data = self.bot.sessions[session_id]
            self.assertEqual(session_data['status'], ConnectionStatus.TRANSCRIBING)
        
        self.async_test(test())


class TestCallBotService(AsyncTestCase):
    """Test main CallBotService class"""
    
    def setUp(self):
        super().setUp()
        self.service = CallBotService()
    
    def test_join_meeting_google_meet(self):
        """Test joining Google Meet through service"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            session = await self.service.join_meeting(meeting_url)
            
            self.assertIsInstance(session, BotSession)
            self.assertEqual(session.platform, Platform.GOOGLE_MEET)
            self.assertEqual(session.status, ConnectionStatus.CONNECTED)
            self.assertEqual(session.meeting_url, meeting_url)
            self.assertIsNotNone(session.join_time)
            
            # Check session is stored
            self.assertIn(session.session_id, self.service.sessions)
        
        self.async_test(test())
    
    def test_join_meeting_with_platform_override(self):
        """Test joining meeting with explicit platform"""
        async def test():
            meeting_url = "https://example.com/meeting"
            
            session = await self.service.join_meeting(meeting_url, platform="teams")
            
            self.assertEqual(session.platform, Platform.MICROSOFT_TEAMS)
            self.assertEqual(session.status, ConnectionStatus.CONNECTED)
        
        self.async_test(test())
    
    def test_start_transcription(self):
        """Test starting transcription through service"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            
            # Start transcription
            stream = await self.service.start_transcription(session.session_id)
            
            self.assertIsInstance(stream, TranscriptionStream)
            self.assertEqual(stream.session_id, session.session_id)
            self.assertTrue(stream.is_active)
            self.assertIsNotNone(stream.stream_id)
            
            # Check session status updated
            updated_session = self.service.sessions[session.session_id]
            self.assertEqual(updated_session.status, ConnectionStatus.TRANSCRIBING)
        
        self.async_test(test())
    
    def test_start_transcription_invalid_session(self):
        """Test starting transcription with invalid session"""
        async def test():
            with self.assertRaises(ValueError):
                await self.service.start_transcription("invalid_session")
        
        self.async_test(test())
    
    def test_start_transcription_not_connected(self):
        """Test starting transcription when not connected"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            
            # Manually set status to disconnected
            session.status = ConnectionStatus.DISCONNECTED
            
            with self.assertRaises(ValueError):
                await self.service.start_transcription(session.session_id)
        
        self.async_test(test())
    
    def test_end_session(self):
        """Test ending session through service"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            session_id = session.session_id
            
            # End session
            summary = await self.service.end_session(session_id)
            
            self.assertIsInstance(summary, dict)
            self.assertEqual(summary['session_id'], session_id)
            self.assertEqual(summary['platform'], 'meet')
            self.assertTrue(summary['leave_success'])
            self.assertIsNotNone(summary['duration'])
            
            # Check session status updated
            updated_session = self.service.sessions[session_id]
            self.assertEqual(updated_session.status, ConnectionStatus.DISCONNECTED)
            self.assertIsNotNone(updated_session.leave_time)
        
        self.async_test(test())
    
    def test_handle_disconnection(self):
        """Test handling disconnection with reconnection"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            session_id = session.session_id
            
            # Simulate disconnection
            session.status = ConnectionStatus.DISCONNECTED
            
            # Handle disconnection
            result = await self.service.handle_disconnection(session_id)
            
            self.assertTrue(result)
            
            # Check reconnection attempt was made
            updated_session = self.service.sessions[session_id]
            self.assertEqual(updated_session.reconnect_attempts, 1)
            self.assertEqual(updated_session.status, ConnectionStatus.CONNECTED)
        
        self.async_test(test())
    
    def test_handle_disconnection_max_attempts(self):
        """Test handling disconnection with max attempts reached"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            session_id = session.session_id
            
            # Set max reconnection attempts
            session.reconnect_attempts = self.service.MAX_RECONNECT_ATTEMPTS
            
            # Handle disconnection
            result = await self.service.handle_disconnection(session_id)
            
            self.assertFalse(result)
            
            # Check session marked as error
            updated_session = self.service.sessions[session_id]
            self.assertEqual(updated_session.status, ConnectionStatus.ERROR)
            self.assertIn("Max reconnection attempts", updated_session.error_message)
        
        self.async_test(test())
    
    def test_get_session_status(self):
        """Test getting session status"""
        async def test():
            meeting_url = "https://meet.google.com/test-meeting"
            
            # Join meeting first
            session = await self.service.join_meeting(meeting_url)
            session_id = session.session_id
            
            # Get status
            status = self.service.get_session_status(session_id)
            
            self.assertIsNotNone(status)
            self.assertEqual(status['session_id'], session_id)
            self.assertEqual(status['platform'], 'meet')
            self.assertEqual(status['status'], 'connected')
            
            # Test non-existent session
            status = self.service.get_session_status("invalid_session")
            self.assertIsNone(status)
        
        self.async_test(test())
    
    def test_list_active_sessions(self):
        """Test listing active sessions"""
        async def test():
            # Join multiple meetings
            session1 = await self.service.join_meeting("https://meet.google.com/test1")
            session2 = await self.service.join_meeting("https://teams.microsoft.com/test2")
            session3 = await self.service.join_meeting("https://zoom.us/j/123")
            
            # End one session
            await self.service.end_session(session3.session_id)
            
            # List active sessions
            active_sessions = self.service.list_active_sessions()
            
            self.assertEqual(len(active_sessions), 2)
            self.assertIn(session1.session_id, active_sessions)
            self.assertIn(session2.session_id, active_sessions)
            self.assertNotIn(session3.session_id, active_sessions)
        
        self.async_test(test())
    
    def test_register_status_callback(self):
        """Test registering status callback"""
        callback = Mock()
        session_id = "test_session"
        
        self.service.register_status_callback(session_id, callback)
        
        self.assertIn(session_id, self.service.status_callbacks)
        self.assertEqual(self.service.status_callbacks[session_id], callback)


class TestConnectionMonitoring(AsyncTestCase):
    """Test connection monitoring functionality"""
    
    def setUp(self):
        super().setUp()
        self.service = CallBotService()
    
    @patch('asyncio.sleep', new_callable=AsyncMock)
    def test_monitor_connections(self, mock_sleep):
        """Test connection monitoring loop"""
        async def test():
            # Mock sleep to prevent infinite loop
            mock_sleep.side_effect = [None, Exception("Stop loop")]
            
            # Join a meeting
            session = await self.service.join_meeting("https://meet.google.com/test")
            
            # Mock bot to return disconnected status
            mock_bot = Mock()
            mock_bot.get_connection_status = AsyncMock(return_value=ConnectionStatus.DISCONNECTED)
            self.service.bots[Platform.GOOGLE_MEET] = mock_bot
            
            # Mock handle_disconnection
            self.service.handle_disconnection = AsyncMock(return_value=True)
            
            # Run monitor (will stop on second sleep due to exception)
            with self.assertRaises(Exception):
                await self.service.monitor_connections()
            
            # Verify disconnection was handled
            self.service.handle_disconnection.assert_called_once_with(session.session_id)
        
        self.async_test(test())


if __name__ == '__main__':
    # Run tests with pytest for async support
    pytest.main([__file__])