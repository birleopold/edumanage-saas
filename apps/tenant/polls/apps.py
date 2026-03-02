from django.apps import AppConfig


class PollsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenant.polls'
    label = 'polls'
    verbose_name = 'Polls & Surveys'
