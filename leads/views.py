from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Lead
from .serializers import LeadSerializer, LeadSyncSerializer
from .services import LeadMatchingService


class LeadListCreateView(generics.ListCreateAPIView):
    """
    List all leads or create a new lead
    """
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter leads based on query parameters"""
        queryset = Lead.objects.all()
        status_filter = self.request.query_params.get('status')
        company_filter = self.request.query_params.get('company')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if company_filter:
            queryset = queryset.filter(company__icontains=company_filter)
        
        return queryset


class LeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a lead
    """
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]


@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def sync_leads(request):
    """
    Webhook endpoint for n8n to sync leads from Creatio CRM
    Handles data transformation from Creatio format and error handling
    """
    try:
        # Transform Creatio format to Django format if needed
        transformed_data = transform_creatio_data(request.data)
        
        serializer = LeadSyncSerializer(data=transformed_data)
        
        if serializer.is_valid():
            result = serializer.save()
            
            # Check if there were any errors during processing
            if result['errors']:
                return Response({
                    'success': False,
                    'message': f"Processed {result['total_processed']} leads with errors",
                    'created': len(result['created']),
                    'updated': len(result['updated']),
                    'errors': result['errors'],
                    'timestamp': timezone.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'message': f"Processed {result['total_processed']} leads",
                'created': len(result['created']),
                'updated': len(result['updated']),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'errors': serializer.errors,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        # Log the error for monitoring
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Lead sync error: {str(e)}", exc_info=True)
        
        return Response({
            'success': False,
            'error': 'Internal server error during lead sync',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def transform_creatio_data(data):
    """
    Transform data from Creatio CRM format to Django format
    """
    from django.utils import timezone
    
    # If data is already in the correct format, return as-is
    if 'leads' in data:
        return data
    
    # Handle single lead or list of leads from Creatio
    leads_data = data if isinstance(data, list) else [data]
    transformed_leads = []
    
    for lead_data in leads_data:
        # Map Creatio fields to Django fields
        transformed_lead = {
            'crm_id': lead_data.get('Id') or lead_data.get('id') or lead_data.get('crm_id'),
            'name': lead_data.get('Name') or lead_data.get('name') or lead_data.get('ContactName', ''),
            'email': lead_data.get('Email') or lead_data.get('email') or lead_data.get('ContactEmail', ''),
            'company': lead_data.get('Company') or lead_data.get('company') or lead_data.get('AccountName', ''),
            'phone': lead_data.get('Phone') or lead_data.get('phone') or lead_data.get('ContactPhone', ''),
            'status': map_creatio_status(lead_data.get('Status') or lead_data.get('status', 'new')),
            'source': lead_data.get('Source') or lead_data.get('source') or lead_data.get('LeadSource', ''),
            'last_sync': timezone.now().isoformat()
        }
        
        # Remove empty values
        transformed_lead = {k: v for k, v in transformed_lead.items() if v}
        transformed_leads.append(transformed_lead)
    
    return {'leads': transformed_leads}


def map_creatio_status(creatio_status):
    """
    Map Creatio lead status to Django lead status
    """
    status_mapping = {
        'New': 'new',
        'Contacted': 'contacted',
        'Qualified': 'qualified',
        'Proposal': 'proposal',
        'Negotiation': 'negotiation',
        'Closed Won': 'closed_won',
        'Closed Lost': 'closed_lost',
        # Add more mappings as needed
    }
    
    return status_mapping.get(creatio_status, 'new')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lead_meetings(request, lead_id):
    """
    Get all meetings associated with a lead
    """
    lead = get_object_or_404(Lead, id=lead_id)
    meetings = lead.meeting_set.all().order_by('-start_time')
    
    # Import here to avoid circular imports
    from meetings.serializers import MeetingSerializer
    serializer = MeetingSerializer(meetings, many=True)
    
    return Response({
        'lead': LeadSerializer(lead).data,
        'meetings': serializer.data
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_lead_status(request, lead_id):
    """
    Update lead status
    """
    lead = get_object_or_404(Lead, id=lead_id)
    new_status = request.data.get('status')
    
    if new_status not in dict(Lead.STATUS_CHOICES):
        return Response({
            'error': 'Invalid status'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    lead.status = new_status
    lead.save()
    
    return Response({
        'success': True,
        'lead': LeadSerializer(lead).data
    })


@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def match_meeting_to_lead(request):
    """
    Match a meeting to the best lead candidate
    Used by n8n workflow for automatic meeting-lead association
    """
    try:
        meeting_data = request.data
        matching_service = LeadMatchingService()
        
        # Try to find automatic match
        match = matching_service.match_meeting_to_lead(meeting_data)
        
        if match:
            return Response({
                'success': True,
                'match_found': True,
                'match': match,
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
        
        # If no automatic match, return potential matches for manual review
        potential_matches = matching_service.find_potential_matches(meeting_data, limit=5)
        
        return Response({
            'success': True,
            'match_found': False,
            'potential_matches': potential_matches,
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Meeting matching error: {str(e)}", exc_info=True)
        
        return Response({
            'success': False,
            'error': 'Internal server error during meeting matching',
            'timestamp': timezone.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_potential_matches(request):
    """
    Get potential lead matches for a meeting (for manual review)
    """
    try:
        # Get meeting data from query parameters
        attendees = request.GET.getlist('attendees')
        title = request.GET.get('title', '')
        organizer = request.GET.get('organizer', '')
        description = request.GET.get('description', '')
        
        meeting_data = {
            'attendees': attendees,
            'title': title,
            'organizer': organizer,
            'description': description
        }
        
        matching_service = LeadMatchingService()
        potential_matches = matching_service.find_potential_matches(meeting_data, limit=10)
        
        return Response({
            'success': True,
            'potential_matches': potential_matches,
            'meeting_data': meeting_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)