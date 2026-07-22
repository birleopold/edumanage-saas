from django.apps import AppConfig


class AcademicsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.academics"
    label = "academics"

    def ready(self):
        from . import pathway_extension_signals, pathway_extensions  # noqa: F401
