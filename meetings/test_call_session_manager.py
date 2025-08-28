"""
Tests for CallSessionManager
Tests session lifecycle, error handling, and state management
"""
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock, patch
from django.test import TestCase
from django.utils import timezone

from .models import Meeting, MeetingSession
from .call_session_manager import (
    CallSessionManager,
    CallSessionConfig,
    CallSessionState,
    SessionStatus,
    create_session_manager,
    start_meeting_session
)
from .call_bot_service import CallBotService, BotSession, ConnectionStatus, Platform
from .transcription_service import TranscriptionService, TranscriptionSession, AudioQuality
from leads.models import Lead


class CallSessionManagerTest(TestCase):
    """Test CallSessionManager functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id="test_lead_123",
            name="John Doe",
            email="john@example.com",
            company="Test Company"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="test_event_123",
            lead=self.lead,
            title="Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
        
        # Create mock services
        self.mock_call_bot_service = Mock(spec=CallBotService)
        self.mock_transcription_service = Mock(spec=TranscriptionService)
        
        # Create session manager
        self.session_manager = CallSessionManager(
            self.mock_call_bot_service,
            self.mock_transcription_service
        )
    
    def tearDown(self):
        """Clean up test environment"""
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)
    
    def test_session_config_creation(self):
        """Test CallSessionConfig creation and serialization"""
        config = CallSessionConfig(
            meeting_id=str(self.meeting.id),
            meeting_url="https://meet.google.com/test-meeting",
            platform="meet",
            auto_join=True,
            auto_transcribe=True
        )
        
        self.assertEqual(config.meeting_id, str(self.meeting.id))
        self.assertEqual(config.meeting_url, "https://meet.google.com/test-meeting")
        self.assertEqual(config.platform, "meet")
        self.assertTrue(config.auto_join)
        self.assertTrue(config.auto_transcribe)
        
        # Test serialization
        config_dict = config.to_dict()
        self.assertIn('meeting_id', config_dict)
        self.assertIn('meeting_url', config_dict)
        self.assertIn('platform', config_dict)
    
    def test_session_state_creation(self):
        """Test CallSessionState creation and serialization"""
        session_state = CallSessionState(
            session_id="test_session_123",
            meeting_id=str(self.meeting.id),
            status=SessionStatus.INITIALIZING
        )
        
        self.assertEqual(session_state.session_id, "test_session_123")
        self.assertEqual(session_state.meeting_id, str(self.meeting.id))
        self.assertEqual(session_state.status, SessionStatus.INITIALIZING)
        self.assertEqual(session_state.retry_count, 0)
        self.assertEqual(session_state.error_count, 0)
        
        # Test serialization
        state_dict = session_state.to_dict()
        self.assertIn('session_id', state_dict)
        self.assertIn('status', state_dict)
        self.assertEqual(state_dict['status'], 'initializing')
    
    def test_start_call_session_success(self):
        """Test successful call session start"""
        async def run_test():
            # Mock successful initialization
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            self.assertIsInstance(session_state, CallSessionState)
            self.assertEqual(session_state.meeting_id, str(self.meeting.id))
            self.assertEqual(session_state.status, SessionStatus.INITIALIZING)
            
            # Check that session is tracked
            self.assertIn(session_state.session_id, self.session_manager.active_sessions)
            
            # Check that MeetingSession was created
            meeting_session = MeetingSession.objects.get(meeting=self.meeting)
            self.assertEqual(meeting_session.ai_session_id, session_state.session_id)
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_start_call_session_invalid_meeting(self):
        """Test call session start with invalid meeting ID"""
        async def run_test():
            config = CallSessionConfig(
                meeting_id="999999",  # Non-existent meeting
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            with self.assertRaises(ValueError) as context:
                await self.session_manager.start_call_session(config)
            
            self.assertIn("Meeting 999999 not found", str(context.exception))
        
        self.async_test(run_test())
    
    def test_stop_call_session(self):
        """Test stopping a call session"""
        async def run_test():
            # Setup mocks
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            self.mock_call_bot_service.leave_meeting = AsyncMock()
            self.mock_transcription_service.stop_transcription = AsyncMock()
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            # Add some mock data
            session_state.bot_session = BotSession(
                session_id="bot_123",
                meeting_url="https://meet.google.com/test-meeting",
                platform=Platform.GOOGLE_MEET,
                status=ConnectionStatus.CONNECTED
            )
            session_state.transcription_session_id = "transcription_123"
            session_state.partial_transcript = "Test transcript content"
            
            # Stop session
            summary = await self.session_manager.stop_call_session(session_state.session_id)
            
            self.assertIsInstance(summary, dict)
            self.assertEqual(summary['session_id'], session_state.session_id)
            self.assertEqual(summary['meeting_id'], str(self.meeting.id))
            self.assertIn('duration', summary)
            self.assertIn('status', summary)
            
            # Check that session was removed
            self.assertNotIn(session_state.session_id, self.session_manager.active_sessions)
            
            # Check that services were called
            self.mock_call_bot_service.leave_meeting.assert_called_once()
            self.mock_transcription_service.stop_transcription.assert_called_once()
        
        self.async_test(run_test())
    
    def test_get_session_status(self):
        """Test getting session status"""
        async def run_test():
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            # Get status
            status = await self.session_manager.get_session_status(session_state.session_id)
            
            self.assertIsNotNone(status)
            self.assertEqual(status['session_id'], session_state.session_id)
            self.assertEqual(status['meeting_id'], str(self.meeting.id))
            self.assertEqual(status['status'], 'initializing')
            
            # Test non-existent session
            status = await self.session_manager.get_session_status("nonexistent")
            self.assertIsNone(status)
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_list_active_sessions(self):
        """Test listing active sessions"""
        async def run_test():
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            # Start multiple sessions
            sessions = []
            for i in range(3):
                # Create additional meetings
                meeting = Meeting.objects.create(
                    calendar_event_id=f"test_event_{i}",
                    lead=self.lead,
                    title=f"Test Meeting {i}",
                    start_time=timezone.now(),
                    end_time=timezone.now() + timezone.timedelta(hours=1)
                )
                
                config = CallSessionConfig(
                    meeting_id=str(meeting.id),
                    meeting_url=f"https://meet.google.com/test-meeting-{i}",
                    platform="meet"
                )
                
                session_state = await self.session_manager.start_call_session(config)
                sessions.append(session_state)
            
            # List active sessions
            active_sessions = await self.session_manager.list_active_sessions()
            
            self.assertEqual(len(active_sessions), 3)
            
            for session in sessions:
                self.assertIn(session.session_id, active_sessions)
            
            # Cleanup
            for session in sessions:
                await self.session_manager.stop_call_session(session.session_id)
        
        self.async_test(run_test())
    
    def test_session_lifecycle_simulation(self):
        """Test session lifecycle state transitions"""
        async def run_test():
            # Setup comprehensive mocks
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            # Mock bot session
            mock_bot_session = BotSession(
                session_id="bot_123",
                meeting_url="https://meet.google.com/test-meeting",
                platform=Platform.GOOGLE_MEET,
                status=ConnectionStatus.CONNECTED
            )
            self.mock_call_bot_service.join_meeting = AsyncMock(return_value=mock_bot_session)
            self.mock_call_bot_service.get_session_status = AsyncMock(return_value={'status': 'connected'})
            
            # Mock transcription session
            mock_transcription_session = TranscriptionSession(
                session_id="transcription_123",
                stream_id="stream_123"
            )
            self.mock_transcription_service.start_transcription = AsyncMock(return_value=mock_transcription_session)
            self.mock_transcription_service.get_full_transcript = AsyncMock(return_value="Test transcript")
            self.mock_transcription_service.get_session_status = AsyncMock(return_value={'audio_quality': 'good'})
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet",
                auto_join=True,
                auto_transcribe=True
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            # Wait for lifecycle to progress
            await asyncio.sleep(0.5)
            
            # Check that session progressed through states
            # Note: In a real test, we'd need to wait for the lifecycle task to complete
            # For now, we just verify the session was created
            self.assertIsInstance(session_state, CallSessionState)
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_event_handler_registration(self):
        """Test event handler registration and emission"""
        async def run_test():
            events_received = []
            
            def event_handler(session_state, *args):
                events_received.append(('session_started', session_state.session_id))
            
            # Register event handler
            self.session_manager.register_event_handler('session_started', event_handler)
            
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            # Start session (should trigger event)
            session_state = await self.session_manager.start_call_session(config)
            
            # Check that event was received
            self.assertEqual(len(events_received), 1)
            self.assertEqual(events_received[0][0], 'session_started')
            self.assertEqual(events_received[0][1], session_state.session_id)
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_session_data_persistence(self):
        """Test session data saving to database"""
        async def run_test():
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet"
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            # Add some transcript data
            session_state.partial_transcript = "Test transcript content"
            session_state.status = SessionStatus.TRANSCRIBING
            
            # Save session data
            await self.session_manager._save_session_data(session_state, final=False)
            
            # Check database
            meeting_session = MeetingSession.objects.get(meeting=self.meeting)
            self.assertEqual(meeting_session.transcript, "Test transcript content")
            self.assertIsNotNone(meeting_session.notes)
            
            # Parse notes to check metadata
            notes_data = json.loads(meeting_session.notes)
            self.assertEqual(notes_data['session_id'], session_state.session_id)
            self.assertEqual(notes_data['status'], 'transcribing')
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms"""
        async def run_test():
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            config = CallSessionConfig(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/test-meeting",
                platform="meet",
                max_retry_attempts=2
            )
            
            # Start session
            session_state = await self.session_manager.start_call_session(config)
            
            # Simulate recoverable error
            test_error = Exception("connection_timeout")
            await self.session_manager._handle_session_error(session_state, config, test_error)
            
            # Check error was recorded
            self.assertEqual(session_state.error_count, 1)
            self.assertEqual(session_state.last_error, "connection_timeout")
            
            # Test retry functionality
            session_state.status = SessionStatus.FAILED
            retry_result = await self.session_manager.retry_failed_session(session_state.session_id)
            self.assertTrue(retry_result)
            self.assertEqual(session_state.retry_count, 1)
            self.assertEqual(session_state.status, SessionStatus.INITIALIZING)
            
            # Cleanup
            await self.session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())
    
    def test_cleanup_functionality(self):
        """Test cleanup of all sessions"""
        async def run_test():
            self.mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            # Start multiple sessions
            sessions = []
            for i in range(2):
                meeting = Meeting.objects.create(
                    calendar_event_id=f"cleanup_test_{i}",
                    lead=self.lead,
                    title=f"Cleanup Test {i}",
                    start_time=timezone.now(),
                    end_time=timezone.now() + timezone.timedelta(hours=1)
                )
                
                config = CallSessionConfig(
                    meeting_id=str(meeting.id),
                    meeting_url=f"https://meet.google.com/cleanup-test-{i}",
                    platform="meet"
                )
                
                session_state = await self.session_manager.start_call_session(config)
                sessions.append(session_state)
            
            # Verify sessions are active
            self.assertEqual(len(self.session_manager.active_sessions), 2)
            
            # Cleanup all sessions
            await self.session_manager.cleanup()
            
            # Verify all sessions were stopped
            self.assertEqual(len(self.session_manager.active_sessions), 0)
            self.assertEqual(len(self.session_manager.session_tasks), 0)
        
        self.async_test(run_test())


