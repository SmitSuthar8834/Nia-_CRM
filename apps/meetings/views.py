"""
API Views for Meeting Intelligence
"""
import logging
from datetime import datetime, timedelta
from django.db.models import Q, Count, Avg, Case, When, IntegerField, F, DurationField
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import Meeting, MeetingParticipant, MeetingNote
from .serializers import (
    MeetingSerializer, MeetingListSerializer, MeetingParticipantSerializer,
    MeetingNoteSerializer, MeetingStatsSerializer, MeetingIntelligenceSerializer,
    MeetingSearchSerializer
)

logger = logging.getLogger(__name__)


class MeetingPagination(PageNumberPagination):
    """Custom pagination for meetings"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        tags=['Meetings'],
        summary='List Meetings',
        description='Retrieve a paginated list of meetings with optional filtering and search.',
        parameters=[
            OpenApiParameter(
                name='meeting_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by meeting type (discovery, demo, negotiation, follow_up, internal, competitive, closing)',
                enum=['discovery', 'demo', 'negotiation', 'follow_up', 'internal', 'competitive', 'closing']
            ),
            OpenApiParameter(
                name='is_sales_meeting',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by sales meeting status'
            ),
            OpenApiParameter(
                name='start_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter meetings from this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='end_date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Filter meetings until this date (YYYY-MM-DD)'
            ),
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search in meeting title, description, and participant names'
            ),
            OpenApiParameter(
                name='organizer',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Filter by organizer user ID'
            ),
            OpenApiParameter(
                name='debriefing_completed',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by debriefing completion status'
            )
        ],
        responses={
            200: MeetingListSerializer(many=True),
            401: {'description': 'Authentication required'}
        }
    ),
    create=extend_schema(
        tags=['Meetings'],
        summary='Create Meeting',
        description='Create a new meeting record with automatic intelligence detection.',
        request=MeetingSerializer,
        responses={
            201: MeetingSerializer,
            400: {'description': 'Validation error'},
            401: {'description': 'Authentication required'}
        }
    ),
    retrieve=extend_schema(
        tags=['Meetings'],
        summary='Get Meeting Details',
        description='Retrieve detailed information about a specific meeting.',
        responses={
            200: MeetingSerializer,
            401: {'description': 'Authentication required'},
            404: {'description': 'Meeting not found'}
        }
    ),
    update=extend_schema(
        tags=['Meetings'],
        summary='Update Meeting',
        description='Update meeting information and trigger intelligence re-analysis.',
        request=MeetingSerializer,
        responses={
            200: MeetingSerializer,
            400: {'description': 'Validation error'},
            401: {'description': 'Authentication required'},
            404: {'description': 'Meeting not found'}
        }
    ),
    partial_update=extend_schema(
        tags=['Meetings'],
        summary='Partially Update Meeting',
        description='Partially update meeting information.',
        request=MeetingSerializer,
        responses={
            200: MeetingSerializer,
            400: {'description': 'Validation error'},
            401: {'description': 'Authentication required'},
            404: {'description': 'Meeting not found'}
        }
    ),
    destroy=extend_schema(
        tags=['Meetings'],
        summary='Delete Meeting',
        description='Delete a meeting record and all associated data.',
        responses={
            204: {'description': 'Meeting deleted successfully'},
            401: {'description': 'Authentication required'},
            404: {'description': 'Meeting not found'}
        }
    )
)
class MeetingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Meeting management with intelligence features
    """
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MeetingPagination
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return MeetingListSerializer
        return MeetingSerializer
    
    def get_queryset(self):
        """Filter meetings based on user permissions and query parameters"""
        queryset = Meeting.objects.select_related('organizer').prefetch_related(
            'participants', 'notes'
        )
        
        # Filter by user permissions - users can see their own meetings
        # Sales managers can see team meetings, admins can see all
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(organizer=user)
        
        # Apply search filters directly from query parameters
        query_params = self.request.query_params
        
        # Text search
        if 'search' in query_params and query_params['search']:
            search_term = query_params['search']
            queryset = queryset.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(participants__name__icontains=search_term) |
                Q(participants__email__icontains=search_term) |
                Q(participants__company__icontains=search_term)
            ).distinct()
        
        # Meeting type filter
        if 'meeting_type' in query_params and query_params['meeting_type']:
            queryset = queryset.filter(meeting_type=query_params['meeting_type'])
        
        # Status filter
        if 'status' in query_params and query_params['status']:
            queryset = queryset.filter(status=query_params['status'])
        
        # Sales meeting filter
        if 'is_sales_meeting' in query_params:
            is_sales = query_params['is_sales_meeting'].lower() == 'true'
            queryset = queryset.filter(is_sales_meeting=is_sales)
        
        # Date range filter
        if 'start_date' in query_params and query_params['start_date']:
            from django.utils.dateparse import parse_datetime
            start_date = parse_datetime(query_params['start_date'])
            if start_date:
                queryset = queryset.filter(start_time__gte=start_date)
        
        if 'end_date' in query_params and query_params['end_date']:
            from django.utils.dateparse import parse_datetime
            end_date = parse_datetime(query_params['end_date'])
            if end_date:
                queryset = queryset.filter(end_time__lte=end_date)
        
        # Organizer filter
        if 'organizer' in query_params and query_params['organizer']:
            try:
                organizer_id = int(query_params['organizer'])
                queryset = queryset.filter(organizer_id=organizer_id)
            except (ValueError, TypeError):
                pass
        
        # Debriefing filter
        if 'has_debriefing' in query_params:
            has_debriefing = query_params['has_debriefing'].lower() == 'true'
            if has_debriefing:
                queryset = queryset.filter(debriefing_completed=True)
            else:
                queryset = queryset.filter(debriefing_completed=False)
        
        # Participant email filter
        if 'participant_email' in query_params and query_params['participant_email']:
            queryset = queryset.filter(
                participants__email__icontains=query_params['participant_email']
            )
        
        # Company filter
        if 'company' in query_params and query_params['company']:
            queryset = queryset.filter(
                participants__company__icontains=query_params['company']
            )
        
        return queryset.order_by('-start_time')
    
    def perform_create(self, serializer):
        """Set the organizer to the current user"""
        serializer.save(organizer=self.request.user)
    
    @action(detail=True, methods=['post'])
    def schedule_debriefing(self, request, pk=None):
        """Schedule a debriefing session for the meeting"""
        meeting = self.get_object()
        
        if not meeting.is_sales_meeting:
            return Response(
                {'error': 'Debriefing can only be scheduled for sales meetings'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if meeting.debriefing_scheduled:
            return Response(
                {'error': 'Debriefing already scheduled for this meeting'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        meeting.schedule_debriefing()
        
        return Response({
            'message': 'Debriefing scheduled successfully',
            'debriefing_due_at': meeting.debriefing_due_at
        })
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming meetings"""
        now = timezone.now()
        upcoming_meetings = self.get_queryset().filter(
            start_time__gte=now,
            status='scheduled'
        )[:10]
        
        serializer = MeetingListSerializer(upcoming_meetings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent completed meetings"""
        recent_meetings = self.get_queryset().filter(
            status='completed'
        )[:10]
        
        serializer = MeetingListSerializer(recent_meetings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def sales_meetings(self, request):
        """Get sales meetings only"""
        sales_meetings = self.get_queryset().filter(is_sales_meeting=True)
        
        page = self.paginate_queryset(sales_meetings)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(sales_meetings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_debriefings(self, request):
        """Get meetings with pending debriefings"""
        pending = self.get_queryset().filter(
            is_sales_meeting=True,
            debriefing_scheduled=True,
            debriefing_completed=False
        )
        
        serializer = MeetingListSerializer(pending, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get meeting statistics"""
        queryset = self.get_queryset()
        now = timezone.now()
        
        # Basic counts
        total_meetings = queryset.count()
        sales_meetings = queryset.filter(is_sales_meeting=True).count()
        completed_meetings = queryset.filter(status='completed').count()
        upcoming_meetings = queryset.filter(
            start_time__gte=now, status='scheduled'
        ).count()
        
        # Debriefing stats
        debriefings_pending = queryset.filter(
            is_sales_meeting=True,
            debriefing_scheduled=True,
            debriefing_completed=False
        ).count()
        debriefings_completed = queryset.filter(
            debriefing_completed=True
        ).count()
        
        # Average duration
        avg_duration = queryset.aggregate(
            avg_duration=Avg(
                Case(
                    When(end_time__isnull=False, start_time__isnull=False,
                         then=F('end_time') - F('start_time')),
                    output_field=DurationField()
                )
            )
        )['avg_duration']
        
        if avg_duration:
            avg_duration = avg_duration.total_seconds() / 60  # Convert to minutes
        else:
            avg_duration = 0
        
        # Meeting types distribution
        meeting_types = dict(
            queryset.values('meeting_type').annotate(
                count=Count('meeting_type')
            ).values_list('meeting_type', 'count')
        )
        
        # Monthly trend (last 6 months)
        monthly_trend = []
        for i in range(6):
            month_start = now.replace(day=1) - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=31)
            month_count = queryset.filter(
                start_time__gte=month_start,
                start_time__lt=month_end
            ).count()
            monthly_trend.append({
                'month': month_start.strftime('%Y-%m'),
                'count': month_count
            })
        
        stats_data = {
            'total_meetings': total_meetings,
            'sales_meetings': sales_meetings,
            'completed_meetings': completed_meetings,
            'upcoming_meetings': upcoming_meetings,
            'debriefings_pending': debriefings_pending,
            'debriefings_completed': debriefings_completed,
            'average_duration': avg_duration,
            'meeting_types': meeting_types,
            'monthly_trend': monthly_trend
        }
        
        serializer = MeetingStatsSerializer(stats_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def detect_intelligence(self, request, pk=None):
        """Run meeting intelligence detection on a specific meeting"""
        meeting = self.get_object()
        
        # This would typically call the AI engine service
        # For now, we'll return mock intelligence data
        intelligence_data = {
            'meeting_id': meeting.id,
            'is_sales_meeting': meeting.is_sales_meeting,
            'confidence_score': meeting.confidence_score,
            'meeting_type': meeting.meeting_type,
            'detected_participants': [
                {
                    'email': p.email,
                    'name': p.name,
                    'company': p.company,
                    'is_external': p.is_external
                }
                for p in meeting.participants.all()
            ],
            'matched_leads': [
                {
                    'participant_email': p.email,
                    'lead_id': p.matched_lead.id if p.matched_lead else None,
                    'match_confidence': p.match_confidence
                }
                for p in meeting.participants.all()
            ],
            'intelligence_summary': {
                'external_participants': meeting.participants.filter(is_external=True).count(),
                'matched_leads': meeting.participants.filter(matched_lead__isnull=False).count(),
                'high_confidence_matches': meeting.participants.filter(match_confidence__gte=0.8).count()
            }
        }
        
        serializer = MeetingIntelligenceSerializer(intelligence_data)
        return Response(serializer.data)


class MeetingParticipantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Meeting Participants
    """
    queryset = MeetingParticipant.objects.all()
    serializer_class = MeetingParticipantSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter participants based on meeting access"""
        queryset = MeetingParticipant.objects.select_related(
            'meeting', 'matched_lead'
        )
        
        # Filter by meeting if provided
        meeting_id = self.request.query_params.get('meeting', None)
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        
        # Filter by external participants only
        external_only = self.request.query_params.get('external_only', None)
        if external_only and external_only.lower() == 'true':
            queryset = queryset.filter(is_external=True)
        
        # Filter by match confidence
        min_confidence = self.request.query_params.get('min_confidence', None)
        if min_confidence:
            try:
                confidence = float(min_confidence)
                queryset = queryset.filter(match_confidence__gte=confidence)
            except ValueError:
                pass
        
        return queryset.order_by('-match_confidence', 'name')
    
    @action(detail=True, methods=['post'])
    def verify_match(self, request, pk=None):
        """Manually verify a participant-lead match"""
        participant = self.get_object()
        
        verified = request.data.get('verified', False)
        lead_id = request.data.get('lead_id', None)
        
        if verified and lead_id:
            from apps.leads.models import Lead
            try:
                lead = Lead.objects.get(id=lead_id)
                participant.matched_lead = lead
                participant.match_confidence = 1.0
                participant.match_method = 'manual_verification'
                participant.manual_verification_required = False
                participant.save()
                
                return Response({
                    'message': 'Match verified successfully',
                    'participant': MeetingParticipantSerializer(participant).data
                })
            except Lead.DoesNotExist:
                return Response(
                    {'error': 'Lead not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            participant.matched_lead = None
            participant.match_confidence = 0.0
            participant.manual_verification_required = False
            participant.save()
            
            return Response({
                'message': 'Match rejected successfully',
                'participant': MeetingParticipantSerializer(participant).data
            })
    
    @action(detail=False, methods=['get'])
    def unmatched(self, request):
        """Get unmatched external participants"""
        unmatched = self.get_queryset().filter(
            is_external=True,
            matched_lead__isnull=True
        )
        
        serializer = self.get_serializer(unmatched, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def verification_required(self, request):
        """Get participants requiring manual verification"""
        verification_required = self.get_queryset().filter(
            manual_verification_required=True
        )
        
        serializer = self.get_serializer(verification_required, many=True)
        return Response(serializer.data)


class MeetingNoteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Meeting Notes
    """
    queryset = MeetingNote.objects.all()
    serializer_class = MeetingNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter notes based on meeting access"""
        queryset = MeetingNote.objects.select_related('meeting', 'author')
        
        # Filter by meeting if provided
        meeting_id = self.request.query_params.get('meeting', None)
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        
        # Filter by note type
        note_type = self.request.query_params.get('note_type', None)
        if note_type:
            queryset = queryset.filter(note_type=note_type)
        
        # Filter by AI generated notes
        ai_generated = self.request.query_params.get('ai_generated', None)
        if ai_generated and ai_generated.lower() == 'true':
            queryset = queryset.filter(ai_generated=True)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set the author to the current user"""
        serializer.save(author=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_meeting(self, request):
        """Get notes for a specific meeting"""
        meeting_id = request.query_params.get('meeting_id')
        if not meeting_id:
            return Response(
                {'error': 'meeting_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notes = self.get_queryset().filter(meeting_id=meeting_id)
        serializer = self.get_serializer(notes, many=True)
        return Response(serializer.data)