"""
Calendar Integration Services
"""
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction

from .models import CalendarEvent, CalendarSyncStatus
from .providers.google_calendar import GoogleCalendarProvider
from .providers.outlook_calendar import OutlookCalendarProvider
from .providers.exchange_calendar import ExchangeCalendarProvider
from .meeting_detection import MeetingDetectionEngine
from .meeting_classifier import MeetingTypeClassifier

logger = logging.getLogger(__name__)


class CalendarIntegrationHub:
    """
    Central hub for managing multiple calendar integrations
    """
    
    def __init__(self):
        self.providers = {
            'google': GoogleCalendarProvider(),
            'outlook': OutlookCalendarProvider(),
            'exchange': ExchangeCalendarProvider(),
        }
        self.meeting_detector = MeetingDetectionEngine()
        self.meeting_classifier = MeetingTypeClassifier()
    
    def get_provider(self, provider_name: str):
        """Get calendar provider by name"""
        if provider_name not in self.providers:
            raise ValueError(f"Unsupported calendar provider: {provider_name}")
        return self.providers[provider_name]
    
    async def sync_user_calendars(self, user: User, provider_names: List[str] = None) -> Dict[str, Any]:
        """
        Sync calendars for a user across multiple providers
        """
        if provider_names is None:
            provider_names = list(self.providers.keys())
        
        results = {}
        
        for provider_name in provider_names:
            try:
                provider = self.get_provider(provider_name)
                if await provider.is_user_connected(user):
                    result = await self.sync_provider_calendars(user, provider_name)
                    results[provider_name] = result
                else:
                    results[provider_name] = {'status': 'not_connected'}
            except Exception as e:
                logger.error(f"Error syncing {provider_name} for user {user.id}: {str(e)}")
                results[provider_name] = {'status': 'error', 'error': str(e)}
        
        return results
    
    async def sync_provider_calendars(self, user: User, provider_name: str) -> Dict[str, Any]:
        """
        Sync all calendars for a specific provider
        """
        provider = self.get_provider(provider_name)
        
        try:
            # Get user's calendars
            calendars = await provider.get_user_calendars(user)
            
            sync_results = {}
            total_events_processed = 0
            
            for calendar in calendars:
                calendar_id = calendar['id']
                
                # Get or create sync status
                sync_status, created = CalendarSyncStatus.objects.get_or_create(
                    user=user,
                    provider=provider_name,
                    calendar_id=calendar_id,
                    defaults={'status': 'idle'}
                )
                
                # Start sync
                sync_status.start_sync()
                
                try:
                    # Sync calendar events
                    events_result = await self.sync_calendar_events(
                        user, provider_name, calendar_id, sync_status
                    )
                    
                    sync_status.complete_sync(events_result)
                    sync_results[calendar_id] = events_result
                    total_events_processed += events_result.get('processed', 0)
                    
                except Exception as e:
                    sync_status.fail_sync(str(e))
                    sync_results[calendar_id] = {'status': 'error', 'error': str(e)}
            
            # Process meetings after all events are synced
            await self.process_meetings_for_user(user)
            
            return {
                'status': 'success',
                'calendars_synced': len(sync_results),
                'total_events_processed': total_events_processed,
                'calendar_results': sync_results
            }
            
        except Exception as e:
            logger.error(f"Error syncing {provider_name} calendars for user {user.id}: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    async def sync_calendar_events(
        self, 
        user: User, 
        provider_name: str, 
        calendar_id: str, 
        sync_status: CalendarSyncStatus
    ) -> Dict[str, int]:
        """
        Sync events for a specific calendar
        """
        provider = self.get_provider(provider_name)
        
        # Calculate sync window (last 30 days to next 90 days)
        time_min = timezone.now() - timedelta(days=30)
        time_max = timezone.now() + timedelta(days=90)
        
        # Get events from provider
        events = await provider.get_calendar_events(
            user, calendar_id, time_min, time_max, sync_status.sync_token
        )
        
        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'deleted': 0
        }
        
        with transaction.atomic():
            for event_data in events.get('items', []):
                stats['processed'] += 1
                
                # Process event
                event, created = await self.process_calendar_event(
                    user, provider_name, calendar_id, event_data
                )
                
                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1
            
            # Update sync token for incremental sync
            if 'nextSyncToken' in events:
                sync_status.sync_token = events['nextSyncToken']
                sync_status.save()
        
        return stats
    
    async def process_calendar_event(
        self, 
        user: User, 
        provider_name: str, 
        calendar_id: str, 
        event_data: Dict[str, Any]
    ) -> Tuple[CalendarEvent, bool]:
        """
        Process a single calendar event
        """
        provider = self.get_provider(provider_name)
        
        # Parse event data
        parsed_event = provider.parse_event_data(event_data)
        
        # Get or create calendar event
        event, created = CalendarEvent.objects.update_or_create(
            provider=provider_name,
            provider_event_id=parsed_event['id'],
            user=user,
            defaults={
                'calendar_id': calendar_id,
                'title': parsed_event['title'],
                'description': parsed_event.get('description', ''),
                'start_time': parsed_event['start_time'],
                'end_time': parsed_event['end_time'],
                'timezone': parsed_event.get('timezone', 'UTC'),
                'location': parsed_event.get('location', ''),
                'meeting_url': parsed_event.get('meeting_url', ''),
                'event_status': parsed_event.get('status', 'confirmed'),
                'is_all_day': parsed_event.get('is_all_day', False),
                'is_recurring': parsed_event.get('is_recurring', False),
                'recurrence_rule': parsed_event.get('recurrence_rule', ''),
                'organizer_email': parsed_event.get('organizer_email', ''),
                'organizer_name': parsed_event.get('organizer_name', ''),
                'attendees': parsed_event.get('attendees', []),
                'last_modified': parsed_event.get('last_modified', timezone.now()),
                'etag': parsed_event.get('etag', ''),
            }
        )
        
        return event, created
    
    async def process_meetings_for_user(self, user: User):
        """
        Process calendar events to detect and create meetings
        """
        from asgiref.sync import sync_to_async
        
        # Get unprocessed calendar events using sync_to_async
        @sync_to_async
        def get_unprocessed_events():
            return list(CalendarEvent.objects.filter(
                user=user,
                meeting_created=False,
                start_time__gte=timezone.now() - timedelta(days=30)
            ).order_by('start_time'))
        
        unprocessed_events = await get_unprocessed_events()
        
        for event in unprocessed_events:
            try:
                await self.process_single_event_for_meeting(event)
            except Exception as e:
                logger.error(f"Error processing event {event.id} for meetings: {str(e)}")
    
    async def process_single_event_for_meeting(self, event: CalendarEvent):
        """
        Process a single calendar event for meeting detection
        """
        from asgiref.sync import sync_to_async
        
        # Detect if this is a sales meeting
        is_sales_meeting, confidence = await self.meeting_detector.detect_sales_meeting(event)
        
        logger.info(f"Meeting detection for event {event.id}: is_sales={is_sales_meeting}, confidence={confidence}")
        
        if is_sales_meeting and confidence >= 0.5:  # Lower threshold for testing
            # Classify meeting type
            meeting_type = await self.meeting_classifier.classify_meeting_type(event)
            
            # Create meeting using sync_to_async
            @sync_to_async
            def create_meeting_and_participants():
                from apps.meetings.models import Meeting, MeetingParticipant
                
                with transaction.atomic():
                    meeting = Meeting.objects.create(
                        calendar_event_id=f"{event.provider}:{event.provider_event_id}",
                        calendar_provider=event.provider,
                        title=event.title,
                        description=event.description,
                        start_time=event.start_time,
                        end_time=event.end_time,
                        timezone=event.timezone,
                        location=event.location,
                        meeting_url=event.meeting_url,
                        meeting_type=meeting_type,
                        is_sales_meeting=True,
                        confidence_score=confidence,
                        organizer=event.user,
                    )
                    
                    # Create participants
                    for attendee in event.attendees:
                        MeetingParticipant.objects.create(
                            meeting=meeting,
                            email=attendee.get('email', ''),
                            name=attendee.get('name', ''),
                            participant_type=attendee.get('type', 'required'),
                            response_status=attendee.get('response_status', 'no_response'),
                            is_external=not attendee.get('email', '').endswith('@ourcompany.com'),
                        )
                    
                    # Schedule debriefing (if method exists)
                    if hasattr(meeting, 'schedule_debriefing'):
                        meeting.schedule_debriefing()
                    else:
                        # Set debriefing_scheduled manually
                        meeting.debriefing_scheduled = True
                        meeting.save()
                    
                    # Mark event as processed
                    event.meeting_created = True
                    event.meeting = meeting
                    event.save()
                    
                    return meeting
            
            meeting = await create_meeting_and_participants()
            logger.info(f"Created meeting {meeting.id} from calendar event {event.id}")
    
    async def detect_calendar_changes(self, user: User) -> List[Dict[str, Any]]:
        """
        Detect changes in calendar events and sync accordingly
        """
        changes = []
        
        for provider_name in self.providers.keys():
            provider = self.get_provider(provider_name)
            
            if await provider.is_user_connected(user):
                try:
                    provider_changes = await provider.detect_changes(user)
                    changes.extend(provider_changes)
                except Exception as e:
                    logger.error(f"Error detecting changes for {provider_name}: {str(e)}")
        
        return changes
    
    async def handle_calendar_webhook(self, provider_name: str, webhook_data: Dict[str, Any]):
        """
        Handle webhook notifications from calendar providers
        """
        provider = self.get_provider(provider_name)
        
        try:
            # Parse webhook data
            change_info = provider.parse_webhook_data(webhook_data)
            
            # Get affected user
            user = User.objects.get(id=change_info['user_id'])
            
            # Sync affected calendar
            await self.sync_provider_calendars(user, provider_name)
            
            logger.info(f"Processed webhook for {provider_name}, user {user.id}")
            
        except Exception as e:
            logger.error(f"Error handling webhook for {provider_name}: {str(e)}")
    
    async def resolve_scheduling_conflicts(self, user: User) -> List[Dict[str, Any]]:
        """
        Detect and resolve scheduling conflicts with enhanced logic
        """
        from asgiref.sync import sync_to_async
        
        conflicts = []
        
        # Get user's meetings for the next 30 days using sync_to_async
        @sync_to_async
        def get_upcoming_meetings():
            return list(CalendarEvent.objects.filter(
                user=user,
                start_time__gte=timezone.now(),
                start_time__lte=timezone.now() + timedelta(days=30),
                event_status='confirmed'
            ).order_by('start_time'))
        
        upcoming_meetings = await get_upcoming_meetings()
        
        # Detect overlapping meetings
        for i, meeting1 in enumerate(upcoming_meetings):
            for meeting2 in upcoming_meetings[i+1:]:
                if self._meetings_overlap(meeting1, meeting2):
                    conflict = {
                        'type': 'overlap',
                        'meeting1': meeting1,
                        'meeting2': meeting2,
                        'suggested_resolution': await self._suggest_conflict_resolution(meeting1, meeting2),
                        'severity': self._calculate_conflict_severity(meeting1, meeting2),
                        'auto_resolvable': await self._is_auto_resolvable(meeting1, meeting2)
                    }
                    conflicts.append(conflict)
        
        # Detect travel time conflicts
        travel_conflicts = await self._detect_travel_conflicts(upcoming_meetings)
        conflicts.extend(travel_conflicts)
        
        # Sort conflicts by severity
        conflicts.sort(key=lambda x: x.get('severity', 0), reverse=True)
        
        return conflicts
    
    def _meetings_overlap(self, meeting1: CalendarEvent, meeting2: CalendarEvent) -> bool:
        """Check if two meetings overlap"""
        return (meeting1.start_time < meeting2.end_time and 
                meeting2.start_time < meeting1.end_time)
    
    async def _suggest_conflict_resolution(
        self, 
        meeting1: CalendarEvent, 
        meeting2: CalendarEvent
    ) -> Dict[str, Any]:
        """Enhanced conflict resolution with multiple factors"""
        
        # Calculate priority scores for both meetings
        score1 = await self._calculate_meeting_priority_score(meeting1)
        score2 = await self._calculate_meeting_priority_score(meeting2)
        
        # Determine resolution based on scores and other factors
        if abs(score1 - score2) < 0.1:  # Very close scores
            return {
                'action': 'manual_review',
                'reason': 'Meetings have similar priority - manual review recommended',
                'score1': score1,
                'score2': score2,
                'suggested_alternatives': await self._suggest_alternative_times(meeting1, meeting2)
            }
        
        # Clear priority difference
        if score1 > score2:
            higher_priority = meeting1
            lower_priority = meeting2
            higher_score = score1
        else:
            higher_priority = meeting2
            lower_priority = meeting1
            higher_score = score2
        
        # Check if lower priority meeting can be moved to virtual
        if not lower_priority.meeting_url and higher_priority.location:
            return {
                'action': 'make_virtual',
                'meeting_to_modify': lower_priority.id,
                'reason': f'Convert to virtual meeting to avoid travel conflict',
                'priority_scores': {'meeting1': score1, 'meeting2': score2}
            }
        
        # Suggest rescheduling lower priority meeting
        alternative_times = await self._find_alternative_times(lower_priority, higher_priority)
        
        return {
            'action': 'reschedule',
            'meeting_to_reschedule': lower_priority.id,
            'reason': f'Lower priority meeting (score: {higher_score:.2f})',
            'priority_scores': {'meeting1': score1, 'meeting2': score2},
            'suggested_times': alternative_times[:3]  # Top 3 alternatives
        }
    
    async def _calculate_meeting_priority_score(self, meeting: CalendarEvent) -> float:
        """Calculate priority score for a meeting based on multiple factors"""
        score = 0.0
        
        # Meeting type priority
        if meeting.meeting and hasattr(meeting.meeting, 'meeting_type'):
            type_scores = {
                'closing': 1.0,
                'negotiation': 0.9,
                'demo': 0.7,
                'discovery': 0.6,
                'follow_up': 0.4,
                'internal': 0.2
            }
            score += type_scores.get(meeting.meeting.meeting_type, 0.3)
        
        # External attendees boost priority
        external_count = len(meeting.external_attendees)
        if external_count > 0:
            score += min(external_count * 0.2, 0.6)  # Cap at 0.6
        
        # Recurring meetings have lower priority for rescheduling
        if meeting.is_recurring:
            score -= 0.2
        
        # Meeting duration factor (longer meetings harder to reschedule)
        duration_hours = meeting.duration_minutes / 60
        if duration_hours > 2:
            score += 0.1
        
        # Time until meeting (urgent meetings have higher priority)
        hours_until = (meeting.start_time - timezone.now()).total_seconds() / 3600
        if hours_until < 24:
            score += 0.3
        elif hours_until < 48:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _calculate_conflict_severity(self, meeting1: CalendarEvent, meeting2: CalendarEvent) -> int:
        """Calculate conflict severity (1-10, 10 being most severe)"""
        severity = 5  # Base severity
        
        # Both are sales meetings
        if meeting1.meeting and meeting2.meeting:
            severity += 3
        
        # External attendees involved
        if meeting1.external_attendees or meeting2.external_attendees:
            severity += 2
        
        # Short notice (less than 24 hours)
        hours_until = min(
            (meeting1.start_time - timezone.now()).total_seconds() / 3600,
            (meeting2.start_time - timezone.now()).total_seconds() / 3600
        )
        if hours_until < 24:
            severity += 2
        
        # Long meetings are harder to reschedule
        total_duration = meeting1.duration_minutes + meeting2.duration_minutes
        if total_duration > 180:  # More than 3 hours total
            severity += 1
        
        return min(severity, 10)
    
    async def _is_auto_resolvable(self, meeting1: CalendarEvent, meeting2: CalendarEvent) -> bool:
        """Determine if conflict can be automatically resolved"""
        
        # Don't auto-resolve if both have external attendees
        if meeting1.external_attendees and meeting2.external_attendees:
            return False
        
        # Don't auto-resolve if both are high-priority sales meetings
        if (meeting1.meeting and meeting2.meeting and 
            meeting1.meeting.meeting_type in ['closing', 'negotiation'] and
            meeting2.meeting.meeting_type in ['closing', 'negotiation']):
            return False
        
        # Don't auto-resolve if very short notice (less than 2 hours)
        hours_until = min(
            (meeting1.start_time - timezone.now()).total_seconds() / 3600,
            (meeting2.start_time - timezone.now()).total_seconds() / 3600
        )
        if hours_until < 2:
            return False
        
        return True
    
    async def _detect_travel_conflicts(self, meetings: List[CalendarEvent]) -> List[Dict[str, Any]]:
        """Detect conflicts due to insufficient travel time between meetings"""
        travel_conflicts = []
        
        for i in range(len(meetings) - 1):
            current_meeting = meetings[i]
            next_meeting = meetings[i + 1]
            
            # Skip if meetings are on different days
            if current_meeting.end_time.date() != next_meeting.start_time.date():
                continue
            
            # Calculate time between meetings
            time_between = (next_meeting.start_time - current_meeting.end_time).total_seconds() / 60
            
            # Check if both meetings have physical locations
            if current_meeting.location and next_meeting.location:
                # Estimate travel time (simplified - in reality you'd use maps API)
                estimated_travel_time = await self._estimate_travel_time(
                    current_meeting.location, 
                    next_meeting.location
                )
                
                if time_between < estimated_travel_time:
                    travel_conflicts.append({
                        'type': 'travel_time',
                        'meeting1': current_meeting,
                        'meeting2': next_meeting,
                        'time_between_minutes': time_between,
                        'estimated_travel_minutes': estimated_travel_time,
                        'suggested_resolution': {
                            'action': 'extend_buffer',
                            'recommended_buffer': estimated_travel_time + 15,  # Add 15 min buffer
                            'alternative': 'make_virtual'
                        },
                        'severity': 8 if time_between < estimated_travel_time / 2 else 6,
                        'auto_resolvable': time_between < 30  # Auto-resolve if very tight
                    })
        
        return travel_conflicts
    
    async def _estimate_travel_time(self, location1: str, location2: str) -> int:
        """Estimate travel time between two locations (simplified implementation)"""
        # In a real implementation, you would use Google Maps API or similar
        # This is a simplified heuristic
        
        if not location1 or not location2:
            return 0
        
        # Same location
        if location1.lower() == location2.lower():
            return 0
        
        # Check for common patterns
        if 'virtual' in location1.lower() or 'virtual' in location2.lower():
            return 0
        
        if 'zoom' in location1.lower() or 'zoom' in location2.lower():
            return 0
        
        if 'teams' in location1.lower() or 'teams' in location2.lower():
            return 0
        
        # Simple heuristic based on location strings
        if any(word in location1.lower() for word in ['building', 'floor', 'room']):
            if any(word in location2.lower() for word in ['building', 'floor', 'room']):
                return 10  # Same building/campus
        
        # Default travel time for different locations
        return 30
    
    async def _suggest_alternative_times(self, meeting1: CalendarEvent, meeting2: CalendarEvent) -> List[Dict[str, Any]]:
        """Suggest alternative times for conflicting meetings"""
        alternatives = []
        
        from asgiref.sync import sync_to_async
        
        # Get user's calendar for the week
        week_start = meeting1.start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        @sync_to_async
        def get_user_events():
            return list(CalendarEvent.objects.filter(
                user=meeting1.user,
                start_time__gte=week_start,
                start_time__lte=week_end,
                event_status='confirmed'
            ).order_by('start_time'))
        
        user_events = await get_user_events()
        
        # Find free slots
        business_hours = [(9, 17)]  # 9 AM to 5 PM
        
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            
            # Skip weekends (simplified)
            if current_date.weekday() >= 5:
                continue
            
            for start_hour, end_hour in business_hours:
                for hour in range(start_hour, end_hour):
                    potential_start = current_date.replace(hour=hour, minute=0)
                    potential_end = potential_start + timedelta(minutes=meeting1.duration_minutes)
                    
                    # Check if slot is free
                    if self._is_time_slot_free(user_events, potential_start, potential_end):
                        alternatives.append({
                            'start_time': potential_start.isoformat(),
                            'end_time': potential_end.isoformat(),
                            'day_name': potential_start.strftime('%A'),
                            'time_display': potential_start.strftime('%I:%M %p')
                        })
                        
                        if len(alternatives) >= 5:  # Limit to 5 suggestions
                            return alternatives
        
        return alternatives
    
    async def _find_alternative_times(self, meeting_to_move: CalendarEvent, fixed_meeting: CalendarEvent) -> List[Dict[str, Any]]:
        """Find alternative times for a meeting that needs to be rescheduled"""
        return await self._suggest_alternative_times(meeting_to_move, fixed_meeting)
    
    def _is_time_slot_free(self, events: List[CalendarEvent], start_time: timezone.datetime, end_time: timezone.datetime) -> bool:
        """Check if a time slot is free of conflicts"""
        for event in events:
            if (start_time < event.end_time and end_time > event.start_time):
                return False
        return True


