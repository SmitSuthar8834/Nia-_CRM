"""
Signal handlers for automatic performance monitoring
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from meetings.models import CallBotSession, DraftSummary
from .services import performance_monitor

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CallBotSession)
def track_call_bot_session_created(sender, instance, created, **kwargs):
    """Track when a call bot session is created"""
    if created:
        try:
            # Calculate connection time if join_time is available
            if instance.join_time:
                connection_time = (timezone.now() - instance.join_time).total_seconds()
                
                # Track the performance
                performance_monitor.track_call_bot_performance(
                    call_bot_session=instance,
                    connection_time=connection_time,
                    connection_attempts=1,
                    connection_success=instance.connection_status in ['connected', 'transcribing']
                )
                
                logger.info(f"Tracked performance for new call bot session {instance.id}")
                
        except Exception as e:
            logger.error(f"Error tracking call bot session performance: {str(e)}")


@receiver(post_save, sender=DraftSummary)
def track_ai_summary_generation(sender, instance, created, **kwargs):
    """Track AI summary generation performance"""
    if created and instance.processing_time:
        try:
            # Estimate input and output sizes
            input_size = len(instance.bot_session.raw_transcript) if instance.bot_session.raw_transcript else 0
            output_size = len(instance.ai_generated_summary)
            
            # Track AI processing performance
            performance_monitor.track_ai_processing(
                operation_type='summary_generation',
                operation_id=f"summary_{instance.id}",
                processing_time=instance.processing_time,
                input_size=input_size,
                output_size=output_size,
                confidence_score=instance.confidence_score,
                model_version='gemini-pro'  # Default model
            )
            
            logger.info(f"Tracked AI processing performance for summary {instance.id}")
            
        except Exception as e:
            logger.error(f"Error tracking AI summary performance: {str(e)}")


@receiver(post_save, sender=CallBotSession)
def update_call_bot_performance_on_status_change(sender, instance, created, **kwargs):
    """Update call bot performance when status changes"""
    if not created:
        try:
            # Check if this is a status change to disconnected or error
            if instance.connection_status in ['disconnected', 'error']:
                # Update error count and other metrics
                from .models import CallBotPerformance
                
                try:
                    performance = CallBotPerformance.objects.get(call_bot_session=instance)
                    
                    if instance.connection_status == 'error':
                        performance.error_count += 1
                    
                    # Update connection success status
                    performance.connection_success = instance.connection_status not in ['error', 'disconnected']
                    performance.save()
                    
                    logger.info(f"Updated performance metrics for call bot session {instance.id}")
                    
                except CallBotPerformance.DoesNotExist:
                    logger.warning(f"No performance record found for call bot session {instance.id}")
                    
        except Exception as e:
            logger.error(f"Error updating call bot performance: {str(e)}")