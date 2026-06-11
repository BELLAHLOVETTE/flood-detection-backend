# config/settings/production.py
import os
import json
import tempfile
from .base import *

DEBUG = False

# Fallback safely to prevent app crashing if ALLOWED_HOSTS is not fully parsed yet
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

# --- DATABASE SETUP ---
# Look for DATABASE_URL. If completely missing during a dry-run or initial build stage, 
# fall back to an empty dummy configuration instead of crashing the entire setup.
DATABASE_URL = env('DATABASE_URL', default=None)

if DATABASE_URL:
    DATABASES = {
        'default': env.db('DATABASE_URL')
    }
else:
    # Safe temporary fallback configuration to keep the container building
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- STATIC FILES ---
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CORS MANAGEMENT ---
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]
)
CORS_ALLOW_CREDENTIALS = True

# --- SECURITY SYSTEM PANELS ---
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'
SESSION_COOKIE_SECURE       = True
CSRF_COOKIE_SECURE          = True
SECURE_SSL_REDIRECT         = env.bool('SECURE_SSL_REDIRECT', default=False)

# --- SYSTEM COMMUNICATIONS ---
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- GOOGLE EARTH ENGINE (GEE) AUTHENTICATION ---
GEE_SERVICE_ACCOUNT_EMAIL   = env('GEE_SERVICE_ACCOUNT_EMAIL', default='')
GEE_PROJECT_ID              = env('GEE_PROJECT_ID', default='')

_GEE_JSON_CONTENT = env('GEE_SERVICE_ACCOUNT_JSON', default='')
if _GEE_JSON_CONTENT:
    _tmp_file = tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False
    )
    _tmp_file.write(_GEE_JSON_CONTENT)
    _tmp_file.close()
    GEE_SERVICE_ACCOUNT_KEY_PATH = _tmp_file.name
else:
    GEE_SERVICE_ACCOUNT_KEY_PATH = env(
        'GEE_SERVICE_ACCOUNT_KEY_PATH',
        default=str(BASE_DIR / 'gee-service-account.json')
    )