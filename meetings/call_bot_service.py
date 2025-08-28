"""
Call Bot Service for multi-platform video call integration
Supports Google Meet, Microsoft Teams, and Zoom
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any, Callable
from urllib.parse import urlparse
import json

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Supported video call platforms"""
    GOOGLE_MEET = "meet"
    MICROSOFT_TEAMS = "teams"
    ZOOM = "zoom"


class ConnectionStatus(Enum):
    """Bot connection status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    TRANSCRIBING = "transcribing"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class BotSession:
    """Bot session data structure"""
    session_id: str
    meeting_url: str
    platform: Platform
    status: ConnectionStatus
    join_time: Optional[float] = None
    leave_time: Optional[float] = None
    error_message: Optional[str] = None
    reconnect_attempts: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'meeting_url': self.meeting_url,
            'platform': self.platform.value,
            'status': self.status.value,
            'join_time': self.join_time,
            'leave_time': self.leave_time,
            'error_message': self.error_message,
            'reconnect_attempts': self.reconnect_attempts
        }


@dataclass
class TranscriptionStream:
    """Transcription stream data structure"""
    session_id: str
    stream_id: str
    is_active: bool = True
    audio_quality: str = "good"
    speaker_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'stream_id': self.stream_id,
            'is_active': self.is_active,
            'audio_quality': self.audio_quality,
            'speaker_count': self.speaker_count
        }


class BasePlatformBot(ABC):
    """Abstract base class for platform-specific bots"""
    
    def __init__(self, platform: Platform):
        self.platform = platform
        self.logger = logging.getLogger(f"{__name__}.{platform.value}")
    
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with the platform"""
        pass
    
    @abstractmethod
    async def join_meeting(self, meeting_url: str, session_id: str) -> bool:
        """Join a meeting as a silent participant"""
        pass
    
    @abstractmethod
    async def start_transcription(self, session_id: str) -> str:
        """Start transcription and return stream ID"""
        pass
    
    @abstractmethod
    async def leave_meeting(self, session_id: str) -> bool:
        """Leave the meeting"""
        pass
    
    @abstractmethod
    async def get_connection_status(self, session_id: str) -> ConnectionStatus:
        """Get current connection status"""
        pass


class GoogleMeetBot(BasePlatformBot):
    """Google Meet bot implementation"""
    
    def __init__(self):
        super().__init__(Platform.GOOGLE_MEET)
        self.sessions: Dict[str, Dict] = {}
    
    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with Google Meet API"""
        try:
            # Mock authentication - in real implementation, use Google OAuth2
            self.logger.info("Authenticating with Google Meet")
            await asyncio.sleep(0.1)  # Simulate API call
            return True
        except Exception as e:
            self.logger.error(f"Google Meet authentication failed: {e}")
            return False
    
    async def join_meeting(self, meeting_url: str, session_id: str) -> bool:
        """Join Google Meet as silent participant"""
        try:
            self.logger.info(f"Joining Google Meet: {meeting_url}")
            
            # Mock joining logic - in real implementation, use Google Meet API
            await asyncio.sleep(0.5)  # Simulate connection time
            
            self.sessions[session_id] = {
                'url': meeting_url,
                'status': ConnectionStatus.CONNECTED,
                'join_time': time.time()
            }
            
            self.logger.info(f"Successfully joined Google Meet session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to join Google Meet: {e}")
            return False
    
    async def start_transcription(self, session_id: str) -> str:
        """Start transcription for Google Meet"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            stream_id = f"gmeet_stream_{session_id}_{int(time.time())}"
            self.sessions[session_id]['stream_id'] = stream_id
            self.sessions[session_id]['status'] = ConnectionStatus.TRANSCRIBING
            
            self.logger.info(f"Started transcription for session {session_id}")
            return stream_id
            
        except Exception as e:
            self.logger.error(f"Failed to start transcription: {e}")
            raise
    
    async def leave_meeting(self, session_id: str) -> bool:
        """Leave Google Meet"""
        try:
            if session_id in self.sessions:
                self.sessions[session_id]['status'] = ConnectionStatus.DISCONNECTED
                self.sessions[session_id]['leave_time'] = time.time()
                self.logger.info(f"Left Google Meet session {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error leaving Google Meet: {e}")
            return False
    
    async def get_connection_status(self, session_id: str) -> ConnectionStatus:
        """Get Google Meet connection status"""
        if session_id in self.sessions:
            return self.sessions[session_id]['status']
        return ConnectionStatus.DISCONNECTED


