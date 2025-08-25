"""
Celery tasks for calendar integration
"""
import logging
from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from .services import CalendarIntegrationHub
from .models import CalendarSyncStatus

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_user_calendars_task(self, user_id, provider_names=None):
    """
    Sync calendars for a specific user
    """
    try:
        user = User.objects.get(id=user_id)
        integration_hub = CalendarIntegrationHub()
        
        # Run sync
        import asyncio
        sync_results = asyncio.run(
            integration_hub.sync_user_calendars(user, provider_names)
        )
        
        logger.info(f"Calendar sync completed for user {user_id}: {sync_results}")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'sync_results': sync_results
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for calendar sync")
        return {
            'status': 'error',
            'user_id': user_id,
            'error': 'User not found'
        }
    except Exception as e:
        logger.error(f"Error syncing calendars for user {user_id}: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            'status': 'error',
            'user_id': user_id,
            'error': str(e)
        }


@shared_task(bind=True, max_retries=3)
def detect_meetings_for_user_task(self, user_id):
    """
    Run meeting detection for a specific user
    """
    try:
        user = User.objects.get(id=user_id)
        integration_hub = CalendarIntegrationHub()
        
        # Run meeting detection
        import asyncio
        asyncio.run(integration_hub.process_meetings_for_user(user))
        
        # Count newly detected meetings
        from apps.meetings.models import Meeting
        recent_meetings = Meeting.objects.filter(
            organizer=user,
            created_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        logger.info(f"Meeting detection completed for user {user_id}: {recent_meetings} meetings detected")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'meetings_detected': recent_meetings
        }
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for meeting detection")
        return {
            'status': 'error',
            'user_id': user_id,
            'error': 'User not found'
        }
    except Exception as e:
        logger.error(f"Error detecting meetings for user {user_id}: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            'status': 'error',
            'user_id': user_id,
            'error': str(e)
        }


@shared_task
def sync_all_user_calendars():
    """
    Sync calendars for all active users
    """
    active_users = User.objects.filter(is_active=True)
    
    results = []
    for user in active_users:
        # Queue individual sync tasks
        task_result = sync_user_calendars_task.delay(user.id)
        results.append({
            'user_id': user.id,
            'task_id': task_result.id
        })
    
    logger.info(f"Queued calendar sync for {len(results)} users")
    
    return {
        'status': 'success',
        'users_queued': len(results),
        'task_results': results
    }


@shared_task
def cleanup_old_calendar_events():
    """
    Clean up old calendar events to prevent database bloat
    """
    from .models import CalendarEvent
    
    # Delete events older than 6 months
    cutoff_date = timezone.now() - timedelta(days=180)
    
    old_events = CalendarEvent.objects.filter(
        start_time__lt=cutoff_date,
        meeting_created=False  # Don't delete events that created meetings
    )
    
    deleted_count = old_events.count()
    old_events.delete()
    
    logger.info(f"Cleaned up {deleted_count} old calendar events")
    
    return {
        'status': 'success',
        'deleted_events': deleted_count
    }


@shared_task
def handle_calendar_webhook_task(provider_name, webhook_data):
    """
    Handle calendar webhook notifications asynchronously
    """
    try:
        integration_hub = CalendarIntegrationHub()
        
        import asyncio
        asyncio.run(
            integration_hub.handle_calendar_webhook(provider_name, webhook_data)
        )
        
        logger.info(f"Processed webhook for {provider_name}")
        
        return {
            'status': 'success',
            'provider': provider_name
        }
        
    except Exception as e:
        logger.error(f"Error handling webhook for {provider_name}: {str(e)}")
        return {
            'status': 'error',
            'provider': provider_name,
            'error': str(e)
        }


@shared_task
def monitor_sync_failures():
    """
    Monitor and report calendar sync failures
    """
    # Find sync statuses with recent failures
    recent_failures = CalendarSyncStatus.objects.filter(
        status='error',
        last_sync_end__gte=timezone.now() - timedelta(hours=24),
        error_count__gte=3  # Multiple failures
    )
    
    failure_summary = {}
    for sync_status in recent_failures:
        provider = sync_status.provider
        if provider not in failure_summary:
            failure_summary[provider] = {
                'count': 0,
                'users': [],
                'common_errors': {}
            }
        
        failure_summary[provider]['count'] += 1
        failure_summary[provider]['users'].append(sync_status.user.username)
        
        error = sync_status.error_message or 'Unknown error'
        if error in failure_summary[provider]['common_errors']:
            failure_summary[provider]['common_errors'][error] += 1
        else:
            failure_summary[provider]['common_errors'][error] = 1
    
    if failure_summary:
        logger.warning(f"Calendar sync failures detected: {failure_summary}")
        
        # Here you could send notifications to administrators
        # send_admin_notification('Calendar Sync Failures', failure_summary)
    
    return {
        'status': 'success',
        'failure_summary': failure_summary
    }


@shared_task
def refresh_calendar_tokens():
    """
    Refresh expired calendar access tokens
    """
    from apps.accounts.models import UserProfile
    
    # Find users with calendar integrations
    profiles_with_calendars = UserProfile.objects.exclude(
        calendar_integrations__isnull=True
    ).exclude(
        calendar_integrations={}
    )
    
    refreshed_count = 0
    failed_count = 0
    
    integration_hub = CalendarIntegrationHub()
    
    for profile in profiles_with_calendars:
        user = profile.user
        
        for provider_name in profile.calendar_integrations.keys():
            try:
                provider = integration_hub.get_provider(provider_name)
                
                # Check if token needs refresh
                import asyncio
                token_refreshed = asyncio.run(provider.refresh_access_token(user))
                
                if token_refreshed:
                    refreshed_count += 1
                    logger.info(f"Refreshed {provider_name} token for user {user.id}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to refresh {provider_name} token for user {user.id}: {str(e)}")
    
    return {
        'status': 'success',
        'tokens_refreshed': refreshed_count,
        'refresh_failures': failed_count
    }


@shared_task
def generate_calendar_sync_report():
    """
    Generate a summary report of calendar synchronization activity
    """
    from django.db.models import Count, Avg
    
    # Get sync statistics
    sync_stats = CalendarSyncStatus.objects.aggregate(
        total_syncs=Count('id'),
        successful_syncs=Count('id', filter=models.Q(status='success')),
        failed_syncs=Count('id', filter=models.Q(status='error')),
        avg_events_processed=Avg('events_processed')
    )
    
    # Get provider breakdown
    provider_stats = CalendarSyncStatus.objects.values('provider').annotate(
        sync_count=Count('id'),
        success_count=Count('id', filter=models.Q(status='success')),
        avg_events=Avg('events_processed')
    )
    
    # Get recent activity (last 24 hours)
    recent_activity = CalendarSyncStatus.objects.filter(
        last_sync_end__gte=timezone.now() - timedelta(hours=24)
    ).aggregate(
        recent_syncs=Count('id'),
        recent_events=models.Sum('events_processed')
    )
    
    report = {
        'generated_at': timezone.now().isoformat(),
        'overall_stats': sync_stats,
        'provider_breakdown': list(provider_stats),
        'recent_activity': recent_activity
    }
    
    logger.info(f"Generated calendar sync report: {report}")
    
    return report