"""
Creatio CRM Integration Adapter
Handles OAuth 2.0 authentication and bidirectional synchronization
"""
import json
import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urljoin

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction, models

from .models import CreatioSync, SyncConflict, SyncLog, CreatioConfiguration
from apps.leads.models import Lead, ActionItem, CompetitiveIntelligence
from apps.meetings.models import Meeting, MeetingParticipant


logger = logging.getLogger(__name__)


class CreatioAuthenticationError(Exception):
    """Raised when Creatio authentication fails"""
    pass


class CreatioSyncError(Exception):
    """Raised when Creatio sync operations fail"""
    pass


class CreatioAdapter:
    """
    Creatio CRM integration adapter with OAuth 2.0 authentication
    and bidirectional synchronization capabilities
    """
    
    def __init__(self):
        self.base_url = settings.CREATIO_API_URL.rstrip('/')
        self.client_id = settings.CREATIO_CLIENT_ID
        self.client_secret = settings.CREATIO_CLIENT_SECRET
        self.token_cache_key = 'creatio_access_token'
        self.refresh_token_cache_key = 'creatio_refresh_token'
        
        # API endpoints
        self.auth_endpoint = '/0/oauth20/token'
        self.leads_endpoint = '/0/odata/Lead'
        self.contacts_endpoint = '/0/odata/Contact'
        self.activities_endpoint = '/0/odata/Activity'
        self.accounts_endpoint = '/0/odata/Account'
        
        # Field mappings (lazy-loaded)
        self._lead_field_mapping = None
        self._activity_field_mapping = None
    
    @property
    def lead_field_mapping(self) -> Dict[str, str]:
        """Get lead field mapping (lazy-loaded)"""
        if self._lead_field_mapping is None:
            self._lead_field_mapping = self._get_lead_field_mapping()
        return self._lead_field_mapping
    
    @property
    def activity_field_mapping(self) -> Dict[str, str]:
        """Get activity field mapping (lazy-loaded)"""
        if self._activity_field_mapping is None:
            self._activity_field_mapping = self._get_activity_field_mapping()
        return self._activity_field_mapping
    
    def _get_lead_field_mapping(self) -> Dict[str, str]:
        """Get field mapping configuration for leads"""
        try:
            config = CreatioConfiguration.objects.get(
                config_key='lead_field_mapping',
                is_active=True
            )
            return config.config_value
        except CreatioConfiguration.DoesNotExist:
            # Default field mapping
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
            }
    
    def _get_activity_field_mapping(self) -> Dict[str, str]:
        """Get field mapping configuration for activities"""
        try:
            config = CreatioConfiguration.objects.get(
                config_key='activity_field_mapping',
                is_active=True
            )
            return config.config_value
        except CreatioConfiguration.DoesNotExist:
            # Default field mapping
            return {
                'title': 'Title',
                'description': 'DetailedResult',
                'start_time': 'StartDate',
                'end_time': 'DueDate',
                'meeting_type': 'ActivityCategory',
                'status': 'Status',
            }
    
    def authenticate(self) -> str:
        """
        Authenticate with Creatio using OAuth 2.0 and return access token
        """
        # Check if we have a valid cached token
        access_token = cache.get(self.token_cache_key)
        if access_token:
            return access_token
        
        # Try to refresh token if available
        refresh_token = cache.get(self.refresh_token_cache_key)
        if refresh_token:
            try:
                return self._refresh_access_token(refresh_token)
            except CreatioAuthenticationError:
                logger.warning("Failed to refresh token, attempting new authentication")
        
        # Perform new authentication
        return self._authenticate_new()
    
    def _authenticate_new(self) -> str:
        """Perform new OAuth 2.0 authentication"""
        auth_url = urljoin(self.base_url, self.auth_endpoint)
        
        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        
        try:
            response = requests.post(
                auth_url,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            refresh_token = token_data.get('refresh_token')
            
            # Cache tokens
            cache.set(self.token_cache_key, access_token, expires_in - 60)  # 1 minute buffer
            if refresh_token:
                cache.set(self.refresh_token_cache_key, refresh_token, expires_in * 2)
            
            self._log_operation('info', 'authenticate', 'Successfully authenticated with Creatio')
            return access_token
            
        except requests.RequestException as e:
            error_msg = f"Creatio authentication failed: {str(e)}"
            self._log_operation('error', 'authenticate', error_msg)
            raise CreatioAuthenticationError(error_msg)
    
    def _refresh_access_token(self, refresh_token: str) -> str:
        """Refresh access token using refresh token"""
        auth_url = urljoin(self.base_url, self.auth_endpoint)
        
        refresh_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        
        try:
            response = requests.post(
                auth_url,
                data=refresh_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            
            # Cache new token
            cache.set(self.token_cache_key, access_token, expires_in - 60)
            
            self._log_operation('info', 'refresh_token', 'Successfully refreshed Creatio token')
            return access_token
            
        except requests.RequestException as e:
            error_msg = f"Token refresh failed: {str(e)}"
            self._log_operation('error', 'refresh_token', error_msg)
            raise CreatioAuthenticationError(error_msg)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated request headers"""
        access_token = self.authenticate()
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None) -> requests.Response:
        """Make authenticated request to Creatio API with retry logic"""
        url = urljoin(self.base_url, endpoint)
        headers = self._get_headers()
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 401:
                    # Token expired, clear cache and retry
                    cache.delete(self.token_cache_key)
                    if attempt < max_retries - 1:
                        headers = self._get_headers()
                        continue
                
                response.raise_for_status()
                return response
                
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise CreatioSyncError(f"Request failed after {max_retries} attempts: {str(e)}")
                
                # Exponential backoff
                import time
                time.sleep(retry_delay * (2 ** attempt))
        
        raise CreatioSyncError("Maximum retry attempts exceeded")

    def sync_leads_bidirectional(self) -> Dict[str, Any]:
        """
        Perform bidirectional synchronization of leads
        Returns summary of sync operations
        """
        sync_summary = {
            'leads_synced_to_creatio': 0,
            'leads_synced_from_creatio': 0,
            'conflicts_detected': 0,
            'errors': [],
            'start_time': timezone.now(),
        }
        
        try:
            # Sync local leads to Creatio
            local_sync_result = self._sync_local_leads_to_creatio()
            sync_summary['leads_synced_to_creatio'] = local_sync_result['synced_count']
            sync_summary['errors'].extend(local_sync_result['errors'])
            
            # Sync Creatio leads to local
            creatio_sync_result = self._sync_creatio_leads_to_local()
            sync_summary['leads_synced_from_creatio'] = creatio_sync_result['synced_count']
            sync_summary['errors'].extend(creatio_sync_result['errors'])
            
            # Handle conflicts
            conflicts = self._detect_and_handle_conflicts()
            sync_summary['conflicts_detected'] = len(conflicts)
            
            sync_summary['end_time'] = timezone.now()
            sync_summary['duration_seconds'] = (
                sync_summary['end_time'] - sync_summary['start_time']
            ).total_seconds()
            
            self._log_operation(
                'info', 
                'bidirectional_sync', 
                f"Bidirectional sync completed: {sync_summary}"
            )
            
        except Exception as e:
            error_msg = f"Bidirectional sync failed: {str(e)}"
            sync_summary['errors'].append(error_msg)
            self._log_operation('error', 'bidirectional_sync', error_msg)
        
        return sync_summary
    
    def _sync_local_leads_to_creatio(self) -> Dict[str, Any]:
        """
        Sync local leads to Creatio CRM
        """
        sync_result = {
            'synced_count': 0,
            'errors': [],
            'created_count': 0,
            'updated_count': 0,
        }
        
        # Get leads that need syncing
        leads_to_sync = Lead.objects.filter(
            models.Q(creatio_id__isnull=True) |  # New leads
            models.Q(updated_at__gt=models.F('creatiosync__last_sync'))  # Updated leads
        ).exclude(
            creatiosync__sync_status='in_progress'
        )
        
        for lead in leads_to_sync:
            try:
                sync_record, created = CreatioSync.objects.get_or_create(
                    entity_type='lead',
                    local_id=lead.id,
                    defaults={
                        'sync_status': 'in_progress',
                        'sync_direction': 'to_creatio'
                    }
                )
                
                if not created:
                    sync_record.sync_status = 'in_progress'
                    sync_record.save()
                
                # Convert lead to Creatio format
                creatio_data = self._convert_lead_to_creatio(lead)
                
                if lead.creatio_id:
                    # Update existing lead
                    response = self._make_request(
                        'PATCH',
                        f"{self.leads_endpoint}({lead.creatio_id})",
                        data=creatio_data
                    )
                    sync_result['updated_count'] += 1
                else:
                    # Create new lead
                    response = self._make_request(
                        'POST',
                        self.leads_endpoint,
                        data=creatio_data
                    )
                    
                    # Extract Creatio ID from response
                    response_data = response.json()
                    creatio_id = response_data.get('Id')
                    
                    if creatio_id:
                        lead.creatio_id = creatio_id
                        lead.save()
                        sync_result['created_count'] += 1
                
                sync_record.mark_success(lead.creatio_id)
                sync_result['synced_count'] += 1
                
                self._log_operation(
                    'info', 
                    'sync_lead', 
                    f"Successfully synced lead {lead.id} to Creatio"
                )
                
            except Exception as e:
                error_msg = f"Failed to sync lead {lead.id}: {str(e)}"
                sync_result['errors'].append(error_msg)
                sync_record.mark_failed(error_msg)
                
                self._log_operation('error', 'sync_lead', error_msg)
        
        return sync_result
    
    def _sync_creatio_leads_to_local(self) -> Dict[str, Any]:
        """
        Sync Creatio leads to local database
        """
        sync_result = {
            'synced_count': 0,
            'errors': [],
            'created_count': 0,
            'updated_count': 0,
        }
        
        try:
            # Get leads from Creatio (with pagination)
            params = {
                '$select': ','.join(self.lead_field_mapping.values()),
                '$orderby': 'ModifiedOn desc',
                '$top': 100  # Process in batches
            }
            
            response = self._make_request('GET', self.leads_endpoint, params=params)
            creatio_leads = response.json().get('value', [])
            
            for creatio_lead in creatio_leads:
                try:
                    creatio_id = creatio_lead.get('Id')
                    if not creatio_id:
                        continue
                    
                    # Check if lead exists locally
                    try:
                        local_lead = Lead.objects.get(creatio_id=creatio_id)
                        # Update existing lead
                        self._update_local_lead_from_creatio(local_lead, creatio_lead)
                        sync_result['updated_count'] += 1
                    except Lead.DoesNotExist:
                        # Create new lead
                        local_lead = self._create_local_lead_from_creatio(creatio_lead)
                        sync_result['created_count'] += 1
                    
                    # Update sync record
                    sync_record, _ = CreatioSync.objects.get_or_create(
                        entity_type='lead',
                        local_id=local_lead.id,
                        defaults={
                            'creatio_id': creatio_id,
                            'sync_direction': 'from_creatio'
                        }
                    )
                    sync_record.mark_success(creatio_id)
                    sync_result['synced_count'] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to sync Creatio lead {creatio_id}: {str(e)}"
                    sync_result['errors'].append(error_msg)
                    self._log_operation('error', 'sync_creatio_lead', error_msg)
            
        except Exception as e:
            error_msg = f"Failed to fetch leads from Creatio: {str(e)}"
            sync_result['errors'].append(error_msg)
            self._log_operation('error', 'sync_creatio_leads', error_msg)
        
        return sync_result
    
    def _convert_lead_to_creatio(self, lead: Lead) -> Dict[str, Any]:
        """
        Convert local lead to Creatio format using field mapping
        """
        creatio_data = {}
        
        for local_field, creatio_field in self.lead_field_mapping.items():
            value = getattr(lead, local_field, None)
            if value is not None:
                # Handle special field conversions
                if local_field in ['estimated_close_date'] and hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif local_field in ['estimated_budget'] and hasattr(value, '__float__'):
                    value = float(value)
                elif local_field == 'status':
                    # Map local status to Creatio status
                    status_mapping = {
                        'new': 'New',
                        'contacted': 'Contacted',
                        'qualified': 'Qualified',
                        'opportunity': 'Converted',
                        'customer': 'Converted',
                        'lost': 'Lost',
                        'disqualified': 'Disqualified'
                    }
                    value = status_mapping.get(value, 'New')
                
                creatio_data[creatio_field] = value
        
        return creatio_data
    
    def _create_local_lead_from_creatio(self, creatio_lead: Dict[str, Any]) -> Lead:
        """
        Create local lead from Creatio data
        """
        lead_data = {}
        
        # Reverse field mapping
        reverse_mapping = {v: k for k, v in self.lead_field_mapping.items()}
        
        for creatio_field, value in creatio_lead.items():
            local_field = reverse_mapping.get(creatio_field)
            if local_field and value is not None:
                # Handle special field conversions
                if local_field == 'status':
                    # Map Creatio status to local status
                    status_mapping = {
                        'New': 'new',
                        'Contacted': 'contacted',
                        'Qualified': 'qualified',
                        'Converted': 'opportunity',
                        'Lost': 'lost',
                        'Disqualified': 'disqualified'
                    }
                    value = status_mapping.get(value, 'new')
                elif local_field in ['estimated_close_date']:
                    from datetime import datetime
                    try:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                    except (ValueError, AttributeError):
                        value = None
                
                lead_data[local_field] = value
        
        # Set required fields with defaults if not provided
        lead_data.setdefault('source', 'crm_sync')
        lead_data.setdefault('creatio_id', creatio_lead.get('Id'))
        
        return Lead.objects.create(**lead_data)
    
    def _update_local_lead_from_creatio(self, lead: Lead, creatio_lead: Dict[str, Any]):
        """
        Update local lead with Creatio data
        """
        reverse_mapping = {v: k for k, v in self.lead_field_mapping.items()}
        updated_fields = []
        
        for creatio_field, value in creatio_lead.items():
            local_field = reverse_mapping.get(creatio_field)
            if local_field and value is not None:
                current_value = getattr(lead, local_field, None)
                
                # Handle field conversions (same as create)
                if local_field == 'status':
                    status_mapping = {
                        'New': 'new',
                        'Contacted': 'contacted',
                        'Qualified': 'qualified',
                        'Converted': 'opportunity',
                        'Lost': 'lost',
                        'Disqualified': 'disqualified'
                    }
                    value = status_mapping.get(value, 'new')
                elif local_field in ['estimated_close_date']:
                    from datetime import datetime
                    try:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                    except (ValueError, AttributeError):
                        continue
                
                # Only update if value has changed
                if current_value != value:
                    setattr(lead, local_field, value)
                    updated_fields.append(local_field)
        
        if updated_fields:
            lead.save(update_fields=updated_fields)
    
    def _detect_and_handle_conflicts(self) -> List[SyncConflict]:
        """
        Detect and handle synchronization conflicts
        """
        conflicts = []
        
        # Find sync records with potential conflicts
        sync_records = CreatioSync.objects.filter(
            sync_status__in=['conflict', 'failed'],
            entity_type='lead'
        )
        
        for sync_record in sync_records:
            try:
                # Get local and Creatio data
                local_lead = Lead.objects.get(id=sync_record.local_id)
                
                if sync_record.creatio_id:
                    response = self._make_request(
                        'GET',
                        f"{self.leads_endpoint}({sync_record.creatio_id})"
                    )
                    creatio_data = response.json()
                    
                    # Compare data and detect conflicts
                    field_conflicts = self._compare_lead_data(local_lead, creatio_data)
                    
                    for field_name, conflict_data in field_conflicts.items():
                        conflict = SyncConflict.objects.create(
                            sync_record=sync_record,
                            conflict_type='data_mismatch',
                            field_name=field_name,
                            local_value=conflict_data['local'],
                            creatio_value=conflict_data['creatio']
                        )
                        conflicts.append(conflict)
                
            except Exception as e:
                self._log_operation(
                    'error', 
                    'conflict_detection', 
                    f"Failed to detect conflicts for {sync_record.id}: {str(e)}"
                )
        
        return conflicts
    
    def _compare_lead_data(self, lead: Lead, creatio_data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Compare local lead data with Creatio data to detect conflicts
        """
        conflicts = {}
        reverse_mapping = {v: k for k, v in self.lead_field_mapping.items()}
        
        for creatio_field, creatio_value in creatio_data.items():
            local_field = reverse_mapping.get(creatio_field)
            if local_field:
                local_value = getattr(lead, local_field, None)
                
                # Normalize values for comparison
                normalized_local = self._normalize_value(local_value)
                normalized_creatio = self._normalize_value(creatio_value)
                
                if normalized_local != normalized_creatio:
                    conflicts[local_field] = {
                        'local': local_value,
                        'creatio': creatio_value
                    }
        
        return conflicts
    
    def _normalize_value(self, value):
        """
        Normalize values for comparison
        """
        if value is None:
            return None
        elif isinstance(value, str):
            return value.strip().lower()
        elif hasattr(value, 'isoformat'):
            return value.isoformat()
        else:
            return str(value)
    
    def update_lead_from_meeting(self, lead_id: str, meeting_data: Dict[str, Any]) -> bool:
        """
        Update lead with meeting-derived data
        """
        try:
            lead = Lead.objects.get(id=lead_id)
            
            # Update meeting statistics
            lead.update_meeting_stats()
            
            # Update qualification score based on meeting data
            if 'qualification_insights' in meeting_data:
                insights = meeting_data['qualification_insights']
                if 'budget_discussed' in insights and insights['budget_discussed']:
                    lead.qualification_score += 10
                if 'timeline_discussed' in insights and insights['timeline_discussed']:
                    lead.qualification_score += 10
                if 'decision_maker_identified' in insights and insights['decision_maker_identified']:
                    lead.qualification_score += 15
                
                # Cap at 100
                lead.qualification_score = min(lead.qualification_score, 100)
            
            # Update relationship stage based on meeting type
            if 'meeting_type' in meeting_data:
                meeting_type = meeting_data['meeting_type']
                stage_mapping = {
                    'discovery': 'warm',
                    'demo': 'hot',
                    'negotiation': 'negotiating',
                    'closing': 'closing'
                }
                if meeting_type in stage_mapping:
                    lead.relationship_stage = stage_mapping[meeting_type]
            
            # Update estimated close date if discussed
            if 'estimated_close_date' in meeting_data and meeting_data['estimated_close_date']:
                lead.estimated_close_date = meeting_data['estimated_close_date']
            
            # Update budget if discussed
            if 'estimated_budget' in meeting_data and meeting_data['estimated_budget']:
                lead.estimated_budget = meeting_data['estimated_budget']
            
            lead.save()
            
            # Create sync record for Creatio update
            sync_record, _ = CreatioSync.objects.get_or_create(
                entity_type='lead',
                local_id=lead.id,
                defaults={'sync_status': 'pending', 'sync_direction': 'to_creatio'}
            )
            
            if sync_record.sync_status != 'pending':
                sync_record.sync_status = 'pending'
                sync_record.save()
            
            self._log_operation(
                'info',
                'update_lead_from_meeting',
                f"Updated lead {lead_id} with meeting data"
            )
            
            return True
            
        except Lead.DoesNotExist:
            self._log_operation(
                'error',
                'update_lead_from_meeting',
                f"Lead {lead_id} not found"
            )
            return False
        except Exception as e:
            self._log_operation(
                'error',
                'update_lead_from_meeting',
                f"Failed to update lead {lead_id}: {str(e)}"
            )
            return False
    
    def create_activity_for_meeting(self, meeting: Meeting) -> bool:
        """
        Create activity record in Creatio for meeting
        """
        try:
            # Convert meeting to Creatio activity format
            activity_data = self._convert_meeting_to_activity(meeting)
            
            response = self._make_request(
                'POST',
                self.activities_endpoint,
                data=activity_data
            )
            
            activity_id = response.json().get('Id')
            
            if activity_id:
                # Create sync record
                CreatioSync.objects.create(
                    entity_type='activity',
                    local_id=meeting.id,
                    creatio_id=activity_id,
                    sync_status='success',
                    sync_direction='to_creatio'
                )
                
                self._log_operation(
                    'info',
                    'create_activity',
                    f"Created activity {activity_id} for meeting {meeting.id}"
                )
                
                return True
            
        except Exception as e:
            self._log_operation(
                'error',
                'create_activity',
                f"Failed to create activity for meeting {meeting.id}: {str(e)}"
            )
        
        return False
    
    def _convert_meeting_to_activity(self, meeting: Meeting) -> Dict[str, Any]:
        """
        Convert meeting to Creatio activity format
        """
        activity_data = {}
        
        for local_field, creatio_field in self.activity_field_mapping.items():
            value = getattr(meeting, local_field, None)
            if value is not None:
                if local_field in ['start_time', 'end_time'] and hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif local_field == 'meeting_type':
                    # Map meeting type to Creatio activity category
                    type_mapping = {
                        'discovery': 'Meeting',
                        'demo': 'Presentation',
                        'negotiation': 'Meeting',
                        'follow_up': 'Call',
                        'closing': 'Meeting'
                    }
                    value = type_mapping.get(value, 'Meeting')
                elif local_field == 'status':
                    # Map meeting status to activity status
                    status_mapping = {
                        'scheduled': 'Planned',
                        'in_progress': 'In Progress',
                        'completed': 'Completed',
                        'cancelled': 'Cancelled'
                    }
                    value = status_mapping.get(value, 'Planned')
                
                activity_data[creatio_field] = value
        
        # Add additional fields
        activity_data['ActivityCategory'] = 'Meeting'
        activity_data['Type'] = 'Meeting'
        
        return activity_data
    
    def resolve_conflict(self, conflict_id: str, resolution: str, user=None) -> bool:
        """
        Resolve synchronization conflict
        """
        try:
            conflict = SyncConflict.objects.get(id=conflict_id)
            
            if resolution == 'local_wins':
                # Use local value, sync to Creatio
                conflict.resolve('resolved_local', conflict.local_value, user)
                # Trigger sync to Creatio
                conflict.sync_record.sync_status = 'pending'
                conflict.sync_record.save()
                
            elif resolution == 'creatio_wins':
                # Use Creatio value, update local
                conflict.resolve('resolved_creatio', conflict.creatio_value, user)
                # Update local record
                self._apply_creatio_value_to_local(conflict)
                
            elif resolution == 'manual':
                # Manual resolution handled separately
                conflict.resolve('resolved_manual', None, user)
            
            self._log_operation(
                'info',
                'resolve_conflict',
                f"Resolved conflict {conflict_id} with resolution: {resolution}"
            )
            
            return True
            
        except SyncConflict.DoesNotExist:
            self._log_operation(
                'error',
                'resolve_conflict',
                f"Conflict {conflict_id} not found"
            )
            return False
        except Exception as e:
            self._log_operation(
                'error',
                'resolve_conflict',
                f"Failed to resolve conflict {conflict_id}: {str(e)}"
            )
            return False
    
    def _apply_creatio_value_to_local(self, conflict: SyncConflict):
        """
        Apply Creatio value to local record
        """
        try:
            if conflict.sync_record.entity_type == 'lead':
                lead = Lead.objects.get(id=conflict.sync_record.local_id)
                setattr(lead, conflict.field_name, conflict.creatio_value)
                lead.save(update_fields=[conflict.field_name])
                
        except Exception as e:
            self._log_operation(
                'error',
                'apply_creatio_value',
                f"Failed to apply Creatio value: {str(e)}"
            )
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get overall synchronization status
        """
        from django.db.models import Count
        
        status_summary = CreatioSync.objects.values('sync_status').annotate(
            count=Count('id')
        )
        
        conflict_summary = SyncConflict.objects.values('resolution_status').annotate(
            count=Count('id')
        )
        
        return {
            'sync_status': {item['sync_status']: item['count'] for item in status_summary},
            'conflicts': {item['resolution_status']: item['count'] for item in conflict_summary},
            'last_sync': CreatioSync.objects.filter(
                sync_status='success'
            ).order_by('-last_sync').first()
        }
    
    def _log_operation(self, level: str, operation: str, message: str, 
                      entity_type: str = None, entity_id: str = None,
                      request_data: Dict = None, response_data: Dict = None):
        """
        Log sync operation
        """
        SyncLog.objects.create(
            log_level=level,
            operation_type=operation,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            request_data=request_data,
            response_data=response_data
        )

    def _convert_lead_to_creatio(self, lead: Lead) -> Dict[str, Any]:
        """
        Convert local lead to Creatio format using field mapping
        """
        creatio_data = {}
        
        for local_field, creatio_field in self.lead_field_mapping.items():
            value = getattr(lead, local_field, None)
            if value is not None:
                # Handle special field conversions
                if local_field in ['estimated_close_date'] and hasattr(value, 'isoformat'):
                    value = value.isoformat()
                elif local_field in ['estimated_budget'] and hasattr(value, '__float__'):
                    value = float(value)
                elif local_field == 'status':
                    # Map local status to Creatio status
                    status_mapping = {
                        'new': 'New',
                        'contacted': 'Contacted',
                        'qualified': 'Qualified',
                        'opportunity': 'Converted',
                        'customer': 'Converted',
                        'lost': 'Lost',
                        'disqualified': 'Disqualified'
                    }
                    value = status_mapping.get(value, 'New')
                
                creatio_data[creatio_field] = value
        
        return creatio_data