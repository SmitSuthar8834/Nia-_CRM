import asyncio
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from .models import Meeting, MeetingSession, ActionItem, CallBotSession, DraftSummary, ValidationSession, DraftEmail, EmailApproval
from .serializers import (
    MeetingSerializer, MeetingSessionSerializer, 
    ActionItemSerializer, MeetingMatchSerializer,
    CallBotSessionSerializer, DraftSummarySerializer,
    CRMFormattedSummarySerializer, ValidationSessionSerializer,
    ValidationResponseSerializer, ValidationSessionCreateSerializer,
    ValidationSessionDetailSerializer, DraftEmailSerializer,
    EmailApprovalSerializer, EmailDraftCreateSerializer,
    EmailApprovalRequestSerializer, EmailApprovalResponseSerializer,
    ScheduledEmailSerializer
)
from .services import MeetingSessionService
from .crm_service import CRMSyncService, CRMSyncStatus
from .task_scheduler import FollowUpTaskScheduler
from .sync_tracker import SyncTracker, SyncOperation
from .ai_summary_service import AISummaryService, extract_meeting_metrics, format_summary_for_export
from .validation_service import ValidationService
from leads.models import Lead


class MeetingListCreateView(generics.ListCreateAPIView):
    """
    List all meetings or create a new meeting
    """
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter meetings based on query parameters"""
        queryset = Meeting.objects.select_related('lead').all()
        status_filter = self.request.query_params.get('status')
        lead_id = self.request.query_params.get('lead_id')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if lead_id:
            queryset = queryset.filter(lead_id=lead_id)
        
        return queryset


class MeetingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a meeting
    """
    queryset = Meeting.objects.select_related('lead').all()
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated]


