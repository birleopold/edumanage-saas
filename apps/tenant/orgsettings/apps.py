from django.apps import AppConfig


class OrgSettingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.orgsettings"
    label = "orgsettings"
