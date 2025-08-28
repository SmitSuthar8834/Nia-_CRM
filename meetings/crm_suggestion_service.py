"""
CRM update suggestion service
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import re


class CRMSystem(Enum):
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    CREATIO = "creatio"


class OpportunityStage(Enum):
    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    NEEDS_ANALYSIS = "needs_analysis"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ReminderType(Enum):
    EMAIL = "email"
    CALENDAR = "calendar"
    TASK = "task"
    NOTIFICATION = "notification"


@dataclass
class OpportunitySuggestion:
    current_stage: str
    suggested_stage: OpportunityStage
    confidence: float
    reasoning: str
    supporting_evidence: List[str]


@dataclass
class FollowUpTask:
    title: str
    description: str
    priority: TaskPriority
    due_date: datetime
    assignee: Optional[str] = None
    task_type: str = "follow_up"
    estimated_duration: Optional[int] = None  # minutes
    crm_category: Optional[str] = None


@dataclass
class ReminderSuggestion:
    reminder_type: ReminderType
    title: str
    description: str
    reminder_date: datetime
    recipient: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM


@dataclass
class CRMFieldMapping:
    field_name: str
    field_value: Any
    field_type: str  # 'text', 'picklist', 'date', 'number', 'boolean'
    confidence: float
    source_evidence: List[str]


@dataclass
class CRMUpdateSuggestion:
    crm_system: CRMSystem
    field_updates: Dict[str, Any]
    field_mappings: List[CRMFieldMapping]
    opportunity_suggestion: Optional[OpportunitySuggestion]
    follow_up_tasks: List[FollowUpTask]
    reminder_suggestions: List[ReminderSuggestion]
    confidence_score: float
    validation_notes: List[str]
    suggested_next_meeting: Optional[datetime] = None
    deal_value_estimate: Optional[float] = None


class CRMSuggestionService:
    def __init__(self):
        self.field_mappings = {
            CRMSystem.SALESFORCE: {
                'notes': {'field': 'Description', 'type': 'text'},
                'key_points': {'field': 'Key_Points__c', 'type': 'text'},
                'decisions': {'field': 'Decisions_Made__c', 'type': 'text'},
                'outcome': {'field': 'Meeting_Outcome__c', 'type': 'picklist'},
                'next_steps': {'field': 'Next_Steps__c', 'type': 'text'},
                'deal_stage': {'field': 'StageName', 'type': 'picklist'},
                'amount': {'field': 'Amount', 'type': 'number'},
                'close_date': {'field': 'CloseDate', 'type': 'date'},
                'probability': {'field': 'Probability', 'type': 'number'}
            },
            CRMSystem.HUBSPOT: {
                'notes': {'field': 'hs_meeting_body', 'type': 'text'},
                'key_points': {'field': 'custom_key_points', 'type': 'text'},
                'decisions': {'field': 'custom_decisions', 'type': 'text'},
                'outcome': {'field': 'hs_meeting_outcome', 'type': 'picklist'},
                'next_steps': {'field': 'hs_meeting_notes', 'type': 'text'},
                'deal_stage': {'field': 'dealstage', 'type': 'picklist'},
                'amount': {'field': 'amount', 'type': 'number'},
                'close_date': {'field': 'closedate', 'type': 'date'},
                'probability': {'field': 'hs_deal_stage_probability', 'type': 'number'}
            },
            CRMSystem.CREATIO: {
                'notes': {'field': 'Notes', 'type': 'text'},
                'key_points': {'field': 'KeyPoints', 'type': 'text'},
                'decisions': {'field': 'Decisions', 'type': 'text'},
                'outcome': {'field': 'Outcome', 'type': 'picklist'},
                'next_steps': {'field': 'NextSteps', 'type': 'text'},
                'deal_stage': {'field': 'Stage', 'type': 'picklist'},
                'amount': {'field': 'Budget', 'type': 'number'},
                'close_date': {'field': 'DueDate', 'type': 'date'},
                'probability': {'field': 'Probability', 'type': 'number'}
            }
        }
        
        self.stage_keywords = {
            OpportunityStage.PROSPECTING: ['initial contact', 'first meeting', 'introduction', 'cold call'],
            OpportunityStage.QUALIFICATION: ['budget', 'timeline', 'decision maker', 'authority', 'need', 'pain point'],
            OpportunityStage.NEEDS_ANALYSIS: ['requirements', 'analysis', 'discovery', 'assessment', 'evaluation'],
            OpportunityStage.PROPOSAL: ['proposal', 'quote', 'pricing', 'demo', 'presentation', 'solution'],
            OpportunityStage.NEGOTIATION: ['negotiation', 'contract', 'terms', 'pricing discussion', 'final details'],
            OpportunityStage.CLOSED_WON: ['signed', 'approved', 'moving forward', 'accepted', 'won', 'closed'],
            OpportunityStage.CLOSED_LOST: ['rejected', 'declined', 'lost', 'competitor', 'no budget', 'cancelled']
        }
        
        self.priority_keywords = {
            TaskPriority.URGENT: ['urgent', 'asap', 'immediately', 'critical', 'emergency'],
            TaskPriority.HIGH: ['high priority', 'important', 'soon', 'this week'],
            TaskPriority.MEDIUM: ['medium', 'normal', 'next week', 'follow up'],
            TaskPriority.LOW: ['low priority', 'when possible', 'eventually', 'nice to have']
        }
        
        self.value_patterns = [
            r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $1,000.00
            r'([0-9,]+(?:\.[0-9]{2})?) dollars?',  # 1000 dollars
            r'([0-9,]+)k',  # 50k
            r'([0-9,]+) thousand',  # 50 thousand
        ]
    
    def generate_crm_suggestions(
        self,
        meeting_summary: str,
        action_items: List[Dict],
        key_points: List[str],
        decisions_made: List[str],
        crm_system: CRMSystem,
        current_opportunity_stage: Optional[str] = None,
        current_deal_value: Optional[float] = None
    ) -> CRMUpdateSuggestion:
        
        all_text = f"{meeting_summary} {' '.join(key_points)} {' '.join(decisions_made)}".lower()
        
        # Generate field mappings and updates
        field_mappings, field_updates = self._generate_field_mappings(
            meeting_summary, key_points, decisions_made, crm_system, all_text
        )
        
        # Generate opportunity stage suggestion
        opportunity_suggestion = self._analyze_opportunity_stage(
            all_text, current_opportunity_stage
        )
        
        # Generate follow-up tasks
        follow_up_tasks = self._generate_follow_up_tasks(action_items, all_text)
        
        # Generate reminder suggestions
        reminder_suggestions = self._generate_reminder_suggestions(
            action_items, opportunity_suggestion
        )
        
        # Extract deal value estimate
        deal_value_estimate = self._extract_deal_value(all_text, current_deal_value)
        
        # Suggest next meeting
        suggested_next_meeting = self._suggest_next_meeting(all_text, opportunity_suggestion)
        
        # Calculate overall confidence score
        confidence_score = self._calculate_confidence_score(
            field_mappings, opportunity_suggestion, follow_up_tasks
        )
        
        # Generate validation notes
        validation_notes = self._generate_validation_notes(
            field_mappings, opportunity_suggestion, follow_up_tasks, deal_value_estimate
        )
        
        return CRMUpdateSuggestion(
            crm_system=crm_system,
            field_updates=field_updates,
            field_mappings=field_mappings,
            opportunity_suggestion=opportunity_suggestion,
            follow_up_tasks=follow_up_tasks,
            reminder_suggestions=reminder_suggestions,
            confidence_score=confidence_score,
            validation_notes=validation_notes,
            suggested_next_meeting=suggested_next_meeting,
            deal_value_estimate=deal_value_estimate
        )
    
    def _generate_field_mappings(
        self, 
        meeting_summary: str, 
        key_points: List[str], 
        decisions_made: List[str], 
        crm_system: CRMSystem,
        all_text: str
    ) -> Tuple[List[CRMFieldMapping], Dict[str, Any]]:
        """Generate CRM field mappings and updates"""
        field_mappings = []
        field_updates = {}
        mappings = self.field_mappings.get(crm_system, {})
        
        # Notes field
        if 'notes' in mappings:
            notes_content = self._format_notes(meeting_summary, key_points, decisions_made)
            field_config = mappings['notes']
            
            field_mappings.append(CRMFieldMapping(
                field_name=field_config['field'],
                field_value=notes_content,
                field_type=field_config['type'],
                confidence=0.95,
                source_evidence=['Meeting summary', 'Key points', 'Decisions']
            ))
            field_updates[field_config['field']] = notes_content
        
        # Key points field
        if 'key_points' in mappings and key_points:
            key_points_text = '\n'.join(f"• {point}" for point in key_points)
            field_config = mappings['key_points']
            
            field_mappings.append(CRMFieldMapping(
                field_name=field_config['field'],
                field_value=key_points_text,
                field_type=field_config['type'],
                confidence=0.9,
                source_evidence=key_points[:3]  # First 3 as evidence
            ))
            field_updates[field_config['field']] = key_points_text
        
        # Decisions field
        if 'decisions' in mappings and decisions_made:
            decisions_text = '\n'.join(f"• {decision}" for decision in decisions_made)
            field_config = mappings['decisions']
            
            field_mappings.append(CRMFieldMapping(
                field_name=field_config['field'],
                field_value=decisions_text,
                field_type=field_config['type'],
                confidence=0.85,
                source_evidence=decisions_made[:3]
            ))
            field_updates[field_config['field']] = decisions_text
        
        # Meeting outcome
        if 'outcome' in mappings:
            outcome = self._determine_meeting_outcome(all_text)
            if outcome:
                field_config = mappings['outcome']
                field_mappings.append(CRMFieldMapping(
                    field_name=field_config['field'],
                    field_value=outcome,
                    field_type=field_config['type'],
                    confidence=0.7,
                    source_evidence=[f"Inferred from: {outcome.lower()}"]
                ))
                field_updates[field_config['field']] = outcome
        
        return field_mappings, field_updates
    
    def _format_notes(self, summary: str, key_points: List[str], decisions: List[str]) -> str:
        """Format comprehensive meeting notes"""
        notes = [summary]
        
        if key_points:
            notes.append("\n--- Key Points ---")
            notes.extend(f"• {point}" for point in key_points)
        
        if decisions:
            notes.append("\n--- Decisions Made ---")
            notes.extend(f"• {decision}" for decision in decisions)
        
        notes.append(f"\n--- Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")
        
        return '\n'.join(notes)
    
    def _determine_meeting_outcome(self, text: str) -> Optional[str]:
        """Determine meeting outcome from text analysis"""
        positive_indicators = ['successful', 'productive', 'good meeting', 'progress', 'agreed']
        negative_indicators = ['cancelled', 'postponed', 'no show', 'unsuccessful']
        neutral_indicators = ['scheduled', 'rescheduled', 'follow up needed']
        
        if any(indicator in text for indicator in positive_indicators):
            return 'COMPLETED'
        elif any(indicator in text for indicator in negative_indicators):
            return 'CANCELLED'
        elif any(indicator in text for indicator in neutral_indicators):
            return 'RESCHEDULED'
        
        return 'COMPLETED'  # Default assumption
    
    def _analyze_opportunity_stage(
        self, 
        text: str, 
        current_stage: Optional[str]
    ) -> Optional[OpportunitySuggestion]:
        """Analyze and suggest opportunity stage changes"""
        stage_scores = {}
        
        for stage, keywords in self.stage_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                stage_scores[stage] = {
                    'score': score,
                    'confidence': min(score / len(keywords), 1.0),
                    'matched_keywords': [k for k in keywords if k in text]
                }
        
        if not stage_scores:
            return None
        
        # Find the stage with highest score
        best_stage = max(stage_scores.keys(), key=lambda s: stage_scores[s]['score'])
        best_score_data = stage_scores[best_stage]
        
        # Only suggest if confidence is reasonable
        if best_score_data['confidence'] > 0.3:
            return OpportunitySuggestion(
                current_stage=current_stage or "unknown",
                suggested_stage=best_stage,
                confidence=best_score_data['confidence'],
                reasoning=f"Detected {len(best_score_data['matched_keywords'])} relevant indicators",
                supporting_evidence=best_score_data['matched_keywords'][:5]
            )
        
        return None
    
    def _generate_follow_up_tasks(
        self, 
        action_items: List[Dict], 
        text: str
    ) -> List[FollowUpTask]:
        """Generate comprehensive follow-up tasks"""
        tasks = []
        
        # Process explicit action items
        for item in action_items:
            if item.get('description'):
                priority = self._determine_task_priority(item['description'], text)
                due_date = self._calculate_due_date(item.get('due_date'), priority)
                
                task = FollowUpTask(
                    title=item['description'][:50] + ('...' if len(item['description']) > 50 else ''),
                    description=item['description'],
                    priority=priority,
                    due_date=due_date,
                    assignee=item.get('assignee'),
                    task_type=item.get('type', 'follow_up'),
                    estimated_duration=item.get('duration', 30),
                    crm_category=self._categorize_task(item['description'])
                )
                tasks.append(task)
        
        # Add standard follow-up tasks based on meeting content
        standard_tasks = self._generate_standard_tasks(text)
        tasks.extend(standard_tasks)
        
        return tasks
    
    def _determine_task_priority(self, description: str, context: str) -> TaskPriority:
        """Determine task priority from description and context"""
        desc_lower = description.lower()
        context_lower = context.lower()
        
        for priority, keywords in self.priority_keywords.items():
            if any(keyword in desc_lower or keyword in context_lower for keyword in keywords):
                return priority
        
        # Default priority based on task type
        if any(word in desc_lower for word in ['proposal', 'quote', 'contract']):
            return TaskPriority.HIGH
        elif any(word in desc_lower for word in ['demo', 'presentation', 'meeting']):
            return TaskPriority.MEDIUM
        
        return TaskPriority.MEDIUM
    
    def _calculate_due_date(self, suggested_date: Optional[str], priority: TaskPriority) -> datetime:
        """Calculate appropriate due date based on priority"""
        base_date = datetime.now()
        
        if suggested_date:
            try:
                return datetime.strptime(suggested_date, '%Y-%m-%d')
            except (ValueError, TypeError):
                pass
        
        # Default based on priority
        priority_days = {
            TaskPriority.URGENT: 1,
            TaskPriority.HIGH: 2,
            TaskPriority.MEDIUM: 5,
            TaskPriority.LOW: 10
        }
        
        return base_date + timedelta(days=priority_days.get(priority, 5))
    
    def _categorize_task(self, description: str) -> str:
        """Categorize task for CRM organization"""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['proposal', 'quote', 'pricing']):
            return 'Sales'
        elif any(word in desc_lower for word in ['demo', 'presentation', 'meeting']):
            return 'Meeting'
        elif any(word in desc_lower for word in ['contract', 'legal', 'terms']):
            return 'Legal'
        elif any(word in desc_lower for word in ['technical', 'integration', 'setup']):
            return 'Technical'
        
        return 'General'
    
    def _generate_standard_tasks(self, text: str) -> List[FollowUpTask]:
        """Generate standard follow-up tasks based on meeting content"""
        tasks = []
        
        # Always add a general follow-up
        tasks.append(FollowUpTask(
            title="Follow up on meeting outcomes",
            description="Check progress on meeting decisions and next steps",
            priority=TaskPriority.MEDIUM,
            due_date=datetime.now() + timedelta(days=3),
            task_type="follow_up",
            crm_category="General"
        ))
        
        # Add specific tasks based on content
        if 'proposal' in text or 'quote' in text:
            tasks.append(FollowUpTask(
                title="Send proposal/quote",
                description="Prepare and send requested proposal or quote",
                priority=TaskPriority.HIGH,
                due_date=datetime.now() + timedelta(days=2),
                task_type="sales_activity",
                crm_category="Sales"
            ))
        
        if 'demo' in text or 'presentation' in text:
            tasks.append(FollowUpTask(
                title="Schedule product demo",
                description="Coordinate and schedule product demonstration",
                priority=TaskPriority.MEDIUM,
                due_date=datetime.now() + timedelta(days=5),
                task_type="meeting",
                crm_category="Meeting"
            ))
        
        return tasks
    
    def _generate_reminder_suggestions(
        self, 
        action_items: List[Dict], 
        opportunity_suggestion: Optional[OpportunitySuggestion]
    ) -> List[ReminderSuggestion]:
        """Generate reminder suggestions for follow-up"""
        reminders = []
        
        # Email reminders for high-priority tasks
        high_priority_items = [item for item in action_items 
                             if item.get('priority') == 'high' or 'urgent' in item.get('description', '').lower()]
        
        for item in high_priority_items:
            reminders.append(ReminderSuggestion(
                reminder_type=ReminderType.EMAIL,
                title=f"Reminder: {item['description'][:30]}...",
                description=f"Follow up on: {item['description']}",
                reminder_date=datetime.now() + timedelta(days=1),
                recipient=item.get('assignee'),
                priority=TaskPriority.HIGH
            ))
        
        # Calendar reminders for meetings
        if opportunity_suggestion and opportunity_suggestion.suggested_stage in [
            OpportunityStage.PROPOSAL, OpportunityStage.NEGOTIATION
        ]:
            reminders.append(ReminderSuggestion(
                reminder_type=ReminderType.CALENDAR,
                title="Schedule follow-up meeting",
                description="Schedule next meeting to advance opportunity",
                reminder_date=datetime.now() + timedelta(days=7),
                priority=TaskPriority.MEDIUM
            ))
        
        # Task reminders for general follow-up
        reminders.append(ReminderSuggestion(
            reminder_type=ReminderType.TASK,
            title="Review meeting outcomes",
            description="Review and validate meeting outcomes in CRM",
            reminder_date=datetime.now() + timedelta(days=1),
            priority=TaskPriority.MEDIUM
        ))
        
        return reminders
    
    def _extract_deal_value(self, text: str, current_value: Optional[float]) -> Optional[float]:
        """Extract potential deal value from meeting text"""
        for pattern in self.value_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Take the first match and convert to float
                    value_str = matches[0].replace(',', '')
                    
                    # Handle 'k' suffix (thousands)
                    if 'k' in text.lower():
                        return float(value_str) * 1000
                    elif 'thousand' in text.lower():
                        return float(value_str) * 1000
                    else:
                        return float(value_str)
                except (ValueError, TypeError):
                    continue
        
        return current_value
    
    def _suggest_next_meeting(
        self, 
        text: str, 
        opportunity_suggestion: Optional[OpportunitySuggestion]
    ) -> Optional[datetime]:
        """Suggest timing for next meeting"""
        # Look for explicit timing mentions
        if 'next week' in text:
            return datetime.now() + timedelta(days=7)
        elif 'two weeks' in text or '2 weeks' in text:
            return datetime.now() + timedelta(days=14)
        elif 'next month' in text:
            return datetime.now() + timedelta(days=30)
        
        # Suggest based on opportunity stage
        if opportunity_suggestion:
            stage_timing = {
                OpportunityStage.PROSPECTING: 14,  # 2 weeks
                OpportunityStage.QUALIFICATION: 7,  # 1 week
                OpportunityStage.NEEDS_ANALYSIS: 10,  # 1.5 weeks
                OpportunityStage.PROPOSAL: 5,  # 5 days
                OpportunityStage.NEGOTIATION: 3,  # 3 days
            }
            
            days = stage_timing.get(opportunity_suggestion.suggested_stage, 7)
            return datetime.now() + timedelta(days=days)
        
        return None
    
    def _calculate_confidence_score(
        self, 
        field_mappings: List[CRMFieldMapping], 
        opportunity_suggestion: Optional[OpportunitySuggestion], 
        follow_up_tasks: List[FollowUpTask]
    ) -> float:
        """Calculate overall confidence score for suggestions"""
        scores = []
        
        # Field mapping confidence
        if field_mappings:
            avg_field_confidence = sum(fm.confidence for fm in field_mappings) / len(field_mappings)
            scores.append(avg_field_confidence * 0.4)  # 40% weight
        
        # Opportunity suggestion confidence
        if opportunity_suggestion:
            scores.append(opportunity_suggestion.confidence * 0.3)  # 30% weight
        else:
            scores.append(0.5 * 0.3)  # Neutral score if no suggestion
        
        # Task generation confidence (based on number and quality)
        task_confidence = min(len(follow_up_tasks) / 5.0, 1.0)  # Max confidence at 5+ tasks
        scores.append(task_confidence * 0.3)  # 30% weight
        
        return sum(scores)
    
    def _generate_validation_notes(
        self, 
        field_mappings: List[CRMFieldMapping], 
        opportunity_suggestion: Optional[OpportunitySuggestion], 
        follow_up_tasks: List[FollowUpTask],
        deal_value_estimate: Optional[float]
    ) -> List[str]:
        """Generate validation notes for human review"""
        notes = []
        
        # Field mapping notes
        notes.append(f"Generated {len(field_mappings)} field mappings for CRM update")
        
        low_confidence_fields = [fm for fm in field_mappings if fm.confidence < 0.7]
        if low_confidence_fields:
            notes.append(f"⚠️ {len(low_confidence_fields)} field(s) have low confidence - please review")
        
        # Opportunity stage notes
        if opportunity_suggestion:
            if opportunity_suggestion.confidence > 0.8:
                notes.append(f"✅ High confidence stage suggestion: {opportunity_suggestion.suggested_stage.value}")
            else:
                notes.append(f"⚠️ Moderate confidence stage suggestion: {opportunity_suggestion.suggested_stage.value}")
        else:
            notes.append("ℹ️ No clear opportunity stage change detected")
        
        # Task notes
        high_priority_tasks = [t for t in follow_up_tasks if t.priority in [TaskPriority.HIGH, TaskPriority.URGENT]]
        if high_priority_tasks:
            notes.append(f"🔥 {len(high_priority_tasks)} high-priority task(s) identified")
        
        # Deal value notes
        if deal_value_estimate:
            notes.append(f"💰 Estimated deal value: ${deal_value_estimate:,.2f}")
        
        # General validation reminder
        notes.append("📋 Please review all suggestions before applying to CRM")
        
        return notes