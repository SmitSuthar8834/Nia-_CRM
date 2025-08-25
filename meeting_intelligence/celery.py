"""
Celery configuration for NIA Meeting Intelligence project.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meeting_intelligence.settings')

app = Celery('meeting_intelligence')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure task routes
app.conf.task_routes = {
    'apps.meetings.tasks.*': {'queue': 'meetings'},
    'apps.debriefings.tasks.*': {'queue': 'debriefings'},
    'apps.calendar_integration.tasks.*': {'queue': 'calendar'},
    'apps.crm_sync.tasks.*': {'queue': 'crm_sync'},
    'apps.ai_engine.tasks.*': {'queue': 'ai_processing'},
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')