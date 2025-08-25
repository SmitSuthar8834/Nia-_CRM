"""
URL Configuration for Lead Management and Participant Matching
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'leads'

# Create router for ViewSets
router = DefaultRouter()
router.register(r'leads', views.LeadViewSet)
router.register(r'matching', views.ParticipantMatchingViewSet, basename='matching')
# router.register(r'verification', views.VerificationViewSet)
router.register(r'action-items', views.ActionItemViewSet)
router.register(r'competitive-intelligence', views.CompetitiveIntelligenceViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Additional custom endpoints can be added here
]