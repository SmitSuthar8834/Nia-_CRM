"""
API views for performance monitoring and alerting
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Max, Min, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, PerformanceThreshold, ConcurrentCallMetrics
)
from .services import PerformanceMonitoringService, AlertingService
from .serializers import (
    PerformanceMetricSerializer, CallBotPerformanceSerializer,
    AIProcessingPerformanceSerializer, SystemAlertSerializer,
    PerformanceThresholdSerializer, ConcurrentCallMetricsSerializer
)


class PerformanceMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for performance metrics
    """
    queryset = PerformanceMetric.objects.all()
    serializer_class = PerformanceMetricSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by time range
        hours = self.request.query_params.get('hours', 24)
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(timestamp__gte=since)
        except (ValueError, TypeError):
            pass
        
        # Filter by metric type
        metric_type = self.request.query_params.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        # Filter by metric name
        metric_name = self.request.query_params.get('metric_name')
        if metric_name:
            queryset = queryset.filter(metric_name=metric_name)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get performance metrics summary"""
        hours = int(request.query_params.get('hours', 24))
        
        performance_service = PerformanceMonitoringService()
        summary = performance_service.get_performance_summary(hours=hours)
        
        return Response(summary)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get metrics grouped by type"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        metrics_by_type = {}
        
        # Get all metric types
        metric_types = PerformanceMetric.objects.filter(
            timestamp__gte=since
        ).values_list('metric_type', flat=True).distinct()
        
        for metric_type in metric_types:
            type_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=since,
                metric_type=metric_type
            ).aggregate(
                count=Count('id'),
                avg_value=Avg('value'),
                max_value=Max('value'),
                min_value=Min('value'),
                error_count=Count('id', filter=Q(status='error'))
            )
            
            type_metrics['error_rate'] = (
                type_metrics['error_count'] / type_metrics['count'] * 100
                if type_metrics['count'] > 0 else 0
            )
            
            metrics_by_type[metric_type] = type_metrics
        
        return Response(metrics_by_type)
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """Get metrics timeline data for charts"""
        hours = int(request.query_params.get('hours', 24))
        metric_type = request.query_params.get('metric_type')
        metric_name = request.query_params.get('metric_name')
        
        if not metric_type or not metric_name:
            return Response(
                {'error': 'metric_type and metric_name parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        since = timezone.now() - timedelta(hours=hours)
        
        metrics = PerformanceMetric.objects.filter(
            timestamp__gte=since,
            metric_type=metric_type,
            metric_name=metric_name
        ).order_by('timestamp').values('timestamp', 'value', 'status')
        
        return Response(list(metrics))


class CallBotPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for call bot performance metrics
    """
    queryset = CallBotPerformance.objects.all()
    serializer_class = CallBotPerformanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by time range
        hours = self.request.query_params.get('hours', 24)
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(created_at__gte=since)
        except (ValueError, TypeError):
            pass
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get call bot performance statistics"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        queryset = self.get_queryset().filter(created_at__gte=since)
        
        stats = queryset.aggregate(
            total_sessions=Count('id'),
            successful_connections=Count('id', filter=Q(connection_success=True)),
            avg_connection_time=Avg('connection_time'),
            max_connection_time=Max('connection_time'),
            avg_audio_quality=Avg('audio_quality_score'),
            avg_transcription_accuracy=Avg('transcription_accuracy'),
            total_errors=Count('error_count'),
            avg_cpu_usage=Avg('cpu_usage_avg'),
            avg_memory_usage=Avg('memory_usage_avg')
        )
        
        # Calculate success rate
        if stats['total_sessions'] > 0:
            stats['success_rate'] = (
                stats['successful_connections'] / stats['total_sessions'] * 100
            )
        else:
            stats['success_rate'] = 0
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def top_performers(self, request):
        """Get top performing call bot sessions"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        limit = int(request.query_params.get('limit', 10))
        
        # Get sessions with highest overall scores
        top_sessions = []
        for performance in self.get_queryset().filter(created_at__gte=since)[:limit * 2]:
            score = performance.overall_score
            if score > 0:
                top_sessions.append({
                    'id': performance.id,
                    'meeting_title': performance.call_bot_session.meeting.title,
                    'platform': performance.call_bot_session.platform,
                    'overall_score': score,
                    'connection_time': performance.connection_time,
                    'audio_quality_score': performance.audio_quality_score,
                    'transcription_accuracy': performance.transcription_accuracy,
                    'created_at': performance.created_at
                })
        
        # Sort by score and limit
        top_sessions.sort(key=lambda x: x['overall_score'], reverse=True)
        return Response(top_sessions[:limit])


class AIProcessingPerformanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for AI processing performance metrics
    """
    queryset = AIProcessingPerformance.objects.all()
    serializer_class = AIProcessingPerformanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by time range
        hours = self.request.query_params.get('hours', 24)
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(timestamp__gte=since)
        except (ValueError, TypeError):
            pass
        
        # Filter by operation type
        operation_type = self.request.query_params.get('operation_type')
        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['get'])
    def by_operation(self, request):
        """Get AI performance metrics grouped by operation type"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        operation_stats = {}
        
        # Get all operation types
        operation_types = self.get_queryset().filter(
            timestamp__gte=since
        ).values_list('operation_type', flat=True).distinct()
        
        for op_type in operation_types:
            ops = self.get_queryset().filter(
                timestamp__gte=since,
                operation_type=op_type
            )
            
            stats = ops.aggregate(
                count=Count('id'),
                avg_processing_time=Avg('processing_time'),
                max_processing_time=Max('processing_time'),
                avg_confidence=Avg('confidence_score'),
                avg_processing_rate=Avg('input_size') / Avg('processing_time'),
                error_count=Count('id', filter=Q(error_occurred=True)),
                total_tokens=Count('tokens_used')
            )
            
            stats['error_rate'] = (
                stats['error_count'] / stats['count'] * 100
                if stats['count'] > 0 else 0
            )
            
            operation_stats[op_type] = stats
        
        return Response(operation_stats)
    
    @action(detail=False, methods=['get'])
    def efficiency_trends(self, request):
        """Get AI processing efficiency trends over time"""
        hours = int(request.query_params.get('hours', 24))
        operation_type = request.query_params.get('operation_type')
        
        since = timezone.now() - timedelta(hours=hours)
        
        queryset = self.get_queryset().filter(timestamp__gte=since)
        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        
        # Group by hour and calculate efficiency metrics
        trends = []
        current_time = since
        while current_time < timezone.now():
            hour_end = current_time + timedelta(hours=1)
            
            hour_ops = queryset.filter(
                timestamp__gte=current_time,
                timestamp__lt=hour_end
            )
            
            if hour_ops.exists():
                hour_stats = hour_ops.aggregate(
                    count=Count('id'),
                    avg_processing_time=Avg('processing_time'),
                    avg_confidence=Avg('confidence_score'),
                    error_count=Count('id', filter=Q(error_occurred=True))
                )
                
                hour_stats['timestamp'] = current_time
                hour_stats['error_rate'] = (
                    hour_stats['error_count'] / hour_stats['count'] * 100
                    if hour_stats['count'] > 0 else 0
                )
                
                trends.append(hour_stats)
            
            current_time = hour_end
        
        return Response(trends)


class SystemAlertViewSet(viewsets.ModelViewSet):
    """
    ViewSet for system alerts
    """
    queryset = SystemAlert.objects.all()
    serializer_class = SystemAlertSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by severity
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by alert type
        alert_type = self.request.query_params.get('alert_type')
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        # Filter by component
        component = self.request.query_params.get('component')
        if component:
            queryset = queryset.filter(component=component)
        
        return queryset.order_by('-first_occurred')
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """Acknowledge an alert"""
        alert = self.get_object()
        user_email = request.user.email if hasattr(request.user, 'email') else 'unknown'
        
        alert.acknowledge(user_email)
        
        return Response({
            'message': 'Alert acknowledged',
            'acknowledged_by': user_email,
            'acknowledged_at': alert.acknowledged_at
        })
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve an alert"""
        alert = self.get_object()
        user_email = request.user.email if hasattr(request.user, 'email') else 'unknown'
        notes = request.data.get('notes', '')
        
        alert.resolve(user_email, notes)
        
        return Response({
            'message': 'Alert resolved',
            'resolved_by': user_email,
            'resolved_at': alert.resolved_at,
            'resolution_notes': notes
        })
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get alert dashboard data"""
        # Active alerts by severity
        active_alerts = self.get_queryset().filter(is_active=True)
        
        severity_counts = {}
        for severity in ['info', 'warning', 'error', 'critical']:
            count = active_alerts.filter(severity=severity).count()
            if count > 0:
                severity_counts[severity] = count
        
        # Recent alerts (last 24 hours)
        recent_since = timezone.now() - timedelta(hours=24)
        recent_alerts = self.get_queryset().filter(
            first_occurred__gte=recent_since
        ).count()
        
        # Alert trends (last 7 days)
        trends = []
        for i in range(7):
            day_start = timezone.now() - timedelta(days=i+1)
            day_end = timezone.now() - timedelta(days=i)
            
            day_count = self.get_queryset().filter(
                first_occurred__gte=day_start,
                first_occurred__lt=day_end
            ).count()
            
            trends.append({
                'date': day_start.date(),
                'count': day_count
            })
        
        trends.reverse()  # Chronological order
        
        return Response({
            'active_alerts': active_alerts.count(),
            'severity_breakdown': severity_counts,
            'recent_alerts_24h': recent_alerts,
            'alert_trends': trends,
            'critical_alerts': active_alerts.filter(severity='critical').count(),
            'unacknowledged_alerts': active_alerts.filter(acknowledged=False).count()
        })


class PerformanceThresholdViewSet(viewsets.ModelViewSet):
    """
    ViewSet for performance thresholds configuration
    """
    queryset = PerformanceThreshold.objects.all()
    serializer_class = PerformanceThresholdSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by metric type
        metric_type = self.request.query_params.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        return queryset.order_by('metric_type', 'metric_name')


class ConcurrentCallMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for concurrent call metrics
    """
    queryset = ConcurrentCallMetrics.objects.all()
    serializer_class = ConcurrentCallMetricsSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by time range
        hours = self.request.query_params.get('hours', 24)
        try:
            hours = int(hours)
            since = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(timestamp__gte=since)
        except (ValueError, TypeError):
            pass
        
        return queryset.order_by('-timestamp')
    
    @action(detail=False, methods=['get'])
    def capacity_analysis(self, request):
        """Get concurrent call capacity analysis"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        metrics = self.get_queryset().filter(timestamp__gte=since)
        
        if not metrics.exists():
            return Response({
                'message': 'No concurrent call metrics available for the specified period'
            })
        
        analysis = metrics.aggregate(
            max_concurrent_calls=Max('active_calls'),
            avg_concurrent_calls=Avg('active_calls'),
            peak_system_load=Max('system_load'),
            avg_system_load=Avg('system_load'),
            min_available_memory=Min('available_memory'),
            avg_available_memory=Avg('available_memory'),
            max_disk_usage=Max('disk_usage'),
            avg_disk_usage=Avg('disk_usage')
        )
        
        # Capacity utilization (assuming 50 call limit)
        max_capacity = 50
        analysis['capacity_utilization'] = (
            analysis['max_concurrent_calls'] / max_capacity * 100
            if analysis['max_concurrent_calls'] else 0
        )
        
        # Performance assessment
        assessment = {
            'capacity_status': 'good',
            'recommendations': []
        }
        
        if analysis['capacity_utilization'] > 80:
            assessment['capacity_status'] = 'warning'
            assessment['recommendations'].append('Consider scaling up resources')
        
        if analysis['peak_system_load'] and analysis['peak_system_load'] > 0.8:
            assessment['capacity_status'] = 'warning'
            assessment['recommendations'].append('High system load detected')
        
        if analysis['min_available_memory'] and analysis['min_available_memory'] < 1024:  # Less than 1GB
            assessment['capacity_status'] = 'critical'
            assessment['recommendations'].append('Low memory availability')
        
        analysis['assessment'] = assessment
        
        return Response(analysis)
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """Get concurrent call timeline for charts"""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        metrics = self.get_queryset().filter(
            timestamp__gte=since
        ).values(
            'timestamp',
            'active_calls',
            'system_load',
            'available_memory',
            'avg_cpu_usage',
            'avg_memory_usage'
        ).order_by('timestamp')
        
        return Response(list(metrics))


class PerformanceMonitoringAPIView(viewsets.ViewSet):
    """
    API endpoints for performance monitoring operations
    """
    permission_classes = [IsAuthenticated]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.performance_service = PerformanceMonitoringService()
        self.alerting_service = AlertingService()
    
    @action(detail=False, methods=['post'])
    def collect_metrics(self, request):
        """Manually trigger metrics collection"""
        try:
            self.performance_service.collect_system_metrics()
            concurrent_metrics = self.performance_service.track_concurrent_calls()
            
            return Response({
                'message': 'Metrics collected successfully',
                'concurrent_calls': concurrent_metrics.active_calls if concurrent_metrics else 0,
                'timestamp': timezone.now()
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to collect metrics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def health_check(self, request):
        """Perform system health check"""
        try:
            self.alerting_service.check_system_health()
            
            # Get current health status
            active_alerts = SystemAlert.objects.filter(is_active=True).count()
            critical_alerts = SystemAlert.objects.filter(
                is_active=True, severity='critical'
            ).count()
            
            health_status = 'healthy'
            if critical_alerts > 0:
                health_status = 'critical'
            elif active_alerts > 0:
                health_status = 'warning'
            
            return Response({
                'health_status': health_status,
                'active_alerts': active_alerts,
                'critical_alerts': critical_alerts,
                'checked_at': timezone.now()
            })
        except Exception as e:
            return Response(
                {'error': f'Health check failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def system_status(self, request):
        """Get current system status"""
        try:
            import psutil
            
            # System resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Active calls
            from meetings.models import CallBotSession
            active_calls = CallBotSession.objects.filter(
                connection_status__in=['connecting', 'connected', 'transcribing']
            ).count()
            
            # Recent performance
            recent_metrics = PerformanceMetric.objects.filter(
                timestamp__gte=timezone.now() - timedelta(minutes=5)
            ).count()
            
            return Response({
                'system_resources': {
                    'cpu_usage': cpu_percent,
                    'memory_usage': memory.percent,
                    'memory_available_gb': memory.available / (1024**3),
                    'disk_usage': disk.percent,
                    'disk_free_gb': disk.free / (1024**3)
                },
                'active_calls': active_calls,
                'recent_metrics': recent_metrics,
                'timestamp': timezone.now()
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to get system status: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )