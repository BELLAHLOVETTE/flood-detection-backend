# config/settings/production.py
# Settings for the live server (Railway/Render)
# This file is used in deployment

from .base import *
import os

DEBUG = False

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Use real PostgreSQL in production
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Email — use real SendGrid in production
EMAIL_BACKEND = 'sendgrid_backend.SendgridBackend'
SENDGRID_API_KEY = env('SENDGRID_API_KEY')