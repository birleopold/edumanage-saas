from django.apps import AppConfig


class ExamsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.exams"
    label = "exams"

    def ready(self):
        # Phase 6 models live in a separate module to keep the mature internal-exam
        # model file stable. Importing them here registers them under this app.
        from . import external_admin, external_models  # noqa: F401
