"""
Summary quality assessment and confidence scoring service
Handles quality metrics, validation, and confidence scoring for AI-generated summaries
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from .models import DraftSummary, CallBotSession
from .transcription_service import MeetingSummary, ActionItem as TranscriptActionItem

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Quality assessment metrics"""
    TRANSCRIPT_LENGTH = "transcript_length"
    SUMMARY_COHERENCE = "summary_coherence"
    ACTION_ITEM_CLARITY = "action_item_clarity"
    KEY_POINTS_RELEVANCE = "key_points_relevance"
    SPEAKER_IDENTIFICATION = "speaker_identification"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    CONTENT_COVERAGE = "content_coverage"


@dataclass
class QualityScore:
    """Individual quality metric score"""
    metric: QualityMetric
    score: float  # 0.0 to 1.0
    weight: float  # Importance weight
    details: str = ""
    
    @property
    def weighted_score(self) -> float:
        """Calculate weighted score"""
        return self.score * self.weight


@dataclass
class QualityAssessment:
    """Complete quality assessment for a summary"""
    overall_confidence: float
    quality_scores: List[QualityScore]
    recommendations: List[str]
    validation_errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'overall_confidence': self.overall_confidence,
            'quality_scores': [
                {
                    'metric': score.metric.value,
                    'score': score.score,
                    'weight': score.weight,
                    'weighted_score': score.weighted_score,
                    'details': score.details
                }
                for score in self.quality_scores
            ],
            'recommendations': self.recommendations,
            'validation_errors': self.validation_errors
        }


