from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import AISession, AIInteraction
from .serializers import (
    AISessionSerializer, AIInitializeSerializer, AIQuestionSerializer,
    AINotesSerializer, AISummarySerializer
)
from .services import AIAssistantService
from meetings.models import Meeting
import time


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_ai_session(request):
    """
    Initialize AI session with lead context
    """
    serializer = AIInitializeSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    meeting_id = serializer.validated_data['meeting_id']
    lead_context = serializer.validated_data.get('lead_context', {})
    
    # Verify meeting exists
    meeting = get_object_or_404(Meeting, id=meeting_id)
    
    try:
        # Initialize AI session using service
        ai_service = AIAssistantService()
        session = ai_service.initialize_session(meeting_id, lead_context)
        
        return Response({
            'success': True,
            'session': AISessionSerializer(session).data,
            'ai_available': ai_service.is_available()
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_questions(request):
    """
    Generate AI-powered question suggestions
    """
    serializer = AIQuestionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    session_id = serializer.validated_data.get('session_id')
    conversation_context = serializer.validated_data['conversation_context']
    meeting_stage = serializer.validated_data.get('meeting_stage', 'general')
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Generate questions using AI service
        ai_service = AIAssistantService()
        questions = ai_service.generate_questions(session_id, conversation_context, meeting_stage)
        
        return Response({
            'success': True,
            'questions': questions,
            'meeting_stage': meeting_stage,
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_notes(request):
    """
    Process meeting notes and extract action items
    """
    serializer = AINotesSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    session_id = serializer.validated_data.get('session_id')
    meeting_notes = serializer.validated_data['meeting_notes']
    extract_action_items = serializer.validated_data.get('extract_action_items', True)
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        
        # Extract action items if requested
        action_items = []
        if extract_action_items:
            action_items = ai_service.extract_action_items(session_id, meeting_notes)
        
        return Response({
            'success': True,
            'processed_notes': meeting_notes,
            'action_items': action_items,
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_summary(request):
    """
    Generate meeting summary
    """
    serializer = AISummarySerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    session_id = serializer.validated_data.get('session_id')
    meeting_transcript = serializer.validated_data['meeting_transcript']
    meeting_notes = serializer.validated_data.get('meeting_notes', '')
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Generate summary using AI service
        ai_service = AIAssistantService()
        summary = ai_service.generate_summary(session_id, meeting_transcript, meeting_notes)
        
        return Response({
            'success': True,
            'summary': summary,
            'word_count': len(summary.split()),
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_ai_session(request):
    """
    End AI session and cleanup
    """
    session_id = request.data.get('session_id')
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        ai_service.end_session(session_id)
        
        return Response({
            'success': True,
            'message': 'AI session ended successfully'
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
from django.http import StreamingHttpResponse
import json
import time

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stream_questions(request):
    """
    Stream AI-powered question suggestions in real-time
    """
    serializer = AIQuestionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    session_id = serializer.validated_data.get('session_id')
    conversation_context = serializer.validated_data['conversation_context']
    meeting_stage = serializer.validated_data.get('meeting_stage', 'general')
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def generate_streaming_questions():
        """Generator function for streaming questions"""
        try:
            ai_service = AIAssistantService()
            
            # Send initial response
            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing conversation...'})}\n\n"
            time.sleep(0.5)  # Simulate processing time
            
            # Analyze context
            context_analysis = ai_service.analyze_conversation_context(conversation_context)
            yield f"data: {json.dumps({'type': 'analysis', 'data': context_analysis})}\n\n"
            time.sleep(0.5)
            
            # Generate questions
            yield f"data: {json.dumps({'type': 'status', 'message': 'Generating questions...'})}\n\n"
            questions = ai_service.generate_questions(session_id, conversation_context, meeting_stage)
            
            # Stream questions one by one
            for i, question in enumerate(questions):
                time.sleep(0.3)  # Simulate streaming delay
                yield f"data: {json.dumps({'type': 'question', 'index': i, 'question': question})}\n\n"
            
            # Send completion
            yield f"data: {json.dumps({'type': 'complete', 'total_questions': len(questions)})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    response = StreamingHttpResponse(
        generate_streaming_questions(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    response['Access-Control-Allow-Origin'] = '*'
    
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_conversation(request):
    """
    Analyze conversation context and return insights
    """
    conversation_context = request.data.get('conversation_context', '')
    
    if not conversation_context:
        return Response({
            'success': False,
            'error': 'conversation_context is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        analysis = ai_service.analyze_conversation_context(conversation_context)
        
        return Response({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_transcript(request):
    """
    Process meeting transcript with speaker identification and note extraction
    """
    session_id = request.data.get('session_id')
    transcript = request.data.get('transcript', '')
    identify_speakers = request.data.get('identify_speakers', True)
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not transcript:
        return Response({
            'success': False,
            'error': 'transcript is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        result = ai_service.process_meeting_transcript(session_id, transcript, identify_speakers)
        
        return Response({
            'success': True,
            'result': result,
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extract_action_items_from_transcript(request):
    """
    Extract action items from meeting transcript with speaker attribution
    """
    session_id = request.data.get('session_id')
    transcript = request.data.get('transcript', '')
    structured_notes = request.data.get('structured_notes', None)
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not transcript:
        return Response({
            'success': False,
            'error': 'transcript is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        action_items = ai_service.extract_action_items_from_transcript(
            session_id, transcript, structured_notes
        )
        
        return Response({
            'success': True,
            'action_items': action_items,
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_comprehensive_summary(request):
    """
    Generate comprehensive meeting summary with all components
    """
    session_id = request.data.get('session_id')
    transcript = request.data.get('transcript', '')
    structured_notes = request.data.get('structured_notes', None)
    include_action_items = request.data.get('include_action_items', True)
    include_decisions = request.data.get('include_decisions', True)
    include_key_points = request.data.get('include_key_points', True)
    
    if not session_id:
        return Response({
            'success': False,
            'error': 'session_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not transcript:
        return Response({
            'success': False,
            'error': 'transcript is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ai_service = AIAssistantService()
        
        # Process transcript if structured notes not provided
        if not structured_notes:
            transcript_result = ai_service.process_meeting_transcript(session_id, transcript, True)
            structured_notes = transcript_result['structured_notes']
        
        # Generate summary
        summary = ai_service.generate_summary(session_id, transcript, '')
        
        # Extract additional components
        result = {
            'summary': summary,
            'speakers': [],
            'key_points': [],
            'decisions': [],
            'action_items': [],
            'questions_raised': []
        }
        
        if structured_notes:
            # Extract speakers
            speakers = set()
            for note in structured_notes:
                if note.get('speaker') and note['speaker'] != 'Unknown':
                    speakers.add(note['speaker'])
            result['speakers'] = list(speakers)
        
        if include_key_points:
            result['key_points'] = ai_service._extract_key_points(transcript)
        
        if include_decisions:
            result['decisions'] = ai_service._extract_decisions(transcript)
        
        if include_action_items:
            result['action_items'] = ai_service.extract_action_items_from_transcript(
                session_id, transcript, structured_notes
            )
        
        result['questions_raised'] = ai_service._extract_questions_from_transcript(transcript)
        
        return Response({
            'success': True,
            'comprehensive_summary': result,
            'ai_available': ai_service.is_available()
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)