"""
Performance monitoring services for collecting and analyzing system metrics
"""
import time
import logging
import psutil
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min
from contextlib import contextmanager

from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold, ConcurrentCallMetrics
)
from meetings.models import CallBotSession, DraftSummary

logger = logging.getLogger(__name__)


class PerformanceMonitoringService:
    """
    Main service for collecting and analyzing performance metrics
    """
    
    def __init__(self):
        self.cache = cache
        self._active_sessions = {}
        self._lock = threading.Lock()
    
    @contextmanager
    def track_performance(self, metric_type: str, metric_name: str, 
                         content_object=None, metadata: Dict = None):
        """
        Context manager for tracking performance of operations
        """
        start_time = time.time()
        start_timestamp = timezone.now()
        error_occurred = False
        error_message = ""
        
        try:
            yield
        except Exception as e:
            error_occurred = True
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            end_timestamp = timezone.now()
            duration = end_time - start_time
            
            # Record the metric
            self.record_metric(
                metric_type=metric_type,
                metric_name=metric_name,
                value=duration,
                unit='seconds',
                status='error' if error_occurred else 'success',
                content_object=content_object,
                metadata=metadata or {},
                error_message=error_message,
                start_time=start_timestamp,
                end_time=end_timestamp
            )
    
    def record_metric(self, metric_type: str, metric_name: str, value: float,
                     unit: str = 'seconds', status: str = 'success',
                     content_object=None, metadata: Dict = None,
                     error_message: str = "", start_time=None, end_time=None):
        """
        Record a performance metric
        """
        try:
            metric = PerformanceMetric.objects.create(
                metric_type=metric_type,
                metric_name=metric_name,
                value=value,
                unit=unit,
                status=status,
                content_object=content_object,
                metadata=metadata or {},
                error_message=error_message,
                start_time=start_time,
                end_time=end_time
            )
            
            # Check thresholds and create alerts if needed
            self._check_thresholds(metric)
            
            logger.debug(f"Recorded metric: {metric_name} = {value} {unit}")
            return metric
            
        except Exception as e:
            logger.error(f"Error recording metric {metric_name}: {str(e)}")
            return None
    
    def track_call_bot_performance(self, call_bot_session: CallBotSession,
                                  connection_time: float, connection_attempts: int = 1,
                                  connection_success: bool = True):
        """
        Track call bot session performance
        """
        try:
            performance, created = CallBotPerformance.objects.get_or_create(
                call_bot_session=call_bot_session,
                defaults={
                    'connection_time': connection_time,
                    'connection_attempts': connection_attempts,
                    'connection_success': connection_success,
                }
            )
            
            if not created:
                # Update existing record
                performance.connection_time = connection_time
                performance.connection_attempts = connection_attempts
                performance.connection_success = connection_success
                performance.save()
            
            # Record general metric
            self.record_metric(
                metric_type='call_bot_session',
                metric_name='connection_time',
                value=connection_time,
                status='success' if connection_success else 'error',
                content_object=call_bot_session,
                metadata={
                    'platform': call_bot_session.platform,
                    'attempts': connection_attempts
                }
            )
            
            return performance
            
        except Exception as e:
            logger.error(f"Error tracking call bot performance: {str(e)}")
            return None
    
    def update_call_bot_audio_metrics(self, call_bot_session: CallBotSession,
                                     audio_quality_score: float = None,
                                     audio_dropouts: int = 0,
                                     audio_latency: float = None):
        """
        Update audio quality metrics for call bot session
        """
        try:
            performance = CallBotPerformance.objects.get(call_bot_session=call_bot_session)
            
            if audio_quality_score is not None:
                performance.audio_quality_score = audio_quality_score
            if audio_dropouts > 0:
                performance.audio_dropouts += audio_dropouts
            if audio_latency is not None:
                performance.audio_latency = audio_latency
            
            performance.save()
            
            # Record metrics
            if audio_quality_score is not None:
                self.record_metric(
                    metric_type='call_bot_session',
                    metric_name='audio_quality',
                    value=audio_quality_score,
                    unit='score',
                    content_object=call_bot_session
                )
            
            return performance
            
        except CallBotPerformance.DoesNotExist:
            logger.warning(f"No performance record found for call bot session {call_bot_session.id}")
            return None
        except Exception as e:
            logger.error(f"Error updating audio metrics: {str(e)}")
            return None
    
    def track_ai_processing(self, operation_type: str, operation_id: str,
                           processing_time: float, input_size: int, output_size: int,
                           confidence_score: float = None, tokens_used: int = None,
                           error_occurred: bool = False, error_type: str = "",
                           model_version: str = "", parameters: Dict = None):
        """
        Track AI processing performance
        """
        try:
            ai_performance = AIProcessingPerformance.objects.create(
                operation_type=operation_type,
                operation_id=operation_id,
                processing_time=processing_time,
                input_size=input_size,
                output_size=output_size,
                confidence_score=confidence_score,
                tokens_used=tokens_used,
                error_occurred=error_occurred,
                error_type=error_type,
                model_version=model_version,
                parameters=parameters or {}
            )
            
            # Record general metric
            self.record_metric(
                metric_type='ai_processing',
                metric_name=f'{operation_type}_processing_time',
                value=processing_time,
                status='error' if error_occurred else 'success',
                metadata={
                    'operation_id': operation_id,
                    'input_size': input_size,
                    'output_size': output_size,
                    'confidence_score': confidence_score,
                    'model_version': model_version
                }
            )
            
            return ai_performance
            
        except Exception as e:
            logger.error(f"Error tracking AI processing: {str(e)}")
            return None
    
    def collect_system_metrics(self):
        """
        Collect current system resource metrics
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric(
                metric_type='system_resource',
                metric_name='cpu_usage',
                value=cpu_percent,
                unit='percent'
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric(
                metric_type='system_resource',
                metric_name='memory_usage',
                value=memory.percent,
                unit='percent'
            )
            
            self.record_metric(
                metric_type='system_resource',
                metric_name='memory_available',
                value=memory.available / (1024 * 1024),  # MB
                unit='MB'
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.record_metric(
                metric_type='system_resource',
                metric_name='disk_usage',
                value=disk.percent,
                unit='percent'
            )
            
            # Network I/O
            network = psutil.net_io_counters()
            self.record_metric(
                metric_type='system_resource',
                metric_name='network_bytes_sent',
                value=network.bytes_sent,
                unit='bytes'
            )
            
            self.record_metric(
                metric_type='system_resource',
                metric_name='network_bytes_recv',
                value=network.bytes_recv,
                unit='bytes'
            )
            
            logger.debug("Collected system metrics")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
    
    def track_concurrent_calls(self):
        """
        Track concurrent call metrics
        """
        try:
            # Get active call bot sessions
            active_sessions = CallBotSession.objects.filter(
                connection_status__in=['connecting', 'connected', 'transcribing']
            )
            
            active_count = active_sessions.count()
            
            # Get performance metrics for active sessions
            performances = CallBotPerformance.objects.filter(
                call_bot_session__in=active_sessions
            )
            
            avg_connection_time = performances.aggregate(
                avg=Avg('connection_time')
            )['avg']
            
            avg_cpu = performances.aggregate(
                avg=Avg('cpu_usage_avg')
            )['avg']
            
            avg_memory = performances.aggregate(
                avg=Avg('memory_usage_avg')
            )['avg']
            
            # System metrics
            system_load = psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None
            available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
            disk_usage = psutil.disk_usage('/').percent
            
            # Create concurrent call metrics record
            metrics = ConcurrentCallMetrics.objects.create(
                active_calls=active_count,
                max_concurrent_calls=active_count,  # Will be updated by aggregation
                avg_connection_time=avg_connection_time,
                avg_cpu_usage=avg_cpu,
                avg_memory_usage=avg_memory,
                system_load=system_load,
                available_memory=available_memory,
                disk_usage=disk_usage
            )
            
            # Record general metric
            self.record_metric(
                metric_type='system_resource',
                metric_name='concurrent_calls',
                value=active_count,
                unit='count'
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error tracking concurrent calls: {str(e)}")
            return None
    
    def _check_thresholds(self, metric: PerformanceMetric):
        """
        Check if metric exceeds configured thresholds and create alerts
        """
        try:
            thresholds = PerformanceThreshold.objects.filter(
                metric_type=metric.metric_type,
                metric_name=metric.metric_name,
                is_active=True
            )
            
            for threshold in thresholds:
                severity = self._evaluate_threshold(metric.value, threshold)
                if severity:
                    self._create_alert(metric, threshold, severity)
                    
        except Exception as e:
            logger.error(f"Error checking thresholds: {str(e)}")
    
    def _evaluate_threshold(self, value: float, threshold: PerformanceThreshold) -> Optional[str]:
        """
        Evaluate if value exceeds threshold and return severity level
        """
        if threshold.comparison_operator == '>':
            if threshold.critical_threshold and value > threshold.critical_threshold:
                return 'critical'
            elif threshold.error_threshold and value > threshold.error_threshold:
                return 'error'
            elif threshold.warning_threshold and value > threshold.warning_threshold:
                return 'warning'
        elif threshold.comparison_operator == '<':
            if threshold.critical_threshold and value < threshold.critical_threshold:
                return 'critical'
            elif threshold.error_threshold and value < threshold.error_threshold:
                return 'error'
            elif threshold.warning_threshold and value < threshold.warning_threshold:
                return 'warning'
        
        return None
    
    def _create_alert(self, metric: PerformanceMetric, threshold: PerformanceThreshold, severity: str):
        """
        Create system alert for threshold violation
        """
        try:
            # Check if similar alert already exists and is active
            existing_alert = SystemAlert.objects.filter(
                alert_type='performance_degradation',
                component=f"{threshold.metric_type}.{threshold.metric_name}",
                is_active=True
            ).first()
            
            if existing_alert:
                # Update existing alert
                existing_alert.last_occurred = timezone.now()
                existing_alert.occurrence_count += 1
                existing_alert.current_value = metric.value
                existing_alert.save()
            else:
                # Create new alert
                SystemAlert.objects.create(
                    alert_type='performance_degradation',
                    severity=severity,
                    title=f"Performance threshold exceeded: {threshold.metric_name}",
                    description=f"Metric {threshold.metric_name} value {metric.value} {metric.unit} "
                               f"exceeds {severity} threshold {getattr(threshold, f'{severity}_threshold')}",
                    component=f"{threshold.metric_type}.{threshold.metric_name}",
                    metric_threshold=getattr(threshold, f'{severity}_threshold'),
                    current_value=metric.value
                )
            
        except Exception as e:
            logger.error(f"Error creating alert: {str(e)}")
    
    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance summary for the last N hours
        """
        try:
            since = timezone.now() - timedelta(hours=hours)
            
            # Overall metrics
            total_metrics = PerformanceMetric.objects.filter(timestamp__gte=since).count()
            error_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=since, status='error'
            ).count()
            
            error_rate = (error_metrics / total_metrics * 100) if total_metrics > 0 else 0
            
            # Call bot performance
            call_bot_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=since,
                metric_type='call_bot_session'
            ).aggregate(
                avg_connection_time=Avg('value'),
                max_connection_time=Max('value'),
                min_connection_time=Min('value'),
                total_sessions=Count('id')
            )
            
            # AI processing performance
            ai_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=since,
                metric_type='ai_processing'
            ).aggregate(
                avg_processing_time=Avg('value'),
                max_processing_time=Max('value'),
                total_operations=Count('id')
            )
            
            # Active alerts
            active_alerts = SystemAlert.objects.filter(is_active=True).count()
            critical_alerts = SystemAlert.objects.filter(
                is_active=True, severity='critical'
            ).count()
            
            # Concurrent calls
            max_concurrent = ConcurrentCallMetrics.objects.filter(
                timestamp__gte=since
            ).aggregate(max_calls=Max('active_calls'))['max_calls'] or 0
            
            return {
                'period_hours': hours,
                'total_metrics': total_metrics,
                'error_rate': round(error_rate, 2),
                'call_bot_performance': call_bot_metrics,
                'ai_performance': ai_metrics,
                'active_alerts': active_alerts,
                'critical_alerts': critical_alerts,
                'max_concurrent_calls': max_concurrent,
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {str(e)}")
            return {}


class AlertingService:
    """
    Service for managing system alerts and notifications
    """
    
    def __init__(self):
        self.monitoring_service = PerformanceMonitoringService()
    
    def create_alert(self, alert_type: str, severity: str, title: str,
                    description: str, component: str = "",
                    metric_threshold: float = None, current_value: float = None):
        """
        Create a new system alert
        """
        try:
            alert = SystemAlert.objects.create(
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                component=component,
                metric_threshold=metric_threshold,
                current_value=current_value
            )
            
            logger.info(f"Created {severity} alert: {title}")
            return alert
            
        except Exception as e:
            logger.error(f"Error creating alert: {str(e)}")
            return None
    
    def check_system_health(self):
        """
        Perform system health checks and create alerts if needed
        """
        try:
            # Check high error rates
            self._check_error_rates()
            
            # Check resource usage
            self._check_resource_usage()
            
            # Check concurrent call capacity
            self._check_concurrent_capacity()
            
            # Check AI processing performance
            self._check_ai_performance()
            
        except Exception as e:
            logger.error(f"Error during system health check: {str(e)}")
    
    def _check_error_rates(self):
        """
        Check for high error rates in the last hour
        """
        since = timezone.now() - timedelta(hours=1)
        
        total_metrics = PerformanceMetric.objects.filter(timestamp__gte=since).count()
        error_metrics = PerformanceMetric.objects.filter(
            timestamp__gte=since, status='error'
        ).count()
        
        if total_metrics > 0:
            error_rate = (error_metrics / total_metrics) * 100
            
            if error_rate > 20:  # 20% error rate threshold
                self.create_alert(
                    alert_type='high_error_rate',
                    severity='critical' if error_rate > 50 else 'error',
                    title=f"High error rate detected: {error_rate:.1f}%",
                    description=f"System error rate is {error_rate:.1f}% in the last hour "
                               f"({error_metrics} errors out of {total_metrics} operations)",
                    component='system',
                    metric_threshold=20.0,
                    current_value=error_rate
                )
    
    def _check_resource_usage(self):
        """
        Check system resource usage
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # CPU usage alert
            if cpu_percent > 90:
                self.create_alert(
                    alert_type='resource_exhaustion',
                    severity='critical',
                    title=f"High CPU usage: {cpu_percent}%",
                    description=f"CPU usage is at {cpu_percent}%, which may impact performance",
                    component='cpu',
                    metric_threshold=90.0,
                    current_value=cpu_percent
                )
            
            # Memory usage alert
            if memory.percent > 85:
                self.create_alert(
                    alert_type='resource_exhaustion',
                    severity='error' if memory.percent > 95 else 'warning',
                    title=f"High memory usage: {memory.percent}%",
                    description=f"Memory usage is at {memory.percent}%, available: {memory.available / (1024**3):.1f}GB",
                    component='memory',
                    metric_threshold=85.0,
                    current_value=memory.percent
                )
            
            # Disk usage alert
            if disk.percent > 90:
                self.create_alert(
                    alert_type='resource_exhaustion',
                    severity='critical' if disk.percent > 95 else 'error',
                    title=f"High disk usage: {disk.percent}%",
                    description=f"Disk usage is at {disk.percent}%, free space: {disk.free / (1024**3):.1f}GB",
                    component='disk',
                    metric_threshold=90.0,
                    current_value=disk.percent
                )
                
        except Exception as e:
            logger.error(f"Error checking resource usage: {str(e)}")
    
    def _check_concurrent_capacity(self):
        """
        Check concurrent call handling capacity
        """
        try:
            active_calls = CallBotSession.objects.filter(
                connection_status__in=['connecting', 'connected', 'transcribing']
            ).count()
            
            # Alert if approaching capacity limit (50 concurrent calls)
            if active_calls > 40:
                self.create_alert(
                    alert_type='resource_exhaustion',
                    severity='warning' if active_calls < 45 else 'error',
                    title=f"High concurrent call load: {active_calls} active calls",
                    description=f"System is handling {active_calls} concurrent calls, "
                               f"approaching capacity limit of 50",
                    component='call_bot',
                    metric_threshold=40.0,
                    current_value=float(active_calls)
                )
                
        except Exception as e:
            logger.error(f"Error checking concurrent capacity: {str(e)}")
    
    def _check_ai_performance(self):
        """
        Check AI processing performance
        """
        try:
            since = timezone.now() - timedelta(hours=1)
            
            # Check average AI processing time
            avg_processing_time = AIProcessingPerformance.objects.filter(
                timestamp__gte=since
            ).aggregate(avg=Avg('processing_time'))['avg']
            
            if avg_processing_time and avg_processing_time > 30:  # 30 seconds threshold
                self.create_alert(
                    alert_type='performance_degradation',
                    severity='warning' if avg_processing_time < 60 else 'error',
                    title=f"Slow AI processing: {avg_processing_time:.1f}s average",
                    description=f"AI processing is taking an average of {avg_processing_time:.1f} seconds, "
                               f"which exceeds the 30-second target",
                    component='ai_processing',
                    metric_threshold=30.0,
                    current_value=avg_processing_time
                )
                
        except Exception as e:
            logger.error(f"Error checking AI performance: {str(e)}")


# Global instance
performance_monitor = PerformanceMonitoringService()
alerting_service = AlertingService()