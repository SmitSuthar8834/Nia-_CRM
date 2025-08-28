"""
Lead matching services for intelligent meeting workflow
"""
from typing import List, Dict, Optional, Tuple
from django.db.models import Q
from fuzzywuzzy import fuzz
from .models import Lead
import re


class LeadMatchingService:
    """
    Service for matching meetings to leads with confidence scoring
    """
    
    # Minimum confidence threshold for automatic matching
    MIN_CONFIDENCE_THRESHOLD = 50
    
    # Weights for different matching criteria
    WEIGHTS = {
        'email': 0.6,  # Email is most important
        'name': 0.25,
        'company': 0.1,
        'phone': 0.05
    }
    
    def __init__(self):
        self.leads_cache = None
        self._refresh_cache()
    
    def _refresh_cache(self):
        """Refresh the leads cache for better performance"""
        self.leads_cache = list(Lead.objects.all().values(
            'id', 'crm_id', 'name', 'email', 'company', 'phone'
        ))
    
    def match_meeting_to_lead(self, meeting_data: Dict) -> Optional[Dict]:
        """
        Match a meeting to the best lead candidate
        
        Args:
            meeting_data: Dictionary containing meeting information
                - attendees: List of attendee emails
                - title: Meeting title
                - organizer: Organizer email
                - description: Meeting description (optional)
        
        Returns:
            Dictionary with match result or None if no good match found
        """
        if not self.leads_cache:
            self._refresh_cache()
        
        best_match = None
        best_confidence = 0
        
        # Extract potential matching data from meeting
        attendee_emails = meeting_data.get('attendees', [])
        meeting_title = meeting_data.get('title', '')
        organizer_email = meeting_data.get('organizer', '')
        description = meeting_data.get('description', '')
        
        # Combine all emails for matching
        all_emails = set(attendee_emails)
        if organizer_email:
            all_emails.add(organizer_email)
        
        for lead in self.leads_cache:
            confidence = self._calculate_match_confidence(
                lead, all_emails, meeting_title, description
            )
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    'lead_id': lead['id'],
                    'crm_id': lead['crm_id'],
                    'confidence': confidence,
                    'match_reasons': self._get_match_reasons(
                        lead, all_emails, meeting_title, description
                    )
                }
        
        # Only return match if confidence meets threshold
        if best_match and best_confidence >= self.MIN_CONFIDENCE_THRESHOLD:
            return best_match
        
        return None
    
    def find_potential_matches(self, meeting_data: Dict, limit: int = 5) -> List[Dict]:
        """
        Find multiple potential lead matches for manual review
        
        Args:
            meeting_data: Dictionary containing meeting information
            limit: Maximum number of matches to return
        
        Returns:
            List of potential matches sorted by confidence
        """
        if not self.leads_cache:
            self._refresh_cache()
        
        matches = []
        attendee_emails = meeting_data.get('attendees', [])
        meeting_title = meeting_data.get('title', '')
        organizer_email = meeting_data.get('organizer', '')
        description = meeting_data.get('description', '')
        
        all_emails = set(attendee_emails)
        if organizer_email:
            all_emails.add(organizer_email)
        
        for lead in self.leads_cache:
            confidence = self._calculate_match_confidence(
                lead, all_emails, meeting_title, description
            )
            
            if confidence > 0:  # Include any potential match
                matches.append({
                    'lead_id': lead['id'],
                    'crm_id': lead['crm_id'],
                    'name': lead['name'],
                    'email': lead['email'],
                    'company': lead['company'],
                    'confidence': confidence,
                    'match_reasons': self._get_match_reasons(
                        lead, all_emails, meeting_title, description
                    )
                })
        
        # Sort by confidence and return top matches
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches[:limit]
    
    def _calculate_match_confidence(self, lead: Dict, emails: set, 
                                  meeting_title: str, description: str) -> float:
        """
        Calculate confidence score for a lead match
        
        Args:
            lead: Lead data dictionary
            emails: Set of email addresses from meeting
            meeting_title: Meeting title
            description: Meeting description
        
        Returns:
            Confidence score between 0 and 100
        """
        total_score = 0
        
        # Email matching (highest weight)
        email_score = self._match_email(lead['email'], emails)
        total_score += email_score * self.WEIGHTS['email']
        
        # Name matching
        name_score = self._match_name(lead['name'], meeting_title, description)
        total_score += name_score * self.WEIGHTS['name']
        
        # Company matching
        company_score = self._match_company(lead['company'], meeting_title, description)
        total_score += company_score * self.WEIGHTS['company']
        
        # Phone matching (if available)
        phone_score = self._match_phone(lead['phone'], description)
        total_score += phone_score * self.WEIGHTS['phone']
        
        return min(total_score * 100, 100)  # Convert to percentage and cap at 100
    
    def _match_email(self, lead_email: str, meeting_emails: set) -> float:
        """Match lead email against meeting attendees"""
        if not lead_email or not meeting_emails:
            return 0
        
        lead_email_lower = lead_email.lower()
        
        # Exact email match
        if lead_email_lower in {email.lower() for email in meeting_emails}:
            return 1.0
        
        # Domain matching for company emails
        lead_domain = lead_email_lower.split('@')[-1] if '@' in lead_email_lower else ''
        if lead_domain:
            for email in meeting_emails:
                email_domain = email.lower().split('@')[-1] if '@' in email else ''
                if lead_domain == email_domain:
                    return 0.7  # High confidence for same domain
        
        return 0
    
    def _match_name(self, lead_name: str, meeting_title: str, description: str) -> float:
        """Match lead name against meeting title and description"""
        if not lead_name:
            return 0
        
        # Combine title and description for name matching
        text_to_search = f"{meeting_title} {description}".lower()
        lead_name_lower = lead_name.lower()
        
        # Split name into parts for better matching
        name_parts = lead_name_lower.split()
        
        max_score = 0
        for part in name_parts:
            if len(part) > 2:  # Skip very short name parts
                # Exact match
                if part in text_to_search:
                    max_score = max(max_score, 1.0)
                else:
                    # Fuzzy matching
                    words = text_to_search.split()
                    for word in words:
                        if len(word) > 2:
                            similarity = fuzz.ratio(part, word) / 100
                            if similarity > 0.8:
                                max_score = max(max_score, similarity)
        
        return max_score
    
    def _match_company(self, lead_company: str, meeting_title: str, description: str) -> float:
        """Match lead company against meeting title and description"""
        if not lead_company:
            return 0
        
        text_to_search = f"{meeting_title} {description}".lower()
        company_lower = lead_company.lower()
        
        # Remove common company suffixes for better matching
        company_clean = re.sub(r'\b(inc|llc|corp|ltd|co|company)\b\.?', '', company_lower).strip()
        
        # Exact match
        if company_clean in text_to_search:
            return 1.0
        
        # Fuzzy matching
        words = text_to_search.split()
        max_similarity = 0
        for word in words:
            if len(word) > 3:
                similarity = fuzz.ratio(company_clean, word) / 100
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity if max_similarity > 0.7 else 0
    
    def _match_phone(self, lead_phone: str, description: str) -> float:
        """Match lead phone against meeting description"""
        if not lead_phone or not description:
            return 0
        
        # Extract phone numbers from description
        phone_pattern = r'[\+]?[1-9]?[\d\s\-\(\)]{10,}'
        phones_in_desc = re.findall(phone_pattern, description)
        
        # Clean phone numbers for comparison
        lead_phone_clean = re.sub(r'[\s\-\(\)]', '', lead_phone)
        
        for phone in phones_in_desc:
            phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
            if lead_phone_clean in phone_clean or phone_clean in lead_phone_clean:
                return 1.0
        
        return 0
    
    def _get_match_reasons(self, lead: Dict, emails: set, 
                          meeting_title: str, description: str) -> List[str]:
        """Get human-readable reasons for the match"""
        reasons = []
        
        # Email reasons
        lead_email = lead['email'].lower() if lead['email'] else ''
        if lead_email in {email.lower() for email in emails}:
            reasons.append(f"Email match: {lead['email']}")
        else:
            lead_domain = lead_email.split('@')[-1] if '@' in lead_email else ''
            if lead_domain:
                for email in emails:
                    email_domain = email.lower().split('@')[-1] if '@' in email else ''
                    if lead_domain == email_domain:
                        reasons.append(f"Same domain: {lead_domain}")
                        break
        
        # Name reasons
        if lead['name']:
            text_to_search = f"{meeting_title} {description}".lower()
            name_parts = lead['name'].lower().split()
            for part in name_parts:
                if len(part) > 2 and part in text_to_search:
                    reasons.append(f"Name match: {part}")
        
        # Company reasons
        if lead['company']:
            text_to_search = f"{meeting_title} {description}".lower()
            company_clean = re.sub(r'\b(inc|llc|corp|ltd|co|company)\b\.?', '', 
                                 lead['company'].lower()).strip()
            if company_clean in text_to_search:
                reasons.append(f"Company match: {lead['company']}")
        
        return reasons