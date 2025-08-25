"""
WebSocket consumers for real-time debriefing conversations
"""
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight
from .conversation_flow import ConversationFlowManager
from .session_manager import DebriefingSessionManager
from .ai_integration import DebriefingAIService

logger = logging.getLogger(__name__)


class DebriefingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time debriefing conversations
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.user = None
        self.session = None
        self.flow_manager = None
        self.session_manager = None
        self.ai_service = None
        self.heartbeat_task = None
        self.session_timeout_task = None
        self.timeout_duration = 30 * 60  # 30 minutes
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Extract session ID from URL
            self.session_id = self.scope['url_route']['kwargs']['session_id']
            self.user = self.scope['user']
            
            if not self.user.is_authenticated:
                await self.close(code=4001)  # Unauthorized
                return
            
            # Validate and load session
            self.session = await self.get_session()
            if not self.session:
                await self.close(code=4004)  # Not found
                return
            
            # Check user permissions
            if not await self.check_permissions():
                await self.close(code=4003)  # Forbidden
                return
            
            # Initialize services
            self.flow_manager = ConversationFlowManager(self.session)
            self.session_manager = DebriefingSessionManager(self.session)
            self.ai_service = DebriefingAIService()
            
            # Join session group
            await self.channel_layer.group_add(
                f"debriefing_{self.session_id}",
                self.channel_name
            )
            
            await self.accept()
            
            # Start session if not already started
            if self.session.status == 'scheduled':
                await self.start_session()
            
            # Send initial state
            await self.send_session_state()
            
            # Start heartbeat and timeout monitoring
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            self.session_timeout_task = asyncio.create_task(self.session_timeout_monitor())
            
            logger.info(f"WebSocket connected for debriefing session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error connecting to debriefing session: {str(e)}")
            await self.close(code=4000)  # Bad request
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Cancel background tasks
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            if self.session_timeout_task:
                self.session_timeout_task.cancel()
            
            # Leave session group
            if self.session_id:
                await self.channel_layer.group_discard(
                    f"debriefing_{self.session_id}",
                    self.channel_name
                )
            
            # Save session state if needed
            if self.session and self.session.status == 'in_progress':
                await self.save_session_state()
            
            logger.info(f"WebSocket disconnected from debriefing session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting from debriefing session: {str(e)}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'response':
                await self.handle_user_response(data)
            elif message_type == 'skip_question':
                await self.handle_skip_question(data)
            elif message_type == 'request_clarification':
                await self.handle_clarification_request(data)
            elif message_type == 'complete_session':
                await self.handle_complete_session(data)
            elif message_type == 'heartbeat':
                await self.handle_heartbeat(data)
            elif message_type == 'get_state':
                await self.send_session_state()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
            await self.send_error("Internal server error")
    
    async def handle_user_response(self, data: Dict[str, Any]):
        """Handle user response to a question"""
        try:
            question_id = data.get('question_id')
            response_text = data.get('response', '').strip()
            
            if not question_id or not response_text:
                await self.send_error("Question ID and response are required")
                return
            
            # Get current question
            question = await self.get_question(question_id)
            if not question:
                await self.send_error("Question not found")
                return
            
            # Record response
            await self.record_response(question, response_text)
            
            # Process response with AI
            await self.send_message({
                'type': 'processing',
                'message': 'Processing your response...'
            })
            
            processing_result = await self.process_response(question, response_text)
            
            # Generate follow-up questions if needed
            follow_up_questions = await self.generate_follow_up_questions(
                question, response_text, processing_result
            )
            
            # Get next question or complete session
            next_question = await self.get_next_question(follow_up_questions)
            
            if next_question:
                await self.send_question(next_question)
            else:
                await self.handle_conversation_complete()
                
        except Exception as e:
            logger.error(f"Error handling user response: {str(e)}")
            await self.send_error("Error processing response")
    
    async def handle_skip_question(self, data: Dict[str, Any]):
        """Handle user skipping a question"""
        try:
            question_id = data.get('question_id')
            reason = data.get('reason', 'user_skip')
            
            question = await self.get_question(question_id)
            if not question:
                await self.send_error("Question not found")
                return
            
            # Mark question as skipped
            await self.skip_question(question, reason)
            
            # Get next question
            next_question = await self.get_next_question()
            
            if next_question:
                await self.send_question(next_question)
            else:
                await self.handle_conversation_complete()
                
        except Exception as e:
            logger.error(f"Error handling skip question: {str(e)}")
            await self.send_error("Error skipping question")
    
    async def handle_clarification_request(self, data: Dict[str, Any]):
        """Handle user request for question clarification"""
        try:
            question_id = data.get('question_id')
            clarification_type = data.get('clarification_type', 'general')
            
            question = await self.get_question(question_id)
            if not question:
                await self.send_error("Question not found")
                return
            
            # Generate clarification using AI
            clarification = await self.generate_clarification(question, clarification_type)
            
            await self.send_message({
                'type': 'clarification',
                'question_id': question_id,
                'clarification': clarification
            })
            
        except Exception as e:
            logger.error(f"Error handling clarification request: {str(e)}")
            await self.send_error("Error generating clarification")
    
    async def handle_complete_session(self, data: Dict[str, Any]):
        """Handle manual session completion"""
        try:
            # Validate session can be completed
            if self.session.status != 'in_progress':
                await self.send_error("Session is not in progress")
                return
            
            # Complete the session
            await self.complete_session()
            
            await self.send_message({
                'type': 'session_completed',
                'message': 'Debriefing session completed successfully'
            })
            
        except Exception as e:
            logger.error(f"Error completing session: {str(e)}")
            await self.send_error("Error completing session")
    
    async def handle_heartbeat(self, data: Dict[str, Any]):
        """Handle heartbeat message to keep connection alive"""
        await self.send_message({
            'type': 'heartbeat_ack',
            'timestamp': timezone.now().isoformat()
        })
    
    async def send_question(self, question: DebriefingQuestion):
        """Send a question to the client"""
        await self.send_message({
            'type': 'question',
            'question_id': str(question.id),
            'question_text': question.question_text,
            'question_type': question.question_type,
            'question_order': question.question_order,
            'is_follow_up': question.is_follow_up,
            'context': question.ai_context,
            'total_questions': await self.get_total_questions(),
            'current_question': question.question_order
        })
    
    async def send_session_state(self):
        """Send current session state to client"""
        state = await self.get_session_state()
        await self.send_message({
            'type': 'session_state',
            'state': state
        })
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket client"""
        await self.send(text_data=json.dumps(message))
    
    async def send_error(self, error_message: str):
        """Send error message to client"""
        await self.send_message({
            'type': 'error',
            'error': error_message,
            'timestamp': timezone.now().isoformat()
        })
    
    async def heartbeat_loop(self):
        """Send periodic heartbeat messages"""
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                await self.send_message({
                    'type': 'heartbeat',
                    'timestamp': timezone.now().isoformat()
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {str(e)}")
    
    async def session_timeout_monitor(self):
        """Monitor session for timeout"""
        try:
            await asyncio.sleep(self.timeout_duration)
            
            # Check if session is still active
            if self.session and self.session.status == 'in_progress':
                await self.handle_session_timeout()
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in session timeout monitor: {str(e)}")
    
    async def handle_session_timeout(self):
        """Handle session timeout"""
        try:
            # Save current state
            await self.save_session_state()
            
            # Send timeout message
            await self.send_message({
                'type': 'session_timeout',
                'message': 'Session timed out due to inactivity',
                'recovery_available': True
            })
            
            # Close connection
            await self.close(code=4008)  # Policy violation (timeout)
            
        except Exception as e:
            logger.error(f"Error handling session timeout: {str(e)}")
    
    # Database operations (async wrappers)
    
    @database_sync_to_async
    def get_session(self) -> Optional[DebriefingSession]:
        """Get debriefing session"""
        try:
            return DebriefingSession.objects.select_related('meeting', 'user').get(
                id=self.session_id
            )
        except ObjectDoesNotExist:
            return None
    
    @database_sync_to_async
    def check_permissions(self) -> bool:
        """Check if user has permission to access session"""
        return (
            self.session.user == self.user or
            self.user.has_perm('debriefings.view_debriefingsession') or
            self.user.is_staff
        )
    
    @database_sync_to_async
    def start_session(self):
        """Start the debriefing session"""
        self.session.status = 'in_progress'
        self.session.started_at = timezone.now()
        self.session.save()
    
    @database_sync_to_async
    def get_question(self, question_id: str) -> Optional[DebriefingQuestion]:
        """Get question by ID"""
        try:
            return DebriefingQuestion.objects.get(
                id=question_id,
                session=self.session
            )
        except ObjectDoesNotExist:
            return None
    
    @database_sync_to_async
    def record_response(self, question: DebriefingQuestion, response_text: str):
        """Record user response to question"""
        question.user_response = response_text
        question.response_timestamp = timezone.now()
        question.save()
    
    @database_sync_to_async
    def skip_question(self, question: DebriefingQuestion, reason: str):
        """Mark question as skipped"""
        question.user_response = f"[SKIPPED: {reason}]"
        question.response_timestamp = timezone.now()
        question.processed = True
        question.save()
    
    @database_sync_to_async
    def get_total_questions(self) -> int:
        """Get total number of questions in session"""
        return self.session.questions.count()
    
    @database_sync_to_async
    def get_session_state(self) -> Dict[str, Any]:
        """Get current session state"""
        return {
            'session_id': str(self.session.id),
            'status': self.session.status,
            'started_at': self.session.started_at.isoformat() if self.session.started_at else None,
            'meeting_title': self.session.meeting.title,
            'meeting_date': self.session.meeting.start_time.isoformat(),
            'total_questions': self.session.questions.count(),
            'answered_questions': self.session.questions.filter(
                user_response__isnull=False
            ).count(),
            'current_question_index': self.session.current_question_index,
            'progress_percentage': self._calculate_progress()
        }
    
    def _calculate_progress(self) -> float:
        """Calculate session progress percentage"""
        total = self.session.total_questions or 1
        answered = self.session.questions.filter(user_response__isnull=False).count()
        return (answered / total) * 100
    
    @database_sync_to_async
    def save_session_state(self):
        """Save current session state"""
        self.session.conversation_data['last_activity'] = timezone.now().isoformat()
        self.session.save()
    
    @database_sync_to_async
    def complete_session(self):
        """Complete the debriefing session"""
        self.session.status = 'completed'
        self.session.completed_at = timezone.now()
        self.session.save()
        
        # Update meeting status
        self.session.meeting.debriefing_completed = True
        self.session.meeting.save()
    
    # AI processing methods (to be implemented with flow manager)
    
    async def process_response(self, question: DebriefingQuestion, response_text: str) -> Dict[str, Any]:
        """Process user response with AI"""
        return await self.flow_manager.process_response(question, response_text)
    
    async def generate_follow_up_questions(
        self, 
        question: DebriefingQuestion, 
        response_text: str, 
        processing_result: Dict[str, Any]
    ) -> List[DebriefingQuestion]:
        """Generate follow-up questions based on response"""
        return await self.flow_manager.generate_follow_up_questions(
            question, response_text, processing_result
        )
    
    async def get_next_question(self, follow_up_questions: List[DebriefingQuestion] = None) -> Optional[DebriefingQuestion]:
        """Get next question in conversation flow"""
        return await self.flow_manager.get_next_question(follow_up_questions)
    
    async def generate_clarification(self, question: DebriefingQuestion, clarification_type: str) -> str:
        """Generate clarification for a question"""
        return await self.flow_manager.generate_clarification(question, clarification_type)
    
    async def handle_conversation_complete(self):
        """Handle completion of conversation flow"""
        # Extract final data
        extraction_result = await self.flow_manager.extract_final_data()
        
        # Generate insights
        insights = await self.flow_manager.generate_insights()
        
        # Complete session
        await self.complete_session()
        
        # Send completion message
        await self.send_message({
            'type': 'conversation_complete',
            'extracted_data': extraction_result,
            'insights': insights,
            'message': 'Debriefing conversation completed successfully'
        })


class DebriefingNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for debriefing notifications and updates
    """
    
    async def connect(self):
        """Handle WebSocket connection for notifications"""
        if not self.scope['user'].is_authenticated:
            await self.close(code=4001)
            return
        
        # Join user's notification group
        user_id = self.scope['user'].id
        await self.channel_layer.group_add(
            f"debriefing_notifications_{user_id}",
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Notification WebSocket connected for user {user_id}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self.scope['user'], 'id'):
            user_id = self.scope['user'].id
            await self.channel_layer.group_discard(
                f"debriefing_notifications_{user_id}",
                self.channel_name
            )
    
    async def debriefing_reminder(self, event):
        """Send debriefing reminder notification"""
        await self.send(text_data=json.dumps({
            'type': 'debriefing_reminder',
            'session_id': event['session_id'],
            'meeting_title': event['meeting_title'],
            'scheduled_time': event['scheduled_time'],
            'message': event['message']
        }))
    
    async def debriefing_overdue(self, event):
        """Send overdue debriefing notification"""
        await self.send(text_data=json.dumps({
            'type': 'debriefing_overdue',
            'session_id': event['session_id'],
            'meeting_title': event['meeting_title'],
            'overdue_hours': event['overdue_hours'],
            'message': event['message']
        }))
    
    async def debriefing_completed(self, event):
        """Send debriefing completion notification"""
        await self.send(text_data=json.dumps({
            'type': 'debriefing_completed',
            'session_id': event['session_id'],
            'meeting_title': event['meeting_title'],
            'insights_count': event['insights_count'],
            'message': event['message']
        }))