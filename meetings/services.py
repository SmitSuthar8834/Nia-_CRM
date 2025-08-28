"""
Meeting session management services
"""
import json
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from .models import Meeting, MeetingSession, ActionItem

logger = logging.getLogger(__name__)


class MeetingSessionService:
    """
    Service for managing meeting sessions with Redis caching and auto-save functionality
    """
    
    CACHE_PREFIX = "meeting_session"
    CACHE_TIMEOUT = 3600  # 1 hour
    AUTO_SAVE_INTERVAL = 30  # 30 seconds
    
    def __init__(self):
        self.cache = cache
    
    def _get_cache_key(self, session_id: int) -> str:
        """Generate cache key for meeting session"""
        return f"{self.CACHE_PREFIX}:{session_id}"
    
    def initialize_session(self, meeting_id: int, ai_session_id: str = "") -> MeetingSession:
        """
        Initialize a new meeting session with Redis caching
        """
        try:
            with transaction.atomic():
                meeting = Meeting.objects.select_for_update().get(id=meeting_id)
                
                # Check if session already exists
                if hasattr(meeting, 'meetingsession'):
                    raise ValueError("Meeting session already exists")
                
                # Create new session
                session = MeetingSession.objects.create(
                    meeting=meeting,
                    ai_session_id=ai_session_id,
                    started_at=timezone.now()
                )
                
                # Update meeting status
                meeting.status = 'in_progress'
                meeting.save()
                
                # Cache session data
                self._cache_session_data(session)
                
                logger.info(f"Initialized meeting session {session.id} for meeting {meeting_id}")
                return session
                
        except Meeting.DoesNotExist:
            raise ValueError(f"Meeting with id {meeting_id} does not exist")
        except Exception as e:
            logger.error(f"Error initializing session for meeting {meeting_id}: {str(e)}")
            raise
    
    def get_session_state(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get session state from cache or database
        """
        cache_key = self._get_cache_key(session_id)
        
        # Try to get from cache first
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug(f"Retrieved session {session_id} from cache")
            return cached_data
        
        # Fallback to database
        try:
            session = MeetingSession.objects.select_related('meeting').get(id=session_id)
            session_data = self._serialize_session(session)
            
            # Cache the data
            self.cache.set(cache_key, session_data, self.CACHE_TIMEOUT)
            logger.debug(f"Retrieved session {session_id} from database and cached")
            return session_data
            
        except MeetingSession.DoesNotExist:
            logger.warning(f"Session {session_id} not found")
            return None
    
    def update_session_notes(self, session_id: int, notes: str, auto_save: bool = True) -> bool:
        """
        Update session notes with auto-save functionality
        """
        try:
            cache_key = self._get_cache_key(session_id)
            
            # Get current session data
            session_data = self.get_session_state(session_id)
            if not session_data:
                return False
            
            # Update notes in cache
            session_data['notes'] = notes
            session_data['last_updated'] = timezone.now().isoformat()
            self.cache.set(cache_key, session_data, self.CACHE_TIMEOUT)
            
            if auto_save:
                # Auto-save to database
                self._auto_save_to_database(session_id, session_data)
            
            logger.debug(f"Updated notes for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating notes for session {session_id}: {str(e)}")
            return False
    
    def update_session_transcript(self, session_id: int, transcript: str) -> bool:
        """
        Update session transcript
        """
        try:
            cache_key = self._get_cache_key(session_id)
            
            # Get current session data
            session_data = self.get_session_state(session_id)
            if not session_data:
                return False
            
            # Update transcript in cache
            session_data['transcript'] = transcript
            session_data['last_updated'] = timezone.now().isoformat()
            self.cache.set(cache_key, session_data, self.CACHE_TIMEOUT)
            
            logger.debug(f"Updated transcript for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating transcript for session {session_id}: {str(e)}")
            return False
    
    def add_action_item(self, session_id: int, description: str, assignee: str, due_date=None) -> bool:
        """
        Add action item to session
        """
        try:
            session = MeetingSession.objects.get(id=session_id)
            
            action_item = ActionItem.objects.create(
                meeting_session=session,
                description=description,
                assignee=assignee,
                due_date=due_date
            )
            
            # Update cached session data
            self._refresh_session_cache(session_id)
            
            logger.info(f"Added action item {action_item.id} to session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding action item to session {session_id}: {str(e)}")
            return False
    
    def end_session(self, session_id: int, notes: str = "", summary: str = "") -> bool:
        """
        End meeting session and save final data
        """
        try:
            with transaction.atomic():
                session = MeetingSession.objects.select_for_update().get(id=session_id)
                
                if session.ended_at:
                    raise ValueError("Session already ended")
                
                # Update session
                session.ended_at = timezone.now()
                if notes:
                    session.notes = notes
                if summary:
                    session.summary = summary
                session.save()
                
                # Update meeting status
                meeting = session.meeting
                meeting.status = 'completed'
                meeting.save()
                
                # Clear cache
                cache_key = self._get_cache_key(session_id)
                self.cache.delete(cache_key)
                
                logger.info(f"Ended session {session_id}")
                return True
                
        except MeetingSession.DoesNotExist:
            logger.error(f"Session {session_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {str(e)}")
            return False
    
    def _cache_session_data(self, session: MeetingSession):
        """
        Cache session data in Redis
        """
        cache_key = self._get_cache_key(session.id)
        session_data = self._serialize_session(session)
        self.cache.set(cache_key, session_data, self.CACHE_TIMEOUT)
    
    def _serialize_session(self, session: MeetingSession) -> Dict[str, Any]:
        """
        Serialize session data for caching
        """
        return {
            'id': session.id,
            'meeting_id': session.meeting.id,
            'ai_session_id': session.ai_session_id,
            'notes': session.notes,
            'transcript': session.transcript,
            'action_items': list(session.actionitem_set.values(
                'id', 'description', 'assignee', 'due_date', 'status'
            )),
            'summary': session.summary,
            'started_at': session.started_at.isoformat(),
            'ended_at': session.ended_at.isoformat() if session.ended_at else None,
            'is_active': session.is_active,
            'last_updated': timezone.now().isoformat()
        }
    
    def _auto_save_to_database(self, session_id: int, session_data: Dict[str, Any]):
        """
        Auto-save session data to database
        """
        try:
            session = MeetingSession.objects.get(id=session_id)
            session.notes = session_data.get('notes', session.notes)
            session.transcript = session_data.get('transcript', session.transcript)
            session.save(update_fields=['notes', 'transcript'])
            
            logger.debug(f"Auto-saved session {session_id} to database")
            
        except Exception as e:
            logger.error(f"Error auto-saving session {session_id}: {str(e)}")
    
    def _refresh_session_cache(self, session_id: int):
        """
        Refresh session cache from database
        """
        try:
            session = MeetingSession.objects.select_related('meeting').get(id=session_id)
            self._cache_session_data(session)
            
        except Exception as e:
            logger.error(f"Error refreshing cache for session {session_id}: {str(e)}")
    
    def force_save_session(self, session_id: int) -> bool:
        """
        Force save cached session data to database
        """
        try:
            session_data = self.get_session_state(session_id)
            if not session_data:
                return False
            
            self._auto_save_to_database(session_id, session_data)
            return True
            
        except Exception as e:
            logger.error(f"Error force saving session {session_id}: {str(e)}")
            return False
    
    def cleanup_expired_sessions(self):
        """
        Cleanup expired session cache entries
        """
        # This would typically be called by a periodic task
        # For now, we rely on Redis TTL to handle cleanup
        pass