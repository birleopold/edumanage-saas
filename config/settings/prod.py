from django.core.exceptions import ImproperlyConfigured

from .tenants import *

DEBUG = False
ENVIRONMENT = "production"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("DJANGO_SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_HSTS_SECONDS = config("DJANGO_SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("DJANGO_SECURE_HSTS_PRELOAD", default=False, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"


def _require(condition, message):
    if not condition:
        raise ImproperlyConfigured(message)


_require(bool(SECRET_KEY) and SECRET_KEY != "unsafe-dev-key" and len(SECRET_KEY) >= 50, "DJANGO_SECRET_KEY must be a unique production secret of at least 50 characters.")
_require(ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS, "DJANGO_ALLOWED_HOSTS must list explicit production hosts.")
_require(bool(DATABASES["default"].get("PASSWORD")), "POSTGRES_PASSWORD is required in production.")
_require(MOBILE_MONEY_DRY_RUN_ENABLED is False, "MOBILE_MONEY_DRY_RUN_ENABLED must be false in production.")
_require(WEBHOOK_ALLOW_PRIVATE_TARGETS is False, "WEBHOOK_ALLOW_PRIVATE_TARGETS must be false in production.")
_require(WEBHOOK_ALLOW_HTTP is False, "WEBHOOK_ALLOW_HTTP must be false in production.")
if PAYMENT_CALLBACKS_ENABLED:
    configured_provider_count = 0
    if MTN_MOMO_COLLECTION_URL:
        configured_provider_count += 1
        _require(bool(MTN_MOMO_CALLBACK_SECRET), "MTN_MOMO_CALLBACK_SECRET is required when MTN MoMo is enabled.")
    if AIRTEL_MONEY_COLLECTION_URL:
        configured_provider_count += 1
        _require(bool(AIRTEL_MONEY_CALLBACK_SECRET), "AIRTEL_MONEY_CALLBACK_SECRET is required when Airtel Money is enabled.")
    _require(configured_provider_count > 0, "Configure at least one mobile-money provider when payment callbacks are enabled.")
