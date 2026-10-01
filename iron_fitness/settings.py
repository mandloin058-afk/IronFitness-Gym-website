"""Django settings for the Iron Fitness Gym backend."""

import os
from pathlib import Path

from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name, default=""):
    return [
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    ]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    "localhost,127.0.0.1",
)

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS"
)

# Vercel sets the VERCEL environment variable automatically.
if os.getenv("VERCEL"):
    ALLOWED_HOSTS += [".vercel.app"]
    CSRF_TRUSTED_ORIGINS += ["https://*.vercel.app"]


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "gym",
]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

ROOT_URLCONF = "iron_fitness.urls"

WSGI_APPLICATION = "iron_fitness.wsgi.application"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

FRONTEND_DIR = BASE_DIR / "frontend"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
            FRONTEND_DIR,
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# DB_ENGINE=sqlite (default) -> local db.sqlite3 file (laptop only)
# DB_ENGINE=mysql            -> MySQL (local MySQL or a hosted one such as
#                               TiDB Cloud / Aiven). Uses PyMySQL, see
#                               iron_fitness/__init__.py.

if os.getenv("DB_ENGINE", "sqlite").strip().lower() == "mysql":

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "iron_fitness"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "charset": "utf8mb4",
            },
        }
    }

    # Hosted MySQL services (TiDB Cloud, Aiven, ...) require SSL.
    # Set DB_SSL=True in their environment variables.
    if env_bool("DB_SSL", False):
        import certifi

        DATABASES["default"]["OPTIONS"]["ssl"] = {
            "ca": os.getenv("DB_SSL_CA", certifi.where()),
        }

else:

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        )
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        )
    },
]

LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "dashboard"

LOGOUT_REDIRECT_URL = "home"


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"

# IMPORTANT:
# This tells Django to look inside the project's static folder
# during development.

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Used by collectstatic for production.

STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise serves the CSS/JS in production (DEBUG=False). USE_FINDERS lets
# it read straight from the "static" folder, so collectstatic is not needed.
WHITENOISE_USE_FINDERS = True


# ---------------------------------------------------------------------------
# Media files
# ---------------------------------------------------------------------------

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Default primary key
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

MESSAGE_TAGS = {
    message_constants.ERROR: "danger",
}


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "no-reply@ironfitness.com",
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "localhost",
)

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        "25",
    )
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    "",
)

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    "",
)

EMAIL_USE_TLS = env_bool(
    "EMAIL_USE_TLS",
    False,
)


# ---------------------------------------------------------------------------
# Gym business rules
# ---------------------------------------------------------------------------

GYM_NOTIFY_EMAIL = os.getenv(
    "GYM_NOTIFY_EMAIL",
    "",
)

BOOKING_WINDOW_DAYS = int(
    os.getenv(
        "BOOKING_WINDOW_DAYS",
        "14",
    )
)

REQUIRE_ACTIVE_MEMBERSHIP_FOR_BOOKING = env_bool(
    "REQUIRE_ACTIVE_MEMBERSHIP_FOR_BOOKING",
    True,
)


# ---------------------------------------------------------------------------
# Production hardening
# ---------------------------------------------------------------------------

if not DEBUG:

    SESSION_COOKIE_SECURE = env_bool(
        "DJANGO_SECURE_COOKIES",
        True,
    )

    CSRF_COOKIE_SECURE = env_bool(
        "DJANGO_SECURE_COOKIES",
        True,
    )