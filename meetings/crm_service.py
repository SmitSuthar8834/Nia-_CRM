"""
Multi-CRM service layer with OAuth2 authentication and rate limiting
Supports Salesforce, SAP C4C, and Creatio CRM systems
"""
import json
import logging
import time
import base64
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from urllib.parse import urlencode, parse_qs, urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import models

from .models import Meeting, MeetingSession, ActionItem, ValidationSession, CRMSyncRecord

logger = logging.getLogger(__name__)


class CRMSystem(Enum):
    """Supported CRM systems"""
    SALESFORCE = "salesforce"
    SAP_C4C = "sap_c4c"
    CREATIO = "creatio"
    HUBSPOT = "hubspot"


class CRMSyncStatus(Enum):
    """Status enum for CRM synchronization operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class CRMSyncResult:
    """Result of CRM synchronization operation"""
    status: CRMSyncStatus
    message: str
    crm_record_id: Optional[str] = None
    error_details: Optional[Dict] = None
    retry_count: int = 0


@dataclass
class OAuth2Token:
    """OAuth2 token data structure"""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None


class CRMAuthenticationError(Exception):
    """Raised when CRM authentication fails"""
    pass


class CRMAPIError(Exception):
    """Raised when CRM API operations fail"""
    pass


class CRMRateLimitError(Exception):
    """Raised when CRM API rate limit is exceeded"""
    pass


class BaseCRMClient(ABC):
    """
    Abstract base class for CRM API clients with OAuth2 authentication
    """
    
    def __init__(self, crm_system: CRMSystem):
        self.crm_system = crm_system
        self.session = requests.Session()
        self.token: Optional[OAuth2Token] = None
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1  # Base delay in seconds
        self.max_delay = 60  # Maximum delay in seconds
        
        # Rate limiting
        self.rate_limit_delay = 0.1  # Minimum delay between requests
        self.last_request_time = 0
        self.requests_per_minute = 100  # Default rate limit
        self.request_timestamps = []
    
    @abstractmethod
    def get_oauth_config(self) -> Dict[str, str]:
        """Get OAuth2 configuration for the CRM system"""
        pass
    
    @abstractmethod
    def format_meeting_data(self, meeting_data: Dict) -> Dict:
        """Format meeting data for CRM-specific fields"""
        pass
    
    @abstractmethod
    def format_task_data(self, task_data: Dict) -> Dict:
        """Format task data for CRM-specific fields"""
        pass
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60
        ]
        
        # Check if we're at the rate limit
        if len(self.request_timestamps) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached for {self.crm_system.value}, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        # Add current request timestamp
        self.request_timestamps.append(current_time)
        
        # Basic delay between requests
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication token"""
        if self.token and self.token.expires_at:
            if timezone.now() < self.token.expires_at:
                return True
        
        return self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with CRM using OAuth2"""
        try:
            config = self.get_oauth_config()
            
            # Get access token using client credentials flow
            token_url = config['token_url']
            client_id = config['client_id']
            client_secret = config['client_secret']
            
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            # Add scope if specified
            if config.get('scope'):
                auth_data['scope'] = config['scope']
            
            response = self.session.post(
                token_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Calculate expiry time
            expires_in = token_data.get('expires_in', 3600)
            expires_at = timezone.now() + timedelta(seconds=expires_in - 60)  # 60s buffer
            
            self.token = OAuth2Token(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_at=expires_at,
                token_type=token_data.get('token_type', 'Bearer'),
                scope=token_data.get('scope')
            )
            
            logger.info(f"Successfully authenticated with {self.crm_system.value}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed for {self.crm_system.value}: {str(e)}")
            raise CRMAuthenticationError(f"Authentication failed: {str(e)}")
    
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
        """Make authenticated request to CRM API with retry logic"""
        if not self._ensure_authenticated():
            raise CRMAuthenticationError(f"Failed to authenticate with {self.crm_system.value}")
        
        # Check rate limiting
        self._check_rate_limit()
        
        # Prepare headers
        request_headers = {
            'Authorization': f'{self.token.token_type} {self.token.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if headers:
            request_headers.update(headers)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=30
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited by {self.crm_system.value}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle authentication expiry
                if response.status_code == 401:
                    logger.warning(f"Token expired for {self.crm_system.value}, re-authenticating")
                    self.token = None
                    if self._authenticate():
                        request_headers['Authorization'] = f'{self.token.token_type} {self.token.access_token}'
                        continue
                    else:
                        raise CRMAuthenticationError("Re-authentication failed")
                
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    logger.error(f"API request failed after {self.max_retries} retries: {str(e)}")
                    raise CRMAPIError(f"API request failed: {str(e)}")
                
                # Exponential backoff
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"API request failed (attempt {attempt + 1}), retrying in {delay}s: {str(e)}")
                time.sleep(delay)
        
        raise CRMAPIError("Maximum retries exceeded")
    
    def update_meeting_outcome(self, crm_record_id: str, meeting_data: Dict) -> Dict:
        """Update CRM record with meeting outcome"""
        formatted_data = self.format_meeting_data(meeting_data)
        return self._update_record(crm_record_id, formatted_data)
    
    def create_follow_up_task(self, crm_record_id: str, task_data: Dict) -> Dict:
        """Create follow-up task in CRM"""
        formatted_task = self.format_task_data(task_data)
        return self._create_task(crm_record_id, formatted_task)
    
    @abstractmethod
    def _update_record(self, record_id: str, data: Dict) -> Dict:
        """Update a record in the CRM system"""
        pass
    
    @abstractmethod
    def _create_task(self, record_id: str, task_data: Dict) -> Dict:
        """Create a task in the CRM system"""
        pass
    
    @abstractmethod
    def update_opportunity_stage(self, opportunity_id: str, stage_data: Dict) -> Dict:
        """Update opportunity/deal stage in the CRM system"""
        pass
    
    @abstractmethod
    def get_opportunity_details(self, opportunity_id: str) -> Dict:
        """Get opportunity/deal details from the CRM system"""
        pass


class SalesforceClient(BaseCRMClient):
    """Salesforce CRM API client with OAuth2 authentication"""
    
    def __init__(self):
        super().__init__(CRMSystem.SALESFORCE)
        self.requests_per_minute = 100  # Salesforce rate limit
    
    def get_oauth_config(self) -> Dict[str, str]:
        """Get Salesforce OAuth2 configuration"""
        return {
            'token_url': f"{getattr(settings, 'SALESFORCE_INSTANCE_URL', '')}/services/oauth2/token",
            'client_id': getattr(settings, 'SALESFORCE_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'SALESFORCE_CLIENT_SECRET', ''),
            'scope': 'api'
        }
    
    def format_meeting_data(self, meeting_data: Dict) -> Dict:
        """Format meeting data for Salesforce fields"""
        return {
            'Description': meeting_data.get('summary', ''),
            'Subject': f"Meeting: {meeting_data.get('title', 'Meeting Summary')}",
            'ActivityDate': meeting_data.get('meeting_date'),
            'Status': 'Completed',
            'Type': 'Meeting',
            'Meeting_Notes__c': meeting_data.get('notes', ''),
            'Key_Points__c': '\n'.join(f"• {point}" for point in meeting_data.get('key_points', [])),
            'Action_Items__c': '\n'.join(f"• {item}" for item in meeting_data.get('action_items', [])),
            'Next_Steps__c': meeting_data.get('next_steps', ''),
            'Meeting_Duration__c': meeting_data.get('duration_minutes')
        }
    
    def format_task_data(self, task_data: Dict) -> Dict:
        """Format task data for Salesforce Task object"""
        return {
            'Subject': task_data.get('title', 'Follow-up Task'),
            'Description': task_data.get('description', ''),
            'ActivityDate': task_data.get('due_date'),
            'Priority': task_data.get('priority', 'Normal').title(),
            'Status': 'Not Started',
            'Type': 'Task',
            'OwnerId': task_data.get('owner_id')
        }
    
    def _update_record(self, record_id: str, data: Dict) -> Dict:
        """Update Salesforce record"""
        instance_url = getattr(settings, 'SALESFORCE_INSTANCE_URL', '')
        url = f"{instance_url}/services/data/v58.0/sobjects/Activity/{record_id}"
        
        response = self._make_request('PATCH', url, data=data)
        return {'Id': record_id, 'success': True}
    
    def _create_task(self, record_id: str, task_data: Dict) -> Dict:
        """Create Salesforce Task"""
        instance_url = getattr(settings, 'SALESFORCE_INSTANCE_URL', '')
        url = f"{instance_url}/services/data/v58.0/sobjects/Task"
        
        # Link task to the record (could be Lead, Contact, or Opportunity)
        task_data['WhatId'] = record_id
        
        response = self._make_request('POST', url, data=task_data)
        return response.json()
    
    def update_opportunity_stage(self, opportunity_id: str, stage_data: Dict) -> Dict:
        """Update Salesforce Opportunity stage"""
        instance_url = getattr(settings, 'SALESFORCE_INSTANCE_URL', '')
        url = f"{instance_url}/services/data/v58.0/sobjects/Opportunity/{opportunity_id}"
        
        # Format stage data for Salesforce
        salesforce_data = {
            'StageName': stage_data.get('stage_name'),
            'Probability': stage_data.get('probability'),
            'CloseDate': stage_data.get('close_date'),
            'Amount': stage_data.get('amount'),
            'NextStep': stage_data.get('next_step'),
            'Description': stage_data.get('description')
        }
        
        # Remove None values
        salesforce_data = {k: v for k, v in salesforce_data.items() if v is not None}
        
        response = self._make_request('PATCH', url, data=salesforce_data)
        return {'Id': opportunity_id, 'success': True}
    
    def get_opportunity_details(self, opportunity_id: str) -> Dict:
        """Get Salesforce Opportunity details"""
        instance_url = getattr(settings, 'SALESFORCE_INSTANCE_URL', '')
        url = f"{instance_url}/services/data/v58.0/sobjects/Opportunity/{opportunity_id}"
        
        response = self._make_request('GET', url)
        return response.json()


class SAPC4CClient(BaseCRMClient):
    """SAP C4C CRM API client with OAuth2 authentication"""
    
    def __init__(self):
        super().__init__(CRMSystem.SAP_C4C)
        self.requests_per_minute = 60  # SAP C4C rate limit
    
    def get_oauth_config(self) -> Dict[str, str]:
        """Get SAP C4C OAuth2 configuration"""
        return {
            'token_url': f"{getattr(settings, 'SAP_C4C_BASE_URL', '')}/sap/bc/sec/oauth2/token",
            'client_id': getattr(settings, 'SAP_C4C_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'SAP_C4C_CLIENT_SECRET', ''),
            'scope': 'UIWC:CC_HOME'
        }
    
    def format_meeting_data(self, meeting_data: Dict) -> Dict:
        """Format meeting data for SAP C4C fields"""
        return {
            'Subject': f"Meeting: {meeting_data.get('title', 'Meeting Summary')}",
            'Description': meeting_data.get('summary', ''),
            'ActivityDate': meeting_data.get('meeting_date'),
            'ActivityType': 'MEETING',
            'Status': 'COMPLETED',
            'Notes': meeting_data.get('notes', ''),
            'Duration': meeting_data.get('duration_minutes'),
            'NextSteps': meeting_data.get('next_steps', '')
        }
    
    def format_task_data(self, task_data: Dict) -> Dict:
        """Format task data for SAP C4C Task object"""
        return {
            'Subject': task_data.get('title', 'Follow-up Task'),
            'Description': task_data.get('description', ''),
            'DueDate': task_data.get('due_date'),
            'Priority': task_data.get('priority', 'MEDIUM').upper(),
            'Status': 'OPEN',
            'ActivityType': 'TASK'
        }
    
    def _update_record(self, record_id: str, data: Dict) -> Dict:
        """Update SAP C4C record"""
        base_url = getattr(settings, 'SAP_C4C_BASE_URL', '')
        url = f"{base_url}/sap/c4c/odata/v1/c4codataapi/ActivityCollection('{record_id}')"
        
        response = self._make_request('PATCH', url, data=data)
        return {'Id': record_id, 'success': True}
    
    def _create_task(self, record_id: str, task_data: Dict) -> Dict:
        """Create SAP C4C Task"""
        base_url = getattr(settings, 'SAP_C4C_BASE_URL', '')
        url = f"{base_url}/sap/c4c/odata/v1/c4codataapi/ActivityCollection"
        
        # Link task to the record
        task_data['AccountID'] = record_id
        
        response = self._make_request('POST', url, data=task_data)
        return response.json()
    
    def update_opportunity_stage(self, opportunity_id: str, stage_data: Dict) -> Dict:
        """Update SAP C4C Opportunity stage"""
        base_url = getattr(settings, 'SAP_C4C_BASE_URL', '')
        url = f"{base_url}/sap/c4c/odata/v1/c4codataapi/OpportunityCollection('{opportunity_id}')"
        
        # Format stage data for SAP C4C
        c4c_data = {
            'SalesStage': stage_data.get('stage_name'),
            'Probability': stage_data.get('probability'),
            'ExpectedCloseDate': stage_data.get('close_date'),
            'ExpectedValue': stage_data.get('amount'),
            'NextSteps': stage_data.get('next_step'),
            'Description': stage_data.get('description')
        }
        
        # Remove None values
        c4c_data = {k: v for k, v in c4c_data.items() if v is not None}
        
        response = self._make_request('PATCH', url, data=c4c_data)
        return {'Id': opportunity_id, 'success': True}
    
    def get_opportunity_details(self, opportunity_id: str) -> Dict:
        """Get SAP C4C Opportunity details"""
        base_url = getattr(settings, 'SAP_C4C_BASE_URL', '')
        url = f"{base_url}/sap/c4c/odata/v1/c4codataapi/OpportunityCollection('{opportunity_id}')"
        
        response = self._make_request('GET', url)
        return response.json()


class CreatioClient(BaseCRMClient):
    """Creatio CRM API client with OAuth2 authentication"""
    
    def __init__(self):
        super().__init__(CRMSystem.CREATIO)
        self.requests_per_minute = 120  # Creatio rate limit
    
    def get_oauth_config(self) -> Dict[str, str]:
        """Get Creatio OAuth2 configuration"""
        return {
            'token_url': f"{getattr(settings, 'CREATIO_BASE_URI_IS', '')}/connect/token",
            'client_id': getattr(settings, 'CREATIO_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'CREATIO_CLIENT_SECRET', ''),
            'scope': 'api'
        }
    
    def _authenticate(self) -> bool:
        """Creatio uses OAuth2 client credentials flow"""
        try:
            config = self.get_oauth_config()
            
            # Get access token using client credentials flow
            token_url = config['token_url']
            client_id = config['client_id']
            client_secret = config['client_secret']
            
            if not token_url or not client_id or not client_secret:
                raise CRMAuthenticationError("Missing Creatio OAuth2 credentials")
            
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            response = self.session.post(
                token_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Calculate expiry time
            expires_in = token_data.get('expires_in', 3600)
            expires_at = timezone.now() + timedelta(seconds=expires_in - 60)  # 60s buffer
            
            self.token = OAuth2Token(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token'),
                expires_at=expires_at,
                token_type=token_data.get('token_type', 'Bearer'),
                scope=token_data.get('scope')
            )
            
            logger.info("Successfully authenticated with Creatio")
            return True
                
        except Exception as e:
            logger.error(f"Creatio authentication failed: {str(e)}")
            raise CRMAuthenticationError(f"Authentication failed: {str(e)}")
    
    def _make_request(self, method: str, url: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
        """Make authenticated request to Creatio API with Bearer token"""
        if not self._ensure_authenticated():
            raise CRMAuthenticationError("Failed to authenticate with Creatio")
        
        self._check_rate_limit()
        
        request_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'ForceUseSession': 'true',
            'Authorization': f'{self.token.token_type} {self.token.access_token}'
        }
        if headers:
            request_headers.update(headers)
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=30
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited by {self.crm_system.value}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle authentication expiry
                if response.status_code == 401:
                    logger.warning("Creatio token expired, re-authenticating")
                    self.token = None
                    if self._authenticate():
                        request_headers['Authorization'] = f'{self.token.token_type} {self.token.access_token}'
                        continue
                    else:
                        raise CRMAuthenticationError("Re-authentication failed")
                
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    raise CRMAPIError(f"API request failed: {str(e)}")
                
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"API request failed (attempt {attempt + 1}), retrying in {delay}s")
                time.sleep(delay)
        
        raise CRMAPIError("Maximum retries exceeded")
    
    def format_meeting_data(self, meeting_data: Dict) -> Dict:
        """Format meeting data for Creatio fields"""
        return {
            'UsrMeetingNotes': meeting_data.get('notes', ''),
            'UsrMeetingSummary': meeting_data.get('summary', ''),
            'UsrLastMeetingDate': meeting_data.get('meeting_date'),
            'UsrMeetingDuration': meeting_data.get('duration_minutes'),
            'UsrMeetingOutcome': meeting_data.get('outcome', 'completed'),
            'UsrNextSteps': meeting_data.get('next_steps', ''),
            'ModifiedOn': timezone.now().isoformat()
        }
    
    def format_task_data(self, task_data: Dict) -> Dict:
        """Format task data for Creatio Activity entity"""
        return {
            'Title': task_data.get('title', 'Follow-up Task'),
            'Notes': task_data.get('description', ''),
            'DueDate': task_data.get('due_date'),
            'StartDate': task_data.get('start_date', timezone.now().isoformat()),
            'Status': {'Name': 'Not started'},
            'Priority': {'Name': task_data.get('priority', 'Normal')},
            'Type': {'Name': 'Task'}
        }
    
    def _update_record(self, record_id: str, data: Dict) -> Dict:
        """Update Creatio record using OData"""
        base_url = getattr(settings, 'CREATIO_BASE_URL', '')
        url = f"{base_url}/0/odata/Lead({record_id})"
        
        response = self._make_request('PATCH', url, data=data)
        return {'Id': record_id, 'success': True}
    
    def _create_task(self, record_id: str, task_data: Dict) -> Dict:
        """Create Creatio Activity using OData"""
        base_url = getattr(settings, 'CREATIO_BASE_URL', '')
        url = f"{base_url}/0/odata/Activity"
        
        # Link task to the account/contact
        task_data['AccountId'] = record_id
        response = self._make_request('POST', url, data=task_data)
        return response.json()
    
    def update_opportunity_stage(self, opportunity_id: str, stage_data: Dict) -> Dict:
        """Update Creatio Opportunity stage using OData"""
        base_url = getattr(settings, 'CREATIO_BASE_URL', '')
        url = f"{base_url}/0/odata/Opportunity({opportunity_id})"
        
        # Format stage data for Creatio OData
        creatio_data = {
            'StageId': stage_data.get('stage_id'),  # Use stage ID instead of name
            'Probability': stage_data.get('probability'),
            'DueDate': stage_data.get('close_date'),
            'Budget': stage_data.get('amount'),
            'NextSteps': stage_data.get('next_step'),
            'Notes': stage_data.get('description'),
            'ModifiedOn': timezone.now().isoformat()
        }
        
        # Remove None values
        creatio_data = {k: v for k, v in creatio_data.items() if v is not None}
        
        response = self._make_request('PATCH', url, data=creatio_data)
        return {'Id': opportunity_id, 'success': True}
    
    def get_opportunity_details(self, opportunity_id: str) -> Dict:
        """Get Creatio Opportunity details using OData"""
        base_url = getattr(settings, 'CREATIO_BASE_URL', '')
        url = f"{base_url}/0/odata/Opportunity({opportunity_id})"
        
        response = self._make_request('GET', url)
        return response.json()


class HubSpotClient(BaseCRMClient):
    """HubSpot CRM API client with OAuth2 authentication"""
    
    def __init__(self):
        super().__init__(CRMSystem.HUBSPOT)
        self.requests_per_minute = 100  # HubSpot rate limit
    
    def get_oauth_config(self) -> Dict[str, str]:
        """Get HubSpot OAuth2 configuration"""
        return {
            'token_url': 'https://api.hubapi.com/oauth/v1/token',
            'client_id': getattr(settings, 'HUBSPOT_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'HUBSPOT_CLIENT_SECRET', ''),
            'scope': 'contacts crm.objects.contacts.write crm.objects.deals.write'
        }
    
    def format_meeting_data(self, meeting_data: Dict) -> Dict:
        """Format meeting data for HubSpot fields"""
        return {
            'hs_meeting_title': f"Meeting: {meeting_data.get('title', 'Meeting Summary')}",
            'hs_meeting_body': meeting_data.get('summary', ''),
            'hs_meeting_start_time': meeting_data.get('meeting_date'),
            'hs_meeting_end_time': meeting_data.get('meeting_end_date'),
            'hs_meeting_outcome': 'COMPLETED',
            'hs_meeting_notes': meeting_data.get('notes', ''),
            'hubspot_owner_id': meeting_data.get('owner_id'),
            'hs_activity_type': 'MEETING',
            'hs_timestamp': meeting_data.get('meeting_date')
        }
    
    def format_task_data(self, task_data: Dict) -> Dict:
        """Format task data for HubSpot Task object"""
        return {
            'hs_task_subject': task_data.get('title', 'Follow-up Task'),
            'hs_task_body': task_data.get('description', ''),
            'hs_task_status': 'NOT_STARTED',
            'hs_task_priority': task_data.get('priority', 'MEDIUM').upper(),
            'hs_task_type': 'TODO',
            'hs_timestamp': task_data.get('due_date'),
            'hubspot_owner_id': task_data.get('owner_id')
        }
    
    def _update_record(self, record_id: str, data: Dict) -> Dict:
        """Update HubSpot record"""
        # HubSpot uses different endpoints for different object types
        # Assuming this is a contact/deal record
        url = f"https://api.hubapi.com/crm/v3/objects/contacts/{record_id}"
        
        # HubSpot expects properties to be nested
        hubspot_data = {
            'properties': data
        }
        
        response = self._make_request('PATCH', url, data=hubspot_data)
        return response.json()
    
    def _create_task(self, record_id: str, task_data: Dict) -> Dict:
        """Create HubSpot Task"""
        url = "https://api.hubapi.com/crm/v3/objects/tasks"
        
        # HubSpot expects properties to be nested
        hubspot_data = {
            'properties': task_data,
            'associations': [
                {
                    'to': {'id': record_id},
                    'types': [{'associationCategory': 'HUBSPOT_DEFINED', 'associationTypeId': 204}]
                }
            ]
        }
        
        response = self._make_request('POST', url, data=hubspot_data)
        return response.json()
    
    def update_opportunity_stage(self, opportunity_id: str, stage_data: Dict) -> Dict:
        """Update HubSpot Deal stage"""
        url = f"https://api.hubapi.com/crm/v3/objects/deals/{opportunity_id}"
        
        # Format stage data for HubSpot
        hubspot_data = {
            'properties': {
                'dealstage': stage_data.get('stage_name'),
                'hs_probability': stage_data.get('probability'),
                'closedate': stage_data.get('close_date'),
                'amount': stage_data.get('amount'),
                'notes_next_activity_note': stage_data.get('next_step'),
                'hs_deal_stage_probability': stage_data.get('probability')
            }
        }
        
        # Remove None values from properties
        hubspot_data['properties'] = {k: v for k, v in hubspot_data['properties'].items() if v is not None}
        
        response = self._make_request('PATCH', url, data=hubspot_data)
        return response.json()
    
    def get_opportunity_details(self, opportunity_id: str) -> Dict:
        """Get HubSpot Deal details"""
        url = f"https://api.hubapi.com/crm/v3/objects/deals/{opportunity_id}"
        
        response = self._make_request('GET', url)
        return response.json()


class CRMService:
    """
    Multi-CRM service layer for synchronizing meeting outcomes and follow-up tasks
    Supports Salesforce, SAP C4C, and Creatio CRM systems with OAuth2 authentication
    """
    
    CACHE_PREFIX = "crm_sync"
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.clients = {
            CRMSystem.SALESFORCE: SalesforceClient(),
            CRMSystem.SAP_C4C: SAPC4CClient(),
            CRMSystem.CREATIO: CreatioClient(),
            CRMSystem.HUBSPOT: HubSpotClient()
        }
        self.cache = cache
    
    def get_client(self, crm_system: Union[str, CRMSystem]) -> BaseCRMClient:
        """Get CRM client for specified system"""
        if isinstance(crm_system, str):
            crm_system = CRMSystem(crm_system)
        
        if crm_system not in self.clients:
            raise ValueError(f"Unsupported CRM system: {crm_system}")
        
        return self.clients[crm_system]
    
    def sync_meeting_outcome(self, validation_session_id: int, crm_system: Union[str, CRMSystem]) -> CRMSyncResult:
        """
        Sync validated meeting outcome to specified CRM system
        """
        try:
            validation_session = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting__lead'
            ).get(id=validation_session_id)
            
            meeting = validation_session.draft_summary.bot_session.meeting
            
            if not meeting.lead or not meeting.lead.crm_id:
                return CRMSyncResult(
                    status=CRMSyncStatus.FAILED,
                    message="No associated lead or CRM ID found"
                )
            
            # Check if already synced recently
            cache_key = f"{self.CACHE_PREFIX}:validation:{validation_session_id}:{crm_system}"
            cached_result = self.cache.get(cache_key)
            if cached_result and cached_result.get('status') == CRMSyncStatus.SUCCESS.value:
                return CRMSyncResult(
                    status=CRMSyncStatus.SUCCESS,
                    message="Already synced (cached)",
                    crm_record_id=cached_result.get('crm_record_id')
                )
            
            # Get CRM client
            client = self.get_client(crm_system)
            
            # Prepare meeting data from validated session
            meeting_data = self._prepare_meeting_data_from_validation(validation_session)
            
            # Update CRM
            result = client.update_meeting_outcome(meeting.lead.crm_id, meeting_data)
            
            # Create or update CRM sync record
            sync_record, created = CRMSyncRecord.objects.get_or_create(
                validation_session=validation_session,
                crm_system=crm_system.value if isinstance(crm_system, CRMSystem) else crm_system,
                defaults={
                    'sync_status': 'completed',
                    'crm_record_id': result.get('Id', ''),
                    'sync_payload': meeting_data,
                    'synced_at': timezone.now()
                }
            )
            
            if not created:
                sync_record.sync_status = 'completed'
                sync_record.crm_record_id = result.get('Id', '')
                sync_record.sync_payload = meeting_data
                sync_record.synced_at = timezone.now()
                sync_record.error_message = ''
                sync_record.save()
            
            # Cache successful result
            sync_result = CRMSyncResult(
                status=CRMSyncStatus.SUCCESS,
                message="Meeting outcome synced successfully",
                crm_record_id=result.get('Id')
            )
            
            self.cache.set(cache_key, {
                'status': sync_result.status.value,
                'message': sync_result.message,
                'crm_record_id': sync_result.crm_record_id,
                'synced_at': timezone.now().isoformat()
            }, self.CACHE_TIMEOUT)
            
            logger.info(f"Successfully synced validation session {validation_session_id} to {crm_system}")
            return sync_result
            
        except ValidationSession.DoesNotExist:
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Validation session {validation_session_id} not found"
            )
        except (CRMAuthenticationError, CRMAPIError, CRMRateLimitError) as e:
            logger.error(f"CRM sync failed for validation session {validation_session_id}: {str(e)}")
            
            # Update sync record with error
            try:
                sync_record = CRMSyncRecord.objects.get(
                    validation_session_id=validation_session_id,
                    crm_system=crm_system.value if isinstance(crm_system, CRMSystem) else crm_system
                )
                sync_record.sync_status = 'failed'
                sync_record.error_message = str(e)
                sync_record.retry_count += 1
                sync_record.save()
            except CRMSyncRecord.DoesNotExist:
                pass
            
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=str(e),
                error_details={'error_type': type(e).__name__}
            )
        except Exception as e:
            logger.error(f"Unexpected error syncing validation session {validation_session_id}: {str(e)}")
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Unexpected error: {str(e)}",
                error_details={'error_type': type(e).__name__}
            )
    
    def create_follow_up_tasks(self, validation_session_id: int, crm_system: Union[str, CRMSystem]) -> List[CRMSyncResult]:
        """
        Create follow-up tasks in CRM from validated action items
        """
        results = []
        
        try:
            validation_session = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting__lead'
            ).get(id=validation_session_id)
            
            meeting = validation_session.draft_summary.bot_session.meeting
            
            if not meeting.lead or not meeting.lead.crm_id:
                return [CRMSyncResult(
                    status=CRMSyncStatus.FAILED,
                    message="No associated lead or CRM ID found"
                )]
            
            # Get CRM client
            client = self.get_client(crm_system)
            
            # Get action items from validated responses
            action_items = validation_session.approved_crm_updates.get('action_items', [])
            
            for action_item in action_items:
                try:
                    task_data = self._prepare_task_data_from_validation(action_item)
                    
                    result = client.create_follow_up_task(meeting.lead.crm_id, task_data)
                    
                    results.append(CRMSyncResult(
                        status=CRMSyncStatus.SUCCESS,
                        message="Follow-up task created successfully",
                        crm_record_id=result.get('Id')
                    ))
                    
                    logger.info(f"Created follow-up task for validation session {validation_session_id}")
                    
                except (CRMAuthenticationError, CRMAPIError, CRMRateLimitError) as e:
                    logger.error(f"Failed to create follow-up task: {str(e)}")
                    results.append(CRMSyncResult(
                        status=CRMSyncStatus.FAILED,
                        message=str(e),
                        error_details={'action_item': action_item}
                    ))
                except Exception as e:
                    logger.error(f"Unexpected error creating follow-up task: {str(e)}")
                    results.append(CRMSyncResult(
                        status=CRMSyncStatus.FAILED,
                        message=f"Unexpected error: {str(e)}",
                        error_details={'action_item': action_item}
                    ))
            
            return results
            
        except ValidationSession.DoesNotExist:
            return [CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Validation session {validation_session_id} not found"
            )]
        except Exception as e:
            logger.error(f"Unexpected error creating follow-up tasks: {str(e)}")
            return [CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Unexpected error: {str(e)}"
            )]
    
    def sync_to_multiple_crms(self, validation_session_id: int, crm_systems: List[Union[str, CRMSystem]]) -> Dict[str, CRMSyncResult]:
        """
        Sync to multiple CRM systems simultaneously
        """
        results = {}
        
        for crm_system in crm_systems:
            try:
                result = self.sync_meeting_outcome(validation_session_id, crm_system)
                system_key = crm_system.value if isinstance(crm_system, CRMSystem) else crm_system
                results[system_key] = result
            except Exception as e:
                system_key = crm_system.value if isinstance(crm_system, CRMSystem) else crm_system
                results[system_key] = CRMSyncResult(
                    status=CRMSyncStatus.FAILED,
                    message=f"Failed to sync to {system_key}: {str(e)}"
                )
        
        return results
    
    def _prepare_meeting_data_from_validation(self, validation_session: ValidationSession) -> Dict:
        """
        Prepare meeting data from validated session
        """
        draft_summary = validation_session.draft_summary
        meeting = draft_summary.bot_session.meeting
        
        data = {
            'title': meeting.title,
            'meeting_date': meeting.start_time.isoformat(),
            'summary': validation_session.validated_summary or draft_summary.ai_generated_summary,
            'outcome': 'completed'
        }
        
        # Add validated data from rep responses
        if validation_session.rep_responses:
            data.update({
                'notes': validation_session.rep_responses.get('meeting_notes', ''),
                'key_points': validation_session.rep_responses.get('key_points', []),
                'action_items': validation_session.rep_responses.get('action_items', []),
                'next_steps': validation_session.rep_responses.get('next_steps', ''),
                'decisions_made': validation_session.rep_responses.get('decisions_made', [])
            })
        
        # Calculate duration
        if draft_summary.bot_session.leave_time:
            duration = draft_summary.bot_session.leave_time - draft_summary.bot_session.join_time
            data['duration_minutes'] = int(duration.total_seconds() / 60)
        
        return data
    
    def _prepare_task_data_from_validation(self, action_item: Dict) -> Dict:
        """
        Prepare task data from validated action item
        """
        return {
            'title': action_item.get('title', action_item.get('description', 'Follow-up Task')[:50]),
            'description': action_item.get('description', ''),
            'due_date': action_item.get('due_date'),
            'assignee': action_item.get('assignee', ''),
            'priority': action_item.get('priority', 'Normal'),
            'start_date': timezone.now().isoformat()
        }
    
    def get_sync_status(self, validation_session_id: int, crm_system: Union[str, CRMSystem]) -> Optional[Dict]:
        """
        Get sync status for a validation session and CRM system
        """
        try:
            system_key = crm_system.value if isinstance(crm_system, CRMSystem) else crm_system
            sync_record = CRMSyncRecord.objects.get(
                validation_session_id=validation_session_id,
                crm_system=system_key
            )
            
            return {
                'status': sync_record.sync_status,
                'crm_record_id': sync_record.crm_record_id,
                'error_message': sync_record.error_message,
                'retry_count': sync_record.retry_count,
                'synced_at': sync_record.synced_at.isoformat() if sync_record.synced_at else None,
                'created_at': sync_record.created_at.isoformat()
            }
        except CRMSyncRecord.DoesNotExist:
            return None
    
    def retry_failed_sync(self, validation_session_id: int, crm_system: Union[str, CRMSystem]) -> CRMSyncResult:
        """
        Retry a failed sync operation
        """
        # Clear cache to force retry
        cache_key = f"{self.CACHE_PREFIX}:validation:{validation_session_id}:{crm_system}"
        self.cache.delete(cache_key)
        
        return self.sync_meeting_outcome(validation_session_id, crm_system)
    
    def update_opportunity_from_meeting(self, validation_session_id: int, crm_system: Union[str, CRMSystem], 
                                      opportunity_id: str, stage_updates: Dict) -> CRMSyncResult:
        """
        Update opportunity/deal stage based on meeting outcome
        """
        try:
            validation_session = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting__lead'
            ).get(id=validation_session_id)
            
            # Get CRM client
            client = self.get_client(crm_system)
            
            # Prepare stage update data
            stage_data = {
                'stage_name': stage_updates.get('stage_name'),
                'probability': stage_updates.get('probability'),
                'close_date': stage_updates.get('close_date'),
                'amount': stage_updates.get('amount'),
                'next_step': stage_updates.get('next_step'),
                'description': f"Updated from meeting: {validation_session.draft_summary.bot_session.meeting.title}"
            }
            
            # Update opportunity
            result = client.update_opportunity_stage(opportunity_id, stage_data)
            
            # Create or update CRM sync record for opportunity update
            sync_record, created = CRMSyncRecord.objects.get_or_create(
                validation_session=validation_session,
                crm_system=crm_system.value if isinstance(crm_system, CRMSystem) else crm_system,
                defaults={
                    'sync_status': 'completed',
                    'crm_record_id': opportunity_id,
                    'sync_payload': {'opportunity_update': stage_data},
                    'synced_at': timezone.now()
                }
            )
            
            if not created:
                # Update existing record
                sync_record.sync_payload.update({'opportunity_update': stage_data})
                sync_record.synced_at = timezone.now()
                sync_record.save()
            
            logger.info(f"Successfully updated opportunity {opportunity_id} from validation session {validation_session_id}")
            
            return CRMSyncResult(
                status=CRMSyncStatus.SUCCESS,
                message="Opportunity updated successfully",
                crm_record_id=opportunity_id
            )
            
        except ValidationSession.DoesNotExist:
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Validation session {validation_session_id} not found"
            )
        except Exception as e:
            logger.error(f"Failed to update opportunity {opportunity_id}: {str(e)}")
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Opportunity update failed: {str(e)}",
                error_details={'error_type': type(e).__name__}
            )
    
    def get_opportunity_sync_suggestions(self, validation_session_id: int, crm_system: Union[str, CRMSystem]) -> Dict:
        """
        Generate opportunity update suggestions based on meeting outcome
        """
        try:
            validation_session = ValidationSession.objects.select_related(
                'draft_summary__bot_session__meeting'
            ).get(id=validation_session_id)
            
            # Get meeting outcome from validated responses
            rep_responses = validation_session.rep_responses
            meeting_outcome = rep_responses.get('meeting_outcome', 'positive')
            next_steps = rep_responses.get('next_steps', '')
            
            # Generate stage suggestions based on outcome
            suggestions = {
                'stage_suggestions': [],
                'probability_adjustment': 0,
                'next_steps': next_steps,
                'follow_up_required': bool(next_steps)
            }
            
            # Basic stage progression logic
            if meeting_outcome == 'very_positive':
                suggestions['stage_suggestions'] = [
                    'Proposal/Price Quote',
                    'Negotiation/Review',
                    'Closed Won'
                ]
                suggestions['probability_adjustment'] = 20
            elif meeting_outcome == 'positive':
                suggestions['stage_suggestions'] = [
                    'Qualification',
                    'Needs Analysis',
                    'Proposal/Price Quote'
                ]
                suggestions['probability_adjustment'] = 10
            elif meeting_outcome == 'neutral':
                suggestions['stage_suggestions'] = [
                    'Qualification',
                    'Needs Analysis'
                ]
                suggestions['probability_adjustment'] = 0
            elif meeting_outcome == 'negative':
                suggestions['stage_suggestions'] = [
                    'Closed Lost',
                    'On Hold'
                ]
                suggestions['probability_adjustment'] = -20
            
            return suggestions
            
        except ValidationSession.DoesNotExist:
            return {'error': f"Validation session {validation_session_id} not found"}
        except Exception as e:
            logger.error(f"Failed to generate opportunity suggestions: {str(e)}")
            return {'error': f"Failed to generate suggestions: {str(e)}"}
    
    def bulk_sync_validation_session(self, validation_session_id: int, crm_system: Union[str, CRMSystem], 
                                   include_opportunity_update: bool = False, opportunity_data: Dict = None) -> Dict[str, CRMSyncResult]:
        """
        Perform bulk sync of meeting outcome, tasks, and optionally opportunity updates
        """
        results = {}
        
        # Sync meeting outcome
        results['meeting_sync'] = self.sync_meeting_outcome(validation_session_id, crm_system)
        
        # Create follow-up tasks
        task_results = self.create_follow_up_tasks(validation_session_id, crm_system)
        results['task_sync'] = task_results
        
        # Update opportunity if requested
        if include_opportunity_update and opportunity_data:
            opportunity_id = opportunity_data.get('opportunity_id')
            stage_updates = opportunity_data.get('stage_updates', {})
            
            if opportunity_id:
                results['opportunity_sync'] = self.update_opportunity_from_meeting(
                    validation_session_id, crm_system, opportunity_id, stage_updates
                )
        
        return results
    
    def test_connection(self, crm_system: Union[str, CRMSystem]) -> bool:
        """
        Test connection to CRM system
        """
        try:
            client = self.get_client(crm_system)
            return client._ensure_authenticated()
        except Exception as e:
            logger.error(f"Connection test failed for {crm_system}: {str(e)}")
            return False


# Compatibility wrapper for existing API
class CRMSyncService:
    """
    Compatibility wrapper for existing CRMSyncService API
    Delegates to the new CRMService with appropriate conversions
    """
    
    def __init__(self):
        self.crm_service = CRMService()
        # Default to Creatio for backward compatibility
        self.default_crm_system = CRMSystem.CREATIO
    
    def sync_meeting_outcome(self, meeting_id: int) -> CRMSyncResult:
        """
        Sync meeting outcome to CRM (backward compatibility method)
        """
        try:
            # Find the latest validation session for this meeting
            meeting = Meeting.objects.get(id=meeting_id)
            
            # Try to find a validation session through the meeting's bot session
            if hasattr(meeting, 'callbotsession'):
                bot_session = meeting.callbotsession
                if hasattr(bot_session, 'draftsummary'):
                    draft_summary = bot_session.draftsummary
                    if hasattr(draft_summary, 'validationsession'):
                        validation_session = draft_summary.validationsession
                        return self.crm_service.sync_meeting_outcome(
                            validation_session.id,
                            self.default_crm_system
                        )
            
            # If no validation session exists, create a mock one for compatibility
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message="No validation session found for meeting"
            )
            
        except Meeting.DoesNotExist:
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Meeting {meeting_id} not found"
            )
        except Exception as e:
            logger.error(f"Error in compatibility sync for meeting {meeting_id}: {str(e)}")
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Compatibility error: {str(e)}"
            )
    
    def create_follow_up_tasks(self, meeting_id: int) -> List[CRMSyncResult]:
        """
        Create follow-up tasks in CRM (backward compatibility method)
        """
        try:
            # Find the latest validation session for this meeting
            meeting = Meeting.objects.get(id=meeting_id)
            
            if hasattr(meeting, 'callbotsession'):
                bot_session = meeting.callbotsession
                if hasattr(bot_session, 'draftsummary'):
                    draft_summary = bot_session.draftsummary
                    if hasattr(draft_summary, 'validationsession'):
                        validation_session = draft_summary.validationsession
                        return self.crm_service.create_follow_up_tasks(
                            validation_session.id,
                            self.default_crm_system
                        )
            
            return [CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message="No validation session found for meeting"
            )]
            
        except Meeting.DoesNotExist:
            return [CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Meeting {meeting_id} not found"
            )]
        except Exception as e:
            logger.error(f"Error creating follow-up tasks for meeting {meeting_id}: {str(e)}")
            return [CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Compatibility error: {str(e)}"
            )]
    
    def get_sync_status(self, meeting_id: int) -> Optional[Dict]:
        """
        Get cached sync status for a meeting (backward compatibility method)
        """
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            
            if hasattr(meeting, 'callbotsession'):
                bot_session = meeting.callbotsession
                if hasattr(bot_session, 'draftsummary'):
                    draft_summary = bot_session.draftsummary
                    if hasattr(draft_summary, 'validationsession'):
                        validation_session = draft_summary.validationsession
                        return self.crm_service.get_sync_status(
                            validation_session.id,
                            self.default_crm_system
                        )
            
            return None
            
        except Meeting.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting sync status for meeting {meeting_id}: {str(e)}")
            return None
    
    def retry_failed_sync(self, meeting_id: int) -> CRMSyncResult:
        """
        Retry a failed sync operation (backward compatibility method)
        """
        try:
            meeting = Meeting.objects.get(id=meeting_id)
            
            if hasattr(meeting, 'callbotsession'):
                bot_session = meeting.callbotsession
                if hasattr(bot_session, 'draftsummary'):
                    draft_summary = bot_session.draftsummary
                    if hasattr(draft_summary, 'validationsession'):
                        validation_session = draft_summary.validationsession
                        return self.crm_service.retry_failed_sync(
                            validation_session.id,
                            self.default_crm_system
                        )
            
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message="No validation session found for meeting"
            )
            
        except Meeting.DoesNotExist:
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Meeting {meeting_id} not found"
            )
        except Exception as e:
            logger.error(f"Error retrying sync for meeting {meeting_id}: {str(e)}")
            return CRMSyncResult(
                status=CRMSyncStatus.FAILED,
                message=f"Compatibility error: {str(e)}"
            )