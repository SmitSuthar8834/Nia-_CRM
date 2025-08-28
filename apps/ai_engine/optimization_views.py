"""
API views for AI optimization and monitoring
"""
import logging
from typing import Dict, Any
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

from .caching_optimization import get_optimization_service
from .tasks import schedule_batch_ai_processing, cleanup_ai_cache, generate_usage_report

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_status(request):
    """Get current optimization status and metrics"""
    try:
        days = int(request.GET.get('days', 7))
        optimization_service = get_optimization_service()
        
        report = optimization_service.get_optimization_report(days)
        
        return Response({
            'status': 'success',
            'data': report
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting optimization status: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cache_metrics(request):
    """Get detailed cache performance metrics"""
    try:
        optimization_service = get_optimization_service()
        days = int(request.GET.get('days', 7))
        
        report = optimization_service.get_optimization_report(days)
        cache_metrics = report.get('usage_metrics', {}).get('cache_metrics', {})
        
        return Response({
            'status': 'success',
            'data': {
                'cache_metrics': cache_metrics,
                'period_days': days,
                'timestamp': report.get('generated_at')
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting cache metrics: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_cache_cleanup(request):
    """Trigger manual cache cleanup"""
    try:
        # Schedule cleanup task
        task = cleanup_ai_cache.delay()
        
        return Response({
            'status': 'success',
            'message': 'Cache cleanup scheduled',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Error triggering cache cleanup: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_batch_processing(request):
    """Schedule batch AI processing"""
    try:
        data = request.data
        requests = data.get('requests', [])
        job_name = data.get('job_name', 'api_batch_job')
        priority = data.get('priority', 'normal')
        
        if not requests:
            return Response({
                'status': 'error',
                'message': 'No requests provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate request format
        for i, req in enumerate(requests):
            if not isinstance(req, dict) or 'prompt' not in req:
                return Response({
                    'status': 'error',
                    'message': f'Invalid request format at index {i}'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Schedule batch processing
        task_id = schedule_batch_ai_processing(requests, job_name, priority)
        
        return Response({
            'status': 'success',
            'message': 'Batch processing scheduled',
            'task_id': task_id,
            'job_name': job_name,
            'request_count': len(requests)
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Error scheduling batch processing: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def service_health(request):
    """Get AI service health status"""
    try:
        optimization_service = get_optimization_service()
        service_status = optimization_service.fallback_manager.get_service_status()
        
        return Response({
            'status': 'success',
            'data': service_status
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting service health: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_report(request):
    """Generate usage report"""
    try:
        data = request.data
        days = data.get('days', 7)
        email_recipients = data.get('email_recipients', [])
        
        # Schedule report generation
        task = generate_usage_report.delay(days, email_recipients)
        
        return Response({
            'status': 'success',
            'message': 'Report generation scheduled',
            'task_id': task.id,
            'days': days,
            'email_recipients_count': len(email_recipients)
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_optimization(request):
    """Test optimization features with a sample request"""
    try:
        data = request.data
        prompt = data.get('prompt', 'Test prompt for optimization')
        use_cache = data.get('use_cache', True)
        use_fallback = data.get('use_fallback', True)
        
        optimization_service = get_optimization_service()
        
        # Test optimized response generation
        response = optimization_service.optimized_generate_response(
            prompt=prompt,
            interaction_type='test',
            use_cache=use_cache,
            use_fallback=use_fallback
        )
        
        return Response({
            'status': 'success',
            'data': {
                'response_content': response.content,
                'confidence_score': response.confidence_score,
                'cached': response.cached,
                'error': response.error,
                'optimization_features': {
                    'caching_enabled': use_cache,
                    'fallback_enabled': use_fallback,
                    'context_optimization': True,
                    'intelligent_caching': True
                }
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error testing optimization: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_suggestions(request):
    """Get optimization suggestions based on current usage patterns"""
    try:
        days = int(request.GET.get('days', 7))
        optimization_service = get_optimization_service()
        
        report = optimization_service.get_optimization_report(days)
        usage_metrics = report.get('usage_metrics', {})
        suggestions = usage_metrics.get('optimization_suggestions', [])
        
        # Add detailed analysis
        cache_metrics = usage_metrics.get('cache_metrics', {})
        error_breakdown = usage_metrics.get('error_breakdown', {})
        
        detailed_analysis = {
            'cache_performance': {
                'hit_rate': cache_metrics.get('estimated_hit_rate', 0),
                'status': 'good' if cache_metrics.get('estimated_hit_rate', 0) > 0.5 else 'needs_improvement',
                'recommendation': 'Cache performing well' if cache_metrics.get('estimated_hit_rate', 0) > 0.5 
                                else 'Consider optimizing cache strategy'
            },
            'error_analysis': {
                'error_rate': error_breakdown.get('error_rate', 0),
                'status': 'good' if error_breakdown.get('error_rate', 0) < 0.05 else 'needs_attention',
                'recommendation': 'Error rate acceptable' if error_breakdown.get('error_rate', 0) < 0.05
                                else 'Review error handling and retry logic'
            },
            'cost_optimization': {
                'api_calls_saved': cache_metrics.get('estimated_api_calls_saved', 0),
                'cost_savings': cache_metrics.get('estimated_cost_savings', 0),
                'recommendation': f"Saved ${cache_metrics.get('estimated_cost_savings', 0):.4f} through caching"
            }
        }
        
        return Response({
            'status': 'success',
            'data': {
                'suggestions': suggestions,
                'detailed_analysis': detailed_analysis,
                'period_days': days,
                'generated_at': report.get('generated_at')
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {str(e)}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Non-DRF views for simple endpoints
@csrf_exempt
@require_http_methods(["GET"])
@login_required
def quick_status(request):
    """Quick status endpoint for monitoring"""
    try:
        optimization_service = get_optimization_service()
        service_status = optimization_service.fallback_manager.get_service_status()
        
        return JsonResponse({
            'ai_service_healthy': service_status.get('ai_service_healthy', False),
            'fallback_available': service_status.get('fallback_available', False),
            'timestamp': service_status.get('timestamp')
        })
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'ai_service_healthy': False
        }, status=500)