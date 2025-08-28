"""
Advanced Data Extraction for Meeting Intelligence
Handles natural language processing and structured data extraction from conversations
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.models import User

from .models import AIInteraction, AIPromptTemplate
from .gemini_client import get_gemini_client, GeminiResponse

logger = logging.getLogger(__name__)


class ContactInformationExtractor:
    """Extracts contact information from conversation text"""
    
    def __init__(self):
        # Regex patterns for contact information
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})')
        self.name_pattern = re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b')
        self.company_pattern = re.compile(r'\b([A-Z][a-zA-Z\s&]+(?:Inc|LLC|Corp|Corporation|Company|Ltd|Limited)\.?)\b')
    
    def extract_contacts(self, text: str) -> List[Dict[str, Any]]:
        """Extract contact information from text"""
        contacts = []
        
        # Find emails
        emails = self.email_pattern.findall(text)
        
        # Find phone numbers
        phones = self.phone_pattern.findall(text)
        phone_numbers = [f"({match[1]}) {match[2]}-{match[3]}" for match in phones]
        
        # Find names (basic pattern matching)
        names = self.name_pattern.findall(text)
        
        # Find companies
        companies = self.company_pattern.findall(text)
        
        # Combine information intelligently
        for email in emails:
            contact = {
                'email': email,
                'confidence': 0.9,  # High confidence for email extraction
                'source': 'regex_extraction'
            }
            
            # Try to associate with names and companies mentioned nearby
            email_position = text.find(email)
            context_window = text[max(0, email_position-200):email_position+200]
            
            # Look for names in context
            context_names = self.name_pattern.findall(context_window)
            if context_names:
                contact['name'] = context_names[0]
                contact['confidence'] = min(contact['confidence'] + 0.05, 1.0)
            
            # Look for companies in context
            context_companies = self.company_pattern.findall(context_window)
            if context_companies:
                contact['company'] = context_companies[0]
                contact['confidence'] = min(contact['confidence'] + 0.05, 1.0)
            
            contacts.append(contact)
        
        # Add standalone phone numbers
        for phone in phone_numbers:
            if not any(phone in str(contact) for contact in contacts):
                contacts.append({
                    'phone': phone,
                    'confidence': 0.7,
                    'source': 'regex_extraction'
                })
        
        return contacts
    
    def extract_with_ai(self, text: str, client) -> List[Dict[str, Any]]:
        """Use AI to extract contact information with higher accuracy"""
        prompt = f"""Extract all contact information from the following text. Return the information in JSON format with the following structure:

{{
  "contacts": [
    {{
      "name": "Full Name",
      "title": "Job Title",
      "company": "Company Name",
      "email": "email@company.com",
      "phone": "phone number",
      "confidence": 0.8
    }}
  ]
}}

Text to analyze:
{text}

Focus on:
- Full names of people mentioned
- Job titles and roles
- Company names and organizations
- Email addresses
- Phone numbers
- Any organizational relationships mentioned

Return only valid JSON. If no contacts are found, return {{"contacts": []}}."""
        
        try:
            response = client.generate_response(
                prompt=prompt,
                temperature=0.2,  # Low temperature for consistent extraction
                max_tokens=1000
            )
            
            if response.error:
                logger.warning(f"AI contact extraction failed: {response.error}")
                return []
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                contacts = result.get('contacts', [])
                
                # Add metadata
                for contact in contacts:
                    contact['source'] = 'ai_extraction'
                    contact['extraction_confidence'] = response.confidence_score
                
                return contacts
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI contact extraction JSON: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error in AI contact extraction: {str(e)}")
            return []


class DealInformationExtractor:
    """Extracts deal-related information from conversations"""
    
    def __init__(self):
        # Budget patterns
        self.budget_patterns = [
            re.compile(r'\$([0-9,]+(?:\.[0-9]{2})?)', re.IGNORECASE),
            re.compile(r'budget.*?(\$?[0-9,]+)', re.IGNORECASE),
            re.compile(r'([0-9,]+)\s*(?:dollars?|USD|k|thousand|million)', re.IGNORECASE)
        ]
        
        # Timeline patterns
        self.timeline_patterns = [
            re.compile(r'by\s+([A-Z][a-z]+\s+[0-9]{1,2})', re.IGNORECASE),  # by March 15
            re.compile(r'in\s+([0-9]{1,2})\s+(?:weeks?|months?)', re.IGNORECASE),  # in 3 weeks
            re.compile(r'Q[1-4]\s+[0-9]{4}', re.IGNORECASE),  # Q1 2024
            re.compile(r'end\s+of\s+([A-Z][a-z]+)', re.IGNORECASE)  # end of March
        ]
    
    def extract_deal_info(self, text: str) -> Dict[str, Any]:
        """Extract deal information using pattern matching"""
        deal_info = {}
        
        # Extract budget information
        budgets = []
        for pattern in self.budget_patterns:
            matches = pattern.findall(text)
            budgets.extend(matches)
        
        if budgets:
            # Clean and parse budget amounts
            parsed_budgets = []
            for budget in budgets:
                cleaned = re.sub(r'[^\d.]', '', str(budget))
                if cleaned:
                    try:
                        amount = float(cleaned)
                        parsed_budgets.append(amount)
                    except ValueError:
                        continue
            
            if parsed_budgets:
                deal_info['budget_mentions'] = parsed_budgets
                deal_info['estimated_budget'] = max(parsed_budgets)  # Take highest mentioned
        
        # Extract timeline information
        timelines = []
        for pattern in self.timeline_patterns:
            matches = pattern.findall(text)
            timelines.extend(matches)
        
        if timelines:
            deal_info['timeline_mentions'] = timelines
        
        # Extract decision makers (basic pattern)
        decision_patterns = [
            r'CEO\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'CTO\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'VP\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Director\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]
        
        decision_makers = []
        for pattern in decision_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            decision_makers.extend(matches)
        
        if decision_makers:
            deal_info['decision_makers'] = decision_makers
        
        return deal_info
    
    def extract_with_ai(self, text: str, client) -> Dict[str, Any]:
        """Use AI to extract deal information with higher accuracy"""
        prompt = f"""Extract deal-related information from the following conversation. Return the information in JSON format:

{{
  "budget": {{
    "amount": "specific amount if mentioned",
    "range": "budget range if mentioned",
    "constraints": "budget constraints or concerns",
    "approval_process": "how budget decisions are made"
  }},
  "timeline": {{
    "implementation_date": "when they want to implement",
    "decision_date": "when they need to decide",
    "urgency_level": "high/medium/low",
    "constraints": "timeline constraints mentioned"
  }},
  "decision_makers": [
    {{
      "name": "Name",
      "title": "Title",
      "role_in_decision": "their role in the decision process"
    }}
  ],
  "requirements": [
    "specific requirements mentioned"
  ],
  "success_criteria": [
    "how they measure success"
  ],
  "concerns": [
    "concerns or objections raised"
  ]
}}

Conversation text:
{text}

Focus on extracting specific, actionable information about budget, timeline, decision-making process, and requirements."""
        
        try:
            response = client.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1500
            )
            
            if response.error:
                logger.warning(f"AI deal extraction failed: {response.error}")
                return {}
            
            try:
                result = json.loads(response.content)
                result['extraction_confidence'] = response.confidence_score
                result['source'] = 'ai_extraction'
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI deal extraction JSON: {e}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in AI deal extraction: {str(e)}")
            return {}


class CompetitiveIntelligenceExtractor:
    """Extracts competitive intelligence from conversations"""
    
    def __init__(self):
        # Common competitor indicators
        self.competitor_indicators = [
            'competitor', 'competing', 'alternative', 'other vendor', 'current solution',
            'existing system', 'incumbent', 'other option', 'comparison'
        ]
        
        # Competitive context patterns
        self.competitive_patterns = [
            re.compile(r'currently\s+using\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE),
            re.compile(r'compared\s+to\s+([A-Z][a-zA-Z\s]+)', re.IGNORECASE),
            re.compile(r'([A-Z][a-zA-Z\s]+)\s+is\s+(?:more|less|better|worse)', re.IGNORECASE)
        ]
    
    def extract_competitive_intel(self, text: str) -> List[Dict[str, Any]]:
        """Extract competitive intelligence using pattern matching"""
        competitive_intel = []
        
        # Find competitor mentions
        for pattern in self.competitive_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if len(match.split()) <= 4:  # Reasonable company name length
                    competitive_intel.append({
                        'competitor_name': match.strip(),
                        'context': 'mentioned_in_comparison',
                        'confidence': 0.6,
                        'source': 'pattern_matching'
                    })
        
        # Look for competitive context around indicators
        for indicator in self.competitor_indicators:
            if indicator in text.lower():
                # Find context around the indicator
                pattern = re.compile(f'.{{0,100}}{re.escape(indicator)}.{{0,100}}', re.IGNORECASE)
                matches = pattern.findall(text)
                
                for match in matches:
                    competitive_intel.append({
                        'context': match.strip(),
                        'indicator': indicator,
                        'confidence': 0.4,
                        'source': 'context_extraction'
                    })
        
        return competitive_intel
    
    def extract_with_ai(self, text: str, client) -> List[Dict[str, Any]]:
        """Use AI to extract competitive intelligence with higher accuracy"""
        prompt = f"""Extract competitive intelligence from the following conversation. Return the information in JSON format:

{{
  "competitive_intelligence": [
    {{
      "competitor_name": "Name of competitor or alternative solution",
      "relationship": "current_vendor/being_evaluated/mentioned_as_alternative",
      "strengths": ["competitor strengths mentioned"],
      "weaknesses": ["competitor weaknesses mentioned"],
      "pricing_info": "any pricing information mentioned",
      "customer_sentiment": "positive/negative/neutral",
      "threat_level": "high/medium/low",
      "context": "full context where competitor was mentioned"
    }}
  ]
}}

Conversation text:
{text}

Look for:
- Direct mentions of competitor names
- References to "current solution" or "existing system"
- Comparisons between solutions
- Pricing discussions involving competitors
- Customer satisfaction with current vendors
- Reasons for considering alternatives

Return only valid JSON. If no competitive intelligence is found, return {{"competitive_intelligence": []}}."""
        
        try:
            response = client.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=1200
            )
            
            if response.error:
                logger.warning(f"AI competitive extraction failed: {response.error}")
                return []
            
            try:
                result = json.loads(response.content)
                intel_list = result.get('competitive_intelligence', [])
                
                # Add metadata
                for intel in intel_list:
                    intel['source'] = 'ai_extraction'
                    intel['extraction_confidence'] = response.confidence_score
                
                return intel_list
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI competitive extraction JSON: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error in AI competitive extraction: {str(e)}")
            return []


class ActionItemExtractor:
    """Extracts action items and commitments from conversations"""
    
    def __init__(self):
        # Action item indicators
        self.action_indicators = [
            'will send', 'will provide', 'will follow up', 'will schedule',
            'need to', 'should', 'must', 'action item', 'next step',
            'follow up', 'deliverable', 'commitment', 'agreed to'
        ]
        
        # Deadline patterns
        self.deadline_patterns = [
            re.compile(r'by\s+([A-Z][a-z]+\s+[0-9]{1,2})', re.IGNORECASE),
            re.compile(r'by\s+([A-Z][a-z]+day)', re.IGNORECASE),
            re.compile(r'in\s+([0-9]{1,2})\s+(?:days?|weeks?)', re.IGNORECASE),
            re.compile(r'end\s+of\s+(?:this\s+)?([A-Z][a-z]+)', re.IGNORECASE)
        ]
    
    def extract_action_items(self, text: str) -> List[Dict[str, Any]]:
        """Extract action items using pattern matching"""
        action_items = []
        
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains action indicators
            for indicator in self.action_indicators:
                if indicator in sentence.lower():
                    # Extract deadline if present
                    deadline = None
                    for pattern in self.deadline_patterns:
                        match = pattern.search(sentence)
                        if match:
                            deadline = match.group(1)
                            break
                    
                    # Determine owner (basic heuristic)
                    owner = 'Unknown'
                    if any(word in sentence.lower() for word in ['i will', 'we will', 'our team']):
                        owner = 'Internal'
                    elif any(word in sentence.lower() for word in ['you will', 'your team', 'client']):
                        owner = 'Customer'
                    
                    action_items.append({
                        'description': sentence,
                        'owner': owner,
                        'deadline': deadline,
                        'indicator': indicator,
                        'confidence': 0.5,
                        'source': 'pattern_matching'
                    })
                    break
        
        return action_items
    
    def extract_with_ai(self, text: str, client) -> List[Dict[str, Any]]:
        """Use AI to extract action items with higher accuracy"""
        prompt = f"""Extract all action items and commitments from the following conversation. Return the information in JSON format:

