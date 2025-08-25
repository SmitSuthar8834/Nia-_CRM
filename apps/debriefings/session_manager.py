"""
Debriefing session management with timeout and recovery mechanisms
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from channels.db import database_sync_to_async

from .models import DebriefingSession, DebriefingQuestion
# from apps.analytics.models import DebriefingMetrics  # Will be added later

logger = logging.getLogger(__name__)


class DebriefingSessionManager:
    """
    Manages debriefing session lifecycle, state, and recovery
    """
    
    def __init__(self, session: DebriefingSession):
        self.session = session
        self.session_timeout = 30 * 60  # 30 minutes
        self.inactivity_timeout = 10 * 60  # 10 minutes
        self.cache_prefix = f"debriefing_session_{session.id}"
    
    async def start_session(self) -> bool:
        """Start a debriefing session"""
        try:
            if self.session.status != 'scheduled':
                logger.warning(f"Cannot start session {self.session.id} - status is {self.session.status}")
                return False
            
            # Update session status
            await self._update_session_status('in_progress')
            
            # Initialize session state in cache
            await self._initialize_session_cache()
            
            # Record session start metrics
            await self._record_session_metric('session_started')
            
            logger.info(f"Started debriefing session {self.session.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting session {self.session.id}: {str(e)}")
            return False
    
    @database_sync_to_async
    def _update_session_status(self, status: str):
        """Update session status in database"""
        self.session.status = status
        if status == 'in_progress' and not self.session.started_at:
            self.session.started_at = timezone.now()
        elif status == 'completed' and not self.session.completed_at:
            self.session.completed_at = timezone.now()
        self.session.save()
    
    async def _initialize_session_cache(self):
        """Initialize session state in cache"""
        session_state = {
            'session_id': str(self.session.id),
            'status': self.session.status,
            'started_at': self.session.started_at.isoformat() if self.session.started_at else None,
            'last_activity': timezone.now().isoformat(),
            'current_question_index': 0,
            'answered_questions': [],
            'active_connections': 0,
            'timeout_warnings_sent': 0
        }
        
        cache.set(
            f"{self.cache_prefix}_state",
            session_state,
            timeout=self.session_timeout + 300  # Cache timeout slightly longer than session
        )
    
    async def update_activity(self, activity_type: str = 'general', metadata: Dict[str, Any] = None):
        """Update last activity timestamp"""
        try:
            # Update cache
            session_state = cache.get(f"{self.cache_prefix}_state", {})
            session_state['last_activity'] = timezone.now().isoformat()
            
            if metadata:
                session_state.update(metadata)
            
            cache.set(f"{self.cache_prefix}_state", session_state, timeout=self.session_timeout + 300)
            
            # Record activity metric
            await self._record_session_metric('activity_update', {
                'activity_type': activity_type,
                'metadata': metadata or {}
            })
            
        except Exception as e:
            logger.error(f"Error updating activity for session {self.session.id}: {str(e)}")
    
    async def check_session_timeout(self) -> Dict[str, Any]:
        """Check if session has timed out"""
        try:
            session_state = cache.get(f"{self.cache_prefix}_state", {})
            
            if not session_state:
                return {'timed_out': True, 'reason': 'cache_expired'}
            
            last_activity_str = session_state.get('last_activity')
            if not last_activity_str:
                return {'timed_out': True, 'reason': 'no_activity_recorded'}
            
            last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
            now = timezone.now()
            
            # Check for session timeout
            if (now - last_activity).total_seconds() > self.session_timeout:
                return {
                    'timed_out': True,
                    'reason': 'session_timeout',
                    'inactive_minutes': int((now - last_activity).total_seconds() / 60)
                }
            
            # Check for inactivity warning
            if (now - last_activity).total_seconds() > self.inactivity_timeout:
                warnings_sent = session_state.get('timeout_warnings_sent', 0)
                if warnings_sent < 3:  # Maximum 3 warnings
                    return {
                        'timed_out': False,
                        'warning': True,
                        'inactive_minutes': int((now - last_activity).total_seconds() / 60),
                        'warnings_sent': warnings_sent
                    }
            
            return {'timed_out': False}
            
        except Exception as e:
            logger.error(f"Error checking session timeout: {str(e)}")
            return {'timed_out': True, 'reason': 'error_checking_timeout'}
    
    async def handle_timeout_warning(self) -> bool:
        """Handle timeout warning"""
        try:
            session_state = cache.get(f"{self.cache_prefix}_state", {})
            warnings_sent = session_state.get('timeout_warnings_sent', 0)
            
            session_state['timeout_warnings_sent'] = warnings_sent + 1
            cache.set(f"{self.cache_prefix}_state", session_state, timeout=self.session_timeout + 300)
            
            await self._record_session_metric('timeout_warning', {
                'warnings_sent': warnings_sent + 1
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling timeout warning: {str(e)}")
            return False
    
    async def handle_session_timeout(self) -> Dict[str, Any]:
        """Handle session timeout"""
        try:
            # Save current state
            await self._save_session_state()
            
            # Update session status
            await self._update_session_status('expired')
            
            # Clear cache
            cache.delete(f"{self.cache_prefix}_state")
            
            # Record timeout metrics
            await self._record_session_metric('session_timeout')
            
            # Check if session can be recovered
            recovery_info = await self._get_recovery_info()
            
            logger.info(f"Session {self.session.id} timed out")
            
            return {
                'timed_out': True,
                'recovery_available': recovery_info['can_recover'],
                'recovery_info': recovery_info
            }
            
        except Exception as e:
            logger.error(f"Error handling session timeout: {str(e)}")
            return {'timed_out': True, 'recovery_available': False}
    
    async def _save_session_state(self):
        """Save current session state to database"""
        try:
            session_state = cache.get(f"{self.cache_prefix}_state", {})
            
            # Update conversation data with current state
            conversation_data = self.session.conversation_data or {}
            conversation_data.update({
                'last_activity': session_state.get('last_activity'),
                'session_state_at_timeout': session_state,
                'timeout_timestamp': timezone.now().isoformat()
            })
            
            await self._update_conversation_data(conversation_data)
            
        except Exception as e:
            logger.error(f"Error saving session state: {str(e)}")
    
    @database_sync_to_async
    def _update_conversation_data(self, conversation_data: Dict[str, Any]):
        """Update conversation data in database"""
        self.session.conversation_data = conversation_data
        self.session.save()
    
    async def _get_recovery_info(self) -> Dict[str, Any]:
        """Get information about session recovery possibilities"""
        try:
            answered_count = await self._get_answered_questions_count()
            total_questions = await self._get_total_questions_count()
            
            can_recover = answered_count > 0 and answered_count < total_questions
            
            return {
                'can_recover': can_recover,
                'answered_questions': answered_count,
                'total_questions': total_questions,
                'progress_percentage': (answered_count / total_questions * 100) if total_questions > 0 else 0,
                'recovery_deadline': (timezone.now() + timedelta(hours=24)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting recovery info: {str(e)}")
            return {'can_recover': False}
    
    @database_sync_to_async
    def _get_answered_questions_count(self) -> int:
        """Get count of answered questions"""
        return DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=False
        ).count()
    
    @database_sync_to_async
    def _get_total_questions_count(self) -> int:
        """Get total questions count"""
        return DebriefingQuestion.objects.filter(session=self.session).count()
    
    async def recover_session(self) -> Dict[str, Any]:
        """Recover a timed-out session"""
        try:
            # Check if recovery is possible
            recovery_info = await self._get_recovery_info()
            
            if not recovery_info['can_recover']:
                return {
                    'recovered': False,
                    'reason': 'recovery_not_possible'
                }
            
            # Check recovery deadline
            timeout_data = self.session.conversation_data.get('timeout_timestamp')
            if timeout_data:
                timeout_time = datetime.fromisoformat(timeout_data.replace('Z', '+00:00'))
                if timezone.now() - timeout_time > timedelta(hours=24):
                    return {
                        'recovered': False,
                        'reason': 'recovery_deadline_expired'
                    }
            
            # Restore session
            await self._update_session_status('in_progress')
            await self._initialize_session_cache()
            
            # Get next question
            next_question = await self._get_next_question()
            
            await self._record_session_metric('session_recovered')
            
            logger.info(f"Recovered session {self.session.id}")
            
            return {
                'recovered': True,
                'next_question_id': str(next_question.id) if next_question else None,
                'recovery_info': recovery_info
            }
            
        except Exception as e:
            logger.error(f"Error recovering session {self.session.id}: {str(e)}")
            return {
                'recovered': False,
                'reason': 'recovery_error',
                'error': str(e)
            }
    
    @database_sync_to_async
    def _get_next_question(self) -> Optional[DebriefingQuestion]:
        """Get next unanswered question"""
        return DebriefingQuestion.objects.filter(
            session=self.session,
            user_response__isnull=True
        ).order_by('question_order').first()
    
    async def complete_session(self, completion_data: Dict[str, Any] = None) -> bool:
        """Complete the debriefing session"""
        try:
            # Update session status
            await self._update_session_status('completed')
            
            # Update meeting status
            await self._update_meeting_completion()
            
            # Save completion data
            if completion_data:
                await self._save_completion_data(completion_data)
            
            # Clear cache
            cache.delete(f"{self.cache_prefix}_state")
            
            # Record completion metrics
            await self._record_session_metric('session_completed', {
                'duration_minutes': self.session.duration_minutes,
                'completion_data': completion_data or {}
            })
            
            logger.info(f"Completed session {self.session.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error completing session {self.session.id}: {str(e)}")
            return False
    
    @database_sync_to_async
    def _update_meeting_completion(self):
        """Update meeting debriefing completion status"""
        self.session.meeting.debriefing_completed = True
        self.session.meeting.save()
    
    @database_sync_to_async
    def _save_completion_data(self, completion_data: Dict[str, Any]):
        """Save session completion data"""
        conversation_data = self.session.conversation_data or {}
        conversation_data['completion_data'] = completion_data
        conversation_data['completed_at'] = timezone.now().isoformat()
        
        self.session.conversation_data = conversation_data
        self.session.save()
    
    async def get_session_analytics(self) -> Dict[str, Any]:
        """Get session analytics and metrics"""
        try:
            session_state = cache.get(f"{self.cache_prefix}_state", {})
            answered_count = await self._get_answered_questions_count()
            total_questions = await self._get_total_questions_count()
            
            analytics = {
                'session_id': str(self.session.id),
                'status': self.session.status,
                'duration_minutes': self.session.duration_minutes,
                'progress': {
                    'answered_questions': answered_count,
                    'total_questions': total_questions,
                    'completion_percentage': (answered_count / total_questions * 100) if total_questions > 0 else 0
                },
                'activity': {
                    'last_activity': session_state.get('last_activity'),
                    'timeout_warnings': session_state.get('timeout_warnings_sent', 0),
                    'active_connections': session_state.get('active_connections', 0)
                },
                'insights_generated': await self._get_insights_count(),
                'extraction_confidence': self._get_extraction_confidence()
            }
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting session analytics: {str(e)}")
            return {}
    
    @database_sync_to_async
    def _get_insights_count(self) -> int:
        """Get count of insights generated"""
        return self.session.insights.count()
    
    def _get_extraction_confidence(self) -> float:
        """Get average extraction confidence score"""
        confidence_scores = self.session.confidence_scores or {}
        if not confidence_scores:
            return 0.0
        
        scores = [score for score in confidence_scores.values() if isinstance(score, (int, float))]
        return sum(scores) / len(scores) if scores else 0.0
    
    @database_sync_to_async
    def _record_session_metric(self, metric_type: str, metric_data: Dict[str, Any] = None):
        """Record session metrics"""
        try:
            # TODO: Implement metrics recording
            logger.info(f"Session {self.session.id} metric: {metric_type}")
        except Exception as e:
            logger.error(f"Error recording session metric: {str(e)}")
    
    async def export_session_data(self) -> Dict[str, Any]:
        """Export complete session data for review"""
        try:
            # Get all questions and responses
            questions_data = await self._get_questions_export_data()
            
            # Get insights
            insights_data = await self._get_insights_export_data()
            
            # Get session analytics
            analytics = await self.get_session_analytics()
            
            export_data = {
                'session_info': {
                    'session_id': str(self.session.id),
                    'meeting_title': self.session.meeting.title,
                    'meeting_date': self.session.meeting.start_time.isoformat(),
                    'status': self.session.status,
                    'started_at': self.session.started_at.isoformat() if self.session.started_at else None,
                    'completed_at': self.session.completed_at.isoformat() if self.session.completed_at else None,
                    'duration_minutes': self.session.duration_minutes
                },
                'conversation': {
                    'questions_and_responses': questions_data,
                    'total_questions': len(questions_data),
                    'answered_questions': len([q for q in questions_data if q['response']])
                },
                'extracted_data': self.session.extracted_data or {},
                'insights': insights_data,
                'analytics': analytics,
                'export_timestamp': timezone.now().isoformat()
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting session data: {str(e)}")
            return {}
    
    @database_sync_to_async
    def _get_questions_export_data(self) -> List[Dict[str, Any]]:
        """Get questions and responses for export"""
        questions_data = []
        
        for question in DebriefingQuestion.objects.filter(session=self.session).order_by('question_order'):
            questions_data.append({
                'question_id': str(question.id),
                'question_order': question.question_order,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'is_follow_up': question.is_follow_up,
                'response': question.user_response,
                'response_timestamp': question.response_timestamp.isoformat() if question.response_timestamp else None,
                'extracted_entities': question.extracted_entities,
                'processed': question.processed
            })
        
        return questions_data
    
    @database_sync_to_async
    def _get_insights_export_data(self) -> List[Dict[str, Any]]:
        """Get insights for export"""
        insights_data = []
        
        for insight in self.session.insights.all():
            insights_data.append({
                'insight_id': str(insight.id),
                'type': insight.insight_type,
                'title': insight.title,
                'description': insight.description,
                'confidence_level': insight.confidence_level,
                'confidence_score': insight.confidence_score,
                'suggested_actions': insight.suggested_actions,
                'priority': insight.priority,
                'user_validated': insight.user_validated,
                'created_at': insight.created_at.isoformat()
            })
        
        return insights_data


class SessionConnectionManager:
    """
    Manages WebSocket connections for debriefing sessions
    """
    
    def __init__(self):
        self.active_connections = {}  # session_id -> list of channel names
    
    def add_connection(self, session_id: str, channel_name: str):
        """Add a WebSocket connection for a session"""
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        
        if channel_name not in self.active_connections[session_id]:
            self.active_connections[session_id].append(channel_name)
        
        # Update cache
        self._update_connection_cache(session_id)
    
    def remove_connection(self, session_id: str, channel_name: str):
        """Remove a WebSocket connection for a session"""
        if session_id in self.active_connections:
            if channel_name in self.active_connections[session_id]:
                self.active_connections[session_id].remove(channel_name)
            
            # Clean up empty session entries
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        # Update cache
        self._update_connection_cache(session_id)
    
    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session"""
        return len(self.active_connections.get(session_id, []))
    
    def _update_connection_cache(self, session_id: str):
        """Update connection count in cache"""
        try:
            cache_key = f"debriefing_session_{session_id}_state"
            session_state = cache.get(cache_key, {})
            session_state['active_connections'] = self.get_connection_count(session_id)
            cache.set(cache_key, session_state, timeout=30 * 60 + 300)
        except Exception as e:
            logger.error(f"Error updating connection cache: {str(e)}")


# Global connection manager instance
connection_manager = SessionConnectionManager()