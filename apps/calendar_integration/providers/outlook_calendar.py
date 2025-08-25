"""
Outlook Calendar Provider (Microsoft Graph API)
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


class OutlookCalendarProvider(BaseCalendarProvider):
    """
    Outlook Calendar integration provider using Microsoft Graph API
    """
    
    def __init__(self):
        super().__init__()
        self.client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', '')
        self.tenant_id = getattr(settings, 'MICROSOFT_TENANT_ID', 'common')
        self.scopes = [
            'https://graph.microsoft.com/Calendars.ReadWrite',
            'https://graph.microsoft.com/Calendars.Read',
            'https://graph.microsoft.com/User.Read'
        ]
        self.api_base_url = 'https://graph.microsoft.com/v1.0'
        self.auth_base_url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0'
    
    async def is_user_connected(self, user: User) -> bool:
        """Check if user has connected Outlook Calendar"""
        try:
            from apps.accounts.models import UserProfile
            profile = await UserProfile.objects.aget(user=user)
            
            outlook_credentials = profile.calendar_integrations.get('outlook', {})
            return bool(outlook_credentials.get('access_token'))
            
        except Exception as e:
            logger.error(f"Error checking Outlook Calendar connection for user {user.id}: {str(e)}")
            return False
    
    async def get_authorization_url(self, user: User, redirect_uri: str) -> str:
        """Get OAuth authorization URL for Outlook Calendar"""
        import urllib.parse
        
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'response_mode': 'query',
            'scope': ' '.join(self.scopes),
            'state': f"user_{user.id}",
            'prompt': 'consent'
        }
        
        auth_url = f'{self.auth_base_url}/authorize?' + urllib.parse.urlencode(params)
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
                'redirect_uri': settings.MICROSOFT_REDIRECT_URI,
                'grant_type': 'authorization_code',
                'scope': ' '.join(self.scopes)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.auth_base_url}/token',
                    data=token_data
                ) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Store credentials
                        await self._store_user_credentials(user, tokens)
                        
                        return {
                            'status': 'success',
                            'message': 'Outlook Calendar connected successfully'
                        }
                    else:
                        error_data = await response.json()
                        return {
                            'status': 'error',
                            'message': f"OAuth error: {error_data.get('error_description', 'Unknown error')}"
                        }
                        
        except Exception as e:
            logger.error(f"Error handling Outlook Calendar OAuth callback: {str(e)}")
            return {
                'status': 'error',
                'message': f"OAuth callback error: {str(e)}"
            }
    
    async def refresh_access_token(self, user: User) -> bool:
        """Refresh user's access token"""
        try:
            from apps.accounts.models import UserProfile
            
            profile = await UserProfile.objects.aget(user=user)
            outlook_credentials = profile.calendar_integrations.get('outlook', {})
            
            refresh_token = outlook_credentials.get('refresh_token')
            if not refresh_token:
                return False
            
            import aiohttp
            
            token_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
                'scope': ' '.join(self.scopes)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.auth_base_url}/token',
                    data=token_data
                ) as response:
                    if response.status == 200:
                        tokens = await response.json()
                        
                        # Update stored credentials
                        outlook_credentials.update({
                            'access_token': tokens['access_token'],
                            'expires_at': django_timezone.now().timestamp() + tokens.get('expires_in', 3600)
                        })
                        
                        if 'refresh_token' in tokens:
                            outlook_credentials['refresh_token'] = tokens['refresh_token']
                        
                        profile.calendar_integrations['outlook'] = outlook_credentials
                        await profile.asave()
                        
                        return True
                    else:
                        logger.error(f"Failed to refresh Outlook Calendar token for user {user.id}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error refreshing Outlook Calendar token: {str(e)}")
            return False
    
    async def get_user_calendars(self, user: User) -> List[Dict[str, Any]]:
        """Get list of user's Outlook calendars"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return []
            
            import aiohttp
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'{self.api_base_url}/me/calendars',
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        calendars = []
                        for calendar_item in data.get('value', []):
                            calendars.append({
                                'id': calendar_item['id'],
                                'name': calendar_item['name'],
                                'description': calendar_item.get('description', ''),
                                'primary': calendar_item.get('isDefaultCalendar', False),
                                'access_role': 'owner',  # Outlook doesn't have granular roles like Google
                                'selected': True,
                                'color': calendar_item.get('color', 'auto')
                            })
                        
                        return calendars
                    else:
                        logger.error(f"Failed to get Outlook calendars: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error getting Outlook calendars: {str(e)}")
            return []
    
    async def get_calendar_events(
        self, 
        user: User, 
        calendar_id: str, 
        time_min: datetime, 
        time_max: datetime,
        sync_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get calendar events from Outlook Calendar"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'value': []}
            
            import aiohttp
            import urllib.parse
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Format dates for Microsoft Graph API
            start_time = time_min.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            end_time = time_max.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
            params = {
                'startDateTime': start_time,
                'endDateTime': end_time,
                '$orderby': 'start/dateTime',
                '$top': 1000,
                '$select': 'id,subject,body,start,end,location,attendees,organizer,isAllDay,recurrence,webLink,onlineMeeting,lastModifiedDateTime'
            }
            
            if sync_token:
                # Microsoft Graph uses delta queries for sync
                url = f'{self.api_base_url}/me/calendars/{calendar_id}/events/delta'
                params = {'$deltatoken': sync_token}
            else:
                url = f'{self.api_base_url}/me/calendars/{calendar_id}/calendarView'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Convert to Google Calendar-like format for consistency
                        return {
                            'items': data.get('value', []),
                            'nextSyncToken': self._extract_delta_token(data)
                        }
                    else:
                        logger.error(f"Failed to get Outlook Calendar events: {response.status}")
                        return {'items': []}
                        
        except Exception as e:
            logger.error(f"Error getting Outlook Calendar events: {str(e)}")
            return {'items': []}
    
    def parse_event_data(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Outlook Calendar event data into standard format"""
        try:
            # Parse start and end times
            start_data = event_data.get('start', {})
            end_data = event_data.get('end', {})
            
            start_time = self._parse_outlook_datetime(start_data)
            end_time = self._parse_outlook_datetime(end_data)
            
            # Parse attendees
            attendees = []
            for attendee in event_data.get('attendees', []):
                attendees.append({
                    'email': attendee.get('emailAddress', {}).get('address', ''),
                    'name': attendee.get('emailAddress', {}).get('name', ''),
                    'response_status': self._map_outlook_response_status(
                        attendee.get('status', {}).get('response', 'none')
                    ),
                    'type': attendee.get('type', 'required').lower(),
                    'optional': attendee.get('type', 'required').lower() == 'optional'
                })
            
            # Extract meeting URL
            meeting_url = self._extract_outlook_meeting_url(event_data)
            
            # Parse body content
            body = event_data.get('body', {})
            description = body.get('content', '') if body else ''
            
            return {
                'id': event_data['id'],
                'title': event_data.get('subject', 'No Title'),
                'description': description,
                'start_time': start_time,
                'end_time': end_time,
                'timezone': start_data.get('timeZone', 'UTC'),
                'location': event_data.get('location', {}).get('displayName', ''),
                'meeting_url': meeting_url,
                'status': 'confirmed',  # Outlook doesn't have the same status concept
                'is_all_day': event_data.get('isAllDay', False),
                'is_recurring': bool(event_data.get('recurrence')),
                'recurrence_rule': self._parse_outlook_recurrence(event_data.get('recurrence')),
                'organizer_email': event_data.get('organizer', {}).get('emailAddress', {}).get('address', ''),
                'organizer_name': event_data.get('organizer', {}).get('emailAddress', {}).get('name', ''),
                'attendees': attendees,
                'last_modified': self._parse_outlook_datetime({'dateTime': event_data.get('lastModifiedDateTime'), 'timeZone': 'UTC'}),
                'etag': event_data.get('@odata.etag', ''),
            }
            
        except Exception as e:
            logger.error(f"Error parsing Outlook Calendar event data: {str(e)}")
            return {}
    
    async def create_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new Outlook Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'status': 'error', 'message': 'No valid access token'}
            
            import aiohttp
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Convert to Outlook format
            outlook_event = self._convert_to_outlook_format(event_data)
            
            url = f'{self.api_base_url}/me/calendars/{calendar_id}/events'
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    json=outlook_event
                ) as response:
                    if response.status == 201:
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
            logger.error(f"Error creating Outlook Calendar event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    async def update_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str, 
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing Outlook Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return {'status': 'error', 'message': 'No valid access token'}
            
            import aiohttp
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Convert to Outlook format
            outlook_event = self._convert_to_outlook_format(event_data)
            
            url = f'{self.api_base_url}/me/calendars/{calendar_id}/events/{event_id}'
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    url, 
                    headers=headers, 
                    json=outlook_event
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
            logger.error(f"Error updating Outlook Calendar event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    async def delete_event(
        self, 
        user: User, 
        calendar_id: str, 
        event_id: str
    ) -> bool:
        """Delete an Outlook Calendar event"""
        try:
            access_token = await self._get_valid_access_token(user)
            if not access_token:
                return False
            
            import aiohttp
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            url = f'{self.api_base_url}/me/calendars/{calendar_id}/events/{event_id}'
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    return response.status == 204
                    
        except Exception as e:
            logger.error(f"Error deleting Outlook Calendar event: {str(e)}")
            return False
    
    async def detect_changes(self, user: User) -> List[Dict[str, Any]]:
        """Detect changes in user's Outlook calendars"""
        changes = []
        
        try:
            calendars = await self.get_user_calendars(user)
            
            for calendar in calendars:
                # Use delta queries to detect changes
                calendar_changes = await self._detect_calendar_changes(user, calendar['id'])
                changes.extend(calendar_changes)
                
        except Exception as e:
            logger.error(f"Error detecting Outlook Calendar changes: {str(e)}")
        
        return changes
    
    def parse_webhook_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Outlook Calendar webhook notification data"""
        return {
            'provider': 'outlook',
            'calendar_id': webhook_data.get('resourceData', {}).get('id'),
            'change_type': webhook_data.get('changeType', 'unknown'),
            'resource': webhook_data.get('resource'),
            'user_id': webhook_data.get('userId')  # This would need to be mapped
        }
    
    async def _store_user_credentials(self, user: User, tokens: Dict[str, Any]):
        """Store user's Outlook Calendar credentials"""
        from apps.accounts.models import UserProfile
        
        profile, created = await UserProfile.objects.aget_or_create(user=user)
        
        if not profile.calendar_integrations:
            profile.calendar_integrations = {}
        
        profile.calendar_integrations['outlook'] = {
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
            outlook_credentials = profile.calendar_integrations.get('outlook', {})
            
            access_token = outlook_credentials.get('access_token')
            expires_at = outlook_credentials.get('expires_at', 0)
            
            # Check if token is expired
            if django_timezone.now().timestamp() >= expires_at:
                if await self.refresh_access_token(user):
                    # Get the refreshed token
                    profile = await UserProfile.objects.aget(user=user)
                    outlook_credentials = profile.calendar_integrations.get('outlook', {})
                    access_token = outlook_credentials.get('access_token')
                else:
                    return None
            
            return access_token
            
        except Exception as e:
            logger.error(f"Error getting valid access token: {str(e)}")
            return None
    
    def _parse_outlook_datetime(self, dt_data: Dict[str, Any]) -> datetime:
        """Parse Outlook Calendar datetime format"""
        if not dt_data or 'dateTime' not in dt_data:
            return django_timezone.now()
        
        try:
            from dateutil import parser
            dt_str = dt_data['dateTime']
            
            # Parse the datetime string
            dt = parser.parse(dt_str)
            
            # Handle timezone
            if dt.tzinfo is None:
                # If no timezone info, assume UTC
                dt = dt.replace(tzinfo=timezone.utc)
            
            return dt
            
        except Exception as e:
            logger.error(f"Error parsing Outlook datetime: {str(e)}")
            return django_timezone.now()
    
    def _map_outlook_response_status(self, outlook_status: str) -> str:
        """Map Outlook response status to standard format"""
        status_mapping = {
            'accepted': 'accepted',
            'declined': 'declined',
            'tentativelyAccepted': 'tentative',
            'none': 'no_response',
            'notResponded': 'no_response'
        }
        return status_mapping.get(outlook_status, 'no_response')
    
    def _extract_outlook_meeting_url(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract meeting URL from Outlook event data"""
        # Check for Teams meeting
        online_meeting = event_data.get('onlineMeeting')
        if online_meeting and online_meeting.get('joinUrl'):
            return online_meeting['joinUrl']
        
        # Check webLink
        web_link = event_data.get('webLink')
        if web_link:
            return web_link
        
        # Fall back to standard URL extraction
        return self._extract_meeting_url(event_data)
    
    def _parse_outlook_recurrence(self, recurrence_data: Optional[Dict[str, Any]]) -> str:
        """Parse Outlook recurrence data to string format"""
        if not recurrence_data:
            return ''
        
        try:
            pattern = recurrence_data.get('pattern', {})
            range_data = recurrence_data.get('range', {})
            
            # Build a simple recurrence string
            recurrence_parts = []
            
            if pattern.get('type'):
                recurrence_parts.append(f"TYPE={pattern['type']}")
            
            if pattern.get('interval'):
                recurrence_parts.append(f"INTERVAL={pattern['interval']}")
            
            if range_data.get('type'):
                recurrence_parts.append(f"RANGE={range_data['type']}")
            
            return ';'.join(recurrence_parts)
            
        except Exception as e:
            logger.error(f"Error parsing Outlook recurrence: {str(e)}")
            return ''
    
    def _convert_to_outlook_format(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard event data to Outlook format"""
        outlook_event = {
            'subject': event_data.get('title', ''),
            'body': {
                'contentType': 'text',
                'content': event_data.get('description', '')
            },
            'start': {
                'dateTime': event_data['start_time'].isoformat(),
                'timeZone': event_data.get('timezone', 'UTC')
            },
            'end': {
                'dateTime': event_data['end_time'].isoformat(),
                'timeZone': event_data.get('timezone', 'UTC')
            }
        }
        
        # Add location if provided
        if event_data.get('location'):
            outlook_event['location'] = {
                'displayName': event_data['location']
            }
        
        # Add attendees if provided
        if 'attendees' in event_data:
            outlook_event['attendees'] = [
                {
                    'emailAddress': {
                        'address': attendee['email'],
                        'name': attendee.get('name', '')
                    },
                    'type': attendee.get('type', 'required')
                }
                for attendee in event_data['attendees']
            ]
        
        return outlook_event
    
    def _extract_delta_token(self, response_data: Dict[str, Any]) -> Optional[str]:
        """Extract delta token from Microsoft Graph response"""
        next_link = response_data.get('@odata.nextLink')
        delta_link = response_data.get('@odata.deltaLink')
        
        if delta_link:
            # Extract deltatoken parameter
            import urllib.parse
            parsed = urllib.parse.urlparse(delta_link)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get('$deltatoken', [None])[0]
        
        return None
    
    async def _detect_calendar_changes(self, user: User, calendar_id: str) -> List[Dict[str, Any]]:
        """Detect changes in a specific Outlook calendar"""
        # This would use Microsoft Graph delta queries
        # Simplified implementation for now
        return []