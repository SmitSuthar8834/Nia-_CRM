"""
Debriefing analytics and completion tracking
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, Sum
from django.contrib.auth.models import User
from django.db import connection

from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight
from apps.meetings.models import Meeting
# from apps.analytics.models import DebriefingMetrics  # Will be added later

logger = logging.getLogger(__name__)


class DebriefingAnalytics:
    """
    Analytics service for debriefing sessions and completion tracking
    """
    
    def __init__(self):
        self.default_period_days = 30
    
    def get_completion_metrics(
        self, 
        user: Optional[User] = None, 
        period_days: int = None,
        team_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive debriefing completion metrics
        """
        try:
            period_days = period_days or self.default_period_days
            start_date = timezone.now() - timedelta(days=period_days)
            
            # Base query
            query = DebriefingSession.objects.filter(created_at__gte=start_date)
            
            if user:
                query = query.filter(user=user)
            elif team_ids:
                query = query.filter(user__id__in=team_ids)
            
            # Get basic counts
            total_sessions = query.count()
            completed_sessions = query.filter(status='completed').count()
            skipped_sessions = query.filter(status='skipped').count()
            expired_sessions = query.filter(status='expired').count()
            in_progress_sessions = query.filter(status='in_progress').count()
            
            # Calculate rates
            completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            skip_rate = (skipped_sessions / total_sessions * 100) if total_sessions > 0 else 0
            expiry_rate = (expired_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            # Get timing metrics
            timing_metrics = self._get_timing_metrics(query.filter(status='completed'))
            
            # Get quality metrics
            quality_metrics = self._get_quality_metrics(query.filter(status='completed'))
            
            # Get trend data
            trend_data = self._get_completion_trends(query, period_days)
            
            return {
                'period_days': period_days,
                'total_sessions': total_sessions,
                'completion_metrics': {
                    'completed': completed_sessions,
                    'skipped': skipped_sessions,
                    'expired': expired_sessions,
                    'in_progress': in_progress_sessions,
                    'completion_rate': round(completion_rate, 2),
                    'skip_rate': round(skip_rate, 2),
                    'expiry_rate': round(expiry_rate, 2)
                },
                'timing_metrics': timing_metrics,
                'quality_metrics': quality_metrics,
                'trends': trend_data
            }
            
        except Exception as e:
            logger.error(f"Error getting completion metrics: {str(e)}")
            return {}
    
    def _get_timing_metrics(self, completed_sessions_query) -> Dict[str, Any]:
        """Get timing-related metrics for completed sessions"""
        try:
            # Calculate duration statistics
            durations = []
            response_times = []
            
            for session in completed_sessions_query.select_related('meeting'):
                if session.started_at and session.completed_at:
                    duration = (session.completed_at - session.started_at).total_seconds() / 60
                    durations.append(duration)
                
                # Time from meeting end to debriefing start
                if session.started_at and session.meeting.end_time:
                    response_time = (session.started_at - session.meeting.end_time).total_seconds() / 60
                    response_times.append(response_time)
            
            return {
                'average_duration_minutes': round(sum(durations) / len(durations), 2) if durations else 0,
                'median_duration_minutes': self._calculate_median(durations),
                'average_response_time_minutes': round(sum(response_times) / len(response_times), 2) if response_times else 0,
                'median_response_time_minutes': self._calculate_median(response_times),
                'sessions_analyzed': len(durations)
            }
            
        except Exception as e:
            logger.error(f"Error calculating timing metrics: {str(e)}")
            return {}
    
    def _get_quality_metrics(self, completed_sessions_query) -> Dict[str, Any]:
        """Get quality-related metrics for completed sessions"""
        try:
            total_sessions = completed_sessions_query.count()
            if total_sessions == 0:
                return {}
            
            # Question completion rates
            question_stats = DebriefingQuestion.objects.filter(
                session__in=completed_sessions_query
            ).aggregate(
                total_questions=Count('id'),
                answered_questions=Count('id', filter=Q(user_response__isnull=False)),
                processed_questions=Count('id', filter=Q(processed=True))
            )
            
            # Insight generation
            insight_stats = DebriefingInsight.objects.filter(
                session__in=completed_sessions_query
            ).aggregate(
                total_insights=Count('id'),
                high_confidence_insights=Count('id', filter=Q(confidence_level='high')),
                validated_insights=Count('id', filter=Q(user_validated=True))
            )
            
            # Confidence scores
            confidence_scores = []
            for session in completed_sessions_query:
                if session.confidence_scores:
                    scores = [score for score in session.confidence_scores.values() 
                             if isinstance(score, (int, float))]
                    if scores:
                        confidence_scores.extend(scores)
            
            return {
                'question_completion_rate': round(
                    (question_stats['answered_questions'] / question_stats['total_questions'] * 100)
                    if question_stats['total_questions'] > 0 else 0, 2
                ),
                'processing_success_rate': round(
                    (question_stats['processed_questions'] / question_stats['total_questions'] * 100)
                    if question_stats['total_questions'] > 0 else 0, 2
                ),
                'average_insights_per_session': round(
                    insight_stats['total_insights'] / total_sessions, 2
                ),
                'high_confidence_insight_rate': round(
                    (insight_stats['high_confidence_insights'] / insight_stats['total_insights'] * 100)
                    if insight_stats['total_insights'] > 0 else 0, 2
                ),
                'insight_validation_rate': round(
                    (insight_stats['validated_insights'] / insight_stats['total_insights'] * 100)
                    if insight_stats['total_insights'] > 0 else 0, 2
                ),
                'average_confidence_score': round(
                    sum(confidence_scores) / len(confidence_scores), 3
                ) if confidence_scores else 0
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {str(e)}")
            return {}
    
    def _get_completion_trends(self, base_query, period_days: int) -> List[Dict[str, Any]]:
        """Get completion trends over time"""
        try:
            # Group by day for the last period
            trends = []
            
            for i in range(period_days):
                date = timezone.now().date() - timedelta(days=i)
                day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)
                
                day_query = base_query.filter(
                    created_at__gte=day_start,
                    created_at__lt=day_end
                )
                
                day_stats = day_query.aggregate(
                    total=Count('id'),
                    completed=Count('id', filter=Q(status='completed')),
                    skipped=Count('id', filter=Q(status='skipped')),
                    expired=Count('id', filter=Q(status='expired'))
                )
                
                trends.append({
                    'date': date.isoformat(),
                    'total_sessions': day_stats['total'],
                    'completed_sessions': day_stats['completed'],
                    'skipped_sessions': day_stats['skipped'],
                    'expired_sessions': day_stats['expired'],
                    'completion_rate': round(
                        (day_stats['completed'] / day_stats['total'] * 100)
                        if day_stats['total'] > 0 else 0, 2
                    )
                })
            
            return list(reversed(trends))  # Oldest to newest
            
        except Exception as e:
            logger.error(f"Error calculating completion trends: {str(e)}")
            return []
    
    def get_user_performance_metrics(
        self, 
        user: User, 
        period_days: int = None
    ) -> Dict[str, Any]:
        """
        Get detailed performance metrics for a specific user
        """
        try:
            period_days = period_days or self.default_period_days
            start_date = timezone.now() - timedelta(days=period_days)
            
            user_sessions = DebriefingSession.objects.filter(
                user=user,
                created_at__gte=start_date
            )
            
            # Basic metrics
            basic_metrics = self.get_completion_metrics(user=user, period_days=period_days)
            
            # Meeting type breakdown
            meeting_type_breakdown = self._get_meeting_type_breakdown(user_sessions)
            
            # Performance compared to team average
            team_comparison = self._get_team_comparison(user, period_days)
            
            # Recent activity
            recent_activity = self._get_recent_activity(user, days=7)
            
            # Improvement suggestions
            suggestions = self._generate_improvement_suggestions(user, user_sessions)
            
            return {
                'user_id': user.id,
                'username': user.username,
                'period_days': period_days,
                'basic_metrics': basic_metrics,
                'meeting_type_breakdown': meeting_type_breakdown,
                'team_comparison': team_comparison,
                'recent_activity': recent_activity,
                'improvement_suggestions': suggestions
            }
            
        except Exception as e:
            logger.error(f"Error getting user performance metrics: {str(e)}")
            return {}
    
    def _get_meeting_type_breakdown(self, user_sessions_query) -> Dict[str, Any]:
        """Get breakdown by meeting type"""
        try:
            breakdown = {}
            
            # Get meeting types and their completion rates
            meeting_types = user_sessions_query.values(
                'meeting__meeting_type'
            ).annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                avg_duration=Avg('meeting__duration_minutes')
            )
            
            for mt in meeting_types:
                meeting_type = mt['meeting__meeting_type'] or 'unknown'
                breakdown[meeting_type] = {
                    'total_sessions': mt['total'],
                    'completed_sessions': mt['completed'],
                    'completion_rate': round(
                        (mt['completed'] / mt['total'] * 100) if mt['total'] > 0 else 0, 2
                    ),
                    'average_meeting_duration': round(mt['avg_duration'] or 0, 2)
                }
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error getting meeting type breakdown: {str(e)}")
            return {}
    
    def _get_team_comparison(self, user: User, period_days: int) -> Dict[str, Any]:
        """Compare user performance to team average"""
        try:
            start_date = timezone.now() - timedelta(days=period_days)
            
            # Get user metrics
            user_metrics = DebriefingSession.objects.filter(
                user=user,
                created_at__gte=start_date
            ).aggregate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed'))
            )
            
            # Get team metrics (assuming same organization/team)
            team_metrics = DebriefingSession.objects.filter(
                created_at__gte=start_date
            ).aggregate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                users=Count('user', distinct=True)
            )
            
            user_completion_rate = (
                user_metrics['completed'] / user_metrics['total'] * 100
            ) if user_metrics['total'] > 0 else 0
            
            team_completion_rate = (
                team_metrics['completed'] / team_metrics['total'] * 100
            ) if team_metrics['total'] > 0 else 0
            
            return {
                'user_completion_rate': round(user_completion_rate, 2),
                'team_average_completion_rate': round(team_completion_rate, 2),
                'performance_vs_team': round(user_completion_rate - team_completion_rate, 2),
                'user_sessions': user_metrics['total'],
                'team_total_sessions': team_metrics['total'],
                'team_size': team_metrics['users']
            }
            
        except Exception as e:
            logger.error(f"Error getting team comparison: {str(e)}")
            return {}
    
    def _get_recent_activity(self, user: User, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent debriefing activity"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            recent_sessions = DebriefingSession.objects.filter(
                user=user,
                created_at__gte=start_date
            ).select_related('meeting').order_by('-created_at')[:10]
            
            activity = []
            for session in recent_sessions:
                activity.append({
                    'session_id': str(session.id),
                    'meeting_title': session.meeting.title,
                    'meeting_date': session.meeting.start_time.isoformat(),
                    'status': session.status,
                    'created_at': session.created_at.isoformat(),
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                    'duration_minutes': session.duration_minutes
                })
            
            return activity
            
        except Exception as e:
            logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def _generate_improvement_suggestions(
        self, 
        user: User, 
        user_sessions_query
    ) -> List[Dict[str, Any]]:
        """Generate personalized improvement suggestions"""
        try:
            suggestions = []
            
            # Analyze completion rate
            total_sessions = user_sessions_query.count()
            completed_sessions = user_sessions_query.filter(status='completed').count()
            completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            
            if completion_rate < 70:
                suggestions.append({
                    'type': 'completion_rate',
                    'priority': 'high',
                    'title': 'Improve Debriefing Completion Rate',
                    'description': f'Your completion rate is {completion_rate:.1f}%. Try to complete debriefings within 30 minutes of meetings.',
                    'action_items': [
                        'Set calendar reminders for debriefing sessions',
                        'Use the quick survey option when time is limited',
                        'Block 15 minutes after each meeting for debriefing'
                    ]
                })
            
            # Analyze response time
            avg_response_time = self._calculate_avg_response_time(user_sessions_query)
            if avg_response_time > 120:  # More than 2 hours
                suggestions.append({
                    'type': 'response_time',
                    'priority': 'medium',
                    'title': 'Reduce Time to Start Debriefing',
                    'description': f'You typically start debriefings {avg_response_time:.0f} minutes after meetings end.',
                    'action_items': [
                        'Start debriefings immediately after meetings',
                        'Use mobile app for quick debriefings',
                        'Set up automatic debriefing notifications'
                    ]
                })
            
            # Analyze question completion
            question_completion = self._calculate_question_completion_rate(user_sessions_query)
            if question_completion < 80:
                suggestions.append({
                    'type': 'question_completion',
                    'priority': 'medium',
                    'title': 'Answer More Questions Completely',
                    'description': f'You complete {question_completion:.1f}% of debriefing questions on average.',
                    'action_items': [
                        'Take notes during meetings to help with debriefing',
                        'Use the clarification feature when questions are unclear',
                        'Skip questions that are not applicable rather than leaving them blank'
                    ]
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating improvement suggestions: {str(e)}")
            return []
    
    def _calculate_avg_response_time(self, sessions_query) -> float:
        """Calculate average response time from meeting end to debriefing start"""
        response_times = []
        
        for session in sessions_query.select_related('meeting'):
            if session.started_at and session.meeting.end_time:
                response_time = (session.started_at - session.meeting.end_time).total_seconds() / 60
                response_times.append(response_time)
        
        return sum(response_times) / len(response_times) if response_times else 0
    
    def _calculate_question_completion_rate(self, sessions_query) -> float:
        """Calculate average question completion rate"""
        total_questions = 0
        answered_questions = 0
        
        for session in sessions_query:
            session_questions = DebriefingQuestion.objects.filter(session=session)
            total_questions += session_questions.count()
            answered_questions += session_questions.filter(user_response__isnull=False).count()
        
        return (answered_questions / total_questions * 100) if total_questions > 0 else 0
    
    def _calculate_median(self, values: List[float]) -> float:
        """Calculate median of a list of values"""
        if not values:
            return 0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def get_system_wide_analytics(self, period_days: int = None) -> Dict[str, Any]:
        """
        Get system-wide debriefing analytics
        """
        try:
            period_days = period_days or self.default_period_days
            start_date = timezone.now() - timedelta(days=period_days)
            
            # Overall metrics
            overall_metrics = self.get_completion_metrics(period_days=period_days)
            
            # User performance distribution
            user_distribution = self._get_user_performance_distribution(start_date)
            
            # Meeting type analysis
            meeting_type_analysis = self._get_system_meeting_type_analysis(start_date)
            
            # AI performance metrics
            ai_performance = self._get_ai_performance_metrics(start_date)
            
            # System health indicators
            health_indicators = self._get_system_health_indicators(start_date)
            
            return {
                'period_days': period_days,
                'overall_metrics': overall_metrics,
                'user_distribution': user_distribution,
                'meeting_type_analysis': meeting_type_analysis,
                'ai_performance': ai_performance,
                'health_indicators': health_indicators,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system-wide analytics: {str(e)}")
            return {}
    
    def _get_user_performance_distribution(self, start_date: datetime) -> Dict[str, Any]:
        """Get distribution of user performance"""
        try:
            # Get completion rates by user
            user_stats = DebriefingSession.objects.filter(
                created_at__gte=start_date
            ).values('user').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed'))
            ).filter(total__gte=3)  # Only users with at least 3 sessions
            
            completion_rates = []
            for stat in user_stats:
                rate = (stat['completed'] / stat['total'] * 100) if stat['total'] > 0 else 0
                completion_rates.append(rate)
            
            if not completion_rates:
                return {}
            
            # Calculate distribution
            high_performers = len([r for r in completion_rates if r >= 80])
            medium_performers = len([r for r in completion_rates if 60 <= r < 80])
            low_performers = len([r for r in completion_rates if r < 60])
            
            return {
                'total_active_users': len(completion_rates),
                'high_performers': high_performers,  # >= 80%
                'medium_performers': medium_performers,  # 60-79%
                'low_performers': low_performers,  # < 60%
                'average_completion_rate': round(sum(completion_rates) / len(completion_rates), 2),
                'median_completion_rate': self._calculate_median(completion_rates)
            }
            
        except Exception as e:
            logger.error(f"Error getting user performance distribution: {str(e)}")
            return {}
    
    def _get_system_meeting_type_analysis(self, start_date: datetime) -> Dict[str, Any]:
        """Get system-wide meeting type analysis"""
        try:
            meeting_types = DebriefingSession.objects.filter(
                created_at__gte=start_date
            ).values('meeting__meeting_type').annotate(
                total=Count('id'),
                completed=Count('id', filter=Q(status='completed')),
                avg_duration=Avg(F('completed_at') - F('started_at'))
            )
            
            analysis = {}
            for mt in meeting_types:
                meeting_type = mt['meeting__meeting_type'] or 'unknown'
                avg_duration_minutes = 0
                if mt['avg_duration']:
                    avg_duration_minutes = mt['avg_duration'].total_seconds() / 60
                
                analysis[meeting_type] = {
                    'total_sessions': mt['total'],
                    'completed_sessions': mt['completed'],
                    'completion_rate': round(
                        (mt['completed'] / mt['total'] * 100) if mt['total'] > 0 else 0, 2
                    ),
                    'avg_debriefing_duration_minutes': round(avg_duration_minutes, 2)
                }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error getting meeting type analysis: {str(e)}")
            return {}
    
    def _get_ai_performance_metrics(self, start_date: datetime) -> Dict[str, Any]:
        """Get AI performance metrics"""
        try:
            completed_sessions = DebriefingSession.objects.filter(
                created_at__gte=start_date,
                status='completed'
            )
            
            # Confidence score analysis
            all_confidence_scores = []
            for session in completed_sessions:
                if session.confidence_scores:
                    scores = [score for score in session.confidence_scores.values() 
                             if isinstance(score, (int, float))]
                    all_confidence_scores.extend(scores)
            
            # Insight generation analysis
            insight_stats = DebriefingInsight.objects.filter(
                session__in=completed_sessions
            ).aggregate(
                total_insights=Count('id'),
                high_confidence=Count('id', filter=Q(confidence_level='high')),
                validated=Count('id', filter=Q(user_validated=True))
            )
            
            # Question processing success
            question_stats = DebriefingQuestion.objects.filter(
                session__in=completed_sessions
            ).aggregate(
                total_questions=Count('id'),
                processed_successfully=Count('id', filter=Q(processed=True))
            )
            
            return {
                'average_confidence_score': round(
                    sum(all_confidence_scores) / len(all_confidence_scores), 3
                ) if all_confidence_scores else 0,
                'confidence_score_distribution': self._get_confidence_distribution(all_confidence_scores),
                'insight_generation_rate': round(
                    insight_stats['total_insights'] / completed_sessions.count(), 2
                ) if completed_sessions.count() > 0 else 0,
                'high_confidence_insight_rate': round(
                    (insight_stats['high_confidence'] / insight_stats['total_insights'] * 100)
                    if insight_stats['total_insights'] > 0 else 0, 2
                ),
                'insight_validation_rate': round(
                    (insight_stats['validated'] / insight_stats['total_insights'] * 100)
                    if insight_stats['total_insights'] > 0 else 0, 2
                ),
                'question_processing_success_rate': round(
                    (question_stats['processed_successfully'] / question_stats['total_questions'] * 100)
                    if question_stats['total_questions'] > 0 else 0, 2
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting AI performance metrics: {str(e)}")
            return {}
    
    def _get_confidence_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Get distribution of confidence scores"""
        if not scores:
            return {}
        
        distribution = {
            'very_low': len([s for s in scores if s < 0.3]),
            'low': len([s for s in scores if 0.3 <= s < 0.5]),
            'medium': len([s for s in scores if 0.5 <= s < 0.7]),
            'high': len([s for s in scores if 0.7 <= s < 0.9]),
            'very_high': len([s for s in scores if s >= 0.9])
        }
        
        return distribution
    
    def _get_system_health_indicators(self, start_date: datetime) -> Dict[str, Any]:
        """Get system health indicators"""
        try:
            # Simple health indicators for now
            total_sessions = DebriefingSession.objects.filter(
                created_at__gte=start_date
            ).count()
            
            # Session timeout analysis
            timeout_sessions = DebriefingSession.objects.filter(
                created_at__gte=start_date,
                status='expired'
            ).count()
            
            error_metrics = 0  # TODO: Implement error tracking
            avg_response_time = 1000  # Mock response time
            
            return {
                'error_rate': round(
                    (error_metrics / total_sessions * 100) if total_sessions > 0 else 0, 2
                ),
                'timeout_rate': round(
                    (timeout_sessions / total_sessions * 100) if total_sessions > 0 else 0, 2
                ),
                'average_ai_response_time_ms': round(avg_response_time, 2),
                'total_sessions_analyzed': total_sessions,
                'health_score': self._calculate_health_score(
                    error_metrics, timeout_sessions, total_sessions
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting system health indicators: {str(e)}")
            return {}
    
    def _calculate_health_score(self, errors: int, timeouts: int, total: int) -> float:
        """Calculate overall system health score (0-100)"""
        if total == 0:
            return 100.0
        
        error_rate = errors / total
        timeout_rate = timeouts / total
        
        # Health score decreases with errors and timeouts
        health_score = 100 - (error_rate * 50) - (timeout_rate * 30)
        
        return max(0, min(100, round(health_score, 1)))


class DebriefingExporter:
    """
    Export debriefing data in various formats
    """
    
    def __init__(self):
        self.analytics = DebriefingAnalytics()
    
    def export_session_summary(self, session: DebriefingSession) -> Dict[str, Any]:
        """Export comprehensive session summary"""
        try:
            # Basic session info
            session_info = {
                'session_id': str(session.id),
                'meeting_title': session.meeting.title,
                'meeting_date': session.meeting.start_time.isoformat(),
                'meeting_duration_minutes': session.meeting.duration_minutes,
                'meeting_type': session.meeting.meeting_type,
                'organizer': session.user.username,
                'status': session.status,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                'debriefing_duration_minutes': session.duration_minutes
            }
            
            # Questions and responses
            questions = []
            for question in session.questions.all().order_by('question_order'):
                questions.append({
                    'order': question.question_order,
                    'type': question.question_type,
                    'question': question.question_text,
                    'response': question.user_response,
                    'is_follow_up': question.is_follow_up,
                    'processed': question.processed
                })
            
            # Insights
            insights = []
            for insight in session.insights.all():
                insights.append({
                    'type': insight.insight_type,
                    'title': insight.title,
                    'description': insight.description,
                    'confidence': insight.confidence_level,
                    'validated': insight.user_validated,
                    'suggested_actions': insight.suggested_actions
                })
            
            # Extracted data
            extracted_data = session.extracted_data or {}
            
            return {
                'session_info': session_info,
                'conversation': {
                    'questions_and_responses': questions,
                    'total_questions': len(questions),
                    'answered_questions': len([q for q in questions if q['response']])
                },
                'insights': insights,
                'extracted_data': extracted_data,
                'export_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting session summary: {str(e)}")
            return {}
    
    def export_user_report(
        self, 
        user: User, 
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Export comprehensive user performance report"""
        try:
            # Get user metrics
            user_metrics = self.analytics.get_user_performance_metrics(user, period_days)
            
            # Get recent sessions
            start_date = timezone.now() - timedelta(days=period_days)
            recent_sessions = DebriefingSession.objects.filter(
                user=user,
                created_at__gte=start_date
            ).select_related('meeting').order_by('-created_at')
            
            sessions_summary = []
            for session in recent_sessions:
                sessions_summary.append({
                    'session_id': str(session.id),
                    'meeting_title': session.meeting.title,
                    'meeting_date': session.meeting.start_time.isoformat(),
                    'status': session.status,
                    'duration_minutes': session.duration_minutes,
                    'insights_count': session.insights.count()
                })
            
            return {
                'user_info': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'report_period_days': period_days,
                'performance_metrics': user_metrics,
                'sessions_summary': sessions_summary,
                'export_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting user report: {str(e)}")
            return {}
    
    def export_system_report(self, period_days: int = 30) -> Dict[str, Any]:
        """Export system-wide analytics report"""
        try:
            system_analytics = self.analytics.get_system_wide_analytics(period_days)
            
            return {
                'report_type': 'system_wide_analytics',
                'report_period_days': period_days,
                'analytics': system_analytics,
                'export_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error exporting system report: {str(e)}")
            return {}