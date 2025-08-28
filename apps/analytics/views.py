"""
Analytics Views and API Endpoints
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from django.utils import timezone
from django.db.models import Q
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from .models import PerformanceMetric, UserEngagementMetric, DataQualityMetric, SystemHealthMetric, Report
from .services import AnalyticsService, ReportingService, RealTimeAnalyticsCollector
from .serializers import (
    PerformanceMetricSerializer, UserEngagementMetricSerializer, 
    DataQualityMetricSerializer, SystemHealthMetricSerializer, ReportSerializer
)
from apps.accounts.permissions import AdminOnlyPermission, ManagerOrAdminPermission

logger = logging.getLogger(__name__)


class AnalyticsPagination(PageNumberPagination):
    """Custom pagination for analytics endpoints"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@method_decorator([cache_page(300), vary_on_headers('Authorization')], name='dispatch')
class DashboardAnalyticsView(APIView):
    """Main dashboard analytics endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get dashboard analytics data"""
        try:
            # Get date range from query params
            days = int(request.GET.get('days', 7))
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Check if user should see all data or just their own
            user_filter = None
            if not request.user.groups.filter(name__in=['admin', 'sales_manager']).exists():
                user_filter = request.user
            
            analytics_service = AnalyticsService()
            
            # Gather all dashboard metrics
            dashboard_data = {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'debriefing_metrics': analytics_service.calculate_debriefing_completion_rate(
                    start_date, end_date, user_filter
                ),
                'extraction_metrics': analytics_service.calculate_data_extraction_accuracy(
                    start_date, end_date
                ),
                'meeting_metrics': analytics_service.calculate_meeting_detection_accuracy(
                    start_date, end_date
                ),
                'participant_metrics': analytics_service.calculate_participant_matching_accuracy(
                    start_date, end_date
                ),
                'crm_metrics': analytics_service.calculate_crm_sync_success_rate(
                    start_date, end_date
                ),
                'engagement_metrics': analytics_service.calculate_user_engagement_metrics(
                    start_date, end_date, user_filter
                ),
                'competitive_metrics': analytics_service.get_competitive_intelligence_insights(
                    start_date, end_date
                )
            }
            
            return Response(dashboard_data)
            
        except Exception as e:
            logger.error(f"Dashboard analytics error: {str(e)}")
            return Response(
                {'error': 'Failed to load dashboard analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PerformanceMetricsView(ListAPIView):
    """List performance metrics with filtering"""
    serializer_class = PerformanceMetricSerializer
    pagination_class = AnalyticsPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = PerformanceMetric.objects.all()
        
        # Filter by metric type
        metric_type = self.request.GET.get('metric_type')
        if metric_type:
            queryset = queryset.filter(metric_type=metric_type)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(period_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(period_end__lte=end_date)
        
        # Filter by user (if not admin/manager)
        if not self.request.user.groups.filter(name__in=['admin', 'sales_manager']).exists():
            queryset = queryset.filter(Q(user=self.request.user) | Q(user__isnull=True))
        
        return queryset.order_by('-period_start')


class UserEngagementMetricsView(ListAPIView):
    """List user engagement metrics"""
    serializer_class = UserEngagementMetricSerializer
    pagination_class = AnalyticsPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = UserEngagementMetric.objects.all()
        
        # Filter by engagement type
        engagement_type = self.request.GET.get('engagement_type')
        if engagement_type:
            queryset = queryset.filter(engagement_type=engagement_type)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Filter by user (if not admin/manager, show only own data)
        if not self.request.user.groups.filter(name__in=['admin', 'sales_manager']).exists():
            queryset = queryset.filter(user=self.request.user)
        
        return queryset.order_by('-created_at')


class DataQualityMetricsView(ListAPIView):
    """List data quality metrics"""
    serializer_class = DataQualityMetricSerializer
    pagination_class = AnalyticsPagination
    permission_classes = [ManagerOrAdminPermission]
    
    def get_queryset(self):
        queryset = DataQualityMetric.objects.all()
        
        # Filter by quality type
        quality_type = self.request.GET.get('quality_type')
        if quality_type:
            queryset = queryset.filter(quality_type=quality_type)
        
        # Filter by entity type
        entity_type = self.request.GET.get('entity_type')
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date:
            queryset = queryset.filter(measurement_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(measurement_date__lte=end_date)
        
        return queryset.order_by('-created_at')


class SystemHealthMetricsView(ListAPIView):
    """List system health metrics"""
    serializer_class = SystemHealthMetricSerializer
    pagination_class = AnalyticsPagination
    permission_classes = [ManagerOrAdminPermission]
    
    def get_queryset(self):
        queryset = SystemHealthMetric.objects.all()
        
        # Filter by health type
        health_type = self.request.GET.get('health_type')
        if health_type:
            queryset = queryset.filter(health_type=health_type)
        
        # Filter by component
        component = self.request.GET.get('component')
        if component:
            queryset = queryset.filter(component=component)
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-measured_at')


class ReportsView(ListAPIView):
    """List generated reports"""
    serializer_class = ReportSerializer
    pagination_class = AnalyticsPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Report.objects.all()
        
        # Filter by report type
        report_type = self.request.GET.get('report_type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Access control - users can see their own reports and public reports
        if not self.request.user.groups.filter(name__in=['admin', 'sales_manager']).exists():
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(is_public=True)
            )
        
        return queryset.order_by('-created_at')


class ReportDetailView(RetrieveAPIView):
    """Get detailed report data"""
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Report.objects.all()
        
        # Access control
        if not self.request.user.groups.filter(name__in=['admin', 'sales_manager']).exists():
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(is_public=True)
            )
        
        return queryset


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def generate_report(request):
    """Generate a new report"""
    try:
        report_type = request.data.get('report_type')
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')
        
        if not all([report_type, start_date_str]):
            return Response(
                {'error': 'report_type and start_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = None
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        reporting_service = ReportingService()
        
        # Generate appropriate report type
        if report_type == 'daily_summary':
            report = reporting_service.generate_daily_summary_report(start_date, request.user)
        elif report_type == 'weekly_performance':
            report = reporting_service.generate_weekly_performance_report(start_date, request.user)
        elif report_type == 'user_activity':
            target_user_id = request.data.get('target_user_id')
            if not target_user_id:
                return Response(
                    {'error': 'target_user_id is required for user_activity reports'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            target_user = get_object_or_404(User, id=target_user_id)
            
            # Check permissions
            if (not request.user.groups.filter(name__in=['admin', 'sales_manager']).exists() 
                and target_user != request.user):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if not end_date:
                end_date = start_date + timedelta(days=30)
            
            report = reporting_service.generate_user_activity_report(
                start_date, end_date, target_user
            )
        else:
            return Response(
                {'error': f'Unsupported report type: {report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        return Response(
            {'error': 'Failed to generate report'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def track_engagement(request):
    """Track user engagement event"""
    try:
        engagement_type = request.data.get('engagement_type')
        session_id = request.data.get('session_id')
        duration_seconds = request.data.get('duration_seconds')
        entity_type = request.data.get('entity_type')
        entity_id = request.data.get('entity_id')
        metadata = request.data.get('metadata', {})
        
        if not engagement_type:
            return Response(
                {'error': 'engagement_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        RealTimeAnalyticsCollector.track_user_engagement(
            user=request.user,
            engagement_type=engagement_type,
            session_id=session_id,
            duration_seconds=duration_seconds,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata
        )
        
        return Response({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Engagement tracking error: {str(e)}")
        return Response(
            {'error': 'Failed to track engagement'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([ManagerOrAdminPermission])
def export_analytics_data(request):
    """Export analytics data in various formats"""
    try:
        export_format = request.GET.get('format', 'json')
        metric_type = request.GET.get('metric_type', 'all')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Default to last 30 days if no dates provided
        if not end_date_str:
            end_date = timezone.now()
        else:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        if not start_date_str:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        
        analytics_service = AnalyticsService()
        
        # Gather export data based on metric type
        export_data = {}
        
        if metric_type in ['all', 'debriefing']:
            export_data['debriefing_metrics'] = analytics_service.calculate_debriefing_completion_rate(
                start_date, end_date
            )
        
        if metric_type in ['all', 'extraction']:
            export_data['extraction_metrics'] = analytics_service.calculate_data_extraction_accuracy(
                start_date, end_date
            )
        
        if metric_type in ['all', 'meeting']:
            export_data['meeting_metrics'] = analytics_service.calculate_meeting_detection_accuracy(
                start_date, end_date
            )
        
        if metric_type in ['all', 'participant']:
            export_data['participant_metrics'] = analytics_service.calculate_participant_matching_accuracy(
                start_date, end_date
            )
        
        if metric_type in ['all', 'crm']:
            export_data['crm_metrics'] = analytics_service.calculate_crm_sync_success_rate(
                start_date, end_date
            )
        
        if metric_type in ['all', 'engagement']:
            export_data['engagement_metrics'] = analytics_service.calculate_user_engagement_metrics(
                start_date, end_date
            )
        
        if metric_type in ['all', 'competitive']:
            export_data['competitive_metrics'] = analytics_service.get_competitive_intelligence_insights(
                start_date, end_date
            )
        
        export_data['export_info'] = {
            'generated_at': timezone.now().isoformat(),
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'metric_type': metric_type,
            'format': export_format
        }
        
        if export_format == 'json':
            response = JsonResponse(export_data)
            response['Content-Disposition'] = f'attachment; filename="analytics_export_{start_date.date()}_to_{end_date.date()}.json"'
            return response
        
        elif export_format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers and data for each metric type
            for metric_name, metric_data in export_data.items():
                if metric_name == 'export_info':
                    continue
                
                writer.writerow([f"=== {metric_name.upper()} ==="])
                
                if isinstance(metric_data, dict):
                    for key, value in metric_data.items():
                        writer.writerow([key, value])
                
                writer.writerow([])  # Empty row for separation
            
            response = HttpResponse(output.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="analytics_export_{start_date.date()}_to_{end_date.date()}.csv"'
            return response
        
        else:
            return Response(
                {'error': f'Unsupported export format: {export_format}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        logger.error(f"Analytics export error: {str(e)}")
        return Response(
            {'error': 'Failed to export analytics data'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([ManagerOrAdminPermission])
def system_health_status(request):
    """Get current system health status"""
    try:
        # Get latest health metrics for each component
        latest_metrics = SystemHealthMetric.objects.filter(
            measured_at__gte=timezone.now() - timedelta(hours=1)
        ).order_by('component', '-measured_at').distinct('component')
        
        health_status = {
            'overall_status': 'healthy',
            'components': [],
            'alerts': [],
            'last_updated': timezone.now().isoformat()
        }
        
        critical_count = 0
        warning_count = 0
        
        for metric in latest_metrics:
            component_data = {
                'component': metric.component,
                'health_type': metric.health_type,
                'value': metric.value,
                'unit': metric.unit,
                'status': metric.status,
                'measured_at': metric.measured_at.isoformat()
            }
            
            health_status['components'].append(component_data)
            
            if metric.status == 'critical':
                critical_count += 1
                health_status['alerts'].append({
                    'level': 'critical',
                    'component': metric.component,
                    'message': f"{metric.component} {metric.health_type} is critical: {metric.value} {metric.unit or ''}"
                })
            elif metric.status == 'warning':
                warning_count += 1
                health_status['alerts'].append({
                    'level': 'warning',
                    'component': metric.component,
                    'message': f"{metric.component} {metric.health_type} is warning: {metric.value} {metric.unit or ''}"
                })
        
        # Determine overall status
        if critical_count > 0:
            health_status['overall_status'] = 'critical'
        elif warning_count > 0:
            health_status['overall_status'] = 'warning'
        
        health_status['summary'] = {
            'total_components': len(health_status['components']),
            'critical_alerts': critical_count,
            'warning_alerts': warning_count
        }
        
        return Response(health_status)
        
    except Exception as e:
        logger.error(f"System health status error: {str(e)}")
        return Response(
            {'error': 'Failed to get system health status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )