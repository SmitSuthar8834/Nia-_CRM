"""
Meeting Type Classifier for categorizing sales meetings
"""
import re
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime, timedelta

from .models import CalendarEvent

logger = logging.getLogger(__name__)


class MeetingTypeClassifier:
    """
    Classifies sales meetings into specific types based on content and context
    """
    
    def __init__(self):
        # Meeting type classification patterns
        self.classification_patterns = {
            'discovery': {
                'keywords': [
                    'discovery', 'discovery call', 'discovery session', 'needs assessment',
                    'qualification', 'qualify', 'initial call', 'first meeting',
                    'introduction', 'intro call', 'getting to know', 'understand needs',
                    'requirements gathering', 'pain points', 'challenges', 'current state',
                    'exploration', 'fact finding', 'scoping', 'assessment'
                ],
                'patterns': [
                    r'\b(discover|explore|understand|assess|qualify)\b',
                    r'\b(needs?|requirements?|challenges?|pain.points?)\b',
                    r'\b(initial|first|intro|introduction)\b'
                ],
                'duration_range': (30, 60),
                'confidence_boost': 0.3
            },
            'demo': {
                'keywords': [
                    'demo', 'demonstration', 'product demo', 'solution demo',
                    'walkthrough', 'presentation', 'showcase', 'show',
                    'product presentation', 'solution presentation', 'preview',
                    'proof of concept', 'poc', 'trial', 'pilot', 'test drive'
                ],
                'patterns': [
                    r'\b(demo|demonstration|walkthrough|showcase|presentation)\b',
                    r'\b(show|present|preview|trial|pilot)\b',
                    r'\b(proof.of.concept|poc)\b'
                ],
                'duration_range': (45, 90),
                'confidence_boost': 0.4
            },
            'negotiation': {
                'keywords': [
                    'negotiation', 'negotiate', 'pricing', 'contract', 'terms',
                    'proposal', 'quote', 'quotation', 'commercial', 'deal',
                    'agreement', 'legal', 'procurement', 'purchasing',
                    'budget', 'cost', 'investment', 'roi', 'value',
                    'decision', 'approval', 'sign off', 'commitment'
                ],
                'patterns': [
                    r'\b(negotiat|pricing|contract|terms|proposal)\b',
                    r'\b(quote|quotation|commercial|deal|agreement)\b',
                    r'\b(budget|cost|investment|roi|value)\b',
                    r'\b(decision|approval|sign.off|commitment)\b'
                ],
                'duration_range': (30, 120),
                'confidence_boost': 0.4
            },
            'follow_up': {
                'keywords': [
                    'follow up', 'follow-up', 'followup', 'check in', 'check-in',
                    'touch base', 'catch up', 'update', 'status', 'progress',
                    'next steps', 'action items', 'recap', 'summary',
                    'review', 'debrief', 'feedback', 'questions'
                ],
                'patterns': [
                    r'\b(follow.up|check.in|touch.base|catch.up)\b',
                    r'\b(update|status|progress|next.steps)\b',
                    r'\b(recap|summary|review|debrief|feedback)\b'
                ],
                'duration_range': (15, 45),
                'confidence_boost': 0.2
            },
            'closing': {
                'keywords': [
                    'closing', 'close', 'final', 'signature', 'signing',
                    'execution', 'finalize', 'conclude', 'complete',
                    'purchase order', 'po', 'contract signing', 'go live',
                    'implementation', 'onboarding', 'kickoff', 'start',
                    'final contract', 'contract', 'agreement', 'execute'
                ],
                'patterns': [
                    r'\b(clos|final|signature|signing|execution)\b',
                    r'\b(finalize|conclude|complete|purchase.order)\b',
                    r'\b(contract.signing|go.live|implementation)\b',
                    r'\b(onboarding|kickoff|start)\b'
                ],
                'duration_range': (30, 90),
                'confidence_boost': 0.5
            },
            'internal': {
                'keywords': [
                    'team meeting', 'internal', 'staff', 'standup', 'scrum',
                    'planning', 'strategy', 'review', 'sync', 'alignment',
                    'training', 'workshop', 'all hands', 'company',
                    'department', 'one on one', '1:1', 'performance'
                ],
                'patterns': [
                    r'\b(team|internal|staff|standup|scrum)\b',
                    r'\b(planning|strategy|sync|alignment)\b',
                    r'\b(training|workshop|all.hands|company)\b',
                    r'\b(department|one.on.one|1:1|performance)\b'
                ],
                'duration_range': (15, 120),
                'confidence_boost': -0.5  # Negative boost as it's not a sales meeting type
            }
        }
        
        # Context-based classification rules
        self.context_rules = {
            'attendee_count': {
                'discovery': (2, 4),      # Usually small groups
                'demo': (2, 8),           # Can be larger for demos
                'negotiation': (2, 6),    # Decision makers present
                'follow_up': (2, 4),      # Usually small
                'closing': (2, 6),        # Key stakeholders
            },
            'external_ratio': {
                'discovery': 0.5,         # Mix of internal/external
                'demo': 0.6,              # More external attendees
                'negotiation': 0.4,       # More internal for support
                'follow_up': 0.5,         # Balanced
                'closing': 0.3,           # More internal for final push
            }
        }
    
    async def classify_meeting_type(self, event: CalendarEvent) -> str:
        """
        Classify the meeting type based on event data
        """
        scores = {}
        
        # Calculate scores for each meeting type
        for meeting_type, patterns in self.classification_patterns.items():
            score = await self._calculate_type_score(event, meeting_type, patterns)
            scores[meeting_type] = score
        
        # Apply context-based adjustments
        scores = self._apply_context_adjustments(event, scores)
        
        # Get the highest scoring type (excluding internal)
        sales_scores = {k: v for k, v in scores.items() if k != 'internal'}
        
        if not sales_scores:
            return 'other'
        
        best_type = max(sales_scores, key=sales_scores.get)
        best_score = sales_scores[best_type]
        
        # Require minimum confidence threshold
        if best_score < 0.3:
            return 'other'
        
        logger.debug(f"Meeting type classification for '{event.title}': {best_type} (score: {best_score:.2f})")
        
        return best_type
    
    async def _calculate_type_score(
        self, 
        event: CalendarEvent, 
        meeting_type: str, 
        patterns: Dict[str, Any]
    ) -> float:
        """
        Calculate score for a specific meeting type
        """
        score = 0.0
        
        # Analyze title and description text
        text_content = f"{event.title} {event.description or ''}".lower()
        
        # Keyword matching
        keyword_matches = 0
        for keyword in patterns['keywords']:
            if keyword in text_content:
                keyword_matches += 1
                score += 0.1
        
        # Pattern matching
        pattern_matches = 0
        for pattern in patterns['patterns']:
            if re.search(pattern, text_content, re.IGNORECASE):
                pattern_matches += 1
                score += 0.15
        
        # Duration matching
        duration_range = patterns.get('duration_range', (0, 999))
        if duration_range[0] <= event.duration_minutes <= duration_range[1]:
            score += 0.2
        
        # Apply confidence boost
        confidence_boost = patterns.get('confidence_boost', 0)
        score += confidence_boost
        
        # Normalize score
        score = max(0.0, min(1.0, score))
        
        return score
    
    def _apply_context_adjustments(
        self, 
        event: CalendarEvent, 
        scores: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Apply context-based adjustments to scores
        """
        adjusted_scores = scores.copy()
        
        # Attendee count adjustments
        attendee_count = len(event.attendees)
        for meeting_type, (min_count, max_count) in self.context_rules['attendee_count'].items():
            if meeting_type in adjusted_scores:
                if min_count <= attendee_count <= max_count:
                    adjusted_scores[meeting_type] += 0.1
                else:
                    adjusted_scores[meeting_type] -= 0.1
        
        # External attendee ratio adjustments
        if event.attendees:
            external_count = sum(1 for att in event.attendees 
                               if not att.get('email', '').endswith('@yourcompany.com'))
            external_ratio = external_count / len(event.attendees)
            
            for meeting_type, expected_ratio in self.context_rules['external_ratio'].items():
                if meeting_type in adjusted_scores:
                    ratio_diff = abs(external_ratio - expected_ratio)
                    if ratio_diff < 0.2:  # Close to expected ratio
                        adjusted_scores[meeting_type] += 0.1
                    elif ratio_diff > 0.5:  # Far from expected ratio
                        adjusted_scores[meeting_type] -= 0.1
        
        # Recurring meeting adjustments
        if event.is_recurring:
            # Recurring meetings are more likely to be follow-ups or internal
            adjusted_scores['follow_up'] = adjusted_scores.get('follow_up', 0) + 0.2
            adjusted_scores['internal'] = adjusted_scores.get('internal', 0) + 0.1
            
            # Less likely to be discovery or closing
            adjusted_scores['discovery'] = adjusted_scores.get('discovery', 0) - 0.2
            adjusted_scores['closing'] = adjusted_scores.get('closing', 0) - 0.3
        
        # Time-based adjustments
        hour = event.start_time.hour
        if hour < 9 or hour > 17:  # Outside business hours
            # More likely to be follow-ups or internal meetings
            adjusted_scores['follow_up'] = adjusted_scores.get('follow_up', 0) + 0.1
            adjusted_scores['internal'] = adjusted_scores.get('internal', 0) + 0.1
        
        # Normalize scores
        for meeting_type in adjusted_scores:
            adjusted_scores[meeting_type] = max(0.0, min(1.0, adjusted_scores[meeting_type]))
        
        return adjusted_scores
    
    async def get_classification_confidence(
        self, 
        event: CalendarEvent, 
        classified_type: str
    ) -> Dict[str, Any]:
        """
        Get detailed confidence information for a classification
        """
        scores = {}
        details = {}
        
        # Calculate scores for all types
        for meeting_type, patterns in self.classification_patterns.items():
            score = await self._calculate_type_score(event, meeting_type, patterns)
            scores[meeting_type] = score
            
            # Get detailed breakdown
            details[meeting_type] = await self._get_classification_details(event, meeting_type, patterns)
        
        # Apply context adjustments
        adjusted_scores = self._apply_context_adjustments(event, scores)
        
        return {
            'classified_type': classified_type,
            'confidence': adjusted_scores.get(classified_type, 0.0),
            'all_scores': adjusted_scores,
            'raw_scores': scores,
            'details': details.get(classified_type, {}),
            'context_factors': self._get_context_factors(event)
        }
    
    async def _get_classification_details(
        self, 
        event: CalendarEvent, 
        meeting_type: str, 
        patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of classification factors
        """
        text_content = f"{event.title} {event.description or ''}".lower()
        
        matched_keywords = []
        matched_patterns = []
        
        # Find matched keywords
        for keyword in patterns['keywords']:
            if keyword in text_content:
                matched_keywords.append(keyword)
        
        # Find matched patterns
        for pattern in patterns['patterns']:
            if re.search(pattern, text_content, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        return {
            'matched_keywords': matched_keywords,
            'matched_patterns': matched_patterns,
            'duration_match': patterns['duration_range'][0] <= event.duration_minutes <= patterns['duration_range'][1],
            'duration_minutes': event.duration_minutes,
            'expected_duration_range': patterns['duration_range']
        }
    
    def _get_context_factors(self, event: CalendarEvent) -> Dict[str, Any]:
        """
        Get context factors that influence classification
        """
        external_count = sum(1 for att in event.attendees 
                           if not att.get('email', '').endswith('@yourcompany.com'))
        
        return {
            'attendee_count': len(event.attendees),
            'external_attendees': external_count,
            'external_ratio': external_count / len(event.attendees) if event.attendees else 0,
            'is_recurring': event.is_recurring,
            'meeting_hour': event.start_time.hour,
            'weekday': event.start_time.weekday(),
            'duration_minutes': event.duration_minutes,
            'has_meeting_url': bool(event.meeting_url)
        }
    
    async def suggest_meeting_type_improvements(self, event: CalendarEvent) -> List[str]:
        """
        Suggest improvements to make meeting type classification more accurate
        """
        suggestions = []
        
        # Analyze current classification
        classified_type = await self.classify_meeting_type(event)
        confidence_info = await self.get_classification_confidence(event, classified_type)
        
        confidence = confidence_info['confidence']
        
        if confidence < 0.5:
            suggestions.append(
                "Consider using more specific keywords in the meeting title to improve classification accuracy"
            )
        
        if not event.description:
            suggestions.append(
                "Add a meeting description with agenda or objectives to improve type detection"
            )
        
        if len(event.attendees) == 0:
            suggestions.append(
                "Add attendees to help determine if this is an internal or external meeting"
            )
        
        # Type-specific suggestions
        if classified_type == 'other':
            suggestions.append(
                "Use keywords like 'demo', 'discovery', 'follow-up', or 'negotiation' to help classify the meeting type"
            )
        
        if event.duration_minutes < 15:
            suggestions.append(
                "Very short meetings may not be classified accurately. Consider if this is actually a sales meeting."
            )
        
        if event.duration_minutes > 180:
            suggestions.append(
                "Very long meetings may indicate multiple meeting types. Consider breaking into separate meetings."
            )
        
        return suggestions
    
    async def batch_classify_meetings(self, events: List[CalendarEvent]) -> Dict[str, Any]:
        """
        Classify multiple meetings in batch for efficiency
        """
        results = {
            'classifications': {},
            'type_distribution': {},
            'confidence_stats': {
                'high_confidence': 0,    # > 0.7
                'medium_confidence': 0,  # 0.4 - 0.7
                'low_confidence': 0      # < 0.4
            }
        }
        
        for event in events:
            meeting_type = await self.classify_meeting_type(event)
            confidence_info = await self.get_classification_confidence(event, meeting_type)
            
            results['classifications'][str(event.id)] = {
                'type': meeting_type,
                'confidence': confidence_info['confidence'],
                'title': event.title
            }
            
            # Update distribution
            results['type_distribution'][meeting_type] = results['type_distribution'].get(meeting_type, 0) + 1
            
            # Update confidence stats
            confidence = confidence_info['confidence']
            if confidence > 0.7:
                results['confidence_stats']['high_confidence'] += 1
            elif confidence > 0.4:
                results['confidence_stats']['medium_confidence'] += 1
            else:
                results['confidence_stats']['low_confidence'] += 1
        
        return results