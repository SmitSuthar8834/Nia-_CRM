from rest_framework import serializers
from .models import Lead


class LeadSerializer(serializers.ModelSerializer):
    """
    Serializer for Lead model with validation
    """
    
    class Meta:
        model = Lead
        fields = [
            'id', 'crm_id', 'name', 'email', 'company', 
            'phone', 'status', 'source', 'created_at', 
            'updated_at', 'last_sync'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_name(self, value):
        """Validate name field"""
        if not value.strip():
            raise serializers.ValidationError("Name cannot be empty")
        return value.strip()
    
    def validate_company(self, value):
        """Validate company field"""
        if not value.strip():
            raise serializers.ValidationError("Company cannot be empty")
        return value.strip()
    
    def validate_phone(self, value):
        """Validate phone field"""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 characters")
        return value.strip() if value else value


class LeadSyncSerializer(serializers.Serializer):
    """
    Serializer for bulk lead sync operations from n8n
    """
    leads = serializers.ListField(child=serializers.DictField())
    
    def create(self, validated_data):
        """Create or update leads in bulk"""
        leads_data = validated_data['leads']
        created_leads = []
        updated_leads = []
        errors = []
        
        for lead_data in leads_data:
            try:
                # Validate individual lead data
                lead_serializer = LeadSerializer(data=lead_data)
                if lead_serializer.is_valid():
                    # Use update_or_create to handle existing leads
                    lead, created = Lead.objects.update_or_create(
                        crm_id=lead_data['crm_id'],
                        defaults=lead_serializer.validated_data
                    )
                    if created:
                        created_leads.append(lead)
                    else:
                        updated_leads.append(lead)
                else:
                    # Try to update existing lead if validation fails due to uniqueness
                    try:
                        existing_lead = Lead.objects.get(crm_id=lead_data['crm_id'])
                        # Update existing lead with new data
                        for field, value in lead_data.items():
                            if field != 'crm_id':  # Don't update the unique identifier
                                setattr(existing_lead, field, value)
                        existing_lead.save()
                        updated_leads.append(existing_lead)
                    except Lead.DoesNotExist:
                        errors.append({
                            'crm_id': lead_data.get('crm_id'),
                            'errors': lead_serializer.errors
                        })
            except Exception as e:
                errors.append({
                    'crm_id': lead_data.get('crm_id'),
                    'error': str(e)
                })
        
        result = {
            'created': created_leads,
            'updated': updated_leads,
            'total_processed': len(leads_data),
            'errors': errors
        }
        
        return result