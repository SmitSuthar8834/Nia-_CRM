"""
Celery tasks for AI engine batch processing and optimization
"""
import logging
from typing import Dict, List, Any, Optional
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .caching_optimization import get_optimization_service
from .models import AIInteraction, AICache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_batch_ai_requests(self, requests: List[Dict[str, Any]], job_name: str = "batch_job"):
    """
    Process multiple AI requests in batch mode
    
    Args:
        requests: List of AI request dictionaries
        job_name: Name for the batch job
    
    Returns:
        Dict with results and statistics
    """
    try:
        optimization_service = get_optimization_service()
        batch_processor = optimization_service.batch_processor
        
        # Progress callback for logging
        def progress_callback(progress: float, completed: int):
            logger.info(f"Batch job '{job_name}' progress: {progress:.1%} ({completed} completed)")
        
        # Process batch
        results = batch_processor.process_batch_requests(requests, progress_callback)
        
        # Calculate statistics
        total_requests = len(requests)
        successful_requests = sum(1 for r in results if r.get('success', False))
        failed_requests = total_requests - successful_requests
        
        logger.info(
            f"Batch job '{job_name}' completed: "
            f"{successful_requests}/{total_requests} successful, "
            f"{failed_requests} failed"
        )
        
        return {
            'job_name': job_name,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'success_rate': successful_requests / max(1, total_requests),
            'results': results,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch job '{job_name}' failed: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries  # Exponential backoff
            logger.info(f"Retrying batch job '{job_name}' in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay, exc=e)
        
        return {
            'job_name': job_name,
            'error': str(e),
            'failed_at': timezone.now().isoformat()
        }


@shared_task
def cleanup_ai_cache():
    """
    Periodic task to clean up expired and low-performance cache entries
    """
    try:
        logger.info("Starting AI cache cleanup task")
        
        # Remove expired entries
        expired_count = AICache.objects.filter(
            expires_at__lte=timezone.now()
        ).count()
        
        AICache.objects.filter(expires_at__lte=timezone.now()).delete()
        
        # Remove low-performance entries older than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        low_perf_count = AICache.objects.filter(
            created_at__lt=cutoff_date,
            hit_count__lt=2
        ).count()
        
        AICache.objects.filter(
            created_at__lt=cutoff_date,
            hit_count__lt=2
        ).delete()
        
        logger.info(
            f"AI cache cleanup completed: "
            f"Removed {expired_count} expired entries, "
            f"{low_perf_count} low-performance entries"
        )
        
        return {
            'expired_removed': expired_count,
            'low_performance_removed': low_perf_count,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI cache cleanup failed: {str(e)}")
        return {
            'error': str(e),
            'failed_at': timezone.now().isoformat()
        }


@shared_task
def generate_usage_report(days: int = 7, email_recipients: Optional[List[str]] = None):
    """
    Generate and optionally email AI usage report
    
    Args:
        days: Number of days to include in report
        email_recipients: List of email addresses to send report to
    """
    try:
        logger.info(f"Generating AI usage report for {days} days")
        
        optimization_service = get_optimization_service()
        report = optimization_service.get_optimization_report(days)
        
        # If email recipients provided, send the report
        if email_recipients:
            from django.core.mail import send_mail
            from django.conf import settings
            
            # Format report for email
            usage_metrics = report.get('usage_metrics', {})
            cache_metrics = usage_metrics.get('cache_metrics', {})
            
            email_body = f"""
AI Usage Report ({days} days)
Generated: {report.get('generated_at', 'Unknown')}

Usage Metrics:
- Total interactions: {usage_metrics.get('total_interactions', 0):,}
- Success rate: {usage_metrics.get('success_rate', 0):.2%}
- Average response time: {usage_metrics.get('average_response_time_ms', 0):.0f}ms
- Total tokens used: {usage_metrics.get('total_tokens_used', 0):,}
- Estimated cost: ${usage_metrics.get('estimated_cost_usd', 0):.4f}

Cache Performance:
- Cache hit rate: {cache_metrics.get('estimated_hit_rate', 0):.2%}
- API calls saved: {cache_metrics.get('estimated_api_calls_saved', 0):,}
- Cost savings: ${cache_metrics.get('estimated_cost_savings', 0):.4f}

Optimization Suggestions:
"""
            
            suggestions = usage_metrics.get('optimization_suggestions', [])
            for suggestion in suggestions:
                email_body += f"• {suggestion}\n"
            
            send_mail(
                subject=f'AI Usage Report ({days} days)',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=email_recipients,
                fail_silently=False,
            )
            
            logger.info(f"Usage report emailed to {len(email_recipients)} recipients")
        
        return {
            'report_generated': True,
            'report_period_days': days,
            'email_sent': bool(email_recipients),
            'email_recipients_count': len(email_recipients) if email_recipients else 0,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Usage report generation failed: {str(e)}")
        return {
            'error': str(e),
            'failed_at': timezone.now().isoformat()
        }


@shared_task
def optimize_ai_performance():
    """
    Periodic task to optimize AI performance based on usage patterns
    """
    try:
        logger.info("Starting AI performance optimization task")
        
        optimization_service = get_optimization_service()
        
        # Get current performance metrics
        report = optimization_service.get_optimization_report(7)
        usage_metrics = report.get('usage_metrics', {})
        cache_metrics = usage_metrics.get('cache_metrics', {})
        
        optimizations_applied = []
        
        # Optimize cache TTL based on hit rate
        hit_rate = cache_metrics.get('estimated_hit_rate', 0)
        if hit_rate < 0.2:
            # Low hit rate - consider reducing cache TTL to save storage
            optimizations_applied.append("Recommended reducing cache TTL due to low hit rate")
        elif hit_rate > 0.8:
            # High hit rate - consider extending cache TTL
            optimizations_applied.append("Recommended extending cache TTL due to high hit rate")
        
        # Check error patterns
        error_breakdown = usage_metrics.get('error_breakdown', {})
        error_rate = error_breakdown.get('error_rate', 0)
        
        if error_rate > 0.1:
            optimizations_applied.append("High error rate detected - review error handling")
        
        # Check for rate limiting issues
        error_types = error_breakdown.get('error_types', {})
        if error_types.get('rate_limit', 0) > 0:
            optimizations_applied.append("Rate limit errors detected - implement better request spacing")
        
        logger.info(f"AI performance optimization completed: {len(optimizations_applied)} recommendations")
        
        return {
            'optimizations_applied': optimizations_applied,
            'hit_rate': hit_rate,
            'error_rate': error_rate,
            'completed_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI performance optimization failed: {str(e)}")
        return {
            'error': str(e),
            'failed_at': timezone.now().isoformat()
        }


@shared_task
def health_check_ai_services():
    """
    Periodic health check for AI services
    """
    try:
        logger.info("Starting AI services health check")
        
        optimization_service = get_optimization_service()
        service_status = optimization_service.fallback_manager.get_service_status()
        
        is_healthy = service_status.get('ai_service_healthy', False)
        
        if not is_healthy:
            logger.warning("AI service health check failed - fallback mechanisms active")
            
            # Could trigger alerts here
            # send_alert_notification("AI service unhealthy")
        
        return {
            'service_healthy': is_healthy,
            'service_status': service_status,
            'checked_at': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AI services health check failed: {str(e)}")
        return {
            'error': str(e),
            'failed_at': timezone.now().isoformat()
        }


# Utility function to schedule batch processing
def schedule_batch_ai_processing(
    requests: List[Dict[str, Any]], 
    job_name: str = "batch_job",
    priority: str = 'normal'
) -> str:
    """
    Schedule batch AI processing task
    
    Args:
        requests: List of AI request dictionaries
        job_name: Name for the batch job
        priority: Task priority ('high', 'normal', 'low')
    
    Returns:
        Task ID
    """
    # Set task priority
    task_kwargs = {}
    if priority == 'high':
        task_kwargs['priority'] = 9
    elif priority == 'low':
        task_kwargs['priority'] = 1
    else:
        task_kwargs['priority'] = 5
    
    # Schedule the task
    task = process_batch_ai_requests.apply_async(
        args=[requests, job_name],
        **task_kwargs
    )
    
    logger.info(f"Scheduled batch AI processing task: {task.id} (job: {job_name})")
    return task.id