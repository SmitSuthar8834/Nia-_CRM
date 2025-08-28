from django.urls import path
from . import views

urlpatterns = [
    path('initialize/', views.initialize_ai_session, name='ai-initialize'),
    path('questions/', views.generate_questions, name='ai-questions'),
    path('questions/stream/', views.stream_questions, name='ai-questions-stream'),
    path('analyze/', views.analyze_conversation, name='ai-analyze'),
    path('notes/', views.process_notes, name='ai-notes'),
    path('transcript/process/', views.process_transcript, name='ai-process-transcript'),
    path('transcript/actions/', views.extract_action_items_from_transcript, name='ai-extract-actions'),
    path('summary/', views.generate_summary, name='ai-summary'),
    path('summary/comprehensive/', views.generate_comprehensive_summary, name='ai-comprehensive-summary'),
    path('end-session/', views.end_ai_session, name='ai-end-session'),
]