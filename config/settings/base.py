from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = config("DJANGO_SECRET_KEY", default="unsafe-dev-key")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=lambda value: [item.strip() for item in value.split(",") if item.strip()])
ENVIRONMENT = config("ENVIRONMENT", default="development")

INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "rest_framework", "widget_tweaks", "apps.tenant.analytics"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "apps.tenant.audit.observability.ObservabilityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "apps.tenant.audit.request_log.RequestLogMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
PUBLIC_SCHEMA_URLCONF = "config.public_urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.debug", "django.template.context_processors.request", "django.template.context_processors.media", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "apps.tenant.orgsettings.context_processors.orgsettings"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
PUBLIC_STATUS_PAGE_ENABLED = config("PUBLIC_STATUS_PAGE_ENABLED", default=True, cast=bool)
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "edumanage-default-locmem"}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "en-us"
TIME_ZONE = config("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "admin_home"
SUPPORT_CONTACT_EMAIL = config("SUPPORT_CONTACT_EMAIL", default="")
AUTHENTICATION_BACKENDS = ["apps.tenant.users.backends.EmailOrUsernameModelBackend", "django.contrib.auth.backends.ModelBackend"]
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",), "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",)}
AUDIT_LOG_ENABLED = config("AUDIT_LOG_ENABLED", default=True, cast=bool)
ADMIN_2FA_REQUIRED = config("ADMIN_2FA_REQUIRED", default=False, cast=bool)
PRIVACY_POLICY_VERSION = config("PRIVACY_POLICY_VERSION", default="1.0")
PRIVACY_ACCEPTANCE_REQUIRED = config("PRIVACY_ACCEPTANCE_REQUIRED", default=False, cast=bool)
FEE_REMINDER_CHANNEL = config("FEE_REMINDER_CHANNEL", default="SMS")
FEE_REMINDER_HANDLER = config("FEE_REMINDER_HANDLER", default="apps.tenant.finance.communication_providers.send_fee_message_provider")
FEE_REMINDER_SMS_HANDLER = config("FEE_REMINDER_SMS_HANDLER", default=None)
FEE_REMINDER_DEFAULT_COUNTRY_CODE = config("FEE_REMINDER_DEFAULT_COUNTRY_CODE", default="256")
FEE_REMINDER_PORTAL_BASE_URL = config("FEE_REMINDER_PORTAL_BASE_URL", default="")
SMS_GATEWAY_URL = config("SMS_GATEWAY_URL", default="")
SMS_GATEWAY_TOKEN = config("SMS_GATEWAY_TOKEN", default="")
SMS_GATEWAY_SENDER_ID = config("SMS_GATEWAY_SENDER_ID", default="EduManage")
SMS_GATEWAY_TIMEOUT_SECONDS = config("SMS_GATEWAY_TIMEOUT_SECONDS", default=15, cast=int)
WHATSAPP_CLOUD_ACCESS_TOKEN = config("WHATSAPP_CLOUD_ACCESS_TOKEN", default="")
WHATSAPP_CLOUD_PHONE_NUMBER_ID = config("WHATSAPP_CLOUD_PHONE_NUMBER_ID", default="")
WHATSAPP_CLOUD_API_VERSION = config("WHATSAPP_CLOUD_API_VERSION", default="v20.0")
WHATSAPP_CLOUD_TIMEOUT_SECONDS = config("WHATSAPP_CLOUD_TIMEOUT_SECONDS", default=15, cast=int)
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@edumanage.local")
FEE_RECEIPT_AUTO_SEND_ON_PAYMENT = config("FEE_RECEIPT_AUTO_SEND_ON_PAYMENT", default=False, cast=bool)
PAYMENT_CALLBACKS_ENABLED = config("PAYMENT_CALLBACKS_ENABLED", default=DEBUG, cast=bool)
MOBILE_MONEY_DRY_RUN_ENABLED = config("MOBILE_MONEY_DRY_RUN_ENABLED", default=DEBUG, cast=bool)
MOBILE_MONEY_TIMEOUT_SECONDS = config("MOBILE_MONEY_TIMEOUT_SECONDS", default=20, cast=int)
MTN_MOMO_COLLECTION_URL = config("MTN_MOMO_COLLECTION_URL", default="")
MTN_MOMO_COLLECTION_TOKEN = config("MTN_MOMO_COLLECTION_TOKEN", default="")
MTN_MOMO_SUBSCRIPTION_KEY = config("MTN_MOMO_SUBSCRIPTION_KEY", default="")
AIRTEL_MONEY_COLLECTION_URL = config("AIRTEL_MONEY_COLLECTION_URL", default="")
AIRTEL_MONEY_COLLECTION_TOKEN = config("AIRTEL_MONEY_COLLECTION_TOKEN", default="")
AIRTEL_MONEY_SUBSCRIPTION_KEY = config("AIRTEL_MONEY_SUBSCRIPTION_KEY", default="")
WEBHOOK_REQUEST_TIMEOUT_SECONDS = config("WEBHOOK_REQUEST_TIMEOUT_SECONDS", default=8, cast=int)
WEBHOOK_MAX_RETRY_ATTEMPTS = config("WEBHOOK_MAX_RETRY_ATTEMPTS", default=5, cast=int)
WEBHOOK_RETRY_BASE_SECONDS = config("WEBHOOK_RETRY_BASE_SECONDS", default=30, cast=int)
WEBHOOK_ALLOW_PRIVATE_TARGETS = config("WEBHOOK_ALLOW_PRIVATE_TARGETS", default=DEBUG, cast=bool)
WEBHOOK_ALLOW_HTTP = config("WEBHOOK_ALLOW_HTTP", default=DEBUG, cast=bool)
WEBHOOK_ALLOWED_HOSTS = config("WEBHOOK_ALLOWED_HOSTS", default="", cast=lambda value: tuple(item.strip().lower() for item in value.split(",") if item.strip()))
WHATSAPP_STATUS_WEBHOOK_SECRET = config("WHATSAPP_STATUS_WEBHOOK_SECRET", default="")
MTN_MOMO_CALLBACK_SECRET = config("MTN_MOMO_CALLBACK_SECRET", default="")
AIRTEL_MONEY_CALLBACK_SECRET = config("AIRTEL_MONEY_CALLBACK_SECRET", default="")
SLOW_REQUEST_THRESHOLD_MS = config("SLOW_REQUEST_THRESHOLD_MS", default=1500, cast=int)
SLOW_QUERY_COUNT_THRESHOLD = config("SLOW_QUERY_COUNT_THRESHOLD", default=75, cast=int)
LOGGING = {"version": 1, "disable_existing_loggers": False, "formatters": {"standard": {"format": "%(levelname)s %(asctime)s %(name)s %(message)s"}}, "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}}, "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True}, "edumanage.observability": {"handlers": ["console"], "level": config("OBSERVABILITY_LOG_LEVEL", default="INFO"), "propagate": False}, "edumanage.security": {"handlers": ["console"], "level": config("SECURITY_LOG_LEVEL", default="INFO"), "propagate": False}, "edumanage.finance": {"handlers": ["console"], "level": config("FINANCE_LOG_LEVEL", default="INFO"), "propagate": False}}}
