"""
User Review Workflow for CRM Updates
Handles user review and approval of CRM data updates
"""
import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from .models import CreatioSync, SyncConflict, SyncLog
from .update_service import CRMUpdateService
from apps.leads.models import Lead

logger = logging.getLogger(__name__)


class ReviewWorkflowManager:
    """
    Manages user review workflows for CRM updates
    """
    
    def __init__(self):
        self.update_service = CRMUpdateService()
    
    def create_review_request(
        self,
        entity_type: str,
        entity_id: str,
        proposed_changes: Dict[str, Any],
        user: User,
        priority: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Create a review request for CRM updates
        """
        try:
            # Get or create sync record
            sync_record, created = CreatioSync.objects.get_or_create(
                entity_type=entity_type,
                local_id=entity_id,
                defaults={
                    'sync_status': 'manual_review',
                    'sync_direction': 'to_creatio'
                }
            )
            
            if not created:
                sync_record.sync_status = 'manual_review'
                sync_record.save()
            
            # Create review data
            review_data = {
                'sync_record_id': str(sync_record.id),
                'entity_type': entity_type,
                'entity_id': entity_id,
                'proposed_changes': proposed_changes,
                'priority': priority,
                'created_by': user.id,
                'created_at': timezone.now().isoformat(),
                'status': 'pending_review'
            }
            
            # Store review data in sync record
            sync_record.request_data = review_data
            sync_record.save()
            
            # Send notification if high priority
            if priority == 'urgent':
                self._send_urgent_review_notification(review_data, user)
            
            # Log review request
            SyncLog.objects.create(
                sync_record=sync_record,
                log_level='info',
                operation_type='review_request',
                message=f"Review request created for {entity_type} {entity_id}",
                user=user,
                request_data=review_data
            )
            
            return {
                'success': True,
                'review_id': str(sync_record.id),
                'status': 'pending_review',
                'priority': priority
            }
            
        except Exception as e:
            logger.error(f"Error creating review request: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_pending_reviews(self, user: User) -> List[Dict[str, Any]]:
        """
        Get pending reviews for user
        """
        try:
            # Get reviews based on user role
            if user.groups.filter(name__in=['sales_manager', 'admin']).exists():
                # Managers can see all reviews
                sync_records = CreatioSync.objects.filter(
                    sync_status='manual_review'
                ).order_by('-updated_at')
            else:
                # Users can only see their own reviews
                sync_records = CreatioSync.objects.filter(
                    sync_status='manual_review',
                    request_data__created_by=user.id
                ).order_by('-updated_at')
            
            reviews = []
            for sync_record in sync_records:
                review_data = sync_record.request_data or {}
                
                # Get entity details
                entity_details = self._get_entity_details(
                    sync_record.entity_type,
                    sync_record.local_id
                )
                
                reviews.append({
                    'review_id': str(sync_record.id),
                    'entity_type': sync_record.entity_type,
                    'entity_id': str(sync_record.local_id),
                    'entity_details': entity_details,
                    'proposed_changes': review_data.get('proposed_changes', {}),
                    'priority': review_data.get('priority', 'normal'),
                    'created_at': review_data.get('created_at'),
                    'created_by': review_data.get('created_by'),
                    'conflicts': self._get_review_conflicts(sync_record)
                })
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting pending reviews: {str(e)}")
            return []
    
    def approve_changes(
        self,
        review_id: str,
        approved_changes: Dict[str, Any],
        user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve specific changes from review
        """
        try:
            sync_record = CreatioSync.objects.get(id=review_id)
            
            if sync_record.sync_status != 'manual_review':
                return {
                    'success': False,
                    'error': 'Review is not in pending status'
                }
            
            # Apply approved changes
            with transaction.atomic():
                if sync_record.entity_type == 'lead':
                    lead = Lead.objects.get(id=sync_record.local_id)
                    
                    # Apply approved changes
                    for field, value in approved_changes.items():
                        if hasattr(lead, field):
                            setattr(lead, field, value)
                    
                    lead.save()
                    
                    # Create approval note
                    from apps.leads.models import LeadNote
                    LeadNote.objects.create(
                        lead=lead,
                        author=user,
                        title='CRM Update Approved',
                        content=f"Changes approved: {', '.join(approved_changes.keys())}\nNotes: {notes or 'None'}",
                        note_type='system'
                    )
                
                # Update sync record
                sync_record.sync_status = 'pending'
                sync_record.next_sync = timezone.now()
                sync_record.response_data = {
                    'approved_changes': approved_changes,
                    'approved_by': user.id,
                    'approved_at': timezone.now().isoformat(),
                    'notes': notes
                }
                sync_record.save()
                
                # Resolve related conflicts
                conflicts = SyncConflict.objects.filter(
                    sync_record=sync_record,
                    resolution_status='pending'
                )
                
                for conflict in conflicts:
                    if conflict.field_name in approved_changes:
                        conflict.resolve(
                            'resolved_manual',
                            approved_changes[conflict.field_name],
                            user,
                            notes
                        )
                
                # Log approval
                SyncLog.objects.create(
                    sync_record=sync_record,
                    log_level='info',
                    operation_type='approve',
                    message=f"Changes approved for {sync_record.entity_type} {sync_record.local_id}",
                    user=user,
                    request_data={'approved_changes': approved_changes},
                    response_data={'notes': notes}
                )
            
            return {
                'success': True,
                'review_id': review_id,
                'approved_changes': list(approved_changes.keys()),
                'sync_scheduled': True
            }
            
        except CreatioSync.DoesNotExist:
            return {
                'success': False,
                'error': 'Review not found'
            }
        except Exception as e:
            logger.error(f"Error approving changes for review {review_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reject_changes(
        self,
        review_id: str,
        rejected_changes: List[str],
        user: User,
        reason: str
    ) -> Dict[str, Any]:
        """
        Reject specific changes from review
        """
        try:
            sync_record = CreatioSync.objects.get(id=review_id)
            
            if sync_record.sync_status != 'manual_review':
                return {
                    'success': False,
                    'error': 'Review is not in pending status'
                }
            
            with transaction.atomic():
                # Update sync record
                sync_record.response_data = {
                    'rejected_changes': rejected_changes,
                    'rejected_by': user.id,
                    'rejected_at': timezone.now().isoformat(),
                    'reason': reason
                }
                
                # Check if all changes were rejected
                proposed_changes = sync_record.request_data.get('proposed_changes', {})
                remaining_changes = {
                    k: v for k, v in proposed_changes.items() 
                    if k not in rejected_changes
                }
                
                if remaining_changes:
                    # Partial rejection - keep in review for remaining changes
                    sync_record.request_data['proposed_changes'] = remaining_changes
                    sync_record.save()
                else:
                    # All changes rejected - mark as failed
                    sync_record.sync_status = 'failed'
                    sync_record.error_message = f"All changes rejected: {reason}"
                    sync_record.save()
                
                # Resolve related conflicts as rejected
                conflicts = SyncConflict.objects.filter(
                    sync_record=sync_record,
                    field_name__in=rejected_changes,
                    resolution_status='pending'
                )
                
                for conflict in conflicts:
                    conflict.resolve('ignored', None, user, reason)
                
                # Log rejection
                SyncLog.objects.create(
                    sync_record=sync_record,
                    log_level='info',
                    operation_type='reject',
                    message=f"Changes rejected for {sync_record.entity_type} {sync_record.local_id}",
                    user=user,
                    request_data={'rejected_changes': rejected_changes},
                    response_data={'reason': reason}
                )
            
            return {
                'success': True,
                'review_id': review_id,
                'rejected_changes': rejected_changes,
                'remaining_changes': list(remaining_changes.keys()) if remaining_changes else []
            }
            
        except CreatioSync.DoesNotExist:
            return {
                'success': False,
                'error': 'Review not found'
            }
        except Exception as e:
            logger.error(f"Error rejecting changes for review {review_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def batch_approve_reviews(
        self,
        review_ids: List[str],
        user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Batch approve multiple reviews
        """
        results = {
            'approved': [],
            'failed': [],
            'total': len(review_ids)
        }
        
        for review_id in review_ids:
            try:
                sync_record = CreatioSync.objects.get(id=review_id)
                proposed_changes = sync_record.request_data.get('proposed_changes', {})
                
                result = self.approve_changes(review_id, proposed_changes, user, notes)
                
                if result['success']:
                    results['approved'].append(review_id)
                else:
                    results['failed'].append({
                        'review_id': review_id,
                        'error': result['error']
                    })
                    
            except Exception as e:
                results['failed'].append({
                    'review_id': review_id,
                    'error': str(e)
                })
        
        return results
    
    def auto_approve_low_risk_updates(self) -> Dict[str, Any]:
        """
        Auto-approve low-risk updates after 24 hours
        """
        try:
            # Find reviews older than 24 hours with low risk
            cutoff_time = timezone.now() - timezone.timedelta(hours=24)
            
            old_reviews = CreatioSync.objects.filter(
                sync_status='manual_review',
                updated_at__lt=cutoff_time
            )
            
            auto_approved = []
            
            for sync_record in old_reviews:
                try:
                    # Check if review is low risk
                    if self._is_low_risk_review(sync_record):
                        proposed_changes = sync_record.request_data.get('proposed_changes', {})
                        
                        # Auto-approve
                        result = self.approve_changes(
                            str(sync_record.id),
                            proposed_changes,
                            None,  # System approval
                            "Auto-approved after 24 hours (low risk)"
                        )
                        
                        if result['success']:
                            auto_approved.append(str(sync_record.id))
                
                except Exception as e:
                    logger.error(f"Error auto-approving review {sync_record.id}: {str(e)}")
            
            return {
                'success': True,
                'auto_approved_count': len(auto_approved),
                'auto_approved_reviews': auto_approved
            }
            
        except Exception as e:
            logger.error(f"Error in auto-approval process: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_entity_details(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Get entity details for display
        """
        try:
            if entity_type == 'lead':
                lead = Lead.objects.get(id=entity_id)
                return {
                    'name': f"{lead.first_name} {lead.last_name}",
                    'company': lead.company,
                    'email': lead.email,
                    'status': lead.status
                }
        except Exception:
            return {'name': 'Unknown', 'details': 'Entity not found'}
        
        return {'name': 'Unknown', 'details': 'Unsupported entity type'}
    
    def _get_review_conflicts(self, sync_record: CreatioSync) -> List[Dict[str, Any]]:
        """
        Get conflicts associated with review
        """
        conflicts = SyncConflict.objects.filter(
            sync_record=sync_record,
            resolution_status='pending'
        )
        
        return [
            {
                'field_name': conflict.field_name,
                'local_value': conflict.local_value,
                'creatio_value': conflict.creatio_value,
                'conflict_type': conflict.conflict_type
            }
            for conflict in conflicts
        ]
    
    def _is_low_risk_review(self, sync_record: CreatioSync) -> bool:
        """
        Determine if review is low risk for auto-approval
        """
        try:
            proposed_changes = sync_record.request_data.get('proposed_changes', {})
            
            # Low risk fields that can be auto-approved
            low_risk_fields = [
                'qualification_score',
                'last_meeting_date',
                'meeting_count',
                'relationship_stage'
            ]
            
            # Check if all proposed changes are low risk
            for field in proposed_changes.keys():
                if field not in low_risk_fields:
                    return False
            
            # Check if there are any high severity conflicts
            high_severity_conflicts = SyncConflict.objects.filter(
                sync_record=sync_record,
                resolution_status='pending'
            ).exclude(
                field_name__in=low_risk_fields
            ).exists()
            
            return not high_severity_conflicts
            
        except Exception:
            return False
    
    def _send_urgent_review_notification(self, review_data: Dict[str, Any], user: User):
        """
        Send notification for urgent reviews
        """
        try:
            # Get managers to notify
            managers = User.objects.filter(
                groups__name__in=['sales_manager', 'admin'],
                is_active=True
            )
            
            if managers.exists():
                subject = f"Urgent CRM Review Required - {review_data['entity_type']}"
                message = f"""
                An urgent CRM review has been requested by {user.get_full_name() or user.username}.
                
                Entity: {review_data['entity_type']} ({review_data['entity_id']})
                Priority: {review_data['priority']}
                Created: {review_data['created_at']}
                
                Please review and approve/reject the proposed changes.
                """
                
                recipient_emails = [manager.email for manager in managers if manager.email]
                
                if recipient_emails:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        recipient_emails,
                        fail_silently=True
                    )
        
        except Exception as e:
            logger.error(f"Error sending urgent review notification: {str(e)}")


class ReviewAnalytics:
    """
    Analytics for review workflow performance
    """
    
    def get_review_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get review workflow metrics
        """
        try:
            start_date = timezone.now() - timezone.timedelta(days=days)
            
            # Get review records
            reviews = CreatioSync.objects.filter(
                sync_status__in=['manual_review', 'success', 'failed'],
                created_at__gte=start_date
            )
            
            # Calculate metrics
            total_reviews = reviews.count()
            pending_reviews = reviews.filter(sync_status='manual_review').count()
            approved_reviews = reviews.filter(
                sync_status='success',
                response_data__approved_by__isnull=False
            ).count()
            rejected_reviews = reviews.filter(
                sync_status='failed',
                response_data__rejected_by__isnull=False
            ).count()
            
            # Average resolution time
            resolved_reviews = reviews.filter(
                sync_status__in=['success', 'failed'],
                response_data__isnull=False
            )
            
            avg_resolution_time = None
            if resolved_reviews.exists():
                resolution_times = []
                for review in resolved_reviews:
                    created_at = review.created_at
                    resolved_at_str = (
                        review.response_data.get('approved_at') or 
                        review.response_data.get('rejected_at')
                    )
                    if resolved_at_str:
                        try:
                            resolved_at = timezone.datetime.fromisoformat(resolved_at_str.replace('Z', '+00:00'))
                            resolution_time = (resolved_at - created_at).total_seconds() / 3600  # hours
                            resolution_times.append(resolution_time)
                        except:
                            continue
                
                if resolution_times:
                    avg_resolution_time = sum(resolution_times) / len(resolution_times)
            
            return {
                'total_reviews': total_reviews,
                'pending_reviews': pending_reviews,
                'approved_reviews': approved_reviews,
                'rejected_reviews': rejected_reviews,
                'approval_rate': (approved_reviews / total_reviews * 100) if total_reviews > 0 else 0,
                'avg_resolution_time_hours': avg_resolution_time,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error calculating review metrics: {str(e)}")
            return {
                'error': str(e)
            }