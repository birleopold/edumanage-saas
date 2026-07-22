from django.apps import AppConfig


class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.exams"
    label = "exams"

    def ready(self):
        # External and policy models live in separate modules to keep the mature
        # internal-exam model file stable. Importing them registers each model
        # and its lifecycle signals under the exams app.
        from . import (  # noqa: F401
            external_admin,
            external_models,
            policy_models,
            policy_signals,
        )
