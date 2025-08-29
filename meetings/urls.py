from django.urls import path
from . import views

urlpatterns = [
    path('', views.MeetingListCreateView.as_view(), name='meeting-list-create'),
    path('<int:pk>/', views.MeetingDetailView.as_view(), name='meeting-detail'),
    path('match-lead/', views.match_lead_to_meeting, name='match-lead-to-meeting'),
    path('<int:meeting_id>/session/', views.meeting_session_detail, name='meeting-session-detail'),
    path('<int:meeting_id>/start/', views.start_meeting_session, name='start-meeting-session'),
    path('<int:meeting_id>/end/', views.end_meeting_session, name='end-meeting-session'),
    
    # Session management endpoints
    path('sessions/<int:session_id>/state/', views.get_session_state, name='get-session-state'),
    path('sessions/<int:session_id>/notes/', views.update_session_notes, name='update-session-notes'),
    path('sessions/<int:session_id>/transcript/', views.update_session_transcript, name='update-session-transcript'),
    path('sessions/<int:session_id>/action-items/', views.add_action_item, name='add-action-item'),
    path('sessions/<int:session_id>/save/', views.force_save_session, name='force-save-session'),
    
    # CRM synchronization endpoints
    path('<int:meeting_id>/sync-crm/', views.sync_meeting_to_crm, name='sync-meeting-to-crm'),
    path('<int:meeting_id>/create-tasks/', views.create_follow_up_tasks, name='create-follow-up-tasks'),
    path('<int:meeting_id>/sync-status/', views.get_crm_sync_status, name='get-crm-sync-status'),
    path('<int:meeting_id>/retry-sync/', views.retry_crm_sync, name='retry-crm-sync'),
    
    # Follow-up task scheduling endpoints
    path('<int:meeting_id>/schedule-tasks/', views.schedule_follow_up_tasks, name='schedule-follow-up-tasks'),
    path('<int:meeting_id>/scheduling-status/', views.get_scheduling_status, name='get-scheduling-status'),
    path('action-items/<int:action_item_id>/cancel-reminders/', views.cancel_reminders, name='cancel-reminders'),
    path('action-items/<int:action_item_id>/reschedule/', views.reschedule_task, name='reschedule-task'),
    
    # Sync tracking endpoints
    path('<int:meeting_id>/comprehensive-sync-status/', views.get_comprehensive_sync_status, name='get-comprehensive-sync-status'),
    path('failed-operations/', views.get_failed_operations, name='get-failed-operations'),
    path('operations/<str:tracking_id>/retry/', views.retry_failed_operation, name='retry-failed-operation'),
    path('sync-report/', views.generate_sync_report, name='generate-sync-report'),
    path('sync-health/', views.get_sync_health_metrics, name='get-sync-health-metrics'),
    
    # AI Summary Generation endpoints
    path('bot-sessions/<int:bot_session_id>/generate-summary/', views.generate_draft_summary, name='generate-draft-summary'),
    path('bot-sessions/<int:bot_session_id>/summary/', views.get_draft_summary, name='get-draft-summary'),
    path('summaries/<int:summary_id>/', views.update_draft_summary, name='update-draft-summary'),
    path('summaries/<int:summary_id>/confidence/', views.update_summary_confidence, name='update-summary-confidence'),
    path('summaries/<int:summary_id>/format-crm/', views.format_summary_for_crm, name='format-summary-for-crm'),
    path('summaries/<int:summary_id>/export/', views.export_summary, name='export-summary'),
    path('summaries/<int:summary_id>/metrics/', views.get_meeting_metrics, name='get-meeting-metrics'),
    
    # Call Bot Session endpoints
    path('bot-sessions/<int:session_id>/', views.get_bot_session, name='get-bot-session'),
    path('bot-sessions/<int:session_id>/update/', views.update_bot_session, name='update-bot-session'),
    path('bot-sessions/<int:session_id>/transcript/', views.update_bot_transcript, name='update-bot-transcript'),
    path('bot-sessions/<int:session_id>/speakers/', views.update_speaker_mapping, name='update-speaker-mapping'),
    
    # Batch Processing endpoints
    path('batch/generate-summaries/', views.batch_generate_summaries, name='batch-generate-summaries'),
    
    # CRM Suggestion endpoints
    path('summaries/<int:summary_id>/crm-suggestions/', views.generate_crm_suggestions, name='generate-crm-suggestions'),
    path('crm/validate-field/', views.validate_crm_field_mapping, name='validate-crm-field-mapping'),
    path('crm/<str:crm_system>/field-mappings/', views.get_crm_field_mappings, name='get-crm-field-mappings'),
    path('summaries/<int:summary_id>/crm-preview/', views.preview_crm_update, name='preview-crm-update'),
    
    # Validation Session endpoints
    path('validation-sessions/', views.create_validation_session, name='create-validation-session'),
    path('validation-sessions/list/', views.list_validation_sessions, name='list-validation-sessions'),
    path('validation-sessions/<int:session_id>/', views.get_validation_session, name='get-validation-session'),
    path('validation-sessions/<int:session_id>/update/', views.update_validation_session, name='update-validation-session'),
    path('validation-sessions/<int:session_id>/questions/', views.get_validation_questions, name='get-validation-questions'),
    path('validation-sessions/<int:session_id>/responses/', views.get_validation_responses, name='get-validation-responses'),
    path('validation-sessions/<int:session_id>/submit-response/', views.submit_validation_response, name='submit-validation-response'),
    path('validation-sessions/<int:session_id>/complete/', views.complete_validation_session, name='complete-validation-session'),
    path('validation-sessions/<int:session_id>/status/', views.validation_session_status, name='validation-session-status'),
    path('validation-sessions/expire-old/', views.expire_old_validation_sessions, name='expire-old-validation-sessions'),
    
    # CRM Approval Workflow endpoints
    path('validation-sessions/<int:session_id>/approve-crm/', views.approve_crm_updates, name='approve-crm-updates'),
    path('validation-sessions/<int:session_id>/reject-crm/', views.reject_crm_updates, name='reject-crm-updates'),
    path('validation-sessions/<int:session_id>/crm-sync-status/', views.get_crm_sync_status, name='get-crm-sync-status'),
    path('validation-sessions/<int:session_id>/approval-summary/', views.get_approval_summary, name='get-approval-summary'),
    path('crm-sync-records/<int:sync_record_id>/retry/', views.retry_failed_crm_sync, name='retry-failed-crm-sync'),
    path('crm-sync-records/<int:sync_record_id>/update-status/', views.update_crm_sync_status, name='update-crm-sync-status'),
    
    # Enhanced CRM data sync endpoints
    path('validation-sessions/<int:validation_session_id>/update-opportunity/', views.update_opportunity_from_meeting, name='update-opportunity-from-meeting'),
    path('validation-sessions/<int:validation_session_id>/opportunity-suggestions/', views.get_opportunity_sync_suggestions, name='get-opportunity-sync-suggestions'),
    path('validation-sessions/<int:validation_session_id>/bulk-sync/', views.bulk_sync_validation_session, name='bulk-sync-validation-session'),
    path('opportunities/<str:opportunity_id>/details/', views.get_opportunity_details, name='get-opportunity-details'),
    
    # Email Management endpoints
    path('draft-emails/', views.create_draft_email, name='create-draft-email'),
    path('draft-emails/list/', views.list_draft_emails, name='list-draft-emails'),
    path('draft-emails/<int:email_id>/', views.get_draft_email, name='get-draft-email'),
    path('draft-emails/<int:email_id>/update/', views.update_draft_email, name='update-draft-email'),
    path('draft-emails/<int:email_id>/delete/', views.delete_draft_email, name='delete-draft-email'),
    
    # Email Approval endpoints
    path('email-approvals/request/', views.request_email_approval, name='request-email-approval'),
    path('email-approvals/respond/', views.respond_to_email_approval, name='respond-to-email-approval'),
    path('email-approvals/list/', views.list_email_approvals, name='list-email-approvals'),
    
    # Scheduled Email endpoints
    path('scheduled-emails/', views.schedule_email, name='schedule-email'),
    path('scheduled-emails/list/', views.list_scheduled_emails, name='list-scheduled-emails'),
    path('scheduled-emails/<int:email_id>/cancel/', views.cancel_scheduled_email, name='cancel-scheduled-email'),
    path('scheduled-emails/<int:email_id>/send/', views.send_email_immediately, name='send-email-immediately'),
]