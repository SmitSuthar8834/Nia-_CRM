import json
import logging
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class MeetingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time meeting updates with authentication and authorization
    """
    
    async def connect(self):
        self.meeting_id = self.scope['url_route']['kwargs']['meeting_id']
        self.meeting_group_name = f'meeting_{self.meeting_id}'
        self.user = self.scope["user"]
        
        # Check authentication
        if self.user == AnonymousUser():
            logger.warning(f"Unauthenticated WebSocket connection attempt for meeting {self.meeting_id}")
            await self.close(code=4001)  # Custom close code for authentication failure
            return
        
        # Check authorization - verify user has access to this meeting
        has_access = await self.check_meeting_access()
        if not has_access:
            logger.warning(f"Unauthorized WebSocket connection attempt by user {self.user.id} for meeting {self.meeting_id}")
            await self.close(code=4003)  # Custom close code for authorization failure
            return
        
        # Join meeting group
        await self.channel_layer.group_add(
            self.meeting_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user.id} connected to meeting {self.meeting_id} WebSocket")
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'meeting_id': self.meeting_id,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        # Leave meeting group
        await self.channel_layer.group_discard(
            self.meeting_group_name,
            self.channel_name
        )
        
        logger.info(f"User {getattr(self.user, 'id', 'unknown')} disconnected from meeting {self.meeting_id} WebSocket (code: {close_code})")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket with enhanced error handling
        """
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            # Validate message structure
            if not message_type:
                await self.send_error('Message type is required')
                return
            
            # Handle different message types
            if message_type == 'ai_suggestion_request':
                await self.handle_ai_suggestion_request(text_data_json)
            elif message_type == 'note_update':
                await self.handle_note_update(text_data_json)
            elif message_type == 'action_item':
                await self.handle_action_item(text_data_json)
            elif message_type == 'ping':
                await self.handle_ping(text_data_json)
            elif message_type == 'connection_status':
                await self.handle_connection_status(text_data_json)
            elif message_type == 'reconnect':
                await self.handle_reconnect(text_data_json)
            else:
                await self.send_error(f'Unknown message type: {message_type}')
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received from user {self.user.id}: {e}")
            await self.send_error('Invalid JSON format')
        except Exception as e:
            logger.error(f"Error processing WebSocket message from user {self.user.id}: {e}")
            await self.send_error('Internal server error')
    
    async def handle_ai_suggestion_request(self, data):
        """
        Handle AI suggestion request messages with real AI integration
        """
        try:
            context = data.get('context', '')
            meeting_stage = data.get('meeting_stage', 'general')
            
            if not context:
                await self.send_error('Context is required for AI suggestions')
                return
            
            # Get AI suggestions using the AI service
            suggestions = await self.get_ai_suggestions(context, meeting_stage)
            
            # Broadcast AI suggestions to meeting group
            await self.channel_layer.group_send(
                self.meeting_group_name,
                {
                    'type': 'ai_suggestion_message',
                    'suggestions': suggestions,
                    'context': context[:100],  # Truncated context for reference
                    'meeting_stage': meeting_stage,
                    'timestamp': datetime.now().isoformat(),
                    'user_id': self.user.id
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling AI suggestion request: {e}")
            await self.send_error('Failed to process AI suggestion request')
    
    async def handle_note_update(self, data):
        """
        Handle note update messages with validation, persistence, and conflict resolution
        """
        try:
            notes = data.get('notes', '')
            version = data.get('version', 0)  # For conflict resolution
            cursor_position = data.get('cursor_position', 0)
            
            if len(notes) > 10000:  # Reasonable limit for notes
                await self.send_error('Notes too long (max 10000 characters)')
                return
            
            # Check for conflicts and save note update
            result = await self.save_note_update_with_conflict_resolution(notes, version)
            
            if result['conflict']:
                # Send conflict resolution message
                await self.send(text_data=json.dumps({
                    'type': 'note_conflict',
                    'server_notes': result['server_notes'],
                    'server_version': result['server_version'],
                    'client_notes': notes,
                    'timestamp': datetime.now().isoformat()
                }))
                return
            
            # Broadcast note update to meeting group
            await self.channel_layer.group_send(
                self.meeting_group_name,
                {
                    'type': 'note_update_message',
                    'notes': notes,
                    'version': result['version'],
                    'cursor_position': cursor_position,
                    'timestamp': datetime.now().isoformat(),
                    'user_id': self.user.id
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling note update: {e}")
            await self.send_error('Failed to process note update')
    
    async def handle_action_item(self, data):
        """
        Handle action item messages with validation
        """
        try:
            action_item = data.get('action_item', {})
            
            # Validate action item structure
            required_fields = ['description', 'assignee']
            for field in required_fields:
                if not action_item.get(field):
                    await self.send_error(f'Action item missing required field: {field}')
                    return
            
            # Save action item to database
            success = await self.save_action_item(action_item)
            if not success:
                await self.send_error('Failed to save action item')
                return
            
            # Broadcast action item to meeting group
            await self.channel_layer.group_send(
                self.meeting_group_name,
                {
                    'type': 'action_item_message',
                    'action_item': action_item,
                    'timestamp': datetime.now().isoformat(),
                    'user_id': self.user.id
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling action item: {e}")
            await self.send_error('Failed to process action item')
    
    async def handle_ping(self, data):
        """
        Handle ping messages for connection health check
        """
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': datetime.now().isoformat(),
            'meeting_id': self.meeting_id,
            'connection_status': 'healthy'
        }))
    
    async def handle_connection_status(self, data):
        """
        Handle connection status updates from client
        """
        status = data.get('status', 'unknown')
        logger.info(f"Connection status update from user {self.user.id}: {status}")
        
        # Respond with server status
        await self.send(text_data=json.dumps({
            'type': 'connection_status_response',
            'server_status': 'healthy',
            'client_status': status,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def handle_reconnect(self, data):
        """
        Handle reconnection requests from client
        """
        try:
            # Get current meeting state for client sync
            meeting_state = await self.get_meeting_state()
            
            await self.send(text_data=json.dumps({
                'type': 'reconnect_success',
                'meeting_state': meeting_state,
                'timestamp': datetime.now().isoformat()
            }))
            
        except Exception as e:
            logger.error(f"Error handling reconnection: {e}")
            await self.send_error('Failed to process reconnection')
    
    async def send_error(self, message):
        """
        Send error message to client
        """
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }))
    
    async def send_heartbeat(self):
        """
        Send heartbeat message for connection health monitoring
        """
        await self.send(text_data=json.dumps({
            'type': 'heartbeat',
            'timestamp': datetime.now().isoformat(),
            'meeting_id': self.meeting_id
        }))
    
    @database_sync_to_async
    def get_ai_suggestions(self, context, meeting_stage):
        """
        Get AI suggestions using the AI assistant service
        """
        from ai_assistant.services import AIAssistantService
        try:
            ai_service = AIAssistantService()
            
            # Get lead context for better suggestions
            from .models import Meeting
            meeting = Meeting.objects.get(id=self.meeting_id)
            lead_context = {
                'name': meeting.lead.name if meeting.lead else 'Unknown',
                'company': meeting.lead.company if meeting.lead else 'Unknown',
                'status': meeting.lead.status if meeting.lead else 'unknown'
            }
            
            # Generate contextual suggestions
            suggestions = ai_service.generate_meeting_suggestions(
                context=context,
                meeting_stage=meeting_stage,
                lead_context=lead_context
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error getting AI suggestions: {e}")
            # Return fallback suggestions
            return [
                "Can you tell me more about your current challenges?",
                "What are your main priorities for this quarter?",
                "How does this align with your company's goals?"
            ]
    
    # Message handlers for group sends
    async def ai_suggestion_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ai_suggestion',
            'suggestions': event.get('suggestions', []),
            'context': event.get('context', ''),
            'meeting_stage': event.get('meeting_stage', 'general'),
            'timestamp': event['timestamp'],
            'user_id': event.get('user_id')
        }))
    
    async def note_update_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'note_update',
            'notes': event['notes'],
            'version': event.get('version', 0),
            'cursor_position': event.get('cursor_position', 0),
            'timestamp': event['timestamp'],
            'user_id': event.get('user_id')
        }))
    
    async def action_item_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'action_item',
            'action_item': event['action_item'],
            'timestamp': event['timestamp'],
            'user_id': event.get('user_id')
        }))
    
    @database_sync_to_async
    def check_meeting_access(self):
        """
        Check if user has access to the meeting
        """
        from .models import Meeting
        try:
            meeting = Meeting.objects.get(id=self.meeting_id)
            # For now, allow access to all authenticated users
            # In production, you might want to check if user is an attendee
            return True
        except Meeting.DoesNotExist:
            return False
    
    @database_sync_to_async
    def save_note_update(self, notes):
        """
        Save note update to database with error handling
        """
        from .models import Meeting, MeetingSession
        try:
            meeting = Meeting.objects.get(id=self.meeting_id)
            session, created = MeetingSession.objects.get_or_create(
                meeting=meeting,
                defaults={
                    'notes': notes,
                    'ai_session_id': f'session_{self.meeting_id}',
                    'started_at': datetime.now()
                }
            )
            if not created:
                session.notes = notes
                session.save()
            return True
        except Meeting.DoesNotExist:
            logger.error(f"Meeting {self.meeting_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error saving notes for meeting {self.meeting_id}: {e}")
            return False
    
    @database_sync_to_async
    def save_note_update_with_conflict_resolution(self, notes, client_version):
        """
        Save note update with conflict resolution
        """
        from .models import Meeting, MeetingSession
        from django.utils import timezone
        
        try:
            meeting = Meeting.objects.get(id=self.meeting_id)
            session, created = MeetingSession.objects.get_or_create(
                meeting=meeting,
                defaults={
                    'notes': notes,
                    'ai_session_id': f'session_{self.meeting_id}',
                    'started_at': timezone.now(),
                    'notes_version': 1
                }
            )
            
            if created:
                return {
                    'conflict': False,
                    'version': 1,
                    'server_notes': notes
                }
            
            # Check for version conflict
            current_version = getattr(session, 'notes_version', 0)
            if client_version < current_version:
                # Conflict detected
                return {
                    'conflict': True,
                    'server_notes': session.notes,
                    'server_version': current_version,
                    'client_notes': notes
                }
            
            # No conflict, update notes
            session.notes = notes
            session.notes_version = current_version + 1
            session.save()
            
            return {
                'conflict': False,
                'version': session.notes_version,
                'server_notes': notes
            }
            
        except Meeting.DoesNotExist:
            logger.error(f"Meeting {self.meeting_id} not found")
            return {'conflict': False, 'version': 0, 'server_notes': ''}
        except Exception as e:
            logger.error(f"Error saving notes with conflict resolution: {e}")
            return {'conflict': False, 'version': 0, 'server_notes': ''}
    
    @database_sync_to_async
    def get_meeting_state(self):
        """
        Get current meeting state for client synchronization
        """
        from .models import Meeting, MeetingSession, ActionItem
        try:
            meeting = Meeting.objects.get(id=self.meeting_id)
            
            # Get meeting session if exists
            try:
                session = MeetingSession.objects.get(meeting=meeting)
                notes = session.notes
                notes_version = getattr(session, 'notes_version', 0)
                
                # Get action items
                action_items = list(ActionItem.objects.filter(
                    meeting_session=session
                ).values('description', 'assignee', 'due_date', 'status'))
                
            except MeetingSession.DoesNotExist:
                notes = ''
                notes_version = 0
                action_items = []
            
            # Get lead context
            lead_context = {}
            if meeting.lead:
                lead_context = {
                    'name': meeting.lead.name,
                    'company': meeting.lead.company,
                    'email': meeting.lead.email,
                    'status': meeting.lead.status
                }
            
            return {
                'meeting_id': str(meeting.id),
                'title': meeting.title,
                'notes': notes,
                'notes_version': notes_version,
                'action_items': action_items,
                'lead_context': lead_context,
                'status': meeting.status
            }
            
        except Meeting.DoesNotExist:
            logger.error(f"Meeting {self.meeting_id} not found")
            return {}
        except Exception as e:
            logger.error(f"Error getting meeting state: {e}")
            return {}
    
    @database_sync_to_async
    def save_action_item(self, action_item_data):
        """
        Save action item to database
        """
        from .models import Meeting, MeetingSession, ActionItem
        try:
            meeting = Meeting.objects.get(id=self.meeting_id)
            session, created = MeetingSession.objects.get_or_create(
                meeting=meeting,
                defaults={
                    'ai_session_id': f'session_{self.meeting_id}',
                    'started_at': datetime.now()
                }
            )
            
            ActionItem.objects.create(
                meeting_session=session,
                description=action_item_data['description'],
                assignee=action_item_data['assignee'],
                due_date=action_item_data.get('due_date'),
                status='pending'
            )
            return True
        except Meeting.DoesNotExist:
            logger.error(f"Meeting {self.meeting_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error saving action item for meeting {self.meeting_id}: {e}")
            return False