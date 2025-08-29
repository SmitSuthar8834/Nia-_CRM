"""
Management command for generating performance reports
"""
import json
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg, Count, Max, Min, Q

from performance_monitoring.models import (
    PerformanceMetric, CallBotPerformance, AIProcessingPerformance,
    SystemAlert, ConcurrentCallMetrics
)
from performance_monitoring.services import PerformanceMonitoringService


class Command(BaseCommand):
    help = 'Generate performance reports and analytics'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Report period in hours (default: 24)'
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json', 'csv'],
            default='text',
            help='Output format (default: text)'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (optional)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Include detailed metrics breakdown'
        )
        parser.add_argument(
            '--alerts-only',
            action='store_true',
            help='Show only alert information'
        )
        parser.add_argument(
            '--call-bot-only',
            action='store_true',
            help='Show only call bot performance'
        )
        parser.add_argument(
            '--ai-only',
            action='store_true',
            help='Show only AI processing performance'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        output_format = options['format']
        output_file = options['output']
        detailed = options['detailed']
        alerts_only = options['alerts_only']
        call_bot_only = options['call_bot_only']
        ai_only = options['ai_only']
        
        since = timezone.now() - timedelta(hours=hours)
        
        try:
            if alerts_only:
                report_data = self.generate_alerts_report(since)
            elif call_bot_only:
                report_data = self.generate_call_bot_report(since, detailed)
            elif ai_only:
                report_data = self.generate_ai_performance_report(since, detailed)
            else:
                report_data = self.generate_comprehensive_report(since, detailed)
            
            # Format and output report
            if output_format == 'json':
                output = json.dumps(report_data, indent=2, default=str)
            elif output_format == 'csv':
                output = self.format_as_csv(report_data)
            else:
                output = self.format_as_text(report_data)
            
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(output)
                self.stdout.write(
                    self.style.SUCCESS(f'Report saved to {output_file}')
                )
            else:
                self.stdout.write(output)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error generating report: {str(e)}')
            )
            raise
    
    def generate_comprehensive_report(self, since, detailed=False):
        """Generate comprehensive performance report"""
        performance_service = PerformanceMonitoringService()
        
        # Get overall summary
        summary = performance_service.get_performance_summary(
            hours=(timezone.now() - since).total_seconds() / 3600
        )
        
        # Get detailed metrics if requested
        detailed_data = {}
        if detailed:
            detailed_data = {
                'call_bot_details': self.get_call_bot_details(since),
                'ai_processing_details': self.get_ai_processing_details(since),
                'system_resource_details': self.get_system_resource_details(since),
                'alert_details': self.get_alert_details(since)
            }
        
        return {
            'report_type': 'comprehensive',
            'period': {
                'start': since,
                'end': timezone.now(),
                'hours': (timezone.now() - since).total_seconds() / 3600
            },
            'summary': summary,
            'detailed_data': detailed_data,
            'generated_at': timezone.now()
        }
    
    def generate_call_bot_report(self, since, detailed=False):
        """Generate call bot performance report"""
        call_bot_metrics = PerformanceMetric.objects.filter(
            timestamp__gte=since,
            metric_type='call_bot_session'
        )
        
        performance_records = CallBotPerformance.objects.filter(
            created_at__gte=since
        )
        
        # Basic statistics
        total_sessions = performance_records.count()
        successful_connections = performance_records.filter(connection_success=True).count()
        
        connection_stats = performance_records.aggregate(
            avg_connection_time=Avg('connection_time'),
            max_connection_time=Max('connection_time'),
            min_connection_time=Min('connection_time')
        )
        
        audio_stats = performance_records.exclude(
            audio_quality_score__isnull=True
        ).aggregate(
            avg_audio_quality=Avg('audio_quality_score'),
            avg_audio_latency=Avg('audio_latency'),
            total_dropouts=Count('audio_dropouts')
        )
        
        transcription_stats = performance_records.exclude(
            transcription_accuracy__isnull=True
        ).aggregate(
            avg_transcription_accuracy=Avg('transcription_accuracy'),
            avg_transcription_latency=Avg('transcription_latency')
        )
        
        report_data = {
            'report_type': 'call_bot_performance',
            'period': {
                'start': since,
                'end': timezone.now(),
                'hours': (timezone.now() - since).total_seconds() / 3600
            },
            'summary': {
                'total_sessions': total_sessions,
                'successful_connections': successful_connections,
                'success_rate': (successful_connections / total_sessions * 100) if total_sessions > 0 else 0,
                'connection_stats': connection_stats,
                'audio_stats': audio_stats,
                'transcription_stats': transcription_stats
            }
        }
        
        if detailed:
            report_data['detailed_sessions'] = list(
                performance_records.values(
                    'call_bot_session__meeting__title',
                    'call_bot_session__platform',
                    'connection_time',
                    'connection_success',
                    'audio_quality_score',
                    'transcription_accuracy',
                    'error_count',
                    'created_at'
                )
            )
        
        return report_data
    
    def generate_ai_performance_report(self, since, detailed=False):
        """Generate AI processing performance report"""
        ai_records = AIProcessingPerformance.objects.filter(
            timestamp__gte=since
        )
        
        # Overall statistics
        total_operations = ai_records.count()
        successful_operations = ai_records.filter(error_occurred=False).count()
        
        processing_stats = ai_records.aggregate(
            avg_processing_time=Avg('processing_time'),
            max_processing_time=Max('processing_time'),
            min_processing_time=Min('processing_time'),
            avg_confidence=Avg('confidence_score'),
            total_tokens=Count('tokens_used')
        )
        
        # By operation type
        operation_breakdown = {}
        for op_type in ['transcription', 'summary_generation', 'action_item_extraction', 'crm_suggestion']:
            ops = ai_records.filter(operation_type=op_type)
            if ops.exists():
                operation_breakdown[op_type] = {
                    'count': ops.count(),
                    'avg_processing_time': ops.aggregate(avg=Avg('processing_time'))['avg'],
                    'avg_confidence': ops.aggregate(avg=Avg('confidence_score'))['avg'],
                    'error_rate': ops.filter(error_occurred=True).count() / ops.count() * 100
                }
        
        report_data = {
            'report_type': 'ai_performance',
            'period': {
                'start': since,
                'end': timezone.now(),
                'hours': (timezone.now() - since).total_seconds() / 3600
            },
            'summary': {
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'success_rate': (successful_operations / total_operations * 100) if total_operations > 0 else 0,
                'processing_stats': processing_stats,
                'operation_breakdown': operation_breakdown
            }
        }
        
        if detailed:
            report_data['detailed_operations'] = list(
                ai_records.values(
                    'operation_type',
                    'operation_id',
                    'processing_time',
                    'input_size',
                    'output_size',
                    'confidence_score',
                    'error_occurred',
                    'timestamp'
                )
            )
        
        return report_data
    
    def generate_alerts_report(self, since):
        """Generate alerts report"""
        alerts = SystemAlert.objects.filter(
            first_occurred__gte=since
        )
        
        # Alert statistics
        total_alerts = alerts.count()
        active_alerts = alerts.filter(is_active=True).count()
        resolved_alerts = alerts.filter(resolved=True).count()
        
        # By severity
        severity_breakdown = {}
        for severity in ['info', 'warning', 'error', 'critical']:
            count = alerts.filter(severity=severity).count()
            if count > 0:
                severity_breakdown[severity] = count
        
        # By alert type
        type_breakdown = {}
        for alert_type in ['performance_degradation', 'high_error_rate', 'system_failure', 'resource_exhaustion']:
            count = alerts.filter(alert_type=alert_type).count()
            if count > 0:
                type_breakdown[alert_type] = count
        
        # Recent alerts
        recent_alerts = list(
            alerts.order_by('-first_occurred')[:10].values(
                'alert_type',
                'severity',
                'title',
                'component',
                'is_active',
                'first_occurred',
                'occurrence_count'
            )
        )
        
        return {
            'report_type': 'alerts',
            'period': {
                'start': since,
                'end': timezone.now(),
                'hours': (timezone.now() - since).total_seconds() / 3600
            },
            'summary': {
                'total_alerts': total_alerts,
                'active_alerts': active_alerts,
                'resolved_alerts': resolved_alerts,
                'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0,
                'severity_breakdown': severity_breakdown,
                'type_breakdown': type_breakdown
            },
            'recent_alerts': recent_alerts
        }
    
    def get_call_bot_details(self, since):
        """Get detailed call bot metrics"""
        return {
            'connection_times': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='call_bot_session',
                    metric_name='connection_time'
                ).values('value', 'timestamp', 'status')
            ),
            'audio_quality': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='call_bot_session',
                    metric_name='audio_quality'
                ).values('value', 'timestamp')
            )
        }
    
    def get_ai_processing_details(self, since):
        """Get detailed AI processing metrics"""
        return {
            'processing_times': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='ai_processing'
                ).values('metric_name', 'value', 'timestamp', 'status')
            )
        }
    
    def get_system_resource_details(self, since):
        """Get detailed system resource metrics"""
        return {
            'cpu_usage': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='system_resource',
                    metric_name='cpu_usage'
                ).values('value', 'timestamp')
            ),
            'memory_usage': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='system_resource',
                    metric_name='memory_usage'
                ).values('value', 'timestamp')
            ),
            'concurrent_calls': list(
                PerformanceMetric.objects.filter(
                    timestamp__gte=since,
                    metric_type='system_resource',
                    metric_name='concurrent_calls'
                ).values('value', 'timestamp')
            )
        }
    
    def get_alert_details(self, since):
        """Get detailed alert information"""
        return list(
            SystemAlert.objects.filter(
                first_occurred__gte=since
            ).values(
                'alert_type',
                'severity',
                'title',
                'description',
                'component',
                'is_active',
                'acknowledged',
                'resolved',
                'first_occurred',
                'last_occurred',
                'occurrence_count'
            )
        )
    
    def format_as_text(self, data):
        """Format report data as human-readable text"""
        output = []
        
        # Header
        output.append("=" * 60)
        output.append(f"PERFORMANCE REPORT - {data['report_type'].upper()}")
        output.append("=" * 60)
        output.append(f"Period: {data['period']['start']} to {data['period']['end']}")
        output.append(f"Duration: {data['period']['hours']:.1f} hours")
        output.append("")
        
        # Summary section
        if 'summary' in data:
            summary = data['summary']
            output.append("SUMMARY")
            output.append("-" * 20)
            
            if data['report_type'] == 'comprehensive':
                output.append(f"Total metrics: {summary.get('total_metrics', 0)}")
                output.append(f"Error rate: {summary.get('error_rate', 0):.2f}%")
                output.append(f"Active alerts: {summary.get('active_alerts', 0)}")
                output.append(f"Critical alerts: {summary.get('critical_alerts', 0)}")
                output.append(f"Max concurrent calls: {summary.get('max_concurrent_calls', 0)}")
                
            elif data['report_type'] == 'call_bot_performance':
                output.append(f"Total sessions: {summary['total_sessions']}")
                output.append(f"Successful connections: {summary['successful_connections']}")
                output.append(f"Success rate: {summary['success_rate']:.1f}%")
                
                conn_stats = summary['connection_stats']
                if conn_stats['avg_connection_time']:
                    output.append(f"Avg connection time: {conn_stats['avg_connection_time']:.2f}s")
                    output.append(f"Max connection time: {conn_stats['max_connection_time']:.2f}s")
                
            elif data['report_type'] == 'ai_performance':
                output.append(f"Total operations: {summary['total_operations']}")
                output.append(f"Successful operations: {summary['successful_operations']}")
                output.append(f"Success rate: {summary['success_rate']:.1f}%")
                
                proc_stats = summary['processing_stats']
                if proc_stats['avg_processing_time']:
                    output.append(f"Avg processing time: {proc_stats['avg_processing_time']:.2f}s")
                    output.append(f"Max processing time: {proc_stats['max_processing_time']:.2f}s")
                
            elif data['report_type'] == 'alerts':
                output.append(f"Total alerts: {summary['total_alerts']}")
                output.append(f"Active alerts: {summary['active_alerts']}")
                output.append(f"Resolved alerts: {summary['resolved_alerts']}")
                output.append(f"Resolution rate: {summary['resolution_rate']:.1f}%")
                
                if summary['severity_breakdown']:
                    output.append("\nBy severity:")
                    for severity, count in summary['severity_breakdown'].items():
                        output.append(f"  {severity}: {count}")
            
            output.append("")
        
        # Recent alerts for alerts report
        if data['report_type'] == 'alerts' and 'recent_alerts' in data:
            output.append("RECENT ALERTS")
            output.append("-" * 20)
            for alert in data['recent_alerts']:
                status = "ACTIVE" if alert['is_active'] else "RESOLVED"
                output.append(f"[{alert['severity'].upper()}] {alert['title']} ({status})")
                output.append(f"  Component: {alert['component']}")
                output.append(f"  First occurred: {alert['first_occurred']}")
                output.append(f"  Occurrences: {alert['occurrence_count']}")
                output.append("")
        
        output.append("=" * 60)
        output.append(f"Report generated at: {timezone.now()}")
        
        return "\n".join(output)
    
    def format_as_csv(self, data):
        """Format report data as CSV"""
        # This is a simplified CSV format - could be expanded based on needs
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Report Type', data['report_type']])
        writer.writerow(['Period Start', data['period']['start']])
        writer.writerow(['Period End', data['period']['end']])
        writer.writerow(['Duration Hours', data['period']['hours']])
        writer.writerow([])
        
        # Write summary data
        if 'summary' in data:
            writer.writerow(['Summary'])
            for key, value in data['summary'].items():
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        writer.writerow([f"{key}.{subkey}", subvalue])
                else:
                    writer.writerow([key, value])
        
        return output.getvalue()