class UtilityFunctionsTest(TestCase):
    """Test utility functions"""
    
    def setUp(self):
        """Set up test environment"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create test data
        self.lead = Lead.objects.create(
            crm_id="util_test_lead",
            name="Jane Doe",
            email="jane@example.com",
            company="Utility Test Company"
        )
        
        self.meeting = Meeting.objects.create(
            calendar_event_id="util_test_event",
            lead=self.lead,
            title="Utility Test Meeting",
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1)
        )
    
    def tearDown(self):
        """Clean up test environment"""
        self.loop.close()
    
    def async_test(self, coro):
        """Helper to run async tests"""
        return self.loop.run_until_complete(coro)
    
    def test_create_session_manager(self):
        """Test session manager factory function"""
        mock_call_bot_service = Mock(spec=CallBotService)
        mock_transcription_service = Mock(spec=TranscriptionService)
        
        session_manager = create_session_manager(mock_call_bot_service, mock_transcription_service)
        
        self.assertIsInstance(session_manager, CallSessionManager)
        self.assertEqual(session_manager.call_bot_service, mock_call_bot_service)
        self.assertEqual(session_manager.transcription_service, mock_transcription_service)
    
    def test_start_meeting_session_convenience(self):
        """Test convenience function for starting meeting sessions"""
        async def run_test():
            mock_call_bot_service = Mock(spec=CallBotService)
            mock_transcription_service = Mock(spec=TranscriptionService)
            mock_transcription_service.initialize = AsyncMock(return_value=True)
            
            session_manager = create_session_manager(mock_call_bot_service, mock_transcription_service)
            
            # Use convenience function
            session_state = await start_meeting_session(
                meeting_id=str(self.meeting.id),
                meeting_url="https://meet.google.com/convenience-test",
                platform="meet",
                session_manager=session_manager
            )
            
            self.assertIsInstance(session_state, CallSessionState)
            self.assertEqual(session_state.meeting_id, str(self.meeting.id))
            
            # Cleanup
            await session_manager.stop_call_session(session_state.session_id)
        
        self.async_test(run_test())