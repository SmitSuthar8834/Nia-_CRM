"""
WSGI config for NIA Meeting Intelligence project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meeting_intelligence.settings')

application = get_wsgi_application()