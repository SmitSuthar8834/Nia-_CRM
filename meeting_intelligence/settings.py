"""
Django settings for NIA Meeting Intelligence project.
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'channels',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.meetings',
    'apps.debriefings',
    'apps.leads',
    'apps.calendar_integration',
    'apps.crm_sync',
    'apps.ai_engine',
    'apps.analytics',
    'apps.api_docs',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.UserActivityMiddleware',
    'apps.accounts.middleware.SecurityHeadersMiddleware',
    'apps.accounts.middleware.RateLimitMiddleware',
    'apps.accounts.middleware.SessionSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'meeting_intelligence.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'meeting_intelligence.wsgi.application'
ASGI_APPLICATION = 'meeting_intelligence.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='meeting_intelligence'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# Use SQLite for testing when PostgreSQL is not available
import sys
if 'test' in sys.argv or 'pytest' in sys.modules:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'apps.accounts.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# DRF Spectacular configuration
SPECTACULAR_SETTINGS = {
    'TITLE': 'NIA Meeting Intelligence API',
    'DESCRIPTION': 'Comprehensive API for the NIA (AI Assistant) CRM Meeting Intelligence system. This API provides endpoints for meeting detection, automated debriefing, lead management, CRM synchronization, and analytics.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    'SERVERS': [
        {
            'url': 'http://localhost:8000',
            'description': 'Development server'
        },
        {
            'url': 'https://api.nia-intelligence.com',
            'description': 'Production server'
        }
    ],
    'TAGS': [
        {
            'name': 'Authentication',
            'description': 'User authentication and authorization endpoints'
        },
        {
            'name': 'Meetings',
            'description': 'Meeting detection, management, and intelligence endpoints'
        },
        {
            'name': 'Debriefings',
            'description': 'Automated debriefing session management and conversation endpoints'
        },
        {
            'name': 'Leads',
            'description': 'Lead management and participant matching endpoints'
        },
        {
            'name': 'Calendar Integration',
            'description': 'Calendar system integration and synchronization endpoints'
        },
        {
            'name': 'CRM Sync',
            'description': 'Creatio CRM synchronization and data management endpoints'
        },
        {
            'name': 'AI Engine',
            'description': 'AI-powered conversation and data extraction endpoints'
        },
        {
            'name': 'Analytics',
            'description': 'Performance metrics, reporting, and analytics endpoints'
        }
    ],
    'CONTACT': {
        'name': 'NIA Development Team',
        'email': 'api-support@nia-intelligence.com'
    },
    'LICENSE': {
        'name': 'Proprietary License',
        'url': 'https://nia-intelligence.com/license'
    },
    'EXTERNAL_DOCS': {
        'description': 'Find more info here',
        'url': 'https://docs.nia-intelligence.com'
    },
    'PREPROCESSING_HOOKS': [
        'meeting_intelligence.api_docs.preprocessing_hooks.custom_preprocessing_hook',
    ],
    'POSTPROCESSING_HOOKS': [
        'meeting_intelligence.api_docs.postprocessing_hooks.custom_postprocessing_hook',
    ],
    'ENUM_NAME_OVERRIDES': {
        'ValidationErrorEnum': 'meeting_intelligence.api_docs.enums.ValidationErrorEnum',
    },
    'AUTHENTICATION_WHITELIST': [
        'meeting_intelligence.api_docs.auth.CustomJWTAuthentication',
    ],
}

# CORS settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

CORS_ALLOW_CREDENTIALS = True

# Redis configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

# Celery configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Channels configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
        },
    },
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

# Creatio CRM Integration Settings
CREATIO_API_URL = config('CREATIO_API_URL', default='https://your-creatio-instance.com')
CREATIO_CLIENT_ID = config('CREATIO_CLIENT_ID', default='')
CREATIO_CLIENT_SECRET = config('CREATIO_CLIENT_SECRET', default='')

# Google Gemini AI Configuration
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

# Google Calendar Integration
GOOGLE_CALENDAR_CREDENTIALS_FILE = config(
    'GOOGLE_CALENDAR_CREDENTIALS_FILE', 
    default=str(BASE_DIR / 'credentials' / 'google_calendar_credentials.json')
)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_REDIRECT_URI = config('GOOGLE_REDIRECT_URI', default='http://localhost:8000/api/v1/calendar/callback/google/')

# External API configurations
CREATIO_API_URL = config('CREATIO_API_URL', default='')
CREATIO_CLIENT_ID = config('CREATIO_CLIENT_ID', default='')
CREATIO_CLIENT_SECRET = config('CREATIO_CLIENT_SECRET', default='')

# JWT Authentication settings
JWT_ACCESS_TOKEN_LIFETIME = 24 * 60 * 60  # 24 hours in seconds
JWT_REFRESH_TOKEN_LIFETIME = 7 * 24 * 60 * 60  # 7 days in seconds

# Session settings
SESSION_COOKIE_AGE = 24 * 60 * 60  # 24 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Two-Factor Authentication settings
TOTP_ISSUER_NAME = 'NIA Meeting Intelligence'
TOTP_VALID_WINDOW = 1  # Allow 30 second window for TOTP verification

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Login attempt settings
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_TIMEOUT = 15 * 60  # 15 minutes

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'meeting_intelligence': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}