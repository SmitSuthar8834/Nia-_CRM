"""
CRM Update Service
Handles CRM data updates and field mapping workflows
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from .models import CreatioSync, SyncConflict, SyncLog
from .field_mapping import FieldMappingService, DataConflictDetector
from .adapters import CreatioAdapter
from apps.leads.models import Lead, ActionItem, CompetitiveIntelligence, LeadNote
from apps.meetings.models import Meeting
from apps.debriefings.models import DebriefingSession

logger = logging.getLogger(__name__)


class CRMUpdateService:
    """
    Service for managing CRM updates from extracted meeting data
    """
    
    def __init__(self):
        self.field_mapper = FieldMappingService()
        self.conflict_detector = DataConflictDetector()
        self.adapter = CreatioAdapter()
    
    def process_debriefing_data(
        self,
        debriefing_session: DebriefingSession,
        user: User
    ) -> Dict[str, Any]:
        """
        Process extracted data from debriefing session and update CRM
        """
        try:
            meeting = debriefing_session.meeting
            extracted_data = debriefing_session.extracted_data
            
            if not extracted_data:
                return {
                    'success': False,
                    'error': 'No extracted data available'
                }
            
            results = {
                'lead_updates': [],
                'competitive_intel': [],
                'action_items': [],
                'opportunities': [],
                'conflicts': [],
                'errors': []
            }
            
            # Process lead updates for each participant
            participants = meeting.participants.filter(matched_lead__isnull=False)
            
            for participant in participants:
                lead = participant.matched_lead
                
                # Update lead with extracted data
                lead_result = self.update_lead_from_extracted_data(
                    lead, meeting, extracted_data, user
                )
                results['lead_updates'].append(lead_result)
                
                # Create competitive intelligence records
                competitive_result = self.create_competitive_intelligence(
                    lead, meeting, extracted_data, user
                )
                if competitive_result:
                    results['competitive_intel'].extend(competitive_result)
                
                # Create opportunity if warranted
                opportunity_result = self.create_opportunity_if_warranted(
                    lead, meeting, extracted_data, user
                )
                if opportunity_result:
                    results['opportunities'].append(opportunity_result)
            
            # Create action items
            action_items_result = self.create_action_items(
                meeting, extracted_data, user
            )
            results['action_items'] = action_items_result
            
            # Update meeting outcome
            self.update_meeting_outcome(meeting, extracted_data)
            
            return {
                'success': True,
                'results': results,
                'processed_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing debriefing data for session {debriefing_session.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_lead_from_extracted_data(
        self,
        lead: Lead,
        meeting: Meeting,
        extracted_data: Dict[str, Any],
        user: User
    ) -> Dict[str, Any]:
        """
        Update lead with extracted data and handle conflicts
        """
        try:
            # Map extracted data to lead fields
            mapping_result = self.field_mapper.map_extracted_data_to_lead(
                extracted_data, lead, meeting
            )
            
            if 'error' in mapping_result:
                return {
                    'lead_id': str(lead.id),
                    'success': False,
                    'error': mapping_result['error']
                }
            
            mapped_data = mapping_result['mapped_data']
            changes_made = mapping_result['changes_made']
            
            if not mapped_data:
                return {
                    'lead_id': str(lead.id),
                    'success': True,
                    'message': 'No updates needed',
                    'changes_made': []
                }
            
            # Check for conflicts with existing Creatio data
            conflicts = []
            if lead.creatio_id:
                conflicts = self.detect_crm_conflicts(lead, mapped_data)
            
            # Apply updates with conflict handling
            with transaction.atomic():
                # Update local lead
                for field, value in mapped_data.items():
                    setattr(lead, field, value)
                lead.save()
                
                # Create lead note about the update
                self.create_update_note(lead, changes_made, extracted_data, user)
                
                # Handle conflicts
                if conflicts:
                    conflict_workflow = self.conflict_detector.create_conflict_resolution_workflow(
                        conflicts, 'lead', str(lead.id)
                    )
                    
                    # Auto-resolve conflicts where possible
                    auto_resolved = self.auto_resolve_conflicts(
                        lead, conflict_workflow['auto_resolvable']
                    )
                    
                    # Create conflict records for manual review
                    manual_conflicts = self.create_conflict_records(
                        lead, conflict_workflow['requires_review']
                    )
                else:
                    # Schedule sync to Creatio
                    self.schedule_crm_sync(lead, 'lead')
            
            return {
                'lead_id': str(lead.id),
                'success': True,
                'changes_made': changes_made,
                'conflicts_detected': len(conflicts),
                'auto_resolved_conflicts': len(conflicts) - len([c for c in conflicts if not self.conflict_detector._can_auto_resolve(c)]),
                'manual_review_required': len([c for c in conflicts if not self.conflict_detector._can_auto_resolve(c)])
            }
            
        except Exception as e:
            logger.error(f"Error updating lead {lead.id} from extracted data: {str(e)}")
            return {
                'lead_id': str(lead.id),
                'success': False,
                'error': str(e)
            }
    
    def detect_crm_conflicts(
        self,
        lead: Lead,
        proposed_updates: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts with existing CRM data
        """
        try:
            if not lead.creatio_id:
                return []
            
            # Get current Creatio data
            response = self.adapter._make_request(
                'GET',
                f"{self.adapter.leads_endpoint}({lead.creatio_id})"
            )
            creatio_data = response.json()
            
            # Prepare local data for comparison
            local_data = {}
            for field in proposed_updates.keys():
                local_data[field] = getattr(lead, field, None)
            
            # Update with proposed changes
            local_data.update(proposed_updates)
            
            # Detect conflicts
            conflicts = self.conflict_detector.detect_conflicts(
                local_data,
                creatio_data,
                self.field_mapper._field_mappings['lead']
            )
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error detecting CRM conflicts for lead {lead.id}: {str(e)}")
            return []
    
    def auto_resolve_conflicts(
        self,
        lead: Lead,
        auto_resolvable: List[Dict[str, Any]]
    ) -> int:
        """
        Auto-resolve conflicts that don't require manual review
        """
        resolved_count = 0
        
        for resolution in auto_resolvable:
            try:
                field = resolution['field']
                strategy = resolution['resolution']
                
                if strategy == 'use_local_value':
                    # Keep the local value (already set)
                    resolved_count += 1
                elif strategy == 'use_creatio_value':
                    # This would require fetching and applying Creatio value
                    # For now, we'll log and handle in manual review
                    logger.info(f"Auto-resolution for {field} requires Creatio value fetch")
                
            except Exception as e:
                logger.error(f"Error auto-resolving conflict for field {resolution.get('field')}: {str(e)}")
        
        return resolved_count
    
    def create_conflict_records(
        self,
        lead: Lead,
        conflicts: List[Dict[str, Any]]
    ) -> List[SyncConflict]:
        """
        Create conflict records for manual review
        """
        conflict_records = []
        
        # Get or create sync record
        sync_record, _ = CreatioSync.objects.get_or_create(
            entity_type='lead',
            local_id=lead.id,
            defaults={
                'creatio_id': lead.creatio_id,
                'sync_status': 'conflict',
                'sync_direction': 'to_creatio'
            }
        )
        
        if sync_record.sync_status != 'conflict':
            sync_record.sync_status = 'conflict'
            sync_record.save()
        
        for conflict in conflicts:
            conflict_record = SyncConflict.objects.create(
                sync_record=sync_record,
                conflict_type='data_mismatch',
                field_name=conflict['field_name'],
                local_value=conflict['local_value'],
                creatio_value=conflict['creatio_value']
            )
            conflict_records.append(conflict_record)
        
        return conflict_records
    
    def create_competitive_intelligence(
        self,
        lead: Lead,
        meeting: Meeting,
        extracted_data: Dict[str, Any],
        user: User
    ) -> List[Dict[str, Any]]:
        """
        Create competitive intelligence records from extracted data
        """
        competitive_intel = extracted_data.get('competitive_intelligence', [])
        created_records = []
        
        for intel in competitive_intel:
            try:
                # Check if we already have intel for this competitor
                existing_intel = CompetitiveIntelligence.objects.filter(
                    lead=lead,
                    competitor_name__iexact=intel.get('competitor_name', '')
                ).first()
                
                if existing_intel:
                    # Update existing record
                    existing_intel.competitive_context = intel.get('context', '')
                    existing_intel.strengths_mentioned = intel.get('strengths', [])
                    existing_intel.weaknesses_mentioned = intel.get('weaknesses', [])
                    
                    if intel.get('pricing_info'):
                        existing_intel.pricing_intelligence = intel.get('pricing_info', {})
                    
                    existing_intel.threat_level = intel.get('threat_level', 'medium')
                    existing_intel.relationship_status = intel.get('relationship', 'unknown')
                    existing_intel.save()
                    
                    created_records.append({
                        'id': str(existing_intel.id),
                        'action': 'updated',
                        'competitor': intel.get('competitor_name')
                    })
                else:
                    # Create new record
                    new_intel = CompetitiveIntelligence.objects.create(
                        lead=lead,
                        meeting=meeting,
                        competitor_name=intel.get('competitor_name', 'Unknown'),
                        competitive_context=intel.get('context', ''),
                        strengths_mentioned=intel.get('strengths', []),
                        weaknesses_mentioned=intel.get('weaknesses', []),
                        pricing_intelligence=intel.get('pricing_info', {}),
                        threat_level=intel.get('threat_level', 'medium'),
                        relationship_status=intel.get('relationship', 'unknown')
                    )
                    
                    created_records.append({
                        'id': str(new_intel.id),
                        'action': 'created',
                        'competitor': intel.get('competitor_name')
                    })
                
                # Schedule sync to Creatio if configured
                self.schedule_competitive_intel_sync(lead, intel)
                
            except Exception as e:
                logger.error(f"Error creating competitive intelligence for lead {lead.id}: {str(e)}")
                created_records.append({
                    'error': str(e),
                    'competitor': intel.get('competitor_name', 'Unknown')
                })
        
        return created_records
    
    def create_action_items(
        self,
        meeting: Meeting,
        extracted_data: Dict[str, Any],
        user: User
    ) -> List[Dict[str, Any]]:
        """
        Create action items from extracted data
        """
        action_items = extracted_data.get('action_items', [])
        created_items = []
        
        for item in action_items:
            try:
                # Determine owner user if internal
                owner_user = None
                if item.get('owner') and 'internal' in item.get('owner', '').lower():
                    # Try to match with actual user
                    owner_user = user  # Default to current user
                
                # Parse due date
                due_date = None
                if item.get('deadline'):
                    due_date = self.field_mapper._parse_date(item['deadline'])
                
                action_item = ActionItem.objects.create(
                    meeting=meeting,
                    description=item.get('description', ''),
                    owner=item.get('owner', 'Unknown'),
                    owner_user=owner_user,
                    due_date=due_date,
                    priority=item.get('priority', 'medium'),
                    is_commitment=item.get('commitment_level') == 'firm',
                    is_internal=owner_user is not None
                )
                
                # Link to lead if single participant
                participants = meeting.participants.filter(matched_lead__isnull=False)
                if participants.count() == 1:
                    action_item.lead = participants.first().matched_lead
                    action_item.save()
                
                created_items.append({
                    'id': str(action_item.id),
                    'description': item.get('description', ''),
                    'owner': item.get('owner', ''),
                    'due_date': due_date.isoformat() if due_date else None,
                    'priority': item.get('priority', 'medium')
                })
                
                # Schedule sync to Creatio as task/activity
                self.schedule_activity_sync(action_item)
                
            except Exception as e:
                logger.error(f"Error creating action item for meeting {meeting.id}: {str(e)}")
                created_items.append({
                    'error': str(e),
                    'description': item.get('description', 'Unknown')
                })
        
        return created_items
    
    def create_opportunity_if_warranted(
        self,
        lead: Lead,
        meeting: Meeting,
        extracted_data: Dict[str, Any],
        user: User
    ) -> Optional[Dict[str, Any]]:
        """
        Create opportunity in Creatio if meeting indicates strong buying signals
        """
        try:
            opportunity_data = self.field_mapper.create_opportunity_from_meeting(
                lead, meeting, extracted_data
            )
            
            if not opportunity_data:
                return None
            
            # Create opportunity in Creatio
            response = self.adapter._make_request(
                'POST',
                '/0/odata/Opportunity',
                data=opportunity_data['opportunity_data']
            )
            
            opportunity_id = response.json().get('Id')
            
            if opportunity_id:
                # Create sync record
                CreatioSync.objects.create(
                    entity_type='opportunity',
                    local_id=meeting.id,  # Use meeting as local reference
                    creatio_id=opportunity_id,
                    sync_status='success',
                    sync_direction='to_creatio'
                )
                
                # Create note on lead
                LeadNote.objects.create(
                    lead=lead,
                    author=user,
                    title='Opportunity Created',
                    content=f"Opportunity created in Creatio based on meeting on {meeting.start_time.date()}",
                    note_type='ai_insight',
                    ai_generated=True,
                    ai_confidence=opportunity_data['confidence']
                )
                
                return {
                    'opportunity_id': opportunity_id,
                    'lead_id': str(lead.id),
                    'confidence': opportunity_data['confidence'],
                    'created_at': timezone.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"Error creating opportunity for lead {lead.id}: {str(e)}")
            return {
                'error': str(e),
                'lead_id': str(lead.id)
            }
        
        return None
    
    def update_meeting_outcome(
        self,
        meeting: Meeting,
        extracted_data: Dict[str, Any]
    ):
        """
        Update meeting with outcome data
        """
        try:
            meeting_outcome = extracted_data.get('meeting_outcome', {})
            
            if meeting_outcome:
                # Store outcome data in meeting
                if not hasattr(meeting, 'outcome_data'):
                    meeting.outcome_data = {}
                
                meeting.outcome_data.update({
                    'sentiment': meeting_outcome.get('overall_sentiment'),
                    'interest_level': meeting_outcome.get('customer_interest_level'),
                    'likelihood_to_proceed': meeting_outcome.get('likelihood_to_proceed'),
                    'next_steps_clarity': meeting_outcome.get('next_steps_clarity'),
                    'summary': meeting_outcome.get('summary'),
                    'updated_at': timezone.now().isoformat()
                })
                
                meeting.save()
        
        except Exception as e:
            logger.error(f"Error updating meeting outcome for meeting {meeting.id}: {str(e)}")
    
    def create_update_note(
        self,
        lead: Lead,
        changes_made: List[str],
        extracted_data: Dict[str, Any],
        user: User
    ):
        """
        Create a note documenting the updates made
        """
        try:
            if not changes_made:
                return
            
            changes_summary = ', '.join(changes_made)
            confidence = extracted_data.get('overall_confidence', 0.5)
            
            note_content = f"""Lead updated from meeting intelligence:
            
Changes made: {changes_summary}
AI Confidence: {confidence:.2f}

Key insights:
"""
            
            # Add key insights from extracted data
            meeting_outcome = extracted_data.get('meeting_outcome', {})
            if meeting_outcome.get('summary'):
                note_content += f"- {meeting_outcome['summary']}\n"
            
            deal_info = extracted_data.get('deal_information', {})
            if deal_info.get('budget', {}).get('amount'):
                note_content += f"- Budget discussed: {deal_info['budget']['amount']}\n"
            
            if deal_info.get('timeline', {}).get('decision_date'):
                note_content += f"- Decision timeline: {deal_info['timeline']['decision_date']}\n"
            
            LeadNote.objects.create(
                lead=lead,
                author=user,
                title='Meeting Intelligence Update',
                content=note_content,
                note_type='ai_insight',
                ai_generated=True,
                ai_confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error creating update note for lead {lead.id}: {str(e)}")
    
    def schedule_crm_sync(self, entity, entity_type: str):
        """
        Schedule entity for CRM synchronization
        """
        try:
            sync_record, created = CreatioSync.objects.get_or_create(
                entity_type=entity_type,
                local_id=entity.id,
                defaults={
                    'sync_status': 'pending',
                    'sync_direction': 'to_creatio',
                    'next_sync': timezone.now()
                }
            )
            
            if not created and sync_record.sync_status != 'pending':
                sync_record.sync_status = 'pending'
                sync_record.next_sync = timezone.now()
                sync_record.save()
        
        except Exception as e:
            logger.error(f"Error scheduling CRM sync for {entity_type} {entity.id}: {str(e)}")
    
    def schedule_competitive_intel_sync(self, lead: Lead, intel_data: Dict[str, Any]):
        """
        Schedule competitive intelligence sync to CRM
        """
        # This would depend on Creatio's competitive intelligence fields
        # For now, we'll log the intent
        logger.info(f"Competitive intelligence sync scheduled for lead {lead.id}: {intel_data.get('competitor_name')}")
    
    def schedule_activity_sync(self, action_item: ActionItem):
        """
        Schedule action item sync to CRM as activity
        """
        try:
            sync_record = CreatioSync.objects.create(
                entity_type='activity',
                local_id=action_item.id,
                sync_status='pending',
                sync_direction='to_creatio',
                next_sync=timezone.now()
            )
            
            logger.info(f"Activity sync scheduled for action item {action_item.id}")
        
        except Exception as e:
            logger.error(f"Error scheduling activity sync for action item {action_item.id}: {str(e)}")


class OpportunityProgressionTracker:
    """
    Tracks opportunity progression and stage updates
    """
    
    def __init__(self):
        self.adapter = CreatioAdapter()
    
    def track_progression(
        self,
        lead: Lead,
        meeting: Meeting,
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track opportunity progression based on meeting data
        """
        try:
            progression_data = {
                'lead_id': str(lead.id),
                'meeting_id': str(meeting.id),
                'previous_stage': lead.relationship_stage,
                'progression_indicators': [],
                'recommended_actions': []
            }
            
            # Analyze progression indicators
            meeting_outcome = extracted_data.get('meeting_outcome', {})
            deal_info = extracted_data.get('deal_information', {})
            
            # Budget progression
            if deal_info.get('budget', {}).get('amount'):
                progression_data['progression_indicators'].append({
                    'type': 'budget_discussion',
                    'value': deal_info['budget']['amount'],
                    'impact': 'positive'
                })
            
            # Timeline progression
            if deal_info.get('timeline', {}).get('decision_date'):
                progression_data['progression_indicators'].append({
                    'type': 'timeline_clarity',
                    'value': deal_info['timeline']['decision_date'],
                    'impact': 'positive'
                })
            
            # Interest level
            interest_level = meeting_outcome.get('customer_interest_level')
            if interest_level:
                progression_data['progression_indicators'].append({
                    'type': 'interest_level',
                    'value': interest_level,
                    'impact': 'positive' if interest_level in ['high', 'medium'] else 'neutral'
                })
            
            # Determine new stage
            new_stage = self._calculate_new_stage(lead, progression_data['progression_indicators'])
            progression_data['new_stage'] = new_stage
            
            # Generate recommendations
            progression_data['recommended_actions'] = self._generate_progression_recommendations(
                lead, progression_data['progression_indicators']
            )
            
            return progression_data
            
        except Exception as e:
            logger.error(f"Error tracking opportunity progression for lead {lead.id}: {str(e)}")
            return {
                'error': str(e),
                'lead_id': str(lead.id)
            }
    
    def _calculate_new_stage(self, lead: Lead, indicators: List[Dict[str, Any]]) -> str:
        """
        Calculate new relationship stage based on progression indicators
        """
        current_stage = lead.relationship_stage or 'cold'
        
        # Count positive indicators
        positive_indicators = [i for i in indicators if i['impact'] == 'positive']
        
        # Stage progression logic
        if len(positive_indicators) >= 3:
            if current_stage in ['cold', 'warm']:
                return 'hot'
            elif current_stage == 'hot':
                return 'engaged'
        elif len(positive_indicators) >= 2:
            if current_stage == 'cold':
                return 'warm'
            elif current_stage == 'warm':
                return 'hot'
        elif len(positive_indicators) >= 1:
            if current_stage == 'cold':
                return 'warm'
        
        return current_stage
    
    def _generate_progression_recommendations(
        self,
        lead: Lead,
        indicators: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate recommendations based on progression indicators
        """
        recommendations = []
        
        # Check for missing qualification elements
        has_budget = any(i['type'] == 'budget_discussion' for i in indicators)
        has_timeline = any(i['type'] == 'timeline_clarity' for i in indicators)
        has_high_interest = any(i['type'] == 'interest_level' and i['value'] == 'high' for i in indicators)
        
        if not has_budget:
            recommendations.append("Discuss budget and financial authority in next meeting")
        
        if not has_timeline:
            recommendations.append("Clarify decision timeline and implementation schedule")
        
        if not has_high_interest:
            recommendations.append("Focus on value proposition and business impact")
        
        # Stage-specific recommendations
        if lead.relationship_stage == 'hot' and has_budget and has_timeline:
            recommendations.append("Consider moving to proposal stage")
        
        if lead.relationship_stage == 'engaged':
            recommendations.append("Schedule decision maker meeting")
        
        return recommendations