class SummaryQualityService:
    """
    Service for assessing and scoring summary quality
    """
    
    # Default quality metric weights
    DEFAULT_WEIGHTS = {
        QualityMetric.TRANSCRIPT_LENGTH: 0.15,
        QualityMetric.SUMMARY_COHERENCE: 0.20,
        QualityMetric.ACTION_ITEM_CLARITY: 0.20,
        QualityMetric.KEY_POINTS_RELEVANCE: 0.15,
        QualityMetric.SPEAKER_IDENTIFICATION: 0.10,
        QualityMetric.TEMPORAL_CONSISTENCY: 0.10,
        QualityMetric.CONTENT_COVERAGE: 0.10
    }
    
    def __init__(self, custom_weights: Optional[Dict[QualityMetric, float]] = None):
        self.weights = custom_weights or self.DEFAULT_WEIGHTS
        self.logger = logging.getLogger(__name__)
    
    def assess_summary_quality(self, draft_summary: DraftSummary) -> QualityAssessment:
        """
        Perform comprehensive quality assessment of a draft summary
        
        Args:
            draft_summary: DraftSummary instance to assess
            
        Returns:
            QualityAssessment with scores and recommendations
        """
        try:
            quality_scores = []
            validation_errors = []
            recommendations = []
            
            # Assess each quality metric
            for metric in QualityMetric:
                score = self._assess_metric(metric, draft_summary)
                quality_scores.append(score)
                
                # Add recommendations for low scores
                if score.score < 0.6:
                    recommendations.extend(self._get_improvement_recommendations(metric, score))
            
            # Validate summary content
            validation_errors = self._validate_summary_content(draft_summary)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(quality_scores, validation_errors)
            
            # Add general recommendations
            if overall_confidence < 0.7:
                recommendations.append("Consider manual review due to low confidence score")
            
            if len(validation_errors) > 0:
                recommendations.append("Address validation errors before finalizing summary")
            
            assessment = QualityAssessment(
                overall_confidence=overall_confidence,
                quality_scores=quality_scores,
                recommendations=list(set(recommendations)),  # Remove duplicates
                validation_errors=validation_errors
            )
            
            self.logger.info(f"Quality assessment completed for summary {draft_summary.id}: {overall_confidence:.3f}")
            return assessment
            
        except Exception as e:
            self.logger.error(f"Failed to assess summary quality: {e}")
            # Return default low-confidence assessment
            return QualityAssessment(
                overall_confidence=0.3,
                quality_scores=[],
                recommendations=["Quality assessment failed - manual review required"],
                validation_errors=[f"Assessment error: {str(e)}"]
            )
    
    def _assess_metric(self, metric: QualityMetric, draft_summary: DraftSummary) -> QualityScore:
        """Assess individual quality metric"""
        try:
            weight = self.weights.get(metric, 0.1)
            
            if metric == QualityMetric.TRANSCRIPT_LENGTH:
                return self._assess_transcript_length(draft_summary, weight)
            elif metric == QualityMetric.SUMMARY_COHERENCE:
                return self._assess_summary_coherence(draft_summary, weight)
            elif metric == QualityMetric.ACTION_ITEM_CLARITY:
                return self._assess_action_item_clarity(draft_summary, weight)
            elif metric == QualityMetric.KEY_POINTS_RELEVANCE:
                return self._assess_key_points_relevance(draft_summary, weight)
            elif metric == QualityMetric.SPEAKER_IDENTIFICATION:
                return self._assess_speaker_identification(draft_summary, weight)
            elif metric == QualityMetric.TEMPORAL_CONSISTENCY:
                return self._assess_temporal_consistency(draft_summary, weight)
            elif metric == QualityMetric.CONTENT_COVERAGE:
                return self._assess_content_coverage(draft_summary, weight)
            else:
                return QualityScore(metric, 0.5, weight, "Unknown metric")
                
        except Exception as e:
            self.logger.error(f"Failed to assess metric {metric.value}: {e}")
            return QualityScore(metric, 0.3, weight, f"Assessment error: {str(e)}")
    
    def _assess_transcript_length(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess transcript length adequacy"""
        transcript_length = len(draft_summary.bot_session.raw_transcript)
        word_count = len(draft_summary.bot_session.raw_transcript.split())
        
        # Score based on transcript length
        if word_count >= 500:
            score = 1.0
            details = f"Excellent transcript length: {word_count} words"
        elif word_count >= 200:
            score = 0.8
            details = f"Good transcript length: {word_count} words"
        elif word_count >= 100:
            score = 0.6
            details = f"Adequate transcript length: {word_count} words"
        elif word_count >= 50:
            score = 0.4
            details = f"Short transcript: {word_count} words"
        else:
            score = 0.2
            details = f"Very short transcript: {word_count} words"
        
        return QualityScore(QualityMetric.TRANSCRIPT_LENGTH, score, weight, details)
    
    def _assess_summary_coherence(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess summary coherence and readability"""
        summary_text = draft_summary.ai_generated_summary
        
        # Basic coherence indicators
        sentence_count = len(re.split(r'[.!?]+', summary_text))
        word_count = len(summary_text.split())
        
        # Check for coherence indicators
        coherence_indicators = 0
        
        # Proper sentence structure
        if sentence_count >= 2:
            coherence_indicators += 1
        
        # Reasonable length
        if 50 <= word_count <= 300:
            coherence_indicators += 1
        
        # Contains business/meeting vocabulary
        business_terms = ['meeting', 'discussed', 'decided', 'agreed', 'project', 'team', 'client']
        if any(term in summary_text.lower() for term in business_terms):
            coherence_indicators += 1
        
        # No obvious errors (basic check)
        if not re.search(r'\b(error|failed|null|undefined)\b', summary_text.lower()):
            coherence_indicators += 1
        
        score = min(1.0, coherence_indicators / 4.0)
        details = f"Coherence indicators: {coherence_indicators}/4, {word_count} words, {sentence_count} sentences"
        
        return QualityScore(QualityMetric.SUMMARY_COHERENCE, score, weight, details)
    
    def _assess_action_item_clarity(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess clarity and completeness of action items"""
        action_items = draft_summary.extracted_action_items
        
        if not action_items:
            return QualityScore(QualityMetric.ACTION_ITEM_CLARITY, 0.5, weight, "No action items extracted")
        
        clarity_score = 0
        total_items = len(action_items)
        
        for item in action_items:
            item_score = 0
            
            # Check description clarity
            description = item.get('description', '')
            if len(description) >= 10 and not description.lower().startswith('error'):
                item_score += 0.4
            
            # Check assignee presence
            if item.get('assignee'):
                item_score += 0.3
            
            # Check confidence level
            confidence = item.get('confidence', 0)
            if confidence >= 0.7:
                item_score += 0.3
            
            clarity_score += item_score
        
        average_score = clarity_score / total_items if total_items > 0 else 0
        details = f"{total_items} action items, average clarity: {average_score:.2f}"
        
        return QualityScore(QualityMetric.ACTION_ITEM_CLARITY, average_score, weight, details)
    
    def _assess_key_points_relevance(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess relevance and quality of key points"""
        key_points = draft_summary.key_points
        
        if not key_points:
            return QualityScore(QualityMetric.KEY_POINTS_RELEVANCE, 0.3, weight, "No key points identified")
        
        relevance_score = 0
        total_points = len(key_points)
        
        for point in key_points:
            point_score = 0
            
            # Check length and substance
            if len(point) >= 20:
                point_score += 0.4
            
            # Check for business relevance
            business_keywords = ['project', 'timeline', 'budget', 'requirement', 'decision', 'action', 'next step']
            if any(keyword in point.lower() for keyword in business_keywords):
                point_score += 0.4
            
            # Check for specificity (dates, names, numbers)
            if re.search(r'\b\d+\b|[A-Z][a-z]+ [A-Z][a-z]+|\b(monday|tuesday|wednesday|thursday|friday)\b', point):
                point_score += 0.2
            
            relevance_score += min(1.0, point_score)
        
        average_score = relevance_score / total_points if total_points > 0 else 0
        details = f"{total_points} key points, average relevance: {average_score:.2f}"
        
        return QualityScore(QualityMetric.KEY_POINTS_RELEVANCE, average_score, weight, details)
    
    def _assess_speaker_identification(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess quality of speaker identification"""
        speaker_mapping = draft_summary.bot_session.speaker_mapping
        
        if not speaker_mapping:
            return QualityScore(QualityMetric.SPEAKER_IDENTIFICATION, 0.2, weight, "No speakers identified")
        
        speaker_count = len(speaker_mapping)
        identified_speakers = 0
        total_confidence = 0
        
        for speaker_id, speaker_data in speaker_mapping.items():
            if speaker_data.get('name') and speaker_data.get('name') != 'Unknown Speaker':
                identified_speakers += 1
            
            confidence = speaker_data.get('confidence', 0)
            total_confidence += confidence
        
        # Score based on identification success
        identification_rate = identified_speakers / speaker_count if speaker_count > 0 else 0
        average_confidence = total_confidence / speaker_count if speaker_count > 0 else 0
        
        score = (identification_rate * 0.6) + (average_confidence * 0.4)
        details = f"{identified_speakers}/{speaker_count} speakers identified, avg confidence: {average_confidence:.2f}"
        
        return QualityScore(QualityMetric.SPEAKER_IDENTIFICATION, score, weight, details)
    
    def _assess_temporal_consistency(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess temporal consistency in summary and action items"""
        # Check for temporal references in summary and action items
        summary_text = draft_summary.ai_generated_summary
        action_items = draft_summary.extracted_action_items
        
        temporal_indicators = 0
        
        # Check for time references in summary
        time_patterns = [
            r'\b(today|tomorrow|yesterday|next week|last week)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b'
        ]
        
        for pattern in time_patterns:
            if re.search(pattern, summary_text.lower()):
                temporal_indicators += 1
                break
        
        # Check for due dates in action items
        due_dates_present = sum(1 for item in action_items if item.get('due_date'))
        if due_dates_present > 0:
            temporal_indicators += 1
        
        # Check for timeline consistency
        if 'timeline' in summary_text.lower() or 'deadline' in summary_text.lower():
            temporal_indicators += 1
        
        score = min(1.0, temporal_indicators / 3.0)
        details = f"Temporal indicators: {temporal_indicators}/3, {due_dates_present} items with due dates"
        
        return QualityScore(QualityMetric.TEMPORAL_CONSISTENCY, score, weight, details)
    
    def _assess_content_coverage(self, draft_summary: DraftSummary, weight: float) -> QualityScore:
        """Assess how well the summary covers the transcript content"""
        transcript = draft_summary.bot_session.raw_transcript
        summary = draft_summary.ai_generated_summary
        
        if not transcript or not summary:
            return QualityScore(QualityMetric.CONTENT_COVERAGE, 0.2, weight, "Missing transcript or summary")
        
        # Basic coverage assessment
        transcript_words = set(word.lower() for word in transcript.split() if len(word) > 3)
        summary_words = set(word.lower() for word in summary.split() if len(word) > 3)
        
        # Calculate word overlap
        overlap = len(transcript_words.intersection(summary_words))
        coverage_ratio = overlap / len(transcript_words) if transcript_words else 0
        
        # Adjust score based on summary length relative to transcript
        length_ratio = len(summary) / len(transcript) if transcript else 0
        
        # Ideal compression ratio is between 0.1 and 0.3
        if 0.1 <= length_ratio <= 0.3:
            length_score = 1.0
        elif 0.05 <= length_ratio < 0.1 or 0.3 < length_ratio <= 0.5:
            length_score = 0.7
        else:
            length_score = 0.4
        
        # Combine coverage and length scores
        score = (coverage_ratio * 0.6) + (length_score * 0.4)
        details = f"Word overlap: {coverage_ratio:.2f}, compression ratio: {length_ratio:.3f}"
        
        return QualityScore(QualityMetric.CONTENT_COVERAGE, score, weight, details)
    
    def _validate_summary_content(self, draft_summary: DraftSummary) -> List[str]:
        """Validate summary content for common issues"""
        errors = []
        
        # Check summary text
        summary_text = draft_summary.ai_generated_summary
        if not summary_text or len(summary_text.strip()) < 10:
            errors.append("Summary text is too short or empty")
        
        # Check for error indicators in summary
        error_indicators = ['error', 'failed', 'null', 'undefined', 'none', 'empty']
        if any(indicator in summary_text.lower() for indicator in error_indicators):
            errors.append("Summary contains error indicators")
        
        # Validate action items
        action_items = draft_summary.extracted_action_items
        for i, item in enumerate(action_items):
            if not item.get('description'):
                errors.append(f"Action item {i+1} missing description")
            
            confidence = item.get('confidence', 0)
            if confidence < 0 or confidence > 1:
                errors.append(f"Action item {i+1} has invalid confidence score: {confidence}")
        
        # Validate key points
        key_points = draft_summary.key_points
        if len(key_points) == 0:
            errors.append("No key points identified")
        elif len(key_points) > 10:
            errors.append("Too many key points (>10) - may indicate extraction issues")
        
        # Check confidence score
        if draft_summary.confidence_score < 0 or draft_summary.confidence_score > 1:
            errors.append(f"Invalid overall confidence score: {draft_summary.confidence_score}")
        
        return errors
    
    def _calculate_overall_confidence(self, quality_scores: List[QualityScore], validation_errors: List[str]) -> float:
        """Calculate overall confidence score from quality metrics"""
        if not quality_scores:
            return 0.3
        
        # Calculate weighted average of quality scores
        total_weighted_score = sum(score.weighted_score for score in quality_scores)
        total_weight = sum(score.weight for score in quality_scores)
        
        base_confidence = total_weighted_score / total_weight if total_weight > 0 else 0.5
        
        # Apply penalties for validation errors
        error_penalty = min(0.3, len(validation_errors) * 0.1)
        
        # Ensure confidence is within valid range
        final_confidence = max(0.0, min(1.0, base_confidence - error_penalty))
        
        return round(final_confidence, 3)
    
    def _get_improvement_recommendations(self, metric: QualityMetric, score: QualityScore) -> List[str]:
        """Get improvement recommendations for low-scoring metrics"""
        recommendations = []
        
        if metric == QualityMetric.TRANSCRIPT_LENGTH:
            recommendations.append("Ensure adequate meeting duration for comprehensive transcription")
        elif metric == QualityMetric.SUMMARY_COHERENCE:
            recommendations.append("Review summary for clarity and coherence")
        elif metric == QualityMetric.ACTION_ITEM_CLARITY:
            recommendations.append("Clarify action items with specific assignees and deadlines")
        elif metric == QualityMetric.KEY_POINTS_RELEVANCE:
            recommendations.append("Focus key points on business-relevant discussion topics")
        elif metric == QualityMetric.SPEAKER_IDENTIFICATION:
            recommendations.append("Improve audio quality for better speaker identification")
        elif metric == QualityMetric.TEMPORAL_CONSISTENCY:
            recommendations.append("Include specific dates and timelines in meeting discussions")
        elif metric == QualityMetric.CONTENT_COVERAGE:
            recommendations.append("Ensure summary adequately covers main discussion points")
        
        return recommendations


def update_summary_confidence_score(draft_summary: DraftSummary) -> float:
    """
    Update the confidence score of a draft summary using quality assessment
    
    Args:
        draft_summary: DraftSummary instance to update
        
    Returns:
        Updated confidence score
    """
    try:
        quality_service = SummaryQualityService()
        assessment = quality_service.assess_summary_quality(draft_summary)
        
        # Update the confidence score
        draft_summary.confidence_score = assessment.overall_confidence
        draft_summary.save(update_fields=['confidence_score'])
        
        logger.info(f"Updated confidence score for summary {draft_summary.id}: {assessment.overall_confidence}")
        return assessment.overall_confidence
        
    except Exception as e:
        logger.error(f"Failed to update confidence score: {e}")
        return draft_summary.confidence_score


def validate_summary_for_crm_sync(draft_summary: DraftSummary, crm_system: str) -> Tuple[bool, List[str]]:
    """
    Validate summary readiness for CRM synchronization
    
    Args:
        draft_summary: DraftSummary to validate
        crm_system: Target CRM system ('salesforce', 'hubspot', 'creatio')
        
    Returns:
        Tuple of (is_ready, validation_errors)
    """
    try:
        errors = []
        
        # Basic validation
        if draft_summary.confidence_score < 0.6:
            errors.append(f"Confidence score too low for CRM sync: {draft_summary.confidence_score}")
        
        # CRM-specific validation
        formatted_data = draft_summary.format_for_crm(crm_system)
        
        if crm_system == 'salesforce':
            if not formatted_data.get('Description'):
                errors.append("Missing description for Salesforce sync")
        elif crm_system == 'hubspot':
            if not formatted_data.get('hs_meeting_body'):
                errors.append("Missing meeting body for HubSpot sync")
        elif crm_system == 'creatio':
            if not formatted_data.get('Notes'):
                errors.append("Missing notes for Creatio sync")
        
        # Check for minimum content requirements
        if len(draft_summary.ai_generated_summary) < 50:
            errors.append("Summary too short for CRM sync")
        
        if len(draft_summary.key_points) == 0:
            errors.append("No key points available for CRM sync")
        
        is_ready = len(errors) == 0
        return is_ready, errors
        
    except Exception as e:
        logger.error(f"Failed to validate summary for CRM sync: {e}")
        return False, [f"Validation error: {str(e)}"]