{{
  "action_items": [
    {{
      "description": "Clear description of the action item",
      "owner": "Who is responsible (name or role)",
      "deadline": "When it needs to be completed",
      "priority": "high/medium/low",
      "type": "deliverable/meeting/follow_up/research/other",
      "commitment_level": "firm/tentative/discussed",
      "dependencies": ["any dependencies mentioned"]
    }}
  ]
}}

Conversation text:
{text}

Look for:
- Explicit commitments ("I will...", "We will...")
- Agreed next steps
- Deliverables mentioned
- Follow-up meetings to be scheduled
- Research or information to be provided
- Deadlines and timelines
- Who is responsible for each item

Return only valid JSON. If no action items are found, return {{"action_items": []}}."""
        
        try:
            response = client.generate_response(
                prompt=prompt,
                temperature=0.2,
                max_tokens=1200
            )
            
            if response.error:
                logger.warning(f"AI action item extraction failed: {response.error}")
                return []
            
            try:
                result = json.loads(response.content)
                action_items = result.get('action_items', [])
                
                # Add metadata
                for item in action_items:
                    item['source'] = 'ai_extraction'
                    item['extraction_confidence'] = response.confidence_score
                
                return action_items
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI action item extraction JSON: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error in AI action item extraction: {str(e)}")
            return []


class MeetingOutcomeClassifier:
    """Classifies meeting outcomes and next steps"""
    
    def __init__(self):
        self.positive_indicators = [
            'interested', 'excited', 'impressed', 'like', 'love', 'great',
            'perfect', 'exactly', 'solution', 'move forward', 'next steps'
        ]
        
        self.negative_indicators = [
            'concerned', 'worried', 'expensive', 'costly', 'not sure',
            'hesitant', 'problem', 'issue', 'difficult', 'complicated'
        ]
        
        self.neutral_indicators = [
            'need to think', 'discuss internally', 'review', 'consider',
            'evaluate', 'compare', 'more information'
        ]
    
    def classify_outcome(self, text: str) -> Dict[str, Any]:
        """Classify meeting outcome based on sentiment and indicators"""
        text_lower = text.lower()
        
        positive_count = sum(1 for indicator in self.positive_indicators if indicator in text_lower)
        negative_count = sum(1 for indicator in self.negative_indicators if indicator in text_lower)
        neutral_count = sum(1 for indicator in self.neutral_indicators if indicator in text_lower)
        
        # Determine overall sentiment
        if positive_count > negative_count and positive_count > neutral_count:
            sentiment = 'positive'
            confidence = min(0.6 + (positive_count * 0.1), 1.0)
        elif negative_count > positive_count and negative_count > neutral_count:
            sentiment = 'negative'
            confidence = min(0.6 + (negative_count * 0.1), 1.0)
        elif neutral_count > 0:
            sentiment = 'neutral'
            confidence = min(0.5 + (neutral_count * 0.1), 0.8)
        else:
            sentiment = 'unknown'
            confidence = 0.3
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'positive_indicators': positive_count,
            'negative_indicators': negative_count,
            'neutral_indicators': neutral_count,
            'source': 'pattern_classification'
        }
    
    def classify_with_ai(self, text: str, client) -> Dict[str, Any]:
        """Use AI to classify meeting outcome with higher accuracy"""
        prompt = f"""Analyze the following conversation and classify the meeting outcome. Return the information in JSON format:

{{
  "meeting_outcome": {{
    "overall_sentiment": "positive/negative/neutral/mixed",
    "confidence_level": 0.8,
    "key_indicators": ["specific phrases that indicate sentiment"],
    "customer_interest_level": "high/medium/low",
    "likelihood_to_proceed": "high/medium/low",
    "main_concerns": ["any concerns raised"],
    "positive_signals": ["positive signals detected"],
    "next_steps_clarity": "clear/unclear/none_defined",
    "urgency_level": "high/medium/low",
    "summary": "Brief summary of the meeting outcome"
  }}
}}

