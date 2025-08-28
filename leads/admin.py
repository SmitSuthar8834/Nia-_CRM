from django.contrib import admin
from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'company', 'status', 'created_at', 'last_sync']
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['name', 'email', 'company', 'crm_id']
    readonly_fields = ['created_at', 'updated_at', 'last_sync']
    ordering = ['-created_at']