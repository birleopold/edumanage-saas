from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.analytics"
    label = "analytics"

    def ready(self):
        try:
            from . import intelligence_models  # noqa: F401
        except Exception:
            pass
