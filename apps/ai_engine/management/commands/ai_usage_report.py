"""
Django management command for AI usage reporting
Generates comprehensive reports on AI usage, costs, and performance
"""
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.ai_engine.caching_optimization import get_optimization_service


class Command(BaseCommand):
    help = 'Generate AI usage and optimization reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for the report (default: 7)',
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (optional)',
        )

    def handle(self, *args, **options):
        days = options['days']
        output_format = options['format']
        output_file = options['output']
        
        # Generate report
        optimization_service = get_optimization_service()
        report = optimization_service.get_optimization_report(days)
        
        if output_format == 'json':
            self.output_json_report(report, output_file)
        else:
            self.output_text_report(report, output_file)

    def output_text_report(self, report, output_file=None):
        """Output report in text format"""
        lines = []
        
        lines.append(f"=== AI Usage Report ({report.get('report_period_days', 0)} days) ===")
        lines.append(f"Generated: {report.get('generated_at', 'Unknown')}")
        lines.append("")
        
        # Usage metrics
        usage_metrics = report.get('usage_metrics', {})
        lines.append("=== Usage Metrics ===")
        lines.append(f"Total interactions: {usage_metrics.get('total_interactions', 0):,}")
        lines.append(f"Successful interactions: {usage_metrics.get('successful_interactions', 0):,}")
        lines.append(f"Success rate: {usage_metrics.get('success_rate', 0):.2%}")
        lines.append(f"Average response time: {usage_metrics.get('average_response_time_ms', 0):.0f}ms")
        lines.append(f"Total tokens used: {usage_metrics.get('total_tokens_used', 0):,}")
        lines.append(f"Estimated cost: ${usage_metrics.get('estimated_cost_usd', 0):.4f}")
        lines.append("")
        
        # Cache metrics
        cache_metrics = usage_metrics.get('cache_metrics', {})
        lines.append("=== Cache Performance ===")
        lines.append(f"Cache entries: {cache_metrics.get('total_cache_entries', 0):,}")
        lines.append(f"Active entries: {cache_metrics.get('active_cache_entries', 0):,}")
        lines.append(f"Cache hits: {cache_metrics.get('total_cache_hits', 0):,}")
        lines.append(f"Hit rate: {cache_metrics.get('estimated_hit_rate', 0):.2%}")
        lines.append(f"API calls saved: {cache_metrics.get('estimated_api_calls_saved', 0):,}")
        lines.append(f"Cost savings: ${cache_metrics.get('estimated_cost_savings', 0):.4f}")
        lines.append("")
        
        # Error analysis
        error_breakdown = usage_metrics.get('error_breakdown', {})
        if error_breakdown.get('total_errors', 0) > 0:
            lines.append("=== Error Analysis ===")
            lines.append(f"Total errors: {error_breakdown.get('total_errors', 0):,}")
            lines.append(f"Error rate: {error_breakdown.get('error_rate', 0):.2%}")
            
            error_types = error_breakdown.get('error_types', {})
            for error_type, count in error_types.items():
                lines.append(f"  {error_type}: {count:,}")
            lines.append("")
        
        # Service status
        service_status = report.get('service_status', {})
        lines.append("=== Service Status ===")
        lines.append(f"AI service healthy: {service_status.get('ai_service_healthy', False)}")
        lines.append(f"Fallback available: {service_status.get('fallback_available', False)}")
        lines.append("")
        
        # Optimization suggestions
        suggestions = usage_metrics.get('optimization_suggestions', [])
        if suggestions:
            lines.append("=== Optimization Suggestions ===")
            for suggestion in suggestions:
                lines.append(f"• {suggestion}")
            lines.append("")
        
        # Output
        report_text = "\n".join(lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_text)
            self.stdout.write(f"Report saved to {output_file}")
        else:
            self.stdout.write(report_text)

    def output_json_report(self, report, output_file=None):
        """Output report in JSON format"""
        report_json = json.dumps(report, indent=2, default=str)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_json)
            self.stdout.write(f"JSON report saved to {output_file}")
        else:
            self.stdout.write(report_json)