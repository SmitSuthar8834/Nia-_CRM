"""
Google Calendar Provider
"""
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone as django_timezone

from .base import BaseCalendarProvider

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(BaseCalendarProvider):
    """
    Google Calendar integration provider
    """
    
    def __init__(self):
        super().__init__()
        self.client_id = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'GOOGLE_CALENDAR_CLIENT_SECRET', '')
        self.scopes = [
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        self.api_base_url = 'https://www.googleapis.com/calendar/v3'
    
    async def is_user_connected(self, user: User) -> bool:
        """Check if user has connected Google Calendar"""
        try:
            from apps.accounts.models import UserProfile
            profile = await UserProfile.objects.aget(user=user)
            
            google_credentials = profile.calendar_integrations.get('google', {})
            return bool(google_credentials.get('access_token'))
            
        except Exception as e:
            logger.error(f"Error checking Google Calendar connection for user {user.id}: {str(e)}")
            return False
    
    async def get_authorization_url(self, user: User, redirect_uri: str) -> str:
        """Get OAuth authorization URL for Google Calendar"""
        import urllib.parse
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(self.scopes),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': f"user_{user.id}"
        }
        
        auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
        return auth_url
    
    async def handle_oauth_callback(self, user: User, code: str, state: str) -> Dict[str, Any]:
        """Handle OAuth callback and store credentials"""
        try:
            import aiohttp
            
            # Exchange code for tokens
            token_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': settings.GOOGLE_CALENDAR_REDIRECT_URI
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://oauth2.googleapis.com/token',
                    data=token_data
                ) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Store credentials
                        await self._store_user_credentials(user, tokens)
                        
                        return {
                            'status': 'success',
                            'message': 'Google Calendar connected successfully'
                        }
                    else:
                        error_data = await response.json()
                        return {
                            'status': 'error',
                            'message': f"OAuth error: {error_data.get('error_description', 'Unknown error')}"
                        }
                        
        except Exception as e:
            logger.error(f"Error handling Google Calendar OAuth callback: {str(e)}")
            return {
                'status': 'error',
                'message': f"OAuth callback error: {str(e)}"
            }
    
    async def refresh_access_token(self, user: User) -> bool:
        """Refresh user's access token"""
        try:
            from apps.accounts.models import UserProfile
            
            profile = await UserProfile.objects.aget(user=user)
            google_credentials = profile.calendar_integrations.get('google', {})
            
            refresh_token = google_credentials.get('refresh_token')
            if not refresh_token:
                return False
            
            import aiohttp
            
            token_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://oauth2.googleapis.com/token',
                    data=token_data
                ) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Update stored credentials
                        google_credentials.update({
                            'access_token': tokens['access_token'],
                            'expires_at': django_timezone.now().timestamp() + tokens.get('expires_in', 3600)
                        })
                        
                        profile.calendar_integrations['google'] = google_credentials
                        await profile.asave()
                        
                        return True
                    else:
                        logger.error(f"Failed to refresh Google Calendar token for user {user.id}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error refreshing Google Calendar token: {str(e)}")
            return False
    
    async def get_user_calendars(self, user: User) -> List[Dict[str, Any]]:
        """Get list of user's Google calendars"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return []
            
            import aiohttp
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{self.api_base_url}/users/me/calendarList',
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        calendars = []
                        for calendar_item in data.get('items', []):
                            calendars.append({
                                'id': calendar_item['id'],
                                'name': calendar_item['summary'],
                                'description': calendar_item.get('description', ''),
                                'primary': calendar_item.get('primary', False),
                                'access_role': calendar_item.get('accessRole', 'reader'),
                                'selected': calendar_item.get('selected', True)
                            })
                        
                        return calendars
                    else:
                        logger.error(f"Failed to get Google calendars: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error getting Google calendars: {str(e)}")
            return []
    
    async def get_calendar_events(
        self, 
        user: User, 
        calendar_id: str, 
        time_min: datetime, 
        time_max: datetime,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calendar events from Google Calendar"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'items': []}
            
            import aiohttp
            import urllib.parse
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            params = {
                'timeMin': time_min.isoformat(),
                'timeMax': time_max.isoformat(),
                'singleEvents': 'true',
                'orderBy': 'startTime',
                'maxResults': 2500
            }
            
            if sync_token:
                params['syncToken'] = sync_token
                # Remove time filters when using sync token
                del params['timeMin']
                del params['timeMax']
            
            url = f'{self.api_base_url}/calendars/{urllib.parse.quote(calendar_id)}/events'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Failed to get Google Calendar events: {response.status}")
                        return {'items': []}
                        
        except Exception as e:
            logger.error(f"Error getting Google Calendar events: {str(e)}")
            return {'items': []}
    
    def parse_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Google Calendar event data into standard format"""
        try:
            # Parse start and end times
            start_data = event_data.get('start', {})
            end_data = event_data.get('end', {})
            
            start_time = self._parse_google_datetime(start_data)
            end_time = self._parse_google_datetime(end_data)
            
            # Parse attendees
            attendees = []
            for attendee in event_data.get('attendees', []):
                attendees.append(self._standardize_attendee(attendee))
            
            # Extract meeting URL
            meeting_url = self._extract_meeting_url(event_data)
            
            return {
                'id': event_data['id'],
                'title': event_data.get('summary', 'No Title'),
                'description': event_data.get('description', ''),
                'start_time': start_time,
                'end_time': end_time,
                'timezone': start_data.get('timeZone', 'UTC'),
                'location': event_data.get('location', ''),
                'meeting_url': meeting_url,
                'status': event_data.get('status', 'confirmed'),
                'is_all_day': 'date' in start_data,
                'is_recurring': 'recurringEventId' in event_data,
                'recurrence_rule': ','.join(event_data.get('recurrence', [])),
                'organizer_email': event_data.get('organizer', {}).get('email', ''),
                'organizer_name': event_data.get('organizer', {}).get('displayName', ''),
                'attendees': attendees,
                'last_modified': self._parse_google_datetime({'dateTime': event_data.get('updated')}),
                'etag': event_data.get('etag', ''),
            }
            
        except Exception as e:
            logger.error(f"Error parsing Google Calendar event data: {str(e)}")
            return {}
    
    async def create_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new Google Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'status': 'error', 'message': 'No valid access token'}
            
            import aiohttp
            import urllib.parse
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Convert to Google Calendar format
            google_event = self._convert_to_google_format(event_data)
            
            url = f'{self.api_base_url}/calendars/{urllib.parse.quote(calendar_id)}/events'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=google_event
                ) as response:
                    if response.status == 200:
                        created_event = await response.json()
                        return {
                            'status': 'success',
                            'event': self.parse_event_data(created_event)
                        }
                    else:
                        error_data = await response.json()
                        return {
                            'status': 'error',
                            'message': error_data.get('error', {}).get('message', 'Unknown error')
                        }
                        
        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    async def update_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing Google Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'status': 'error', 'message': 'No valid access token'}
            
            import aiohttp
            import urllib.parse
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Convert to Google Calendar format
            google_event = self._convert_to_google_format(event_data)
            
            url = f'{self.api_base_url}/calendars/{urllib.parse.quote(calendar_id)}/events/{event_id}'
            
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url, 
                    headers=headers, 
                    json=google_event
                ) as response:
                    if response.status == 200:
                        updated_event = await response.json()
                        return {
                            'status': 'success',
                            'event': self.parse_event_data(updated_event)
                        }
                    else:
                        error_data = await response.json()
                        return {
                            'status': 'error',
                            'message': error_data.get('error', {}).get('message', 'Unknown error')
                        }
                        
        except Exception as e:
            logger.error(f"Error updating Google Calendar event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    async def delete_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str
    ) -> bool:
        """Delete a Google Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return False
            
            import aiohttp
            import urllib.parse
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            url = f'{self.api_base_url}/calendars/{urllib.parse.quote(calendar_id)}/events/{event_id}'
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    return response.status == 204
                    
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event: {str(e)}")
            return False
    
    async def detect_changes(self, user: User) -> List[Dict[str, Any]]:
        """Detect changes in user's Google calendars"""
        changes = []
        
        try:
            calendars = await self.get_user_calendars(user)
            
            for calendar in calendars:
                # Use sync tokens to detect changes
                # This is a simplified implementation
                calendar_changes = await self._detect_calendar_changes(user, calendar['id'])
                changes.extend(calendar_changes)
                
        except Exception as e:
            logger.error(f"Error detecting Google Calendar changes: {str(e)}")
        
        return changes
    
    def parse_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Google Calendar webhook notification data"""
        return {
            'provider': 'google',
            'calendar_id': webhook_data.get('resourceId'),
            'change_type': webhook_data.get('eventType', 'unknown'),
            'resource_state': webhook_data.get('resourceState'),
            'user_id': webhook_data.get('userId')  # This would need to be mapped from the webhook
        }
    
    async def _store_user_credentials(self, user: User, tokens: Dict[str, Any]):
        """Store user's Google Calendar credentials"""
        from apps.accounts.models import UserProfile
        
        profile, created = await UserProfile.objects.aget_or_create(user=user)
        
        if not profile.calendar_integrations:
            profile.calendar_integrations = {}
        
        profile.calendar_integrations['google'] = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens.get('refresh_token'),
            'expires_at': django_timezone.now().timestamp() + tokens.get('expires_in', 3600),
            'scope': tokens.get('scope', ' '.join(self.scopes))
        }
        
        await profile.asave()
    
    async def _get_valid_access_token(self, user: User) -> Optional[str]:
        """Get a valid access token, refreshing if necessary"""
        try:
            from apps.accounts.models import UserProfile
            
            profile = await UserProfile.objects.aget(user=user)
            google_credentials = profile.calendar_integrations.get('google', {})
            
            access_token = google_credentials.get('access_token')
            expires_at = google_credentials.get('expires_at', 0)
            
            # Check if token is expired
            if django_timezone.now().timestamp() >= expires_at:
                if await self.refresh_access_token(user):
                    # Get the refreshed token
                    profile = await UserProfile.objects.aget(user=user)
                    google_credentials = profile.calendar_integrations.get('google', {})
                    access_token = google_credentials.get('access_token')
                else:
                    return None
            
            return access_token
            
        except Exception as e:
            logger.error(f"Error getting valid access token: {str(e)}")
            return None
    
    def _parse_google_datetime(self, dt_data: Dict[str, Any]) -> datetime:
        """Parse Google Calendar datetime format"""
        if 'dateTime' in dt_data:
            # Parse RFC3339 datetime
            from dateutil import parser
            return parser.parse(dt_data['dateTime'])
        elif 'date' in dt_data:
            # Parse date-only (all-day event)
            from dateutil import parser
            date_obj = parser.parse(dt_data['date']).date()
            return datetime.combine(date_obj, datetime.min.time()).replace(tzinfo=timezone.utc)
        else:
            return django_timezone.now()
    
    def _convert_to_google_format(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard event data to Google Calendar format"""
        google_event = {
            'summary': event_data.get('title', ''),
            'description': event_data.get('description', ''),
            'location': event_data.get('location', ''),
            'start': {
                'dateTime': event_data['start_time'].isoformat(),
                'timeZone': event_data.get('timezone', 'UTC')
            },
            'end': {
                'dateTime': event_data['end_time'].isoformat(),
                'timeZone': event_data.get('timezone', 'UTC')
            }
        }
        
        # Add attendees if provided
        if 'attendees' in event_data:
            google_event['attendees'] = [
                {
                    'email': attendee['email'],
                    'displayName': attendee.get('name', ''),
                    'responseStatus': 'needsAction'
                }
                for attendee in event_data['attendees']
            ]
        
        return google_event
    
    async def _detect_calendar_changes(self, user: User, calendar_id: str) -> List[Dict[str, Any]]:
        """Detect changes in a specific calendar"""
        # This would use Google Calendar's sync tokens to detect changes
        # Simplified implementation for now
        return []