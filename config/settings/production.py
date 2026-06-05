# config/settings/production.py
from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security
SECURE_BROWSER_XSS_FILTER    = True
SECURE_CONTENT_TYPE_NOSNIFF  = True
X_FRAME_OPTIONS              = 'DENY'
SECURE_SSL_REDIRECT          = env.bool('SECURE_SSL_REDIRECT', default=False)
SESSION_COOKIE_SECURE        = True
CSRF_COOKIE_SECURE           = True

# Email
EMAIL_BACKEND    = 'django.core.mail.backends.console.EmailBackend'
SENDGRID_API_KEY = env('SENDGRID_API_KEY', default='')

# CORS — allow your Vercel frontend domain
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:3000']
)
CORS_ALLOW_CREDENTIALS = True