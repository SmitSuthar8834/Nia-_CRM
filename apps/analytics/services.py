"""
Analytics Services for Meeting Intelligence System
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.db.models import Count, Avg, Q, F, Sum
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.cache import cache

from .models import PerformanceMetric, UserEngagementMetric, DataQualityMetric, SystemHealthMetric, Report
from apps.meetings.models import Meeting, MeetingParticipant
from apps.debriefings.models import DebriefingSession
from apps.leads.models import Lead
from apps.crm_sync.models import SyncLog

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Core analytics service for data aggregation and calculation"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def calculate_debriefing_completion_rate(self, start_date: datetime, end_date: datetime, 
                                           user: Optional[User] = None) -> Dict[str, Any]:
        """Calculate debriefing completion rates"""
        cache_key = f"debriefing_completion_{start_date.date()}_{end_date.date()}_{user.id if user else 'all'}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Base query for meetings in the period
        meetings_query = Meeting.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date,
            is_sales_meeting=True
        )
        
        if user:
            meetings_query = meetings_query.filter(organizer=user)
        
        total_meetings = meetings_query.count()
        
        # Count completed debriefings
        completed_debriefings = meetings_query.filter(
            debriefing_completed=True
        ).count()
        
        # Count scheduled but not completed
        scheduled_debriefings = meetings_query.filter(
            debriefing_scheduled=True,
            debriefing_completed=False
        ).count()
        
        completion_rate = (completed_debriefings / total_meetings * 100) if total_meetings > 0 else 0
        
        result = {
            'total_meetings': total_meetings,
            'completed_debriefings': completed_debriefings,
            'scheduled_debriefings': scheduled_debriefings,
            'completion_rate': round(completion_rate, 2),
            'period_start': start_date,
            'period_end': end_date
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def calculate_data_extraction_accuracy(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate data extraction accuracy metrics"""
        cache_key = f"extraction_accuracy_{start_date.date()}_{end_date.date()}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get debriefing sessions in the period
        sessions = DebriefingSession.objects.filter(
            completed_at__gte=start_date,
            completed_at__lte=end_date,
            status='completed'
        )
        
        total_sessions = sessions.count()
        
        if total_sessions == 0:
            return {
                'total_sessions': 0,
                'average_confidence': 0,
                'high_confidence_rate': 0,
                'extraction_accuracy': 0
            }
        
        # Calculate confidence scores
        confidence_scores = []
        high_confidence_count = 0
        
        for session in sessions:
            if session.confidence_scores:
                avg_confidence = sum(session.confidence_scores.values()) / len(session.confidence_scores)
                confidence_scores.append(avg_confidence)
                if avg_confidence >= 0.8:  # High confidence threshold
                    high_confidence_count += 1
        
        average_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        high_confidence_rate = (high_confidence_count / total_sessions * 100) if total_sessions > 0 else 0
        
        result = {
            'total_sessions': total_sessions,
            'average_confidence': round(average_confidence, 3),
            'high_confidence_rate': round(high_confidence_rate, 2),
            'extraction_accuracy': round(average_confidence * 100, 2)
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def calculate_meeting_detection_accuracy(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate meeting detection accuracy"""
        cache_key = f"meeting_detection_{start_date.date()}_{end_date.date()}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        meetings = Meeting.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        total_meetings = meetings.count()
        sales_meetings = meetings.filter(is_sales_meeting=True).count()
        high_confidence_meetings = meetings.filter(confidence_score__gte=0.8).count()
        
        detection_accuracy = (high_confidence_meetings / total_meetings * 100) if total_meetings > 0 else 0
        sales_meeting_rate = (sales_meetings / total_meetings * 100) if total_meetings > 0 else 0
        
        result = {
            'total_meetings': total_meetings,
            'sales_meetings': sales_meetings,
            'high_confidence_meetings': high_confidence_meetings,
            'detection_accuracy': round(detection_accuracy, 2),
            'sales_meeting_rate': round(sales_meeting_rate, 2)
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def calculate_participant_matching_accuracy(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate participant matching accuracy"""
        cache_key = f"participant_matching_{start_date.date()}_{end_date.date()}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        participants = MeetingParticipant.objects.filter(
            meeting__start_time__gte=start_date,
            meeting__start_time__lte=end_date,
            is_external=True
        )
        
        total_participants = participants.count()
        matched_participants = participants.filter(matched_lead__isnull=False).count()
        high_confidence_matches = participants.filter(match_confidence__gte=0.8).count()
        
        matching_rate = (matched_participants / total_participants * 100) if total_participants > 0 else 0
        accuracy_rate = (high_confidence_matches / total_participants * 100) if total_participants > 0 else 0
        
        result = {
            'total_participants': total_participants,
            'matched_participants': matched_participants,
            'high_confidence_matches': high_confidence_matches,
            'matching_rate': round(matching_rate, 2),
            'accuracy_rate': round(accuracy_rate, 2)
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def calculate_crm_sync_success_rate(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate CRM synchronization success rates"""
        cache_key = f"crm_sync_{start_date.date()}_{end_date.date()}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        sync_logs = SyncLog.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        total_syncs = sync_logs.count()
        successful_syncs = sync_logs.filter(status='success').count()
        failed_syncs = sync_logs.filter(status='failed').count()
        
        success_rate = (successful_syncs / total_syncs * 100) if total_syncs > 0 else 0
        
        result = {
            'total_syncs': total_syncs,
            'successful_syncs': successful_syncs,
            'failed_syncs': failed_syncs,
            'success_rate': round(success_rate, 2)
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def calculate_user_engagement_metrics(self, start_date: datetime, end_date: datetime, 
                                        user: Optional[User] = None) -> Dict[str, Any]:
        """Calculate user engagement metrics"""
        cache_key = f"user_engagement_{start_date.date()}_{end_date.date()}_{user.id if user else 'all'}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        engagement_query = UserEngagementMetric.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        if user:
            engagement_query = engagement_query.filter(user=user)
        
        # Count different engagement types
        engagement_counts = engagement_query.values('engagement_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        total_engagements = engagement_query.count()
        unique_users = engagement_query.values('user').distinct().count()
        
        # Calculate average session duration for applicable engagement types
        session_durations = engagement_query.filter(
            duration_seconds__isnull=False
        ).aggregate(avg_duration=Avg('duration_seconds'))
        
        result = {
            'total_engagements': total_engagements,
            'unique_users': unique_users,
            'engagement_breakdown': list(engagement_counts),
            'average_session_duration': session_durations['avg_duration'] or 0
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def get_competitive_intelligence_insights(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get competitive intelligence insights"""
        from apps.meetings.models import CompetitiveIntelligence
        
        cache_key = f"competitive_intel_{start_date.date()}_{end_date.date()}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        competitive_data = CompetitiveIntelligence.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Top competitors mentioned
        top_competitors = competitive_data.values('competitor_name').annotate(
            mention_count=Count('id'),
            threat_level_avg=Avg('threat_level')
        ).order_by('-mention_count')[:10]
        
        # Threat level distribution
        threat_distribution = competitive_data.values('threat_level').annotate(
            count=Count('id')
        ).order_by('threat_level')
        
        result = {
            'total_competitive_mentions': competitive_data.count(),
            'top_competitors': list(top_competitors),
            'threat_distribution': list(threat_distribution),
            'unique_competitors': competitive_data.values('competitor_name').distinct().count()
        }
        
        cache.set(cache_key, result, self.cache_timeout)
        return result
    
    def store_performance_metric(self, metric_type: str, value: float, 
                               aggregation_period: str, period_start: datetime,
                               period_end: datetime, user: Optional[User] = None,
                               metadata: Optional[Dict] = None) -> PerformanceMetric:
        """Store a performance metric"""
        metric, created = PerformanceMetric.objects.get_or_create(
            metric_type=metric_type,
            aggregation_period=aggregation_period,
            period_start=period_start,
            user=user,
            defaults={
                'metric_name': metric_type.replace('_', ' ').title(),
                'period_end': period_end,
                'value': value,
                'count': 1,
                'metadata': metadata or {}
            }
        )
        
        if not created:
            # Update existing metric
            metric.value = value
            metric.period_end = period_end
            metric.metadata.update(metadata or {})
            metric.save()
        
        return metric


class ReportingService:
    """Service for generating automated reports"""
    
    def __init__(self):
        self.analytics_service = AnalyticsService()
    
    def generate_daily_summary_report(self, date: datetime, user: Optional[User] = None) -> Report:
        """Generate daily summary report"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        report = Report.objects.create(
            report_type='daily_summary',
            title=f"Daily Summary Report - {date.strftime('%Y-%m-%d')}",
            period_start=start_date,
            period_end=end_date,
            created_by=user or User.objects.filter(is_superuser=True).first(),
            status='generating'
        )
        
        try:
            # Gather analytics data
            debriefing_data = self.analytics_service.calculate_debriefing_completion_rate(
                start_date, end_date, user
            )
            extraction_data = self.analytics_service.calculate_data_extraction_accuracy(
                start_date, end_date
            )
            meeting_data = self.analytics_service.calculate_meeting_detection_accuracy(
                start_date, end_date
            )
            engagement_data = self.analytics_service.calculate_user_engagement_metrics(
                start_date, end_date, user
            )
            
            report_data = {
                'debriefing_metrics': debriefing_data,
                'extraction_metrics': extraction_data,
                'meeting_metrics': meeting_data,
                'engagement_metrics': engagement_data,
                'generated_at': timezone.now().isoformat()
            }
            
            summary = f"""
            Daily Summary for {date.strftime('%Y-%m-%d')}:
            - Meetings: {meeting_data['total_meetings']} total, {meeting_data['sales_meetings']} sales meetings
            - Debriefing completion rate: {debriefing_data['completion_rate']}%
            - Data extraction accuracy: {extraction_data['extraction_accuracy']}%
            - User engagements: {engagement_data['total_engagements']}
            """
            
            report.mark_completed(report_data, summary.strip())
            
        except Exception as e:
            logger.error(f"Failed to generate daily summary report: {str(e)}")
            report.mark_failed(str(e))
        
        return report
    
    def generate_weekly_performance_report(self, start_date: datetime, user: Optional[User] = None) -> Report:
        """Generate weekly performance report"""
        end_date = start_date + timedelta(days=7)
        
        report = Report.objects.create(
            report_type='weekly_performance',
            title=f"Weekly Performance Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            period_start=start_date,
            period_end=end_date,
            created_by=user or User.objects.filter(is_superuser=True).first(),
            status='generating'
        )
        
        try:
            # Comprehensive weekly analytics
            debriefing_data = self.analytics_service.calculate_debriefing_completion_rate(
                start_date, end_date, user
            )
            extraction_data = self.analytics_service.calculate_data_extraction_accuracy(
                start_date, end_date
            )
            meeting_data = self.analytics_service.calculate_meeting_detection_accuracy(
                start_date, end_date
            )
            participant_data = self.analytics_service.calculate_participant_matching_accuracy(
                start_date, end_date
            )
            crm_data = self.analytics_service.calculate_crm_sync_success_rate(
                start_date, end_date
            )
            engagement_data = self.analytics_service.calculate_user_engagement_metrics(
                start_date, end_date, user
            )
            competitive_data = self.analytics_service.get_competitive_intelligence_insights(
                start_date, end_date
            )
            
            report_data = {
                'debriefing_metrics': debriefing_data,
                'extraction_metrics': extraction_data,
                'meeting_metrics': meeting_data,
                'participant_metrics': participant_data,
                'crm_metrics': crm_data,
                'engagement_metrics': engagement_data,
                'competitive_metrics': competitive_data,
                'generated_at': timezone.now().isoformat()
            }
            
            summary = f"""
            Weekly Performance Summary:
            - Total meetings: {meeting_data['total_meetings']}
            - Debriefing completion: {debriefing_data['completion_rate']}%
            - Data extraction accuracy: {extraction_data['extraction_accuracy']}%
            - Participant matching: {participant_data['matching_rate']}%
            - CRM sync success: {crm_data['success_rate']}%
            - Competitive mentions: {competitive_data['total_competitive_mentions']}
            """
            
            report.mark_completed(report_data, summary.strip())
            
        except Exception as e:
            logger.error(f"Failed to generate weekly performance report: {str(e)}")
            report.mark_failed(str(e))
        
        return report
    
    def generate_user_activity_report(self, start_date: datetime, end_date: datetime, 
                                    target_user: User) -> Report:
        """Generate user activity report"""
        report = Report.objects.create(
            report_type='user_activity',
            title=f"User Activity Report - {target_user.username}",
            period_start=start_date,
            period_end=end_date,
            created_by=target_user,
            status='generating'
        )
        
        try:
            # User-specific analytics
            engagement_data = self.analytics_service.calculate_user_engagement_metrics(
                start_date, end_date, target_user
            )
            debriefing_data = self.analytics_service.calculate_debriefing_completion_rate(
                start_date, end_date, target_user
            )
            
            # User's meetings
            user_meetings = Meeting.objects.filter(
                organizer=target_user,
                start_time__gte=start_date,
                start_time__lte=end_date
            )
            
            meeting_stats = {
                'total_meetings': user_meetings.count(),
                'sales_meetings': user_meetings.filter(is_sales_meeting=True).count(),
                'completed_debriefings': user_meetings.filter(debriefing_completed=True).count()
            }
            
            report_data = {
                'user_info': {
                    'username': target_user.username,
                    'email': target_user.email,
                    'first_name': target_user.first_name,
                    'last_name': target_user.last_name
                },
                'engagement_metrics': engagement_data,
                'debriefing_metrics': debriefing_data,
                'meeting_stats': meeting_stats,
                'generated_at': timezone.now().isoformat()
            }
            
            summary = f"""
            User Activity Summary for {target_user.username}:
            - Total engagements: {engagement_data['total_engagements']}
            - Meetings organized: {meeting_stats['total_meetings']}
            - Debriefing completion rate: {debriefing_data['completion_rate']}%
            """
            
            report.mark_completed(report_data, summary.strip())
            
        except Exception as e:
            logger.error(f"Failed to generate user activity report: {str(e)}")
            report.mark_failed(str(e))
        
        return report


class RealTimeAnalyticsCollector:
    """Service for real-time analytics data collection"""
    
    @staticmethod
    def track_user_engagement(user: User, engagement_type: str, 
                            session_id: Optional[str] = None,
                            duration_seconds: Optional[int] = None,
                            entity_type: Optional[str] = None,
                            entity_id: Optional[str] = None,
                            metadata: Optional[Dict] = None):
        """Track user engagement event"""
        try:
            UserEngagementMetric.objects.create(
                user=user,
                engagement_type=engagement_type,
                session_id=session_id,
                duration_seconds=duration_seconds,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Failed to track user engagement: {str(e)}")
    
    @staticmethod
    def track_data_quality(entity_type: str, entity_id: str, 
                          quality_type: str, score: float,
                          field_name: Optional[str] = None,
                          confidence: Optional[float] = None,
                          user: Optional[User] = None,
                          details: Optional[Dict] = None):
        """Track data quality metric"""
        try:
            DataQualityMetric.objects.create(
                quality_type=quality_type,
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                score=score,
                confidence=confidence,
                user=user,
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to track data quality: {str(e)}")
    
    @staticmethod
    def track_system_health(health_type: str, component: str, 
                          value: float, unit: Optional[str] = None,
                          warning_threshold: Optional[float] = None,
                          critical_threshold: Optional[float] = None,
                          details: Optional[Dict] = None):
        """Track system health metric"""
        try:
            metric = SystemHealthMetric.objects.create(
                health_type=health_type,
                component=component,
                value=value,
                unit=unit,
                warning_threshold=warning_threshold,
                critical_threshold=critical_threshold,
                details=details or {}
            )
            metric.update_status()
            return metric
        except Exception as e:
            logger.error(f"Failed to track system health: {str(e)}")
            return None