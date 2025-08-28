"""
Calendar Integration Views
"""
import logging
from typing import Dict, Any
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .services import CalendarIntegrationHub
from .models import CalendarEvent, CalendarSyncStatus

logger = logging.getLogger(__name__)


def sync_google_calendar_events(user, access_token):
    """
    Sync events from Google Calendar API
    """
    try:
        import requests
        from datetime import datetime, timedelta
        from apps.meetings.models import Meeting
        
        # Get events from Google Calendar API
        calendar_api_url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        # Get events for the next 30 days
        time_min = datetime.utcnow().isoformat() + 'Z'
        time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + 'Z'
        
        params = {
            'timeMin': time_min,
            'timeMax': time_max,
            'singleEvents': True,
            'orderBy': 'startTime',
            'maxResults': 50
        }
        
        response = requests.get(calendar_api_url, headers=headers, params=params)
        
        if response.status_code == 200:
            events_data = response.json()
            events_created = 0
            
            for event in events_data.get('items', []):
                # Skip events without start time or that are cancelled
                if 'start' not in event or event.get('status') == 'cancelled':
                    continue
                
                # Parse start and end times
                start_time_str = event['start'].get('dateTime') or event['start'].get('date')
                end_time_str = event['end'].get('dateTime') or event['end'].get('date')
                
                if not start_time_str or not end_time_str:
                    continue
                
                # Convert to datetime objects
                from dateutil import parser
                start_time = parser.parse(start_time_str)
                end_time = parser.parse(end_time_str)
                
                # Create or update Meeting object
                meeting, created = Meeting.objects.get_or_create(
                    calendar_event_id=event['id'],
                    defaults={
                        'organizer': user,
                        'title': event.get('summary', 'Untitled Event'),
                        'description': event.get('description', ''),
                        'start_time': start_time,
                        'end_time': end_time,
                        'location': event.get('location', ''),
                        'meeting_url': event.get('hangoutLink') or event.get('htmlLink', ''),
                        'calendar_provider': 'google',
                        'meeting_type': 'other',
                        'is_sales_meeting': False,
                        'confidence_score': 0.0
                    }
                )
                
                if created:
                    events_created += 1
                    logger.info(f"Created meeting: {meeting.title}")
            
            logger.info(f"Synced {events_created} new events from Google Calendar")
            return events_created
            
        else:
            logger.error(f"Failed to fetch Google Calendar events: {response.status_code} - {response.text}")
            return 0
            
    except Exception as e:
        logger.error(f"Error syncing Google Calendar events: {str(e)}")
        return 0


