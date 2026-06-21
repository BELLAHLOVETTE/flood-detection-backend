# config/settings/production.py
import os
import json
import tempfile
from .base import *
import sys

_database_url = env('DATABASE_URL', default='')

print(f"DEBUG: DATABASE_URL raw value starts with: {_database_url[:15]}...", file=sys.stderr)

if not _database_url:
    print(
        "FATAL: DATABASE_URL environment variable is not set! "
        "The application cannot start without a database connection.",
        file=sys.stderr
    )
    sys.exit(1)

if not _database_url.startswith('postgres'):
    print(
        f"FATAL: DATABASE_URL does not point to PostgreSQL! "
        f"Got: {_database_url[:20]}... — refusing to start with SQLite in production.",
        file=sys.stderr
    )
    sys.exit(1)

DATABASES = {
    'default': env.db('DATABASE_URL')
}

print(f"Database engine confirmed: {DATABASES['default']['ENGINE']}", file=sys.stderr)

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

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://githubrepobackend-production.up.railway.app',
        'https://*.railway.app',
    ]
)

# ── GOOGLE EARTH ENGINE — DEFENSIVE LOADING ──────────────────────────────────
GEE_SERVICE_ACCOUNT_EMAIL = env('GEE_SERVICE_ACCOUNT_EMAIL', default='')
GEE_PROJECT_ID            = env('GEE_PROJECT_ID', default='')
GEE_SERVICE_ACCOUNT_KEY_PATH = env(
    'GEE_SERVICE_ACCOUNT_KEY_PATH',
    default=str(BASE_DIR / 'gee-service-account.json')
)

_GEE_JSON_CONTENT = env('GEE_SERVICE_ACCOUNT_JSON', default='')
if _GEE_JSON_CONTENT:
    try:
        import json as _json
        import tempfile as _tempfile

        # Validate it is actually valid JSON before writing it anywhere
        _json.loads(_GEE_JSON_CONTENT)

        _tmp_file = _tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        _tmp_file.write(_GEE_JSON_CONTENT)
        _tmp_file.close()
        GEE_SERVICE_ACCOUNT_KEY_PATH = _tmp_file.name
    except Exception as _gee_err:
        # NEVER let this crash the entire Django app at import time.
        # Just log it and fall back to the default file path.
        import sys
        print(
            f"WARNING: GEE_SERVICE_ACCOUNT_JSON could not be parsed: {_gee_err}",
            file=sys.stderr
        )