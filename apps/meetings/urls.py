"""
URL configuration for meetings app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MeetingViewSet, MeetingParticipantViewSet, MeetingNoteViewSet

app_name = 'meetings'

# Create separate routers to avoid any potential conflicts
meeting_router = DefaultRouter()
meeting_router.register(r'', MeetingViewSet, basename='meeting')

participant_router = DefaultRouter()
participant_router.register(r'', MeetingParticipantViewSet, basename='meeting-participant')

note_router = DefaultRouter()
note_router.register(r'', MeetingNoteViewSet, basename='meeting-note')

urlpatterns = [
    # Meeting endpoints at root
    path('', include(meeting_router.urls)),
    # Participant endpoints at /participants/
    path('participants/', include(participant_router.urls)),
    # Note endpoints at /notes/
    path('notes/', include(note_router.urls)),
]