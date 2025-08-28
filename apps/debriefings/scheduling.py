"""
Advanced Debriefing Scheduling Service with Smart Consolidation
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.core.cache import cache

from .models import DebriefingSession, DebriefingTemplate
from .notifications import DebriefingNotificationService, SmartReschedulingService
from apps.meetings.models import Meeting, MeetingParticipant
from apps.analytics.models import DebriefingMetrics

logger = logging.getLogger(__name__)


class AutomatedDebriefingScheduler:
    """
    Advanced automated debriefing scheduling with intelligent consolidation
    """
    
    def __init__(self):
        self.default_delay_minutes = 30
        self.consolidation_window_minutes = 60
        self.max_consolidation_meetings = 5
        self.business_hours = {'start': 9, 'end': 18}
        self.notification_service = DebriefingNotificationService()
        self.rescheduling_service = SmartReschedulingService()
    
    def schedule_debriefing_for_meeting(self, meeting: Meeting, 
                                      force_reschedule: bool = False) -> Optional[DebriefingSession]:
        """
        Main entry point for scheduling debriefings after meeting completion
        """
        try:
            logger.info(f"Processing debriefing scheduling for meeting {meeting.id}")
            
            # Validate meeting eligibility
            if not self._is_meeting_eligible(meeting):
                logger.info(f"Meeting {meeting.id} not eligible for debriefing")
                return None
            
            # Check for existing debriefing
            existing_session = DebriefingSession.objects.filter(meeting=meeting).first()
            if existing_session and not force_reschedule:
                logger.info(f"Debriefing already exists for meeting {meeting.id}")
                return existing_session
            
            # Find consolidation opportunities
            consolidation_candidates = self._find_consolidation_candidates(meeting)
            
            with transaction.atomic():
                if consolidation_candidates:
                    session = self._create_consolidated_debriefing(meeting, consolidation_candidates)
                else:
                    session = self._create_individual_debriefing(meeting)
                
                if session:
                    # Schedule notification sequence
                    self.notification_service.schedule_reminder_sequence(session)
                    
                    # Update meeting status
                    meeting.debriefing_scheduled = True
                    meeting.debriefing_due_at = session.scheduled_time
                    meeting.save()
                    
                    logger.info(f"Successfully scheduled debriefing {session.id} for meeting {meeting.id}")
                
                return session
                
        except Exception as e:
            logger.error(f"Error scheduling debriefing for meeting {meeting.id}: {str(e)}")
            return None
    
    def _is_meeting_eligible(self, meeting: Meeting) -> bool:
        """
        Determine if a meeting qualifies for automated debriefing scheduling
        """
        # Must be a sales meeting
        if not meeting.is_sales_meeting:
            logger.debug(f"Meeting {meeting.id} not a sales meeting")
            return False
        
        # Must be completed
        if meeting.status != 'completed':
            logger.debug(f"Meeting {meeting.id} not completed (status: {meeting.status})")
            return False
        
        # Must have external participants
        external_participants = meeting.participants.filter(is_external=True).count()
        if external_participants == 0:
            logger.debug(f"Meeting {meeting.id} has no external participants")
            return False
        
        # Must meet minimum duration (15 minutes)
        if meeting.duration_minutes < 15:
            logger.debug(f"Meeting {meeting.id} too short ({meeting.duration_minutes} minutes)")
            return False
        
        # Must be recent (within last 24 hours)
        if meeting.end_time < timezone.now() - timedelta(hours=24):
            logger.debug(f"Meeting {meeting.id} too old for debriefing")
            return False
        
        # Check if user has debriefing enabled
        if not self._user_has_debriefing_enabled(meeting.organizer):
            logger.debug(f"User {meeting.organizer.id} has debriefing disabled")
            return False
        
        return True
    
    def _user_has_debriefing_enabled(self, user: User) -> bool:
        """
        Check if user has debriefing enabled in their preferences
        """
        # This would check user preferences
        # For now, assume all users have it enabled
        return True
    
    def _find_consolidation_candidates(self, meeting: Meeting) -> List[Meeting]:
        """
        Find meetings that can be consolidated into a single debriefing session
        """
        try:
            # Define consolidation window
            window_start = meeting.end_time - timedelta(minutes=self.consolidation_window_minutes)
            window_end = meeting.end_time + timedelta(minutes=self.consolidation_window_minutes)
            
            # Find candidate meetings
            candidates = Meeting.objects.filter(
                organizer=meeting.organizer,
                is_sales_meeting=True,
                status='completed',
                start_time__gte=window_start,
                end_time__lte=window_end
            ).exclude(id=meeting.id)
            
            # Exclude meetings that already have debriefings
            candidates = candidates.exclude(debriefing_scheduled=True)
            
            # Analyze consolidation potential
            consolidatable = []
            meeting_participants = set(
                meeting.participants.values_list('email', flat=True)
            )
            
            for candidate in candidates:
                if self._can_consolidate_meetings(meeting, candidate, meeting_participants):
                    consolidatable.append(candidate)
                    
                    # Limit consolidation size
                    if len(consolidatable) >= self.max_consolidation_meetings - 1:
                        break
            
            if consolidatable:
                logger.info(f"Found {len(consolidatable)} meetings for consolidation with {meeting.id}")
            
            return consolidatable
            
        except Exception as e:
            logger.error(f"Error finding consolidation candidates: {str(e)}")
            return []
    
    def _can_consolidate_meetings(self, primary_meeting: Meeting, 
                                candidate_meeting: Meeting, 
                                primary_participants: set) -> bool:
        """
        Determine if two meetings can be consolidated
        """
        try:
            # Get candidate participants
            candidate_participants = set(
                candidate_meeting.participants.values_list('email', flat=True)
            )
            
            # Calculate participant overlap
            overlap = len(primary_participants & candidate_participants)
            total_unique = len(primary_participants | candidate_participants)
            
            if total_unique == 0:
                return False
            
            overlap_ratio = overlap / total_unique
            
            # Require at least 30% participant overlap
            if overlap_ratio < 0.3:
                return False
            
            # Check meeting types compatibility
            compatible_types = {
                'discovery': ['discovery', 'follow_up'],
                'demo': ['demo', 'follow_up'],
                'negotiation': ['negotiation', 'follow_up'],
                'follow_up': ['discovery', 'demo', 'negotiation', 'follow_up'],
                'closing': ['closing'],
                'internal': ['internal'],
                'other': ['other', 'follow_up']
            }
            
            primary_type = primary_meeting.meeting_type
            candidate_type = candidate_meeting.meeting_type
            
            if candidate_type not in compatible_types.get(primary_type, []):
                return False
            
            # Check time proximity (meetings should be close in time)
            time_gap = abs((primary_meeting.start_time - candidate_meeting.end_time).total_seconds() / 60)
            if time_gap > self.consolidation_window_minutes:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking consolidation compatibility: {str(e)}")
            return False
    
    def _create_individual_debriefing(self, meeting: Meeting) -> DebriefingSession:
        """
        Create an individual debriefing session for a single meeting
        """
        try:
            # Calculate optimal scheduling time
            scheduled_time = self._calculate_optimal_debriefing_time(meeting)
            
            # Get appropriate template
            template = self._get_debriefing_template(meeting.meeting_type)
            
            # Create session
            session = DebriefingSession.objects.create(
                meeting=meeting,
                user=meeting.organizer,
                scheduled_time=scheduled_time,
                status='scheduled'
            )
            
            # Initialize conversation data
            session.conversation_data = {
                'session_type': 'individual',
                'meeting_context': {
                    'meeting_id': str(meeting.id),
                    'meeting_type': meeting.meeting_type,
                    'duration_minutes': meeting.duration_minutes,
                    'participant_count': meeting.participants.count(),
                    'external_participant_count': meeting.participants.filter(is_external=True).count()
                },
                'template_id': str(template.id) if template else None,
                'scheduling_metadata': {
                    'scheduled_at': timezone.now().isoformat(),
                    'scheduling_method': 'automated',
                    'delay_minutes': self.default_delay_minutes
                }
            }
            session.save()
            
            logger.info(f"Created individual debriefing {session.id} for meeting {meeting.id}")
            return session
            
        except Exception as e:
            logger.error(f"Error creating individual debriefing: {str(e)}")
            raise
    
    def _create_consolidated_debriefing(self, primary_meeting: Meeting, 
                                     other_meetings: List[Meeting]) -> DebriefingSession:
        """
        Create a consolidated debriefing session for multiple meetings
        """
        try:
            all_meetings = [primary_meeting] + other_meetings
            
            # Use the latest meeting's end time as base for scheduling
            latest_meeting = max(all_meetings, key=lambda m: m.end_time)
            scheduled_time = self._calculate_optimal_debriefing_time(latest_meeting)
            
            # Create session for primary meeting
            session = DebriefingSession.objects.create(
                meeting=primary_meeting,
                user=primary_meeting.organizer,
                scheduled_time=scheduled_time,
                status='scheduled'
            )
            
            # Prepare consolidated meeting data
            consolidated_data = []
            all_participants = set()
            total_duration = 0
            
            for meeting in all_meetings:
                meeting_data = {
                    'meeting_id': str(meeting.id),
                    'title': meeting.title,
                    'meeting_type': meeting.meeting_type,
                    'start_time': meeting.start_time.isoformat(),
                    'end_time': meeting.end_time.isoformat(),
                    'duration_minutes': meeting.duration_minutes,
                    'participants': list(meeting.participants.values(
                        'email', 'name', 'company', 'is_external'
                    ))
                }
                consolidated_data.append(meeting_data)
                
                # Collect unique participants
                for participant in meeting.participants.all():
                    all_participants.add(participant.email)
                
                total_duration += meeting.duration_minutes
            
            # Initialize conversation data
            session.conversation_data = {
                'session_type': 'consolidated',
                'consolidated_meetings': consolidated_data,
                'consolidation_summary': {
                    'total_meetings': len(all_meetings),
                    'total_duration_minutes': total_duration,
                    'unique_participants': len(all_participants),
                    'meeting_types': list(set(m.meeting_type for m in all_meetings)),
                    'time_span': {
                        'start': min(m.start_time for m in all_meetings).isoformat(),
                        'end': max(m.end_time for m in all_meetings).isoformat()
                    }
                },
                'scheduling_metadata': {
                    'scheduled_at': timezone.now().isoformat(),
                    'scheduling_method': 'automated_consolidated',
                    'consolidation_window_minutes': self.consolidation_window_minutes
                }
            }
            session.save()
            
            # Mark all meetings as having debriefing scheduled
            for meeting in all_meetings:
                meeting.debriefing_scheduled = True
                meeting.debriefing_due_at = scheduled_time
                meeting.save()
            
            logger.info(f"Created consolidated debriefing {session.id} for {len(all_meetings)} meetings")
            return session
            
        except Exception as e:
            logger.error(f"Error creating consolidated debriefing: {str(e)}")
            raise
    
    def _calculate_optimal_debriefing_time(self, meeting: Meeting) -> datetime:
        """
        Calculate optimal time for debriefing based on meeting end time and user patterns
        """
        try:
            # Start with default delay
            base_time = meeting.end_time + timedelta(minutes=self.default_delay_minutes)
            
            # Get user's historical patterns
            user_patterns = self._get_user_debriefing_patterns(meeting.organizer)
            
            # Adjust based on user patterns
            if user_patterns['avg_delay_minutes']:
                pattern_time = meeting.end_time + timedelta(
                    minutes=user_patterns['avg_delay_minutes']
                )
                # Use pattern if it's reasonable (between 15 minutes and 4 hours)
                if 15 <= user_patterns['avg_delay_minutes'] <= 240:
                    base_time = pattern_time
            
            # Adjust for business hours
            adjusted_time = self._adjust_for_business_hours(base_time)
            
            # Avoid conflicts with existing meetings (placeholder)
            final_time = self._avoid_meeting_conflicts(adjusted_time, meeting.organizer)
            
            return final_time
            
        except Exception as e:
            logger.error(f"Error calculating optimal debriefing time: {str(e)}")
            # Fallback to simple calculation
            return meeting.end_time + timedelta(minutes=self.default_delay_minutes)
    
    def _get_user_debriefing_patterns(self, user: User) -> Dict:
        """
        Analyze user's historical debriefing patterns
        """
        cache_key = f"user_debriefing_patterns_{user.id}"
        cached_patterns = cache.get(cache_key)
        
        if cached_patterns:
            return cached_patterns
        
        try:
            # Get recent completed debriefings
            recent_sessions = DebriefingSession.objects.filter(
                user=user,
                status='completed',
                started_at__isnull=False
            ).order_by('-started_at')[:20]
            
            if not recent_sessions:
                patterns = {
                    'avg_delay_minutes': None,
                    'preferred_hours': [],
                    'completion_rate': 0,
                    'avg_duration_minutes': None
                }
            else:
                # Calculate average delay
                delays = []
                completion_hours = []
                durations = []
                
                for session in recent_sessions:
                    delay = (session.started_at - session.meeting.end_time).total_seconds() / 60
                    delays.append(delay)
                    completion_hours.append(session.started_at.hour)
                    
                    if session.completed_at:
                        duration = (session.completed_at - session.started_at).total_seconds() / 60
                        durations.append(duration)
                
                patterns = {
                    'avg_delay_minutes': int(sum(delays) / len(delays)) if delays else None,
                    'preferred_hours': list(set(completion_hours)),
                    'completion_rate': len(recent_sessions) / 20 * 100,
                    'avg_duration_minutes': int(sum(durations) / len(durations)) if durations else None
                }
            
            # Cache for 1 hour
            cache.set(cache_key, patterns, 3600)
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing user patterns: {str(e)}")
            return {
                'avg_delay_minutes': None,
                'preferred_hours': [],
                'completion_rate': 0,
                'avg_duration_minutes': None
            }
    
    def _adjust_for_business_hours(self, target_time: datetime) -> datetime:
        """
        Adjust debriefing time to fall within business hours
        """
        try:
            # If target is before business hours, move to start of business day
            if target_time.hour < self.business_hours['start']:
                adjusted = target_time.replace(
                    hour=self.business_hours['start'], 
                    minute=0, second=0, microsecond=0
                )
            # If target is after business hours, move to next business day
            elif target_time.hour >= self.business_hours['end']:
                adjusted = target_time.replace(
                    hour=self.business_hours['start'], 
                    minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
            else:
                adjusted = target_time
            
            # Skip weekends
            while adjusted.weekday() >= 5:  # Saturday = 5, Sunday = 6
                adjusted += timedelta(days=1)
                adjusted = adjusted.replace(
                    hour=self.business_hours['start'], 
                    minute=0, second=0, microsecond=0
                )
            
            return adjusted
            
        except Exception as e:
            logger.error(f"Error adjusting for business hours: {str(e)}")
            return target_time
    
    def _avoid_meeting_conflicts(self, target_time: datetime, user: User) -> datetime:
        """
        Adjust time to avoid conflicts with existing meetings (placeholder)
        """
        # This would integrate with calendar systems to check for conflicts
        # For now, just return the target time
        return target_time
    
    def _get_debriefing_template(self, meeting_type: str) -> Optional[DebriefingTemplate]:
        """
        Get appropriate debriefing template for meeting type
        """
        try:
            template = DebriefingTemplate.objects.filter(
                template_type=meeting_type,
                is_active=True
            ).first()
            
            if not template:
                # Fallback to general template
                template = DebriefingTemplate.objects.filter(
                    template_type='general',
                    is_active=True
                ).first()
            
            return template
            
        except Exception as e:
            logger.error(f"Error getting debriefing template: {str(e)}")
            return None
    
    def reschedule_debriefing(self, session: DebriefingSession, 
                            new_time: Optional[datetime] = None,
                            reason: str = 'user_request') -> DebriefingSession:
        """
        Reschedule a debriefing session with smart time suggestions
        """
        try:
            if session.status not in ['scheduled']:
                raise ValueError(f"Cannot reschedule debriefing in status: {session.status}")
            
            # Cancel existing reminders
            self.notification_service.cancel_scheduled_reminders(session)
            
            # Get new time
            if new_time is None:
                suggestions = self.rescheduling_service.suggest_reschedule_times(session, count=1)
                if suggestions:
                    new_time = suggestions[0]['time']
                else:
                    # Fallback to simple rescheduling
                    new_time = timezone.now() + timedelta(hours=1)
                    new_time = self._adjust_for_business_hours(new_time)
            
            # Update session
            old_time = session.scheduled_time
            session.scheduled_time = new_time
            
            # Update conversation data
            if 'rescheduling_history' not in session.conversation_data:
                session.conversation_data['rescheduling_history'] = []
            
            session.conversation_data['rescheduling_history'].append({
                'old_time': old_time.isoformat(),
                'new_time': new_time.isoformat(),
                'reason': reason,
                'rescheduled_at': timezone.now().isoformat()
            })
            
            session.save()
            
            # Update meeting
            session.meeting.debriefing_due_at = new_time
            session.meeting.save()
            
            # Schedule new reminders
            self.notification_service.schedule_reminder_sequence(session)
            
            logger.info(f"Rescheduled debriefing {session.id} from {old_time} to {new_time}")
            return session
            
        except Exception as e:
            logger.error(f"Error rescheduling debriefing {session.id}: {str(e)}")
            raise
    
    def handle_back_to_back_meetings(self, user: User, time_window_hours: int = 2) -> int:
        """
        Process back-to-back meetings for consolidation opportunities
        """
        try:
            # Find recent completed meetings without debriefings
            cutoff_time = timezone.now() - timedelta(hours=time_window_hours)
            
            recent_meetings = Meeting.objects.filter(
                organizer=user,
                is_sales_meeting=True,
                status='completed',
                end_time__gte=cutoff_time,
                debriefing_scheduled=False
            ).order_by('start_time')
            
            processed_count = 0
            
            for meeting in recent_meetings:
                try:
                    session = self.schedule_debriefing_for_meeting(meeting)
                    if session:
                        processed_count += 1
                except Exception as e:
                    logger.error(f"Error processing meeting {meeting.id}: {str(e)}")
                    continue
            
            logger.info(f"Processed {processed_count} back-to-back meetings for user {user.id}")
            return processed_count
            
        except Exception as e:
            logger.error(f"Error handling back-to-back meetings: {str(e)}")
            return 0
    
    def get_scheduling_statistics(self, user: Optional[User] = None, 
                                days: int = 30) -> Dict:
        """
        Get debriefing scheduling statistics
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            query = DebriefingSession.objects.filter(created_at__gte=start_date)
            if user:
                query = query.filter(user=user)
            
            # Basic counts
            stats = query.aggregate(
                total_scheduled=Count('id'),
                individual_sessions=Count('id', filter=Q(
                    conversation_data__session_type='individual'
                )),
                consolidated_sessions=Count('id', filter=Q(
                    conversation_data__session_type='consolidated'
                )),
                completed=Count('id', filter=Q(status='completed')),
                skipped=Count('id', filter=Q(status='skipped')),
                expired=Count('id', filter=Q(status='expired'))
            )
            
            # Calculate rates
            total = stats['total_scheduled'] or 1
            stats['completion_rate'] = (stats['completed'] / total) * 100
            stats['consolidation_rate'] = (stats['consolidated_sessions'] / total) * 100
            
            # Average scheduling delay
            completed_sessions = query.filter(
                status='completed',
                started_at__isnull=False
            )
            
            if completed_sessions.exists():
                delays = []
                for session in completed_sessions:
                    delay = (session.started_at - session.meeting.end_time).total_seconds() / 60
                    delays.append(delay)
                
                stats['avg_scheduling_delay_minutes'] = sum(delays) / len(delays)
            else:
                stats['avg_scheduling_delay_minutes'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting scheduling statistics: {str(e)}")
            return {}


class QuickSurveyService:
    """
    Service for handling quick survey fallback for skipped debriefings
    """
    
    def __init__(self):
        self.survey_questions = [
            {
                'id': 'meeting_outcome',
                'question': 'How would you rate the overall outcome of this meeting?',
                'type': 'rating',
                'scale': 5,
                'required': True
            },
            {
                'id': 'next_steps',
                'question': 'What are the key next steps from this meeting?',
                'type': 'text',
                'required': True
            },
            {
                'id': 'follow_up_required',
                'question': 'Does this meeting require follow-up actions?',
                'type': 'boolean',
                'required': True
            },
            {
                'id': 'key_insights',
                'question': 'Any key insights or concerns from this meeting?',
                'type': 'text',
                'required': False
            },
            {
                'id': 'competitive_mentions',
                'question': 'Were any competitors mentioned?',
                'type': 'text',
                'required': False
            }
        ]
    
    def create_quick_survey(self, session: DebriefingSession) -> Dict:
        """
        Create a quick survey for a skipped debriefing
        """
        try:
            if session.status != 'skipped':
                raise ValueError("Quick survey only available for skipped debriefings")
            
            # Customize questions based on meeting type
            customized_questions = self._customize_questions_for_meeting(
                session.meeting.meeting_type
            )
            
            survey_data = {
                'survey_id': f"quick_survey_{session.id}",
                'session_id': str(session.id),
                'meeting_title': session.meeting.title,
                'meeting_type': session.meeting.meeting_type,
                'questions': customized_questions,
                'created_at': timezone.now().isoformat(),
                'expires_at': (timezone.now() + timedelta(hours=24)).isoformat(),
                'completed': False
            }
            
            # Store in session data
            session.conversation_data['quick_survey'] = survey_data
            session.save()
            
            logger.info(f"Created quick survey for session {session.id}")
            return survey_data
            
        except Exception as e:
            logger.error(f"Error creating quick survey: {str(e)}")
            raise
    
    def _customize_questions_for_meeting(self, meeting_type: str) -> List[Dict]:
        """
        Customize survey questions based on meeting type
        """
        base_questions = self.survey_questions.copy()
        
        # Add meeting-type specific questions
        if meeting_type == 'demo':
            base_questions.append({
                'id': 'demo_feedback',
                'question': 'How did the prospect respond to the demo?',
                'type': 'text',
                'required': True
            })
        elif meeting_type == 'negotiation':
            base_questions.append({
                'id': 'negotiation_points',
                'question': 'What were the main negotiation points discussed?',
                'type': 'text',
                'required': True
            })
        elif meeting_type == 'discovery':
            base_questions.append({
                'id': 'pain_points',
                'question': 'What pain points were identified?',
                'type': 'text',
                'required': True
            })
        
        return base_questions
    
    def process_survey_response(self, session: DebriefingSession, 
                              responses: Dict) -> bool:
        """
        Process quick survey responses and extract basic insights
        """
        try:
            if 'quick_survey' not in session.conversation_data:
                raise ValueError("No quick survey found for this session")
            
            survey_data = session.conversation_data['quick_survey']
            
            # Validate responses
            self._validate_survey_responses(survey_data['questions'], responses)
            
            # Store responses
            survey_data['responses'] = responses
            survey_data['completed'] = True
            survey_data['completed_at'] = timezone.now().isoformat()
            
            # Extract basic insights
            extracted_data = self._extract_insights_from_survey(responses, session.meeting)
            
            # Update session
            session.conversation_data['quick_survey'] = survey_data
            session.extracted_data = extracted_data
            session.save()
            
            logger.info(f"Processed quick survey for session {session.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing survey response: {str(e)}")
            raise
    
    def _validate_survey_responses(self, questions: List[Dict], responses: Dict):
        """
        Validate survey responses against questions
        """
        for question in questions:
            question_id = question['id']
            
            if question['required'] and question_id not in responses:
                raise ValueError(f"Required question '{question_id}' not answered")
            
            if question_id in responses:
                response = responses[question_id]
                
                if question['type'] == 'rating':
                    if not isinstance(response, int) or not (1 <= response <= question['scale']):
                        raise ValueError(f"Invalid rating for question '{question_id}'")
                elif question['type'] == 'boolean':
                    if not isinstance(response, bool):
                        raise ValueError(f"Invalid boolean response for question '{question_id}'")
                elif question['type'] == 'text':
                    if not isinstance(response, str) or len(response.strip()) == 0:
                        raise ValueError(f"Invalid text response for question '{question_id}'")
    
    def _extract_insights_from_survey(self, responses: Dict, meeting: Meeting) -> Dict:
        """
        Extract structured insights from survey responses
        """
        extracted = {
            'extraction_method': 'quick_survey',
            'confidence_score': 0.6,  # Lower confidence for survey data
            'meeting_outcome': responses.get('meeting_outcome'),
            'next_steps': [],
            'follow_up_required': responses.get('follow_up_required', False),
            'key_insights': [],
            'competitive_intelligence': [],
            'extracted_at': timezone.now().isoformat()
        }
        
        # Process next steps
        if 'next_steps' in responses and responses['next_steps']:
            # Simple parsing - split by newlines or common separators
            next_steps_text = responses['next_steps']
            steps = [step.strip() for step in next_steps_text.replace('\n', ';').split(';') if step.strip()]
            extracted['next_steps'] = steps
        
        # Process key insights
        if 'key_insights' in responses and responses['key_insights']:
            extracted['key_insights'] = [responses['key_insights']]
        
        # Process competitive mentions
        if 'competitive_mentions' in responses and responses['competitive_mentions']:
            extracted['competitive_intelligence'] = [{
                'competitor_name': responses['competitive_mentions'],
                'context': 'mentioned_in_survey',
                'confidence': 0.5
            }]
        
        # Add meeting-type specific extractions
        if meeting.meeting_type == 'demo' and 'demo_feedback' in responses:
            extracted['demo_feedback'] = responses['demo_feedback']
        elif meeting.meeting_type == 'negotiation' and 'negotiation_points' in responses:
            extracted['negotiation_points'] = responses['negotiation_points']
        elif meeting.meeting_type == 'discovery' and 'pain_points' in responses:
            extracted['pain_points'] = responses['pain_points']
        
        return extracted