class MicrosoftTeamsBot(BasePlatformBot):
    """Microsoft Teams bot implementation"""
    
    def __init__(self):
        super().__init__(Platform.MICROSOFT_TEAMS)
        self.sessions: Dict[str, Dict] = {}
    
    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with Microsoft Teams API"""
        try:
            # Mock authentication - in real implementation, use Microsoft Graph API
            self.logger.info("Authenticating with Microsoft Teams")
            await asyncio.sleep(0.1)  # Simulate API call
            return True
        except Exception as e:
            self.logger.error(f"Teams authentication failed: {e}")
            return False
    
    async def join_meeting(self, meeting_url: str, session_id: str) -> bool:
        """Join Teams meeting as silent participant"""
        try:
            self.logger.info(f"Joining Teams meeting: {meeting_url}")
            
            # Mock joining logic - in real implementation, use Teams API
            await asyncio.sleep(0.7)  # Simulate connection time
            
            self.sessions[session_id] = {
                'url': meeting_url,
                'status': ConnectionStatus.CONNECTED,
                'join_time': time.time()
            }
            
            self.logger.info(f"Successfully joined Teams session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to join Teams meeting: {e}")
            return False
    
    async def start_transcription(self, session_id: str) -> str:
        """Start transcription for Teams"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            stream_id = f"teams_stream_{session_id}_{int(time.time())}"
            self.sessions[session_id]['stream_id'] = stream_id
            self.sessions[session_id]['status'] = ConnectionStatus.TRANSCRIBING
            
            self.logger.info(f"Started transcription for Teams session {session_id}")
            return stream_id
            
        except Exception as e:
            self.logger.error(f"Failed to start Teams transcription: {e}")
            raise
    
    async def leave_meeting(self, session_id: str) -> bool:
        """Leave Teams meeting"""
        try:
            if session_id in self.sessions:
                self.sessions[session_id]['status'] = ConnectionStatus.DISCONNECTED
                self.sessions[session_id]['leave_time'] = time.time()
                self.logger.info(f"Left Teams session {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error leaving Teams meeting: {e}")
            return False
    
    async def get_connection_status(self, session_id: str) -> ConnectionStatus:
        """Get Teams connection status"""
        if session_id in self.sessions:
            return self.sessions[session_id]['status']
        return ConnectionStatus.DISCONNECTED


