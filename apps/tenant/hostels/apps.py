from django.apps import AppConfig


class HostelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.hostels"
    label = "hostels"

    def ready(self):
        from . import hardening_models  # noqa: F401
