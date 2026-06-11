# config/settings/production.py
from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['*']
)

# Database — Railway provides DATABASE_URL
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# CORS — update after Vercel deploy
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]
)
CORS_ALLOW_CREDENTIALS = True

# Security
SECURE_BROWSER_XSS_FILTER   = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS             = 'DENY'
SESSION_COOKIE_SECURE       = True
CSRF_COOKIE_SECURE          = True
SECURE_SSL_REDIRECT         = env.bool('SECURE_SSL_REDIRECT', default=False)

# Email
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# GEE credentials from environment variable
GEE_SERVICE_ACCOUNT_EMAIL   = env('GEE_SERVICE_ACCOUNT_EMAIL', default='')
GEE_PROJECT_ID              = env('GEE_PROJECT_ID', default='')

# Handle GEE JSON key stored as environment variable
_GEE_JSON_CONTENT = env('GEE_SERVICE_ACCOUNT_JSON', default='')
if _GEE_JSON_CONTENT:
    import json
    import tempfile
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