"""
WebSocket routing for debriefings app
"""
from django.urls import path, re_path
from . import consumers

websocket_urlpatterns = [
    # Debriefing conversation WebSocket
    re_path(
        r'ws/debriefing/(?P<session_id>[0-9a-f-]+)/$',
        consumers.DebriefingConsumer.as_asgi()
    ),
    
    # Debriefing notifications WebSocket
    path(
        'ws/debriefing/notifications/',
        consumers.DebriefingNotificationConsumer.as_asgi()
    ),
]