from django.apps import AppConfig


class DutyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenant.duty'
    label = 'duty'
    verbose_name = 'Duty Roster'
