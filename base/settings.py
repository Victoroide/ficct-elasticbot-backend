import os
import sys
from pathlib import Path
import environ
import dj_database_url

env = environ.Env(
    DEBUG=(bool, False)
)

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-this-in-production')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Add apps directory to Python path for imports
sys.path.insert(0, str(BASE_DIR / 'apps'))

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'drf_spectacular',
    'corsheaders',
    'django_celery_beat',
    
    # Local apps (using apps/ structure) - ALL 5 APPS
    'apps.market_data',
    'apps.elasticity',
    'apps.ai_interpretation',
    'apps.simulator',
    'apps.reports',
    
    # Utilities
    'utils',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'base.urls'

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

WSGI_APPLICATION = 'base.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration (Anonymous API - No Authentication)
REST_FRAMEWORK = {
    # No authentication - anonymous access only for academic project
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    # IP-based rate limiting (can be disabled via RATE_LIMITING_ENABLED=False)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ] if env.bool('RATE_LIMITING_ENABLED', default=True) else [],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',  # General endpoints
    },
    'EXCEPTION_HANDLER': 'utils.exceptions.custom_exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:5173', 'http://127.0.0.1:5173']
)
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'  # Use UTC for consistent task scheduling
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_RESULT_EXTENDED = True

# Task reliability settings - prevent zombie tasks
CELERY_TASK_ACKS_LATE = True  # Acknowledge task after completion, not before
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Re-queue task if worker crashes
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Don't prefetch tasks aggressively

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ==============================================================================
# ELASTICITY CALCULATION MODE
# ==============================================================================
# When True: Use Celery async tasks (requires Redis to be running)
# When False: Execute calculations synchronously in the request (no Redis needed)
#
# Set to False if:
# - Redis is not available or unstable
# - You want guaranteed calculation completion (at cost of request latency)
# - Development/testing without Redis
#
# Trade-offs:
# - Async (True): Non-blocking requests, but fails silently if Redis is down
# - Sync (False): Blocking requests (5-15s), but always works
# ==============================================================================
ELASTICITY_ASYNC_ENABLED = env.bool('ELASTICITY_ASYNC_ENABLED', default=False)

# ==============================================================================
# CACHE CONFIGURATION
# ==============================================================================
# Default: LocMemCache (no Redis needed)
# Set REDIS_CACHE_ENABLED=True to use Redis (requires Redis server running)
#
# LocMemCache is sufficient for:
# - Single-process deployments
# - Development and testing
# - When Redis is unavailable
#
# Use Redis when:
# - Multiple workers need to share cache
# - Cache persistence across restarts is needed
# ==============================================================================
REDIS_CACHE_ENABLED = env.bool('REDIS_CACHE_ENABLED', default=False)

if REDIS_CACHE_ENABLED:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
            'KEY_PREFIX': 'elasticbot',
            'TIMEOUT': env.int('CACHE_TTL_SECONDS', default=900),
        }
    }
else:
    # In-memory cache - works without Redis
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'elasticbot-cache',
        }
    }

# AWS Configuration
AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = env('AWS_S3_BUCKET_NAME', default='ficct-elasticbot-bucket')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', default='us-east-1')
AWS_BEDROCK_REGION = env('AWS_BEDROCK_REGION', default='us-east-1')
AWS_SES_REGION_NAME = env('AWS_SES_REGION_NAME', default='us-east-1')
USE_S3 = env.bool('USE_S3', default=False)
USE_SES = env.bool('USE_SES', default=False)

if USE_S3:
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_FILE_OVERWRITE = False

if USE_SES:
    EMAIL_BACKEND = 'django_ses.SESBackend'
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='dev@ficct.com')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Application-specific Configuration
BINANCE_P2P_API_URL = env('BINANCE_P2P_API_URL')
BINANCE_API_TIMEOUT = env.int('BINANCE_API_TIMEOUT', default=10)
BINANCE_MAX_RETRIES = env.int('BINANCE_MAX_RETRIES', default=3)

# External OHLC API (usage-based pricing - call sparingly!)
# Set to None/empty to disable the import command
EXTERNAL_OHLC_API_URL = env('EXTERNAL_OHLC_API_URL', default=None)

ELASTICITY_CALCULATION_TIMEOUT = env.int('ELASTICITY_CALCULATION_TIMEOUT', default=300)
MAX_DATA_RETENTION_DAYS = env.int('MAX_DATA_RETENTION_DAYS', default=90)

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s'
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'elasticbot.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'elasticity': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'market_data': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'ai_interpretation': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# drf-spectacular Configuration (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'ElasticBot API',
    'DESCRIPTION': '''## USDT/BOB Price Elasticity Analysis System

### About
ElasticBot calculates price elasticity of demand for USDT/BOB in the Bolivian P2P market using real-time data from Binance.

### Authentication
**No authentication required** - This is an anonymous API for academic purposes.

### Rate Limiting
All endpoints are rate-limited by IP address:
- Market Data: 100 requests/hour
- Elasticity Calculations: 10 requests/hour
- AI Interpretations: 5 requests/hour
- Reports: 10 requests/hour
''',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'LICENSE': {
        'name': 'Academic Use Only',
    },
    'TAGS': [
        {'name': 'Market Data', 'description': 'Real-time and historical USDT/BOB market snapshots from Binance P2P'},
        {'name': 'Elasticity Analysis', 'description': 'Core elasticity calculation engine using midpoint and regression methods'},
        {'name': 'AI Interpretation', 'description': 'AWS Bedrock-powered economic analysis and interpretation'},
        {'name': 'Scenario Simulator', 'description': 'Hypothetical elasticity modeling for what-if analysis'},
        {'name': 'Report Generation', 'description': 'PDF report generation and download'},
    ],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
}