@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def match_lead_to_meeting(request):
    """
    Webhook endpoint for n8n to match calendar events to leads
    """
    serializer = MeetingMatchSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    meeting_data = serializer.validated_data
    
    # Simple lead matching logic (can be enhanced later)
    matched_lead = None
    match_confidence = 0.0
    
    # Try to match by email in attendees
    for email in meeting_data.get('attendees', []):
        try:
            lead = Lead.objects.get(email=email)
            matched_lead = lead
            match_confidence = 0.9
            break
        except Lead.DoesNotExist:
            continue
    
    # Create or update meeting
    meeting, created = Meeting.objects.update_or_create(
        calendar_event_id=meeting_data['calendar_event_id'],
        defaults={
            'title': meeting_data['title'],
            'start_time': meeting_data['start_time'],
            'end_time': meeting_data['end_time'],
            'attendees': meeting_data.get('attendees', []),
            'lead': matched_lead,
            'match_confidence': match_confidence if matched_lead else None,
        }
    )
    
    return Response({
        'success': True,
        'meeting_id': meeting.id,
        'matched_lead_id': matched_lead.id if matched_lead else None,
        'match_confidence': match_confidence,
        'created': created
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def meeting_session_detail(request, meeting_id):
    """
    Get meeting session data
    """
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    try:
        session = meeting.meetingsession
        serializer = MeetingSessionSerializer(session)
        return Response(serializer.data)
    except MeetingSession.DoesNotExist:
        return Response({
            'error': 'No session found for this meeting'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_meeting_session(request, meeting_id):
    """
    Start a meeting session using MeetingSessionService
    """
    session_service = MeetingSessionService()
    
    try:
        ai_session_id = request.data.get('ai_session_id', '')
        session = session_service.initialize_session(meeting_id, ai_session_id)
        
        serializer = MeetingSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': 'Failed to start meeting session'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_meeting_session(request, meeting_id):
    """
    End a meeting session using MeetingSessionService
    """
    meeting = get_object_or_404(Meeting, id=meeting_id)
    session_service = MeetingSessionService()
    
    try:
        session = meeting.meetingsession
        session_id = session.id
        
        notes = request.data.get('notes', '')
        summary = request.data.get('summary', '')
        
        success = session_service.end_session(session_id, notes, summary)
        
        if success:
            # Refresh session from database
            session.refresh_from_db()
            serializer = MeetingSessionSerializer(session)
            return Response(serializer.data)
        else:
            return Response({
                'error': 'Failed to end meeting session'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except MeetingSession.DoesNotExist:
        return Response({
            'error': 'No active session found for this meeting'
        }, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_session_notes(request, session_id):
    """
    Update session notes with auto-save functionality
    """
    session_service = MeetingSessionService()
    
    notes = request.data.get('notes', '')
    auto_save = request.data.get('auto_save', True)
    
    success = session_service.update_session_notes(session_id, notes, auto_save)
    
    if success:
        return Response({
            'success': True,
            'message': 'Notes updated successfully'
        })
    else:
        return Response({
            'error': 'Failed to update notes'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_session_transcript(request, session_id):
    """
    Update session transcript
    """
    session_service = MeetingSessionService()
    
    transcript = request.data.get('transcript', '')
    
    success = session_service.update_session_transcript(session_id, transcript)
    
    if success:
        return Response({
            'success': True,
            'message': 'Transcript updated successfully'
        })
    else:
        return Response({
            'error': 'Failed to update transcript'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session_state(request, session_id):
    """
    Get session state from cache or database
    """
    session_service = MeetingSessionService()
    
    session_data = session_service.get_session_state(session_id)
    
    if session_data:
        return Response(session_data)
    else:
        return Response({
            'error': 'Session not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_action_item(request, session_id):
    """
    Add action item to session
    """
    session_service = MeetingSessionService()
    
    description = request.data.get('description', '')
    assignee = request.data.get('assignee', '')
    due_date = request.data.get('due_date')
    
    if not description or not assignee:
        return Response({
            'error': 'Description and assignee are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    success = session_service.add_action_item(session_id, description, assignee, due_date)
    
    if success:
        return Response({
            'success': True,
            'message': 'Action item added successfully'
        })
    else:
        return Response({
            'error': 'Failed to add action item'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def force_save_session(request, session_id):
    """
    Force save cached session data to database
    """
    session_service = MeetingSessionService()
    
    success = session_service.force_save_session(session_id)
    
    if success:
        return Response({
            'success': True,
            'message': 'Session saved successfully'
        })
    else:
        return Response({
            'error': 'Failed to save session'
        }, status=status.HTTP_400_BAD_REQUEST)


# CRM Synchronization Endpoints

@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def sync_meeting_to_crm(request, meeting_id):
    """
    Webhook endpoint for n8n to sync meeting outcomes to CRM
    """
    crm_service = CRMSyncService()
    
    try:
        result = crm_service.sync_meeting_outcome(meeting_id)
        
        response_data = {
            'success': result.status == CRMSyncStatus.SUCCESS,
            'status': result.status.value,
            'message': result.message,
            'crm_record_id': result.crm_record_id,
            'retry_count': result.retry_count
        }
        
        if result.error_details:
            response_data['error_details'] = result.error_details
        
        status_code = status.HTTP_200_OK if result.status == CRMSyncStatus.SUCCESS else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)
        
    except Exception as e:
        return Response({
            'success': False,
            'status': CRMSyncStatus.FAILED.value,
            'message': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def create_follow_up_tasks(request, meeting_id):
    """
    Webhook endpoint for n8n to create follow-up tasks in CRM
    """
    crm_service = CRMSyncService()
    
    try:
        results = crm_service.create_follow_up_tasks(meeting_id)
        
        response_data = {
            'success': all(r.status == CRMSyncStatus.SUCCESS for r in results),
            'total_tasks': len(results),
            'successful_tasks': len([r for r in results if r.status == CRMSyncStatus.SUCCESS]),
            'failed_tasks': len([r for r in results if r.status == CRMSyncStatus.FAILED]),
            'results': [
                {
                    'status': r.status.value,
                    'message': r.message,
                    'crm_record_id': r.crm_record_id,
                    'error_details': r.error_details
                }
                for r in results
            ]
        }
        
        status_code = status.HTTP_200_OK if response_data['success'] else status.HTTP_207_MULTI_STATUS
        return Response(response_data, status=status_code)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crm_sync_status(request, meeting_id):
    """
    Get CRM synchronization status for a meeting
    """
    crm_service = CRMSyncService()
    
    sync_status = crm_service.get_sync_status(meeting_id)
    
    if sync_status:
        return Response({
            'meeting_id': meeting_id,
            'sync_status': sync_status
        })
    else:
        return Response({
            'meeting_id': meeting_id,
            'sync_status': None,
            'message': 'No sync status found'
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_crm_sync(request, meeting_id):
    """
    Retry failed CRM synchronization
    """
    crm_service = CRMSyncService()
    
    try:
        result = crm_service.retry_failed_sync(meeting_id)
        
        response_data = {
            'success': result.status == CRMSyncStatus.SUCCESS,
            'status': result.status.value,
            'message': result.message,
            'crm_record_id': result.crm_record_id
        }
        
        if result.error_details:
            response_data['error_details'] = result.error_details
        
        status_code = status.HTTP_200_OK if result.status == CRMSyncStatus.SUCCESS else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)
        
    except Exception as e:
        return Response({
            'success': False,
            'status': CRMSyncStatus.FAILED.value,
            'message': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Follow-up Task Scheduling Endpoints

@api_view(['POST'])
@permission_classes([AllowAny])  # n8n webhook endpoint
def schedule_follow_up_tasks(request, meeting_id):
    """
    Webhook endpoint for n8n to schedule follow-up tasks and reminders
    """
    scheduler = FollowUpTaskScheduler()
    
    try:
        # Get custom reminder configurations from request if provided
        reminder_configs = request.data.get('reminder_configs')
        
        result = scheduler.schedule_follow_up_tasks(meeting_id, reminder_configs)
        
        response_data = {
            'success': result['success'],
            'message': result['message'],
            'scheduled_tasks': result['scheduled_tasks'],
            'scheduled_reminders': result['scheduled_reminders']
        }
        
        if result.get('errors'):
            response_data['errors'] = result['errors']
        
        status_code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Unexpected error: {str(e)}',
            'scheduled_tasks': 0,
            'scheduled_reminders': 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_scheduling_status(request, meeting_id):
    """
    Get follow-up task scheduling status for a meeting
    """
    scheduler = FollowUpTaskScheduler()
    
    scheduling_status = scheduler.get_scheduling_status(meeting_id)
    
    if scheduling_status:
        return Response({
            'meeting_id': meeting_id,
            'scheduling_status': scheduling_status
        })
    else:
        return Response({
            'meeting_id': meeting_id,
            'scheduling_status': None,
            'message': 'No scheduling status found'
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_reminders(request, action_item_id):
    """
    Cancel scheduled reminders for an action item
    """
    scheduler = FollowUpTaskScheduler()
    
    success = scheduler.cancel_scheduled_reminders(action_item_id)
    
    if success:
        return Response({
            'success': True,
            'message': 'Reminders cancelled successfully'
        })
    else:
        return Response({
            'success': False,
            'message': 'Failed to cancel reminders'
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reschedule_task(request, action_item_id):
    """
    Reschedule a follow-up task with a new due date
    """
    scheduler = FollowUpTaskScheduler()
    
    new_due_date_str = request.data.get('new_due_date')
    if not new_due_date_str:
        return Response({
            'success': False,
            'message': 'new_due_date is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from datetime import datetime
        new_due_date = datetime.strptime(new_due_date_str, '%Y-%m-%d').date()
        
        success = scheduler.reschedule_task(action_item_id, new_due_date)
        
        if success:
            return Response({
                'success': True,
                'message': 'Task rescheduled successfully',
                'new_due_date': new_due_date_str
            })
        else:
            return Response({
                'success': False,
                'message': 'Failed to reschedule task'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except ValueError:
        return Response({
            'success': False,
            'message': 'Invalid date format. Use YYYY-MM-DD'
        }, status=status.HTTP_400_BAD_REQUEST)


# Sync Tracking Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comprehensive_sync_status(request, meeting_id):
    """
    Get comprehensive sync status including tracking information
    """
    tracker = SyncTracker()
    
    sync_status = tracker.get_sync_status(meeting_id)
    
    return Response(sync_status)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_failed_operations(request):
    """
    Get all failed sync operations within a time window
    """
    tracker = SyncTracker()
    
    hours_back = int(request.query_params.get('hours_back', 24))
    failed_operations = tracker.get_failed_operations(hours_back)
    
    return Response({
        'failed_operations': failed_operations,
        'count': len(failed_operations),
        'hours_back': hours_back
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_failed_operation(request, tracking_id):
    """
    Retry a specific failed sync operation
    """
    tracker = SyncTracker()
    
    result = tracker.retry_failed_operation(tracking_id)
    
    status_code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
    return Response(result, status=status_code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_sync_report(request):
    """
    Generate a comprehensive sync report for a date range
    """
    tracker = SyncTracker()
    
    try:
        from datetime import datetime
        
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if not start_date_str or not end_date_str:
            # Default to last 7 days
            end_date = timezone.now()
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
            
            # Make timezone aware
            start_date = timezone.make_aware(start_date)
            end_date = timezone.make_aware(end_date)
        
        report = tracker.generate_sync_report(start_date, end_date)
        
        return Response(report)
        
    except ValueError:
        return Response({
            'error': 'Invalid date format. Use YYYY-MM-DD'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'Failed to generate report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sync_health_metrics(request):
    """
    Get overall sync health metrics
    """
    tracker = SyncTracker()
    
    metrics = tracker.get_sync_health_metrics()
    
    return Response(metrics)


# AI Summary Generation Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_draft_summary(request, bot_session_id):
    """
    Generate AI-powered draft summary from call bot session
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=bot_session_id)
        
        # Initialize AI summary service
        ai_service = AISummaryService()
        
        # Run async initialization and summary generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize service
            initialized = loop.run_until_complete(ai_service.initialize())
            if not initialized:
                return Response({
                    'error': 'Failed to initialize AI summary service'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Generate draft summary
            draft_summary = loop.run_until_complete(
                ai_service.generate_draft_summary(bot_session)
            )
            
            if draft_summary:
                serializer = DraftSummarySerializer(draft_summary)
                return Response({
                    'success': True,
                    'draft_summary': serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': 'Failed to generate draft summary'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        finally:
            loop.run_until_complete(ai_service.cleanup())
            loop.close()
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_draft_summary(request, bot_session_id):
    """
    Get existing draft summary for a call bot session
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=bot_session_id)
        
        try:
            draft_summary = bot_session.draftsummary
            serializer = DraftSummarySerializer(draft_summary)
            return Response(serializer.data)
        except DraftSummary.DoesNotExist:
            return Response({
                'error': 'No draft summary found for this bot session'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_draft_summary(request, summary_id):
    """
    Update an existing draft summary
    """
    try:
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        
        serializer = DraftSummarySerializer(draft_summary, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_summary_confidence(request, summary_id):
    """
    Recalculate and update confidence score for a draft summary
    """
    try:
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        
        # Initialize AI summary service
        ai_service = AISummaryService()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Update confidence score
            loop.run_until_complete(ai_service.update_summary_confidence(draft_summary))
            
            # Return updated summary
            draft_summary.refresh_from_db()
            serializer = DraftSummarySerializer(draft_summary)
            return Response({
                'success': True,
                'updated_confidence': draft_summary.confidence_score,
                'draft_summary': serializer.data
            })
            
        finally:
            loop.run_until_complete(ai_service.cleanup())
            loop.close()
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def format_summary_for_crm(request, summary_id):
    """
    Format draft summary for specific CRM system
    """
    try:
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        crm_system = request.query_params.get('crm_system')
        
        if not crm_system:
            return Response({
                'error': 'crm_system parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if crm_system not in ['salesforce', 'hubspot', 'creatio']:
            return Response({
                'error': 'Invalid CRM system. Must be one of: salesforce, hubspot, creatio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        formatted_data = draft_summary.format_for_crm(crm_system)
        
        return Response({
            'crm_system': crm_system,
            'formatted_data': formatted_data
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_summary(request, summary_id):
    """
    Export draft summary in various formats
    """
    try:
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        export_format = request.query_params.get('format', 'markdown')
        
        if export_format not in ['markdown', 'html', 'text']:
            return Response({
                'error': 'Invalid format. Must be one of: markdown, html, text'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        formatted_content = format_summary_for_export(draft_summary, export_format)
        
        # Set appropriate content type
        content_types = {
            'markdown': 'text/markdown',
            'html': 'text/html',
            'text': 'text/plain'
        }
        
        return Response({
            'format': export_format,
            'content': formatted_content,
            'content_type': content_types[export_format]
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_meeting_metrics(request, summary_id):
    """
    Get comprehensive metrics for a meeting summary
    """
    try:
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        
        metrics = extract_meeting_metrics(draft_summary)
        
        return Response({
            'summary_id': summary_id,
            'meeting_title': draft_summary.bot_session.meeting.title,
            'metrics': metrics
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Validation Session Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_validation_session(request):
    """
    Create a new validation session for a draft summary
    """
    try:
        serializer = ValidationSessionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validation_service = ValidationService()
        
        # Extract validated data
        draft_summary_id = serializer.validated_data['draft_summary_id']
        sales_rep_email = serializer.validated_data['sales_rep_email']
        session_duration_hours = serializer.validated_data.get('session_duration_hours', 24)
        
        # Convert hours to timedelta
        from datetime import timedelta
        session_duration = timedelta(hours=session_duration_hours)
        
        # Create validation session
        validation_session = validation_service.create_validation_session(
            draft_summary_id=draft_summary_id,
            sales_rep_email=sales_rep_email,
            session_duration=session_duration
        )
        
        # Return detailed session data
        response_serializer = ValidationSessionDetailSerializer(validation_session)
        return Response({
            'success': True,
            'validation_session': response_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_validation_sessions(request):
    """
    List validation sessions with optional filtering
    """
    try:
        # Get query parameters
        sales_rep_email = request.query_params.get('sales_rep_email')
        status_filter = request.query_params.get('status')
        
        if sales_rep_email:
            # Get sessions for specific rep
            validation_service = ValidationService()
            sessions = validation_service.get_sessions_for_rep(sales_rep_email, status_filter)
        else:
            # Get all sessions with optional status filter
            queryset = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting__lead'
            ).order_by('-started_at')
            
            if status_filter:
                queryset = queryset.filter(validation_status=status_filter)
            
            sessions = list(queryset)
        
        serializer = ValidationSessionDetailSerializer(sessions, many=True)
        return Response({
            'validation_sessions': serializer.data,
            'count': len(sessions)
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_session(request, session_id):
    """
    Get detailed validation session information
    """
    try:
        validation_service = ValidationService()
        validation_session = validation_service.get_validation_session(session_id)
        
        serializer = ValidationSessionDetailSerializer(validation_session)
        return Response(serializer.data)
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_validation_session(request, session_id):
    """
    Update validation session metadata (not responses)
    """
    try:
        validation_session = get_object_or_404(ValidationSession, id=session_id)
        
        # Only allow updating certain fields
        allowed_fields = ['sales_rep_email']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        if not update_data:
            return Response({
                'error': 'No valid fields to update'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = ValidationSessionSerializer(validation_session, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            
            # Return detailed session data
            response_serializer = ValidationSessionDetailSerializer(validation_session)
            return Response(response_serializer.data)
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_questions(request, session_id):
    """
    Get validation questions for a session
    """
    try:
        validation_service = ValidationService()
        validation_session = validation_service.get_validation_session(session_id)
        
        return Response({
            'session_id': session_id,
            'validation_questions': validation_session.validation_questions,
            'session_status': validation_session.validation_status,
            'expires_at': validation_session.expires_at,
            'time_remaining': validation_session.time_remaining
        })
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_responses(request, session_id):
    """
    Get current validation responses for a session
    """
    try:
        validation_service = ValidationService()
        validation_session = validation_service.get_validation_session(session_id)
        
        return Response({
            'session_id': session_id,
            'rep_responses': validation_session.rep_responses,
            'validation_status': validation_session.validation_status,
            'changes_made': validation_session.changes_made
        })
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_validation_response(request, session_id):
    """
    Submit a response to a validation question
    """
    try:
        serializer = ValidationResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validation_service = ValidationService()
        
        question_id = serializer.validated_data['question_id']
        response = serializer.validated_data['response']
        
        # Submit response
        updated_session = validation_service.submit_validation_response(
            session_id=session_id,
            question_id=question_id,
            response=response
        )
        
        # Return updated session data
        response_serializer = ValidationSessionDetailSerializer(updated_session)
        return Response({
            'success': True,
            'message': 'Response submitted successfully',
            'validation_session': response_serializer.data
        })
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_validation_session(request, session_id):
    """
    Complete validation session and generate final summary
    """
    try:
        validation_service = ValidationService()
        
        # Complete the session
        validation_session, final_summary = validation_service.complete_validation_session(session_id)
        
        # Return completed session data
        response_serializer = ValidationSessionDetailSerializer(validation_session)
        return Response({
            'success': True,
            'message': 'Validation session completed successfully',
            'final_summary': final_summary,
            'validation_session': response_serializer.data
        })
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validation_session_status(request, session_id):
    """
    Get validation session status and progress
    """
    try:
        validation_service = ValidationService()
        validation_session = validation_service.get_validation_session(session_id)
        
        # Calculate progress
        total_questions = len(validation_session.validation_questions)
        required_questions = len([q for q in validation_session.validation_questions if q.get('required', False)])
        answered_questions = len(validation_session.rep_responses)
        answered_required = len([
            q_id for q_id in validation_session.rep_responses.keys()
            if any(q['id'] == q_id and q.get('required', False) for q in validation_session.validation_questions)
        ])
        
        return Response({
            'session_id': session_id,
            'validation_status': validation_session.validation_status,
            'is_expired': validation_session.is_expired,
            'time_remaining': validation_session.time_remaining,
            'progress': {
                'total_questions': total_questions,
                'required_questions': required_questions,
                'answered_questions': answered_questions,
                'answered_required': answered_required,
                'completion_percentage': (answered_questions / total_questions * 100) if total_questions > 0 else 0,
                'required_completion_percentage': (answered_required / required_questions * 100) if required_questions > 0 else 0
            },
            'can_complete': answered_required == required_questions and validation_session.validation_status == 'in_progress'
        })
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def expire_old_validation_sessions(request):
    """
    Manually expire old validation sessions (typically called by scheduled task)
    """
    try:
        validation_service = ValidationService()
        expired_count = validation_service.expire_old_sessions()
        
        return Response({
            'success': True,
            'message': f'Expired {expired_count} validation sessions',
            'expired_count': expired_count
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Call Bot Session Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bot_session(request, session_id):
    """
    Get call bot session details
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=session_id)
        serializer = CallBotSessionSerializer(bot_session)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_bot_session(request, session_id):
    """
    Update call bot session data
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=session_id)
        
        serializer = CallBotSessionSerializer(bot_session, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_bot_transcript(request, session_id):
    """
    Update bot session transcript (for real-time updates)
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=session_id)
        
        transcript_chunk = request.data.get('transcript_chunk', '')
        append_mode = request.data.get('append', True)
        
        if append_mode:
            # Append to existing transcript
            bot_session.raw_transcript += f" {transcript_chunk}"
        else:
            # Replace entire transcript
            bot_session.raw_transcript = transcript_chunk
        
        bot_session.save(update_fields=['raw_transcript'])
        
        return Response({
            'success': True,
            'transcript_length': len(bot_session.raw_transcript),
            'message': 'Transcript updated successfully'
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_speaker_mapping(request, session_id):
    """
    Update speaker mapping for bot session
    """
    try:
        bot_session = get_object_or_404(CallBotSession, id=session_id)
        
        speaker_mapping = request.data.get('speaker_mapping', {})
        
        if not isinstance(speaker_mapping, dict):
            return Response({
                'error': 'speaker_mapping must be a dictionary'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Merge with existing mapping
        bot_session.speaker_mapping.update(speaker_mapping)
        bot_session.save(update_fields=['speaker_mapping'])
        
        return Response({
            'success': True,
            'speaker_count': len(bot_session.speaker_mapping),
            'message': 'Speaker mapping updated successfully'
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Batch Processing Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_generate_summaries(request):
    """
    Generate draft summaries for multiple bot sessions
    """
    try:
        session_ids = request.data.get('session_ids', [])
        
        if not session_ids:
            return Response({
                'error': 'session_ids list is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        results = []
        ai_service = AISummaryService()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize service once
            initialized = loop.run_until_complete(ai_service.initialize())
            if not initialized:
                return Response({
                    'error': 'Failed to initialize AI summary service'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Process each session
            for session_id in session_ids:
                try:
                    bot_session = CallBotSession.objects.get(id=session_id)
                    draft_summary = loop.run_until_complete(
                        ai_service.generate_draft_summary(bot_session)
                    )
                    
                    if draft_summary:
                        results.append({
                            'session_id': session_id,
                            'success': True,
                            'summary_id': draft_summary.id
                        })
                    else:
                        results.append({
                            'session_id': session_id,
                            'success': False,
                            'error': 'Failed to generate summary'
                        })
                        
                except CallBotSession.DoesNotExist:
                    results.append({
                        'session_id': session_id,
                        'success': False,
                        'error': 'Bot session not found'
                    })
                except Exception as e:
                    results.append({
                        'session_id': session_id,
                        'success': False,
                        'error': str(e)
                    })
            
            successful_count = len([r for r in results if r['success']])
            
            return Response({
                'total_processed': len(session_ids),
                'successful': successful_count,
                'failed': len(session_ids) - successful_count,
                'results': results
            })
            
        finally:
            loop.run_until_complete(ai_service.cleanup())
            loop.close()
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# CRM Suggestion Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_crm_suggestions(request, summary_id):
    """
    Generate CRM update suggestions from draft summary
    """
    try:
        from .crm_suggestion_service import CRMSuggestionService, CRMSystem
        
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        crm_system_str = request.data.get('crm_system', 'salesforce')
        current_stage = request.data.get('current_opportunity_stage')
        current_deal_value = request.data.get('current_deal_value')
        
        # Validate CRM system
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Invalid CRM system: {crm_system_str}. Must be one of: salesforce, hubspot, creatio'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Initialize service and generate suggestions
        suggestion_service = CRMSuggestionService()
        
        suggestions = suggestion_service.generate_crm_suggestions(
            meeting_summary=draft_summary.ai_generated_summary,
            action_items=draft_summary.extracted_action_items,
            key_points=draft_summary.key_points,
            decisions_made=draft_summary.decisions_made,
            crm_system=crm_system,
            current_opportunity_stage=current_stage,
            current_deal_value=current_deal_value
        )
        
        # Serialize response
        response_data = {
            'crm_system': suggestions.crm_system.value,
            'field_updates': suggestions.field_updates,
            'field_mappings': [
                {
                    'field_name': fm.field_name,
                    'field_value': fm.field_value,
                    'field_type': fm.field_type,
                    'confidence': fm.confidence,
                    'source_evidence': fm.source_evidence
                }
                for fm in suggestions.field_mappings
            ],
            'opportunity_suggestion': {
                'current_stage': suggestions.opportunity_suggestion.current_stage,
                'suggested_stage': suggestions.opportunity_suggestion.suggested_stage.value,
                'confidence': suggestions.opportunity_suggestion.confidence,
                'reasoning': suggestions.opportunity_suggestion.reasoning,
                'supporting_evidence': suggestions.opportunity_suggestion.supporting_evidence
            } if suggestions.opportunity_suggestion else None,
            'follow_up_tasks': [
                {
                    'title': task.title,
                    'description': task.description,
                    'priority': task.priority.value,
                    'due_date': task.due_date.isoformat(),
                    'assignee': task.assignee,
                    'task_type': task.task_type,
                    'estimated_duration': task.estimated_duration,
                    'crm_category': task.crm_category
                }
                for task in suggestions.follow_up_tasks
            ],
            'reminder_suggestions': [
                {
                    'reminder_type': reminder.reminder_type.value,
                    'title': reminder.title,
                    'description': reminder.description,
                    'reminder_date': reminder.reminder_date.isoformat(),
                    'recipient': reminder.recipient,
                    'priority': reminder.priority.value
                }
                for reminder in suggestions.reminder_suggestions
            ],
            'confidence_score': suggestions.confidence_score,
            'validation_notes': suggestions.validation_notes,
            'suggested_next_meeting': suggestions.suggested_next_meeting.isoformat() if suggestions.suggested_next_meeting else None,
            'deal_value_estimate': suggestions.deal_value_estimate
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to generate CRM suggestions: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_crm_field_mapping(request):
    """
    Validate CRM field mapping for specific system
    """
    try:
        from .crm_suggestion_service import CRMSuggestionService, CRMSystem
        
        crm_system_str = request.data.get('crm_system')
        field_name = request.data.get('field_name')
        field_value = request.data.get('field_value')
        
        if not all([crm_system_str, field_name, field_value]):
            return Response({
                'error': 'crm_system, field_name, and field_value are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Invalid CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = CRMSuggestionService()
        field_mappings = service.field_mappings.get(crm_system, {})
        
        # Check if field exists in mapping
        field_exists = any(
            config['field'] == field_name 
            for config in field_mappings.values()
        )
        
        if not field_exists:
            return Response({
                'valid': False,
                'message': f'Field {field_name} not found in {crm_system_str} mapping',
                'available_fields': [config['field'] for config in field_mappings.values()]
            })
        
        # Basic validation (could be enhanced with actual CRM API validation)
        return Response({
            'valid': True,
            'message': f'Field {field_name} is valid for {crm_system_str}',
            'field_type': next(
                config['type'] for config in field_mappings.values() 
                if config['field'] == field_name
            )
        })
        
    except Exception as e:
        return Response({
            'error': f'Validation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crm_field_mappings(request, crm_system):
    """
    Get available field mappings for a CRM system
    """
    try:
        from .crm_suggestion_service import CRMSuggestionService, CRMSystem
        
        try:
            crm_enum = CRMSystem(crm_system)
        except ValueError:
            return Response({
                'error': f'Invalid CRM system: {crm_system}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = CRMSuggestionService()
        mappings = service.field_mappings.get(crm_enum, {})
        
        formatted_mappings = {
            logical_name: {
                'crm_field': config['field'],
                'field_type': config['type'],
                'description': f'{logical_name.replace("_", " ").title()} field'
            }
            for logical_name, config in mappings.items()
        }
        
        return Response({
            'crm_system': crm_system,
            'field_mappings': formatted_mappings,
            'total_fields': len(formatted_mappings)
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to get field mappings: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_crm_update(request, summary_id):
    """
    Preview what the CRM update would look like without applying it
    """
    try:
        from .crm_suggestion_service import CRMSuggestionService, CRMSystem
        
        draft_summary = get_object_or_404(DraftSummary, id=summary_id)
        crm_system_str = request.data.get('crm_system', 'salesforce')
        
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Invalid CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        service = CRMSuggestionService()
        suggestions = service.generate_crm_suggestions(
            meeting_summary=draft_summary.ai_generated_summary,
            action_items=draft_summary.extracted_action_items,
            key_points=draft_summary.key_points,
            decisions_made=draft_summary.decisions_made,
            crm_system=crm_system
        )
        
        # Format as CRM-specific preview
        crm_formatted = draft_summary.format_for_crm(crm_system_str)
        
        return Response({
            'preview': {
                'crm_system': crm_system_str,
                'formatted_data': crm_formatted,
                'suggested_updates': suggestions.field_updates,
                'confidence_score': suggestions.confidence_score,
                'validation_required': suggestions.confidence_score < 0.8
            },
            'summary': {
                'total_fields': len(suggestions.field_updates),
                'high_confidence_fields': len([
                    fm for fm in suggestions.field_mappings if fm.confidence > 0.8
                ]),
                'requires_review': len([
                    fm for fm in suggestions.field_mappings if fm.confidence < 0.7
                ])
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to generate preview: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Validation Session Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_validation_session(request):
    """
    Create a new validation session for a draft summary
    """
    validation_service = ValidationService()
    
    serializer = ValidationSessionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from datetime import timedelta
        
        data = serializer.validated_data
        session_duration = timedelta(hours=data.get('session_duration_hours', 24))
        
        validation_session = validation_service.create_validation_session(
            draft_summary_id=data['draft_summary_id'],
            sales_rep_email=data['sales_rep_email'],
            session_duration=session_duration
        )
        
        response_serializer = ValidationSessionDetailSerializer(validation_session)
        return Response({
            'success': True,
            'validation_session': response_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_session(request, session_id):
    """
    Get validation session details
    """
    validation_service = ValidationService()
    
    try:
        validation_session = validation_service.get_validation_session(session_id)
        serializer = ValidationSessionDetailSerializer(validation_session)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_validation_sessions(request):
    """
    List validation sessions for a sales rep with optional status filter
    """
    validation_service = ValidationService()
    
    sales_rep_email = request.query_params.get('sales_rep_email')
    status_filter = request.query_params.get('status')
    
    if not sales_rep_email:
        return Response({
            'error': 'sales_rep_email parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        sessions = validation_service.get_sessions_for_rep(sales_rep_email, status_filter)
        serializer = ValidationSessionSerializer(sessions, many=True)
        
        return Response({
            'sessions': serializer.data,
            'count': len(sessions),
            'filters': {
                'sales_rep_email': sales_rep_email,
                'status': status_filter
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_validation_response(request, session_id):
    """
    Submit a response to a validation question
    """
    validation_service = ValidationService()
    
    serializer = ValidationResponseSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        data = serializer.validated_data
        
        updated_session = validation_service.submit_validation_response(
            session_id=session_id,
            question_id=data['question_id'],
            response=data['response']
        )
        
        response_serializer = ValidationSessionDetailSerializer(updated_session)
        return Response({
            'success': True,
            'validation_session': response_serializer.data,
            'message': 'Response submitted successfully'
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_validation_session(request, session_id):
    """
    Complete a validation session and generate final summary
    """
    validation_service = ValidationService()
    
    try:
        completed_session, final_summary = validation_service.complete_validation_session(session_id)
        
        response_serializer = ValidationSessionDetailSerializer(completed_session)
        return Response({
            'success': True,
            'validation_session': response_serializer.data,
            'final_summary': final_summary,
            'message': 'Validation session completed successfully'
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_questions(request, session_id):
    """
    Get validation questions for a session
    """
    validation_service = ValidationService()
    
    try:
        validation_session = validation_service.get_validation_session(session_id)
        
        return Response({
            'session_id': session_id,
            'validation_questions': validation_session.validation_questions,
            'validation_status': validation_session.validation_status,
            'expires_at': validation_session.expires_at,
            'is_expired': validation_session.is_expired
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_validation_responses(request, session_id):
    """
    Get submitted responses for a validation session
    """
    validation_service = ValidationService()
    
    try:
        validation_session = validation_service.get_validation_session(session_id)
        
        return Response({
            'session_id': session_id,
            'rep_responses': validation_session.rep_responses,
            'validation_status': validation_session.validation_status,
            'changes_made': validation_session.changes_made
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_validation_session(request, session_id):
    """
    Update validation session metadata (status, notes, etc.)
    """
    try:
        validation_session = get_object_or_404(ValidationSession, id=session_id)
        
        # Only allow updating certain fields
        allowed_fields = ['validated_summary', 'approved_crm_updates']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = ValidationSessionSerializer(validation_session, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            
            response_serializer = ValidationSessionDetailSerializer(validation_session)
            return Response({
                'success': True,
                'validation_session': response_serializer.data
            })
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def expire_old_validation_sessions(request):
    """
    Manually trigger expiration of old validation sessions
    """
    validation_service = ValidationService()
    
    try:
        expired_count = validation_service.expire_old_sessions()
        
        return Response({
            'success': True,
            'expired_sessions': expired_count,
            'message': f'Marked {expired_count} sessions as expired'
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validation_session_status(request, session_id):
    """
    Get validation session status and progress
    """
    validation_service = ValidationService()
    
    try:
        validation_session = validation_service.get_validation_session(session_id)
        
        # Calculate progress
        total_questions = len(validation_session.validation_questions)
        required_questions = len([q for q in validation_session.validation_questions if q.get('required', False)])
        answered_questions = len(validation_session.rep_responses)
        answered_required = len([
            q_id for q_id in validation_session.rep_responses.keys()
            if any(q['id'] == q_id and q.get('required', False) for q in validation_session.validation_questions)
        ])
        
        progress = {
            'total_questions': total_questions,
            'required_questions': required_questions,
            'answered_questions': answered_questions,
            'answered_required': answered_required,
            'completion_percentage': (answered_questions / total_questions * 100) if total_questions > 0 else 0,
            'required_completion_percentage': (answered_required / required_questions * 100) if required_questions > 0 else 0,
            'can_complete': answered_required == required_questions
        }
        
        return Response({
            'session_id': session_id,
            'validation_status': validation_session.validation_status,
            'is_expired': validation_session.is_expired,
            'time_remaining': validation_session.time_remaining,
            'progress': progress,
            'started_at': validation_session.started_at,
            'completed_at': validation_session.completed_at,
            'expires_at': validation_session.expires_at
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)

# CRM Approval Workflow Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_crm_updates(request, session_id):
    """
    Approve CRM updates for specific systems after validation completion
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    approved_systems = request.data.get('approved_systems', [])
    custom_updates = request.data.get('custom_updates')
    
    if not approved_systems:
        return Response({
            'error': 'approved_systems is required and must not be empty'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        success, sync_records = approval_service.approve_crm_updates(
            session_id=session_id,
            approved_systems=approved_systems,
            custom_updates=custom_updates
        )
        
        from .serializers import CRMSyncRecordSerializer
        sync_records_data = CRMSyncRecordSerializer(sync_records, many=True).data
        
        return Response({
            'success': success,
            'message': f'CRM updates approved for {len(approved_systems)} systems',
            'approved_systems': approved_systems,
            'sync_records': sync_records_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_crm_updates(request, session_id):
    """
    Reject CRM updates for a validation session
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    rejection_reason = request.data.get('rejection_reason', '')
    
    if not rejection_reason:
        return Response({
            'error': 'rejection_reason is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        updated_session = approval_service.reject_crm_updates(
            session_id=session_id,
            rejection_reason=rejection_reason
        )
        
        response_serializer = ValidationSessionDetailSerializer(updated_session)
        return Response({
            'success': True,
            'message': 'CRM updates rejected',
            'rejection_reason': rejection_reason,
            'validation_session': response_serializer.data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crm_sync_status(request, session_id):
    """
    Get CRM synchronization status for a validation session
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    try:
        sync_status = approval_service.get_crm_sync_status(session_id)
        return Response(sync_status)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_failed_crm_sync(request, sync_record_id):
    """
    Retry a failed CRM synchronization
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    try:
        updated_record = approval_service.retry_failed_sync(sync_record_id)
        
        from .serializers import CRMSyncRecordSerializer
        record_data = CRMSyncRecordSerializer(updated_record).data
        
        return Response({
            'success': True,
            'message': 'CRM sync retry initiated',
            'sync_record': record_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([AllowAny])  # External sync processes
def update_crm_sync_status(request, sync_record_id):
    """
    Update CRM sync record status (for external sync processes)
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    new_status = request.data.get('status')
    crm_record_id = request.data.get('crm_record_id')
    error_message = request.data.get('error_message')
    
    if not new_status:
        return Response({
            'error': 'status is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        updated_record = approval_service.update_sync_record_status(
            sync_record_id=sync_record_id,
            status=new_status,
            crm_record_id=crm_record_id,
            error_message=error_message
        )
        
        from .serializers import CRMSyncRecordSerializer
        record_data = CRMSyncRecordSerializer(updated_record).data
        
        return Response({
            'success': True,
            'message': f'CRM sync status updated to {new_status}',
            'sync_record': record_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_approval_summary(request, session_id):
    """
    Get comprehensive approval summary for a validation session
    """
    from .crm_approval_service import CRMApprovalService
    
    approval_service = CRMApprovalService()
    
    try:
        approval_summary = approval_service.generate_approval_summary(session_id)
        return Response(approval_summary)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_opportunity_from_meeting(request, validation_session_id):
    """
    Update CRM opportunity/deal based on meeting outcome
    """
    try:
        from .crm_service import CRMService, CRMSystem
        
        crm_service = CRMService()
        
        # Get request data
        crm_system_str = request.data.get('crm_system', 'salesforce')
        opportunity_id = request.data.get('opportunity_id')
        stage_updates = request.data.get('stage_updates', {})
        
        if not opportunity_id:
            return Response({
                'error': 'opportunity_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert string to enum
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Unsupported CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update opportunity
        result = crm_service.update_opportunity_from_meeting(
            validation_session_id,
            crm_system,
            opportunity_id,
            stage_updates
        )
        
        return Response({
            'success': result.status.value == 'success',
            'status': result.status.value,
            'message': result.message,
            'opportunity_id': result.crm_record_id
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to update opportunity',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_opportunity_sync_suggestions(request, validation_session_id):
    """
    Get opportunity update suggestions based on meeting outcome
    """
    try:
        from .crm_service import CRMService, CRMSystem
        
        crm_service = CRMService()
        
        crm_system_str = request.query_params.get('crm_system', 'salesforce')
        
        # Convert string to enum
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Unsupported CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get suggestions
        suggestions = crm_service.get_opportunity_sync_suggestions(
            validation_session_id,
            crm_system
        )
        
        if 'error' in suggestions:
            return Response({
                'error': suggestions['error']
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response(suggestions)
        
    except Exception as e:
        return Response({
            'error': 'Failed to get opportunity suggestions',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_sync_validation_session(request, validation_session_id):
    """
    Perform bulk sync of meeting outcome, tasks, and optionally opportunity updates
    """
    try:
        from .crm_service import CRMService, CRMSystem
        
        crm_service = CRMService()
        
        # Get request data
        crm_system_str = request.data.get('crm_system', 'salesforce')
        include_opportunity_update = request.data.get('include_opportunity_update', False)
        opportunity_data = request.data.get('opportunity_data', {})
        
        # Convert string to enum
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Unsupported CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Perform bulk sync
        results = crm_service.bulk_sync_validation_session(
            validation_session_id,
            crm_system,
            include_opportunity_update,
            opportunity_data
        )
        
        # Format response
        response_data = {
            'success': True,
            'results': {}
        }
        
        for sync_type, result in results.items():
            if isinstance(result, list):
                # Handle task sync results (list of results)
                response_data['results'][sync_type] = [
                    {
                        'status': r.status.value,
                        'message': r.message,
                        'crm_record_id': r.crm_record_id
                    } for r in result
                ]
            else:
                # Handle single result
                response_data['results'][sync_type] = {
                    'status': result.status.value,
                    'message': result.message,
                    'crm_record_id': result.crm_record_id
                }
        
        return Response(response_data)
        
    except Exception as e:
        return Response({
            'error': 'Failed to perform bulk sync',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_opportunity_details(request, opportunity_id):
    """
    Get opportunity/deal details from CRM system
    """
    try:
        from .crm_service import CRMService, CRMSystem
        
        crm_service = CRMService()
        
        crm_system_str = request.query_params.get('crm_system', 'salesforce')
        
        # Convert string to enum
        try:
            crm_system = CRMSystem(crm_system_str)
        except ValueError:
            return Response({
                'error': f'Unsupported CRM system: {crm_system_str}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get CRM client and fetch opportunity details
        client = crm_service.get_client(crm_system)
        opportunity_details = client.get_opportunity_details(opportunity_id)
        
        return Response({
            'success': True,
            'opportunity_details': opportunity_details,
            'crm_system': crm_system_str
        })
        
    except Exception as e:
        return Response({
            'error': 'Failed to get opportunity details',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#
 Email Management Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_draft_email(request):
    """
    Create a draft follow-up email based on validation session
    """
    try:
        serializer = EmailDraftCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get validation session
        validation_session_id = serializer.validated_data['validation_session_id']
        validation_session = get_object_or_404(ValidationSession, id=validation_session_id)
        
        # Generate email content based on meeting outcome
        from .email_service import EmailDraftService
        email_service = EmailDraftService()
        draft_email = email_service.create_draft_email(
            validation_session=validation_session,
            email_type=serializer.validated_data['email_type'],
            recipient_email=serializer.validated_data['recipient_email'],
            recipient_name=serializer.validated_data.get('recipient_name', ''),
            cc_emails=serializer.validated_data.get('cc_emails', []),
            bcc_emails=serializer.validated_data.get('bcc_emails', []),
            custom_template=serializer.validated_data.get('custom_template', ''),
            include_meeting_summary=serializer.validated_data.get('include_meeting_summary', True),
            include_action_items=serializer.validated_data.get('include_action_items', True),
            include_next_steps=serializer.validated_data.get('include_next_steps', True)
        )
        
        if draft_email:
            serializer = DraftEmailSerializer(draft_email)
            return Response({
                'success': True,
                'draft_email': serializer.data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': 'Failed to create draft email'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_draft_emails(request):
    """
    List draft emails with optional filtering
    """
    try:
        queryset = DraftEmail.objects.select_related('validation_session').all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        email_type_filter = request.query_params.get('email_type')
        validation_session_id = request.query_params.get('validation_session_id')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if email_type_filter:
            queryset = queryset.filter(email_type=email_type_filter)
        if validation_session_id:
            queryset = queryset.filter(validation_session_id=validation_session_id)
        
        # Order by creation date (newest first)
        queryset = queryset.order_by('-created_at')
        
        serializer = DraftEmailSerializer(queryset, many=True)
        return Response({
            'success': True,
            'draft_emails': serializer.data,
            'count': queryset.count()
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_draft_email(request, email_id):
    """
    Get detailed draft email information
    """
    try:
        draft_email = get_object_or_404(DraftEmail, id=email_id)
        serializer = DraftEmailSerializer(draft_email)
        return Response(serializer.data)
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_draft_email(request, email_id):
    """
    Update draft email content
    """
    try:
        draft_email = get_object_or_404(DraftEmail, id=email_id)
        
        # Only allow updates if email is in draft status
        if draft_email.status not in ['draft', 'rejected']:
            return Response({
                'error': 'Cannot update email that is not in draft or rejected status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = DraftEmailSerializer(draft_email, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'draft_email': serializer.data
            })
        else:
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_draft_email(request, email_id):
    """
    Delete draft email
    """
    try:
        draft_email = get_object_or_404(DraftEmail, id=email_id)
        
        # Only allow deletion if email is in draft status
        if draft_email.status not in ['draft', 'rejected']:
            return Response({
                'error': 'Cannot delete email that is not in draft or rejected status'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        draft_email.delete()
        return Response({
            'success': True,
            'message': 'Draft email deleted successfully'
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_email_approval(request):
    """
    Request approval for a draft email
    """
    try:
        serializer = EmailApprovalRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get draft email
        draft_email_id = serializer.validated_data['draft_email_id']
        draft_email = get_object_or_404(DraftEmail, id=draft_email_id)
        
        # Check if email is in draft status
        if draft_email.status != 'draft':
            return Response({
                'error': 'Email must be in draft status to request approval'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create approval request
        from .email_service import EmailApprovalService
        email_service = EmailApprovalService()
        approval = email_service.request_approval(
            draft_email=draft_email,
            approver_email=serializer.validated_data['approver_email'],
            approval_expires_hours=serializer.validated_data.get('approval_expires_hours', 24)
        )
        
        if approval:
            # Update draft email status
            draft_email.status = 'pending_approval'
            draft_email.approval_requested_at = timezone.now()
            draft_email.save()
            
            serializer = EmailApprovalSerializer(approval)
            return Response({
                'success': True,
                'approval': serializer.data,
                'message': 'Approval request sent successfully'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': 'Failed to create approval request'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])  # Public endpoint for email approval links
def respond_to_email_approval(request):
    """
    Respond to email approval request (approve/reject)
    """
    try:
        serializer = EmailApprovalResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get approval by token
        approval_token = serializer.validated_data['approval_token']
        approval = get_object_or_404(EmailApproval, approval_token=approval_token)
        
        # Check if approval is still valid
        if approval.is_expired:
            return Response({
                'error': 'Approval request has expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if approval.status != 'pending':
            return Response({
                'error': 'Approval request has already been processed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process approval response
        from .email_service import EmailApprovalService
        email_service = EmailApprovalService()
        result = email_service.process_approval_response(
            approval=approval,
            action=serializer.validated_data['action'],
            rejection_reason=serializer.validated_data.get('rejection_reason', '')
        )
        
        if result:
            return Response({
                'success': True,
                'message': f'Email {serializer.validated_data["action"]}d successfully',
                'action': serializer.validated_data['action']
            })
        else:
            return Response({
                'error': 'Failed to process approval response'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_email_approvals(request):
    """
    List email approval requests
    """
    try:
        queryset = EmailApproval.objects.select_related('draft_email').all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        approver_email = request.query_params.get('approver_email')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if approver_email:
            queryset = queryset.filter(approver_email=approver_email)
        
        # Order by creation date (newest first)
        queryset = queryset.order_by('-created_at')
        
        serializer = EmailApprovalSerializer(queryset, many=True)
        return Response({
            'success': True,
            'approvals': serializer.data,
            'count': queryset.count()
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_email(request):
    """
    Schedule an approved email for future sending
    """
    try:
        serializer = ScheduledEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid data',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get draft email
        draft_email_id = serializer.validated_data['draft_email_id']
        draft_email = get_object_or_404(DraftEmail, id=draft_email_id)
        
        # Check if email is approved
        if draft_email.status != 'approved':
            return Response({
                'error': 'Email must be approved before scheduling'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Schedule email
        from .email_service import EmailSchedulingService
        email_service = EmailSchedulingService()
        result = email_service.schedule_email(
            draft_email=draft_email,
            scheduled_send_time=serializer.validated_data['scheduled_send_time']
        )
        
        if result:
            return Response({
                'success': True,
                'message': 'Email scheduled successfully',
                'scheduled_send_time': serializer.validated_data['scheduled_send_time']
            })
        else:
            return Response({
                'error': 'Failed to schedule email'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_scheduled_emails(request):
    """
    List scheduled emails
    """
    try:
        queryset = DraftEmail.objects.filter(status='scheduled').order_by('scheduled_send_time')
        
        # Apply filters
        email_type_filter = request.query_params.get('email_type')
        if email_type_filter:
            queryset = queryset.filter(email_type=email_type_filter)
        
        serializer = DraftEmailSerializer(queryset, many=True)
        return Response({
            'success': True,
            'scheduled_emails': serializer.data,
            'count': queryset.count()
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_scheduled_email(request, email_id):
    """
    Cancel a scheduled email
    """
    try:
        draft_email = get_object_or_404(DraftEmail, id=email_id)
        
        # Check if email is scheduled
        if draft_email.status != 'scheduled':
            return Response({
                'error': 'Email is not scheduled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Cancel scheduling
        draft_email.status = 'approved'
        draft_email.scheduled_send_time = None
        draft_email.save()
        
        return Response({
            'success': True,
            'message': 'Scheduled email cancelled successfully'
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_email_immediately(request, email_id):
    """
    Send an approved email immediately
    """
    try:
        draft_email = get_object_or_404(DraftEmail, id=email_id)
        
        # Check if email is approved or scheduled
        if draft_email.status not in ['approved', 'scheduled']:
            return Response({
                'error': 'Email must be approved or scheduled before sending'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Send email
        from .email_service import EmailSendingService
        email_service = EmailSendingService()
        result = email_service.send_email(draft_email)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Email sent successfully'
            })
        else:
            return Response({
                'error': f'Failed to send email: {result["error"]}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)