class CalendarIntegrationView(View):
    """
    Base view for calendar integration operations
    """
    
    def __init__(self):
        super().__init__()
        self.integration_hub = CalendarIntegrationHub()
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_calendar_providers(request):
    """
    Get list of available calendar providers and their connection status
    """
    try:
        # Simple provider status check
        from apps.accounts.models import UserProfile
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            calendar_integrations = getattr(profile, 'calendar_integrations', {})
        except UserProfile.DoesNotExist:
            calendar_integrations = {}
        
        providers_status = {
            'google': {
                'name': 'Google Calendar',
                'connected': profile.google_calendar_connected if profile else False,
                'provider_key': 'google'
            },
            'outlook': {
                'name': 'Outlook Calendar',
                'connected': profile.outlook_calendar_connected if profile else False,
                'provider_key': 'outlook'
            },
            'exchange': {
                'name': 'Exchange Calendar',
                'connected': 'exchange' in calendar_integrations if calendar_integrations else False,
                'provider_key': 'exchange'
            }
        }
        
        return Response({
            'status': 'success',
            'providers': providers_status
        })
        
    except Exception as e:
        logger.error(f"Error getting calendar providers: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def connect_calendar_provider(request, provider_name):
    """
    Initiate connection to a calendar provider
    """
    try:
        if provider_name == 'google':
            # Simple Google OAuth URL generation
            from django.conf import settings
            import urllib.parse
            
            # Google OAuth parameters
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '268537028303-7ijcl8l6jkf5slbl8melaoio4u494c1p.apps.googleusercontent.com')
            redirect_uri = 'http://localhost:8000/api/v1/calendar/callback/google/'
            scope = 'https://www.googleapis.com/auth/calendar.readonly'
            
            # Build OAuth URL
            params = {
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'scope': scope,
                'response_type': 'code',
                'access_type': 'offline',
                'prompt': 'consent',
                'state': f'user_{request.user.id}'  # Include user ID for security
            }
            
            auth_url = 'https://accounts.google.com/o/oauth2/auth?' + urllib.parse.urlencode(params)
            
            return Response({
                'status': 'success',
                'auth_url': auth_url,
                'provider': provider_name
            })
        
        else:
            return Response({
                'status': 'error',
                'message': f'Provider {provider_name} not yet implemented'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error connecting to {provider_name}: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([])  # Allow unauthenticated access for OAuth callback
def calendar_oauth_callback(request, provider_name):
    """
    Handle OAuth callback from calendar providers
    """
    try:
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            # Redirect to frontend with error
            return HttpResponse(f"""
                <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'calendar_oauth_error',
                            error: '{error}'
                        }}, 'http://localhost:3000');
                        window.close();
                    </script>
                </body>
                </html>
            """, content_type='text/html')
        
        if not code:
            return HttpResponse(f"""
                <html>
                <body>
                    <script>
                        window.opener.postMessage({{
                            type: 'calendar_oauth_error',
                            error: 'Missing authorization code'
                        }}, 'http://localhost:3000');
                        window.close();
                    </script>
                </body>
                </html>
            """, content_type='text/html')
        
        if provider_name == 'google':
            # Extract user ID from state
            if state and state.startswith('user_'):
                user_id = state.replace('user_', '')
                
                # Exchange authorization code for access tokens and sync calendar
                try:
                    from apps.accounts.models import UserProfile
                    from django.contrib.auth.models import User
                    import requests
                    from django.conf import settings
                    
                    user = User.objects.get(id=user_id)
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    
                    # Exchange code for tokens
                    token_url = 'https://oauth2.googleapis.com/token'
                    token_data = {
                        'client_id': settings.GOOGLE_CLIENT_ID,
                        'client_secret': settings.GOOGLE_CLIENT_SECRET,
                        'code': code,
                        'grant_type': 'authorization_code',
                        'redirect_uri': 'http://localhost:8000/api/v1/calendar/callback/google/'
                    }
                    
                    token_response = requests.post(token_url, data=token_data)
                    token_info = token_response.json()
                    
                    if 'access_token' in token_info:
                        # Save tokens to user profile
                        if not hasattr(profile, 'calendar_integrations') or profile.calendar_integrations is None:
                            profile.calendar_integrations = {}
                        
                        profile.calendar_integrations['google'] = {
                            'connected': True,
                            'connected_at': timezone.now().isoformat(),
                            'access_token': token_info['access_token'],
                            'refresh_token': token_info.get('refresh_token'),
                            'expires_in': token_info.get('expires_in', 3600),
                            'token_type': token_info.get('token_type', 'Bearer')
                        }
                        profile.google_calendar_connected = True
                        profile.save()
                        
                        # Sync calendar events immediately
                        sync_google_calendar_events(user, token_info['access_token'])
                        
                    else:
                        logger.error(f"Failed to exchange code for tokens: {token_info}")
                        
                except Exception as e:
                    logger.error(f"Error exchanging code for tokens: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"Error saving Google Calendar connection: {str(e)}")
                
                return HttpResponse(f"""
                    <html>
                    <body>
                        <h2>Calendar Connected Successfully!</h2>
                        <p>You can close this window and return to the application.</p>
                        <script>
                            window.opener.postMessage({{
                                type: 'calendar_oauth_success',
                                provider: 'google',
                                message: 'Google Calendar connected successfully!'
                            }}, 'http://localhost:3000');
                            setTimeout(() => window.close(), 2000);
                        </script>
                    </body>
                    </html>
                """, content_type='text/html')
            else:
                return HttpResponse(f"""
                    <html>
                    <body>
                        <script>
                            window.opener.postMessage({{
                                type: 'calendar_oauth_error',
                                error: 'Invalid state parameter'
                            }}, 'http://localhost:3000');
                            window.close();
                        </script>
                    </body>
                    </html>
                """, content_type='text/html')
        else:
            return Response({
                'status': 'error',
                'message': f'Provider {provider_name} not yet implemented'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback for {provider_name}: {str(e)}")
        return HttpResponse(f"""
            <html>
            <body>
                <script>
                    window.opener.postMessage({{
                        type: 'calendar_oauth_error',
                        error: 'Internal server error'
                    }}, 'http://localhost:3000');
                    window.close();
                </script>
            </body>
            </html>
        """, content_type='text/html')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_calendars(request):
    """
    Trigger calendar synchronization for user
    """
    try:
        from apps.accounts.models import UserProfile
        
        profile = UserProfile.objects.get(user=request.user)
        
        if not profile.google_calendar_connected:
            return Response({
                'status': 'error',
                'message': 'Google Calendar not connected'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get stored access token
        calendar_integrations = getattr(profile, 'calendar_integrations', {})
        google_integration = calendar_integrations.get('google', {})
        access_token = google_integration.get('access_token')
        
        if not access_token:
            return Response({
                'status': 'error',
                'message': 'No access token found. Please reconnect Google Calendar.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Sync events
        events_synced = sync_google_calendar_events(request.user, access_token)
        
        return Response({
            'status': 'success',
            'message': f'Successfully synced {events_synced} events from Google Calendar',
            'events_synced': events_synced
        })
        
    except Exception as e:
        logger.error(f"Error syncing calendars: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_calendar_events(request):
    """
    Get calendar events for user
    """
    try:
        # Get query parameters
        start_date = request.GET.get('start')
        end_date = request.GET.get('end')
        provider = request.GET.get('provider')
        
        # Build query
        query = CalendarEvent.objects.filter(user=request.user)
        
        if start_date:
            from dateutil import parser
            query = query.filter(start_time__gte=parser.parse(start_date))
        
        if end_date:
            from dateutil import parser
            query = query.filter(end_time__lte=parser.parse(end_date))
        
        if provider:
            query = query.filter(provider=provider)
        
        # Get events
        events = query.order_by('start_time')[:100]  # Limit to 100 events
        
        events_data = []
        for event in events:
            events_data.append({
                'id': str(event.id),
                'provider': event.provider,
                'title': event.title,
                'description': event.description,
                'start_time': event.start_time.isoformat(),
                'end_time': event.end_time.isoformat(),
                'location': event.location,
                'meeting_url': event.meeting_url,
                'attendees': event.attendees,
                'is_sales_meeting': event.meeting_created,
                'meeting_id': str(event.meeting.id) if event.meeting else None
            })
        
        return Response({
            'status': 'success',
            'events': events_data,
            'count': len(events_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting calendar events: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sync_status(request):
    """
    Get calendar synchronization status for user
    """
    try:
        sync_statuses = CalendarSyncStatus.objects.filter(user=request.user)
        
        status_data = []
        for sync_status in sync_statuses:
            status_data.append({
                'provider': sync_status.provider,
                'calendar_id': sync_status.calendar_id,
                'status': sync_status.status,
                'last_sync_start': sync_status.last_sync_start.isoformat() if sync_status.last_sync_start else None,
                'last_sync_end': sync_status.last_sync_end.isoformat() if sync_status.last_sync_end else None,
                'last_successful_sync': sync_status.last_successful_sync.isoformat() if sync_status.last_successful_sync else None,
                'events_processed': sync_status.events_processed,
                'events_created': sync_status.events_created,
                'events_updated': sync_status.events_updated,
                'error_message': sync_status.error_message,
                'error_count': sync_status.error_count
            })
        
        return Response({
            'status': 'success',
            'sync_statuses': status_data
        })
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def detect_meetings(request):
    """
    Trigger meeting detection for user's calendar events
    """
    try:
        integration_hub = CalendarIntegrationHub()
        
        # Process meetings for user
        import asyncio
        asyncio.run(integration_hub.process_meetings_for_user(request.user))
        
        # Get newly created meetings
        from apps.meetings.models import Meeting
        recent_meetings = Meeting.objects.filter(
            organizer=request.user,
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('-created_at')
        
        meetings_data = []
        for meeting in recent_meetings:
            meetings_data.append({
                'id': str(meeting.id),
                'title': meeting.title,
                'meeting_type': meeting.meeting_type,
                'confidence_score': meeting.confidence_score,
                'start_time': meeting.start_time.isoformat(),
                'participants_count': meeting.participants.count()
            })
        
        return Response({
            'status': 'success',
            'meetings_detected': len(meetings_data),
            'meetings': meetings_data
        })
        
    except Exception as e:
        logger.error(f"Error detecting meetings: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_meeting_insights(request, event_id):
    """
    Get meeting detection insights for a specific calendar event
    """
    try:
        from .meeting_detection import MeetingDetectionEngine
        
        event = CalendarEvent.objects.get(id=event_id, user=request.user)
        detection_engine = MeetingDetectionEngine()
        
        import asyncio
        insights = asyncio.run(detection_engine.get_detection_insights(event))
        
        return Response({
            'status': 'success',
            'insights': insights
        })
        
    except CalendarEvent.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Calendar event not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting meeting insights: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scheduling_conflicts(request):
    """
    Get scheduling conflicts for user
    """
    try:
        integration_hub = CalendarIntegrationHub()
        
        import asyncio
        conflicts = asyncio.run(integration_hub.resolve_scheduling_conflicts(request.user))
        
        conflicts_data = []
        for conflict in conflicts:
            conflicts_data.append({
                'type': conflict['type'],
                'meeting1': {
                    'id': str(conflict['meeting1'].id),
                    'title': conflict['meeting1'].title,
                    'start_time': conflict['meeting1'].start_time.isoformat(),
                    'end_time': conflict['meeting1'].end_time.isoformat()
                },
                'meeting2': {
                    'id': str(conflict['meeting2'].id),
                    'title': conflict['meeting2'].title,
                    'start_time': conflict['meeting2'].start_time.isoformat(),
                    'end_time': conflict['meeting2'].end_time.isoformat()
                },
                'suggested_resolution': conflict['suggested_resolution']
            })
        
        return Response({
            'status': 'success',
            'conflicts': conflicts_data,
            'count': len(conflicts_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting scheduling conflicts: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
def calendar_webhook(request, provider_name):
    """
    Handle webhook notifications from calendar providers
    """
    try:
        integration_hub = CalendarIntegrationHub()
        
        if provider_name not in integration_hub.providers:
            return JsonResponse({
                'status': 'error',
                'message': f'Unsupported provider: {provider_name}'
            }, status=400)
        
        import json
        webhook_data = json.loads(request.body)
        
        # Handle webhook asynchronously
        from .tasks import handle_calendar_webhook_task
        handle_calendar_webhook_task.delay(provider_name, webhook_data)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook processed'
        })
        
    except Exception as e:
        logger.error(f"Error handling calendar webhook: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disconnect_calendar_provider(request, provider_name):
    """
    Disconnect a calendar provider
    """
    try:
        from apps.accounts.models import UserProfile
        
        profile = UserProfile.objects.get(user=request.user)
        
        if provider_name in profile.calendar_integrations:
            del profile.calendar_integrations[provider_name]
            profile.save()
            
            # Clean up related data
            CalendarEvent.objects.filter(
                user=request.user,
                provider=provider_name
            ).delete()
            
            CalendarSyncStatus.objects.filter(
                user=request.user,
                provider=provider_name
            ).delete()
        
        return Response({
            'status': 'success',
            'message': f'{provider_name.title()} calendar disconnected successfully'
        })
        
    except Exception as e:
        logger.error(f"Error disconnecting {provider_name}: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_calendar_connection(request, provider_name):
    """
    Test connection to a calendar provider
    """
    try:
        integration_hub = CalendarIntegrationHub()
        
        if provider_name not in integration_hub.providers:
            return Response({
                'status': 'error',
                'message': f'Unsupported provider: {provider_name}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        provider = integration_hub.get_provider(provider_name)
        import asyncio
        test_result = asyncio.run(provider.test_connection(request.user))
        
        return Response(test_result)
        
    except Exception as e:
        logger.error(f"Error testing {provider_name} connection: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)