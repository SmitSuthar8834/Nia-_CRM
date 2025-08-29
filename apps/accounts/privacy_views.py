"""
Privacy and data protection views
"""
import json
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from .models import (
    ConsentRecord, DataRetentionPolicy, DataDeletionRequest, 
    EncryptedDataField, PrivacySettings, UserActivity
)
from .permissions import AdminOnlyPermission
from .encryption import DataEncryption, PIIEncryption, DataAnonymization
from .serializers import UserProfileSerializer


class ConsentManagementView(APIView):
    """
    Manage user consent for data processing
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Privacy'],
        summary='Get User Consent Status',
        description='Get current consent status for all data processing types.',
        responses={
            200: {
                'description': 'Consent status retrieved',
                'examples': [
                    OpenApiExample(
                        'Consent Status',
                        value={
                            'consents': [
                                {
                                    'consent_type': 'call_recording',
                                    'status': 'granted',
                                    'granted_at': '2024-01-01T10:00:00Z',
                                    'expires_at': None,
                                    'is_active': True
                                }
                            ]
                        }
                    )
                ]
            }
        }
    )
    def get(self, request):
        """Get user's consent status"""
        consents = ConsentRecord.objects.filter(user=request.user)
        
        consent_data = []
        for consent in consents:
            consent_data.append({
                'consent_type': consent.consent_type,
                'status': consent.status,
                'granted_at': consent.granted_at.isoformat() if consent.granted_at else None,
                'withdrawn_at': consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                'expires_at': consent.expires_at.isoformat() if consent.expires_at else None,
                'is_active': consent.is_active,
                'purpose': consent.purpose
            })
        
        return Response({
            'consents': consent_data
        })
    
    @extend_schema(
        tags=['Privacy'],
        summary='Grant or Update Consent',
        description='Grant or update consent for specific data processing types.',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'consent_type': {
                        'type': 'string',
                        'enum': ['call_recording', 'transcription', 'ai_analysis', 'data_storage', 'analytics', 'marketing', 'third_party_sharing']
                    },
                    'status': {
                        'type': 'string',
                        'enum': ['granted', 'denied']
                    },
                    'expires_at': {'type': 'string', 'format': 'date-time', 'nullable': True}
                },
                'required': ['consent_type', 'status']
            }
        },
        responses={
            200: {
                'description': 'Consent updated successfully'
            },
            400: {
                'description': 'Invalid consent data'
            }
        }
    )
    def post(self, request):
        """Grant or update consent"""
        consent_type = request.data.get('consent_type')
        status_value = request.data.get('status')
        expires_at = request.data.get('expires_at')
        
        if not consent_type or not status_value:
            return Response({
                'error': 'consent_type and status are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create consent record
        consent, created = ConsentRecord.objects.get_or_create(
            user=request.user,
            consent_type=consent_type,
            defaults={
                'status': status_value,
                'purpose': f'User consent for {consent_type}',
                'ip_address': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'expires_at': expires_at
            }
        )
        
        if not created:
            # Update existing consent
            consent.status = status_value
            consent.expires_at = expires_at
            if status_value == 'granted':
                consent.withdrawn_at = None
            elif status_value == 'denied':
                consent.withdrawn_at = timezone.now()
            consent.save()
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='settings_change',
            description=f'Consent {status_value} for {consent_type}',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'message': f'Consent {status_value} for {consent_type}'
        })
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PrivacySettingsView(generics.RetrieveUpdateAPIView):
    """
    Manage user privacy settings
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Privacy'],
        summary='Get Privacy Settings',
        description='Get current user\'s privacy settings and preferences.',
        responses={
            200: {
                'description': 'Privacy settings retrieved',
                'examples': [
                    OpenApiExample(
                        'Privacy Settings',
                        value={
                            'allow_ai_analysis': True,
                            'allow_transcript_storage': True,
                            'allow_analytics_processing': True,
                            'allow_third_party_integrations': True,
                            'share_anonymized_data': False,
                            'share_with_team_members': True,
                            'share_with_managers': True,
                            'auto_delete_transcripts': False,
                            'transcript_retention_days': 2555
                        }
                    )
                ]
            }
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        tags=['Privacy'],
        summary='Update Privacy Settings',
        description='Update user\'s privacy settings and preferences.',
        responses={
            200: {
                'description': 'Privacy settings updated'
            }
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    def get_object(self):
        settings_obj, created = PrivacySettings.objects.get_or_create(user=self.request.user)
        return settings_obj
    
    def get_serializer_class(self):
        from .serializers import PrivacySettingsSerializer
        return PrivacySettingsSerializer


class DataExportView(APIView):
    """
    Export user data for GDPR compliance
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Privacy'],
        summary='Export User Data',
        description='Export all user data in a portable format (GDPR compliance).',
        parameters=[
            OpenApiParameter(
                name='format',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Export format (json, csv)',
                enum=['json', 'csv'],
                default='json'
            ),
            OpenApiParameter(
                name='anonymize',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='Anonymize sensitive data',
                default=False
            )
        ],
        responses={
            200: {
                'description': 'Data export file',
                'content': {
                    'application/json': {},
                    'text/csv': {}
                }
            }
        }
    )
    def get(self, request):
        """Export user data"""
        export_format = request.query_params.get('format', 'json')
        anonymize = request.query_params.get('anonymize', 'false').lower() == 'true'
        
        # Collect user data
        user_data = self._collect_user_data(request.user, anonymize)
        
        if export_format == 'csv':
            return self._export_as_csv(user_data)
        else:
            return self._export_as_json(user_data)
    
    def _collect_user_data(self, user, anonymize=False):
        """Collect all user data for export"""
        data = {
            'export_info': {
                'user_id': user.id if not anonymize else f"user_{user.id}",
                'username': user.username if not anonymize else f"user_{user.id}",
                'export_date': timezone.now().isoformat(),
                'anonymized': anonymize
            },
            'profile': {
                'email': user.email if not anonymize else PIIEncryption.mask_pii_for_display(user.email, 'email'),
                'first_name': user.first_name if not anonymize else '***',
                'last_name': user.last_name if not anonymize else '***',
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            },
            'consent_records': [],
            'privacy_settings': {},
            'activity_logs': [],
            'encrypted_data': []
        }
        
        # Add consent records
        consents = ConsentRecord.objects.filter(user=user)
        for consent in consents:
            data['consent_records'].append({
                'consent_type': consent.consent_type,
                'status': consent.status,
                'granted_at': consent.granted_at.isoformat(),
                'purpose': consent.purpose
            })
        
        # Add privacy settings
        try:
            privacy_settings = PrivacySettings.objects.get(user=user)
            data['privacy_settings'] = {
                'allow_ai_analysis': privacy_settings.allow_ai_analysis,
                'allow_transcript_storage': privacy_settings.allow_transcript_storage,
                'auto_delete_transcripts': privacy_settings.auto_delete_transcripts,
                'transcript_retention_days': privacy_settings.transcript_retention_days
            }
        except PrivacySettings.DoesNotExist:
            pass
        
        # Add recent activity (last 90 days)
        recent_activities = UserActivity.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(days=90)
        )[:100]  # Limit to 100 most recent
        
        for activity in recent_activities:
            data['activity_logs'].append({
                'activity_type': activity.activity_type,
                'description': activity.description,
                'created_at': activity.created_at.isoformat(),
                'ip_address': activity.ip_address if not anonymize else '***'
            })
        
        # Add encrypted data metadata (not the actual encrypted content)
        encrypted_fields = EncryptedDataField.objects.filter(owner=user)
        for field in encrypted_fields:
            data['encrypted_data'].append({
                'field_type': field.field_type,
                'sensitivity_level': field.sensitivity_level,
                'encrypted_at': field.encrypted_at.isoformat(),
                'access_count': field.access_count,
                'last_accessed': field.last_accessed.isoformat() if field.last_accessed else None
            })
        
        return data
    
    def _export_as_json(self, data):
        """Export data as JSON"""
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="user_data_export_{timezone.now().strftime("%Y%m%d")}.json"'
        return response
    
    def _export_as_csv(self, data):
        """Export data as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write profile data
        writer.writerow(['Profile Data'])
        writer.writerow(['Field', 'Value'])
        for key, value in data['profile'].items():
            writer.writerow([key, value])
        
        writer.writerow([])  # Empty row
        
        # Write consent records
        writer.writerow(['Consent Records'])
        writer.writerow(['Type', 'Status', 'Granted At', 'Purpose'])
        for consent in data['consent_records']:
            writer.writerow([
                consent['consent_type'],
                consent['status'],
                consent['granted_at'],
                consent['purpose']
            ])
        
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="user_data_export_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response


class DataDeletionRequestView(APIView):
    """
    Handle data deletion requests (Right to be Forgotten)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Privacy'],
        summary='Request Data Deletion',
        description='Request deletion of user data (GDPR Right to be Forgotten).',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'data_types': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Types of data to delete'
                    },
                    'include_backups': {'type': 'boolean', 'default': True},
                    'reason': {'type': 'string', 'description': 'Reason for deletion request'}
                },
                'required': ['data_types']
            }
        },
        responses={
            201: {
                'description': 'Deletion request created',
                'examples': [
                    OpenApiExample(
                        'Request Created',
                        value={
                            'request_id': 'uuid-string',
                            'status': 'pending',
                            'message': 'Data deletion request submitted successfully'
                        }
                    )
                ]
            }
        }
    )
    def post(self, request):
        """Create data deletion request"""
        data_types = request.data.get('data_types', [])
        include_backups = request.data.get('include_backups', True)
        reason = request.data.get('reason', 'User requested data deletion')
        
        if not data_types:
            return Response({
                'error': 'data_types is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create deletion request
        deletion_request = DataDeletionRequest.objects.create(
            user=request.user,
            request_type='user_initiated',
            data_types=data_types,
            include_backups=include_backups,
            legal_basis=reason,
            requested_by=request.user
        )
        
        # Log activity
        UserActivity.objects.create(
            user=request.user,
            activity_type='settings_change',
            description=f'Data deletion requested for: {", ".join(data_types)}',
            entity_type='deletion_request',
            entity_id=deletion_request.id
        )
        
        return Response({
            'request_id': str(deletion_request.id),
            'status': deletion_request.status,
            'message': 'Data deletion request submitted successfully. You will be notified when processing is complete.'
        }, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        tags=['Privacy'],
        summary='Get Deletion Requests',
        description='Get user\'s data deletion requests.',
        responses={
            200: {
                'description': 'Deletion requests retrieved'
            }
        }
    )
    def get(self, request):
        """Get user's deletion requests"""
        requests = DataDeletionRequest.objects.filter(user=request.user).order_by('-requested_at')
        
        request_data = []
        for req in requests:
            request_data.append({
                'id': str(req.id),
                'request_type': req.request_type,
                'status': req.status,
                'data_types': req.data_types,
                'requested_at': req.requested_at.isoformat(),
                'completed_at': req.completed_at.isoformat() if req.completed_at else None,
                'error_message': req.error_message
            })
        
        return Response({
            'deletion_requests': request_data
        })


class AdminDataRetentionView(APIView):
    """
    Admin view for managing data retention policies
    """
    permission_classes = [AdminOnlyPermission]
    
    @extend_schema(
        tags=['Privacy Admin'],
        summary='Get Data Retention Policies',
        description='Get all data retention policies (Admin only).',
        responses={
            200: {
                'description': 'Retention policies retrieved'
            }
        }
    )
    def get(self, request):
        """Get all retention policies"""
        policies = DataRetentionPolicy.objects.all()
        
        policy_data = []
        for policy in policies:
            policy_data.append({
                'id': str(policy.id),
                'data_type': policy.data_type,
                'retention_period_days': policy.retention_period_days,
                'auto_delete_enabled': policy.auto_delete_enabled,
                'archive_before_delete': policy.archive_before_delete,
                'legal_basis': policy.legal_basis,
                'created_at': policy.created_at.isoformat()
            })
        
        return Response({
            'policies': policy_data
        })
    
    @extend_schema(
        tags=['Privacy Admin'],
        summary='Create Retention Policy',
        description='Create a new data retention policy (Admin only).',
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'data_type': {'type': 'string'},
                    'retention_period_days': {'type': 'integer'},
                    'auto_delete_enabled': {'type': 'boolean'},
                    'legal_basis': {'type': 'string'}
                },
                'required': ['data_type', 'retention_period_days']
            }
        }
    )
    def post(self, request):
        """Create retention policy"""
        data_type = request.data.get('data_type')
        retention_days = request.data.get('retention_period_days')
        auto_delete = request.data.get('auto_delete_enabled', True)
        legal_basis = request.data.get('legal_basis', '')
        
        if not data_type or not retention_days:
            return Response({
                'error': 'data_type and retention_period_days are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        policy = DataRetentionPolicy.objects.create(
            data_type=data_type,
            retention_period_days=retention_days,
            auto_delete_enabled=auto_delete,
            legal_basis=legal_basis,
            created_by=request.user
        )
        
        return Response({
            'id': str(policy.id),
            'message': f'Retention policy created for {data_type}'
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AdminOnlyPermission])
def process_deletion_request(request, request_id):
    """
    Process a data deletion request (Admin only)
    """
    try:
        deletion_request = DataDeletionRequest.objects.get(id=request_id)
    except DataDeletionRequest.DoesNotExist:
        return Response({
            'error': 'Deletion request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if deletion_request.status != 'pending':
        return Response({
            'error': 'Request is not in pending status'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Start processing
    deletion_request.start_processing(request.user)
    
    # This would trigger background task to actually delete data
    # For now, we'll simulate the process
    deleted_counts = {
        'user_profiles': 0,
        'meeting_transcripts': 0,
        'activity_logs': 0,
        'consent_records': 0
    }
    
    # Simulate deletion process
    for data_type in deletion_request.data_types:
        if data_type == 'meeting_transcripts':
            # Delete encrypted transcript data
            encrypted_data = EncryptedDataField.objects.filter(
                owner=deletion_request.user,
                field_type='transcript'
            )
            count = encrypted_data.count()
            encrypted_data.delete()
            deleted_counts['meeting_transcripts'] = count
        
        elif data_type == 'activity_logs':
            # Delete activity logs
            activities = UserActivity.objects.filter(user=deletion_request.user)
            count = activities.count()
            activities.delete()
            deleted_counts['activity_logs'] = count
    
    # Mark as completed
    deletion_request.mark_completed(deleted_counts)
    
    return Response({
        'message': 'Deletion request processed successfully',
        'deleted_counts': deleted_counts
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def privacy_dashboard(request):
    """
    Privacy dashboard with user's data overview
    """
    user = request.user
    
    # Get consent status
    consents = ConsentRecord.objects.filter(user=user)
    active_consents = [c for c in consents if c.is_active]
    
    # Get privacy settings
    try:
        privacy_settings = PrivacySettings.objects.get(user=user)
    except PrivacySettings.DoesNotExist:
        privacy_settings = None
    
    # Get data retention info
    encrypted_data_count = EncryptedDataField.objects.filter(owner=user).count()
    
    # Get recent activity
    recent_activity_count = UserActivity.objects.filter(
        user=user,
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Get deletion requests
    pending_deletions = DataDeletionRequest.objects.filter(
        user=user,
        status='pending'
    ).count()
    
    return Response({
        'privacy_overview': {
            'active_consents': len(active_consents),
            'total_consents': len(consents),
            'privacy_settings_configured': privacy_settings is not None,
            'encrypted_data_items': encrypted_data_count,
            'recent_activity_count': recent_activity_count,
            'pending_deletion_requests': pending_deletions
        },
        'data_retention': {
            'transcript_retention_days': privacy_settings.transcript_retention_days if privacy_settings else 2555,
            'auto_delete_enabled': privacy_settings.auto_delete_transcripts if privacy_settings else False
        },
        'consent_summary': [
            {
                'type': consent.consent_type,
                'status': consent.status,
                'is_active': consent.is_active
            }
            for consent in consents
        ]
    })