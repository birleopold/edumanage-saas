from django.apps import AppConfig


class CourseworkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.coursework"
    label = "coursework"
    verbose_name = "Coursework"

    def ready(self):
        from . import signals  # noqa: F401
