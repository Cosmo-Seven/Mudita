from pathlib import Path
import environ
import os
from django.contrib import messages

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

DOMAIN = env("DOMAIN", default="")
SECRET_KEY = env("SECRET_KEY")
DEBUG = True
MAINTENANCE_MODE = True

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

HYPER = env("HYPER")

SITE_ID = 1
DASHBOARD_LOGIN_URL = env("DASHBOARD_LOGIN_URL")
DASHBOARD_LOGOUT_URL = env("DASHBOARD_LOGOUT_URL")
ADMIN_LOGIN_URL = env("ADMIN_LOGIN_URL")
LOGIN_URL = env("LOGIN_URL")
PROJECT_NAME = env("PROJECT_NAME", default="")

AUTH_USER_MODEL = "core.UserModel"

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django.contrib.humanize",

    # app
    'pwa',
    'core',
    "django.contrib.sites",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mudita.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "utils.site.site",
                "utils.routes.routes",
                "utils.languages.languages",
                "utils.sidebar.sidebar",
            ],
        },
    },
]

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}
WSGI_APPLICATION = f"{PROJECT_NAME}.wsgi.application"
ASGI_APPLICATION = f"{PROJECT_NAME}.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE"),
        "NAME": (
            BASE_DIR / env("DB_NAME")
            if env("DB_ENGINE") == "django.db.backends.sqlite3"
            else env("DB_NAME")
        ),
        "USER": env("DB_USER", default=""),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST", default=""),
        "PORT": env("DB_PORT", default=""),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("LANGUAGE_CODE", default="en-us")
TIME_ZONE = env("TIME_ZONE", default="Asia/Yangon")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]


MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "error",
}

EMAIL_BACKEND = env("EMAIL_BACKEND")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


PWA_APP_NAME = "Mudita"
PWA_APP_DESCRIPTION = "HR management for Mudita"
PWA_APP_THEME_COLOR = "#fa7b20"
PWA_APP_BACKGROUND_COLOR = "#ffffff"
PWA_APP_DISPLAY = "standalone"
PWA_APP_SCOPE = "/"
PWA_APP_START_URL = "/"
PWA_APP_ORIENTATION = "portrait"
PWA_APP_STATUS_BAR_COLOR = "default"
PWA_SERVICE_WORKER_PATH = BASE_DIR / "templates" / "pwa" / "serviceworker.js"
PWA_APP_DIR = "ltr"
PWA_APP_LANG = "en-US"
PWA_APP_ICONS = [
    {
        "src": "/static/dashboard/images/logo.png",
        "sizes": "192x192",
    },
    {
        "src": "/static/dashboard/images/logo.png",
        "sizes": "512x512",
    },
]

LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
    }
}

