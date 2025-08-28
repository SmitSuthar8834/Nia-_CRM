"""
Management command for running participant matching algorithms
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.leads.services import ParticipantAnalysisService
from apps.leads.verification import ManualVerificationService
from apps.meetings.models import Meeting, MeetingParticipant


class Command(BaseCommand):
    help = 'Run participant matching algorithms for meetings'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--meeting-id',
            type=str,
            help='Specific meeting ID to process'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Process meetings from the last N days (default: 7)'
        )
        parser.add_argument(
            '--use-linkedin',
            action='store_true',
            help='Use LinkedIn enhancement for matching'
        )
        parser.add_argument(
            '--auto-approve-threshold',
            type=float,
            default=0.8,
            help='Auto-approve matches above this confidence threshold'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        meeting_id = options['meeting_id']
        days = options['days']
        use_linkedin = options['use_linkedin']
        auto_approve_threshold = options['auto_approve_threshold']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )
        
        analysis_service = ParticipantAnalysisService()
        verification_service = ManualVerificationService()
        
        if meeting_id:
            # Process specific meeting
            try:
                meeting = Meeting.objects.get(id=meeting_id)
                self._process_meeting(meeting, analysis_service, use_linkedin, dry_run)
            except Meeting.DoesNotExist:
                raise CommandError(f'Meeting with ID {meeting_id} not found')
        else:
            # Process meetings from the last N days
            cutoff_date = timezone.now() - timezone.timedelta(days=days)
            meetings = Meeting.objects.filter(
                start_time__gte=cutoff_date,
                is_sales_meeting=True
            ).order_by('-start_time')
            
            self.stdout.write(
                f'Processing {meetings.count()} meetings from the last {days} days'
            )
            
            for meeting in meetings:
                self._process_meeting(meeting, analysis_service, use_linkedin, dry_run)
        
        # Auto-approve high confidence matches if not dry run
        if not dry_run and auto_approve_threshold > 0:
            approved_count = verification_service.bulk_approve_high_confidence_matches(
                auto_approve_threshold
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Auto-approved {approved_count} high-confidence matches'
                )
            )
        
        # Show verification statistics
        self._show_verification_stats(verification_service)
    
    def _process_meeting(self, meeting, analysis_service, use_linkedin, dry_run):
        """Process a single meeting for participant matching"""
        self.stdout.write(f'Processing meeting: {meeting.title} ({meeting.start_time})')
        
        # Get existing participants
        participants_data = []
        existing_participants = MeetingParticipant.objects.filter(meeting=meeting)
        
        for participant in existing_participants:
            participants_data.append({
                'email': participant.email,
                'name': participant.name or '',
                'company': participant.company or '',
                'title': participant.title or '',
                'phone': participant.phone or ''
            })
        
        if not participants_data:
            self.stdout.write('  No participants found for this meeting')
            return
        
        if dry_run:
            # Just show what would be matched
            from apps.leads.services import ParticipantMatchingService
            matching_service = ParticipantMatchingService()
            results = matching_service.match_participants(participants_data)
            
            self.stdout.write(f'  Would process {len(participants_data)} participants:')
            for result in results:
                participant = result['participant']
                if result['matched_lead']:
                    self.stdout.write(
                        f'    {participant["email"]} -> {result["matched_lead"].full_name} '
                        f'({result["confidence_score"]:.2f} confidence)'
                    )
                elif result['should_create_new_lead']:
                    self.stdout.write(f'    {participant["email"]} -> CREATE NEW LEAD')
                elif result['requires_manual_verification']:
                    self.stdout.write(f'    {participant["email"]} -> NEEDS VERIFICATION')
        else:
            # Actually process the participants
            try:
                results = analysis_service.analyze_meeting_participants(
                    str(meeting.id), participants_data, use_linkedin
                )
                
                self.stdout.write(
                    f'  Processed {results["total_participants"]} participants: '
                    f'{results["matched_participants"]} matched, '
                    f'{results["new_leads_created"]} new leads, '
                    f'{results["manual_verification_required"]} need verification'
                )
                
                if use_linkedin and results.get('linkedin_enhanced', 0) > 0:
                    self.stdout.write(
                        f'  LinkedIn enhanced: {results["linkedin_enhanced"]} participants'
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Error processing meeting: {str(e)}')
                )
    
    def _show_verification_stats(self, verification_service):
        """Show verification statistics"""
        try:
            from apps.leads.verification import VerificationAnalyticsService
            analytics_service = VerificationAnalyticsService()
            stats = analytics_service.get_verification_statistics(30)
            
            self.stdout.write('\nVerification Statistics (last 30 days):')
            self.stdout.write(f'  Total requests: {stats["total_requests"]}')
            self.stdout.write(f'  Approved: {stats["approved_requests"]}')
            self.stdout.write(f'  Rejected: {stats["rejected_requests"]}')
            self.stdout.write(f'  Pending: {stats["pending_requests"]}')
            self.stdout.write(f'  Approval rate: {stats["approval_rate"]:.1%}')
            self.stdout.write(f'  Avg review time: {stats["avg_review_hours"]:.1f} hours')
            
            if stats["overdue_requests"] > 0:
                self.stdout.write(
                    self.style.WARNING(f'  Overdue requests: {stats["overdue_requests"]}')
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting verification stats: {str(e)}')
            )