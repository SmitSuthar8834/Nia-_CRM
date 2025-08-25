"""
AI Engine API Views
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from .services import (
    get_question_generation_service,
    get_data_extraction_service,
    get_ai_health_service,
    get_prompt_template_service,
    AIServiceError
)
from .models import AIInteraction, AIPromptTemplate


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_questions(request):
    """Generate debriefing questions for a meeting"""
    try:
        meeting_context = request.data.get('meeting_context', {})
        question_count = request.data.get('question_count', 5)
        
        if not meeting_context:
            return Response(
                {'error': 'meeting_context is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_question_generation_service().generate_questions(
            meeting_context=meeting_context,
            user=request.user,
            question_count=question_count
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except AIServiceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_follow_up(request):
    """Generate follow-up question based on user response"""
    try:
        original_question = request.data.get('original_question')
        user_response = request.data.get('user_response')
        meeting_context = request.data.get('meeting_context', {})
        
        if not all([original_question, user_response]):
            return Response(
                {'error': 'original_question and user_response are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_question_generation_service().generate_follow_up_question(
            original_question=original_question,
            user_response=user_response,
            meeting_context=meeting_context,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except AIServiceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extract_data(request):
    """Extract structured data from conversation text"""
    try:
        conversation_text = request.data.get('conversation_text')
        meeting_context = request.data.get('meeting_context', {})
        
        if not conversation_text:
            return Response(
                {'error': 'conversation_text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_data_extraction_service().extract_meeting_data(
            conversation_text=conversation_text,
            meeting_context=meeting_context,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except AIServiceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extract_specific_data(request):
    """Extract specific type of data from conversation text"""
    try:
        conversation_text = request.data.get('conversation_text')
        data_type = request.data.get('data_type')
        meeting_context = request.data.get('meeting_context', {})
        
        if not conversation_text:
            return Response(
                {'error': 'conversation_text is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not data_type:
            return Response(
                {'error': 'data_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_types = ['contacts', 'deal_information', 'competitive_intelligence', 'action_items', 'meeting_outcome']
        if data_type not in valid_types:
            return Response(
                {'error': f'data_type must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_data_extraction_service().extract_specific_data_type(
            conversation_text=conversation_text,
            data_type=data_type,
            meeting_context=meeting_context,
            user=request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
        
    except AIServiceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_status(request):
    """Get AI system health status"""
    try:
        health_data = get_ai_health_service().get_health_status()
        return Response(health_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to get health status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_templates(request):
    """List available prompt templates"""
    try:
        template_type = request.GET.get('type')
        context = request.GET.get('context')
        
        templates = AIPromptTemplate.objects.filter(is_active=True)
        
        if template_type:
            templates = templates.filter(template_type=template_type)
        
        if context:
            templates = templates.filter(context=context)
        
        templates_data = []
        for template in templates:
            templates_data.append({
                'id': str(template.id),
                'name': template.name,
                'template_type': template.template_type,
                'context': template.context,
                'usage_count': template.usage_count,
                'success_rate': template.success_rate,
                'created_at': template.created_at.isoformat()
            })
        
        return Response({
            'templates': templates_data,
            'count': len(templates_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to list templates'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_template(request):
    """Create a new prompt template"""
    try:
        required_fields = ['name', 'template_type', 'prompt_template']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        template = get_prompt_template_service().create_template(
            name=request.data['name'],
            template_type=request.data['template_type'],
            prompt_template=request.data['prompt_template'],
            context=request.data.get('context', 'general'),
            system_prompt=request.data.get('system_prompt'),
            temperature=request.data.get('temperature', 0.7),
            max_tokens=request.data.get('max_tokens', 1000),
            user=request.user
        )
        
        return Response({
            'id': str(template.id),
            'name': template.name,
            'template_type': template.template_type,
            'context': template.context,
            'created_at': template.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except AIServiceError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Failed to create template'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def interaction_history(request):
    """Get user's AI interaction history"""
    try:
        interactions = AIInteraction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]  # Last 50 interactions
        
        history_data = []
        for interaction in interactions:
            history_data.append({
                'id': str(interaction.id),
                'interaction_type': interaction.interaction_type,
                'status': interaction.status,
                'confidence_score': interaction.confidence_score,
                'response_time_ms': interaction.response_time_ms,
                'created_at': interaction.created_at.isoformat(),
                'completed_at': interaction.completed_at.isoformat() if interaction.completed_at else None
            })
        
        return Response({
            'interactions': history_data,
            'count': len(history_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to get interaction history'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )