"""
Management command for generating analytics reports
"""
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from apps.analytics.services import ReportingService
from apps.analytics.models import Report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate analytics reports for the meeting intelligence system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--report-type',
            type=str,
            choices=['daily_summary', 'weekly_performance', 'monthly_analytics', 'user_activity'],
            default='daily_summary',
            help='Type of report to generate'
        )
        
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to generate report for (YYYY-MM-DD format)'
        )
        
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for user-specific reports'
        )
        
        parser.add_argument(
            '--email-recipients',
            type=str,
            nargs='+',
            help='Email addresses to send the report to'
        )
        
        parser.add_argument(
            '--auto-schedule',
            action='store_true',
            help='Generate reports based on automatic scheduling'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration of existing reports'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        try:
            self.stdout.write(
                self.style.SUCCESS('Starting report generation...')
            )
            
            if options['auto_schedule']:
                self.handle_auto_scheduled_reports()
            else:
                self.handle_single_report(options)
            
            self.stdout.write(
                self.style.SUCCESS('Report generation completed successfully!')
            )
            
        except Exception as e:
            logger.error(f"Report generation error: {str(e)}")
            raise CommandError(f'Report generation failed: {str(e)}')
    
    def handle_single_report(self, options):
        """Handle generation of a single report"""
        report_type = options['report_type']
        
        # Determine date
        if options['date']:
            target_date = datetime.strptime(options['date'], '%Y-%m-%d')
            target_date = timezone.make_aware(target_date)
        else:
            target_date = timezone.now()
        
        # Get user if specified
        user = None
        if options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f"User with ID {options['user_id']} not found")
        
        # Check if report already exists
        if not options['force']:
            existing_report = self.check_existing_report(report_type, target_date, user)
            if existing_report:
                self.stdout.write(
                    self.style.WARNING(
                        f'Report already exists: {existing_report.title} '
                        f'(use --force to regenerate)'
                    )
                )
                return
        
        # Generate report
        report = self.generate_report(report_type, target_date, user)
        
        if report:
            self.stdout.write(
                self.style.SUCCESS(f'Generated report: {report.title}')
            )
            
            # Send email if recipients specified
            if options['email_recipients']:
                self.send_report_email(report, options['email_recipients'])
        else:
            self.stdout.write(
                self.style.ERROR('Failed to generate report')
            )
    
    def handle_auto_scheduled_reports(self):
        """Handle automatically scheduled reports"""
        self.stdout.write('Generating auto-scheduled reports...')
        
        now = timezone.now()
        reports_generated = 0
        
        # Generate daily summary reports for yesterday
        yesterday = now - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if not self.check_existing_report('daily_summary', yesterday):
            report = self.generate_report('daily_summary', yesterday)
            if report:
                reports_generated += 1
                self.stdout.write(f'Generated daily summary for {yesterday.date()}')
        
        # Generate weekly reports on Mondays for the previous week
        if now.weekday() == 0:  # Monday
            last_monday = now - timedelta(days=7)
            last_monday = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not self.check_existing_report('weekly_performance', last_monday):
                report = self.generate_report('weekly_performance', last_monday)
                if report:
                    reports_generated += 1
                    self.stdout.write(f'Generated weekly performance for week of {last_monday.date()}')
        
        # Generate monthly reports on the 1st of each month
        if now.day == 1:
            # First day of current month, generate report for previous month
            if now.month == 1:
                last_month = now.replace(year=now.year - 1, month=12, day=1)
            else:
                last_month = now.replace(month=now.month - 1, day=1)
            
            last_month = last_month.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if not self.check_existing_report('monthly_analytics', last_month):
                report = self.generate_report('monthly_analytics', last_month)
                if report:
                    reports_generated += 1
                    self.stdout.write(f'Generated monthly analytics for {last_month.strftime("%B %Y")}')
        
        self.stdout.write(f'Generated {reports_generated} auto-scheduled reports')
    
    def check_existing_report(self, report_type, target_date, user=None):
        """Check if a report already exists for the given parameters"""
        # Calculate period based on report type
        if report_type == 'daily_summary':
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif report_type == 'weekly_performance':
            # Assume target_date is the start of the week (Monday)
            start_date = target_date
            end_date = start_date + timedelta(days=7)
        elif report_type == 'monthly_analytics':
            start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1)
        else:
            # For user activity reports, use the target date as start
            start_date = target_date
            end_date = start_date + timedelta(days=30)  # Default 30-day period
        
        query = Report.objects.filter(
            report_type=report_type,
            period_start=start_date,
            status='completed'
        )
        
        if user:
            query = query.filter(created_by=user)
        
        return query.first()
    
    def generate_report(self, report_type, target_date, user=None):
        """Generate a specific type of report"""
        reporting_service = ReportingService()
        
        try:
            if report_type == 'daily_summary':
                report = reporting_service.generate_daily_summary_report(target_date, user)
            
            elif report_type == 'weekly_performance':
                report = reporting_service.generate_weekly_performance_report(target_date, user)
            
            elif report_type == 'monthly_analytics':
                # For monthly reports, we need to implement this in the service
                report = self.generate_monthly_analytics_report(target_date, user)
            
            elif report_type == 'user_activity':
                if not user:
                    raise CommandError("User ID is required for user activity reports")
                
                end_date = target_date + timedelta(days=30)
                report = reporting_service.generate_user_activity_report(
                    target_date, end_date, user
                )
            
            else:
                raise CommandError(f"Unsupported report type: {report_type}")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate {report_type} report: {str(e)}")
            return None
    
    def generate_monthly_analytics_report(self, target_date, user=None):
        """Generate monthly analytics report"""
        # Calculate month boundaries
        start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        
        report = Report.objects.create(
            report_type='monthly_analytics',
            title=f"Monthly Analytics Report - {start_date.strftime('%B %Y')}",
            period_start=start_date,
            period_end=end_date,
            created_by=user or User.objects.filter(is_superuser=True).first(),
            status='generating'
        )
        
        try:
            from apps.analytics.services import AnalyticsService
            analytics_service = AnalyticsService()
            
            # Comprehensive monthly analytics
            debriefing_data = analytics_service.calculate_debriefing_completion_rate(
                start_date, end_date, user
            )
            extraction_data = analytics_service.calculate_data_extraction_accuracy(
                start_date, end_date
            )
            meeting_data = analytics_service.calculate_meeting_detection_accuracy(
                start_date, end_date
            )
            participant_data = analytics_service.calculate_participant_matching_accuracy(
                start_date, end_date
            )
            crm_data = analytics_service.calculate_crm_sync_success_rate(
                start_date, end_date
            )
            engagement_data = analytics_service.calculate_user_engagement_metrics(
                start_date, end_date, user
            )
            competitive_data = analytics_service.get_competitive_intelligence_insights(
                start_date, end_date
            )
            
            # Calculate trends (compare with previous month)
            prev_start = start_date - timedelta(days=32)
            prev_start = prev_start.replace(day=1)
            prev_end = start_date
            
            prev_debriefing = analytics_service.calculate_debriefing_completion_rate(
                prev_start, prev_end, user
            )
            
            trends = {
                'debriefing_completion_trend': (
                    debriefing_data['completion_rate'] - prev_debriefing['completion_rate']
                ),
                'meeting_count_trend': (
                    debriefing_data['total_meetings'] - prev_debriefing['total_meetings']
                )
            }
            
            report_data = {
                'debriefing_metrics': debriefing_data,
                'extraction_metrics': extraction_data,
                'meeting_metrics': meeting_data,
                'participant_metrics': participant_data,
                'crm_metrics': crm_data,
                'engagement_metrics': engagement_data,
                'competitive_metrics': competitive_data,
                'trends': trends,
                'generated_at': timezone.now().isoformat()
            }
            
            summary = f"""
            Monthly Analytics Summary for {start_date.strftime('%B %Y')}:
            - Total meetings: {meeting_data['total_meetings']}
            - Debriefing completion: {debriefing_data['completion_rate']}%
            - Data extraction accuracy: {extraction_data['extraction_accuracy']}%
            - Participant matching: {participant_data['matching_rate']}%
            - CRM sync success: {crm_data['success_rate']}%
            - Competitive mentions: {competitive_data['total_competitive_mentions']}
            - Completion rate trend: {trends['debriefing_completion_trend']:+.1f}%
            """
            
            report.mark_completed(report_data, summary.strip())
            
        except Exception as e:
            logger.error(f"Failed to generate monthly analytics report: {str(e)}")
            report.mark_failed(str(e))
        
        return report
    
    def send_report_email(self, report, recipients):
        """Send report via email"""
        try:
            subject = f"Analytics Report: {report.title}"
            
            message = f"""
            Analytics Report Generated
            
            Report: {report.title}
            Period: {report.period_start.date()} to {report.period_end.date()}
            Generated: {report.generated_at}
            Status: {report.status}
            
            Summary:
            {report.summary}
            
            You can view the full report in the analytics dashboard.
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Report emailed to {", ".join(recipients)}')
            )
            
        except Exception as e:
            logger.error(f"Failed to send report email: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Failed to send email: {str(e)}')
            )