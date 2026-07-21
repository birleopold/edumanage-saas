from django.apps import AppConfig


class ActivitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.activities"
    label = "activities"
    verbose_name = "Activities"

    def ready(self):
        from . import programme_models  # noqa: F401
