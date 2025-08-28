"""
Call session management for video call bot integration
Handles session lifecycle, transcript saving, and error recovery
"""
import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from asgiref.sync import sync_to_async

from .models import Meeting, MeetingSession
from .transcription_service import TranscriptionService, AudioQuality
from .call_bot_service import CallBotService, BotSession

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Call session status types"""
    INITIALIZING = "initializing"
    JOINING = "joining"
    CONNECTED = "connected"
    TRANSCRIBING = "transcribing"
    DISCONNECTED = "disconnected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CallSessionConfig:
    """Configuration for call session"""
    meeting_id: str
    meeting_url: str
    platform: str  # 'meet', 'teams', 'zoom'
    auto_join: bool = True
    auto_transcribe: bool = True
    save_partial_transcripts: bool = True
    max_retry_attempts: int = 3
    retry_delay: float = 5.0
    session_timeout: float = 7200.0  # 2 hours
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'meeting_id': self.meeting_id,
            'meeting_url': self.meeting_url,
            'platform': self.platform,
            'auto_join': self.auto_join,
            'auto_transcribe': self.auto_transcribe,
            'save_partial_transcripts': self.save_partial_transcripts,
            'max_retry_attempts': self.max_retry_attempts,
            'retry_delay': self.retry_delay,
            'session_timeout': self.session_timeout
        }


@dataclass
class CallSessionState:
    """Current state of a call session"""
    session_id: str
    meeting_id: str
    status: SessionStatus
    bot_session: Optional[BotSession] = None
    transcription_session_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    join_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    partial_transcript: str = ""
    audio_quality: AudioQuality = AudioQuality.GOOD
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'meeting_id': self.meeting_id,
            'status': self.status.value,
            'bot_session': self.bot_session.to_dict() if self.bot_session else None,
            'transcription_session_id': self.transcription_session_id,
            'start_time': self.start_time,
            'join_time': self.join_time,
            'end_time': self.end_time,
            'retry_count': self.retry_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'partial_transcript_length': len(self.partial_transcript),
            'audio_quality': self.audio_quality.value
        }


class CallSessionManager:
    """
    Manages video call bot sessions with lifecycle handling and error recovery
    """
    
    def __init__(self, call_bot_service: CallBotService, transcription_service: TranscriptionService):
        self.call_bot_service = call_bot_service
        self.transcription_service = transcription_service
        self.active_sessions: Dict[str, CallSessionState] = {}
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger(__name__)
    
    async def start_call_session(self, config: CallSessionConfig) -> CallSessionState:
        """
        Start a new call session
        
        Args:
            config: Call session configuration
            
        Returns:
            CallSessionState: The created session state
            
        Raises:
            ValueError: If session already exists or invalid config
            Exception: If session initialization fails
        """
        try:
            session_id = f"call_session_{config.meeting_id}_{int(time.time())}"
            
            if session_id in self.active_sessions:
                raise ValueError(f"Call session {session_id} already exists")
            
            # Validate meeting exists
            try:
                meeting = await sync_to_async(Meeting.objects.get)(id=config.meeting_id)
            except ObjectDoesNotExist:
                raise ValueError(f"Meeting {config.meeting_id} not found")
            
            # Create session state
            session_state = CallSessionState(
                session_id=session_id,
                meeting_id=config.meeting_id,
                status=SessionStatus.INITIALIZING
            )
            
            self.active_sessions[session_id] = session_state
            
            # Create or get meeting session record
            meeting_session, created = await sync_to_async(MeetingSession.objects.get_or_create)(
                meeting=meeting,
                defaults={
                    'ai_session_id': session_id,
                    'started_at': timezone.now()
                }
            )
            
            if not created:
                # Update existing session
                meeting_session.ai_session_id = session_id
                meeting_session.started_at = timezone.now()
                meeting_session.ended_at = None
                await sync_to_async(meeting_session.save)()
            
            # Start session management task
            self.session_tasks[session_id] = asyncio.create_task(
                self._manage_session_lifecycle(session_id, config)
            )
            
            self.logger.info(f"Started call session {session_id} for meeting {config.meeting_id}")
            await self._emit_event('session_started', session_state)
            
            return session_state
            
        except Exception as e:
            self.logger.error(f"Failed to start call session: {e}")
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            raise
    
    async def stop_call_session(self, session_id: str, reason: str = "manual_stop") -> Dict[str, Any]:
        """
        Stop a call session
        
        Args:
            session_id: Session ID to stop
            reason: Reason for stopping
            
        Returns:
            Dict containing session summary
            
        Raises:
            ValueError: If session not found
        """
        try:
            if session_id not in self.active_sessions:
                raise ValueError(f"Call session {session_id} not found")
            
            session_state = self.active_sessions[session_id]
            session_state.status = SessionStatus.COMPLETED
            session_state.end_time = time.time()
            
            # Cancel session management task
            if session_id in self.session_tasks:
                self.session_tasks[session_id].cancel()
                del self.session_tasks[session_id]
            
            # Stop bot session if active
            if session_state.bot_session:
                try:
                    await self.call_bot_service.leave_meeting(session_state.bot_session.session_id)
                except Exception as e:
                    self.logger.warning(f"Error leaving meeting: {e}")
            
            # Stop transcription if active
            if session_state.transcription_session_id:
                try:
                    await self.transcription_service.stop_transcription(session_state.transcription_session_id)
                except Exception as e:
                    self.logger.warning(f"Error stopping transcription: {e}")
            
            # Save final transcript and session data
            await self._save_session_data(session_state, final=True)
            
            # Generate session summary
            summary = {
                'session_id': session_id,
                'meeting_id': session_state.meeting_id,
                'duration': session_state.end_time - session_state.start_time if session_state.end_time else 0,
                'status': session_state.status.value,
                'retry_count': session_state.retry_count,
                'error_count': session_state.error_count,
                'reason': reason,
                'transcript_length': len(session_state.partial_transcript),
                'audio_quality': session_state.audio_quality.value
            }
            
            # Clean up
            del self.active_sessions[session_id]
            
            self.logger.info(f"Stopped call session {session_id}: {reason}")
            await self._emit_event('session_stopped', session_state, summary)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Failed to stop call session {session_id}: {e}")
            raise
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a call session"""
        if session_id not in self.active_sessions:
            return None
        
        return self.active_sessions[session_id].to_dict()
    
    async def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active call sessions"""
        return {
            session_id: session_state.to_dict()
            for session_id, session_state in self.active_sessions.items()
        }
    
    async def retry_failed_session(self, session_id: str) -> bool:
        """
        Retry a failed session
        
        Args:
            session_id: Session ID to retry
            
        Returns:
            bool: True if retry was initiated, False otherwise
        """
        try:
            if session_id not in self.active_sessions:
                self.logger.warning(f"Cannot retry session {session_id}: not found")
                return False
            
            session_state = self.active_sessions[session_id]
            
            if session_state.status not in [SessionStatus.FAILED, SessionStatus.DISCONNECTED]:
                self.logger.warning(f"Cannot retry session {session_id}: status is {session_state.status}")
                return False
            
            session_state.status = SessionStatus.INITIALIZING
            session_state.retry_count += 1
            session_state.last_error = None
            
            self.logger.info(f"Retrying call session {session_id} (attempt {session_state.retry_count})")
            await self._emit_event('session_retry', session_state)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to retry session {session_id}: {e}")
            return False
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register event handler for session events"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def _manage_session_lifecycle(self, session_id: str, config: CallSessionConfig):
        """
        Manage the complete lifecycle of a call session
        
        Args:
            session_id: Session ID to manage
            config: Session configuration
        """
        try:
            session_state = self.active_sessions[session_id]
            
            while session_state.status not in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
                try:
                    if session_state.status == SessionStatus.INITIALIZING:
                        await self._initialize_session(session_state, config)
                    
                    elif session_state.status == SessionStatus.JOINING:
                        await self._join_meeting(session_state, config)
                    
                    elif session_state.status == SessionStatus.CONNECTED:
                        await self._start_transcription(session_state, config)
                    
                    elif session_state.status == SessionStatus.TRANSCRIBING:
                        await self._monitor_session(session_state, config)
                    
                    elif session_state.status == SessionStatus.DISCONNECTED:
                        await self._handle_disconnection(session_state, config)
                    
                    # Check for timeout
                    if time.time() - session_state.start_time > config.session_timeout:
                        self.logger.warning(f"Session {session_id} timed out")
                        session_state.status = SessionStatus.COMPLETED
                        break
                    
                    # Small delay to prevent busy waiting
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    await self._handle_session_error(session_state, config, e)
            
        except Exception as e:
            self.logger.error(f"Session lifecycle management failed for {session_id}: {e}")
            session_state.status = SessionStatus.FAILED
            session_state.last_error = str(e)
            await self._emit_event('session_error', session_state, e)
    
    async def _initialize_session(self, session_state: CallSessionState, config: CallSessionConfig):
        """Initialize session components"""
        try:
            self.logger.info(f"Initializing session {session_state.session_id}")
            
            # Initialize transcription service if needed
            if config.auto_transcribe:
                transcription_config = {}  # Add any needed config
                success = await self.transcription_service.initialize(transcription_config)
                if not success:
                    raise Exception("Failed to initialize transcription service")
            
            session_state.status = SessionStatus.JOINING
            await self._emit_event('session_initialized', session_state)
            
        except Exception as e:
            self.logger.error(f"Session initialization failed: {e}")
            raise
    
    async def _join_meeting(self, session_state: CallSessionState, config: CallSessionConfig):
        """Join the video meeting"""
        try:
            self.logger.info(f"Joining meeting for session {session_state.session_id}")
            
            # Join meeting using call bot service
            bot_session = await self.call_bot_service.join_meeting(
                config.meeting_url, 
                config.platform
            )
            
            session_state.bot_session = bot_session
            session_state.join_time = time.time()
            session_state.status = SessionStatus.CONNECTED
            
            await self._emit_event('meeting_joined', session_state)
            
        except Exception as e:
            self.logger.error(f"Failed to join meeting: {e}")
            raise
    
    async def _start_transcription(self, session_state: CallSessionState, config: CallSessionConfig):
        """Start transcription for the session"""
        try:
            if not config.auto_transcribe:
                session_state.status = SessionStatus.TRANSCRIBING
                return
            
            self.logger.info(f"Starting transcription for session {session_state.session_id}")
            
            # Start transcription
            transcription_session = await self.transcription_service.start_transcription(
                session_state.session_id,
                f"stream_{session_state.session_id}"
            )
            
            session_state.transcription_session_id = transcription_session.session_id
            session_state.status = SessionStatus.TRANSCRIBING
            
            await self._emit_event('transcription_started', session_state)
            
        except Exception as e:
            self.logger.error(f"Failed to start transcription: {e}")
            raise
    
    async def _monitor_session(self, session_state: CallSessionState, config: CallSessionConfig):
        """Monitor active session for issues"""
        try:
            # Check bot connection status
            if session_state.bot_session:
                bot_status = await self.call_bot_service.get_session_status(
                    session_state.bot_session.session_id
                )
                
                if bot_status and bot_status.get('status') == 'disconnected':
                    self.logger.warning(f"Bot disconnected for session {session_state.session_id}")
                    session_state.status = SessionStatus.DISCONNECTED
                    return
            
            # Check transcription status and save partial transcript
            if session_state.transcription_session_id and config.save_partial_transcripts:
                transcript = await self.transcription_service.get_full_transcript(
                    session_state.transcription_session_id
                )
                
                if transcript != session_state.partial_transcript:
                    session_state.partial_transcript = transcript
                    await self._save_session_data(session_state, final=False)
                
                # Update audio quality
                transcription_status = await self.transcription_service.get_session_status(
                    session_state.transcription_session_id
                )
                
                if transcription_status:
                    quality_str = transcription_status.get('audio_quality', 'good')
                    session_state.audio_quality = AudioQuality(quality_str)
            
            # Monitor for natural meeting end (could be enhanced with meeting duration checks)
            await asyncio.sleep(10.0)  # Check every 10 seconds
            
        except Exception as e:
            self.logger.error(f"Session monitoring failed: {e}")
            raise
    
    async def _handle_disconnection(self, session_state: CallSessionState, config: CallSessionConfig):
        """Handle session disconnection and retry logic"""
        try:
            self.logger.warning(f"Handling disconnection for session {session_state.session_id}")
            
            # Save partial transcript before retry
            if config.save_partial_transcripts and session_state.partial_transcript:
                await self._save_session_data(session_state, final=False)
            
            # Check retry limits
            if session_state.retry_count >= config.max_retry_attempts:
                self.logger.error(f"Max retry attempts reached for session {session_state.session_id}")
                session_state.status = SessionStatus.FAILED
                return
            
            # Wait before retry
            await asyncio.sleep(config.retry_delay)
            
            # Reset for retry
            session_state.retry_count += 1
            session_state.bot_session = None
            session_state.transcription_session_id = None
            session_state.status = SessionStatus.JOINING
            
            self.logger.info(f"Retrying session {session_state.session_id} (attempt {session_state.retry_count})")
            await self._emit_event('session_reconnecting', session_state)
            
        except Exception as e:
            self.logger.error(f"Disconnection handling failed: {e}")
            session_state.status = SessionStatus.FAILED
            raise
    
    async def _handle_session_error(self, session_state: CallSessionState, config: CallSessionConfig, error: Exception):
        """Handle session errors"""
        try:
            session_state.error_count += 1
            session_state.last_error = str(error)
            
            self.logger.error(f"Session error for {session_state.session_id}: {error}")
            
            # Save partial data before handling error
            if config.save_partial_transcripts and session_state.partial_transcript:
                await self._save_session_data(session_state, final=False)
            
            # Determine if error is recoverable
            recoverable_errors = [
                "connection_timeout",
                "network_error",
                "temporary_failure"
            ]
            
            error_str = str(error).lower()
            is_recoverable = any(err in error_str for err in recoverable_errors)
            
            if is_recoverable and session_state.retry_count < config.max_retry_attempts:
                session_state.status = SessionStatus.DISCONNECTED
                await self._emit_event('session_error_recoverable', session_state, error)
            else:
                session_state.status = SessionStatus.FAILED
                await self._emit_event('session_error_fatal', session_state, error)
            
        except Exception as e:
            self.logger.error(f"Error handling failed: {e}")
            session_state.status = SessionStatus.FAILED
    
    async def _save_session_data(self, session_state: CallSessionState, final: bool = False):
        """Save session data to database"""
        try:
            meeting = await sync_to_async(Meeting.objects.get)(id=session_state.meeting_id)
            meeting_session = await sync_to_async(MeetingSession.objects.get)(meeting=meeting)
            
            # Update transcript
            if session_state.partial_transcript:
                meeting_session.transcript = session_state.partial_transcript
            
            # Update session metadata
            session_metadata = {
                'session_id': session_state.session_id,
                'status': session_state.status.value,
                'retry_count': session_state.retry_count,
                'error_count': session_state.error_count,
                'audio_quality': session_state.audio_quality.value,
                'last_updated': time.time()
            }
            
            if not meeting_session.notes:
                meeting_session.notes = json.dumps(session_metadata)
            else:
                try:
                    notes_data = json.loads(meeting_session.notes)
                    notes_data.update(session_metadata)
                    meeting_session.notes = json.dumps(notes_data)
                except json.JSONDecodeError:
                    meeting_session.notes = json.dumps(session_metadata)
            
            # Mark as ended if final
            if final:
                meeting_session.ended_at = timezone.now()
            
            await sync_to_async(meeting_session.save)()
            
            self.logger.debug(f"Saved session data for {session_state.session_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save session data: {e}")
    
    async def _emit_event(self, event_type: str, session_state: CallSessionState, *args):
        """Emit session event to registered handlers"""
        try:
            if event_type in self.event_handlers:
                for handler in self.event_handlers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(session_state, *args)
                        else:
                            handler(session_state, *args)
                    except Exception as e:
                        self.logger.error(f"Event handler error for {event_type}: {e}")
        except Exception as e:
            self.logger.error(f"Event emission failed for {event_type}: {e}")
    
    async def cleanup(self):
        """Cleanup all active sessions"""
        try:
            self.logger.info("Cleaning up call session manager")
            
            # Stop all active sessions
            session_ids = list(self.active_sessions.keys())
            for session_id in session_ids:
                try:
                    await self.stop_call_session(session_id, "cleanup")
                except Exception as e:
                    self.logger.error(f"Error stopping session {session_id} during cleanup: {e}")
            
            # Cancel any remaining tasks
            for task in self.session_tasks.values():
                if not task.done():
                    task.cancel()
            
            self.session_tasks.clear()
            self.active_sessions.clear()
            
            self.logger.info("Call session manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Utility functions for session management
def create_session_manager(call_bot_service: CallBotService, transcription_service: TranscriptionService) -> CallSessionManager:
    """
    Factory function to create a configured CallSessionManager
    
    Args:
        call_bot_service: Initialized call bot service
        transcription_service: Initialized transcription service
        
    Returns:
        CallSessionManager: Configured session manager
    """
    return CallSessionManager(call_bot_service, transcription_service)


async def start_meeting_session(meeting_id: str, meeting_url: str, platform: str, 
                              session_manager: CallSessionManager) -> CallSessionState:
    """
    Convenience function to start a meeting session with default configuration
    
    Args:
        meeting_id: Meeting ID from database
        meeting_url: Video meeting URL
        platform: Meeting platform ('meet', 'teams', 'zoom')
        session_manager: Session manager instance
        
    Returns:
        CallSessionState: Started session state
    """
    config = CallSessionConfig(
        meeting_id=meeting_id,
        meeting_url=meeting_url,
        platform=platform,
        auto_join=True,
        auto_transcribe=True,
        save_partial_transcripts=True
    )
    
    return await session_manager.start_call_session(config)