class ZoomBot(BasePlatformBot):
    """Zoom bot implementation"""
    
    def __init__(self):
        super().__init__(Platform.ZOOM)
        self.sessions: Dict[str, Dict] = {}
    
    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with Zoom API"""
        try:
            # Mock authentication - in real implementation, use Zoom SDK/API
            self.logger.info("Authenticating with Zoom")
            await asyncio.sleep(0.1)  # Simulate API call
            return True
        except Exception as e:
            self.logger.error(f"Zoom authentication failed: {e}")
            return False
    
    async def join_meeting(self, meeting_url: str, session_id: str) -> bool:
        """Join Zoom meeting as silent participant"""
        try:
            self.logger.info(f"Joining Zoom meeting: {meeting_url}")
            
            # Mock joining logic - in real implementation, use Zoom SDK
            await asyncio.sleep(0.3)  # Simulate connection time
            
            self.sessions[session_id] = {
                'url': meeting_url,
                'status': ConnectionStatus.CONNECTED,
                'join_time': time.time()
            }
            
            self.logger.info(f"Successfully joined Zoom session {session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to join Zoom meeting: {e}")
            return False
    
    async def start_transcription(self, session_id: str) -> str:
        """Start transcription for Zoom"""
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            stream_id = f"zoom_stream_{session_id}_{int(time.time())}"
            self.sessions[session_id]['stream_id'] = stream_id
            self.sessions[session_id]['status'] = ConnectionStatus.TRANSCRIBING
            
            self.logger.info(f"Started transcription for Zoom session {session_id}")
            return stream_id
            
        except Exception as e:
            self.logger.error(f"Failed to start Zoom transcription: {e}")
            raise
    
    async def leave_meeting(self, session_id: str) -> bool:
        """Leave Zoom meeting"""
        try:
            if session_id in self.sessions:
                self.sessions[session_id]['status'] = ConnectionStatus.DISCONNECTED
                self.sessions[session_id]['leave_time'] = time.time()
                self.logger.info(f"Left Zoom session {session_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error leaving Zoom meeting: {e}")
            return False
    
    async def get_connection_status(self, session_id: str) -> ConnectionStatus:
        """Get Zoom connection status"""
        if session_id in self.sessions:
            return self.sessions[session_id]['status']
        return ConnectionStatus.DISCONNECTED


class CallBotService:
    """
    Main service class for managing video call bots across multiple platforms
    """
    
    MAX_RECONNECT_ATTEMPTS = 3
    RECONNECT_DELAY_BASE = 2  # Base delay in seconds for exponential backoff
    
    def __init__(self):
        self.bots: Dict[Platform, BasePlatformBot] = {
            Platform.GOOGLE_MEET: GoogleMeetBot(),
            Platform.MICROSOFT_TEAMS: MicrosoftTeamsBot(),
            Platform.ZOOM: ZoomBot()
        }
        self.sessions: Dict[str, BotSession] = {}
        self.status_callbacks: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
    
    def _detect_platform(self, meeting_url: str) -> Platform:
        """Detect platform from meeting URL"""
        parsed_url = urlparse(meeting_url.lower())
        domain = parsed_url.netloc
        
        if 'meet.google.com' in domain:
            return Platform.GOOGLE_MEET
        elif 'teams.microsoft.com' in domain or 'teams.live.com' in domain:
            return Platform.MICROSOFT_TEAMS
        elif 'zoom.us' in domain or 'zoom.com' in domain:
            return Platform.ZOOM
        else:
            raise ValueError(f"Unsupported meeting platform: {domain}")
    
    async def join_meeting(self, meeting_url: str, platform: Optional[str] = None) -> BotSession:
        """
        Join a meeting and return bot session
        
        Args:
            meeting_url: URL of the meeting to join
            platform: Optional platform override (auto-detected if not provided)
            
        Returns:
            BotSession object with session details
            
        Raises:
            ValueError: If platform is unsupported or URL is invalid
        """
        try:
            # Detect platform if not provided
            if platform:
                detected_platform = Platform(platform)
            else:
                detected_platform = self._detect_platform(meeting_url)
            
            # Generate session ID
            session_id = f"{detected_platform.value}_{int(time.time())}"
            
            # Create session object
            session = BotSession(
                session_id=session_id,
                meeting_url=meeting_url,
                platform=detected_platform,
                status=ConnectionStatus.CONNECTING
            )
            
            self.sessions[session_id] = session
            self.logger.info(f"Starting bot session {session_id} for {detected_platform.value}")
            
            # Get platform bot
            bot = self.bots[detected_platform]
            
            # Authenticate if needed
            auth_success = await bot.authenticate({})
            if not auth_success:
                session.status = ConnectionStatus.ERROR
                session.error_message = "Authentication failed"
                raise Exception("Bot authentication failed")
            
            # Join meeting
            join_success = await bot.join_meeting(meeting_url, session_id)
            if join_success:
                session.status = ConnectionStatus.CONNECTED
                session.join_time = time.time()
                self.logger.info(f"Bot successfully joined meeting {session_id}")
            else:
                session.status = ConnectionStatus.ERROR
                session.error_message = "Failed to join meeting"
                raise Exception("Failed to join meeting")
            
            return session
            
        except Exception as e:
            self.logger.error(f"Error joining meeting: {e}")
            if session_id in self.sessions:
                self.sessions[session_id].status = ConnectionStatus.ERROR
                self.sessions[session_id].error_message = str(e)
            raise
    
    async def start_transcription(self, session_id: str) -> TranscriptionStream:
        """
        Start transcription for a bot session
        
        Args:
            session_id: ID of the bot session
            
        Returns:
            TranscriptionStream object
            
        Raises:
            ValueError: If session not found or not connected
        """
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session = self.sessions[session_id]
            
            if session.status != ConnectionStatus.CONNECTED:
                raise ValueError(f"Session {session_id} is not connected")
            
            # Get platform bot
            bot = self.bots[session.platform]
            
            # Start transcription
            stream_id = await bot.start_transcription(session_id)
            
            # Update session status
            session.status = ConnectionStatus.TRANSCRIBING
            
            # Create transcription stream
            transcription_stream = TranscriptionStream(
                session_id=session_id,
                stream_id=stream_id,
                is_active=True
            )
            
            self.logger.info(f"Started transcription for session {session_id}")
            return transcription_stream
            
        except Exception as e:
            self.logger.error(f"Error starting transcription: {e}")
            raise
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a bot session and leave the meeting
        
        Args:
            session_id: ID of the bot session to end
            
        Returns:
            Dictionary with session summary
        """
        try:
            if session_id not in self.sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session = self.sessions[session_id]
            
            # Get platform bot
            bot = self.bots[session.platform]
            
            # Leave meeting
            leave_success = await bot.leave_meeting(session_id)
            
            # Update session
            session.status = ConnectionStatus.DISCONNECTED
            session.leave_time = time.time()
            
            # Calculate session duration
            duration = None
            if session.join_time and session.leave_time:
                duration = session.leave_time - session.join_time
            
            session_summary = {
                'session_id': session_id,
                'platform': session.platform.value,
                'duration': duration,
                'leave_success': leave_success,
                'reconnect_attempts': session.reconnect_attempts
            }
            
            self.logger.info(f"Ended bot session {session_id}")
            return session_summary
            
        except Exception as e:
            self.logger.error(f"Error ending session: {e}")
            raise
    
    async def handle_disconnection(self, session_id: str) -> bool:
        """
        Handle unexpected disconnection with reconnection logic
        
        Args:
            session_id: ID of the disconnected session
            
        Returns:
            True if reconnection successful, False otherwise
        """
        try:
            if session_id not in self.sessions:
                self.logger.warning(f"Session {session_id} not found for reconnection")
                return False
            
            session = self.sessions[session_id]
            
            if session.reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
                self.logger.error(f"Max reconnection attempts reached for session {session_id}")
                session.status = ConnectionStatus.ERROR
                session.error_message = "Max reconnection attempts exceeded"
                return False
            
            session.reconnect_attempts += 1
            session.status = ConnectionStatus.RECONNECTING
            
            # Exponential backoff delay
            delay = self.RECONNECT_DELAY_BASE ** session.reconnect_attempts
            self.logger.info(f"Reconnecting session {session_id} in {delay} seconds (attempt {session.reconnect_attempts})")
            
            await asyncio.sleep(delay)
            
            # Get platform bot
            bot = self.bots[session.platform]
            
            # Attempt to rejoin
            join_success = await bot.join_meeting(session.meeting_url, session_id)
            
            if join_success:
                session.status = ConnectionStatus.CONNECTED
                self.logger.info(f"Successfully reconnected session {session_id}")
                return True
            else:
                self.logger.warning(f"Reconnection failed for session {session_id}")
                # Will retry on next disconnection event
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling disconnection for session {session_id}: {e}")
            return False
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a bot session
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with session status or None if not found
        """
        if session_id in self.sessions:
            return self.sessions[session_id].to_dict()
        return None
    
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active bot sessions
        
        Returns:
            Dictionary of active sessions
        """
        active_sessions = {}
        for session_id, session in self.sessions.items():
            if session.status in [ConnectionStatus.CONNECTED, ConnectionStatus.TRANSCRIBING, ConnectionStatus.RECONNECTING]:
                active_sessions[session_id] = session.to_dict()
        
        return active_sessions
    
    def register_status_callback(self, session_id: str, callback: Callable):
        """
        Register a callback for status updates
        
        Args:
            session_id: ID of the session to monitor
            callback: Function to call on status changes
        """
        self.status_callbacks[session_id] = callback
    
    async def monitor_connections(self):
        """
        Monitor all active connections and handle disconnections
        This should be run as a background task
        """
        while True:
            try:
                for session_id, session in self.sessions.items():
                    if session.status in [ConnectionStatus.CONNECTED, ConnectionStatus.TRANSCRIBING]:
                        # Check connection status with platform bot
                        bot = self.bots[session.platform]
                        current_status = await bot.get_connection_status(session_id)
                        
                        if current_status == ConnectionStatus.DISCONNECTED:
                            self.logger.warning(f"Detected disconnection for session {session_id}")
                            await self.handle_disconnection(session_id)
                
                # Sleep before next check
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(30)  # Wait longer on error