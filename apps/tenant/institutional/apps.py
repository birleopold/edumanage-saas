from django.apps import AppConfig


class InstitutionalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.institutional"
    verbose_name = "Institutional Education Operations"

    def ready(self):
        from . import academic_records, candidate_readiness, uace_signals  # noqa: F401
