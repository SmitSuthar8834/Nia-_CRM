"""
LinkedIn Integration for Enhanced Participant Matching
"""
import logging
import requests
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


class LinkedInProfileService:
    """
    Service for LinkedIn profile integration and enhanced matching
    """
    
    def __init__(self):
        self.api_base_url = "https://api.linkedin.com/v2"
        self.cache_timeout = 3600  # 1 hour cache
    
    def search_profiles(self, name: str, company: str = None, email: str = None) -> List[Dict]:
        """
        Search LinkedIn profiles for enhanced participant matching
        
        Args:
            name: Full name to search for
            company: Company name for filtering
            email: Email address for verification
            
        Returns:
            List of LinkedIn profile matches with confidence scores
        """
        # Check cache first
        cache_key = f"linkedin_search_{name}_{company}_{email}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        profiles = []
        
        try:
            # Note: This is a simplified implementation
            # In production, you would need proper LinkedIn API credentials
            # and handle OAuth authentication
            
            if not self._has_linkedin_credentials():
                logger.warning("LinkedIn API credentials not configured")
                return profiles
            
            # Search for profiles
            search_results = self._search_linkedin_api(name, company)
            
            for profile_data in search_results:
                profile_match = self._analyze_profile_match(
                    profile_data, name, company, email
                )
                if profile_match['confidence'] > 0.3:  # Minimum threshold
                    profiles.append(profile_match)
            
            # Cache results
            cache.set(cache_key, profiles, self.cache_timeout)
            
        except Exception as e:
            logger.error(f"LinkedIn profile search failed: {str(e)}")
        
        return sorted(profiles, key=lambda x: x['confidence'], reverse=True)
    
    def enrich_participant_data(self, participant: Dict) -> Dict:
        """
        Enrich participant data with LinkedIn profile information
        
        Args:
            participant: Participant dictionary
            
        Returns:
            Enhanced participant data with LinkedIn information
        """
        name = participant.get('name', '')
        company = participant.get('company', '')
        email = participant.get('email', '')
        
        if not name:
            return participant
        
        # Search for LinkedIn profiles
        profiles = self.search_profiles(name, company, email)
        
        if profiles:
            best_match = profiles[0]  # Highest confidence match
            
            # Enrich participant data
            enhanced_participant = participant.copy()
            enhanced_participant.update({
                'linkedin_profile': best_match.get('profile_url'),
                'linkedin_confidence': best_match.get('confidence'),
                'enhanced_title': best_match.get('title', participant.get('title')),
                'enhanced_company': best_match.get('company', participant.get('company')),
                'industry': best_match.get('industry'),
                'location': best_match.get('location'),
                'profile_summary': best_match.get('summary'),
                'experience_years': best_match.get('experience_years'),
                'skills': best_match.get('skills', []),
                'education': best_match.get('education', [])
            })
            
            return enhanced_participant
        
        return participant
    
    def _has_linkedin_credentials(self) -> bool:
        """Check if LinkedIn API credentials are configured"""
        return (
            hasattr(settings, 'LINKEDIN_CLIENT_ID') and
            hasattr(settings, 'LINKEDIN_CLIENT_SECRET') and
            hasattr(settings, 'LINKEDIN_ACCESS_TOKEN')
        )
    
    def _search_linkedin_api(self, name: str, company: str = None) -> List[Dict]:
        """
        Search LinkedIn API for profiles
        
        Note: This is a simplified implementation. In production, you would need:
        1. Proper OAuth 2.0 authentication flow
        2. LinkedIn Partner Program access for profile search
        3. Rate limiting and error handling
        4. Compliance with LinkedIn's API terms of service
        """
        if not self._has_linkedin_credentials():
            return []
        
        headers = {
            'Authorization': f'Bearer {settings.LINKEDIN_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        # Build search query
        search_params = {
            'keywords': name,
            'facet': 'network',
            'facetNetwork': ['F', 'S', 'O']  # 1st, 2nd, 3rd+ connections
        }
        
        if company:
            search_params['facetCurrentCompany'] = company
        
        try:
            # Note: LinkedIn's People Search API requires special permissions
            # This is a placeholder implementation
            response = requests.get(
                f"{self.api_base_url}/people-search",
                headers=headers,
                params=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('elements', [])
            else:
                logger.warning(f"LinkedIn API returned status {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f"LinkedIn API request failed: {str(e)}")
        
        return []
    
    def _analyze_profile_match(self, profile_data: Dict, name: str, company: str = None, email: str = None) -> Dict:
        """
        Analyze LinkedIn profile match confidence
        
        Args:
            profile_data: LinkedIn profile data
            name: Target name
            company: Target company
            email: Target email
            
        Returns:
            Profile match with confidence score
        """
        from difflib import SequenceMatcher
        
        profile_name = profile_data.get('formattedName', '')
        profile_company = profile_data.get('positions', {}).get('values', [{}])[0].get('company', {}).get('name', '')
        profile_title = profile_data.get('headline', '')
        
        # Calculate name similarity
        name_similarity = SequenceMatcher(None, name.lower(), profile_name.lower()).ratio()
        
        # Calculate company similarity
        company_similarity = 0.0
        if company and profile_company:
            company_similarity = SequenceMatcher(None, company.lower(), profile_company.lower()).ratio()
        
        # Base confidence from name match
        confidence = name_similarity * 0.7
        
        # Boost confidence with company match
        if company_similarity > 0.5:
            confidence += company_similarity * 0.3
        
        # Additional factors
        if email and self._email_matches_profile(email, profile_data):
            confidence += 0.2
        
        # Industry relevance (if available)
        industry = profile_data.get('industry', '')
        if industry and self._is_business_relevant_industry(industry):
            confidence += 0.05
        
        return {
            'profile_url': profile_data.get('publicProfileUrl', ''),
            'name': profile_name,
            'title': profile_title,
            'company': profile_company,
            'industry': industry,
            'location': profile_data.get('location', {}).get('name', ''),
            'summary': profile_data.get('summary', ''),
            'confidence': min(confidence, 0.95),  # Cap at 95%
            'experience_years': self._calculate_experience_years(profile_data),
            'skills': self._extract_skills(profile_data),
            'education': self._extract_education(profile_data)
        }
    
    def _email_matches_profile(self, email: str, profile_data: Dict) -> bool:
        """Check if email matches LinkedIn profile indicators"""
        # This would require additional LinkedIn API calls or data
        # that may not be available through standard API access
        return False
    
    def _is_business_relevant_industry(self, industry: str) -> bool:
        """Check if industry is relevant for business/sales context"""
        business_industries = [
            'technology', 'software', 'consulting', 'financial services',
            'healthcare', 'manufacturing', 'retail', 'telecommunications',
            'media', 'education', 'government', 'non-profit'
        ]
        
        industry_lower = industry.lower()
        return any(biz_industry in industry_lower for biz_industry in business_industries)
    
    def _calculate_experience_years(self, profile_data: Dict) -> int:
        """Calculate years of experience from LinkedIn profile"""
        positions = profile_data.get('positions', {}).get('values', [])
        
        total_months = 0
        for position in positions:
            start_date = position.get('startDate', {})
            end_date = position.get('endDate', {})
            
            if start_date:
                start_year = start_date.get('year', 0)
                start_month = start_date.get('month', 1)
                
                if end_date:
                    end_year = end_date.get('year', 0)
                    end_month = end_date.get('month', 12)
                else:
                    # Current position
                    from datetime import datetime
                    now = datetime.now()
                    end_year = now.year
                    end_month = now.month
                
                if start_year and end_year:
                    months = (end_year - start_year) * 12 + (end_month - start_month)
                    total_months += max(months, 0)
        
        return max(total_months // 12, 0)
    
    def _extract_skills(self, profile_data: Dict) -> List[str]:
        """Extract skills from LinkedIn profile"""
        skills_data = profile_data.get('skills', {}).get('values', [])
        return [skill.get('skill', {}).get('name', '') for skill in skills_data if skill.get('skill')]
    
    def _extract_education(self, profile_data: Dict) -> List[Dict]:
        """Extract education information from LinkedIn profile"""
        education_data = profile_data.get('educations', {}).get('values', [])
        education_list = []
        
        for edu in education_data:
            education_list.append({
                'school': edu.get('schoolName', ''),
                'degree': edu.get('degree', ''),
                'field_of_study': edu.get('fieldOfStudy', ''),
                'start_year': edu.get('startDate', {}).get('year'),
                'end_year': edu.get('endDate', {}).get('year')
            })
        
        return education_list


class SocialProfileMatcher:
    """
    Enhanced matching using social profile data
    """
    
    def __init__(self):
        self.linkedin_service = LinkedInProfileService()
    
    def enhance_participant_matching(self, participant: Dict, potential_matches: List[Dict]) -> List[Dict]:
        """
        Enhance participant matching using social profile data
        
        Args:
            participant: Participant information
            potential_matches: List of potential lead matches
            
        Returns:
            Enhanced matches with social profile confidence scores
        """
        enhanced_matches = []
        
        # Get LinkedIn profile data for participant
        linkedin_profiles = self.linkedin_service.search_profiles(
            participant.get('name', ''),
            participant.get('company', ''),
            participant.get('email', '')
        )
        
        if not linkedin_profiles:
            return potential_matches
        
        best_linkedin_profile = linkedin_profiles[0]
        
        for match in potential_matches:
            lead = match['lead']
            enhanced_match = match.copy()
            
            # Calculate social profile match confidence
            social_confidence = self._calculate_social_match_confidence(
                best_linkedin_profile, lead
            )
            
            # Combine original confidence with social profile confidence
            original_confidence = match['confidence']
            combined_confidence = (original_confidence * 0.7) + (social_confidence * 0.3)
            
            enhanced_match.update({
                'confidence': min(combined_confidence, 0.98),  # Cap at 98%
                'social_profile_confidence': social_confidence,
                'linkedin_profile': best_linkedin_profile.get('profile_url'),
                'enhanced_with_social': True
            })
            
            enhanced_matches.append(enhanced_match)
        
        return sorted(enhanced_matches, key=lambda x: x['confidence'], reverse=True)
    
    def _calculate_social_match_confidence(self, linkedin_profile: Dict, lead) -> float:
        """Calculate confidence based on social profile match"""
        from difflib import SequenceMatcher
        
        confidence = 0.0
        
        # Name similarity
        linkedin_name = linkedin_profile.get('name', '')
        if linkedin_name:
            name_similarity = SequenceMatcher(
                None, linkedin_name.lower(), lead.full_name.lower()
            ).ratio()
            confidence += name_similarity * 0.4
        
        # Company similarity
        linkedin_company = linkedin_profile.get('company', '')
        if linkedin_company and lead.company:
            company_similarity = SequenceMatcher(
                None, linkedin_company.lower(), lead.company.lower()
            ).ratio()
            confidence += company_similarity * 0.3
        
        # Title similarity
        linkedin_title = linkedin_profile.get('title', '')
        if linkedin_title and lead.title:
            title_similarity = SequenceMatcher(
                None, linkedin_title.lower(), lead.title.lower()
            ).ratio()
            confidence += title_similarity * 0.2
        
        # Industry relevance
        industry = linkedin_profile.get('industry', '')
        if industry:
            confidence += 0.1  # Small boost for having industry data
        
        return min(confidence, 0.9)  # Cap at 90%