Conversation text:
{text}

Analyze for:
- Customer engagement and interest level
- Concerns or objections raised
- Positive buying signals
- Clarity of next steps
- Overall likelihood to move forward
- Urgency indicators

Return only valid JSON."""
        
        try:
            response = client.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=800
            )
            
            if response.error:
                logger.warning(f"AI outcome classification failed: {response.error}")
                return {}
            
            try:
                result = json.loads(response.content)
                outcome = result.get('meeting_outcome', {})
                outcome['source'] = 'ai_classification'
                outcome['extraction_confidence'] = response.confidence_score
                return outcome
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI outcome classification JSON: {e}")
                return {}
                
        except Exception as e:
            logger.error(f"Error in AI outcome classification: {str(e)}")
            return {}


class ComprehensiveDataExtractor:
    """Comprehensive data extraction service combining all extractors"""
    
    def __init__(self):
        self.contact_extractor = ContactInformationExtractor()
        self.deal_extractor = DealInformationExtractor()
        self.competitive_extractor = CompetitiveIntelligenceExtractor()
        self.action_extractor = ActionItemExtractor()
        self.outcome_classifier = MeetingOutcomeClassifier()
        self.client = get_gemini_client()
    
    def extract_all_data(
        self,
        conversation_text: str,
        meeting_context: Dict[str, Any],
        use_ai: bool = True
    ) -> Dict[str, Any]:
        """Extract all structured data from conversation text"""
        try:
            extracted_data = {
                'extraction_timestamp': timezone.now().isoformat(),
                'conversation_length': len(conversation_text),
                'meeting_context': meeting_context,
                'extraction_method': 'ai_enhanced' if use_ai else 'pattern_matching'
            }
            
            if use_ai:
                # Use AI-enhanced extraction
                extracted_data.update(self._extract_with_ai(conversation_text))
            else:
                # Use pattern-based extraction
                extracted_data.update(self._extract_with_patterns(conversation_text))
            
            # Calculate overall confidence score
            extracted_data['overall_confidence'] = self._calculate_overall_confidence(extracted_data)
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error in comprehensive data extraction: {str(e)}")
            return {
                'error': str(e),
                'extraction_timestamp': timezone.now().isoformat()
            }
    
    def _extract_with_ai(self, text: str) -> Dict[str, Any]:
        """Extract data using AI-enhanced methods"""
        return {
            'contacts': self.contact_extractor.extract_with_ai(text, self.client),
            'deal_information': self.deal_extractor.extract_with_ai(text, self.client),
            'competitive_intelligence': self.competitive_extractor.extract_with_ai(text, self.client),
            'action_items': self.action_extractor.extract_with_ai(text, self.client),
            'meeting_outcome': self.outcome_classifier.classify_with_ai(text, self.client)
        }
    
    def _extract_with_patterns(self, text: str) -> Dict[str, Any]:
        """Extract data using pattern-based methods"""
        return {
            'contacts': self.contact_extractor.extract_contacts(text),
            'deal_information': self.deal_extractor.extract_deal_info(text),
            'competitive_intelligence': self.competitive_extractor.extract_competitive_intel(text),
            'action_items': self.action_extractor.extract_action_items(text),
            'meeting_outcome': self.outcome_classifier.classify_outcome(text)
        }
    
    def _calculate_overall_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """Calculate overall confidence score for extracted data"""
        confidence_scores = []
        
        # Collect confidence scores from different extractors
        for key, value in extracted_data.items():
            if isinstance(value, dict) and 'extraction_confidence' in value:
                confidence_scores.append(value['extraction_confidence'])
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and 'extraction_confidence' in item:
                        confidence_scores.append(item['extraction_confidence'])
                    elif isinstance(item, dict) and 'confidence' in item:
                        confidence_scores.append(item['confidence'])
        
        if confidence_scores:
            return sum(confidence_scores) / len(confidence_scores)
        else:
            return 0.5  # Default confidence if no scores available