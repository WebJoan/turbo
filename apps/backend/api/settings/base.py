#import os
from os import environ
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

######################################################################
# General
######################################################################
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = environ.get("SECRET_KEY", get_random_secret_key())

DEBUG = environ.get("DEBUG", "") == "1"

ALLOWED_HOSTS = [h.strip() for h in environ.get("ALLOWED_HOSTS", "localhost,api").split(",") if h.strip()]

WSGI_APPLICATION = "api.wsgi.application"
ASGI_APPLICATION = "api.asgi.application"

ROOT_URLCONF = "api.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

######################################################################
# Apps
######################################################################
INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 3rd party
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_celery_beat",
    "dj_rest_auth",
    "django_filters",
    # apps
    "api",
    "goods",
    "core",
    "customers",
    "persons",
    "sales",
    "rfqs",
    "db",
    "stock",
]

######################################################################
# Middleware
######################################################################
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

######################################################################
# Templates
######################################################################
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

######################################################################
# Database
######################################################################
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": environ.get("DATABASE_USER", "postgres"),
        "PASSWORD": environ.get("DATABASE_PASSWORD", "change-password"),
        "NAME": environ.get("DATABASE_NAME", "db"),
        "HOST": environ.get("DATABASE_HOST", "db"),
        "PORT": "5432",
        "TEST": {
            "NAME": "test",
        },
    }
}

######################################################################
# Authentication
######################################################################
AUTH_USER_MODEL = "api.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


######################################################################
# Internationalization
######################################################################
LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True

######################################################################
# Staticfiles
######################################################################
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise settings для оптимальной производительности
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Максимальный возраст кэша для статических файлов (1 год)
WHITENOISE_MAX_AGE = 31536000  # 1 год в секундах

# Дополнительные MIME типы для сжатия
WHITENOISE_USE_FINDERS = True  # Полезно для разработки
WHITENOISE_AUTOREFRESH = True  # Автообновление в DEBUG режиме

######################################################################
# Media
######################################################################
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
######################################################################
# Rest Framework
######################################################################
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "user": "120/min",
    },
}

SPECTACULAR_SETTINGS = {
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

######################################################################
# CORS
######################################################################
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://ai-frontend:3000",
    "http://api:8000",
    "http://langgraph-api:8080",
    "https://web4app.ru",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_ALL_ORIGINS = environ.get("CORS_ALLOW_ALL_ORIGINS", "0") == "1"

CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

######################################################################
# JWT Configuration
######################################################################
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=60),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

######################################################################
# dj-rest-auth Configuration
######################################################################
REST_AUTH = {
    'USE_JWT': True,
    'JWT_AUTH_COOKIE': 'access_token',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh_token',
    'JWT_AUTH_HTTPONLY': True,
    # Безопасные cookie; для dev можно переопределить через переменные окружения
    'JWT_AUTH_SECURE': False if DEBUG else True,
    'JWT_AUTH_SAMESITE': 'Lax' if DEBUG else 'None',
    # Отключаем TokenModel, т.к. используем только JWT
    'TOKEN_MODEL': None,
    'SESSION_LOGIN': False,
    'USER_DETAILS_SERIALIZER': 'api.serializers.UserDetailsSerializer'
}

# CSRF / Cookies security
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://ai-frontend:3000",
    "http://api:8000",
    "http://langgraph-api:8080",
    "https://web4app.ru",
]
SESSION_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SECURE = False if DEBUG else True

######################################################################
# Unfold
######################################################################
UNFOLD = {
    "SITE_HEADER": _("RUELIQ Admin"),
    "SITE_TITLE": _("RUELIQ Admin"),
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": _("Navigation"),
                "separator": False,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "person",
                        "link": reverse_lazy("admin:api_user_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "label",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
}


# RabbitMQ connection settings
RABBITMQ_HOST = environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = environ.get("RABBITMQ_PORT", "5672")
RABBITMQ_USER = environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = environ.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = environ.get("RABBITMQ_VHOST", "/")
AMQP_URL = environ.get("AMQP_URL")

# Celery Configuration
if AMQP_URL:
    CELERY_BROKER_URL = AMQP_URL
else:
    CELERY_BROKER_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["application/json"]


CELERY_IMPORTS = (
    # scheduled tasks
    #"plane.bgtasks.issue_automation_task",
    #"plane.bgtasks.exporter_expired_task",
    #"plane.bgtasks.file_asset_task",
    #"plane.bgtasks.email_notification_task",
    #"plane.bgtasks.api_logs_task",
    #"plane.license.bgtasks.tracer",
    # management tasks
    #"plane.bgtasks.dummy_data_task",
    # issue version tasks
    #"plane.bgtasks.issue_version_sync",
    #"plane.bgtasks.issue_description_version_sync",
)

# Redis Config
REDIS_URL = environ.get("REDIS_URL", "redis://redis:6379/0")
REDIS_SSL = REDIS_URL and "rediss" in REDIS_URL

if REDIS_SSL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }


######################################################################
# MeiliSearch
######################################################################
MEILISEARCH_HOST = environ.get("MEILISEARCH_HOST", "http://meilisearch:7700")
MEILISEARCH_API_KEY = environ.get("MEILISEARCH_API_KEY", "meilisearch")
#MEILISEARCH_INDEX_NAME = environ.get("MEILISEARCH_INDEX_NAME", "products")