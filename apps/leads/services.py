"""
Lead Matching and Participant Analysis Services
"""
import re
import logging
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from django.db.models import Q
from django.utils import timezone
from .models import Lead
from apps.meetings.models import MeetingParticipant


logger = logging.getLogger(__name__)


class ParticipantMatchingService:
    """
    Multi-tier participant matching service for lead identification
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.65
    LOW_CONFIDENCE_THRESHOLD = 0.40
    
    # Domain patterns for company matching
    COMMON_EMAIL_DOMAINS = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 
        'aol.com', 'icloud.com', 'protonmail.com'
    }
    
    def __init__(self):
        self.matching_results = []
    
    def match_participants(self, participants: List[Dict]) -> List[Dict]:
        """
        Main method to match meeting participants with existing leads
        
        Args:
            participants: List of participant dictionaries with email, name, company, etc.
            
        Returns:
            List of matching results with confidence scores and matched leads
        """
        results = []
        
        for participant in participants:
            match_result = self._match_single_participant(participant)
            results.append(match_result)
            
        return results
    
    def _match_single_participant(self, participant: Dict) -> Dict:
        """
        Match a single participant using multi-tier matching algorithms
        
        Args:
            participant: Dictionary with participant information
            
        Returns:
            Dictionary with matching results and confidence scores
        """
        email = participant.get('email', '').lower().strip()
        name = participant.get('name', '').strip()
        company = participant.get('company', '').strip()
        phone = participant.get('phone', '').strip()
        
        # Initialize result structure
        result = {
            'participant': participant,
            'matched_lead': None,
            'confidence_score': 0.0,
            'match_method': None,
            'potential_matches': [],
            'requires_manual_verification': False,
            'should_create_new_lead': False
        }
        
        if not email:
            logger.warning("Participant missing email address")
            result['should_create_new_lead'] = True
            return result
        
        # Tier 1: Exact email match (highest confidence)
        exact_match = self._find_exact_email_match(email)
        if exact_match:
            result.update({
                'matched_lead': exact_match,
                'confidence_score': 1.0,
                'match_method': 'exact_email'
            })
            return result
        
        # Tier 2: Name and company combination matching
        if name and company:
            name_company_matches = self._find_name_company_matches(name, company)
            if name_company_matches:
                best_match = max(name_company_matches, key=lambda x: x['confidence'])
                if best_match['confidence'] >= self.HIGH_CONFIDENCE_THRESHOLD:
                    result.update({
                        'matched_lead': best_match['lead'],
                        'confidence_score': best_match['confidence'],
                        'match_method': 'name_company',
                        'potential_matches': name_company_matches
                    })
                    return result
                else:
                    result['potential_matches'].extend(name_company_matches)
        
        # Tier 3: Company domain matching
        domain_matches = self._find_domain_matches(email, company)
        if domain_matches:
            result['potential_matches'].extend(domain_matches)
            best_domain_match = max(domain_matches, key=lambda x: x['confidence'])
            if best_domain_match['confidence'] >= self.MEDIUM_CONFIDENCE_THRESHOLD:
                result.update({
                    'matched_lead': best_domain_match['lead'],
                    'confidence_score': best_domain_match['confidence'],
                    'match_method': 'domain'
                })
        
        # Tier 4: Phone number matching (if available)
        if phone:
            phone_matches = self._find_phone_matches(phone)
            if phone_matches:
                result['potential_matches'].extend(phone_matches)
                best_phone_match = max(phone_matches, key=lambda x: x['confidence'])
                if best_phone_match['confidence'] >= self.MEDIUM_CONFIDENCE_THRESHOLD:
                    if not result['matched_lead'] or best_phone_match['confidence'] > result['confidence_score']:
                        result.update({
                            'matched_lead': best_phone_match['lead'],
                            'confidence_score': best_phone_match['confidence'],
                            'match_method': 'phone'
                        })
        
        # Tier 5: Fuzzy name matching within company context
        if company and name:
            fuzzy_matches = self._find_fuzzy_name_matches(name, company)
            if fuzzy_matches:
                result['potential_matches'].extend(fuzzy_matches)
                best_fuzzy_match = max(fuzzy_matches, key=lambda x: x['confidence'])
                if not result['matched_lead'] and best_fuzzy_match['confidence'] >= self.LOW_CONFIDENCE_THRESHOLD:
                    result.update({
                        'matched_lead': best_fuzzy_match['lead'],
                        'confidence_score': best_fuzzy_match['confidence'],
                        'match_method': 'fuzzy_name'
                    })
        
        # Determine if manual verification is required
        if result['confidence_score'] < self.MEDIUM_CONFIDENCE_THRESHOLD and result['matched_lead']:
            result['requires_manual_verification'] = True
        
        # Determine if new lead should be created
        if not result['matched_lead'] and not result['potential_matches']:
            result['should_create_new_lead'] = True
        elif result['confidence_score'] < self.LOW_CONFIDENCE_THRESHOLD:
            result['should_create_new_lead'] = True
            result['requires_manual_verification'] = True
        
        return result
    
    def _find_exact_email_match(self, email: str) -> Optional[Lead]:
        """Find exact email match in existing leads"""
        try:
            return Lead.objects.get(email__iexact=email)
        except Lead.DoesNotExist:
            return None
        except Lead.MultipleObjectsReturned:
            # Return the most recently updated lead
            return Lead.objects.filter(email__iexact=email).order_by('-updated_at').first()
    
    def _find_name_company_matches(self, name: str, company: str) -> List[Dict]:
        """Find matches based on name and company combination"""
        matches = []
        
        # Parse name into first and last name
        name_parts = self._parse_name(name)
        if not name_parts:
            return matches
        
        first_name, last_name = name_parts
        
        # Search for leads with similar names in the same company
        potential_leads = Lead.objects.filter(
            Q(company__icontains=company) |
            Q(company__iexact=company)
        ).filter(
            Q(first_name__icontains=first_name) |
            Q(last_name__icontains=last_name) |
            Q(first_name__iexact=first_name) |
            Q(last_name__iexact=last_name)
        )
        
        for lead in potential_leads:
            confidence = self._calculate_name_company_confidence(
                name, company, lead.full_name, lead.company
            )
            if confidence >= self.LOW_CONFIDENCE_THRESHOLD:
                matches.append({
                    'lead': lead,
                    'confidence': confidence,
                    'match_type': 'name_company'
                })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
    
    def _find_domain_matches(self, email: str, company: str = None) -> List[Dict]:
        """Find matches based on email domain"""
        matches = []
        
        domain = email.split('@')[-1].lower()
        
        # Skip common email providers
        if domain in self.COMMON_EMAIL_DOMAINS:
            return matches
        
        # Find leads with the same domain
        domain_leads = Lead.objects.filter(email__iendswith=f'@{domain}')
        
        for lead in domain_leads:
            confidence = 0.7  # Base confidence for domain match
            
            # Boost confidence if company names are similar
            if company and lead.company:
                company_similarity = self._calculate_string_similarity(company, lead.company)
                confidence += (company_similarity * 0.2)
            
            # Reduce confidence if domain is very generic
            if self._is_generic_domain(domain):
                confidence *= 0.8
            
            matches.append({
                'lead': lead,
                'confidence': min(confidence, 0.95),  # Cap at 95%
                'match_type': 'domain'
            })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
    
    def _find_phone_matches(self, phone: str) -> List[Dict]:
        """Find matches based on phone number"""
        matches = []
        
        # Normalize phone number
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return matches
        
        # Search for leads with matching phone numbers
        phone_leads = Lead.objects.filter(
            Q(phone__icontains=normalized_phone) |
            Q(mobile__icontains=normalized_phone)
        )
        
        for lead in phone_leads:
            # Calculate confidence based on phone number similarity
            lead_phone = self._normalize_phone(lead.phone or '')
            lead_mobile = self._normalize_phone(lead.mobile or '')
            
            confidence = 0.0
            if lead_phone and normalized_phone in lead_phone:
                confidence = 0.9
            elif lead_mobile and normalized_phone in lead_mobile:
                confidence = 0.9
            elif lead_phone:
                confidence = self._calculate_phone_similarity(normalized_phone, lead_phone)
            elif lead_mobile:
                confidence = self._calculate_phone_similarity(normalized_phone, lead_mobile)
            
            if confidence >= self.LOW_CONFIDENCE_THRESHOLD:
                matches.append({
                    'lead': lead,
                    'confidence': confidence,
                    'match_type': 'phone'
                })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
    
    def _find_fuzzy_name_matches(self, name: str, company: str) -> List[Dict]:
        """Find fuzzy name matches within company context"""
        matches = []
        
        # Parse name
        name_parts = self._parse_name(name)
        if not name_parts:
            return matches
        
        first_name, last_name = name_parts
        
        # Find leads in similar companies
        company_leads = Lead.objects.filter(
            Q(company__icontains=company) |
            Q(company__iexact=company)
        )
        
        for lead in company_leads:
            # Calculate name similarity
            name_similarity = self._calculate_name_similarity(name, lead.full_name)
            company_similarity = self._calculate_string_similarity(company, lead.company)
            
            # Combined confidence score
            confidence = (name_similarity * 0.7) + (company_similarity * 0.3)
            
            if confidence >= self.LOW_CONFIDENCE_THRESHOLD:
                matches.append({
                    'lead': lead,
                    'confidence': confidence,
                    'match_type': 'fuzzy_name'
                })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)
    
    def _parse_name(self, full_name: str) -> Optional[Tuple[str, str]]:
        """Parse full name into first and last name"""
        if not full_name:
            return None
        
        name_parts = full_name.strip().split()
        if len(name_parts) < 2:
            return None
        
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])
        
        return first_name, last_name
    
    def _calculate_name_company_confidence(self, name1: str, company1: str, name2: str, company2: str) -> float:
        """Calculate confidence score for name and company match"""
        name_similarity = self._calculate_name_similarity(name1, name2)
        company_similarity = self._calculate_string_similarity(company1, company2)
        
        # Weight name similarity more heavily
        confidence = (name_similarity * 0.7) + (company_similarity * 0.3)
        
        return confidence
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names"""
        if not name1 or not name2:
            return 0.0
        
        # Normalize names
        name1 = name1.lower().strip()
        name2 = name2.lower().strip()
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Parse names
        parts1 = name1.split()
        parts2 = name2.split()
        
        # Check for first name and last name matches
        first_match = 0.0
        last_match = 0.0
        
        if parts1 and parts2:
            first_match = SequenceMatcher(None, parts1[0], parts2[0]).ratio()
            if len(parts1) > 1 and len(parts2) > 1:
                last_match = SequenceMatcher(None, parts1[-1], parts2[-1]).ratio()
        
        # Overall similarity
        overall_similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # Return the best score
        return max(overall_similarity, (first_match + last_match) / 2)
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        if not str1 or not str2:
            return 0.0
        
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for comparison"""
        if not phone:
            return ''
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Remove country code if present (assuming US numbers)
        if len(digits_only) == 11 and digits_only.startswith('1'):
            digits_only = digits_only[1:]
        
        return digits_only
    
    def _calculate_phone_similarity(self, phone1: str, phone2: str) -> float:
        """Calculate similarity between phone numbers"""
        if not phone1 or not phone2:
            return 0.0
        
        # Exact match
        if phone1 == phone2:
            return 1.0
        
        # Check if one contains the other
        if phone1 in phone2 or phone2 in phone1:
            return 0.8
        
        # Check last 7 digits (local number)
        if len(phone1) >= 7 and len(phone2) >= 7:
            if phone1[-7:] == phone2[-7:]:
                return 0.7
        
        return 0.0
    
    def _is_generic_domain(self, domain: str) -> bool:
        """Check if domain is generic (e.g., consulting.com, services.com)"""
        generic_keywords = [
            'consulting', 'services', 'solutions', 'group', 'company',
            'corp', 'inc', 'llc', 'ltd', 'partners'
        ]
        
        domain_lower = domain.lower()
        return any(keyword in domain_lower for keyword in generic_keywords)


class LeadCreationService:
    """
    Service for creating new leads from unmatched participants
    """
    
    def create_lead_from_participant(self, participant: Dict, meeting_id: str = None) -> Lead:
        """
        Create a new lead from participant information
        
        Args:
            participant: Dictionary with participant information
            meeting_id: Optional meeting ID for tracking source
            
        Returns:
            Created Lead instance
        """
        email = participant.get('email', '').lower().strip()
        name = participant.get('name', '').strip()
        company = participant.get('company', '').strip()
        phone = participant.get('phone', '').strip()
        title = participant.get('title', '').strip()
        
        # Parse name
        first_name, last_name = self._parse_participant_name(name, email)
        
        # Infer company from email domain if not provided
        if not company and email:
            company = self._infer_company_from_email(email)
        
        # Create lead
        lead = Lead.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone or None,
            company=company or 'Unknown',
            title=title or None,
            source='meeting',
            status='new',
            qualification_score=0
        )
        
        logger.info(f"Created new lead from meeting participant: {lead.full_name} ({lead.email})")
        
        return lead
    
    def _parse_participant_name(self, name: str, email: str) -> Tuple[str, str]:
        """Parse participant name or derive from email"""
        if name:
            name_parts = name.strip().split()
            if len(name_parts) >= 2:
                return name_parts[0], ' '.join(name_parts[1:])
            elif len(name_parts) == 1:
                return name_parts[0], ''
        
        # Derive name from email
        if email:
            local_part = email.split('@')[0]
            # Handle common email patterns
            if '.' in local_part:
                parts = local_part.split('.')
                first_name = parts[0].capitalize()
                last_name = '.'.join(parts[1:]).capitalize()
                return first_name, last_name
            elif '_' in local_part:
                parts = local_part.split('_')
                first_name = parts[0].capitalize()
                last_name = '_'.join(parts[1:]).capitalize()
                return first_name, last_name
            else:
                return local_part.capitalize(), ''
        
        return 'Unknown', 'Contact'
    
    def _infer_company_from_email(self, email: str) -> str:
        """Infer company name from email domain"""
        if not email:
            return 'Unknown'
        
        domain = email.split('@')[-1].lower()
        
        # Skip common email providers
        common_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'icloud.com', 'protonmail.com'
        }
        
        if domain in common_domains:
            return 'Unknown'
        
        # Convert domain to company name
        company_name = domain.split('.')[0]
        return company_name.replace('-', ' ').replace('_', ' ').title()


class ParticipantAnalysisService:
    """
    Service for analyzing meeting participants and updating lead information
    """
    
    def __init__(self):
        self.matching_service = ParticipantMatchingService()
        self.creation_service = LeadCreationService()
        self.linkedin_service = None  # Will be imported when needed to avoid circular imports
    
    def analyze_meeting_participants(self, meeting_id: str, participants: List[Dict], 
                                   use_linkedin_enhancement: bool = True) -> Dict:
        """
        Analyze all participants for a meeting and update/create leads
        
        Args:
            meeting_id: Meeting ID
            participants: List of participant dictionaries
            use_linkedin_enhancement: Whether to use LinkedIn for enhanced matching
            
        Returns:
            Analysis results with statistics and actions taken
        """
        results = {
            'total_participants': len(participants),
            'matched_participants': 0,
            'new_leads_created': 0,
            'manual_verification_required': 0,
            'linkedin_enhanced': 0,
            'matching_results': [],
            'created_leads': [],
            'verification_queue': []
        }
        
        # Enhance participants with LinkedIn data if enabled
        enhanced_participants = participants
        if use_linkedin_enhancement:
            enhanced_participants = self._enhance_participants_with_linkedin(participants)
            results['linkedin_enhanced'] = sum(1 for p in enhanced_participants if p.get('linkedin_profile'))
        
        # Match participants
        matching_results = self.matching_service.match_participants(enhanced_participants)
        
        for match_result in matching_results:
            participant = match_result['participant']
            
            # Enhance matching with LinkedIn data if available
            if use_linkedin_enhancement and match_result['potential_matches']:
                match_result = self._enhance_matching_with_linkedin(match_result)
            
            # Update MeetingParticipant record
            meeting_participant = self._update_meeting_participant(
                meeting_id, participant, match_result
            )
            
            if match_result['matched_lead']:
                results['matched_participants'] += 1
                # Update lead meeting statistics
                self._update_lead_meeting_stats(match_result['matched_lead'], meeting_id)
            
            if match_result['should_create_new_lead'] and not match_result['requires_manual_verification']:
                new_lead = self.creation_service.create_lead_from_participant(
                    participant, meeting_id
                )
                results['new_leads_created'] += 1
                results['created_leads'].append(new_lead)
                
                # Update meeting participant with new lead
                meeting_participant.matched_lead = new_lead
                meeting_participant.match_confidence = 1.0
                meeting_participant.match_method = 'new_lead_created'
                meeting_participant.save()
            
            if match_result['requires_manual_verification']:
                results['manual_verification_required'] += 1
                # Create verification request
                verification_request = self._create_verification_request(
                    meeting_participant, participant, match_result['potential_matches']
                )
                results['verification_queue'].append({
                    'participant': meeting_participant,
                    'verification_request': verification_request,
                    'potential_matches': match_result['potential_matches']
                })
            
            results['matching_results'].append(match_result)
        
        logger.info(f"Participant analysis complete for meeting {meeting_id}: "
                   f"{results['matched_participants']} matched, "
                   f"{results['new_leads_created']} new leads created, "
                   f"{results['manual_verification_required']} require verification, "
                   f"{results['linkedin_enhanced']} LinkedIn enhanced")
        
        return results
    
    def _update_meeting_participant(self, meeting_id: str, participant: Dict, match_result: Dict) -> MeetingParticipant:
        """Update or create MeetingParticipant record"""
        from apps.meetings.models import Meeting
        
        meeting = Meeting.objects.get(id=meeting_id)
        email = participant.get('email', '').lower().strip()
        
        # Extract enhanced data from LinkedIn if available
        enhanced_title = participant.get('enhanced_title', participant.get('title', ''))
        enhanced_company = participant.get('enhanced_company', participant.get('company', ''))
        
        # Get or create meeting participant
        meeting_participant, created = MeetingParticipant.objects.get_or_create(
            meeting=meeting,
            email=email,
            defaults={
                'name': participant.get('name', ''),
                'company': enhanced_company,
                'title': enhanced_title,
                'phone': participant.get('phone', ''),
                'is_external': True,  # Assume external unless proven otherwise
                'matched_lead': match_result.get('matched_lead'),
                'match_confidence': match_result.get('confidence_score', 0.0),
                'match_method': match_result.get('match_method', ''),
                'manual_verification_required': match_result.get('requires_manual_verification', False)
            }
        )
        
        # Update existing participant if not created
        if not created:
            meeting_participant.name = participant.get('name', meeting_participant.name)
            meeting_participant.company = enhanced_company or meeting_participant.company
            meeting_participant.title = enhanced_title or meeting_participant.title
            meeting_participant.phone = participant.get('phone', meeting_participant.phone)
            meeting_participant.matched_lead = match_result.get('matched_lead')
            meeting_participant.match_confidence = match_result.get('confidence_score', 0.0)
            meeting_participant.match_method = match_result.get('match_method', '')
            meeting_participant.manual_verification_required = match_result.get('requires_manual_verification', False)
            meeting_participant.save()
        
        return meeting_participant
    
    def _update_lead_meeting_stats(self, lead: Lead, meeting_id: str):
        """Update lead meeting statistics"""
        lead.update_meeting_stats()
        
        # Update relationship stage based on meeting frequency
        if lead.meeting_count >= 3:
            if lead.relationship_stage in ['cold', 'warm']:
                lead.relationship_stage = 'engaged'
        elif lead.meeting_count >= 2:
            if lead.relationship_stage == 'cold':
                lead.relationship_stage = 'warm'
        
        lead.save()
    
    def _enhance_participants_with_linkedin(self, participants: List[Dict]) -> List[Dict]:
        """Enhance participant data with LinkedIn information"""
        if not self.linkedin_service:
            try:
                from .linkedin_integration import LinkedInProfileService
                self.linkedin_service = LinkedInProfileService()
            except ImportError:
                logger.warning("LinkedIn integration not available")
                return participants
        
        enhanced_participants = []
        for participant in participants:
            try:
                enhanced_participant = self.linkedin_service.enrich_participant_data(participant)
                enhanced_participants.append(enhanced_participant)
            except Exception as e:
                logger.warning(f"LinkedIn enhancement failed for {participant.get('email', 'unknown')}: {str(e)}")
                enhanced_participants.append(participant)
        
        return enhanced_participants
    
    def _enhance_matching_with_linkedin(self, match_result: Dict) -> Dict:
        """Enhance matching results with LinkedIn profile data"""
        if not self.linkedin_service:
            return match_result
        
        try:
            from .linkedin_integration import SocialProfileMatcher
            social_matcher = SocialProfileMatcher()
            
            enhanced_matches = social_matcher.enhance_participant_matching(
                match_result['participant'],
                match_result['potential_matches']
            )
            
            match_result['potential_matches'] = enhanced_matches
            
            # Update best match if LinkedIn enhanced the confidence
            if enhanced_matches:
                best_match = max(enhanced_matches, key=lambda x: x['confidence'])
                if best_match['confidence'] > match_result['confidence_score']:
                    match_result.update({
                        'matched_lead': best_match['lead'],
                        'confidence_score': best_match['confidence'],
                        'match_method': f"{best_match['match_type']}_linkedin_enhanced"
                    })
                    
                    # Reduce manual verification requirement if confidence is high enough
                    if best_match['confidence'] >= ParticipantMatchingService.MEDIUM_CONFIDENCE_THRESHOLD:
                        match_result['requires_manual_verification'] = False
            
        except Exception as e:
            logger.warning(f"LinkedIn matching enhancement failed: {str(e)}")
        
        return match_result
    
    def _create_verification_request(self, meeting_participant: MeetingParticipant, 
                                   participant_data: Dict, potential_matches: List[Dict]):
        """Create a verification request for manual review"""
        try:
            from .verification import ManualVerificationService
            verification_service = ManualVerificationService()
            
            return verification_service.create_verification_request(
                meeting_participant=meeting_participant,
                participant_data=participant_data,
                potential_matches=potential_matches,
                verification_type='participant_match'
            )
        except Exception as e:
            logger.error(f"Failed to create verification request: {str(e)}")
            return None