from django.apps import AppConfig

class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant.finance"
    label = "finance"
    def ready(self):
        from . import accounting_models, integration_models, payment_gateway_models, signals  # noqa: F401
