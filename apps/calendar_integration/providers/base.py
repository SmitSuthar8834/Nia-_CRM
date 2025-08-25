"""
Base calendar provider interface
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from django.contrib.auth.models import User


class BaseCalendarProvider(ABC):
    """
    Abstract base class for calendar providers
    """
    
    def __init__(self):
        # Extract provider name from class name (e.g., GoogleCalendarProvider -> google)
        class_name = self.__class__.__name__.lower()
        if 'calendar' in class_name:
            self.provider_name = class_name.replace('calendarprovider', '').replace('provider', '')
        else:
            self.provider_name = class_name.replace('provider', '')
    
    @abstractmethod
    async def is_user_connected(self, user: User) -> bool:
        """Check if user has connected this calendar provider"""
        pass
    
    @abstractmethod
    async def get_authorization_url(self, user: User, redirect_uri: str) -> str:
        """Get OAuth authorization URL for user"""
        pass
    
    @abstractmethod
    async def handle_oauth_callback(self, user: User, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback and store credentials"""
        pass
    
    @abstractmethod
    async def refresh_access_token(self, user: User) -> bool:
        """Refresh user's access token"""
        pass
    
    @abstractmethod
    async def get_user_calendars(self, user: User) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        pass
    
    @abstractmethod
    async def get_calendar_events(
        self, 
        user: User, 
        calendar_id: str, 
        time_min: datetime, 
        time_max: datetime,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calendar events within time range"""
        pass
    
    @abstractmethod
    def parse_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse provider-specific event data into standard format"""
        pass
    
    @abstractmethod
    async def create_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new calendar event"""
        pass
    
    @abstractmethod
    async def update_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing calendar event"""
        pass
    
    @abstractmethod
    async def delete_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str
    ) -> bool:
        """Delete a calendar event"""
        pass
    
    @abstractmethod
    async def detect_changes(self, user: User) -> List[Dict[str, Any]]:
        """Detect changes in user's calendars"""
        pass
    
    @abstractmethod
    def parse_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse webhook notification data"""
        pass
    
    def get_provider_name(self) -> str:
        """Get provider name"""
        return self.provider_name
    
    def _standardize_datetime(self, dt_data: Dict[str, Any]) -> datetime:
        """
        Standardize datetime from provider format to Python datetime
        """
        # This will be implemented by each provider based on their format
        raise NotImplementedError("Subclasses must implement _standardize_datetime")
    
    def _standardize_attendee(self, attendee_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize attendee data from provider format
        """
        return {
            'email': attendee_data.get('email', ''),
            'name': attendee_data.get('displayName', attendee_data.get('name', '')),
            'response_status': self._map_response_status(attendee_data.get('responseStatus', 'needsAction')),
            'type': attendee_data.get('type', 'required'),
            'optional': attendee_data.get('optional', False)
        }
    
    def _map_response_status(self, provider_status: str) -> str:
        """
        Map provider-specific response status to standard format
        """
        status_mapping = {
            'accepted': 'accepted',
            'declined': 'declined',
            'tentative': 'tentative',
            'needsAction': 'no_response',
            'pending': 'no_response'
        }
        return status_mapping.get(provider_status, 'no_response')
    
    def _extract_meeting_url(self, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract meeting URL from event data
        """
        # Common patterns for meeting URLs
        description = event_data.get('description', '')
        location = event_data.get('location', '')
        
        # Check for common video conferencing URLs
        import re
        url_patterns = [
            r'https://[a-zA-Z0-9.-]+\.zoom\.us/[^\s]+',
            r'https://teams\.microsoft\.com/[^\s]+',
            r'https://meet\.google\.com/[^\s]+',
            r'https://[a-zA-Z0-9.-]+\.webex\.com/[^\s]+',
            r'https://[a-zA-Z0-9.-]+\.gotomeeting\.com/[^\s]+'
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, f"{description} {location}")
            if match:
                return match.group(0)
        
        return None
    
    async def test_connection(self, user: User) -> Dict[str, Any]:
        """
        Test the connection to the calendar provider
        """
        try:
            if not await self.is_user_connected(user):
                return {
                    'status': 'error',
                    'message': 'User not connected to calendar provider'
                }
            
            # Try to get calendars as a connection test
            calendars = await self.get_user_calendars(user)
            
            return {
                'status': 'success',
                'message': f'Successfully connected to {self.provider_name}',
                'calendar_count': len(calendars)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Connection test failed: {str(e)}'
            }
    
    def _handle_api_error(self, error: Exception, operation: str) -> Dict[str, Any]:
        """
        Handle API errors in a standardized way
        """
        error_info = {
            'operation': operation,
            'provider': self.provider_name,
            'error_type': type(error).__name__,
            'error_message': str(error)
        }
        
        # Add specific handling for common errors
        if 'unauthorized' in str(error).lower() or 'invalid_grant' in str(error).lower():
            error_info['requires_reauth'] = True
        elif 'rate_limit' in str(error).lower() or 'quota' in str(error).lower():
            error_info['rate_limited'] = True
        elif 'not_found' in str(error).lower():
            error_info['resource_not_found'] = True
        
        return error_info