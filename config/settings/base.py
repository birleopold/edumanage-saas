from pathlib import Path

from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="unsafe-dev-key")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="*", cast=lambda v: [s.strip() for s in v.split(",") if s.strip()])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "widget_tweaks",
    "apps.tenant.analytics",
]


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


ROOT_URLCONF = "config.urls"
PUBLIC_SCHEMA_URLCONF = "config.public_urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.tenant.orgsettings.context_processors.orgsettings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Public marketing / trust pages (no auth required; no secrets exposed).
PUBLIC_STATUS_PAGE_ENABLED = config("PUBLIC_STATUS_PAGE_ENABLED", default=True, cast=bool)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "edumanage-default-locmem",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = config("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin_home"

# Shown in portal footers; optional support email for non-technical users contacting help.
SUPPORT_CONTACT_EMAIL = config("SUPPORT_CONTACT_EMAIL", default="")

AUTHENTICATION_BACKENDS = [
    "apps.tenant.users.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

# Fee reminder delivery channel: SMS or WHATSAPP.
FEE_REMINDER_CHANNEL = config("FEE_REMINDER_CHANNEL", default="SMS")

# Optional dotted path to callable(phone: str, message: str[, channel: str]) -> bool.
# Preferred setting: FEE_REMINDER_HANDLER; legacy FEE_REMINDER_SMS_HANDLER remains supported.
# If unset, reminders are logged only.
# Examples:
#   "apps.tenant.finance.sms_defaults.log_fee_reminder_to_logger"
#   "apps.tenant.finance.whatsapp_defaults.send_fee_reminder_whatsapp_cloud_api"
FEE_REMINDER_HANDLER = config("FEE_REMINDER_HANDLER", default=None)
FEE_REMINDER_SMS_HANDLER = config("FEE_REMINDER_SMS_HANDLER", default=None)

# Default country code used for WhatsApp phone normalization (e.g. 256 for Uganda).
FEE_REMINDER_DEFAULT_COUNTRY_CODE = config("FEE_REMINDER_DEFAULT_COUNTRY_CODE", default="256")

# Optional absolute base URL used to include a parent invoice link in reminder text.
# Example: "https://school.example.com"
FEE_REMINDER_PORTAL_BASE_URL = config("FEE_REMINDER_PORTAL_BASE_URL", default="")

# WhatsApp Cloud API settings (used by whatsapp_defaults.send_fee_reminder_whatsapp_cloud_api).
WHATSAPP_CLOUD_ACCESS_TOKEN = config("WHATSAPP_CLOUD_ACCESS_TOKEN", default="")
WHATSAPP_CLOUD_PHONE_NUMBER_ID = config("WHATSAPP_CLOUD_PHONE_NUMBER_ID", default="")
WHATSAPP_CLOUD_API_VERSION = config("WHATSAPP_CLOUD_API_VERSION", default="v20.0")
WHATSAPP_CLOUD_TIMEOUT_SECONDS = config("WHATSAPP_CLOUD_TIMEOUT_SECONDS", default=15, cast=int)

# When True, payment receipt message is sent automatically after recording a payment in admin.
FEE_RECEIPT_AUTO_SEND_ON_PAYMENT = config("FEE_RECEIPT_AUTO_SEND_ON_PAYMENT", default=False, cast=bool)

# Webhook delivery timeout (seconds) for outbound integration events.
WEBHOOK_REQUEST_TIMEOUT_SECONDS = config("WEBHOOK_REQUEST_TIMEOUT_SECONDS", default=8, cast=int)
WEBHOOK_MAX_RETRY_ATTEMPTS = config("WEBHOOK_MAX_RETRY_ATTEMPTS", default=5, cast=int)
WEBHOOK_RETRY_BASE_SECONDS = config("WEBHOOK_RETRY_BASE_SECONDS", default=30, cast=int)

# Shared secret for signed inbound WhatsApp delivery-status callbacks.
WHATSAPP_STATUS_WEBHOOK_SECRET = config("WHATSAPP_STATUS_WEBHOOK_SECRET", default="")