class CalendarEventChangeDetector:
    """
    Detects changes in calendar events and triggers appropriate actions
    """
    
    def __init__(self):
        self.integration_hub = CalendarIntegrationHub()
    
    async def monitor_changes(self, user: User):
        """
        Monitor calendar changes for a user
        """
        while True:
            try:
                changes = await self.integration_hub.detect_calendar_changes(user)
                
                for change in changes:
                    await self.process_change(change)
                
                # Wait before next check
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error monitoring calendar changes: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def process_change(self, change: Dict[str, Any]):
        """
        Process a detected calendar change
        """
        change_type = change.get('type')
        
        if change_type == 'event_created':
            await self._handle_event_created(change)
        elif change_type == 'event_updated':
            await self._handle_event_updated(change)
        elif change_type == 'event_deleted':
            await self._handle_event_deleted(change)
    
    async def _handle_event_created(self, change: Dict[str, Any]):
        """Handle new calendar event"""
        event_data = change['event_data']
        user = change['user']
        
        # Process the new event
        event, created = await self.integration_hub.process_calendar_event(
            user, change['provider'], change['calendar_id'], event_data
        )
        
        if created:
            # Check if it should become a meeting
            await self.integration_hub.process_single_event_for_meeting(event)
    
    async def _handle_event_updated(self, change: Dict[str, Any]):
        """Handle updated calendar event"""
        # Update the existing event and check if meeting needs updates
        pass
    
    async def _handle_event_deleted(self, change: Dict[str, Any]):
        """Handle deleted calendar event"""
        # Mark associated meeting as cancelled if exists
        pass