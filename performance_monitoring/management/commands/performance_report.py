"""
Management command to generate performance reports
"""
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from performance_monitoring.services import performance_monitor


class Command(BaseCommand):
    help = 'Generate performance reports'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Report period in hours (default: 24)'
        )
        
        parser.add_argument(
            '--format',
            choices=['json', 'text'],
            default='text',
            help='Output format (default: text)'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (optional)'
        )
    
    def handle(self, *args, **options):
        hours = options['hours']
        output_format = options['format']
        output_file = options['output']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Generating performance report for last {hours} hours...'
            )
        )
        
        try:
            # Get performance summary
            summary = performance_monitor.get_performance_summary(hours=hours)
            
            if output_format == 'json':
                output = json.dumps(summary, indent=2, default=str)
            else:
                output = self._format_text_report(summary)
            
            # Output to file or stdout
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
    
    def _format_text_report(self, summary):
        """Format summary as text report"""
        report = []
        report.append("=" * 60)
        report.append("NIA PERFORMANCE REPORT")
        report.append("=" * 60)
        report.append(f"Report Period: {summary.get('period_hours', 0)} hours")
        report.append(f"Generated: {summary.get('generated_at', 'Unknown')}")
        report.append("")
        
        # Overall metrics
        report.append("OVERALL METRICS")
        report.append("-" * 20)
        report.append(f"Total Metrics Collected: {summary.get('total_metrics', 0):,}")
        report.append(f"Error Rate: {summary.get('error_rate', 0)}%")
        report.append(f"Active Alerts: {summary.get('active_alerts', 0)}")
        report.append(f"Critical Alerts: {summary.get('critical_alerts', 0)}")
        report.append(f"Max Concurrent Calls: {summary.get('max_concurrent_calls', 0)}")
        report.append("")
        
        # Call bot performance
        call_bot = summary.get('call_bot_performance', {})
        if call_bot:
            report.append("CALL BOT PERFORMANCE")
            report.append("-" * 25)
            report.append(f"Total Sessions: {call_bot.get('total_sessions', 0):,}")
            
            avg_conn = call_bot.get('avg_connection_time')
            if avg_conn:
                report.append(f"Avg Connection Time: {avg_conn:.2f}s")
            
            max_conn = call_bot.get('max_connection_time')
            if max_conn:
                report.append(f"Max Connection Time: {max_conn:.2f}s")
            
            min_conn = call_bot.get('min_connection_time')
            if min_conn:
                report.append(f"Min Connection Time: {min_conn:.2f}s")
            
            report.append("")
        
        # AI performance
        ai_perf = summary.get('ai_performance', {})
        if ai_perf:
            report.append("AI PROCESSING PERFORMANCE")
            report.append("-" * 30)
            report.append(f"Total Operations: {ai_perf.get('total_operations', 0):,}")
            
            avg_proc = ai_perf.get('avg_processing_time')
            if avg_proc:
                report.append(f"Avg Processing Time: {avg_proc:.2f}s")
            
            max_proc = ai_perf.get('max_processing_time')
            if max_proc:
                report.append(f"Max Processing Time: {max_proc:.2f}s")
            
            report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)