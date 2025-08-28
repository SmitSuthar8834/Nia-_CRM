"""
API Views for Lead Matching and Participant Analysis
"""
import logging
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Lead, ActionItem, CompetitiveIntelligence
from .services import ParticipantAnalysisService, ParticipantMatchingService
# from .verification import ManualVerificationService, VerificationRequest
from .serializers import (
    LeadSerializer, ActionItemSerializer, CompetitiveIntelligenceSerializer,
    # VerificationRequestSerializer, 
    ParticipantMatchResultSerializer
)
from apps.meetings.models import Meeting, MeetingParticipant


logger = logging.getLogger(__name__)


class LeadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Lead management with meeting intelligence features
    """
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter leads based on user permissions and query parameters"""
        queryset = Lead.objects.all()
        
        # Filter by search query
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(company__icontains=search)
            )
        
        # Filter by company
        company = self.request.query_params.get('company', None)
        if company:
            queryset = queryset.filter(company__icontains=company)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by source
        source = self.request.query_params.get('source', None)
        if source:
            queryset = queryset.filter(source=source)
        
        return queryset.order_by('-updated_at')
    
    @action(detail=True, methods=['get'])
    def meetings(self, request, pk=None):
        """Get meetings for a specific lead"""
        lead = self.get_object()
        
        # Get meeting participants for this lead
        participants = MeetingParticipant.objects.filter(
            matched_lead=lead
        ).select_related('meeting').order_by('-meeting__start_time')
        
        meetings_data = []
        for participant in participants:
            meeting = participant.meeting
            meetings_data.append({
                'id': str(meeting.id),
                'title': meeting.title,
                'start_time': meeting.start_time,
                'end_time': meeting.end_time,
                'meeting_type': meeting.meeting_type,
                'status': meeting.status,
                'debriefing_completed': meeting.debriefing_completed,
                'participant_role': participant.participant_type,
                'match_confidence': participant.match_confidence
            })
        
        return Response(meetings_data)
    
    @action(detail=True, methods=['get'])
    def competitive_intelligence(self, request, pk=None):
        """Get competitive intelligence for a specific lead"""
        lead = self.get_object()
        competitive_intel = CompetitiveIntelligence.objects.filter(lead=lead)
        serializer = CompetitiveIntelligenceSerializer(competitive_intel, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def action_items(self, request, pk=None):
        """Get action items for a specific lead"""
        lead = self.get_object()
        action_items = ActionItem.objects.filter(lead=lead)
        serializer = ActionItemSerializer(action_items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_meeting_stats(self, request, pk=None):
        """Manually update meeting statistics for a lead"""
        lead = self.get_object()
        lead.update_meeting_stats()
        
        return Response({
            'message': 'Meeting statistics updated',
            'meeting_count': lead.meeting_count,
            'last_meeting_date': lead.last_meeting_date
        })


class ParticipantMatchingViewSet(viewsets.ViewSet):
    """
    ViewSet for participant matching operations
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def match_participants(self, request):
        """
        Match a list of participants against existing leads
        
        Expected payload:
        {
            "participants": [
                {
                    "email": "john@company.com",
                    "name": "John Doe",
                    "company": "Company Inc",
                    "title": "Manager",
                    "phone": "555-123-4567"
                }
            ],
            "use_linkedin_enhancement": true
        }
        """
        participants = request.data.get('participants', [])
        use_linkedin = request.data.get('use_linkedin_enhancement', False)
        
        if not participants:
            return Response(
                {'error': 'No participants provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            matching_service = ParticipantMatchingService()
            results = matching_service.match_participants(participants)
            
            # Enhance with LinkedIn if requested
            if use_linkedin:
                try:
                    from .linkedin_integration import SocialProfileMatcher
                    social_matcher = SocialProfileMatcher()
                    
                    enhanced_results = []
                    for result in results:
                        if result['potential_matches']:
                            enhanced_result = social_matcher.enhance_participant_matching(
                                result['participant'], result['potential_matches']
                            )
                            result['potential_matches'] = enhanced_result
                        enhanced_results.append(result)
                    results = enhanced_results
                except ImportError:
                    logger.warning("LinkedIn integration not available")
            
            serializer = ParticipantMatchResultSerializer(results, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Participant matching failed: {str(e)}")
            return Response(
                {'error': 'Participant matching failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def analyze_meeting_participants(self, request):
        """
        Analyze participants for a specific meeting
        
        Expected payload:
        {
            "meeting_id": "uuid",
            "participants": [...],
            "use_linkedin_enhancement": true
        }
        """
        meeting_id = request.data.get('meeting_id')
        participants = request.data.get('participants', [])
        use_linkedin = request.data.get('use_linkedin_enhancement', False)
        
        if not meeting_id:
            return Response(
                {'error': 'Meeting ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not participants:
            return Response(
                {'error': 'No participants provided'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify meeting exists and user has access
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            # Add permission check here if needed
        except Meeting.DoesNotExist:
            return Response(
                {'error': 'Meeting not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            analysis_service = ParticipantAnalysisService()
            results = analysis_service.analyze_meeting_participants(
                meeting_id, participants, use_linkedin
            )
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Participant analysis failed: {str(e)}")
            return Response(
                {'error': 'Participant analysis failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class VerificationViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for manual verification requests
#     """
#     queryset = VerificationRequest.objects.all()
#     serializer_class = VerificationRequestSerializer
#     permission_classes = [permissions.IsAuthenticated]
#     
#     def get_queryset(self):
        """Filter verification requests based on user and status"""
        queryset = VerificationRequest.objects.all()
        
        # Filter by assigned user
        if not self.request.user.is_staff:
            queryset = queryset.filter(assigned_to=self.request.user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by verification type
        verification_type = self.request.query_params.get('type', None)
        if verification_type:
            queryset = queryset.filter(verification_type=verification_type)
        
        return queryset.select_related(
            'meeting_participant', 'assigned_to', 'reviewed_by', 'selected_match'
        ).order_by('due_date', '-created_at')
    
    @action(detail=True, methods=['post'])
    def approve_match(self, request, pk=None):
        """
        Approve a verification request with a specific lead match
        
        Expected payload:
        {
            "lead_id": "uuid",
            "notes": "Optional reviewer notes"
        }
        """
        verification_request = self.get_object()
        lead_id = request.data.get('lead_id')
        notes = request.data.get('notes', '')
        
        if not lead_id:
            return Response(
                {'error': 'Lead ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lead = Lead.objects.get(id=lead_id)
            verification_request.approve_match(lead, request.user, notes)
            
            return Response({
                'message': 'Verification approved',
                'status': verification_request.status,
                'matched_lead': {
                    'id': str(lead.id),
                    'name': lead.full_name,
                    'email': lead.email,
                    'company': lead.company
                }
            })
            
        except Lead.DoesNotExist:
            return Response(
                {'error': 'Lead not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Verification approval failed: {str(e)}")
            return Response(
                {'error': 'Verification approval failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def approve_new_lead(self, request, pk=None):
        """
        Approve creation of a new lead
        
        Expected payload:
        {
            "notes": "Optional reviewer notes"
        }
        """
        verification_request = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            verification_request.approve_new_lead_creation(request.user, notes)
            
            return Response({
                'message': 'New lead creation approved',
                'status': verification_request.status,
                'created_lead': {
                    'id': str(verification_request.meeting_participant.matched_lead.id),
                    'name': verification_request.meeting_participant.matched_lead.full_name,
                    'email': verification_request.meeting_participant.matched_lead.email
                }
            })
            
        except Exception as e:
            logger.error(f"New lead approval failed: {str(e)}")
            return Response(
                {'error': 'New lead approval failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a verification request
        
        Expected payload:
        {
            "notes": "Reason for rejection"
        }
        """
        verification_request = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            verification_request.reject(request.user, notes)
            
            return Response({
                'message': 'Verification rejected',
                'status': verification_request.status
            })
            
        except Exception as e:
            logger.error(f"Verification rejection failed: {str(e)}")
            return Response(
                {'error': 'Verification rejection failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending verification requests for the current user"""
        verification_service = ManualVerificationService()
        pending_requests = verification_service.get_pending_verifications(request.user)
        
        serializer = self.get_serializer(pending_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue verification requests"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification_service = ManualVerificationService()
        overdue_requests = verification_service.get_overdue_verifications()
        
        serializer = self.get_serializer(overdue_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_approve_high_confidence(self, request):
        """Bulk approve high confidence verification requests"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        confidence_threshold = request.data.get('confidence_threshold', 0.8)
        
        try:
            verification_service = ManualVerificationService()
            approved_count = verification_service.bulk_approve_high_confidence_matches(
                confidence_threshold
            )
            
            return Response({
                'message': f'Bulk approved {approved_count} verification requests',
                'approved_count': approved_count
            })
            
        except Exception as e:
            logger.error(f"Bulk approval failed: {str(e)}")
            return Response(
                {'error': 'Bulk approval failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ActionItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Action Item management
    """
    queryset = ActionItem.objects.all()
    serializer_class = ActionItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter action items based on user permissions"""
        queryset = ActionItem.objects.all()
        
        # Filter by meeting
        meeting_id = self.request.query_params.get('meeting', None)
        if meeting_id:
            queryset = queryset.filter(meeting_id=meeting_id)
        
        # Filter by lead
        lead_id = self.request.query_params.get('lead', None)
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by owner
        owner = self.request.query_params.get('owner', None)
        if owner:
            queryset = queryset.filter(owner_user=owner)
        
        return queryset.select_related('meeting', 'lead', 'owner_user')
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """Mark an action item as completed"""
        action_item = self.get_object()
        notes = request.data.get('notes', '')
        
        action_item.mark_completed(notes)
        
        return Response({
            'message': 'Action item marked as completed',
            'status': action_item.status,
            'completed_at': action_item.completed_at
        })


class CompetitiveIntelligenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Competitive Intelligence management
    """
    queryset = CompetitiveIntelligence.objects.all()
    serializer_class = CompetitiveIntelligenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter competitive intelligence based on parameters"""
        queryset = CompetitiveIntelligence.objects.all()
        
        # Filter by lead
        lead_id = self.request.query_params.get('lead', None)
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)
        
        # Filter by competitor
        competitor = self.request.query_params.get('competitor', None)
        if competitor:
            queryset = queryset.filter(competitor_name__icontains=competitor)
        
        # Filter by threat level
        threat_level = self.request.query_params.get('threat_level', None)
        if threat_level:
            queryset = queryset.filter(threat_level=threat_level)
        
        return queryset.select_related('lead', 'meeting')