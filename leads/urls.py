from django.urls import path
from . import views

urlpatterns = [
    path('', views.LeadListCreateView.as_view(), name='lead-list-create'),
    path('<int:pk>/', views.LeadDetailView.as_view(), name='lead-detail'),
    path('sync/', views.sync_leads, name='lead-sync'),
    path('match-meeting/', views.match_meeting_to_lead, name='match-meeting-to-lead'),
    path('potential-matches/', views.get_potential_matches, name='get-potential-matches'),
    path('<int:lead_id>/meetings/', views.lead_meetings, name='lead-meetings'),
    path('<int:lead_id>/status/', views.update_lead_status, name='update-lead-status'),
]