# config/settings/base.py
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env file
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-dev-key-12345')
DEBUG = env('DEBUG', default=True)
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    # Django built-in apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_spectacular',

    # Celery apps (comment these out if migrate still fails)
    'django_celery_beat',
    'django_celery_results',

    # Our custom apps
    'apps.core',
    'apps.ingestion',
    'apps.predictions',
    'apps.alerts',
    'apps.floods',
    'apps.api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database is defined in development.py and production.py
DATABASES = {}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# Custom user model
AUTH_USER_MODEL = 'core.User'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# GEE
GEE_SERVICE_ACCOUNT_EMAIL = env('GEE_SERVICE_ACCOUNT_EMAIL', default='')
GEE_SERVICE_ACCOUNT_KEY_PATH = env('GEE_SERVICE_ACCOUNT_KEY_PATH', default='')
GEE_PROJECT_ID = env('GEE_PROJECT_ID', default='')

# Twilio
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER = env('TWILIO_FROM_NUMBER', default='')

# SendGrid
SENDGRID_API_KEY = env('SENDGRID_API_KEY', default='')
DEFAULT_FROM_EMAIL = 'alerts@floodwatch-cameroon.com'

# Celery
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'Africa/Douala'

# ML
ML_MODELS_DIR = BASE_DIR / 'ml' / 'models'