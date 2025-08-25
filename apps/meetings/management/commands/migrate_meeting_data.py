"""
Management command to migrate meeting data between formats or fix data issues
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.meetings.models import Meeting, MeetingParticipant
from apps.leads.models import Lead
import logging
import json

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate meeting data and fix data consistency issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--operation',
            type=str,
            choices=[
                'fix_participant_matching',
                'update_meeting_types',
                'fix_timezone_issues',
                'consolidate_duplicates',
                'validate_data'
            ],
            required=True,
            help='Migration operation to perform'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process in each batch (default: 100)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration without confirmation'
        )
    
    def handle(self, *args, **options):
        operation = options['operation']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting data migration: {operation}'
            )
        )
        
        if operation == 'fix_participant_matching':
            self.fix_participant_matching(batch_size, dry_run, force)
        elif operation == 'update_meeting_types':
            self.update_meeting_types(batch_size, dry_run, force)
        elif operation == 'fix_timezone_issues':
            self.fix_timezone_issues(batch_size, dry_run, force)
        elif operation == 'consolidate_duplicates':
            self.consolidate_duplicates(batch_size, dry_run, force)
        elif operation == 'validate_data':
            self.validate_data()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Data migration completed: {operation}'
            )
        )
    
    def fix_participant_matching(self, batch_size, dry_run, force):
        """Fix participant matching issues"""
        self.stdout.write('Fixing participant matching issues...')
        
        # Find participants without matched leads
        unmatched_participants = MeetingParticipant.objects.filter(
            matched_lead__isnull=True,
            is_external=True
        )
        
        total_unmatched = unmatched_participants.count()
        self.stdout.write(f'Found {total_unmatched} unmatched external participants')
        
        if total_unmatched == 0:
            self.stdout.write(self.style.SUCCESS('No unmatched participants found'))
            return
        
        fixed_count = 0
        created_leads_count = 0
        
        if dry_run:
            self.stdout.write('Dry run - showing first 10 unmatched participants:')
            for participant in unmatched_participants[:10]:
                self.stdout.write(f'  - {participant.email} ({participant.name}) from {participant.company}')
            return
        
        if not force:
            confirm = input(f'Attempt to match {total_unmatched} participants? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        try:
            with transaction.atomic():
                for i in range(0, total_unmatched, batch_size):
                    batch = unmatched_participants[i:i + batch_size]
                    
                    for participant in batch:
                        # Try to find existing lead by email
                        existing_lead = Lead.objects.filter(email=participant.email).first()
                        
                        if existing_lead:
                            participant.matched_lead = existing_lead
                            participant.match_confidence = 1.0
                            participant.match_method = 'email_exact'
                            participant.save()
                            fixed_count += 1
                        elif participant.name and participant.company:
                            # Create new lead
                            name_parts = participant.name.split(' ', 1)
                            first_name = name_parts[0]
                            last_name = name_parts[1] if len(name_parts) > 1 else ''
                            
                            new_lead = Lead.objects.create(
                                first_name=first_name,
                                last_name=last_name,
                                email=participant.email,
                                company=participant.company,
                                source='meeting_participant',
                                status='new'
                            )
                            
                            participant.matched_lead = new_lead
                            participant.match_confidence = 0.8
                            participant.match_method = 'created_from_participant'
                            participant.save()
                            
                            created_leads_count += 1
                            fixed_count += 1
                    
                    self.stdout.write(f'Processed batch {i//batch_size + 1}/{(total_unmatched + batch_size - 1)//batch_size}')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Fixed {fixed_count} participant matches, created {created_leads_count} new leads'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during participant matching: {str(e)}')
            )
    
    def update_meeting_types(self, batch_size, dry_run, force):
        """Update meeting types based on improved classification"""
        self.stdout.write('Updating meeting types...')
        
        meetings_to_update = Meeting.objects.filter(
            meeting_type__isnull=True
        )
        
        total_meetings = meetings_to_update.count()
        self.stdout.write(f'Found {total_meetings} meetings without type classification')
        
        if total_meetings == 0:
            self.stdout.write(self.style.SUCCESS('No meetings need type updates'))
            return
        
        if dry_run:
            self.stdout.write('Dry run - showing first 10 meetings to classify:')
            for meeting in meetings_to_update[:10]:
                self.stdout.write(f'  - {meeting.title} ({meeting.start_time.date()})')
            return
        
        if not force:
            confirm = input(f'Update types for {total_meetings} meetings? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        try:
            from apps.calendar_integration.meeting_classifier import MeetingClassifier
            classifier = MeetingClassifier()
            
            updated_count = 0
            
            with transaction.atomic():
                for i in range(0, total_meetings, batch_size):
                    batch = meetings_to_update[i:i + batch_size]
                    
                    for meeting in batch:
                        # Classify meeting type
                        meeting_type = classifier.classify_meeting_type({
                            'title': meeting.title,
                            'description': meeting.description or '',
                            'attendees': [p.email for p in meeting.participants.all()]
                        })
                        
                        meeting.meeting_type = meeting_type
                        meeting.save()
                        updated_count += 1
                    
                    self.stdout.write(f'Processed batch {i//batch_size + 1}/{(total_meetings + batch_size - 1)//batch_size}')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated meeting types for {updated_count} meetings'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during meeting type update: {str(e)}')
            )
    
    def fix_timezone_issues(self, batch_size, dry_run, force):
        """Fix timezone-related issues in meeting data"""
        self.stdout.write('Fixing timezone issues...')
        
        # Find meetings with potential timezone issues
        meetings_with_issues = Meeting.objects.filter(
            timezone__isnull=True
        )
        
        total_meetings = meetings_with_issues.count()
        self.stdout.write(f'Found {total_meetings} meetings without timezone information')
        
        if total_meetings == 0:
            self.stdout.write(self.style.SUCCESS('No timezone issues found'))
            return
        
        if dry_run:
            self.stdout.write('Dry run - showing first 10 meetings with timezone issues:')
            for meeting in meetings_with_issues[:10]:
                self.stdout.write(f'  - {meeting.title} ({meeting.start_time})')
            return
        
        if not force:
            confirm = input(f'Fix timezone for {total_meetings} meetings? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        try:
            updated_count = 0
            
            with transaction.atomic():
                for i in range(0, total_meetings, batch_size):
                    batch = meetings_with_issues[i:i + batch_size]
                    
                    for meeting in batch:
                        # Set default timezone based on organizer's profile
                        if hasattr(meeting.organizer, 'profile') and meeting.organizer.profile.timezone:
                            meeting.timezone = meeting.organizer.profile.timezone
                        else:
                            meeting.timezone = 'UTC'  # Default fallback
                        
                        meeting.save()
                        updated_count += 1
                    
                    self.stdout.write(f'Processed batch {i//batch_size + 1}/{(total_meetings + batch_size - 1)//batch_size}')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Fixed timezone for {updated_count} meetings'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during timezone fix: {str(e)}')
            )
    
    def consolidate_duplicates(self, batch_size, dry_run, force):
        """Consolidate duplicate meetings"""
        self.stdout.write('Finding and consolidating duplicate meetings...')
        
        # Find potential duplicates based on title, start_time, and organizer
        from django.db.models import Count
        
        duplicates = Meeting.objects.values(
            'title', 'start_time', 'organizer'
        ).annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        total_duplicate_groups = duplicates.count()
        self.stdout.write(f'Found {total_duplicate_groups} groups of duplicate meetings')
        
        if total_duplicate_groups == 0:
            self.stdout.write(self.style.SUCCESS('No duplicate meetings found'))
            return
        
        if dry_run:
            self.stdout.write('Dry run - showing first 5 duplicate groups:')
            for dup in duplicates[:5]:
                meetings = Meeting.objects.filter(
                    title=dup['title'],
                    start_time=dup['start_time'],
                    organizer=dup['organizer']
                )
                self.stdout.write(f'  - "{dup["title"]}" ({dup["count"]} duplicates)')
                for meeting in meetings:
                    self.stdout.write(f'    ID: {meeting.id}, Created: {meeting.created_at}')
            return
        
        if not force:
            confirm = input(f'Consolidate {total_duplicate_groups} duplicate groups? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
        
        try:
            consolidated_count = 0
            deleted_count = 0
            
            with transaction.atomic():
                for dup in duplicates:
                    meetings = Meeting.objects.filter(
                        title=dup['title'],
                        start_time=dup['start_time'],
                        organizer=dup['organizer']
                    ).order_by('created_at')
                    
                    # Keep the first (oldest) meeting, merge data from others
                    primary_meeting = meetings.first()
                    duplicate_meetings = meetings[1:]
                    
                    for duplicate in duplicate_meetings:
                        # Merge participants
                        for participant in duplicate.participants.all():
                            participant.meeting = primary_meeting
                            participant.save()
                        
                        # Merge notes
                        for note in duplicate.notes.all():
                            note.meeting = primary_meeting
                            note.save()
                        
                        # Update primary meeting with any missing data
                        if not primary_meeting.description and duplicate.description:
                            primary_meeting.description = duplicate.description
                        
                        if not primary_meeting.location and duplicate.location:
                            primary_meeting.location = duplicate.location
                        
                        # Delete the duplicate
                        duplicate.delete()
                        deleted_count += 1
                    
                    primary_meeting.save()
                    consolidated_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Consolidated {consolidated_count} meeting groups, deleted {deleted_count} duplicates'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during consolidation: {str(e)}')
            )
    
    def validate_data(self):
        """Validate meeting data integrity"""
        self.stdout.write('Validating meeting data integrity...')
        
        issues = []
        
        # Check for meetings without organizers
        meetings_without_organizer = Meeting.objects.filter(organizer__isnull=True).count()
        if meetings_without_organizer > 0:
            issues.append(f'{meetings_without_organizer} meetings without organizer')
        
        # Check for participants without email
        participants_without_email = MeetingParticipant.objects.filter(email='').count()
        if participants_without_email > 0:
            issues.append(f'{participants_without_email} participants without email')
        
        # Check for meetings with invalid dates
        invalid_date_meetings = Meeting.objects.filter(start_time__gt=timezone.now() + timezone.timedelta(days=365*2)).count()
        if invalid_date_meetings > 0:
            issues.append(f'{invalid_date_meetings} meetings with dates more than 2 years in future')
        
        from django.db import models
        
        # Check for meetings with end time before start time
        invalid_duration_meetings = Meeting.objects.filter(end_time__lt=models.F('start_time')).count()
        if invalid_duration_meetings > 0:
            issues.append(f'{invalid_duration_meetings} meetings with end time before start time')
        
        if issues:
            self.stdout.write(self.style.WARNING('Data integrity issues found:'))
            for issue in issues:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('No data integrity issues found'))
        
        # Show statistics
        total_meetings = Meeting.objects.count()
        total_participants = MeetingParticipant.objects.count()
        sales_meetings = Meeting.objects.filter(is_sales_meeting=True).count()
        
        self.stdout.write('\nData statistics:')
        self.stdout.write(f'  Total meetings: {total_meetings}')
        self.stdout.write(f'  Total participants: {total_participants}')
        self.stdout.write(f'  Sales meetings: {sales_meetings} ({(sales_meetings/total_meetings)*100:.1f}%)')
        
        return len(issues) == 0