"""
CRM Field Mapping and Data Update Service
Handles automatic field mapping from extracted data to Creatio fields
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User

from .models import CreatioSync, SyncConflict, CreatioConfiguration
from .adapters import CreatioAdapter
from apps.leads.models import Lead, ActionItem, CompetitiveIntelligence, LeadNote
from apps.meetings.models import Meeting
from apps.debriefings.models import DebriefingSession

logger = logging.getLogger(__name__)


class FieldMappingService:
    """
    Service for mapping extracted data to CRM fields
    """
    
    def __init__(self):
        self.adapter = CreatioAdapter()
        self._field_mappings = {}
        self._load_field_mappings()
    
    def _load_field_mappings(self):
        """Load field mappings from configuration"""
        try:
            # Load lead field mappings
            lead_config = CreatioConfiguration.objects.get(
                config_key='lead_field_mapping',
                is_active=True
            )
            self._field_mappings['lead'] = lead_config.config_value
        except CreatioConfiguration.DoesNotExist:
            self._field_mappings['lead'] = self._get_default_lead_mapping()
        
        try:
            # Load opportunity field mappings
            opp_config = CreatioConfiguration.objects.get(
                config_key='opportunity_field_mapping',
                is_active=True
            )
            self._field_mappings['opportunity'] = opp_config.config_value
        except CreatioConfiguration.DoesNotExist:
            self._field_mappings['opportunity'] = self._get_default_opportunity_mapping()
        
        try:
            # Load activity field mappings
            activity_config = CreatioConfiguration.objects.get(
                config_key='activity_field_mapping',
                is_active=True
            )
            self._field_mappings['activity'] = activity_config.config_value
        except CreatioConfiguration.DoesNotExist:
            self._field_mappings['activity'] = self._get_default_activity_mapping()
    
    def _get_default_lead_mapping(self) -> Dict[str, str]:
        """Get default lead field mapping"""
        return {
            'first_name': 'Name',
            'last_name': 'Surname',
            'email': 'Email',
            'phone': 'MobilePhone',
            'company': 'AccountName',
            'title': 'JobTitle',
            'status': 'QualifyStatus',
            'qualification_score': 'Score',
            'estimated_budget': 'Budget',
            'estimated_close_date': 'DecisionDate',
            'probability': 'Probability',
            'source': 'LeadSource',
            'relationship_stage': 'LeadStage',
            'decision_authority': 'DecisionRole',
            'industry': 'Industry',
            'company_size': 'CompanySize',
            'department': 'Department',
            'website': 'Website',
            'last_meeting_date': 'LastMeetingDate',
            'meeting_count': 'MeetingCount'
        }
    
    def _get_default_opportunity_mapping(self) -> Dict[str, str]:
        """Get default opportunity field mapping"""
        return {
            'title': 'Title',
            'amount': 'Amount',
            'close_date': 'DueDate',
            'probability': 'Probability',
            'stage': 'Stage',
            'source': 'Source',
            'description': 'Description',
            'next_step': 'NextStep',
            'decision_date': 'DecisionDate',
            'budget_confirmed': 'BudgetConfirmed',
            'authority_confirmed': 'AuthorityConfirmed',
            'need_confirmed': 'NeedConfirmed',
            'timeline_confirmed': 'TimelineConfirmed'
        }
    
    def _get_default_activity_mapping(self) -> Dict[str, str]:
        """Get default activity field mapping"""
        return {
            'title': 'Title',
            'description': 'DetailedResult',
            'start_time': 'StartDate',
            'end_time': 'DueDate',
            'activity_type': 'ActivityCategory',
            'status': 'Status',
            'priority': 'Priority',
            'owner': 'Owner',
            'account': 'Account',
            'contact': 'Contact',
            'result': 'Result'
        }
    
    def map_extracted_data_to_lead(
        self,
        extracted_data: Dict[str, Any],
        lead: Lead,
        meeting: Meeting
    ) -> Dict[str, Any]:
        """
        Map extracted data to lead fields
        """
        mapped_data = {}
        changes_made = []
        
        try:
            # Map contact information
            contacts = extracted_data.get('contacts', [])
            if contacts:
                primary_contact = contacts[0]  # Use first contact as primary
                
                # Update contact details if confidence is high
                if primary_contact.get('confidence', 0) > 0.7:
                    if 'name' in primary_contact and primary_contact['name']:
                        name_parts = primary_contact['name'].split(' ', 1)
                        if len(name_parts) >= 2:
                            if not lead.first_name or lead.first_name.lower() == 'unknown':
                                mapped_data['first_name'] = name_parts[0]
                                changes_made.append('first_name')
                            if not lead.last_name or lead.last_name.lower() == 'unknown':
                                mapped_data['last_name'] = name_parts[1]
                                changes_made.append('last_name')
                    
                    if 'title' in primary_contact and primary_contact['title']:
                        if not lead.title or primary_contact.get('confidence', 0) > 0.8:
                            mapped_data['title'] = primary_contact['title']
                            changes_made.append('title')
                    
                    if 'company' in primary_contact and primary_contact['company']:
                        if not lead.company or primary_contact.get('confidence', 0) > 0.8:
                            mapped_data['company'] = primary_contact['company']
                            changes_made.append('company')
            
            # Map deal information
            deal_info = extracted_data.get('deal_information', {})
            if deal_info:
                # Budget information
                budget = deal_info.get('budget', {})
                if budget.get('amount'):
                    try:
                        budget_amount = self._parse_budget_amount(budget['amount'])
                        if budget_amount and (not lead.estimated_budget or budget_amount > lead.estimated_budget):
                            mapped_data['estimated_budget'] = budget_amount
                            changes_made.append('estimated_budget')
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse budget amount: {budget.get('amount')}")
                
                # Timeline information
                timeline = deal_info.get('timeline', {})
                if timeline.get('decision_date'):
                    try:
                        decision_date = self._parse_date(timeline['decision_date'])
                        if decision_date and (not lead.estimated_close_date or decision_date != lead.estimated_close_date):
                            mapped_data['estimated_close_date'] = decision_date
                            changes_made.append('estimated_close_date')
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse decision date: {timeline.get('decision_date')}")
                
                # Decision makers
                decision_makers = deal_info.get('decision_makers', [])
                if decision_makers:
                    # Update decision authority based on identified decision makers
                    for dm in decision_makers:
                        if dm.get('role_in_decision') == 'final_decision_maker':
                            mapped_data['decision_authority'] = 'decision_maker'
                            changes_made.append('decision_authority')
                            break
                        elif dm.get('role_in_decision') == 'influencer':
                            if lead.decision_authority == 'unknown':
                                mapped_data['decision_authority'] = 'influencer'
                                changes_made.append('decision_authority')
            
            # Map meeting outcome to relationship stage
            meeting_outcome = extracted_data.get('meeting_outcome', {})
            if meeting_outcome:
                sentiment = meeting_outcome.get('overall_sentiment')
                interest_level = meeting_outcome.get('customer_interest_level')
                
                if sentiment == 'positive' and interest_level == 'high':
                    if lead.relationship_stage in ['cold', 'warm']:
                        mapped_data['relationship_stage'] = 'hot'
                        changes_made.append('relationship_stage')
                elif sentiment == 'positive' and interest_level == 'medium':
                    if lead.relationship_stage == 'cold':
                        mapped_data['relationship_stage'] = 'warm'
                        changes_made.append('relationship_stage')
                elif sentiment == 'negative':
                    # Don't downgrade automatically, but log for review
                    logger.info(f"Negative sentiment detected for lead {lead.id}, manual review recommended")
            
            # Update qualification score based on extracted insights
            qualification_updates = self._calculate_qualification_updates(extracted_data, lead)
            if qualification_updates:
                new_score = min(lead.qualification_score + qualification_updates, 100)
                if new_score != lead.qualification_score:
                    mapped_data['qualification_score'] = new_score
                    changes_made.append('qualification_score')
            
            # Update meeting statistics
            mapped_data['last_meeting_date'] = meeting.start_time
            mapped_data['meeting_count'] = lead.meeting_count + 1
            changes_made.extend(['last_meeting_date', 'meeting_count'])
            
            return {
                'mapped_data': mapped_data,
                'changes_made': changes_made,
                'confidence_score': self._calculate_mapping_confidence(extracted_data)
            }
            
        except Exception as e:
            logger.error(f"Error mapping extracted data to lead {lead.id}: {str(e)}")
            return {
                'mapped_data': {},
                'changes_made': [],
                'error': str(e)
            }
    
    def _parse_budget_amount(self, budget_str: str) -> Optional[Decimal]:
        """Parse budget amount from string"""
        if not budget_str:
            return None
        
        # Remove currency symbols and common formatting
        cleaned = str(budget_str).replace('$', '').replace(',', '').replace(' ', '')
        
        # Handle 'k' and 'million' suffixes
        if 'k' in cleaned.lower():
            cleaned = cleaned.lower().replace('k', '')
            try:
                return Decimal(cleaned) * 1000
            except:
                return None
        elif 'million' in cleaned.lower():
            cleaned = cleaned.lower().replace('million', '')
            try:
                return Decimal(cleaned) * 1000000
            except:
                return None
        else:
            try:
                return Decimal(cleaned)
            except:
                return None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date from string"""
        if not date_str:
            return None
        
        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%Y-%m-%d %H:%M:%S',
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(str(date_str), fmt).date()
                return parsed_date
            except ValueError:
                continue
        
        return None
    
    def _calculate_qualification_updates(self, extracted_data: Dict[str, Any], lead: Lead) -> int:
        """Calculate qualification score updates based on extracted data"""
        score_updates = 0
        
        # Budget discussion
        deal_info = extracted_data.get('deal_information', {})
        if deal_info.get('budget', {}).get('amount'):
            score_updates += 15
        
        # Timeline discussion
        if deal_info.get('timeline', {}).get('decision_date'):
            score_updates += 10
        
        # Decision maker identification
        decision_makers = deal_info.get('decision_makers', [])
        if any(dm.get('role_in_decision') == 'final_decision_maker' for dm in decision_makers):
            score_updates += 20
        
        # Requirements discussion
        requirements = deal_info.get('requirements', [])
        if requirements:
            score_updates += 10
        
        # Positive meeting outcome
        meeting_outcome = extracted_data.get('meeting_outcome', {})
        if meeting_outcome.get('overall_sentiment') == 'positive':
            score_updates += 5
        
        # High interest level
        if meeting_outcome.get('customer_interest_level') == 'high':
            score_updates += 10
        
        return score_updates
    
    def _calculate_mapping_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """Calculate overall confidence for the mapping"""
        confidence_scores = []
        
        # Collect confidence scores from extracted data
        for key, value in extracted_data.items():
            if isinstance(value, dict) and 'extraction_confidence' in value:
                confidence_scores.append(value['extraction_confidence'])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'confidence' in item:
                        confidence_scores.append(item['confidence'])
        
        if confidence_scores:
            return sum(confidence_scores) / len(confidence_scores)
        else:
            return 0.5
    
    def create_opportunity_from_meeting(
        self,
        lead: Lead,
        meeting: Meeting,
        extracted_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create opportunity record in Creatio based on meeting data
        """
        try:
            deal_info = extracted_data.get('deal_information', {})
            meeting_outcome = extracted_data.get('meeting_outcome', {})
            
            # Only create opportunity if there are strong buying signals
            if (meeting_outcome.get('customer_interest_level') == 'high' and 
                meeting_outcome.get('likelihood_to_proceed') in ['high', 'medium']):
                
                opportunity_data = {
                    'Title': f"Opportunity - {lead.company}",
                    'AccountId': lead.creatio_id,  # Link to lead/contact
                    'Amount': self._parse_budget_amount(deal_info.get('budget', {}).get('amount', '0')) or 0,
                    'DueDate': self._parse_date(deal_info.get('timeline', {}).get('decision_date', '')),
                    'Probability': self._calculate_opportunity_probability(extracted_data),
                    'Stage': self._determine_opportunity_stage(extracted_data),
                    'Source': 'Meeting Intelligence',
                    'Description': f"Opportunity created from meeting on {meeting.start_time.date()}",
                    'NextStep': self._determine_next_steps(extracted_data)
                }
                
                # Remove None values
                opportunity_data = {k: v for k, v in opportunity_data.items() if v is not None}
                
                return {
                    'opportunity_data': opportunity_data,
                    'confidence': meeting_outcome.get('confidence_level', 0.5)
                }
        
        except Exception as e:
            logger.error(f"Error creating opportunity data for lead {lead.id}: {str(e)}")
        
        return None
    
    def _calculate_opportunity_probability(self, extracted_data: Dict[str, Any]) -> int:
        """Calculate opportunity probability based on extracted data"""
        base_probability = 20
        
        meeting_outcome = extracted_data.get('meeting_outcome', {})
        deal_info = extracted_data.get('deal_information', {})
        
        # Interest level
        interest_level = meeting_outcome.get('customer_interest_level')
        if interest_level == 'high':
            base_probability += 30
        elif interest_level == 'medium':
            base_probability += 15
        
        # Budget discussion
        if deal_info.get('budget', {}).get('amount'):
            base_probability += 20
        
        # Timeline clarity
        if deal_info.get('timeline', {}).get('decision_date'):
            base_probability += 15
        
        # Decision maker involvement
        decision_makers = deal_info.get('decision_makers', [])
        if any(dm.get('role_in_decision') == 'final_decision_maker' for dm in decision_makers):
            base_probability += 15
        
        return min(base_probability, 100)
    
    def _determine_opportunity_stage(self, extracted_data: Dict[str, Any]) -> str:
        """Determine opportunity stage based on extracted data"""
        deal_info = extracted_data.get('deal_information', {})
        meeting_outcome = extracted_data.get('meeting_outcome', {})
        
        # Check for negotiation indicators
        if any('price' in str(req).lower() or 'cost' in str(req).lower() 
               for req in deal_info.get('requirements', [])):
            return 'Negotiation'
        
        # Check for proposal stage
        if meeting_outcome.get('likelihood_to_proceed') == 'high':
            return 'Proposal'
        
        # Check for qualification stage
        if deal_info.get('budget') and deal_info.get('timeline'):
            return 'Qualification'
        
        # Default to discovery
        return 'Discovery'
    
    def _determine_next_steps(self, extracted_data: Dict[str, Any]) -> str:
        """Determine next steps based on action items"""
        action_items = extracted_data.get('action_items', [])
        
        if action_items:
            # Get highest priority action items
            high_priority_items = [
                item for item in action_items 
                if item.get('priority') in ['high', 'urgent']
            ]
            
            if high_priority_items:
                return f"Next: {high_priority_items[0].get('description', 'Follow up')}"
            else:
                return f"Next: {action_items[0].get('description', 'Follow up')}"
        
        return "Follow up on meeting discussion"


class DataConflictDetector:
    """
    Detects and handles data conflicts during CRM updates
    """
    
    def __init__(self):
        self.adapter = CreatioAdapter()
    
    def detect_conflicts(
        self,
        local_data: Dict[str, Any],
        creatio_data: Dict[str, Any],
        field_mapping: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts between local and Creatio data
        """
        conflicts = []
        
        for local_field, creatio_field in field_mapping.items():
            if creatio_field in creatio_data:
                local_value = local_data.get(local_field)
                creatio_value = creatio_data.get(creatio_field)
                
                # Normalize values for comparison
                normalized_local = self._normalize_value(local_value)
                normalized_creatio = self._normalize_value(creatio_value)
                
                if normalized_local != normalized_creatio:
                    conflicts.append({
                        'field_name': local_field,
                        'creatio_field': creatio_field,
                        'local_value': local_value,
                        'creatio_value': creatio_value,
                        'conflict_type': self._classify_conflict_type(local_value, creatio_value),
                        'severity': self._assess_conflict_severity(local_field, local_value, creatio_value)
                    })
        
        return conflicts
    
    def _normalize_value(self, value):
        """Normalize values for comparison"""
        if value is None:
            return None
        elif isinstance(value, str):
            return value.strip().lower()
        elif isinstance(value, (int, float, Decimal)):
            return float(value)
        elif isinstance(value, (date, datetime)):
            return value.isoformat() if hasattr(value, 'isoformat') else str(value)
        else:
            return str(value).strip().lower()
    
    def _classify_conflict_type(self, local_value, creatio_value) -> str:
        """Classify the type of conflict"""
        if local_value is None and creatio_value is not None:
            return 'local_missing'
        elif local_value is not None and creatio_value is None:
            return 'creatio_missing'
        elif isinstance(local_value, str) and isinstance(creatio_value, str):
            if local_value.lower() in creatio_value.lower() or creatio_value.lower() in local_value.lower():
                return 'partial_match'
            else:
                return 'value_mismatch'
        else:
            return 'value_mismatch'
    
    def _assess_conflict_severity(self, field_name: str, local_value, creatio_value) -> str:
        """Assess the severity of the conflict"""
        # Critical fields that should not have conflicts
        critical_fields = ['email', 'first_name', 'last_name', 'company']
        
        # Important fields that need attention
        important_fields = ['phone', 'title', 'estimated_budget', 'estimated_close_date']
        
        if field_name in critical_fields:
            return 'high'
        elif field_name in important_fields:
            return 'medium'
        else:
            return 'low'
    
    def create_conflict_resolution_workflow(
        self,
        conflicts: List[Dict[str, Any]],
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """
        Create a workflow for resolving conflicts
        """
        workflow = {
            'entity_type': entity_type,
            'entity_id': entity_id,
            'total_conflicts': len(conflicts),
            'high_severity_conflicts': len([c for c in conflicts if c['severity'] == 'high']),
            'auto_resolvable': [],
            'requires_review': [],
            'recommended_actions': []
        }
        
        for conflict in conflicts:
            if self._can_auto_resolve(conflict):
                workflow['auto_resolvable'].append({
                    'field': conflict['field_name'],
                    'resolution': self._get_auto_resolution(conflict),
                    'reason': self._get_auto_resolution_reason(conflict)
                })
            else:
                workflow['requires_review'].append(conflict)
        
        # Generate recommended actions
        if workflow['high_severity_conflicts'] > 0:
            workflow['recommended_actions'].append('Immediate review required for critical field conflicts')
        
        if len(workflow['auto_resolvable']) > 0:
            workflow['recommended_actions'].append(f"Auto-resolve {len(workflow['auto_resolvable'])} low-risk conflicts")
        
        return workflow
    
    def _can_auto_resolve(self, conflict: Dict[str, Any]) -> bool:
        """Determine if conflict can be auto-resolved"""
        # Auto-resolve low severity conflicts with specific patterns
        if conflict['severity'] == 'low':
            return True
        
        # Auto-resolve partial matches in non-critical fields
        if (conflict['conflict_type'] == 'partial_match' and 
            conflict['severity'] != 'high'):
            return True
        
        # Auto-resolve missing values by taking the non-null value
        if conflict['conflict_type'] in ['local_missing', 'creatio_missing']:
            return True
        
        return False
    
    def _get_auto_resolution(self, conflict: Dict[str, Any]) -> str:
        """Get auto-resolution strategy"""
        if conflict['conflict_type'] == 'local_missing':
            return 'use_creatio_value'
        elif conflict['conflict_type'] == 'creatio_missing':
            return 'use_local_value'
        elif conflict['conflict_type'] == 'partial_match':
            return 'use_longer_value'
        else:
            return 'use_local_value'  # Default to local value for meeting-derived data
    
    def _get_auto_resolution_reason(self, conflict: Dict[str, Any]) -> str:
        """Get reason for auto-resolution"""
        resolution_reasons = {
            'use_creatio_value': 'Local value is missing, using Creatio value',
            'use_local_value': 'Meeting-derived data takes precedence',
            'use_longer_value': 'Using more complete value',
        }
        
        resolution = self._get_auto_resolution(conflict)
        return resolution_reasons.get(resolution, 'Auto-resolved based on conflict type')