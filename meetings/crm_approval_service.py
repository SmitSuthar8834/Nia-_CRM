"""
CRM approval service for managing validation completion and CRM update workflows
"""
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import ValidationSession, CRMSyncRecord
from .validation_service import ValidationService


class CRMApprovalService:
    """
    Service class for managing CRM approval workflows after validation completion
    """
    
    def __init__(self):
        self.validation_service = ValidationService()
    
    def approve_crm_updates(
        self, 
        session_id: int, 
        approved_systems: List[str],
        custom_updates: Optional[Dict] = None
    ) -> Tuple[bool, List[CRMSyncRecord]]:
        """
        Approve CRM updates for specific systems after validation completion
        
        Args:
            session_id: ValidationSession ID
            approved_systems: List of CRM systems to sync to ('salesforce', 'hubspot', 'creatio')
            custom_updates: Optional custom updates to override approved updates
            
        Returns:
            Tuple of (success, list of CRM sync records)
            
        Raises:
            ValidationError: If session is not completed or invalid systems specified
        """
        try:
            session = self.validation_service.get_validation_session(session_id)
        except Exception as e:
            raise ValidationError(f"Invalid session: {str(e)}")
        
        if session.validation_status != 'completed':
            raise ValidationError("Can only approve CRM updates for completed validation sessions")
        
        # Validate CRM systems
        valid_systems = ['salesforce', 'hubspot', 'creatio']
        invalid_systems = [sys for sys in approved_systems if sys not in valid_systems]
        if invalid_systems:
            raise ValidationError(f"Invalid CRM systems: {', '.join(invalid_systems)}")
        
        # Prepare CRM updates
        crm_updates = session.approved_crm_updates.copy()
        if custom_updates:
            crm_updates.update(custom_updates)
        
        sync_records = []
        
        with transaction.atomic():
            # Create CRM sync records for each approved system
            for crm_system in approved_systems:
                # Format data for specific CRM system
                formatted_payload = self._format_crm_payload(
                    session, crm_updates, crm_system
                )
                
                sync_record = CRMSyncRecord.objects.create(
                    validation_session=session,
                    crm_system=crm_system,
                    sync_status='pending',
                    sync_payload=formatted_payload
                )
                sync_records.append(sync_record)
            
            # Update session audit trail
            session.changes_made.append({
                'action': 'crm_updates_approved',
                'timestamp': timezone.now().isoformat(),
                'approved_systems': approved_systems,
                'custom_updates_applied': bool(custom_updates)
            })
            session.save()
        
        return True, sync_records
    
    def _format_crm_payload(
        self, 
        session: ValidationSession, 
        crm_updates: Dict, 
        crm_system: str
    ) -> Dict:
        """
        Format CRM payload for specific system
        
        Args:
            session: ValidationSession instance
            crm_updates: Approved CRM updates
            crm_system: Target CRM system
            
        Returns:
            Formatted payload for the CRM system
        """
        meeting = session.draft_summary.bot_session.meeting
        base_payload = {
            'meeting_id': meeting.id,
            'meeting_title': meeting.title,
            'meeting_date': meeting.start_time.isoformat(),
            'attendees': meeting.attendees,
            'summary': session.validated_summary,
            'validation_completed_at': session.completed_at.isoformat(),
            'sales_rep_email': session.sales_rep_email
        }
        
        # Add lead information if available
        if meeting.lead:
            base_payload.update({
                'lead_id': meeting.lead.crm_id,
                'lead_name': meeting.lead.name,
                'lead_email': meeting.lead.email,
                'company': meeting.lead.company
            })
        
        # Format for specific CRM system
        if crm_system == 'salesforce':
            return self._format_salesforce_payload(base_payload, crm_updates)
        elif crm_system == 'hubspot':
            return self._format_hubspot_payload(base_payload, crm_updates)
        elif crm_system == 'creatio':
            return self._format_creatio_payload(base_payload, crm_updates)
        else:
            return base_payload
    
    def _format_salesforce_payload(self, base_payload: Dict, crm_updates: Dict) -> Dict:
        """Format payload for Salesforce"""
        sf_payload = base_payload.copy()
        
        # Map to Salesforce field names
        sf_payload.update({
            'Subject': base_payload['meeting_title'],
            'Description': base_payload['summary'],
            'ActivityDate': base_payload['meeting_date'][:10],  # Date only
            'Status': 'Completed',
            'Type': 'Meeting'
        })
        
        # Add CRM-specific updates
        if 'deal_stage' in crm_updates:
            sf_payload['StageName'] = crm_updates['deal_stage']
        
        if 'next_action' in crm_updates:
            sf_payload['NextStep'] = crm_updates['next_action']
        
        # Add all other custom updates directly
        for key, value in crm_updates.items():
            if key not in ['deal_stage', 'next_action', 'meeting_summary']:
                sf_payload[key] = value
        
        return sf_payload
    
    def _format_hubspot_payload(self, base_payload: Dict, crm_updates: Dict) -> Dict:
        """Format payload for HubSpot"""
        hs_payload = base_payload.copy()
        
        # Map to HubSpot field names
        hs_payload.update({
            'hs_meeting_title': base_payload['meeting_title'],
            'hs_meeting_body': base_payload['summary'],
            'hs_meeting_start_time': base_payload['meeting_date'],
            'hs_meeting_outcome': 'COMPLETED'
        })
        
        # Add CRM-specific updates
        if 'deal_stage' in crm_updates:
            hs_payload['dealstage'] = crm_updates['deal_stage']
        
        # Add all other custom updates directly
        for key, value in crm_updates.items():
            if key not in ['deal_stage', 'meeting_summary']:
                hs_payload[key] = value
        
        return hs_payload
    
    def _format_creatio_payload(self, base_payload: Dict, crm_updates: Dict) -> Dict:
        """Format payload for Creatio"""
        creatio_payload = base_payload.copy()
        
        # Map to Creatio field names
        creatio_payload.update({
            'Title': base_payload['meeting_title'],
            'Notes': base_payload['summary'],
            'StartDate': base_payload['meeting_date'],
            'Status': 'Completed'
        })
        
        # Add CRM-specific updates
        if 'deal_stage' in crm_updates:
            creatio_payload['Stage'] = crm_updates['deal_stage']
        
        # Add all other custom updates directly
        for key, value in crm_updates.items():
            if key not in ['deal_stage', 'meeting_summary']:
                creatio_payload[key] = value
        
        return creatio_payload
    
    def reject_crm_updates(
        self, 
        session_id: int, 
        rejection_reason: str
    ) -> ValidationSession:
        """
        Reject CRM updates for a validation session
        
        Args:
            session_id: ValidationSession ID
            rejection_reason: Reason for rejection
            
        Returns:
            Updated ValidationSession instance
            
        Raises:
            ValidationError: If session is not completed
        """
        try:
            session = self.validation_service.get_validation_session(session_id)
        except Exception as e:
            raise ValidationError(f"Invalid session: {str(e)}")
        
        if session.validation_status != 'completed':
            raise ValidationError("Can only reject CRM updates for completed validation sessions")
        
        with transaction.atomic():
            # Update session audit trail
            session.changes_made.append({
                'action': 'crm_updates_rejected',
                'timestamp': timezone.now().isoformat(),
                'rejection_reason': rejection_reason
            })
            
            # Clear approved CRM updates
            session.approved_crm_updates = {}
            session.save()
        
        return session
    
    def get_crm_sync_status(self, session_id: int) -> Dict:
        """
        Get CRM synchronization status for a validation session
        
        Args:
            session_id: ValidationSession ID
            
        Returns:
            Dictionary with sync status information
        """
        try:
            session = self.validation_service.get_validation_session(session_id)
        except Exception as e:
            raise ValidationError(f"Invalid session: {str(e)}")
        
        sync_records = CRMSyncRecord.objects.filter(
            validation_session=session
        ).order_by('created_at')
        
        sync_status = {
            'session_id': session_id,
            'validation_status': session.validation_status,
            'has_approved_updates': bool(session.approved_crm_updates),
            'sync_records': []
        }
        
        for record in sync_records:
            sync_status['sync_records'].append({
                'id': record.id,
                'crm_system': record.crm_system,
                'sync_status': record.sync_status,
                'crm_record_id': record.crm_record_id,
                'error_message': record.error_message,
                'retry_count': record.retry_count,
                'synced_at': record.synced_at,
                'created_at': record.created_at
            })
        
        return sync_status
    
    def retry_failed_sync(self, sync_record_id: int) -> CRMSyncRecord:
        """
        Retry a failed CRM synchronization
        
        Args:
            sync_record_id: CRMSyncRecord ID
            
        Returns:
            Updated CRMSyncRecord instance
            
        Raises:
            ValidationError: If sync record is not in failed state
        """
        try:
            sync_record = CRMSyncRecord.objects.get(id=sync_record_id)
        except CRMSyncRecord.DoesNotExist:
            raise ValidationError(f"CRM sync record with ID {sync_record_id} not found")
        
        if sync_record.sync_status != 'failed':
            raise ValidationError("Can only retry failed synchronizations")
        
        with transaction.atomic():
            # Reset sync record for retry
            sync_record.sync_status = 'pending'
            sync_record.error_message = ''
            sync_record.retry_count += 1
            sync_record.save()
            
            # Update session audit trail
            session = sync_record.validation_session
            session.changes_made.append({
                'action': 'crm_sync_retried',
                'timestamp': timezone.now().isoformat(),
                'crm_system': sync_record.crm_system,
                'retry_count': sync_record.retry_count
            })
            session.save()
        
        return sync_record
    
    def update_sync_record_status(
        self, 
        sync_record_id: int, 
        status: str, 
        crm_record_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> CRMSyncRecord:
        """
        Update CRM sync record status (typically called by external sync processes)
        
        Args:
            sync_record_id: CRMSyncRecord ID
            status: New sync status ('in_progress', 'completed', 'failed')
            crm_record_id: Optional CRM record ID if sync was successful
            error_message: Optional error message if sync failed
            
        Returns:
            Updated CRMSyncRecord instance
        """
        try:
            sync_record = CRMSyncRecord.objects.get(id=sync_record_id)
        except CRMSyncRecord.DoesNotExist:
            raise ValidationError(f"CRM sync record with ID {sync_record_id} not found")
        
        valid_statuses = ['pending', 'in_progress', 'completed', 'failed', 'retrying']
        if status not in valid_statuses:
            raise ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        with transaction.atomic():
            sync_record.sync_status = status
            
            if crm_record_id:
                sync_record.crm_record_id = crm_record_id
            
            if error_message:
                sync_record.error_message = error_message
            
            if status == 'completed':
                sync_record.synced_at = timezone.now()
            
            sync_record.save()
            
            # Update session audit trail
            session = sync_record.validation_session
            session.changes_made.append({
                'action': 'crm_sync_status_updated',
                'timestamp': timezone.now().isoformat(),
                'crm_system': sync_record.crm_system,
                'new_status': status,
                'crm_record_id': crm_record_id,
                'has_error': bool(error_message)
            })
            session.save()
        
        return sync_record
    
    def generate_approval_summary(self, session_id: int) -> Dict:
        """
        Generate a comprehensive approval summary for a validation session
        
        Args:
            session_id: ValidationSession ID
            
        Returns:
            Dictionary with approval summary information
        """
        try:
            session = self.validation_service.get_validation_session(session_id)
        except Exception as e:
            raise ValidationError(f"Invalid session: {str(e)}")
        
        meeting = session.draft_summary.bot_session.meeting
        
        # Calculate validation metrics
        total_questions = len(session.validation_questions)
        answered_questions = len(session.rep_responses)
        required_questions = len([q for q in session.validation_questions if q.get('required', False)])
        
        # Analyze changes made during validation
        changes_summary = self._analyze_validation_changes(session)
        
        # Get CRM sync status
        crm_sync_status = self.get_crm_sync_status(session_id)
        
        approval_summary = {
            'session_info': {
                'id': session.id,
                'sales_rep_email': session.sales_rep_email,
                'validation_status': session.validation_status,
                'started_at': session.started_at,
                'completed_at': session.completed_at,
                'duration_minutes': (
                    (session.completed_at - session.started_at).total_seconds() / 60
                ) if session.completed_at else None
            },
            'meeting_info': {
                'id': meeting.id,
                'title': meeting.title,
                'start_time': meeting.start_time,
                'lead_name': meeting.lead.name if meeting.lead else None,
                'company': meeting.lead.company if meeting.lead else None
            },
            'validation_metrics': {
                'total_questions': total_questions,
                'answered_questions': answered_questions,
                'required_questions': required_questions,
                'completion_rate': (answered_questions / total_questions * 100) if total_questions > 0 else 0
            },
            'changes_summary': changes_summary,
            'crm_sync_status': crm_sync_status,
            'final_summary': session.validated_summary,
            'approved_crm_updates': session.approved_crm_updates,
            'audit_trail': session.changes_made
        }
        
        return approval_summary
    
    def _analyze_validation_changes(self, session: ValidationSession) -> Dict:
        """
        Analyze changes made during validation process
        
        Args:
            session: ValidationSession instance
            
        Returns:
            Dictionary with changes analysis
        """
        changes_summary = {
            'total_changes': len(session.changes_made),
            'response_submissions': 0,
            'corrections_made': 0,
            'crm_approvals': 0,
            'crm_rejections': 0,
            'timeline': []
        }
        
        for change in session.changes_made:
            action = change.get('action', '')
            
            if action == 'response_submitted':
                changes_summary['response_submissions'] += 1
            elif action == 'correction_made':
                changes_summary['corrections_made'] += 1
            elif action == 'crm_updates_approved':
                changes_summary['crm_approvals'] += 1
            elif action == 'crm_updates_rejected':
                changes_summary['crm_rejections'] += 1
            
            changes_summary['timeline'].append({
                'timestamp': change.get('timestamp'),
                'action': action,
                'description': self._format_change_description(change)
            })
        
        return changes_summary
    
    def _format_change_description(self, change: Dict) -> str:
        """
        Format a human-readable description of a change
        
        Args:
            change: Change record from audit trail
            
        Returns:
            Human-readable description
        """
        action = change.get('action', '')
        
        if action == 'response_submitted':
            question_id = change.get('question_id', 'unknown')
            return f"Submitted response to question: {question_id}"
        elif action == 'session_completed':
            return "Validation session completed"
        elif action == 'crm_updates_approved':
            systems = change.get('approved_systems', [])
            return f"Approved CRM updates for: {', '.join(systems)}"
        elif action == 'crm_updates_rejected':
            reason = change.get('rejection_reason', 'No reason provided')
            return f"Rejected CRM updates: {reason}"
        elif action == 'crm_sync_status_updated':
            system = change.get('crm_system', 'unknown')
            status = change.get('new_status', 'unknown')
            return f"CRM sync status updated for {system}: {status}"
        else:
            return f"Action: {action}"