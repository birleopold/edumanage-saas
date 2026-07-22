from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.assessments"
    label = "assessments"

    def ready(self):
        from . import policy_models, policy_signals  # noqa: F401
