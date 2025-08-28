"""
Debriefing API views for conversation interface and management
"""
import logging
from typing import Dict, Any
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action

from .models import DebriefingSession, DebriefingQuestion, DebriefingInsight, DebriefingTemplate
from .serializers import (
    DebriefingSessionSerializer, DebriefingQuestionSerializer, 
    DebriefingInsightSerializer, DebriefingTemplateSerializer
)
from .conversation_flow import ConversationFlowManager, ConversationRecoveryManager
from .session_manager import DebriefingSessionManager
from .analytics import DebriefingAnalytics, DebriefingExporter
from apps.accounts.permissions import DebriefingAccessPermission

logger = logging.getLogger(__name__)


class DebriefingSessionViewSet(ModelViewSet):
    """
    ViewSet for managing debriefing sessions
    """
    serializer_class = DebriefingSessionSerializer
    permission_classes = [permissions.IsAuthenticated, DebriefingAccessPermission]
    
    def get_queryset(self):
        """Filter sessions by user permissions"""
        user = self.request.user
        if user.has_perm('debriefings.view_all_sessions') or user.is_staff:
            return DebriefingSession.objects.all()
        return DebriefingSession.objects.filter(user=user)
    
    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        """Start a debriefing session"""
        try:
            session = self.get_object()
            
            # Start session synchronously for now
            session.status = 'in_progress'
            session.started_at = timezone.now()
            session.save()
            
            return Response({
                'status': 'started',
                'session_id': str(session.id),
                'websocket_url': f'/ws/debriefing/{session.id}/',
                'message': 'Session started. Connect to WebSocket to begin conversation.'
            })
                
        except Exception as e:
            logger.error(f"Error starting session {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def complete_session(self, request, pk=None):
        """Complete a debriefing session"""
        try:
            session = self.get_object()
            completion_data = request.data.get('completion_data', {})
            
            # Complete session synchronously
            session.status = 'completed'
            session.completed_at = timezone.now()
            session.save()
            
            # Update meeting status
            session.meeting.debriefing_completed = True
            session.meeting.save()
            
            return Response({
                'status': 'completed',
                'session_id': str(session.id),
                'completion_data': completion_data
            })
                
        except Exception as e:
            logger.error(f"Error completing session {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def recovery_info(self, request, pk=None):
        """Get session recovery information"""
        try:
            session = self.get_object()
            
            # Simple recovery check
            answered_count = session.questions.filter(user_response__isnull=False).count()
            total_questions = session.questions.count()
            can_recover = answered_count > 0 and session.status in ['expired', 'in_progress']
            
            recovery_state = {
                'can_recover': can_recover,
                'answered_questions': answered_count,
                'total_questions': total_questions,
                'progress_percentage': (answered_count / total_questions * 100) if total_questions > 0 else 0
            }
            
            return Response({
                'can_recover': can_recover,
                'recovery_state': recovery_state
            })
            
        except Exception as e:
            logger.error(f"Error getting recovery info for session {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def recover_session(self, request, pk=None):
        """Recover a timed-out session"""
        try:
            session = self.get_object()
            
            # Simple recovery - set status back to in_progress
            if session.status == 'expired':
                session.status = 'in_progress'
                session.save()
                
                # Get next unanswered question
                next_question = session.questions.filter(
                    user_response__isnull=True
                ).order_by('question_order').first()
                
                return Response({
                    'status': 'recovered',
                    'session_id': str(session.id),
                    'next_question': {
                        'question_id': str(next_question.id),
                        'question_text': next_question.question_text,
                        'question_type': next_question.question_type,
                        'question_order': next_question.question_order
                    } if next_question else None,
                    'websocket_url': f'/ws/debriefing/{session.id}/'
                })
            else:
                return Response(
                    {'error': 'Session cannot be recovered'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error recovering session {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get session analytics"""
        try:
            session = self.get_object()
            
            # Simple analytics
            analytics = {
                'session_id': str(session.id),
                'status': session.status,
                'duration_minutes': session.duration_minutes,
                'progress': {
                    'answered_questions': session.questions.filter(user_response__isnull=False).count(),
                    'total_questions': session.questions.count(),
                },
                'insights_generated': session.insights.count(),
            }
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting analytics for session {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def export_data(self, request, pk=None):
        """Export session data"""
        try:
            session = self.get_object()
            
            # Simple export
            export_data = {
                'session_info': {
                    'session_id': str(session.id),
                    'meeting_title': session.meeting.title,
                    'status': session.status,
                    'started_at': session.started_at.isoformat() if session.started_at else None,
                    'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                },
                'questions_and_responses': [
                    {
                        'question': q.question_text,
                        'response': q.user_response,
                        'question_type': q.question_type
                    }
                    for q in session.questions.all().order_by('question_order')
                ],
                'extracted_data': session.extracted_data or {},
                'export_timestamp': timezone.now().isoformat()
            }
            
            return Response(export_data)
            
        except Exception as e:
            logger.error(f"Error exporting session data {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DebriefingQuestionViewSet(ModelViewSet):
    """
    ViewSet for managing debriefing questions
    """
    serializer_class = DebriefingQuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter questions by session access"""
        user = self.request.user
        if user.has_perm('debriefings.view_all_sessions') or user.is_staff:
            return DebriefingQuestion.objects.all()
        return DebriefingQuestion.objects.filter(session__user=user)
    
    @action(detail=True, methods=['post'])
    def submit_response(self, request, pk=None):
        """Submit response to a question"""
        try:
            question = self.get_object()
            response_text = request.data.get('response', '').strip()
            
            if not response_text:
                return Response(
                    {'error': 'Response text is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Record response
            question.record_response(response_text)
            
            # Simple processing result
            processing_result = {
                'status': 'processed',
                'confidence_score': 0.8
            }
            
            return Response({
                'status': 'response_recorded',
                'question_id': str(question.id),
                'processing_result': processing_result
            })
            
        except Exception as e:
            logger.error(f"Error submitting response for question {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DebriefingInsightViewSet(ModelViewSet):
    """
    ViewSet for managing debriefing insights
    """
    serializer_class = DebriefingInsightSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter insights by session access"""
        user = self.request.user
        if user.has_perm('debriefings.view_all_sessions') or user.is_staff:
            return DebriefingInsight.objects.all()
        return DebriefingInsight.objects.filter(session__user=user)
    
    @action(detail=True, methods=['post'])
    def validate_insight(self, request, pk=None):
        """Validate or reject an insight"""
        try:
            insight = self.get_object()
            is_valid = request.data.get('is_valid', True)
            feedback = request.data.get('feedback', '')
            
            insight.user_validated = is_valid
            insight.user_feedback = feedback
            insight.save()
            
            return Response({
                'status': 'insight_validated',
                'insight_id': str(insight.id),
                'validated': is_valid
            })
            
        except Exception as e:
            logger.error(f"Error validating insight {pk}: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DebriefingTemplateViewSet(ModelViewSet):
    """
    ViewSet for managing debriefing templates
    """
    serializer_class = DebriefingTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get templates accessible to user"""
        return DebriefingTemplate.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        """Set creator when creating template"""
        serializer.save(created_by=self.request.user)


class DebriefingAnalyticsView(APIView):
    """
    API view for debriefing analytics
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self):
        super().__init__()
        self.analytics = DebriefingAnalytics()
    
    def get(self, request):
        """Get debriefing analytics"""
        try:
            period_days = int(request.query_params.get('period_days', 30))
            user_id = request.query_params.get('user_id')
            team_ids = request.query_params.getlist('team_ids')
            
            # Convert team_ids to integers
            if team_ids:
                team_ids = [int(tid) for tid in team_ids]
            
            # Get user if specified
            user = None
            if user_id:
                from django.contrib.auth.models import User
                user = get_object_or_404(User, id=user_id)
                
                # Check permissions
                if user != request.user and not request.user.has_perm('debriefings.view_all_analytics'):
                    return Response(
                        {'error': 'Permission denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            # Get analytics
            if user:
                analytics = self.analytics.get_user_performance_metrics(user, period_days)
            else:
                analytics = self.analytics.get_completion_metrics(
                    user=request.user if not request.user.has_perm('debriefings.view_all_analytics') else None,
                    period_days=period_days,
                    team_ids=team_ids
                )
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SystemAnalyticsView(APIView):
    """
    API view for system-wide analytics
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self):
        super().__init__()
        self.analytics = DebriefingAnalytics()
    
    def get(self, request):
        """Get system-wide analytics"""
        try:
            # Check permissions
            if not request.user.has_perm('debriefings.view_system_analytics') and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            period_days = int(request.query_params.get('period_days', 30))
            
            analytics = self.analytics.get_system_wide_analytics(period_days)
            
            return Response(analytics)
            
        except Exception as e:
            logger.error(f"Error getting system analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DebriefingExportView(APIView):
    """
    API view for exporting debriefing data
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self):
        super().__init__()
        self.exporter = DebriefingExporter()
    
    def get(self, request):
        """Export debriefing data"""
        try:
            export_type = request.query_params.get('type', 'session')
            
            if export_type == 'session':
                session_id = request.query_params.get('session_id')
                if not session_id:
                    return Response(
                        {'error': 'session_id is required for session export'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                session = get_object_or_404(DebriefingSession, id=session_id)
                
                # Check permissions
                if session.user != request.user and not request.user.has_perm('debriefings.view_all_sessions'):
                    return Response(
                        {'error': 'Permission denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                export_data = self.exporter.export_session_summary(session)
                
            elif export_type == 'user':
                user_id = request.query_params.get('user_id')
                period_days = int(request.query_params.get('period_days', 30))
                
                if user_id:
                    from django.contrib.auth.models import User
                    user = get_object_or_404(User, id=user_id)
                    
                    # Check permissions
                    if user != request.user and not request.user.has_perm('debriefings.view_all_analytics'):
                        return Response(
                            {'error': 'Permission denied'},
                            status=status.HTTP_403_FORBIDDEN
                        )
                else:
                    user = request.user
                
                export_data = self.exporter.export_user_report(user, period_days)
                
            elif export_type == 'system':
                # Check permissions
                if not request.user.has_perm('debriefings.view_system_analytics') and not request.user.is_staff:
                    return Response(
                        {'error': 'Permission denied'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                period_days = int(request.query_params.get('period_days', 30))
                export_data = self.exporter.export_system_report(period_days)
                
            else:
                return Response(
                    {'error': 'Invalid export type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(export_data)
            
        except Exception as e:
            logger.error(f"Error exporting data: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def check_session_timeout(request):
    """Check if a session has timed out"""
    try:
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session = get_object_or_404(DebriefingSession, id=session_id)
        
        # Check permissions
        if session.user != request.user and not request.user.has_perm('debriefings.view_all_sessions'):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Simple timeout check
        timeout_info = {
            'timed_out': session.status == 'expired',
            'session_status': session.status
        }
        
        return Response(timeout_info)
        
    except Exception as e:
        logger.error(f"Error checking session timeout: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_active_sessions(request):
    """Get active debriefing sessions for user"""
    try:
        user = request.user
        
        active_sessions = DebriefingSession.objects.filter(
            user=user,
            status__in=['scheduled', 'in_progress']
        ).select_related('meeting').order_by('-scheduled_time')
        
        sessions_data = []
        for session in active_sessions:
            sessions_data.append({
                'session_id': str(session.id),
                'meeting_title': session.meeting.title,
                'meeting_date': session.meeting.start_time.isoformat(),
                'status': session.status,
                'scheduled_time': session.scheduled_time.isoformat(),
                'is_overdue': session.is_overdue,
                'websocket_url': f'/ws/debriefing/{session.id}/'
            })
        
        return Response({
            'active_sessions': sessions_data,
            'count': len(sessions_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )